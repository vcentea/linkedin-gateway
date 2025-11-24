# Database Ownership & Privileges Guide

## Overview

This guide explains how LinkedIn Gateway handles database ownership and privileges to ensure smooth installations and migrations across all deployment scenarios.

## How It Works

### During Installation (`install.sh`)

When you run the install script, the following happens automatically:

1. **PostgreSQL Container Setup**
   - Docker creates a PostgreSQL user from `DB_USER` env var (default: `linkedin_gateway_user`)
   - Docker creates a database from `DB_NAME` env var (default: `LinkedinGateway`)
   - The `DB_USER` is automatically made the **database owner**

2. **Schema Creation** (`init-scripts/01-create-schema.sql`)
   - Creates all tables, indexes, and constraints
   - Runs as `DB_USER`, so all objects are owned by that user
   - Includes extensions, triggers, and initial data

3. **Privilege Setup** (`init-scripts/02-grant-privileges.sql`) ✨ **NEW!**
   - Grants all privileges on all database objects
   - Sets default privileges for future objects
   - Ensures the user can perform migrations without issues

**Result:** Your application user owns everything and has full control.

---

### During Updates (`update-to-v1.1.sh`)

When you run the update script, it automatically:

1. **Checks Database Ownership**
   - Queries which user owns the tables
   - Detects if there's a mismatch (e.g., tables owned by `postgres`)

2. **Transfers Ownership (if needed)** ✨ **AUTOMATIC!**
   - If tables are owned by another user, automatically transfers them
   - Uses database owner privileges (no superuser required!)
   - Transfers tables, sequences, and views
   - Grants all necessary privileges

3. **Applies Migrations**
   - Adds new columns: `instance_id`, `instance_name`, `browser_info`
   - Creates new indexes for multi-key support
   - All operations succeed because ownership is correct

**Result:** Updates work automatically regardless of how the database was initially set up.

---

## Supported Scenarios

### ✅ Scenario 1: Fresh Installation
```bash
./install.sh
```
- User creates database and owns all objects
- Privileges granted automatically
- **No manual steps required**

### ✅ Scenario 2: Manual Database Setup (Dev Instance)
```bash
# Manually created database where postgres owns tables
./update-to-v1.1.sh
```
- Script detects ownership mismatch
- Automatically transfers ownership
- **No manual intervention needed**

### ✅ Scenario 3: Docker Installation
```bash
docker-compose up -d
```
- Init scripts run automatically
- Ownership and privileges set correctly
- **Just works™**

---

## Cross-Platform Compatibility

All scripts work on:
- ✅ **Linux** (Debian, Ubuntu, CentOS, etc.)
- ✅ **macOS** (Intel and Apple Silicon)
- ✅ **Windows** (Git Bash)
- ✅ **Windows** (WSL/WSL2)

**Requirements:**
- Bash shell (included in Git for Windows)
- Docker (for containerized deployment)
- PostgreSQL client tools (psql, pg_dump)

---

## What Gets Fixed Automatically

### Ownership Issues
```sql
-- Before: Mixed ownership
api_keys       | postgres
users          | postgres
profiles       | linkedin_gateway_user

-- After: Consistent ownership
api_keys       | linkedin_gateway_user
users          | linkedin_gateway_user
profiles       | linkedin_gateway_user
```

### Privilege Issues
```sql
-- Automatically grants:
- ALL PRIVILEGES ON ALL TABLES
- ALL PRIVILEGES ON ALL SEQUENCES
- CREATE privileges on schema
- Default privileges for future objects
```

---

## Manual Fixes (If Needed)

### If Update Fails (Rare)

If the automatic ownership transfer fails, you can manually fix it:

```bash
cd deployment/scripts
./fix-db-ownership.sh
```

This standalone script:
- Checks current ownership
- Transfers everything to the application user
- Verifies the fix
- Safe to run multiple times

### If Database Owner is Wrong

If somehow the database itself has the wrong owner:

```bash
# Connect as postgres superuser
docker exec -it linkedin-gateway-core-db psql -U postgres

# Fix database ownership
ALTER DATABASE LinkedinGateway OWNER TO linkedin_gateway_user;

# Exit and run fix script
\q
cd deployment/scripts
./fix-db-ownership.sh
```

---

## Technical Details

### Why Database Owner Can Transfer Ownership

In PostgreSQL, a database owner has special privileges:
- Can take ownership of any object in their database
- Can grant/revoke privileges
- Can create and drop objects
- **Does not need superuser privileges**

This is why our scripts work without requiring `postgres` superuser access.

### SQL Used for Ownership Transfer

```sql
DO $$
DECLARE
    r RECORD;
BEGIN
    -- Transfer tables
    FOR r IN SELECT tablename FROM pg_tables
             WHERE schemaname = 'public'
               AND tableowner != current_user
    LOOP
        EXECUTE format('ALTER TABLE %I OWNER TO %I',
                      r.tablename, current_user);
    END LOOP;

    -- Transfer sequences
    FOR r IN SELECT sequence_name FROM information_schema.sequences
             WHERE sequence_schema = 'public'
    LOOP
        EXECUTE format('ALTER SEQUENCE %I OWNER TO %I',
                      r.sequence_name, current_user);
    END LOOP;
END $$;
```

---

## Verification

After installation or update, verify everything is correct:

### Check Ownership
```bash
docker exec -it linkedin-gateway-core-db psql \
    -U linkedin_gateway_user \
    -d LinkedinGateway \
    -c "SELECT tablename, tableowner FROM pg_tables WHERE schemaname = 'public';"
```

### Check Privileges
```bash
docker exec -it linkedin-gateway-core-db psql \
    -U linkedin_gateway_user \
    -d LinkedinGateway \
    -c "SELECT grantee, privilege_type FROM information_schema.table_privileges WHERE grantee = 'linkedin_gateway_user' LIMIT 10;"
```

### Check v1.1.0 Columns
```bash
docker exec -it linkedin-gateway-core-db psql \
    -U linkedin_gateway_user \
    -d LinkedinGateway \
    -c "SELECT column_name FROM information_schema.columns WHERE table_name = 'api_keys' AND column_name IN ('instance_id', 'instance_name', 'browser_info');"
```

---

## Troubleshooting

### Error: "must be owner of table"

**Cause:** User doesn't own the table and isn't database owner

**Solution:**
```bash
./fix-db-ownership.sh
```

### Error: "permission denied for schema"

**Cause:** User doesn't have CREATE privileges

**Solution:**
```bash
docker exec -it linkedin-gateway-core-db psql -U postgres -d LinkedinGateway \
    -c "GRANT CREATE ON SCHEMA public TO linkedin_gateway_user;"
```

### Error: "database does not exist"

**Cause:** Database wasn't created properly

**Solution:**
```bash
# Recreate database
docker-compose down
docker volume rm linkedin-gateway-core-postgres-data
./install.sh
```

---

## Best Practices

### For Development
- Use the install script for initial setup
- Update scripts handle ownership automatically
- No manual database configuration needed

### For Production
- Always use install script for deployment
- Keep backups before updates (automatic)
- Monitor logs during updates

### For CI/CD
- Install script is idempotent (safe to re-run)
- Include database verification in pipeline
- Use health checks before deploying

---

## Files Reference

- `install.sh` - Main installation script (auto-runs init scripts)
- `init-scripts/01-create-schema.sql` - Creates database schema
- `init-scripts/02-grant-privileges.sql` - Grants privileges (NEW!)
- `update-to-v1.1.sh` - Update script with auto-ownership fix
- `rollback-from-v1.1.sh` - Rollback script with auto-ownership fix
- `fix-db-ownership.sh` - Standalone ownership fix utility

---

## Summary

✅ **Installation:** Automatically sets correct ownership and privileges
✅ **Updates:** Automatically fixes ownership if needed
✅ **Cross-platform:** Works on Linux, macOS, and Windows
✅ **No manual steps:** Everything is automatic
✅ **Safe:** Creates backups before changes
✅ **Idempotent:** Safe to run multiple times

**You don't need to do anything special - just run the scripts!** 🚀
