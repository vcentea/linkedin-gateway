# Complete Reinstall Instructions

This guide shows how to completely wipe and reinstall LinkedIn Gateway from scratch.

## 🗑️ Complete Cleanup (Deletes Everything!)

### SaaS Edition

```bash
cd /opt/linkedin_gateway/app/deployment

# Complete cleanup
docker compose -f docker-compose.yml -f docker-compose.saas.yml down -v --remove-orphans
docker volume rm linkedin-gateway-saas-postgres-data 2>/dev/null || true
docker volume rm linkedin-gateway-saas-backend-logs 2>/dev/null || true
docker network rm linkedin-gateway-saas-network 2>/dev/null || true
docker image prune -f

# Or use the cleanup script
./scripts/clean-saas.sh
```

### Core Edition

```bash
cd /opt/linkedin_gateway/app/deployment

# Complete cleanup
docker compose -f docker-compose.yml down -v --remove-orphans
docker volume rm linkedin-gateway-core-postgres-data 2>/dev/null || true
docker volume rm linkedin-gateway-core-backend-logs 2>/dev/null || true
docker network rm linkedin-gateway-core-network 2>/dev/null || true
docker image prune -f

# Or use the cleanup script
./scripts/clean-core.sh
```

## 🚀 Fresh Installation

### SaaS Edition

```bash
cd /opt/linkedin_gateway/app

# Pull latest code
git pull

# Make scripts executable
chmod +x deployment/scripts/*.sh

# Run installer
cd deployment/scripts
./install-saas.sh

# Follow prompts:
# - Press Enter for port 7778 (or choose custom)
# - Wait for installation to complete

# Configure OAuth
cd ../
nano .env
# Add your LinkedIn credentials:
# LINKEDIN_CLIENT_ID=your_client_id
# LINKEDIN_CLIENT_SECRET=your_client_secret
# PUBLIC_URL=https://lg.ainnovate.tech

# Restart to apply OAuth config
docker compose -f docker-compose.yml -f docker-compose.saas.yml restart
```

### Core Edition

```bash
cd /opt/linkedin_gateway/app

# Pull latest code
git pull

# Make scripts executable
chmod +x deployment/scripts/*.sh

# Run installer
cd deployment/scripts
./install-core.sh

# Follow prompts and configure as above
```

## ✅ Verification

After installation:

```bash
cd /opt/linkedin_gateway/app/deployment

# Check containers are running
docker compose -f docker-compose.yml -f docker-compose.saas.yml ps

# Verify database schema
./scripts/verify-db.sh

# Check logs
docker compose -f docker-compose.yml -f docker-compose.saas.yml logs -f backend

# Test health endpoint
curl http://localhost:7778/health
```

## 🔍 What Gets Installed

The automated installer will:

1. ✅ Check environment configuration
2. ✅ Generate secure credentials (DB password, SECRET_KEY, JWT_SECRET_KEY)
3. ✅ Copy configuration to backend
4. ✅ Build and start Docker containers
5. ✅ Wait for PostgreSQL to be ready
6. ✅ **Verify database schema was created**
7. ✅ **Auto-run init scripts if tables missing**
8. ✅ Wait for backend API to be healthy
9. ✅ Show configuration instructions

## 🎯 One-Line Complete Reinstall

### SaaS Edition
```bash
cd /opt/linkedin_gateway/app/deployment && docker compose -f docker-compose.yml -f docker-compose.saas.yml down -v && docker volume rm linkedin-gateway-saas-postgres-data linkedin-gateway-saas-backend-logs 2>/dev/null; docker network rm linkedin-gateway-saas-network 2>/dev/null; cd scripts && ./install-saas.sh
```

### Core Edition
```bash
cd /opt/linkedin_gateway/app/deployment && docker compose -f docker-compose.yml down -v && docker volume rm linkedin-gateway-core-postgres-data linkedin-gateway-core-backend-logs 2>/dev/null; docker network rm linkedin-gateway-core-network 2>/dev/null; cd scripts && ./install-core.sh
```

## 📝 Notes

- **Database**: All data will be lost during cleanup
- **API Keys**: Users will need to regenerate API keys
- **Sessions**: All user sessions will be invalidated
- **Configuration**: .env file is preserved (not deleted)
- **Init Scripts**: Now automatically verified and run if needed
- **No Manual Steps**: Database schema is created automatically

## 🔧 Troubleshooting

If database tables are missing after install:

```bash
cd /opt/linkedin_gateway/app/deployment
./scripts/verify-db.sh    # Check status
./scripts/init-db.sh      # Manually initialize if needed
```

If containers won't start:

```bash
# Check logs
docker compose -f docker-compose.yml -f docker-compose.saas.yml logs

# Check disk space
df -h

# Check Docker status
docker info
```

