# Environment Configuration Guide

## Overview

This document explains how environment variables are managed in different environments.

## Environment Variable Flow

### Local Development (without Docker)
```
deployment/.env (created by install script)
    ↓ (copied)
backend/.env
    ↓ (loaded by load_dotenv())
Python reads from os.environ
    ↓
Application runs ✅
```

### Docker Deployment (Production/VPS)
```
deployment/.env (created by install script)
    ↓ (read by docker-compose via env_file:)
Docker injects into container environment
    ↓
Python reads from os.environ
    ↓
Application runs ✅
```

**Important:** In Docker, `backend/.env` is excluded by `.dockerignore` and doesn't exist in the container. This is correct! Environment variables come from docker-compose's `env_file:` directive.

## How to Modify Configuration

### On VPS (Docker)

1. **Edit the .env file:**
   ```bash
   cd /opt/linkedin_gateway/app/deployment
   nano .env
   ```

2. **Update the values you need:**
   ```bash
   LINKEDIN_CLIENT_ID=your_client_id
   LINKEDIN_CLIENT_SECRET=your_client_secret
   PUBLIC_URL=https://yourdomain.com
   ```

3. **Restart containers (NO rebuild needed!):**
   ```bash
   docker compose -f docker-compose.yml -f docker-compose.saas.yml restart
   ```

   Or for core edition:
   ```bash
   docker compose -f docker-compose.yml restart
   ```

**That's it!** The `env_file:` directive in docker-compose reads from `.env` on every container start.

### For Local Development

1. **Edit the .env file:**
   ```bash
   cd backend
   nano .env
   ```

2. **Restart your dev server:**
   ```bash
   python main.py
   ```

## Complete Cleanup Commands

### SaaS Edition - Full Cleanup
```bash
cd /opt/linkedin_gateway/app/deployment
./scripts/clean-saas.sh
```

Or manually:
```bash
cd /opt/linkedin_gateway/app/deployment

# Stop and remove everything
docker compose -f docker-compose.yml -f docker-compose.saas.yml down -v --remove-orphans

# Remove volumes (this deletes the database!)
docker volume rm linkedin-gateway-saas-postgres-data
docker volume rm linkedin-gateway-saas-backend-logs

# Remove network
docker network rm linkedin-gateway-saas-network

# Clean up images
docker image prune -f
```

### Core Edition - Full Cleanup
```bash
cd /opt/linkedin_gateway/app/deployment

# Stop and remove everything
docker compose -f docker-compose.yml down -v --remove-orphans

# Remove volumes (this deletes the database!)
docker volume rm linkedin-gateway-core-postgres-data
docker volume rm linkedin-gateway-core-backend-logs

# Remove network
docker network rm linkedin-gateway-core-network

# Clean up images
docker image prune -f
```

### Reinstall from Scratch
After cleanup:
```bash
cd /opt/linkedin_gateway/app/deployment/scripts

# For SaaS edition
./install-saas.sh

# For Core edition
./install-core.sh
```

## Environment Variable Priority

When using Docker Compose with `env_file:`, the priority is:

1. **Explicit `environment:` section** (highest priority)
2. **env_file: .env** (variables not explicitly set in environment:)
3. **Shell environment** (lowest priority)

In our setup:
- Most vars come from `env_file: .env`
- Some are explicitly set in `environment:` (like DB_HOST: postgres)
- This allows .env to be the single source of truth

## Key Files

### `.dockerignore`
Excludes `backend/.env` from Docker image:
```dockerignore
# Environment files (managed in deployment/)
.env
.env.*
```

This is correct! Environment should come from docker-compose, not baked into the image.

### `docker-compose.yml`
Loads environment from `.env`:
```yaml
services:
  backend:
    env_file:
      - .env
    environment:
      # Override specific vars here if needed
      DB_HOST: postgres
```

### `backend/app/core/config.py`
Tries to load `.env` but gracefully handles if it doesn't exist (Docker case):
```python
env_path = Path(__file__).resolve().parent.parent.parent / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
# Pydantic reads from os.environ regardless
```

## FAQ

**Q: Why doesn't the container have a .env file?**
A: This is by design! Docker Compose passes environment variables directly via `env_file:`. The file doesn't need to be in the container.

**Q: Do I need to rebuild after changing .env?**
A: No! Just restart: `docker compose restart`

**Q: Where do I edit .env on VPS?**
A: In `/opt/linkedin_gateway/app/deployment/.env`

**Q: Why does install script copy .env to backend/.env?**
A: For local development without Docker. The Docker container doesn't use it.

**Q: How do I verify env vars are loaded in Docker?**
A: Run: `docker exec linkedin-gateway-saas-api env | grep DB_`

## Troubleshooting

### Issue: Variables not updating after .env change
**Solution:** Make sure to restart, not just reload:
```bash
docker compose -f docker-compose.yml -f docker-compose.saas.yml restart
```

### Issue: Container fails to start after .env change
**Solution:** Check .env syntax (no spaces around =):
```bash
# Correct
DB_PASSWORD=mypassword

# Wrong
DB_PASSWORD = mypassword
```

### Issue: Want to use different .env file
**Solution:** Specify it in docker-compose:
```yaml
env_file:
  - .env.production  # Instead of .env
```

