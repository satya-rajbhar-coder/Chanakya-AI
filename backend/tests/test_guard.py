import pytest
import sqlalchemy as sa

from modules.analysis import global_catalog
from modules.analysis.guard import UnsafeSQL, validate_select

ALLOWED = {"orders", "customers"}


def test_allows_simple_select():
    out = validate_select("SELECT id FROM orders WHERE id > 5", "postgres", ALLOWED)
    assert out.upper().startswith("SELECT")


def test_allows_cte_and_join():
    sql = """
        WITH big AS (SELECT * FROM orders WHERE total > 100)
        SELECT c.name FROM big JOIN customers c ON c.id = big.customer_id
    """
    assert validate_select(sql, "postgres", ALLOWED)


def test_allows_main_schema_reference():
    """Shared main-DB tables are read through the client connection."""
    sql = "SELECT u.name FROM pollmatrix.users u JOIN orders o ON o.user_id = u.id"
    assert validate_select(sql, "postgres", {"orders", "users"})


def test_rejects_main_schema_table_not_allowed():
    with pytest.raises(UnsafeSQL):
        validate_select("SELECT * FROM pollmatrix.secrets", "postgres", ALLOWED)


@pytest.mark.parametrize(
    "sql",
    [
        "DROP TABLE orders",
        "UPDATE orders SET total = 0",
        "DELETE FROM orders",
        "INSERT INTO orders (id) VALUES (1)",
        "SELECT 1; SELECT 2",
        "SELECT * FROM secrets",
        "SELECT pg_sleep(10)",
        "SELECT * FROM other_schema.orders",
        "SELECT * FROM other_db.public.orders",
    ],
)
def test_rejects_unsafe_sql(sql):
    with pytest.raises(UnsafeSQL):
        validate_select(sql, "postgres", ALLOWED)


def _sqlite_db(tmp_path, name, ddl):
    url = f"sqlite:///{tmp_path / name}"
    engine = sa.create_engine(url)
    with engine.begin() as conn:
        for stmt in ddl:
            conn.execute(sa.text(stmt))
    engine.dispose()
    return url


def test_accepts_real_table_missing_from_topk_and_executes(tmp_path, monkeypatch):
    """The model correctly used executive_master, but the top-k prompt set
    only contained activity_details_corp. Scope must come from reflection."""
    url = _sqlite_db(
        tmp_path,
        "case.db",
        [
            "CREATE TABLE executive_master (executive_id INTEGER PRIMARY KEY, full_name TEXT, mobile_no TEXT)",
            "CREATE TABLE activity_details_corp (executive_id INTEGER, screen_name TEXT)",
            "INSERT INTO executive_master VALUES (7, 'Asha', '99999')",
            "INSERT INTO activity_details_corp VALUES (7, 'SMSActivity')",
        ],
    )
    monkeypatch.setattr(
        global_catalog, "get_engine", lambda name: sa.create_engine(url)
    )
    global_catalog.list_tables.cache_clear()
    global_catalog.list_main_tables.cache_clear()
    try:
        known, resolve = global_catalog.physical_scope(["anydb"])
    finally:
        global_catalog.list_tables.cache_clear()
        global_catalog.list_main_tables.cache_clear()
    assert "executive_master" in known

    sql = (
        "SELECT DISTINCT e.executive_id, e.full_name, e.mobile_no "
        "FROM executive_master AS e "
        "JOIN activity_details_corp AS a ON a.executive_id = e.executive_id "
        "WHERE a.screen_name = 'SMSActivity'"
    )
    # Top-k prompt set misses executive_master -> previously rejected.
    out = validate_select(sql, "sqlite", {"activity_details_corp"}, known, resolve)

    with sa.create_engine(url).connect() as conn:
        rows = conn.execute(sa.text(out)).all()
    assert rows == [(7, "Asha", "99999")]


def test_rewrites_logical_name_to_physical(tmp_path, monkeypatch):
    url = _sqlite_db(
        tmp_path, "suffixed.db", ["CREATE TABLE user_master__partition_client9 (id INTEGER)"]
    )
    monkeypatch.setattr(
        global_catalog, "get_engine", lambda name: sa.create_engine(url)
    )
    global_catalog.list_tables.cache_clear()
    global_catalog.list_main_tables.cache_clear()
    try:
        known, resolve = global_catalog.physical_scope(["anydb"])
    finally:
        global_catalog.list_tables.cache_clear()
        global_catalog.list_main_tables.cache_clear()
    assert resolve == {"user_master": "user_master__partition_client9"}

    out = validate_select("SELECT id FROM user_master", "sqlite", set(), known, resolve)
    assert "user_master__partition_client9" in out


def test_sharded_logical_name_resolves_to_first_database(monkeypatch):
    """The same logical table exists as differently-suffixed physical tables
    across databases. The guard rewrites to the first database's physical
    name; the union builder re-maps it per database."""
    monkeypatch.setattr(
        global_catalog,
        "list_tables",
        lambda db: ("user_master__partition_client9",)
        if db == "db1"
        else ("user_master__partition_client12",),
    )
    global_catalog.list_main_tables.cache_clear()
    try:
        known, resolve = global_catalog.physical_scope(["db1", "db2"])
    finally:
        global_catalog.list_main_tables.cache_clear()
    assert resolve == {"user_master": "user_master__partition_client9"}
    out = validate_select("SELECT id FROM user_master", "postgres", set(), known, resolve)
    assert "user_master__partition_client9" in out


def test_rewrites_bare_shared_table_to_fdw_schema(tmp_path, monkeypatch):
    """The model wrote executive_master bare, but that table only exists in
    the shared main database, exposed through the pollmatrix FDW schema. The
    guard must rewrite it to pollmatrix.executive_master, not reject it."""
    url = _sqlite_db(
        tmp_path,
        "fdw.db",
        [
            "CREATE TABLE activity_details_corp (executive_id INTEGER, screen_name TEXT)",
            "INSERT INTO activity_details_corp VALUES (7, 'SMSActivity')",
        ],
    )
    monkeypatch.setattr(
        global_catalog, "get_engine", lambda name: sa.create_engine(url)
    )
    monkeypatch.setattr(
        global_catalog,
        "list_main_tables",
        lambda db: ("pollmatrix.executive_master",),
    )
    global_catalog.list_tables.cache_clear()
    try:
        known, resolve = global_catalog.physical_scope(["anydb"])
    finally:
        global_catalog.list_tables.cache_clear()
    assert resolve == {"executive_master": "pollmatrix.executive_master"}

    sql = (
        "SELECT DISTINCT e.executive_id, e.full_name, e.mobile_no "
        "FROM executive_master AS e "
        "JOIN activity_details_corp AS a ON a.executive_id = e.executive_id "
        "WHERE a.screen_name = 'SMSActivity'"
    )
    out = validate_select(sql, "sqlite", {"activity_details_corp"}, known, resolve)
    assert "pollmatrix.executive_master" in out
    assert "executive_master__" not in out


def test_client_table_shadows_shared_table_with_same_name(tmp_path, monkeypatch):
    """A bare name that exists as a real client table is used locally, not
    rewritten to the shared FDW table."""
    url = _sqlite_db(tmp_path, "local.db", ["CREATE TABLE client_master (id INTEGER)"])
    monkeypatch.setattr(
        global_catalog, "get_engine", lambda name: sa.create_engine(url)
    )
    monkeypatch.setattr(
        global_catalog,
        "list_main_tables",
        lambda db: ("pollmatrix.client_master", "pollmatrix.executive_master"),
    )
    global_catalog.list_tables.cache_clear()
    try:
        known, resolve = global_catalog.physical_scope(["anydb"])
    finally:
        global_catalog.list_tables.cache_clear()
    assert resolve == {"executive_master": "pollmatrix.executive_master"}
    out = validate_select("SELECT id FROM client_master", "sqlite", set(), known, resolve)
    assert "pollmatrix." not in out


def test_guard_accepts_prompt_shared_tables_as_bare_without_fdw_reflection(
    tmp_path, monkeypatch
):
    """The user's failing scenario end-to-end: FDW reflection returns nothing
    at guard time, but the shared tables documented in the system prompt must
    still be accepted as bare names — never rewritten to a qualified
    pollmatrix.<table> form, which does not exist on client connections."""
    from modules.analysis.service import AnalysisService

    url = _sqlite_db(
        tmp_path,
        "client.db",
        [
            "CREATE TABLE activity_details_corp (executive_id INTEGER, screen_name TEXT)",
            "INSERT INTO activity_details_corp VALUES (7, 'SMSActivity')",
        ],
    )
    monkeypatch.setattr(
        global_catalog, "get_engine", lambda name: sa.create_engine(url)
    )
    monkeypatch.setattr(global_catalog, "list_main_tables", lambda db: ())
    global_catalog.list_tables.cache_clear()
    try:
        sql = (
            "SELECT DISTINCT e.executive_id, e.full_name, e.mobile_no, "
            "e.designation_id, e.is_active "
            "FROM executive_master AS e "
            "JOIN activity_details_corp AS a ON a.executive_id = e.executive_id "
            "WHERE a.screen_name = 'SMSActivity'"
        )
        out = AnalysisService._validate_guarded(
            sql, "sqlite", {"activity_details_corp"}, ["anydb"]
        )
    finally:
        global_catalog.list_tables.cache_clear()
    # Shared tables stay bare; no pollmatrix. prefix is appended.
    assert "pollmatrix." not in out
    assert "executive_master AS e" in out
    assert "Table not available" not in out


def test_unknown_table_still_rejected():
    with pytest.raises(UnsafeSQL, match="Table not available"):
        validate_select(
            "SELECT * FROM hallucinated_table",
            "postgres",
            {"orders"},
            {"orders", "customers"},
            {},
        )
