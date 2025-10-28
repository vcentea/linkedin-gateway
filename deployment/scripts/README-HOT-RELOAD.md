# Hot Reload Configuration Guide

## Understanding Hot Reload

**Hot reload** means your code changes are **immediately reflected** in the running application without rebuilding the Docker image.

### How It Works

1. **Without Hot Reload (Production Mode)**
   - Source code is **copied into** the Docker image during build
   - Code is **read-only** inside the container
   - Changes require rebuilding the image (`docker compose build`)
   - **More secure** - no write access to source

2. **With Hot Reload (Development Mode)**
   - Source code is **mounted as a volume** from your host machine
   - Code is **read-write** - changes on host = changes in container
   - Uvicorn watches for file changes and auto-restarts
   - **Instant feedback** for development

---

## Current Setup Status

### ✅ Production/SaaS Mode (DEFAULT)
- **File**: `docker-compose.yml` + `docker-compose.saas.yml`
- **Hot Reload**: ❌ **DISABLED** (by design for security)
- **Volumes**: Only logs and .env (read-only)
- **Command**: `uvicorn main:app --host 0.0.0.0 --port ${PORT}` (no --reload)
- **Use Case**: Production servers, stable deployments

### ✅ Development Mode (AVAILABLE)
- **File**: `docker-compose.dev.yml`
- **Hot Reload**: ✅ **ENABLED**
- **Volumes**: Entire `/backend` source mounted
- **Command**: `uvicorn main:app --host 0.0.0.0 --port ${PORT} --reload --log-level debug`
- **Use Case**: Local development, testing changes

---

## How to Switch Between Modes

### Option 1: Use Different Docker Compose Files

#### Start in Production Mode (No Hot Reload)
```bash
cd deployment

# Core edition
docker compose -f docker-compose.yml up -d

# SaaS edition
docker compose -f docker-compose.yml -f docker-compose.saas.yml --env-file .env.prod.saas up -d
```

#### Start in Development Mode (With Hot Reload)
```bash
cd deployment
docker compose -f docker-compose.dev.yml up -d
```

**Note**: You can only run ONE mode at a time (same ports).

---

### Option 2: Create a Dev/Prod Overlay System

We can create separate compose files for hot reload that work with both core and SaaS.

---

## Creating Hot Reload for SaaS

If you want hot reload on your SaaS development instance:

### Create `docker-compose.dev-saas.yml`:

```yaml
name: linkedin-gateway-dev-saas

# Development SaaS with Hot Reload
# Usage: docker compose -f docker-compose.yml -f docker-compose.saas.yml -f docker-compose.dev-saas.yml up

services:
  backend:
    # Override the build - use direct Python image
    image: python:3.11-slim
    
    # Add source code volume for hot reload
    volumes:
      - ../backend:/app
      - backend_logs:/app/logs
      - /app/__pycache__
      - /app/app/__pycache__
    
    # Override command to use --reload
    command: >
      bash -c "
        apt-get update && 
        apt-get install -y gcc postgresql-client curl openssl &&
        pip install --no-cache-dir -r requirements/base.txt &&
        mkdir -p /app/logs &&
        echo 'Starting SaaS development server with hot reload...' &&
        uvicorn main:app --host 0.0.0.0 --port ${PORT:-7778} --reload --log-level debug
      "
    
    # Dev-specific environment
    environment:
      DEBUG: "true"
      LOG_LEVEL: "DEBUG"
      PYTHONUNBUFFERED: "1"
```

Then start with:
```bash
docker compose -f docker-compose.yml -f docker-compose.saas.yml -f docker-compose.dev-saas.yml --env-file .env.prod.saas up -d
```

---

## Volume Configuration Comparison

### Production (No Hot Reload)

```yaml
volumes:
  # Only logs and config
  - backend_logs:/app/logs
  - ./.env:/app/.env:ro  # Read-only
```

**Result**: Code is baked into image, changes need rebuild

### Development (Hot Reload)

```yaml
volumes:
  # ENTIRE source code mounted
  - ../backend:/app  # ← This enables hot reload!
  - backend_logs:/app/logs
  - /app/__pycache__  # Exclude Python cache
```

**Result**: Code changes on host instantly reflect in container

---

## Security Implications

### Why Production Disables Hot Reload

1. **No Write Access**: Attackers can't modify source code
2. **Immutable**: Code matches Git commit exactly
3. **Performance**: No file watching overhead
4. **Predictable**: Same code every time, no drift

### Why Development Enables Hot Reload

1. **Speed**: Instant feedback on changes
2. **Convenience**: No rebuild cycle
3. **Debugging**: Live code changes while testing

---

## Environment Variables for Hot Reload

Currently, there's **NO environment variable** to toggle hot reload. It's controlled by:

1. **Which docker-compose file you use**
2. **Volume mounts** (present or not)
3. **Uvicorn command** (--reload flag or not)

### To Add an Environment Variable Toggle

We could add `HOT_RELOAD_ENABLED` to `.env`:

```bash
# .env
HOT_RELOAD_ENABLED=false  # Production
# or
HOT_RELOAD_ENABLED=true   # Development
```

Then modify docker-compose to conditionally mount volumes, but **Docker Compose doesn't support conditional volumes** easily. Better to use separate files.

---

## Recommended Approach

### For Your Use Case

Since you want to:
1. Develop on SaaS edition
2. Test changes quickly
3. Deploy to production safely

**Recommended Structure**:

```
deployment/
├── docker-compose.yml              # Base config
├── docker-compose.saas.yml         # SaaS overrides (edition=saas)
├── docker-compose.dev.yml          # Dev mode (core + hot reload)
└── docker-compose.dev-saas.yml     # NEW: Dev mode (saas + hot reload)
```

**Usage**:

```bash
# Production SaaS (No hot reload)
docker compose -f docker-compose.yml -f docker-compose.saas.yml --env-file .env.prod.saas up -d

# Development SaaS (Hot reload)
docker compose -f docker-compose.yml -f docker-compose.saas.yml -f docker-compose.dev-saas.yml up -d

# Switch modes
docker compose down  # Stop current
# Then start with different compose files
```

---

## Quick Reference

| Mode | Files | Hot Reload | Source Volume | Rebuild Needed | Use Case |
|------|-------|------------|---------------|----------------|----------|
| **Prod Core** | `docker-compose.yml` | ❌ | ❌ | ✅ | Production |
| **Prod SaaS** | `docker-compose.yml` + `docker-compose.saas.yml` | ❌ | ❌ | ✅ | SaaS Production |
| **Dev Core** | `docker-compose.dev.yml` | ✅ | ✅ | ❌ | Local Dev |
| **Dev SaaS** | *Not yet created* | - | - | - | Would need custom file |

---

## Creating the Dev-SaaS File

Want me to create `docker-compose.dev-saas.yml` for you? This would give you:
- ✅ Hot reload enabled
- ✅ SaaS edition (LG_BACKEND_EDITION=saas)
- ✅ Instant code changes
- ✅ Debug logging

Let me know if you want this!

