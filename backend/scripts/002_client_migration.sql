-- Migration: Replace Constituency/Assembly with Client model
-- Run once against the APP PostgreSQL database before restarting the updated API.
-- Back up both the app database and pgvector data first. create_all does NOT update existing tables.

-- 1. Create new clients table
CREATE TABLE IF NOT EXISTS clients (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code VARCHAR(100) UNIQUE NOT NULL,
    name VARCHAR(200) NOT NULL,
    database_name VARCHAR(100) NOT NULL UNIQUE,
    client_identifier VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 2. Create new user_clients table
CREATE TABLE IF NOT EXISTS user_clients (
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    is_primary BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (user_id, client_id)
);

-- 3. Migrate data from constituencies to clients (if constituencies table exists)
DO $$
DECLARE
    v_constituency RECORD;
    v_client_id UUID;
BEGIN
    -- Check if constituencies table exists
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'constituencies') THEN
        -- Migrate each constituency to a client
        FOR v_constituency IN SELECT * FROM constituencies WHERE database_name IS NOT NULL LOOP
            -- Generate a client_identifier from the code (e.g., "MH_150" -> "client150")
            -- or use a default pattern
            BEGIN
                INSERT INTO clients (code, name, database_name, client_identifier, is_active, created_at)
                VALUES (
                    v_constituency.code,
                    v_constituency.name,
                    v_constituency.database_name,
                    'client' || regexp_replace(v_constituency.code, '\D', '', 'g'),
                    TRUE,
                    v_constituency.created_at
                )
                ON CONFLICT (database_name) DO NOTHING
                RETURNING id INTO v_client_id;
                
                -- If insert was skipped due to conflict, get the existing client id
                IF v_client_id IS NULL THEN
                    SELECT id INTO v_client_id FROM clients WHERE database_name = v_constituency.database_name;
                END IF;
                
                -- Migrate user assignments
                IF v_client_id IS NOT NULL THEN
                    INSERT INTO user_clients (user_id, client_id, is_primary, created_at)
                    SELECT uc.user_id, v_client_id, uc.is_primary, uc.created_at
                    FROM user_constituencies uc
                    WHERE uc.constituency_id = v_constituency.id
                    ON CONFLICT (user_id, client_id) DO NOTHING;
                END IF;
            EXCEPTION WHEN OTHERS THEN
                RAISE NOTICE 'Failed to migrate constituency %: %', v_constituency.id, SQLERRM;
            END;
        END LOOP;
    END IF;
END $$;

-- 4. Add client_id column to documents table (if not exists)
ALTER TABLE documents ADD COLUMN IF NOT EXISTS client_id UUID REFERENCES clients(id) ON DELETE SET NULL;

-- 5. Migrate documents from constituency_id to client_id
DO $$
DECLARE
    v_doc RECORD;
    v_client_id UUID;
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'documents' AND column_name = 'constituency_id') THEN
        FOR v_doc IN SELECT id, constituency_id FROM documents WHERE constituency_id IS NOT NULL LOOP
            -- Find the client that has the same database as the constituency
            SELECT c.id INTO v_client_id
            FROM clients c
            JOIN constituencies con ON con.database_name = c.database_name
            WHERE con.id = v_doc.constituency_id
            LIMIT 1;
            
            IF v_client_id IS NOT NULL THEN
                UPDATE documents SET client_id = v_client_id WHERE id = v_doc.id;
            END IF;
        END LOOP;
    END IF;
END $$;

-- 6. Create index on client_id
CREATE INDEX IF NOT EXISTS ix_documents_client_id ON documents (client_id);

-- 7. Create unique index on client code (already defined in table creation)
-- CREATE UNIQUE INDEX IF NOT EXISTS ix_clients_code ON clients (code);

-- 8. Create unique index on client_identifier (already defined in table creation)
-- CREATE UNIQUE INDEX IF NOT EXISTS ix_clients_client_identifier ON clients (client_identifier);

-- 9. After migration is complete and verified, you can optionally drop the old tables:
-- DROP TABLE IF EXISTS user_constituencies CASCADE;
-- DROP TABLE IF EXISTS constituencies CASCADE;
-- ALTER TABLE documents DROP COLUMN IF EXISTS constituency_id;

-- NOTE: Keep the old tables until you've verified the migration works correctly.
-- The old tables are left in place for rollback capability.