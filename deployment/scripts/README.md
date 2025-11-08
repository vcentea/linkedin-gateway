# LinkedIn Gateway - Deployment Scripts

This directory contains all deployment and maintenance scripts for LinkedIn Gateway.

## Quick Reference

### Fresh Installation
```bash
./install.sh [core|saas|enterprise]
```

### Update Existing Installation
```bash
./update.sh [core|saas|enterprise]
```

## Script Categories

### 🚀 Installation (For New Users)

| Script | Description |
|--------|-------------|
| **`install.sh`** | Main installer - supports all editions |
| `install-core.sh` | Wrapper for Core edition |
| `install-saas.sh` | Wrapper for SaaS edition |
| `install-enterprise.sh` | Wrapper for Enterprise edition |

**What it does:**
- Creates complete database schema from SQL
- Generates secure credentials
- Builds Docker containers
- Marks database as up-to-date

### 🔄 Updates (For Existing Users)

| Script | Description |
|--------|-------------|
| **`update.sh`** | Main updater - supports all editions |
| `update-core.sh` | Wrapper for Core edition |
| `update-saas.sh` | Wrapper for SaaS edition |
| `update-enterprise.sh` | Wrapper for Enterprise edition |
| `update-backend.sh` | Backend-only update (advanced) |
| `update-saas-quick.sh` | Quick restart without rebuild |

**What it does:**
- Pulls latest code from Git
- Rebuilds Docker containers
- Applies database migrations via Alembic
- Verifies backend health

### 🗄️ Database Management

| Script | Description |
|--------|-------------|
| `init-db.sh` | Manually initialize database |
| `verify-db.sh` | Check database schema |
| `reset-db-saas.sh` | Reset SaaS database (destructive!) |
| `fix-db-password.sh` | Fix database password issues |
| `fix-db-ownership.sh` | Fix table ownership problems |

### 🛠️ Utilities

| Script | Description |
|--------|-------------|
| `verify-env.sh` | Verify environment configuration |
| `uninstall-core.sh` | Remove Core installation |
| `uninstall-enterprise.sh` | Remove Enterprise installation |
| `clean-core.sh` | Clean Core deployment |
| `clean-saas.sh` | Clean SaaS deployment |
| `start-dev-saas.sh` | Start SaaS in development mode |
| `start-dev-enterprise.sh` | Start Enterprise in development mode |

### 🗂️ Obsolete Scripts

Location: `obsolete/`

These scripts are **no longer needed** and kept only for reference:
- `update-to-v1.1.sh` - Manual v1.1 migration (use Alembic instead)
- `update-to-v1.1-docker.sh` - Docker version of above
- `rollback-from-v1.1.sh` - Manual rollback (use `alembic downgrade`)

**DO NOT USE** - see `obsolete/README.md` for details.

## Usage Examples

### Fresh Installation

**Install Core Edition:**
```bash
cd deployment/scripts
./install.sh core
```

**Install SaaS Edition:**
```bash
cd deployment/scripts
./install.sh saas
```

**Or use edition-specific scripts:**
```bash
./install-core.sh      # Equivalent to: ./install.sh core
./install-saas.sh      # Equivalent to: ./install.sh saas
```

### Updating

**Update Core Edition:**
```bash
cd deployment/scripts
./update.sh core
```

**Update SaaS Edition:**
```bash
cd deployment/scripts
./update.sh saas
```

**Quick update (no rebuild):**
```bash
./update-saas-quick.sh  # Only for SaaS, during development
```

### Database Operations

**Verify database is healthy:**
```bash
./verify-db.sh
```

**Manually initialize database:**
```bash
./init-db.sh
```

**Reset database (⚠️ DESTRUCTIVE):**
```bash
./reset-db-saas.sh  # This will DELETE all data!
```

## How It Works

### Installation System

```
┌─────────────────────────────────────────────────────────┐
│ install.sh [edition]                                     │
│                                                          │
│ 1. Check prerequisites (Docker, Docker Compose)         │
│ 2. Create .env from .env.example                        │
│ 3. Generate secure credentials                          │
│ 4. Build and start Docker containers                    │
│ 5. Wait for PostgreSQL to be ready                      │
│ 6. Run init-scripts/*.sql (creates full schema)         │
│ 7. Run: alembic stamp head                              │
│    └─ Marks DB as "at latest version"                   │
│ 8. Verify backend health                                │
│                                                          │
│ ✓ Database is fully set up, no migrations needed        │
└─────────────────────────────────────────────────────────┘
```

### Update System

```
┌─────────────────────────────────────────────────────────┐
│ update.sh [edition]                                      │
│                                                          │
│ 1. Check prerequisites                                   │
│ 2. Git pull latest code (stash if needed)              │
│ 3. Pull latest Docker images                            │
│ 4. Rebuild containers with --no-cache                   │
│ 5. Wait for PostgreSQL to be ready                      │
│ 6. Run: alembic upgrade head                            │
│    └─ Applies only new migrations                       │
│ 7. Verify backend health                                │
│                                                          │
│ ✓ Database updated incrementally with new changes       │
└─────────────────────────────────────────────────────────┘
```

## Database Migration Strategy

### Two-Track System

**Fresh Installations** (New Users):
- ✅ Creates complete schema from `deployment/init-scripts/01-create-schema.sql`
- ✅ Includes ALL latest features and columns
- ✅ Marks as up-to-date with `alembic stamp head`
- ✅ **No migrations run**

**Updates** (Existing Users):
- ✅ Detects existing `alembic_version` table
- ✅ Runs only new migrations via `alembic upgrade head`
- ✅ Preserves all data
- ✅ **Incremental changes only**

### Why This Approach?

| Approach | Fresh Install | Updates |
|----------|---------------|---------|
| **Alembic Only** | Slow (runs all migrations) | ✅ Good |
| **SQL Only** | ✅ Fast | ❌ No upgrade path |
| **SQL + Alembic** | ✅ Fast | ✅ Good |

We use **SQL + Alembic** to get the best of both worlds.

## Common Issues

### "Database tables not found"
```bash
# Solution: Run init scripts manually
./init-db.sh
```

### "Migration fails: column already exists"
```bash
# Check current version
docker compose exec backend alembic current

# Stamp to correct version if needed
docker compose exec backend alembic stamp head
```

### "Git pull conflicts during update"
```bash
# The update script auto-stashes changes
# Or manually:
git stash
git pull origin main
```

### "Docker is not running"
```bash
# Start Docker first
sudo systemctl start docker  # Linux
# Or start Docker Desktop on Windows/Mac
```

## Development Workflow

### Making Database Changes

1. **Update Model** - Edit `backend/app/db/models/*.py`
2. **Generate Migration** - Run `alembic revision --autogenerate -m "description"`
3. **Update SQL Schema** - Add columns to `deployment/init-scripts/01-create-schema.sql`
4. **Test Fresh Install** - Run `./install.sh core` on clean system
5. **Test Update** - Run `./update.sh core` on existing system
6. **Commit Both Files** - Migration + SQL schema

### Testing

```bash
# Test fresh install
docker compose down -v
./install.sh core

# Test update
git checkout previous-version
./install.sh core
git checkout main
./update.sh core
```

## Script Maintenance

### Adding a New Script

1. Create in `deployment/scripts/`
2. Make executable: `chmod +x script-name.sh`
3. Follow naming convention: `action-target.sh`
4. Add documentation to this README
5. Test on clean system

### Deprecating a Script

1. Move to `obsolete/` directory
2. Update `obsolete/README.md`
3. Remove from this README
4. Document replacement in deprecation notes

## Documentation

For detailed documentation, see:
- **[DEPLOYMENT.md](../DEPLOYMENT.md)** - Complete deployment guide
- **[obsolete/README.md](obsolete/README.md)** - Info on deprecated scripts
- **Backend README** - Application-specific docs

## Support

Having issues?
1. Check [Common Issues](#common-issues) above
2. Review logs: `docker compose logs backend`
3. Verify database: `./verify-db.sh`
4. Read [DEPLOYMENT.md](../DEPLOYMENT.md) for troubleshooting

---

**Always use the provided scripts** - they handle all edge cases and ensure consistency.
