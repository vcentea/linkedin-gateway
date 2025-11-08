# LinkedIn Gateway Enterprise Edition - Quick Start Guide

This guide will help you deploy LinkedIn Gateway Enterprise Edition on your infrastructure.

## Prerequisites

Before you begin, ensure you have:

- **Docker & Docker Compose** installed and running
- **Git** for pulling updates
- **A VPS or server** with:
  - Ubuntu 20.04+ / Debian 11+ / CentOS 8+ / Windows Server 2019+
  - Minimum 2GB RAM, 20GB disk space
  - Public IP address or domain name
- **LinkedIn OAuth credentials** from [LinkedIn Developers](https://www.linkedin.com/developers/apps)
- **HTTPS access** via:
  - Cloudflare Tunnel (recommended for testing)
  - Nginx/Caddy reverse proxy
  - ngrok or similar tunneling service

## Installation Steps

### 1. Clone Repository

```bash
git clone <your-private-enterprise-repo-url>
cd LinkedinGateway-SaaS
```

### 2. Configure Environment

Copy the Enterprise environment template:

```bash
cd deployment
cp .env.enterprise.example .env
```

Edit `.env` and configure:

```bash
# Required Configuration
LG_BACKEND_EDITION=enterprise
LG_CHANNEL=default

# Database credentials
DB_USER=linkedin_gateway_user
DB_PASSWORD=<generate-secure-password>
DB_NAME=LinkedinGateway

# Security keys (generate with: openssl rand -hex 32)
SECRET_KEY=<your-secret-key>
JWT_SECRET_KEY=<your-jwt-secret>

# LinkedIn OAuth credentials
LINKEDIN_CLIENT_ID=<your-linkedin-client-id>
LINKEDIN_CLIENT_SECRET=<your-linkedin-client-secret>

# Public URL (REQUIRED for OAuth callback)
PUBLIC_URL=https://your-enterprise-domain.com

# Optional: Enable Enterprise features
ENT_FEATURE_ORGANIZATIONS=false
ENT_FEATURE_QUOTAS=false
ENT_FEATURE_AUDIT_LOGS=false
```

### 3. Set Up HTTPS (Required)

LinkedIn OAuth requires HTTPS. Choose one option:

#### Option A: Cloudflare Tunnel (Easiest for Testing)

```bash
# Install cloudflared
wget -q https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb
sudo dpkg -i cloudflared-linux-amd64.deb

# Start tunnel (replace PORT with your backend port, default 7778)
cloudflared tunnel --url http://localhost:7778
```

Copy the `https://xxxx.trycloudflare.com` URL to your `.env` file as `PUBLIC_URL`.

#### Option B: Nginx Reverse Proxy

See [deployment/docs/HTTPS_SETUP.md](./HTTPS_SETUP.md) for detailed Nginx configuration.

### 4. Deploy Enterprise Edition

Run the installation script:

**Linux/macOS:**
```bash
cd deployment/scripts
chmod +x install-enterprise.sh
./install-enterprise.sh
```

**Windows:**
```cmd
cd deployment\scripts
install-enterprise.bat
```

The script will:
1. Pull latest code
2. Check Docker installation
3. Create database and backend containers
4. Run database migrations
5. Start all services

### 5. Verify Installation

Check that services are running:

```bash
cd deployment
docker compose -f docker-compose.yml -f docker-compose.enterprise.yml ps
```

Test the API:

```bash
curl http://localhost:7778/health
# Should return: {"status":"ok"}

curl http://localhost:7778/api/v1/server/info
# Should show edition=enterprise
```

### 6. Configure LinkedIn OAuth Callback

In your [LinkedIn Developer App](https://www.linkedin.com/developers/apps):

1. Go to **Auth** tab
2. Add **Authorized redirect URL**:
   ```
   https://your-enterprise-domain.com/auth/user/callback
   ```
3. Save changes

### 7. Connect Extension

Users can connect to your Enterprise instance:

1. Install the LinkedIn Gateway browser extension
2. Open extension settings
3. Select **Custom Server**
4. Enter your server URL: `https://your-enterprise-domain.com`
5. Click **Connect**
6. Authenticate via LinkedIn OAuth

## Post-Installation

### Access API Documentation

Visit `https://your-enterprise-domain.com/docs` to view interactive API documentation.

### View Logs

```bash
cd deployment
docker compose -f docker-compose.yml -f docker-compose.enterprise.yml logs -f backend
```

### Check Enterprise Features

```bash
curl http://localhost:7778/api/v1/enterprise/features
```

Returns status of optional Enterprise features.

## Updating

To update to the latest version:

**Linux/macOS:**
```bash
cd deployment/scripts
./update-enterprise.sh
```

**Windows:**
```cmd
cd deployment\scripts
update-enterprise.bat
```

Use `--force` flag to discard local changes if needed.

## Development Mode (Hot Reload)

For development with instant code changes:

**Linux/macOS:**
```bash
cd deployment/scripts
./start-dev-enterprise.sh
```

**Windows:**
```cmd
cd deployment\scripts
start-dev-enterprise.bat
```

Edit Python files in `backend/` and see changes instantly without rebuilding.

## Troubleshooting

### OAuth Callback Fails

- Verify `PUBLIC_URL` in `.env` matches exactly what's configured in LinkedIn app
- Ensure URL starts with `https://` (not `http://`)
- Check that your server is accessible from the internet

### Extension Can't Connect

- Verify backend is running: `docker compose ps`
- Check firewall allows traffic on your port (default 7778)
- Ensure CORS is configured: `CORS_ORIGINS=*` or specific origins

### Database Connection Errors

```bash
# Check database logs
docker compose logs postgres

# Verify database is running
docker compose ps postgres

# Test connection
docker compose exec backend python -c "from app.db.session import engine; print(engine)"
```

### Container Won't Start

```bash
# Check detailed logs
docker compose logs backend

# Rebuild from scratch
docker compose down
docker compose build --no-cache
docker compose up -d
```

## Uninstalling

To remove Enterprise installation:

**Linux/macOS:**
```bash
cd deployment/scripts
./uninstall-enterprise.sh
```

**Windows:**
```cmd
cd deployment\scripts
uninstall-enterprise.bat
```

You'll be prompted whether to keep or remove data volumes.

## Support

For Enterprise support, documentation, and advanced configuration:

- Environment Variables: See [ENTERPRISE_ENV.md](./ENTERPRISE_ENV.md)
- Architecture: See [../../docs/ARCHITECTURE.md](../../docs/ARCHITECTURE.md)
- API Reference: `https://your-domain.com/docs`

## Security Considerations

- **Change default passwords** in `.env` before production deployment
- **Use strong secret keys** generated with `openssl rand -hex 32`
- **Enable firewall** to restrict database access
- **Regular backups** of database volumes
- **Keep software updated** with `update-enterprise.sh`
- **Monitor logs** for suspicious activity

## What's Next?

- **Enable Enterprise Features**: Set `ENT_FEATURE_*` flags in `.env`
- **Set Up Monitoring**: Configure Sentry with `SENTRY_DSN`
- **Database Backups**: See [DATABASE_BACKUP.md](./DATABASE_BACKUP.md)
- **License Activation**: Coming in future release

---

**Edition**: Enterprise (Self-Hosted)  
**Server Execution**: ✅ Enabled  
**License Required**: Not enforced yet  
**Support**: Professional (when licensed)



