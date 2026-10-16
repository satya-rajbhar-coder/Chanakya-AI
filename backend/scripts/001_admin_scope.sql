-- Run once against the APP PostgreSQL database before restarting the updated API.
-- Back up both the app database and pgvector data first. create_all does NOT update existing tables.
ALTER TABLE users ADD COLUMN IF NOT EXISTS role VARCHAR(10) NOT NULL DEFAULT 'user';
ALTER TABLE users ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE;
ALTER TABLE constituencies ADD COLUMN IF NOT EXISTS database_name VARCHAR(100);
ALTER TABLE documents ADD COLUMN IF NOT EXISTS constituency_id UUID REFERENCES constituencies(id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS ix_documents_constituency_id ON documents (constituency_id);

-- IMPORTANT: Existing assemblies have no database mapping. Explicitly set each one
-- to the database name you want before assigning users or allowing analysis:
-- UPDATE constituencies SET database_name = 'MH_150_Oct_2024' WHERE code = '150';
-- Existing uploads have no assembly scope and are intentionally hidden from dashboard
-- users until an admin calls PATCH /api/admin/documents/{id} with constituency_id.
-- A database must be exclusive to one assembly (no row-level filtering is inferred).
-- Resolve any duplicate legacy mappings before adding this unique index:
CREATE UNIQUE INDEX IF NOT EXISTS ix_constituencies_database_name ON constituencies (database_name);
-- After all existing assembly rows have a database_name, optionally enforce:
-- ALTER TABLE constituencies ALTER COLUMN database_name SET NOT NULL;
