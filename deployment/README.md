# LinkedIn Gateway Deployment

Docker-based deployment for LinkedIn Gateway backend (Core and SaaS editions).

## 🚀 Quick Start

### Development (with Hot Reload)
```bash
cd deployment
cp .env.dev.example .env
# Edit .env with your credentials
docker compose -f docker-compose.dev.yml up
```

### Production - Core Edition
```bash
cd deployment
cp .env.example .env
# Edit .env with strong secrets
./scripts/install-core.sh   # Linux/Mac
# or
scripts\install-core.bat    # Windows
```

### Production - SaaS Edition
```bash
cd deployment
cp .env.saas.example .env
# Edit .env with strong secrets
./scripts/install-saas.sh   # Linux/Mac
# or
scripts\install-saas.bat    # Windows
```

## 📚 Documentation

- **[Quick Start Guide](docs/QUICK_START.md)** - Get up and running fast
- **[Updates & Deployments](docs/UPDATES_AND_DEPLOYMENTS.md)** - How to update backend code
- **[Deployment Workflow](docs/DEPLOYMENT_WORKFLOW.md)** - Production deployment process
- **[Database Setup](docs/DATABASE_SETUP.md)** - Database configuration and migrations
- **[Deployment Recommendations](docs/DEPLOYMENT_RECOMMENDATIONS.md)** - Security and best practices

## 🔧 Common Tasks

### Update Backend Code (Production)
```bash
cd deployment/scripts

# Core Edition (automatically pulls from Git)
./update-backend.sh core    # Linux/Mac
update-backend.bat core     # Windows

# SaaS Edition (automatically pulls from Git)
./update-backend.sh saas    # Linux/Mac
update-backend.bat saas     # Windows

# Advanced options:
./update-backend.sh core --branch develop  # Use different branch
./update-backend.sh core --no-pull         # Skip git pull
```

### View Logs
```bash
# Development
docker compose -f docker-compose.dev.yml logs -f

# Production - Core
docker compose logs -f backend

# Production - SaaS
docker compose -f docker-compose.yml -f docker-compose.saas.yml logs -f backend
```

### Check Status
```bash
docker compose ps
curl http://localhost:7778/health
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

## 🏗️ Architecture

### Components
- **PostgreSQL 17**: Database (Alpine Linux)
- **Python 3.11**: Backend API (FastAPI/Uvicorn)
- **Docker Networks**: Isolated networking
- **Docker Volumes**: Persistent data storage

### Editions
- **Core**: Open-source, self-hosted, full feature set
- **SaaS**: Multi-tenant with future billing, analytics, organizations

### Files
```
deployment/
├── docker-compose.yml           # Base production config (Core)
├── docker-compose.saas.yml      # SaaS edition overlay
├── docker-compose.dev.yml       # Development with hot reload
├── Dockerfile                   # Backend image definition
├── .env.example                 # Core production template
├── .env.saas.example            # SaaS production template
├── .env.dev.example             # Development template
├── init-scripts/                # Database initialization
├── scripts/                     # Installation & update scripts
└── docs/                        # Detailed documentation
```

## 🔄 How Updates Work

### Development Mode (Hot Reload)
- Code is **mounted as a volume**
- Changes are **instantly reflected**
- Uvicorn auto-reloads on file changes
- **Never use in production**

### Production Mode (Immutable Images)
- Code is **baked into Docker image**
- Changes require **rebuild + restart**
- More secure, portable, and production-ready
- Use `update-backend` scripts for updates

### Update Process
```
Code Change → Build Image → Restart Container
```

See [UPDATES_AND_DEPLOYMENTS.md](docs/UPDATES_AND_DEPLOYMENTS.md) for detailed information.

## 🔐 Security

### Environment Variables
- **Never commit `.env` files**
- Use strong secrets in production
- Generate with: `python scripts/generate_passwords.py`

### Production Checklist
- [ ] Strong `SECRET_KEY` and `JWT_SECRET_KEY`
- [ ] Secure database password
- [ ] Configure `PUBLIC_URL` correctly
- [ ] Set appropriate `CORS_ORIGINS`
- [ ] Enable HTTPS (via reverse proxy)
- [ ] Set up rate limiting
- [ ] Configure firewall rules
- [ ] Enable database backups

## 🌐 Network Configuration

### Default Ports
- Backend API: `7778` (configurable via `PORT` env var)
- PostgreSQL: `5432` (exposed in dev, internal in prod)

### CORS Configuration
- Development: `*` (allow all)
- Production: Set `CORS_ORIGINS` to your frontend domain

### Reverse Proxy (Recommended for Production)
Use Nginx or Caddy in front of the backend:
```
Internet → Nginx (443) → Backend (7778)
```

## 📦 Docker Volumes

### Persistent Data
- `postgres_data`: Database files
- `backend_logs`: Application logs

### Backup
```bash
# Database
docker compose exec postgres pg_dump -U linkedin_gateway_user LinkedinGateway > backup.sql

# Logs
docker cp linkedin-gateway-core-api:/app/logs ./logs-backup
```

## 🔍 Troubleshooting

### Backend won't start
```bash
# Check logs
docker compose logs backend

# Check database connectivity
docker compose exec backend env | grep DB_

# Verify database is healthy
docker compose exec postgres pg_isready
```

### Port conflicts
```bash
# Windows
netstat -ano | findstr :7778

# Linux/Mac
lsof -i :7778

# Change port in .env
PORT=8888
```

### Changes not reflected
```bash
# Development: Should auto-reload (check logs)
docker compose -f docker-compose.dev.yml logs -f backend

# Production: Pull and rebuild
cd deployment/scripts
./update-backend.sh core  # Automatically pulls from Git + rebuilds
```

### Database connection errors
```bash
# Restart database
docker compose restart postgres

# Check connection
docker compose exec postgres psql -U linkedin_gateway_user -d LinkedinGateway
```

## 📊 Monitoring

### Health Check
```bash
curl http://localhost:7778/health
```

### Container Stats
```bash
docker stats
```

### Logs
```bash
# Follow logs
docker compose logs -f

# Last 100 lines
docker compose logs --tail=100 backend

# Filter by service
docker compose logs backend
```

## 🚢 Production Deployment Options

### Option 1: VPS (DigitalOcean, Linode, etc.)
- Install Docker & Docker Compose
- Clone repository
- Run installation scripts
- Set up reverse proxy (Nginx/Caddy)

### Option 2: Docker Swarm
- Multi-node deployment
- Zero-downtime updates
- Automatic failover

### Option 3: Railway (Recommended for Easy Setup)
See [RAILWAY.md](RAILWAY.md) for Railway deployment.

### Option 4: AWS/GCP/Azure
- Use managed PostgreSQL (RDS/CloudSQL)
- Deploy backend on ECS/Cloud Run/App Service
- Use container registry

## 🔄 CI/CD Integration

For automated deployments, integrate with:
- GitHub Actions
- GitLab CI
- Jenkins
- CircleCI

Example workflow:
```yaml
Build → Test → Push to Registry → Deploy
```

See [UPDATES_AND_DEPLOYMENTS.md](docs/UPDATES_AND_DEPLOYMENTS.md) for CI/CD setup.

## 📝 Environment Variables Reference

### Required
- `DB_USER`, `DB_PASSWORD`, `DB_NAME`
- `SECRET_KEY`, `JWT_SECRET_KEY`
- `LINKEDIN_CLIENT_ID`, `LINKEDIN_CLIENT_SECRET`
- `PUBLIC_URL`

### Optional
- `PORT` (default: 7778)
- `CORS_ORIGINS` (default: *)
- `DEFAULT_RATE_LIMIT` (default: 100)
- `LG_BACKEND_EDITION` (core/saas)

See `.env.example` files for complete reference.

## 🆘 Getting Help

1. Check [Quick Start Guide](docs/QUICK_START.md)
2. Review [Troubleshooting](#-troubleshooting) section
3. Check Docker logs: `docker compose logs -f`
4. Verify health: `curl http://localhost:7778/health`
5. Review environment variables: `docker compose config`

## 📄 License

See main project README for license information.

---

**Quick Links:**
- [Quick Start](docs/QUICK_START.md)
- [Updates Guide](docs/UPDATES_AND_DEPLOYMENTS.md)
- [Deployment Workflow](docs/DEPLOYMENT_WORKFLOW.md)
- [Database Setup](docs/DATABASE_SETUP.md)
- [Security Recommendations](docs/DEPLOYMENT_RECOMMENDATIONS.md)

