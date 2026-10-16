-- ============================================================================
-- One-time setup per CLIENT database.
--
-- Exposes the shared main database (pollmatrix_db) through a foreign schema
-- so that ALL database communication happens through the client connection:
-- the backend connects only to the client DB and reads shared tables as
-- `pollmatrix.<table>`.
--
-- Usage:
--   psql -h <host> -U <analysis_user> -d <client_database> -f setup_main_db_fdw.sql
--
-- Requirements: the analysis role must be allowed to create FDW objects, or
-- run this as a superuser once. The main DB host/port and credentials below
-- must match your deployment (the FDW schema name is configured in
-- backend/.env as ANALYSIS_MAIN_DB_SCHEMA).
-- ============================================================================

\set main_host 'localhost'
\set main_port '5432'
\set main_db 'pollmatrix_db'
\set main_user 'analysis_readonly'
\set main_password 'CHANGE_ME'
\set main_schema 'pollmatrix'

CREATE EXTENSION IF NOT EXISTS postgres_fdw;

-- One foreign server per main database (idempotent by name).
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_foreign_server WHERE srvname = 'pollmatrix_main_server'
    ) THEN
        EXECUTE format(
            'CREATE SERVER pollmatrix_main_server '
            'FOREIGN DATA WRAPPER postgres_fdw '
            'OPTIONS (host %L, port %L, dbname %L)',
            current_setting('main_host'),
            current_setting('main_port'),
            current_setting('main_db')
        );
    END IF;
END $$;

-- User mapping for the current (read-only) analysis role.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_user_mappings
        WHERE srvname = 'pollmatrix_main_server'
          AND usename = current_user
    ) THEN
        EXECUTE format(
            'CREATE USER MAPPING FOR %I SERVER pollmatrix_main_server '
            'OPTIONS (user %L, password %L)',
            current_user,
            current_setting('main_user'),
            current_setting('main_password')
        );
    END IF;
END $$;

-- Import the main DB public schema as the pollmatrix foreign schema.
DROP SCHEMA IF EXISTS :main_schema CASCADE;
CREATE SCHEMA :main_schema;

IMPORT FOREIGN SCHEMA public
    FROM SERVER pollmatrix_main_server
    INTO :main_schema;

GRANT USAGE ON FOREIGN SERVER pollmatrix_main_server TO PUBLIC;
