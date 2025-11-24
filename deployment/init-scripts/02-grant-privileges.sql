-- ============================================================================
-- LinkedIn Gateway - Grant Full Privileges
-- ============================================================================
-- This script ensures the application user has all necessary privileges
-- for current and future database operations including migrations
-- ============================================================================

-- Show current context
SELECT
    current_user as "Running as",
    current_database() as "Database",
    pg_catalog.pg_get_userbyid(d.datdba) as "DB Owner"
FROM pg_catalog.pg_database d
WHERE d.datname = current_database();

-- Grant all privileges on database
-- Use current_database() to handle case-sensitive database names correctly
DO $$
BEGIN
    EXECUTE format('GRANT ALL PRIVILEGES ON DATABASE %I TO %I', 
                   current_database(), current_user);
END $$;

-- Grant all privileges on schema
GRANT ALL PRIVILEGES ON SCHEMA public TO CURRENT_USER;

-- Grant all privileges on all tables
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO CURRENT_USER;

-- Grant all privileges on all sequences
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO CURRENT_USER;

-- Grant all privileges on all functions
GRANT ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA public TO CURRENT_USER;

-- Set default privileges for future objects created by this user
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT ALL ON TABLES TO CURRENT_USER;

ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT ALL ON SEQUENCES TO CURRENT_USER;

ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT ALL ON FUNCTIONS TO CURRENT_USER;

-- Ensure the user can create objects
-- Note: The user should already be the database owner, but this is explicit
DO $$
BEGIN
    -- Grant CREATE on schema (allows creating new tables, indexes, etc.)
    EXECUTE format('GRANT CREATE ON SCHEMA public TO %I', current_user);

    RAISE NOTICE 'Granted full privileges to: %', current_user;
END $$;

-- Verification: Show granted privileges
SELECT
    grantee,
    privilege_type,
    is_grantable
FROM information_schema.table_privileges
WHERE grantee = current_user
    AND table_schema = 'public'
LIMIT 10;

-- Show summary
SELECT
    'Privilege setup complete for: ' || current_user as "Status";
