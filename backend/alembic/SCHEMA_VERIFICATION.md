# Schema Enforcement System

## Simple Approach: Just Check and Fix

We keep it simple: **Check if columns exist, add them if they don't.**

No complex verification, no migration tracking - just ensure the schema is correct.

## Problem This Solves

**The Issue:**
Alembic tracks which migrations have been run in the `alembic_version` table, but it **doesn't verify that the migration actually succeeded**. This can cause situations where:

1. Alembic marks a migration as "done" in `alembic_version`
2. Migration runs but encounters an error (DB connection issue, permissions, etc.)
3. Database columns/tables don't actually get created
4. Alembic thinks everything is fine and skips the migration on next run
5. **Application crashes** because expected columns are missing

**Real Example:**
```
ERROR: column api_keys.webhook_url does not exist
```

Even though:
- The migration file `add_webhook_fields_to_api_keys.py` exists
- Alembic says it ran
- The migration uses safe `add_columns_if_not_exist` helpers

## The Solution

We've implemented a **schema verification system** that runs **after** Alembic migrations to:

1. ✅ Check if the **actual database schema** matches expectations
2. ✅ Detect partial migration failures
3. ✅ **Automatically fix** missing columns/indexes
4. ✅ Work regardless of what Alembic thinks the migration state is

## How It Works

### 1. Schema Enforcement Script

**File:** `backend/alembic/ensure_schema.py`

This script is **simple and direct**:
- Checks if each required column exists
- Adds it if it doesn't
- That's it!

**Usage:**

```bash
# Just run it - it will check and fix automatically
python -m alembic.ensure_schema
```

**Example Output:**

```
============================================================
Ensuring Database Schema
============================================================

Checking api_keys table...
  ✓ api_keys.id exists
  ✓ api_keys.user_id exists
  ...
  ⚠ api_keys.webhook_url missing - adding now...
  ✓ api_keys.webhook_url added successfully
  ⚠ api_keys.webhook_headers missing - adding now...
  ✓ api_keys.webhook_headers added successfully

============================================================
✅ Schema fixed - 2 item(s) added
============================================================
```

### 2. Integrated into Update Scripts

Both `update_v2.sh` and `update_v2.bat` now:

1. Run `alembic upgrade head` (migrations)
2. **NEW:** Run `ensure_schema.py` (check and fix)
3. Continue with health checks

**Update Script Flow:**

```bash
[5/6] Running migrations...
  ℹ Running alembic upgrade head...
  ✓ Migrations applied
  ℹ Current migration state:
    add_webhook_fields (head)
  ℹ Ensuring schema is correct...
  ✓ Schema updated - missing columns added
```

### 3. Adding New Required Columns

**File:** `backend/alembic/ensure_schema.py`

Just add a new `ensure_column()` call:

```python
async def ensure_schema():
    print("Checking api_keys table...")

    # Existing columns
    await ensure_column("api_keys", "webhook_url", "VARCHAR(1024)")
    await ensure_column("api_keys", "webhook_headers", "JSONB NOT NULL DEFAULT '{}'::jsonb")

    # Add your new column here
    await ensure_column("api_keys", "new_column", "VARCHAR(255)")
```

**That's it!** Next time the update script runs, it will add the column if it's missing.

## Why This Matters

### Before (Alembic Only)

❌ **Alembic says:** "Migration `add_webhook_fields` is done"
❌ **Database reality:** Columns don't exist
❌ **Result:** App crashes with "column does not exist"
❌ **Fix required:** Manual SQL or database reset

### After (With Verification)

✅ **Alembic says:** "Migration is done"
✅ **Verification checks:** "Actually, columns are missing"
✅ **Auto-fix runs:** "Adding missing columns now"
✅ **Result:** App works correctly
✅ **Fix required:** None - automatic

## Common Scenarios

### Scenario 1: Partial Migration Failure

**What happened:**
- DB connection dropped mid-migration
- Only 1 of 2 columns got created
- Alembic marked it as complete

**How verification helps:**
```bash
./update_v2.sh saas

# Output:
  ✓ Migrations applied
  ⚠ Schema issues detected - attempting auto-fix...
  ✓ Schema fixed successfully
```

### Scenario 2: Manual Column Deletion

**What happened:**
- Someone manually dropped a column
- Alembic has no idea

**How verification helps:**
```bash
python -m alembic.verify_schema --fix

# Output:
❌ Missing column: webhook_url
🔧 Fixing issues...
✅ Fixed: webhook_url
```

### Scenario 3: Environment Mismatch

**What happened:**
- Dev has migrations, production doesn't
- Deployment updates code but migrations fail silently

**How verification helps:**
- Update script detects mismatch immediately
- Auto-fixes on the spot
- No downtime or manual intervention needed

## Manual Usage

### Ensure Schema is Correct

```bash
# In Docker container
docker compose -f docker-compose.yml -f docker-compose.saas.yml \
    exec backend python -m alembic.ensure_schema

# Or connect to container
docker exec -it linkedin-gateway-saas-api bash
cd /app
python -m alembic.ensure_schema
```

It automatically checks and fixes - no flags needed!

### Add New Required Columns

Edit `ensure_schema.py` and add your columns:

```python
async def ensure_schema():
    print("Checking api_keys table...")

    # Just add new ensure_column() calls
    await ensure_column("api_keys", "your_new_column", "VARCHAR(255)")
    await ensure_column("users", "another_column", "INTEGER DEFAULT 0")
```

## Benefits

### 🛡️ Safety
- Catches partial migration failures
- Detects schema drift
- Prevents "column does not exist" errors in production

### 🔧 Self-Healing
- Auto-fixes common issues
- No manual intervention needed
- Works across all environments

### 📊 Visibility
- Clear reports of what's wrong
- Shows exactly what was fixed
- Helps debug deployment issues

### 🚀 Reliability
- Trust your migrations
- Deploy with confidence
- Less downtime from schema issues

## Best Practices

### 1. Keep EXPECTED_SCHEMA Updated

When you create a new migration:
```python
# 1. Create migration
alembic revision -m "add new column"

# 2. Edit migration file
def upgrade():
    add_column_if_not_exists('table', Column('new_col', String()))

# 3. Update verify_schema.py
EXPECTED_SCHEMA = {
    'table': {
        'new_col': ('character varying', True, None),  # ← Add this
    }
}
```

### 2. Run Verification After Major Changes

```bash
# After merging migration PRs
python -m alembic.verify_schema

# After restoring from backup
python -m alembic.verify_schema --fix

# After manual database changes
python -m alembic.verify_schema
```

### 3. Include in CI/CD Pipeline

```yaml
# In your CI pipeline
- name: Verify Schema
  run: |
    docker compose exec -T backend python -m alembic.verify_schema
```

## Troubleshooting

### "Schema verification FAILED"

**Cause:** Database schema doesn't match expectations

**Solution:**
```bash
python -m alembic.verify_schema --fix
```

### "Could not verify schema"

**Cause:** Database not accessible or tables don't exist yet

**Solution:** This is normal for first install. Run `alembic upgrade head` first.

### "Failed to fix schema issues"

**Cause:** Database permissions or connection issues

**Solution:**
1. Check database is running: `docker compose ps`
2. Check DB credentials in `.env`
3. Check logs: `docker compose logs backend`

## Technical Details

### How Column Checks Work

```python
async def column_exists(table_name: str, column_name: str) -> bool:
    """Query information_schema to check if column exists."""
    conn = op.get_bind()
    result = conn.execute(text("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = :table_name
        AND column_name = :column_name
    """), {"table_name": table_name, "column_name": column_name})

    return result.fetchone() is not None
```

This queries PostgreSQL's system catalog directly, which always reflects the **actual** database state.

### Auto-Fix Implementation

```python
async def fix_issues(issues: list):
    """Generate and execute ALTER TABLE statements for missing columns."""
    for issue in issues:
        if issue['type'] == 'missing_column':
            sql = f"""
                ALTER TABLE {table}
                ADD COLUMN IF NOT EXISTS {column} {type} {nullable} {default}
            """
            await conn.execute(text(sql))
```

Uses `ADD COLUMN IF NOT EXISTS` for safety - won't fail if column already exists.

## Summary

**Problem:** Alembic can think migrations ran when they actually failed
**Solution:** Independent schema verification that checks the actual database
**Result:** Self-healing migrations that just work

**Key Points:**
- ✅ Runs automatically during updates
- ✅ Catches partial migration failures
- ✅ Auto-fixes missing columns
- ✅ Works independently of Alembic state
- ✅ Zero manual intervention needed

This makes your database migrations **bulletproof** and your deployments **more reliable**.
