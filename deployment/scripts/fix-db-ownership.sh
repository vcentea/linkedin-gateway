#!/bin/bash
# Fix Database Ownership - Transfer all objects to the database owner
# This script ensures the application user owns all database objects
# Safe to run on any instance - will only transfer if needed

set -e

echo "============================================"
echo "LinkedIn Gateway - Fix Database Ownership"
echo "============================================"
echo ""
echo "This script ensures your database user owns all database objects."
echo "This is required for running migrations and updates."
echo ""

# Check if running from correct directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [ ! -f "../../backend/main.py" ]; then
    echo "ERROR: This script must be run from the deployment/scripts directory"
    echo "Current directory: $(pwd)"
    exit 1
fi

echo "Step 1: Loading database configuration..."
echo ""

# Find and load environment variables from .env file
ENV_FILE=""
if [ -f "../../backend/.env" ]; then
    ENV_FILE="../../backend/.env"
    echo "✓ Found: backend/.env"
elif [ -f "../.env" ]; then
    ENV_FILE="../.env"
    echo "✓ Found: deployment/.env"
else
    echo "✗ No .env file found"
    echo "Using defaults"
    export DB_USER=linkedin_gateway_user
    export DB_PASSWORD=postgres
    export DB_NAME=LinkedinGateway
    export DB_HOST=localhost
    export DB_PORT=5432
fi

# Load environment variables if file was found
if [ -n "$ENV_FILE" ]; then
    export $(grep -v '^#' "$ENV_FILE" | grep -E '^DB_' | xargs)
fi

# Set defaults
export DB_USER=${DB_USER:-linkedin_gateway_user}
export DB_PASSWORD=${DB_PASSWORD:-postgres}
export DB_NAME=${DB_NAME:-LinkedinGateway}
export DB_HOST=${DB_HOST:-localhost}
export DB_PORT=${DB_PORT:-5432}

echo ""
echo "Database configuration:"
echo "  Host: $DB_HOST"
echo "  Port: $DB_PORT"
echo "  Database: $DB_NAME"
echo "  User: $DB_USER"
echo ""

export PGPASSWORD=$DB_PASSWORD

# Test connection
echo "Step 2: Testing database connection..."
if ! psql -U $DB_USER -h $DB_HOST -p $DB_PORT -d $DB_NAME -c "SELECT version();" > /dev/null 2>&1; then
    echo "✗ Cannot connect to database"
    echo ""
    echo "Troubleshooting:"
    echo "  1. Check if PostgreSQL is running"
    echo "  2. Verify credentials in .env file"
    echo "  3. If using Docker: docker exec -it <container> psql -U $DB_USER -d $DB_NAME"
    exit 1
fi
echo "✓ Connection successful"
echo ""

# Check current ownership
echo "Step 3: Checking current ownership..."
echo ""

OWNERSHIP_CHECK=$(psql -U $DB_USER -h $DB_HOST -p $DB_PORT -d $DB_NAME -t -c "
SELECT
    COUNT(*) FILTER (WHERE tableowner = '$DB_USER') as owned_by_user,
    COUNT(*) FILTER (WHERE tableowner != '$DB_USER') as owned_by_others,
    COUNT(*) as total
FROM pg_tables
WHERE schemaname = 'public';
" 2>/dev/null)

OWNED_BY_USER=$(echo $OWNERSHIP_CHECK | awk '{print $1}')
OWNED_BY_OTHERS=$(echo $OWNERSHIP_CHECK | awk '{print $2}')
TOTAL_TABLES=$(echo $OWNERSHIP_CHECK | awk '{print $3}')

echo "  Total tables: $TOTAL_TABLES"
echo "  Owned by $DB_USER: $OWNED_BY_USER"
echo "  Owned by others: $OWNED_BY_OTHERS"
echo ""

if [ "$OWNED_BY_OTHERS" -eq "0" ]; then
    echo "✓ All tables are already owned by $DB_USER"
    echo "✓ No changes needed!"
    echo ""
    exit 0
fi

echo "⚠ Some tables are owned by other users"
echo ""
echo "Step 4: Transferring ownership..."
echo ""

# Create SQL script to transfer ownership
TRANSFER_SQL=$(mktemp)

cat > $TRANSFER_SQL << 'EOF'
-- Fix Database Ownership
-- This script transfers ownership of all database objects to the current user
-- Safe to run multiple times

-- Show current user (should be the database owner)
SELECT
    current_user as "Running as",
    current_database() as "Database",
    pg_catalog.pg_get_userbyid(d.datdba) as "DB Owner"
FROM pg_catalog.pg_database d
WHERE d.datname = current_database();

-- Transfer ownership of all tables
DO $$
DECLARE
    r RECORD;
    obj_count INTEGER := 0;
BEGIN
    RAISE NOTICE '=== Transferring Table Ownership ===';

    FOR r IN
        SELECT tablename, tableowner
        FROM pg_tables
        WHERE schemaname = 'public' AND tableowner != current_user
    LOOP
        EXECUTE format('ALTER TABLE %I OWNER TO %I', r.tablename, current_user);
        obj_count := obj_count + 1;
        RAISE NOTICE '  ✓ Transferred table: % (was: %)', r.tablename, r.tableowner;
    END LOOP;

    IF obj_count = 0 THEN
        RAISE NOTICE '  → All tables already owned by current user';
    ELSE
        RAISE NOTICE '  → Transferred % tables', obj_count;
    END IF;
END $$;

-- Transfer ownership of all sequences
DO $$
DECLARE
    r RECORD;
    obj_count INTEGER := 0;
BEGIN
    RAISE NOTICE '=== Transferring Sequence Ownership ===';

    FOR r IN
        SELECT sequence_name, sequence_schema
        FROM information_schema.sequences
        WHERE sequence_schema = 'public'
    LOOP
        EXECUTE format('ALTER SEQUENCE %I OWNER TO %I', r.sequence_name, current_user);
        obj_count := obj_count + 1;
        RAISE NOTICE '  ✓ Transferred sequence: %', r.sequence_name;
    END LOOP;

    IF obj_count = 0 THEN
        RAISE NOTICE '  → No sequences found';
    ELSE
        RAISE NOTICE '  → Transferred % sequences', obj_count;
    END IF;
END $$;

-- Transfer ownership of all views (if any)
DO $$
DECLARE
    r RECORD;
    obj_count INTEGER := 0;
BEGIN
    RAISE NOTICE '=== Transferring View Ownership ===';

    FOR r IN
        SELECT table_name
        FROM information_schema.views
        WHERE table_schema = 'public'
    LOOP
        EXECUTE format('ALTER VIEW %I OWNER TO %I', r.table_name, current_user);
        obj_count := obj_count + 1;
        RAISE NOTICE '  ✓ Transferred view: %', r.table_name;
    END LOOP;

    IF obj_count = 0 THEN
        RAISE NOTICE '  → No views found';
    ELSE
        RAISE NOTICE '  → Transferred % views', obj_count;
    END IF;
END $$;

-- Grant all privileges on all objects (redundant but ensures everything works)
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO CURRENT_USER;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO CURRENT_USER;

-- Verification: Show final ownership
SELECT
    '=== Verification ===' as status;

SELECT
    COUNT(*) FILTER (WHERE tableowner = current_user) as "Tables owned by user",
    COUNT(*) FILTER (WHERE tableowner != current_user) as "Tables owned by others",
    COUNT(*) as "Total tables"
FROM pg_tables
WHERE schemaname = 'public';

-- Show any remaining tables not owned by current user (should be none)
SELECT
    tablename as "Table",
    tableowner as "Owner"
FROM pg_tables
WHERE schemaname = 'public' AND tableowner != current_user
ORDER BY tablename;

EOF

# Execute the ownership transfer
psql -U $DB_USER -h $DB_HOST -p $DB_PORT -d $DB_NAME -f $TRANSFER_SQL

if [ $? -ne 0 ]; then
    echo "✗ Failed to transfer ownership"
    echo ""
    echo "Possible causes:"
    echo "  1. User is not the database owner"
    echo "  2. Insufficient privileges"
    echo ""
    echo "To fix manually:"
    echo "  docker exec -it <db-container> psql -U postgres -d $DB_NAME"
    echo "  ALTER DATABASE $DB_NAME OWNER TO $DB_USER;"
    rm $TRANSFER_SQL
    exit 1
fi

rm $TRANSFER_SQL

echo ""
echo "============================================"
echo "✓ Ownership Transfer Complete!"
echo "============================================"
echo ""
echo "All database objects are now owned by: $DB_USER"
echo ""
echo "You can now run migrations and updates:"
echo "  ./update-to-v1.1.sh"
echo ""
