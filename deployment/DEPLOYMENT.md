# LinkedIn Gateway - Deployment & Migration System

This document describes the clean, maintainable deployment and database migration system for LinkedIn Gateway.

## Table of Contents

- [System Overview](#system-overview)
- [Fresh Installation](#fresh-installation)
- [Updating Existing Installations](#updating-existing-installations)
- [Database Migration Strategy](#database-migration-strategy)
- [Adding New Database Changes](#adding-new-database-changes)
- [Script Reference](#script-reference)
- [Troubleshooting](#troubleshooting)

## System Overview

LinkedIn Gateway uses a **two-track system** for database management:

| Scenario | Method | Tools |
|----------|--------|-------|
| **Fresh Installations** | Complete schema from SQL | `01-create-schema.sql` + `alembic stamp head` |
| **Existing Installations** | Incremental migrations | `alembic upgrade head` |

### Why This Approach?

**For New Users:**
- Creates entire database schema at once from SQL file
- No migration history needed
- Faster installation
- Marks database as "up-to-date" with Alembic

**For Existing Users:**
- Applies only the changes since their last update
- Preserves all existing data
- Handles schema evolution incrementally
- Tracked via Alembic migration system

## Fresh Installation

### Quick Start

```bash
cd deployment/scripts
./install.sh [core|saas|enterprise]
```

**Example:**
```bash
./install.sh core        # Install Open Core Edition
./install.sh saas        # Install SaaS Edition
./install.sh enterprise  # Install Enterprise Edition
```

### What Happens During Installation

1. **Prerequisites Check** - Verifies Docker is installed and running
2. **Environment Setup** - Creates `.env` file from `.env.example`
3. **Port Configuration** - Prompts for port (default: 7778)
4. **Credential Generation** - Creates secure DB passwords and secrets
5. **Docker Build** - Builds and starts all containers
6. **Database Creation** - Runs `init-scripts/*.sql` to create complete schema
7. **Version Stamping** - Marks DB as current with `alembic stamp head`
8. **Health Check** - Verifies backend is running

### Edition-Specific Wrappers

For convenience, you can also use:
```bash
./install-core.sh        # Equivalent to: ./install.sh core
./install-saas.sh        # Equivalent to: ./install.sh saas
./install-enterprise.sh  # Equivalent to: ./install.sh enterprise
```

## Updating Existing Installations

### Standard Update

```bash
cd deployment/scripts
./update.sh [core|saas|enterprise]
```

**Example:**
```bash
./update.sh core         # Update Open Core Edition
./update.sh saas         # Update SaaS Edition
./update.sh enterprise   # Update Enterprise Edition
```

### What Happens During Update

1. **Prerequisites Check** - Verifies Docker and existing installation
2. **Git Pull** - Pulls latest code (stashes uncommitted changes)
3. **Docker Pull** - Pulls latest base images
4. **Rebuild** - Rebuilds containers with `--no-cache`
5. **Database Check** - Waits for PostgreSQL to be ready
6. **Migrations** - Runs `alembic upgrade head` to apply new schema changes
7. **Health Check** - Verifies backend is responding

### Edition-Specific Wrappers

For convenience:
```bash
./update-core.sh         # Equivalent to: ./update.sh core
./update-saas.sh         # Equivalent to: ./update.sh saas
./update-enterprise.sh   # Equivalent to: ./update.sh enterprise
```

### Quick Update (SaaS Only)

For development/hot-reload scenarios where you don't need a full rebuild:

```bash
./update-saas-quick.sh
```

This script:
- Pulls latest code
- Restarts backend service (no rebuild)
- Applies migrations
- Useful when you only changed Python code and have hot-reload enabled

## Database Migration Strategy

### The Two-Track System

```
┌─────────────────────────────────────────────────────────────┐
│                     Fresh Installation                       │
│                                                              │
│  1. Run: 01-create-schema.sql                               │
│     ├─ Creates ALL tables                                   │
│     ├─ Creates ALL indexes                                  │
│     ├─ Creates ALL constraints                              │
│     └─ Includes latest schema (with webhook columns, etc.)  │
│                                                              │
│  2. Run: alembic stamp head                                 │
│     └─ Marks DB as "at latest version"                      │
│                                                              │
│  ✓ Done! No migrations needed.                              │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                   Existing Installation                      │
│                                                              │
│  1. Detect: alembic_version table exists                    │
│                                                              │
│  2. Run: alembic upgrade head                               │
│     ├─ migration_001: add csrf_token                        │
│     ├─ migration_002: add unique constraint                 │
│     └─ migration_003: add webhook fields                    │
│                                                              │
│  ✓ Done! Database updated incrementally.                    │
└─────────────────────────────────────────────────────────────┘
```

### Current Migration Chain

The migration chain in `backend/alembic/versions/`:

```
None (fresh DB)
  ↓
add_csrf_token (add csrf_token column to api_keys)
  ↓
unique_user_instance (add unique constraint for user+instance)
  ↓
add_webhook_fields (add webhook_url and webhook_headers)
  ↓
HEAD (current version)
```

## Adding New Database Changes

When you need to modify the database schema, follow these steps:

### 1. Update Your SQLAlchemy Models

Edit the model files in `backend/app/db/models/`:

```python
# Example: Adding a new column to APIKey model
class APIKey(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "api_keys"

    # ... existing columns ...

    # New column
    new_feature = Column(String(255), nullable=True)  # Add your new column
```

### 2. Generate Alembic Migration

```bash
cd backend
alembic revision --autogenerate -m "add new_feature column to api_keys"
```

This creates a new file in `backend/alembic/versions/` like:
```python
"""add new_feature column to api_keys

Revision ID: abc123def456
Revises: add_webhook_fields
Create Date: 2025-01-15 10:30:00
"""
from alembic import op
import sqlalchemy as sa

revision = 'abc123def456'
down_revision = 'add_webhook_fields'  # Points to previous migration

def upgrade():
    op.add_column('api_keys', sa.Column('new_feature', sa.String(255)))

def downgrade():
    op.drop_column('api_keys', 'new_feature')
```

### 3. Update SQL Schema for Fresh Installs

**CRITICAL**: Update `deployment/init-scripts/01-create-schema.sql` to include your new column:

```sql
-- API Keys
CREATE TABLE IF NOT EXISTS api_keys (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    -- ... existing columns ...
    webhook_url VARCHAR(1024),
    webhook_headers JSONB DEFAULT '{}' NOT NULL,
    new_feature VARCHAR(255),  -- ADD YOUR NEW COLUMN HERE
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL
);
```

### 4. Test Both Paths

**Test Fresh Install:**
```bash
# Clean slate test
docker compose down -v  # Remove volumes
./install.sh core
# Verify new column exists
```

**Test Update:**
```bash
# On an existing installation without your changes
./update.sh core
# Verify migration applied successfully
```

### 5. Commit Both Files

```bash
git add backend/alembic/versions/abc123def456_add_new_feature.py
git add deployment/init-scripts/01-create-schema.sql
git commit -m "feat: add new_feature column to api_keys"
```

## Script Reference

### Installation Scripts

| Script | Purpose | Usage |
|--------|---------|-------|
| `install.sh` | Main installation script | `./install.sh [core\|saas\|enterprise]` |
| `install-core.sh` | Core edition installer | `./install-core.sh` |
| `install-saas.sh` | SaaS edition installer | `./install-saas.sh` |
| `install-enterprise.sh` | Enterprise edition installer | `./install-enterprise.sh` |

### Update Scripts

| Script | Purpose | Usage |
|--------|---------|-------|
| `update.sh` | Main update script | `./update.sh [core\|saas\|enterprise]` |
| `update-core.sh` | Core edition updater | `./update-core.sh` |
| `update-saas.sh` | SaaS edition updater | `./update-saas.sh` |
| `update-enterprise.sh` | Enterprise edition updater | `./update-enterprise.sh` |
| `update-saas-quick.sh` | Quick restart (no rebuild) | `./update-saas-quick.sh` |
| `update-backend.sh` | Backend-only update | `./update-backend.sh [core\|saas]` |

### Database Scripts

| Script | Purpose | Usage |
|--------|---------|-------|
| `init-db.sh` | Manual DB initialization | `./init-db.sh` |
| `verify-db.sh` | Verify DB schema | `./verify-db.sh` |
| `reset-db-saas.sh` | Reset SaaS database | `./reset-db-saas.sh` |

### Utility Scripts

| Script | Purpose | Usage |
|--------|---------|-------|
| `verify-env.sh` | Check environment config | `./verify-env.sh` |
| `fix-db-password.sh` | Fix DB password issues | `./fix-db-password.sh` |
| `fix-db-ownership.sh` | Fix table ownership | `./fix-db-ownership.sh` |

### Obsolete Scripts

Located in `scripts/obsolete/` - DO NOT USE:
- `update-to-v1.1.sh` - Manual v1.1 migration (now handled by Alembic)
- `update-to-v1.1-docker.sh` - Docker version of above
- `rollback-from-v1.1.sh` - Manual rollback (use `alembic downgrade` instead)

See `scripts/obsolete/README.md` for details.

## Troubleshooting

### Installation Issues

**Problem: Database schema not created**
```bash
# Solution: Manually run init scripts
cd deployment/scripts
./init-db.sh
```

**Problem: Alembic migration fails on fresh install**
```
alembic.script.base.RevisionError: No such revision or branch
```
```bash
# Solution: Stamp the database version
docker compose exec backend alembic stamp head
```

### Update Issues

**Problem: Migration fails with "column already exists"**
```
sqlalchemy.exc.ProgrammingError: column "webhook_url" already exists
```
```bash
# This means migrations are out of sync
# Solution 1: Check what version DB thinks it's at
docker compose exec backend alembic current

# Solution 2: Manually stamp to correct version
docker compose exec backend alembic stamp head
```

**Problem: Git pull conflicts during update**
```
error: Your local changes would be overwritten by merge
```
```bash
# Solution: The update script auto-stashes changes
# Or manually:
git stash
git pull
git stash pop  # Only if you want your changes back
```

### Alembic Commands

```bash
# Check current DB version
docker compose exec backend alembic current

# View migration history
docker compose exec backend alembic history

# Upgrade to latest
docker compose exec backend alembic upgrade head

# Downgrade one version
docker compose exec backend alembic downgrade -1

# Downgrade to specific version
docker compose exec backend alembic downgrade abc123def456

# Generate new migration (auto-detect changes)
docker compose exec backend alembic revision --autogenerate -m "description"

# Generate empty migration (manual)
docker compose exec backend alembic revision -m "description"
```

### Verify Database State

```bash
# Check if tables exist
docker exec linkedin-gateway-core-db psql -U linkedin_gateway_user -d LinkedinGateway -c "\dt"

# Check alembic version
docker exec linkedin-gateway-core-db psql -U linkedin_gateway_user -d LinkedinGateway -c "SELECT * FROM alembic_version;"

# Count tables
docker exec linkedin-gateway-core-db psql -U linkedin_gateway_user -d LinkedinGateway -c "SELECT COUNT(*) FROM pg_tables WHERE schemaname = 'public';"
```

## Best Practices

### For Developers

1. **Always update both**: When adding columns, update both the model AND `01-create-schema.sql`
2. **Test both paths**: Test fresh install and update on existing DB
3. **Never skip migrations**: Don't manually ALTER tables in production
4. **Use autogenerate carefully**: Always review generated migrations before committing
5. **Write reversible migrations**: Always implement proper `downgrade()` functions

### For Deployment

1. **Backup before updates**: Especially in production
2. **Use the provided scripts**: Don't manually run Alembic unless troubleshooting
3. **Check logs**: After updates, verify backend logs for errors
4. **Monitor migrations**: Watch Alembic output during updates
5. **Keep .env secure**: Never commit `.env` files to git

### For Production

1. **Test migrations in staging first**
2. **Have rollback plan ready** (database backups)
3. **Schedule maintenance windows** for major updates
4. **Monitor application after updates**
5. **Keep migration history clean** (don't delete old migrations)

## Architecture Decisions

### Why SQL + Alembic?

We use **both** instead of Alembic-only because:

1. **Fresh installs are faster**: Creating entire schema from SQL is faster than running 100+ migrations
2. **Simpler onboarding**: New users get a clean, working DB immediately
3. **Easier to audit**: One SQL file shows complete current schema
4. **Migration history stays manageable**: Only tracks incremental changes
5. **Docker init scripts**: PostgreSQL automatically runs `*.sql` files in init-scripts/

### Why Not Just Alembic?

If we only used Alembic:
- New users would run all historical migrations (slow)
- Migration chain could break over time
- Harder to see "current complete schema"
- More points of failure during setup

### Why Not Just SQL?

If we only used SQL:
- Existing users would have no upgrade path
- Manual migrations are error-prone
- No rollback capability
- Hard to track what changed when

## Version History

| Version | Date | Major Changes |
|---------|------|---------------|
| v1.0.0 | Jan 2025 | Initial release with basic schema |
| v1.1.0 | Feb 2025 | Multi-key support, webhook configuration |
| Current | - | Clean two-track deployment system |

## Support

For issues or questions:
- Check the [Troubleshooting](#troubleshooting) section
- Review script logs in `deployment/scripts/`
- Check backend logs: `docker compose logs backend`
- Verify database: `./scripts/verify-db.sh`

---

**Last Updated:** 2025-01-15
**Maintained By:** LinkedIn Gateway Team
