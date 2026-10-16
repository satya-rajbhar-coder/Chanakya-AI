"""
Global schema discovery across ALL databases.

Databases are sharded by client: each has the same *logical* schema but the
physical table names may carry a client/partition suffix, e.g.

    user_master__partition_client147   ->  logical: user_master
    user_master__partition_client152   ->  logical: user_master
    contact_sync_corp                  ->  logical: contact_sync_corp

Discovery is done by reflecting each database directly (cached), NOT through a
vector store, so it always reflects the real schema.
"""

import logging
import re
from functools import lru_cache

from sqlalchemy import inspect

from .registry import get_all_database_names, get_engine

logger = logging.getLogger(__name__)

# Matches trailing client / partition suffixes.
_SUFFIX_PATTERNS = (
    re.compile(r"__partition_client\d+$", re.IGNORECASE),
    re.compile(r"__client\d+$", re.IGNORECASE),
    re.compile(r"_client\d+$", re.IGNORECASE),
    re.compile(r"_partition\d+$", re.IGNORECASE),
)


def logical_table_name(table_name: str) -> str:
    """Strip a client/partition suffix so identical tables across databases match."""
    name = table_name
    for pattern in _SUFFIX_PATTERNS:
        stripped = pattern.sub("", name)
        if stripped != name:
            return stripped
    return name


def physical_scope(databases: list[str]) -> tuple[set[str], dict[str, str]]:
    """Reflect the real tables reachable through the given client databases.

    Returns (known, resolve):
      known   - every bare physical table name (lowercased) found in the
                client databases.
      resolve - rewrites for names that are real but not reflected verbatim:
                * a logical (suffix-stripped) name -> its physical table,
                  preferring the first database that has it (the union
                  builder re-maps it per database afterwards);
                * a shared main-database table -> its qualified
                  `<fdw_schema>.<table>` name, so a bare reference the model
                  writes is rewritten to the FDW form.

    Databases that cannot be reflected are skipped. Client tables win over
    shared tables on a name clash.
    """
    known: set[str] = set()
    candidates: dict[str, list[str]] = {}
    for db in databases:
        try:
            tables = list_tables(db)
        except Exception as exc:
            logger.warning("Cannot list tables for %s: %s", db, exc)
            continue
        for table in tables:
            known.add(table.lower())
            candidates.setdefault(logical_table_name(table).lower(), []).append(table)
    resolve: dict[str, str] = {
        logical: physicals[0]
        for logical, physicals in candidates.items()
        if logical not in known
    }
    if databases:
        try:
            for qualified in list_main_tables(databases[0]):
                bare = qualified.rpartition(".")[2].lower()
                if bare not in known:
                    resolve.setdefault(bare, qualified)
        except Exception as exc:
            logger.warning("Cannot list shared tables for scope: %s", exc)
    return known, resolve


def classify_table_type(table_name: str) -> str:
    """Group tables by broad purpose to help relevance ranking."""
    name = table_name.lower()
    if "contact_sync" in name:
        return "contact_sync"
    if "user_master" in name:
        return "user_master"
    if "executive" in name:
        return "executive"
    if "sync" in name:
        return "sync"
    if "master" in name:
        return "master"
    if "partition" in name:
        return "partition"
    return "other"


@lru_cache(maxsize=128)
def list_tables(db: str) -> tuple[str, ...]:
    """Table names of one database (cached). Client-owned tables only."""
    return tuple(sorted(inspect(get_engine(db)).get_table_names()))


@lru_cache(maxsize=128)
def list_main_tables(db: str) -> tuple[str, ...]:
    """Shared main-database tables, reachable THROUGH the client connection
    via the pollmatrix foreign schema (qualified names, cached)."""
    from .registry import main_schema

    schema = main_schema()
    try:
        names = inspect(get_engine(db)).get_table_names(schema=schema)
    except Exception as exc:  # foreign schema not set up on this client DB yet
        logger.warning("Main schema %r unavailable via %s: %s", schema, db, exc)
        return ()
    return tuple(sorted(f"{schema}.{n}" for n in names))


@lru_cache(maxsize=512)
def describe_table_lazy(
    db: str, table: str, question: str = ""
) -> tuple[str, tuple[str, ...]]:
    """Bounded schema string for a table: keys + question-relevant columns first."""
    insp = inspect(get_engine(db))
    if not insp.has_table(table):
        raise LookupError(f"Table {table} not found in {db}")

    pk = set(insp.get_pk_constraint(table).get("constrained_columns") or [])
    fks = insp.get_foreign_keys(table)
    fk_map = {
        c: f"{fk['referred_table']}.{rc}"
        for fk in fks
        for c, rc in zip(fk["constrained_columns"], fk["referred_columns"])
    }
    words = set(re.findall(r"[a-z0-9]+", (question or "").lower()))
    columns = insp.get_columns(table)

    def rank(col):
        name = col["name"]
        parts = set(name.lower().split("_"))
        return (name in pk or name in fk_map, len(words & parts), name.lower() in words)

    columns = sorted(columns, key=rank, reverse=True)
    cols = []
    for c in columns:
        name = c["name"]
        part = f"{name} {str(c['type']).split('(')[0].lower()}"
        if name in pk:
            part += " PK"
        if name in fk_map:
            part += f" FK->{fk_map[name]}"
        cols.append(part)

    related = tuple(
        sorted({fk["referred_table"] for fk in fks} & set(insp.get_table_names()))
    )
    return f"{table}({', '.join(cols)})", related


def discover_logical_tables(databases: list[str]) -> dict[str, dict[str, str]]:
    """
    Map logical table name -> {database: physical table name}.

    Example:
        {"user_master": {"client147": "user_master__partition_client147",
                         "client152": "user_master__partition_client152"}}

    Note: If multiple physical tables in the same database map to the same
    logical name, the LAST one encountered is kept (could indicate a naming issue).
    """
    mapping: dict[str, dict[str, str]] = {}
    for db in databases:
        try:
            tables = list_tables(db)
        except Exception as exc:
            logger.warning("Cannot list tables for %s: %s", db, exc)
            continue
        for table in tables:
            logical = logical_table_name(table)
            mapping.setdefault(logical, {})[db] = table
    return mapping


def rank_logical_tables(
    question: str,
    logical_map: dict[str, dict[str, str]],
    limit: int = 6,
) -> list[str]:
    """Keyword-rank logical table names against the question (no vector store)."""
    q = question.lower()
    words = set(re.findall(r"[a-z0-9]+", q))
    scored: list[tuple[float, str]] = []

    for logical, per_db in logical_map.items():
        name = logical.lower()
        parts = set(re.findall(r"[a-z0-9]+", name))
        score = 0.0
        if name in q:
            score += 10.0
        score += 3.0 * len(parts & words)
        # singular/plural and substring tolerance
        for word in words:
            if len(word) >= 4 and (word in name or name in word):
                score += 2.0
        # prefer tables that exist in more databases (more "global")
        score += 0.5 * len(per_db)
        if score > 0:
            scored.append((score, logical))

    scored.sort(reverse=True)
    return [logical for _, logical in scored[:limit]]


def find_tables_across_databases(
    question: str,
    table_type_filter: str | None = None,
    k: int = 10,
    databases: list[str] | None = None,
) -> list[dict]:
    """
    Find relevant tables across all databases for a question.
    Returns list of dicts with db, table_name, table_type, score.

    Args:
        question: The user's question
        table_type_filter: Optional filter by table type
        k: Max number of logical tables to return
        databases: Optional list of database names to search (if None, auto-discover)
    """
    if databases is None:
        databases = get_all_database_names()
    if not databases:
        return []

    # Discover all logical tables across databases
    logical_map = discover_logical_tables(databases)

    # Filter by table type if specified
    if table_type_filter:
        filtered_map = {
            logical: per_db
            for logical, per_db in logical_map.items()
            if classify_table_type(logical) == table_type_filter
        }
        if filtered_map:
            logical_map = filtered_map

    # Rank logical tables
    ranked_logicals = rank_logical_tables(question, logical_map, limit=k)

    # Convert to flat list of {db, table_name, table_type, score}
    results = []
    for logical in ranked_logicals:
        per_db = logical_map[logical]
        table_type = classify_table_type(logical)
        for db, physical_table in per_db.items():
            results.append(
                {
                    "db": db,
                    "table_name": physical_table,
                    "logical_name": logical,
                    "table_type": table_type,
                }
            )

    return results


def select_tables_global(
    question: str,
    table_type_filter: str | None = None,
    databases: list[str] | None = None,
) -> list[tuple[str, str]]:
    """
    Select relevant (db, table_name) pairs across ALL databases for a question.
    """
    tables = find_tables_across_databases(
        question, table_type_filter=table_type_filter, k=20, databases=databases
    )

    if not tables:
        return []

    # Return unique (db, table_name) pairs
    seen = set()
    result = []
    for t in tables:
        key = (t["db"], t["table_name"])
        if key not in seen:
            seen.add(key)
            result.append(key)

    return result


def build_global_catalog() -> int:
    """
    Build/rebuild the global schema catalog by discovering all tables
    across all client databases and logging the results.
    Returns the total number of logical tables discovered.
    """
    databases = get_all_database_names()
    if not databases:
        logger.warning("No client databases found")
        return 0

    logical_map = discover_logical_tables(databases)
    clear_caches()  # Refresh caches

    total_logical = len(logical_map)
    total_physical = sum(len(per_db) for per_db in logical_map.values())

    logger.info(
        "Global catalog built: %d logical tables across %d databases (%d physical tables)",
        total_logical,
        len(databases),
        total_physical,
    )

    # Log details by type
    by_type = {}
    for logical, per_db in logical_map.items():
        ttype = classify_table_type(logical)
        by_type[ttype] = by_type.get(ttype, 0) + 1

    for ttype, count in sorted(by_type.items()):
        logger.info("  %s: %d tables", ttype, count)

    return total_logical


def clear_caches() -> None:
    """Drop reflection caches (call after catalog rebuilds)."""
    list_tables.cache_clear()
    describe_table_lazy.cache_clear()
