# Deployment Recommendations

## 🔒 Security Best Practices

### Never Commit Secrets to Git

**Rule:** `.env` files with real credentials should **NEVER** be committed to git, even in private repositories.

**Why?**
- Git preserves history forever—secrets can't be easily removed
- Repository access might expand over time
- Accidental public exposure would leak all secrets
- Industry standard: secrets in environment, not code

---

## 🚀 SaaS Deployment (Our Single Instance)

### Option 1: Platform Environment Variables (Recommended)

**Platforms:** Railway, Heroku, AWS ECS, Google Cloud Run, etc.

**Setup:**
1. Deploy from git (no `.env` in repo)
2. Set environment variables in platform UI:
   ```
   DATABASE_URL=postgresql://user:pass@host:5432/db
   SECRET_KEY=<generated-secret>
   JWT_SECRET_KEY=<generated-secret>
   LINKEDIN_CLIENT_ID=<your-id>
   LINKEDIN_CLIENT_SECRET=<your-secret>
   PUBLIC_URL=https://yourdomain.com
   LG_BACKEND_EDITION=saas
   LG_CHANNEL=default
   ```
3. Platform injects env vars into container at runtime

**Advantages:**
- ✅ No secrets in git
- ✅ Easy to rotate secrets
- ✅ Built-in secrets management
- ✅ Different values per environment (dev/staging/prod)

---

### Option 2: Secrets Manager

**Platforms:** AWS Secrets Manager, HashiCorp Vault, GCP Secret Manager

**Setup:**
1. Store secrets in secrets manager
2. Application fetches secrets at startup
3. Requires code changes to integrate

**Advantages:**
- ✅ Centralized secret management
- ✅ Audit logging
- ✅ Automatic rotation
- ✅ Fine-grained access control

---

### Option 3: External Config File (Docker Volume)

**For:** Development, staging, or small deployments

**Setup:**
```bash
# Create config directory (gitignored)
mkdir -p config
cp .env.saas.example config/.env

# Edit with real values
nano config/.env
```

**docker-compose.saas.yml:**
```yaml
services:
  backend:
    volumes:
      - ./config/.env:/app/.env:ro  # Read-only mount
```

**.gitignore:**
```
config/
*.env
!*.env.example
```

**Advantages:**
- ✅ Simple setup
- ✅ No platform lock-in
- ✅ Easy local development
- ⚠️  Manual secret management

---

## 🏠 Core Deployment (Customer Self-Hosted)

### Recommended: Interactive Install Script

**The install script should:**
1. ✅ Auto-generate secure secrets (SECRET_KEY, JWT_SECRET_KEY)
2. ✅ Prompt for critical values (DB password, OAuth credentials)
3. ✅ Validate input (non-empty, format checks)
4. ✅ Save to `.env` (which is gitignored)
5. ✅ Provide clear instructions

**Enhanced Install Flow:**
```bash
./install-core.sh

# Output:
[1/5] Environment Setup
  → .env not found, let's create it...

  🔐 Database Password (leave empty to generate random):
  [user enters: my_secure_db_pass_123]
  ✓ DB_PASSWORD set

  🔑 LinkedIn OAuth Setup
  Get credentials from: https://www.linkedin.com/developers/apps
  
  LinkedIn Client ID:
  [user enters: 78abc...]
  ✓ LINKEDIN_CLIENT_ID set

  LinkedIn Client Secret:
  [user enters: xyz789...]
  ✓ LINKEDIN_CLIENT_SECRET set

  🌐 Public URL (for OAuth callback):
  Example: https://yourdomain.com or https://tunnel.trycloudflare.com
  [user enters: https://lg.example.com]
  ✓ PUBLIC_URL set

[2/5] Generating Secrets...
  ✓ Generated SECRET_KEY
  ✓ Generated JWT_SECRET_KEY
  ✓ Set edition to core
  ✓ Set channel to default

[3/5] Starting Services...
  ✓ Docker Compose up
  ...
```

---

## 📝 Environment Variables Priority

**Docker Compose Variable Resolution (in order):**
1. Environment variables set in shell
2. Variables in `.env` file
3. Defaults in `docker-compose.yml`
4. Dockerfile `ENV` statements

**Example:**
```bash
# This overrides .env file
DATABASE_URL=postgres://... docker compose up

# This uses .env file
docker compose up
```

---

## 🔄 Rotating Secrets

### For SaaS:
1. Generate new secret in platform UI
2. Update environment variable
3. Restart service (zero-downtime if using blue-green deployment)

### For Core (Customer):
1. Edit `.env` file
2. Run `./update-core.sh` or `docker compose restart`

---

## 🛡️ Security Checklist

### SaaS Deployment:
- [ ] `.env` files are in `.gitignore`
- [ ] No secrets committed to git history
- [ ] Secrets stored in platform env vars or secrets manager
- [ ] `PUBLIC_URL` set to HTTPS domain
- [ ] `BEHIND_PROXY=true` for reverse proxy/tunnel
- [ ] Different secrets for dev/staging/prod
- [ ] Regular secret rotation schedule

### Core Deployment:
- [ ] Install script prompts for critical values
- [ ] `.env.example` has placeholder values only
- [ ] Database password is strong or auto-generated
- [ ] OAuth credentials required for installation
- [ ] Clear documentation for customers
- [ ] Update script preserves `.env` changes

---

## 📦 What Goes Where

### ✅ Commit to Git:
- `.env.example` (with placeholder values)
- `docker-compose.yml`
- `docker-compose.saas.yml`
- Deployment scripts
- Documentation

### ❌ Never Commit to Git:
- `.env` (real credentials)
- `config/.env` (external config)
- Database dumps with data
- API keys, tokens, passwords
- Private keys, certificates

---

## 🎯 Current Action Items

### For SaaS:
1. Add `config/` to `.gitignore`
2. Create `config/.env` with real credentials (local only)
3. Document how to set Railway/platform env vars
4. Or: Implement secrets manager integration

### For Core:
1. Enhance install script with interactive prompts
2. Validate input (non-empty, format checks)
3. Add `--unattended` mode for CI/CD
4. Provide clear error messages

---

## 🔍 Example: Railway Setup

**1. Push code (no .env in repo)**
```bash
git push railway main
```

**2. Set environment variables in Railway dashboard:**
```
DATABASE_URL → (auto-provided by Railway Postgres plugin)
SECRET_KEY → (generate: openssl rand -hex 32)
JWT_SECRET_KEY → (generate: openssl rand -hex 32)
LINKEDIN_CLIENT_ID → 78abc...
LINKEDIN_CLIENT_SECRET → xyz789...
PUBLIC_URL → https://your-app.up.railway.app
LG_BACKEND_EDITION → saas
LG_CHANNEL → default
PORT → 7778
```

**3. Deploy automatically**
Railway injects env vars and deploys.

---

## 📚 Additional Resources

- [12-Factor App: Config](https://12factor.net/config)
- [OWASP: Secure Configuration](https://owasp.org/www-project-top-ten/2017/A6_2017-Security_Misconfiguration)
- [Docker Secrets](https://docs.docker.com/engine/swarm/secrets/)
- [Railway Environment Variables](https://docs.railway.app/develop/variables)

