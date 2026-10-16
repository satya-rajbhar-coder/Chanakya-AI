from modules.analysis.executor import run_page, stream_csv


def test_pagination(demo_db):
    sql = "SELECT id, name FROM items ORDER BY id"

    first = run_page(demo_db, sql, 0, 100)
    assert first["columns"] == ["id", "name"]
    assert len(first["rows"]) == 100 and first["has_more"] is True

    last = run_page(demo_db, sql, 2, 100)
    assert len(last["rows"]) == 50 and last["has_more"] is False
    assert last["rows"][0][0] == 201


def test_page_size_is_clamped(demo_db):
    from core.config import settings

    page = run_page(demo_db, "SELECT id FROM items", 0, 10_000)
    assert page["page_size"] == settings.ANALYSIS_MAX_PAGE_SIZE


def test_colons_and_percent_in_literals(demo_db):
    page = run_page(demo_db, "SELECT 'a:b' AS x, name FROM items WHERE name LIKE 'item1%'", 0, 5)
    assert page["rows"][0][0] == "a:b"


def test_csv_streams_everything(demo_db):
    text = "".join(stream_csv(demo_db, "SELECT id, name FROM items ORDER BY id"))
    lines = text.strip().splitlines()
    assert lines[0] == "id,name"
    assert len(lines) == 251  # header + 250 rows
