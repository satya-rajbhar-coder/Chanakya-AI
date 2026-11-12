from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI, HTTPException, status
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
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
from modules.conversations.models import Conversation
from modules.intelligence.repository import IntelligenceRepository
from modules.messages.models import Message, Role
from modules.messages.repository import MessageRepository
from modules.messages.schemas import MessageResponse
from modules.messages.services import MessageService
from modules.users.models import User


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
    def mock_plan_and_run(self, question, user_id, client_id=None):
        if client_id == unassigned_id:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Client is not assigned")
        return ("demo", assigned_id, ["items"], "All items", "SELECT id, name FROM items ORDER BY id",
                {"columns": ["id", "name"], "rows": [[i, f"item{i}"] for i in range(1, 101)], "page": 0,
                 "page_size": 100, "has_more": True, "total_time_ms": 10.0})

    monkeypatch.setattr(analysis_service.AnalysisService, "plan_and_run", mock_plan_and_run)

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


def test_query(client):
    http, _, client_id, _, _ = client
    res = http.post("/analysis/query", json={"question": "list items", "client_id": str(client_id)})
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["database"] == "demo"
    assert len(body["result"]["rows"]) == 100 and body["result"]["has_more"]
    assert body["analysis_query_id"]
    assert "token" in body
    assert "sql" in body


def test_saved_query_can_be_reloaded_by_page(client):
    http, _, client_id, _, _ = client
    response = http.post(
        "/analysis/query",
        json={"question": "list items", "client_id": str(client_id)},
    )
    query_id = response.json()["analysis_query_id"]

    page = http.post(
        f"/analysis/history/{query_id}/run?page=2&page_size=30",
    )

    assert page.status_code == 200, page.text
    result = page.json()["result"]
    assert result["page"] == 2
    assert result["page_size"] == 30
    assert [row[0] for row in result["rows"]] == list(range(61, 91))


def test_legacy_chat_turn_links_to_its_saved_query(client):
    http, user_id, client_id, _, engine = client
    response = http.post(
        "/analysis/query",
        json={"question": "list items", "client_id": str(client_id)},
    )
    query_id = response.json()["analysis_query_id"]

    with Session(engine, expire_on_commit=False) as db:
        user = db.get(User, user_id)
        conversation = Conversation(user_id=user_id, title="Saved query")
        db.add(conversation)
        db.flush()
        db.add_all(
            [
                Message(
                    conversation_id=conversation.id,
                    user_id=user_id,
                    role=Role.USER,
                    content="list items",
                ),
                Message(
                    conversation_id=conversation.id,
                    user_id=user_id,
                    role=Role.ASSISTANT,
                    content="Here are the items.",
                ),
            ]
        )
        db.commit()

        messages, _ = MessageService(db).get_messages(
            conversation.id,
            user,
        )

    assistant_message = next(message for message in messages if message.role == Role.ASSISTANT)
    assert str(assistant_message.analysis_query_id) == query_id
    response = MessageResponse.model_validate(assistant_message)
    assert str(response.analysis_query_id) == query_id


def test_new_chat_turn_persists_its_query_link(client):
    http, user_id, client_id, _, engine = client
    response = http.post(
        "/analysis/query",
        json={"question": "list items", "client_id": str(client_id)},
    )
    query_id = response.json()["analysis_query_id"]

    with Session(engine, expire_on_commit=False) as db:
        user = db.get(User, user_id)
        conversation = Conversation(user_id=user_id, title="Saved query")
        db.add(conversation)
        db.commit()
        _, assistant_message = IntelligenceRepository(db, user).save_chat_turn(
            conversation.id,
            "list items",
            "Here are the items.",
            analysis_query_id=UUID(query_id),
        )
        conversation_id = conversation.id
        assistant_message_id = assistant_message.id

    with Session(engine) as db:
        restored_message = MessageRepository(db).get_by_id(
            conversation_id,
            assistant_message_id,
        )
        message_response = MessageResponse.model_validate(restored_message)
        assert str(message_response.analysis_query_id) == query_id


def test_unassigned_client_rejected(client):
    http, user_id, assigned_id, other_id, engine = client
    res = http.post("/analysis/query", json={"question": "list", "client_id": str(other_id)})
    assert res.status_code == 403


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
