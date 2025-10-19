# Backend Updates and Deployment Guide

## Understanding Your Current Setup

### Code is Baked into Docker Image
Your backend code is **copied into the Docker image** during build time, not mounted as a volume. This means:

- ✅ **Production-ready**: Immutable, secure, portable
- ✅ **Fast startup**: No file system dependencies
- ❌ **Requires rebuild**: Code changes need image rebuild
- ❌ **Not for hot-reload**: No automatic code refresh

### What's Mounted as Volumes
Only these directories are mounted:
```yaml
volumes:
  - backend_logs:/app/logs  # Log files (persistent)
  - postgres_data:/var/lib/postgresql/data  # Database (persistent)
```

## How to Update Backend Code

### Quick Update (Pull + Rebuild + Restart)

**Windows:**
```cmd
cd deployment\scripts
update-backend.bat [core|saas]
```

**Linux/Mac:**
```bash
cd deployment/scripts
./update-backend.sh [core|saas]
```

This script will:
1. **Pull latest code from Git** (main branch by default)
2. Check for uncommitted changes and warn you
3. Rebuild the backend Docker image with latest code
4. Restart the backend container
5. Show container status

**Advanced Options:**

```bash
# Update SaaS edition
./update-backend.sh saas

# Update from different branch
./update-backend.sh core --branch develop

# Skip git pull (use local code only)
./update-backend.sh core --no-pull

# Combine options
./update-backend.sh saas --branch feature/new-api --no-pull
```

### Manual Update Process

#### For Core Edition:
```bash
cd deployment
docker compose build --no-cache backend
docker compose up -d backend
docker compose logs -f backend
```

#### For SaaS Edition:
```bash
cd deployment
docker compose -f docker-compose.yml -f docker-compose.saas.yml build --no-cache backend
docker compose -f docker-compose.yml -f docker-compose.saas.yml up -d backend
docker compose -f docker-compose.yml -f docker-compose.saas.yml logs -f backend
```

### Full Stack Restart
If you need to restart everything (database + backend):

```bash
# WARNING: This may cause downtime
cd deployment
docker compose down
docker compose build
docker compose up -d
```

## Production Deployment Best Practices

### Option 1: Direct Build on Server (Current Method)
**Pros:**
- Simple, no registry needed
- Good for single-server deployments

**Cons:**
- Server needs to build images (CPU/memory intensive)
- Downtime during rebuild
- No rollback capability

**Process:**
```bash
# 1. SSH to server
ssh user@yourserver.com

# 2. Navigate to project and run update script
cd /path/to/LinkedinGateway-SaaS/deployment/scripts
./update-backend.sh core

# The script automatically:
# - Pulls latest code from Git
# - Checks for uncommitted changes
# - Rebuilds Docker image
# - Restarts container
```

**Or manually:**
```bash
# If you prefer to pull manually
cd /path/to/LinkedinGateway-SaaS
git pull origin main
cd deployment/scripts
./update-backend.sh core --no-pull
```

### Option 2: CI/CD with Docker Registry (Recommended)
**Pros:**
- Zero downtime deployments
- Easy rollbacks
- Build once, deploy anywhere
- No build load on production server

**Process:**
```yaml
# GitHub Actions, GitLab CI, or similar
1. Code push triggers CI/CD
2. CI builds Docker image
3. Push to registry (Docker Hub, AWS ECR, GitHub Container Registry)
4. Server pulls new image
5. Rolling restart
```

**Example workflow:**
```bash
# On CI/CD server
docker build -t yourregistry/linkedin-gateway:v1.2.3 -f deployment/Dockerfile backend/
docker push yourregistry/linkedin-gateway:v1.2.3

# On production server
docker pull yourregistry/linkedin-gateway:v1.2.3
docker tag yourregistry/linkedin-gateway:v1.2.3 yourregistry/linkedin-gateway:latest
docker compose up -d backend
```

### Option 3: Docker Swarm/Kubernetes
For multiple servers and high availability:
- Zero-downtime rolling updates
- Automatic load balancing
- Health check-based deployments
- Automatic rollback on failure

## Development with Hot Reload

For local development, use the development docker-compose file:

```bash
cd deployment
docker compose -f docker-compose.dev.yml up
```

This mounts your code as a volume and enables auto-reload on file changes.

**Note:** Never use this in production!

## Update Checklist

Before updating:
- [ ] Backup database if making schema changes
- [ ] Review environment variables (.env)
- [ ] Check for breaking changes in dependencies
- [ ] Test in staging environment if available
- [ ] Notify users if expecting downtime

During update:
- [ ] Pull latest code or build new image
- [ ] Check Docker image builds successfully
- [ ] Review container logs for errors
- [ ] Verify health check passes
- [ ] Test critical API endpoints

After update:
- [ ] Monitor application logs
- [ ] Check database migrations ran successfully
- [ ] Verify user authentication works
- [ ] Test LinkedIn integration functionality
- [ ] Monitor error rates and performance

## Rollback Procedure

If something goes wrong:

### If using Git tags/versions:
```bash
# Checkout previous version
git checkout v1.2.2
cd deployment/scripts
./update-backend.sh core
```

### If using Docker registry:
```bash
# Pull and use previous image
docker pull yourregistry/linkedin-gateway:v1.2.2
docker tag yourregistry/linkedin-gateway:v1.2.2 yourregistry/linkedin-gateway:latest
docker compose up -d backend
```

### Emergency rollback:
```bash
# Stop current container
docker compose stop backend

# Find previous image
docker images | grep linkedin-gateway

# Start with specific image ID
docker run -d --name linkedin-gateway-backend <image-id>
```

## Monitoring Updates

Check container status:
```bash
docker compose ps
```

View live logs:
```bash
docker compose logs -f backend
```

Check resource usage:
```bash
docker stats
```

Verify health:
```bash
curl http://localhost:7778/health
```

## Database Migrations

When your update includes database schema changes:

```bash
# 1. Backup database first
docker compose exec postgres pg_dump -U linkedin_gateway_user LinkedinGateway > backup.sql

# 2. Run migrations (if using Alembic)
docker compose exec backend alembic upgrade head

# 3. Verify migrations
docker compose exec postgres psql -U linkedin_gateway_user -d LinkedinGateway -c "\dt"
```

## Environment Variables

After updating `.env` files:
```bash
# Recreate containers with new env vars
docker compose up -d --force-recreate backend
```

## Troubleshooting

### Issue: Changes not reflected after update
**Solution:** Make sure you used `--no-cache` flag during build
```bash
docker compose build --no-cache backend
```

### Issue: Container keeps restarting
**Solution:** Check logs for errors
```bash
docker compose logs backend
```

### Issue: Database connection errors
**Solution:** Verify database is healthy
```bash
docker compose ps postgres
docker compose exec postgres pg_isready
```

### Issue: Port already in use
**Solution:** Check what's using the port
```bash
# Windows
netstat -ano | findstr :7778

# Linux/Mac
lsof -i :7778
```

## Performance Tips

1. **Use multi-stage builds** to reduce image size
2. **Layer caching** - put frequently changing code last
3. **Build context** - use .dockerignore to exclude unnecessary files
4. **Health checks** - ensure proper startup detection
5. **Resource limits** - set memory and CPU limits in docker-compose.yml

## Security Considerations

- Never mount code as volume in production
- Don't include secrets in Docker images
- Use environment variables or secrets management
- Regularly update base images for security patches
- Scan images for vulnerabilities
- Use non-root user in containers (future improvement)

## Next Steps for Production

Consider implementing:
1. **Image Registry**: Docker Hub, AWS ECR, or self-hosted
2. **CI/CD Pipeline**: GitHub Actions, GitLab CI, Jenkins
3. **Monitoring**: Prometheus + Grafana, DataDog, or New Relic
4. **Log Aggregation**: ELK Stack, Loki, or CloudWatch
5. **Backup Strategy**: Automated database backups
6. **Staging Environment**: Test before production
7. **Blue-Green Deployment**: Zero downtime updates

