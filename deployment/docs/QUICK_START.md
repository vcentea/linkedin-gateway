# Quick Start Guide

## For Local Development (Hot Reload)

Perfect for active development with automatic code reload:

```bash
# 1. Copy development environment file
cd deployment
cp .env.dev.example .env

# 2. Edit .env with your LinkedIn OAuth credentials
notepad .env  # Windows
# nano .env   # Linux/Mac

# 3. Start development stack
docker compose -f docker-compose.dev.yml up

# 4. Your backend is now running at http://localhost:7778
# Code changes will automatically reload!
```

**Features:**
- ✅ Auto-reload on file changes
- ✅ Code mounted as volume
- ✅ Debug logging enabled
- ✅ Database exposed for tools like pgAdmin

**Stop development:**
```bash
docker compose -f docker-compose.dev.yml down
```

---

## For Production Deployment

For running a production instance:

```bash
# 1. Copy production environment file
cd deployment
cp .env.example .env  # or .env.saas.example for SaaS

# 2. Edit .env with STRONG secrets and production settings
notepad .env  # Windows
# nano .env   # Linux/Mac

# IMPORTANT: Generate strong secrets!
# Use the password generator: python scripts/generate_passwords.py

# 3. Install and start (Core Edition)
./scripts/install-core.sh  # Linux/Mac
# or
scripts\install-core.bat   # Windows

# 4. Or for SaaS Edition
./scripts/install-saas.sh  # Linux/Mac
# or
scripts\install-saas.bat   # Windows
```

**Your backend is now running at http://localhost:7778**

---

## Common Commands

### View Logs
```bash
# Development
docker compose -f docker-compose.dev.yml logs -f

# Production - Core
docker compose logs -f backend

# Production - SaaS
docker compose -f docker-compose.yml -f docker-compose.saas.yml logs -f backend
```

### Stop Services
```bash
# Development
docker compose -f docker-compose.dev.yml down

# Production - Core
docker compose down

# Production - SaaS
docker compose -f docker-compose.yml -f docker-compose.saas.yml down
```

### Restart Backend Only
```bash
# Development
docker compose -f docker-compose.dev.yml restart backend

# Production - Core
docker compose restart backend

# Production - SaaS
docker compose -f docker-compose.yml -f docker-compose.saas.yml restart backend
```

### Update Backend Code (Production)
```bash
cd deployment/scripts

# Core Edition - pulls from Git automatically
./update-backend.sh core    # Linux/Mac
update-backend.bat core     # Windows

# SaaS Edition - pulls from Git automatically
./update-backend.sh saas    # Linux/Mac
update-backend.bat saas     # Windows

# Advanced: update from different branch
./update-backend.sh core --branch develop

# Advanced: skip git pull (use local code)
./update-backend.sh core --no-pull
```

### Access Database
```bash
# Using docker exec
docker compose exec postgres psql -U linkedin_gateway_user -d LinkedinGateway

# Or use a GUI tool like pgAdmin
# Host: localhost
# Port: 5432
# User: linkedin_gateway_user
# Password: (from your .env file)
# Database: LinkedinGateway
```

### Check Status
```bash
docker compose ps
docker compose exec backend curl http://localhost:7778/health
```

---

## Troubleshooting

### Port already in use
```bash
# Windows - check what's using port 7778
netstat -ano | findstr :7778

# Linux/Mac - check what's using port 7778
lsof -i :7778

# Change port in .env file
PORT=8888
```

### Database connection issues
```bash
# Check if database is healthy
docker compose ps postgres
docker compose exec postgres pg_isready

# Restart database
docker compose restart postgres
```

### Permission denied on scripts (Linux/Mac)
```bash
chmod +x deployment/scripts/*.sh
```

### Changes not reflected (Production)
The script pulls from Git and rebuilds:
```bash
cd deployment/scripts
./update-backend.sh core

# Or if you already pulled manually:
./update-backend.sh core --no-pull
```

### Can't access from Chrome Extension
1. Check `PUBLIC_URL` in `.env` matches your actual URL
2. For localhost, use `http://localhost:7778`
3. For production, use your actual domain
4. Make sure CORS is configured correctly

---

## Environment Modes

| Mode | File | Use Case | Hot Reload | Security |
|------|------|----------|------------|----------|
| Development | `docker-compose.dev.yml` | Active coding | ✅ Yes | ⚠️ Weak |
| Production Core | `docker-compose.yml` | Self-hosted | ❌ No | ✅ Strong |
| Production SaaS | `docker-compose.yml` + `docker-compose.saas.yml` | Multi-tenant | ❌ No | ✅ Strong |

---

## Next Steps

1. **For Development**: See [UPDATES_AND_DEPLOYMENTS.md](./UPDATES_AND_DEPLOYMENTS.md)
2. **For Production**: See [DEPLOYMENT_WORKFLOW.md](./DEPLOYMENT_WORKFLOW.md)
3. **Database Setup**: See [DATABASE_SETUP.md](./DATABASE_SETUP.md)
4. **Security**: See [DEPLOYMENT_RECOMMENDATIONS.md](./DEPLOYMENT_RECOMMENDATIONS.md)

---

## Getting Help

- **Logs**: Always check logs first - `docker compose logs -f`
- **Health Check**: `curl http://localhost:7778/health`
- **Database**: `docker compose exec postgres psql -U linkedin_gateway_user -d LinkedinGateway`
- **Restart**: When in doubt, restart - `docker compose restart`

---

## Important Notes

⚠️ **NEVER use development configuration in production**
- Development uses weak secrets
- Development exposes database port
- Development has permissive CORS
- Development has no rate limiting

✅ **Always use update scripts for production deployments**
- Code is baked into Docker images
- Volume mounting code is for development only
- Production requires image rebuild for code updates

