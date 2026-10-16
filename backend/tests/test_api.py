from uuid import uuid4
import json

import pytest
from fastapi import FastAPI, HTTPException, status
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from api.dependencies import get_current_user
from database.base import Base
from database.session import get_db
from modules.analysis import router as analysis_router
from modules.analysis import service as analysis_service
from modules.analysis.models import Client, UserClient
from modules.users.models import User
from modules.documents.models import Document
from modules.documents.repository import DocumentRepository


@compiles(JSONB, "sqlite")
def compile_jsonb(element, compiler, **kw):
    return "TEXT"


@pytest.fixture
def client(demo_db, monkeypatch):
    import api.router  # noqa: F401 -- register all ORM models

    app_engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(app_engine)
    user = User(id=uuid4(), name="Analyst", email="analyst@example.com", hashed_password="unused")
    client1 = Client(code="CLIENT1", name="Test Client", database_name="demo", client_identifier="client1")
    client2 = Client(code="CLIENT2", name="Other Client", database_name="not_configured", client_identifier="client2")
    with Session(app_engine, expire_on_commit=False) as db:
        db.add_all([user, client1, client2])
        db.flush()
        db.add(UserClient(user_id=user.id, client_id=client1.id))
        db.commit()
        assigned_id, unassigned_id = client1.id, client2.id

    # Mock the service methods
    def mock_plan_and_run(question, client_id, previous_sql, user_id, db_session):
        if client_id == unassigned_id:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Client is not assigned")
        return ("demo", assigned_id, ["items"], "All items", "SELECT id, name FROM items ORDER BY id", 
                {"columns": ["id", "name"], "rows": [[i, f"item{i}"] for i in range(1, 101)], "page": 0, "page_size": 100, "has_more": True, "total_time_ms": 10.0})

    monkeypatch.setattr(analysis_service.AnalysisService, "plan_and_run", mock_plan_and_run)
    # Mock the page/executor layer (not get_rows) so result-token
    # validation in get_rows/export_rows still runs.
    def mock_run_page(db, sql, page, page_size):
        start = page * page_size
        end = start + page_size
        all_rows = [[i, f"item{i}"] for i in range(1, 251)]
        return {"columns": ["id", "name"], "rows": all_rows[start:end], "page": page, "page_size": page_size, "has_more": end < len(all_rows), "total_time_ms": 10.0}
    monkeypatch.setattr(analysis_service, "run_page", mock_run_page)
    def mock_stream_csv(db, sql):
        yield "id,name\n"
        for i in range(1, 251):
            yield f"{i},item{i}\n"
    monkeypatch.setattr(analysis_service, "stream_csv", mock_stream_csv)
    
    from modules.admin.router import router as admin_router
    from modules.auth.router import router as auth_router
    from modules.documents.router import router as documents_router
    app = FastAPI()
    app.include_router(analysis_router.router)
    app.include_router(admin_router)
    app.include_router(auth_router)
    app.include_router(documents_router)
    app.dependency_overrides[get_current_user] = lambda: user

    def session():
        with Session(app_engine) as db:
            yield db

    app.dependency_overrides[get_db] = session
    yield TestClient(app), user.id, assigned_id, unassigned_id, app_engine
    app_engine.dispose()


def test_query_page_and_export(client):
    http, _, client_id, _, _ = client
    res = http.post("/analysis/query", json={"question": "list items", "client_id": str(client_id)})
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["database"] == "demo"
    assert len(body["result"]["rows"]) == 100 and body["result"]["has_more"]

    page3 = http.post("/analysis/rows", json={"token": body["token"], "page": 2, "page_size": 100})
    assert page3.status_code == 200
    assert len(page3.json()["rows"]) == 50

    csv_res = http.post("/analysis/export", json={"token": body["token"]})
    assert csv_res.status_code == 200
    assert len(csv_res.text.strip().splitlines()) == 251


def test_token_of_another_user_is_rejected(client):
    http, _, client_id, _, _ = client
    foreign = analysis_service.AnalysisService.sign_result(uuid4(), "demo", "SELECT 1", client_id)
    assert http.post("/analysis/rows", json={"token": foreign}).status_code == 403


def test_tampered_token_is_rejected(client):
    http, *_ = client
    res = http.post("/analysis/rows", json={"token": "not-a-token"})
    assert res.status_code == 400


def test_unassigned_client_and_revoked_token(client):
    http, user_id, assigned_id, other_id, engine = client
    res = http.post("/analysis/query", json={"question": "list", "client_id": str(other_id)})
    assert res.status_code == 403
    token = http.post("/analysis/query", json={"question": "list", "client_id": str(assigned_id)}).json()["token"]
    with Session(engine) as db:
        row = db.scalar(select(UserClient).where(UserClient.user_id == user_id))
        db.delete(row)
        db.commit()
    assert http.post("/analysis/rows", json={"token": token}).status_code == 403
    assert http.post("/analysis/export", json={"token": token}).status_code == 403


def test_admin_only_registration_and_ingestion(client):
    http, user_id, client_id, _, engine = client
    assert http.post("/auth/register", json={}).status_code == 404
    assert http.get("/admin/users").status_code == 403
    assert http.post("/admin/users", json={}).status_code == 403
    assert http.post("/documents", data={"user_ids": json.dumps([str(user_id)])}, files={"file": ("a.txt", b"test")}).status_code == 403
    assert http.delete(f"/documents/{uuid4()}").status_code == 403
    with Session(engine) as db:
        user = db.get(User, user_id)
        user.role = "admin"
        db.commit()
    http.app.dependency_overrides[get_current_user] = lambda: User(
        id=user_id, name="Admin", email="admin@example.com", role="admin", is_active=True
    )
    created = http.post("/admin/users", json={
        "name": "New user", "email": "new@example.com", "password": "verysecretpassword",
        "client_ids": [str(client_id)],
    })
    assert created.status_code == 201, created.text
    assert created.json()["client_ids"] == [str(client_id)]
    assert created.json()["role"] == "user"
    assert http.put(f"/admin/users/{created.json()['id']}/assignments", json={"client_ids": []}).status_code == 200


def test_document_visibility_tracks_assignments(client):
    http, user_id, assigned_id, other_id, engine = client
    with Session(engine, expire_on_commit=False) as db:
        user = db.get(User, user_id)
        db.add_all([
            Document(user_id=user_id, client_id=assigned_id, filename="visible.txt", size_bytes=1),
            Document(user_id=user_id, client_id=other_id, filename="private.txt", size_bytes=1),
            Document(user_id=user_id, filename="legacy.txt", size_bytes=1),
        ])
        db.commit()
        assert [doc.filename for doc in DocumentRepository(db).get_all(user)] == ["visible.txt"]
        assert DocumentRepository(db).count_visible(user) == 1
    assert [doc["filename"] for doc in http.get("/documents").json()] == ["visible.txt"]
    with Session(engine) as db:
        db.delete(db.scalar(select(UserClient).where(UserClient.user_id == user_id)))
        db.commit()
    assert http.get("/documents").json() == []


def test_unsafe_sql_from_llm_is_blocked(monkeypatch, demo_db):
    """Test that unsafe SQL from LLM is blocked - uses separate setup to avoid fixture mock."""
    import api.router  # noqa: F401

    app_engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(app_engine)
    user = User(id=uuid4(), name="Analyst", email="analyst@example.com", hashed_password="unused")
    client1 = Client(code="CLIENT1", name="Test Client", database_name="demo", client_identifier="client1")
    with Session(app_engine, expire_on_commit=False) as db:
        db.add_all([user, client1])
        db.flush()
        db.add(UserClient(user_id=user.id, client_id=client1.id))
        db.commit()
        assigned_id = client1.id

    # Mock generate_sql to return unsafe SQL (patch where it is looked up)
    monkeypatch.setattr(
        analysis_service,
        "generate_sql",
        lambda *a, **k: {"title": "x", "sql": "DROP TABLE items", "reason": None},
    )
    # Mock select_tables and describe_table (patched where used)
    monkeypatch.setattr(analysis_service, "select_tables", lambda q, db: (db, ["items"]))
    monkeypatch.setattr(analysis_service, "describe_table", lambda db, t, q="": ("items(id int, name text)", ()))
    
    from modules.admin.router import router as admin_router
    from modules.auth.router import router as auth_router
    from modules.documents.router import router as documents_router
    app = FastAPI()
    app.include_router(analysis_router.router)
    app.include_router(admin_router)
    app.include_router(auth_router)
    app.include_router(documents_router)
    app.dependency_overrides[get_current_user] = lambda: user

    def session():
        with Session(app_engine) as db:
            yield db

    app.dependency_overrides[get_db] = session
    http = TestClient(app)
    
    res = http.post("/analysis/query", json={"question": "drop it", "client_id": str(assigned_id)})
    assert res.status_code == 422
    
    app_engine.dispose()