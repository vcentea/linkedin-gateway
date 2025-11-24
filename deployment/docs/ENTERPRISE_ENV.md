# LinkedIn Gateway Enterprise Edition - Environment Variables

Complete reference for all environment variables used in Enterprise edition.

## Table of Contents

- [Edition Configuration](#edition-configuration)
- [Database Configuration](#database-configuration)
- [API Configuration](#api-configuration)
- [Security Configuration](#security-configuration)
- [LinkedIn OAuth](#linkedin-oauth)
- [CORS Configuration](#cors-configuration)
- [Enterprise Features](#enterprise-features)
- [License Configuration](#license-configuration)
- [Monitoring](#monitoring)
- [Rate Limiting](#rate-limiting)

---

## Edition Configuration

### `LG_BACKEND_EDITION`
**Required**: Yes  
**Default**: `core`  
**Valid Values**: `core`, `saas`, `enterprise`  
**Example**: `LG_BACKEND_EDITION=enterprise`

Determines which edition of LinkedIn Gateway is running. Must be set to `enterprise` for Enterprise edition.

### `LG_CHANNEL`
**Required**: No  
**Default**: `default`  
**Valid Values**: `default`, `railway_private`  
**Example**: `LG_CHANNEL=default`

Deployment channel for edition-specific behaviors. Use `default` for standard Enterprise deployments.

---

## Database Configuration

### `DATABASE_URL`
**Required**: No (if using individual DB_* variables)  
**Default**: None  
**Example**: `DATABASE_URL=postgresql://user:pass@localhost:5432/LinkedinGateway`

Complete PostgreSQL connection string. If provided, overrides individual `DB_*` variables.

### `DB_USER`
**Required**: Yes (if not using DATABASE_URL)  
**Default**: None  
**Example**: `DB_USER=linkedin_gateway_user`

PostgreSQL database username.

### `DB_PASSWORD`
**Required**: Yes (if not using DATABASE_URL)  
**Default**: None  
**Example**: `DB_PASSWORD=secure_password_123`

PostgreSQL database password. Use a strong, randomly generated password.

**Security Note**: Generate with `openssl rand -base64 32`

### `DB_NAME`
**Required**: Yes (if not using DATABASE_URL)  
**Default**: None  
**Example**: `DB_NAME=LinkedinGateway`

PostgreSQL database name.

### `DB_HOST`
**Required**: No  
**Default**: `postgres` (Docker service name)  
**Example**: `DB_HOST=localhost`

PostgreSQL server hostname.

### `DB_PORT`
**Required**: No  
**Default**: `5432`  
**Example**: `DB_PORT=5432`

PostgreSQL server port.

---

## API Configuration

### `PORT`
**Required**: No  
**Default**: `7778`  
**Example**: `PORT=8000`

Port the backend API server listens on.

### `BACKEND_PORT`
**Required**: No  
**Default**: Value of `PORT`  
**Example**: `BACKEND_PORT=7778`

Alias for `PORT`. If both are set, `PORT` takes precedence.

### `API_HOST`
**Required**: No  
**Default**: `0.0.0.0`  
**Example**: `API_HOST=0.0.0.0`

Host address the API server binds to. Use `0.0.0.0` to accept connections from any interface.

### `PUBLIC_URL`
**Required**: Yes (for OAuth to work)  
**Default**: None  
**Example**: `PUBLIC_URL=https://enterprise.example.com`

Your public HTTPS URL. Used for OAuth callbacks and extension configuration.

**Requirements**:
- Must start with `https://`
- Must be accessible from the internet
- Must match exactly what's configured in LinkedIn Developer App

---

## Security Configuration

### `SECRET_KEY`
**Required**: Yes  
**Default**: None  
**Example**: `SECRET_KEY=abc123...` (64 characters)

Secret key for session encryption and security operations.

**Generate with**: `openssl rand -hex 32`

### `JWT_SECRET_KEY`
**Required**: Yes  
**Default**: None  
**Example**: `JWT_SECRET_KEY=xyz789...` (64 characters)

Secret key for JWT token signing and verification.

**Generate with**: `openssl rand -hex 32`

**Security Note**: Use different keys for `SECRET_KEY` and `JWT_SECRET_KEY`.

---

## LinkedIn OAuth

### `LINKEDIN_CLIENT_ID`
**Required**: Yes  
**Default**: None  
**Example**: `LINKEDIN_CLIENT_ID=78abc12345`

LinkedIn OAuth application client ID.

**Get from**: [LinkedIn Developers](https://www.linkedin.com/developers/apps)

### `LINKEDIN_CLIENT_SECRET`
**Required**: Yes  
**Default**: None  
**Example**: `LINKEDIN_CLIENT_SECRET=AbCdEf123456`

LinkedIn OAuth application client secret.

**Get from**: [LinkedIn Developers](https://www.linkedin.com/developers/apps)

**Security Note**: Keep this secret. Never commit to version control.

---

## CORS Configuration

### `CORS_ORIGINS`
**Required**: No  
**Default**: `*` (all origins allowed)  
**Example**: `CORS_ORIGINS=https://app.example.com,https://admin.example.com`

Comma-separated list of allowed CORS origins.

**Options**:
- `*` - Allow all origins (development/testing only)
- Specific origins - Production security best practice

---

## Enterprise Features

These feature flags control which optional Enterprise modules are enabled.

### `ENT_FEATURE_ORGANIZATIONS`
**Required**: No  
**Default**: `false`  
**Valid Values**: `true`, `false`, `1`, `0`, `yes`, `no`  
**Example**: `ENT_FEATURE_ORGANIZATIONS=false`

Enable Organizations & Teams management API.

**When enabled**:
- `/api/v1/enterprise/organizations/*` endpoints become available
- Currently returns "coming soon" responses (implementation pending)

### `ENT_FEATURE_QUOTAS`
**Required**: No  
**Default**: `false`  
**Valid Values**: `true`, `false`, `1`, `0`, `yes`, `no`  
**Example**: `ENT_FEATURE_QUOTAS=false`

Enable Usage & Quotas tracking API.

**When enabled**:
- `/api/v1/enterprise/quotas/*` endpoints become available
- Currently returns "coming soon" responses (implementation pending)

### `ENT_FEATURE_AUDIT_LOGS`
**Required**: No  
**Default**: `false`  
**Valid Values**: `true`, `false`, `1`, `0`, `yes`, `no`  
**Example**: `ENT_FEATURE_AUDIT_LOGS=false`

Enable Audit Logs & Security Events API.

**When enabled**:
- `/api/v1/enterprise/audit/*` endpoints become available
- Currently returns "coming soon" responses (implementation pending)

---

## License Configuration

**Note**: License validation is not enforced yet. These variables are placeholders for future releases.

### `LICENSE_KEY`
**Required**: No (not enforced)  
**Default**: None  
**Example**: `LICENSE_KEY=ENT-XXXX-XXXX-XXXX-XXXX`

Enterprise license key. Will be validated against licensing server in future releases.

### `LICENSE_VALIDATION_URL`
**Required**: No (not enforced)  
**Default**: None  
**Example**: `LICENSE_VALIDATION_URL=https://licensing.example.com/validate`

URL of the licensing validation server. Enterprise instances will validate against the SaaS licensing server.

---

## Monitoring

### `SENTRY_DSN`
**Required**: No  
**Default**: None  
**Example**: `SENTRY_DSN=https://xxx@yyy.ingest.sentry.io/zzz`

Sentry Data Source Name for error tracking and monitoring.

**Get from**: [Sentry.io](https://sentry.io)

### `SENTRY_ENVIRONMENT`
**Required**: No  
**Default**: `production`  
**Example**: `SENTRY_ENVIRONMENT=staging`

Environment name for Sentry error categorization.

**Common values**: `production`, `staging`, `development`

---

## Rate Limiting

### `DEFAULT_RATE_LIMIT`
**Required**: No  
**Default**: `100`  
**Example**: `DEFAULT_RATE_LIMIT=200`

Default number of requests allowed per window.

### `DEFAULT_RATE_WINDOW`
**Required**: No  
**Default**: `3600` (1 hour)  
**Example**: `DEFAULT_RATE_WINDOW=7200`

Rate limit window in seconds.

**Example**: With `DEFAULT_RATE_LIMIT=100` and `DEFAULT_RATE_WINDOW=3600`, users can make 100 requests per hour.

---

## Development Configuration

### `RELOAD`
**Required**: No  
**Default**: `false`  
**Valid Values**: `true`, `false`  
**Example**: `RELOAD=true`

Enable hot reload for development. Set automatically by `start-dev-enterprise.sh`.

**Warning**: Do not enable in production (performance impact).

---

## Enterprise Edition Feature Matrix

| Feature | Core | SaaS | Enterprise |
|---------|------|------|------------|
| **Server-side execution** (`server_call=true`) | ✅ Yes | ❌ No | ✅ Yes |
| **Local account management** | ✅ Yes | ❌ No | ✅ Yes |
| **OAuth/SSO authentication** | ✅ Yes | ✅ Yes | ✅ Yes |
| **Organizations & Teams** (optional) | ❌ No | ❌ No | 🔜 Coming |
| **Usage & Quotas** (optional) | ❌ No | ❌ No | 🔜 Coming |
| **Audit Logs** (optional) | ❌ No | ❌ No | 🔜 Coming |
| **License validation** | ❌ No | N/A | 🔜 Coming |
| **Licensing server** | ❌ No | ✅ Yes | ❌ No |

---

## Example Configurations

### Minimal Production Configuration

```bash
# Edition
LG_BACKEND_EDITION=enterprise
LG_CHANNEL=default

# Database
DB_USER=linkedin_gateway_user
DB_PASSWORD=<strong-random-password>
DB_NAME=LinkedinGateway

# API
PORT=7778
PUBLIC_URL=https://enterprise.example.com

# Security
SECRET_KEY=<64-char-hex-key>
JWT_SECRET_KEY=<64-char-hex-key>

# LinkedIn OAuth
LINKEDIN_CLIENT_ID=<your-client-id>
LINKEDIN_CLIENT_SECRET=<your-client-secret>

# CORS
CORS_ORIGINS=*
```

### Full Configuration with Features

```bash
# Edition
LG_BACKEND_EDITION=enterprise
LG_CHANNEL=default

# Database
DB_USER=linkedin_gateway_user
DB_PASSWORD=<strong-random-password>
DB_NAME=LinkedinGateway

# API
PORT=7778
PUBLIC_URL=https://enterprise.example.com

# Security
SECRET_KEY=<64-char-hex-key>
JWT_SECRET_KEY=<64-char-hex-key>

# LinkedIn OAuth
LINKEDIN_CLIENT_ID=<your-client-id>
LINKEDIN_CLIENT_SECRET=<your-client-secret>

# CORS
CORS_ORIGINS=https://app.example.com,https://admin.example.com

# Enterprise Features (all optional)
ENT_FEATURE_ORGANIZATIONS=false
ENT_FEATURE_QUOTAS=false
ENT_FEATURE_AUDIT_LOGS=false

# Monitoring
SENTRY_DSN=<your-sentry-dsn>
SENTRY_ENVIRONMENT=production

# Rate Limiting
DEFAULT_RATE_LIMIT=200
DEFAULT_RATE_WINDOW=3600
```

---

## Security Best Practices

1. **Never commit `.env` files** to version control
2. **Use strong, randomly generated passwords** for database
3. **Generate unique secret keys** for each deployment
4. **Restrict CORS origins** in production
5. **Enable HTTPS** for all deployments
6. **Rotate secrets regularly** (especially JWT keys)
7. **Monitor Sentry alerts** for security issues
8. **Keep database access restricted** to backend only

---

## Troubleshooting

### Environment Variables Not Loading

- Verify `.env` file is in `deployment/` directory
- Check file encoding (should be UTF-8, no BOM)
- Ensure no spaces around `=` in variable assignments
- Check for syntax errors (quotes, special characters)

### OAuth Not Working

- Verify `PUBLIC_URL` is set and matches LinkedIn app config
- Ensure `PUBLIC_URL` starts with `https://`
- Check `LINKEDIN_CLIENT_ID` and `LINKEDIN_CLIENT_SECRET` are correct
- Verify callback URL in LinkedIn app: `{PUBLIC_URL}/auth/user/callback`

### Database Connection Fails

- Check `DB_*` variables are set correctly
- Verify PostgreSQL container is running: `docker compose ps`
- Test connection: `docker compose exec backend python -c "from app.db.session import engine; print(engine)"`
- Check database logs: `docker compose logs postgres`

---

**Last Updated**: 2025-10-29  
**Edition**: Enterprise  
**Version**: 1.0.0



