import sqlglot
from collections.abc import Collection, Mapping

from sqlglot import exp


class UnsafeSQL(ValueError):
    pass


_FORBIDDEN = (
    exp.Insert,
    exp.Update,
    exp.Delete,
    exp.Drop,
    exp.Create,
    exp.Alter,
    exp.Merge,
    exp.Command,
    exp.Into,
    exp.TruncateTable,
)


def validate_select(
    sql: str,
    dialect: str,
    allowed_tables: set[str],
    known_tables: Collection[str] = (),
    resolve: Mapping[str, str] | None = None,
) -> str:
    """Return normalized SQL, or raise UnsafeSQL.

    Defence in depth only: the database role must ALSO be read-only.

    allowed_tables is the top-k prompt set. known_tables is the full set of
    real tables in the queried database(s): a model that correctly reaches
    for a real table outside the top-k is accepted, not rejected. resolve
    maps a logical (suffix-stripped) name to its exact physical table; such
    references are rewritten to the physical name in the returned SQL.

    Schema-qualified references are allowed ONLY for the shared main database
    (pollmatrix.<table>), which every client connection exposes through its
    foreign schema. All other cross-schema/cross-database reads are rejected.
    A bare reference to a known shared table is rewritten to its qualified
    FDW form; a logical (suffix-stripped) client-table name is rewritten to
    the exact physical table.
    """
    try:
        statements = [s for s in sqlglot.parse(sql, read=dialect) if s]
    except sqlglot.errors.SqlglotError as exc:
        raise UnsafeSQL(f"Invalid SQL: {exc}") from exc

    if len(statements) != 1:
        raise UnsafeSQL("Exactly one statement is allowed")

    tree = statements[0]
    if not isinstance(tree, exp.Query):
        raise UnsafeSQL("Only SELECT queries are allowed")
    if next(tree.find_all(*_FORBIDDEN), None) is not None:
        raise UnsafeSQL("Data-modifying statements are not allowed")

    for fn in tree.find_all(exp.Anonymous, exp.Func):
        name = (fn.name or "").lower()
        if name.startswith(("pg_", "lo_", "dblink")) or name in {
            "pg_sleep",
            "current_setting",
            "current_database",
            "version",
        }:
            raise UnsafeSQL(f"Function not allowed: {fn.name}")

    from core.config import settings

    main_schema = settings.ANALYSIS_MAIN_DB_SCHEMA.lower()

    ctes = {c.alias_or_name.lower() for c in tree.find_all(exp.CTE)}
    allowed = {t.lower().split(".")[-1] for t in allowed_tables}
    known = {t.lower().split(".")[-1] for t in known_tables}
    mapping = {k.lower(): v for k, v in (resolve or {}).items()}
    tables = list(tree.find_all(exp.Table))

    # Strict scope: a query that reads no table could "answer" from the model's
    # own knowledge, e.g. SELECT 'Paris'.
    if not tables:
        raise UnsafeSQL("The query must read from the database tables")

    for table in tables:
        schema = (table.db or "").lower()
        if schema and schema != main_schema:
            raise UnsafeSQL(
                "Cross-schema or cross-database references are not allowed"
            )
        name = table.name.lower()
        if name in ctes or name in allowed or name in known:
            continue
        physical = mapping.get(name)
        if physical is None:
            raise UnsafeSQL(f"Table not available: {table.name}")
        if "." in physical:
            # Shared table reached through the FDW schema: qualify it.
            fdw_schema, _, bare = physical.rpartition(".")
            table.set("db", exp.to_identifier(fdw_schema))
            table.set("this", exp.to_identifier(bare))
        else:
            table.set("this", exp.to_identifier(physical))

    return tree.sql(dialect=dialect)
