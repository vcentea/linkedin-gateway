# Deployment Workflow

## 🎯 Simple, Unified Deployment Strategy

Both **SaaS** (your single instance) and **Core** (customer self-hosted) follow the same simple workflow:

1. **Install script** creates `.env` with auto-generated credentials
2. **User manually edits** `.env` to add LinkedIn OAuth credentials
3. **Restart** services to apply changes

---

## 🏢 SaaS Deployment (Your Single Instance)

### Installation

```bash
cd deployment/scripts
./install-saas.sh
```

**What it does:**
1. ✅ Creates `.env` from `.env.example`
2. ✅ Prompts for port (default: 7778)
3. ✅ Auto-generates secure `DB_PASSWORD`
4. ✅ Auto-generates `SECRET_KEY` and `JWT_SECRET_KEY`
5. ✅ Sets `LG_BACKEND_EDITION=saas`
6. ✅ Starts services with `docker-compose.yml` + `docker-compose.saas.yml`

### Post-Installation Configuration

**Edit** `deployment/.env` to add your LinkedIn OAuth credentials:

```bash
# Open .env in your favorite editor
nano deployment/.env

# Add these values:
LINKEDIN_CLIENT_ID=your_actual_client_id
LINKEDIN_CLIENT_SECRET=your_actual_client_secret
PUBLIC_URL=https://your-actual-domain.com
```

**Restart** to apply changes:

```bash
cd deployment
docker compose -f docker-compose.yml -f docker-compose.saas.yml restart
```

---

## 🏠 Core Deployment (Customer Self-Hosted)

### Installation

```bash
cd deployment/scripts
./install-core.sh
```

**What it does:**
1. ✅ Creates `.env` from `.env.example`
2. ✅ Prompts for port (default: 7778)
3. ✅ Auto-generates secure `DB_PASSWORD`
4. ✅ Auto-generates `SECRET_KEY` and `JWT_SECRET_KEY`
5. ✅ Sets `LG_BACKEND_EDITION=core`
6. ✅ Starts services with `docker-compose.yml`

### Post-Installation Configuration

**Edit** `deployment/.env` to add LinkedIn OAuth credentials:

```bash
# Open .env in your favorite editor
nano deployment/.env

# Add these values:
LINKEDIN_CLIENT_ID=your_actual_client_id
LINKEDIN_CLIENT_SECRET=your_actual_client_secret
PUBLIC_URL=https://your-actual-domain.com
```

**Restart** to apply changes:

```bash
cd deployment
docker compose restart
```

---

## 📝 .env File Location

**Location:** `deployment/.env`

**Why this location?**
- ✅ Docker Compose expects it there
- ✅ No code changes needed
- ✅ Easy to find and edit
- ✅ Gitignored by default

**Security:**
- ❌ `.env` is **never** committed to git
- ✅ Only `.env.example` (with placeholders) is in git
- ✅ Each deployment has its own `.env` with real credentials

---

## 🔑 What Gets Auto-Generated

### Auto-Generated (You don't need to touch these):
- ✅ `DB_PASSWORD` - Random 16-character password
- ✅ `SECRET_KEY` - 64-character hex secret
- ✅ `JWT_SECRET_KEY` - 64-character hex secret
- ✅ `LG_BACKEND_EDITION` - Set based on install script
- ✅ `LG_CHANNEL` - Set to "default"
- ✅ `PORT` / `BACKEND_PORT` - Set to your chosen port (default 7778)

### Manual Configuration Required:
- ⚠️ `LINKEDIN_CLIENT_ID` - Get from LinkedIn Developer Portal
- ⚠️ `LINKEDIN_CLIENT_SECRET` - Get from LinkedIn Developer Portal
- ⚠️ `PUBLIC_URL` - Your public HTTPS URL (domain or tunnel)

---

## 🔄 Updating Services

### After editing .env:

**SaaS:**
```bash
cd deployment
docker compose -f docker-compose.yml -f docker-compose.saas.yml restart
```

**Core:**
```bash
cd deployment
docker compose restart
```

### To update code (rebuild containers):

**SaaS:**
```bash
cd deployment/scripts
./update-saas.sh  # TODO: Create this script
```

**Core:**
```bash
cd deployment/scripts
./update-core.sh
```

---

## 📊 Typical Workflow Example

### For Your SaaS Instance:

```bash
# 1. Initial install
cd deployment/scripts
./install-saas.sh
# → Prompted for port: Press Enter (uses 7778)
# → Services start, shows message about LinkedIn OAuth

# 2. Configure LinkedIn OAuth
nano deployment/.env
# Add:
#   LINKEDIN_CLIENT_ID=78abc...
#   LINKEDIN_CLIENT_SECRET=xyz789...
#   PUBLIC_URL=https://lg.ainnovate.tech

# 3. Restart to apply changes
cd deployment
docker compose -f docker-compose.yml -f docker-compose.saas.yml restart

# 4. Test
curl http://localhost:7778/health
# {"status":"ok"}

# 5. Check server info
curl http://localhost:7778/api/v1/server/info
# {
#   "edition": "saas",
#   "channel": "default",
#   "version": "0.1.0",
#   ...
# }
```

### For Customer Core Instance:

```bash
# 1. Customer runs install
cd deployment/scripts
./install-core.sh
# → Prompted for port: (customer enters their preferred port or uses default)
# → Services start

# 2. Customer edits .env
nano deployment/.env
# Customer adds their LinkedIn OAuth credentials

# 3. Customer restarts
cd deployment
docker compose restart

# 4. Customer tests
curl http://localhost:7778/health
```

---

## 🛡️ Security Notes

### What's Safe:
- ✅ `.env.example` in git (has placeholder values like `your_linkedin_client_id`)
- ✅ Auto-generated secrets (created by install script, never in git)

### What's NOT Safe:
- ❌ `.env` with real credentials in git
- ❌ Committing LinkedIn OAuth secrets
- ❌ Sharing `.env` files between deployments

### Best Practices:
1. ✅ Each deployment has its own `.env`
2. ✅ Use different LinkedIn OAuth apps for dev/staging/prod
3. ✅ Use HTTPS (PUBLIC_URL) for production
4. ✅ Keep `.env` file permissions restricted (chmod 600)
5. ✅ Back up `.env` securely (encrypted, not in git)

---

## 🎛️ Port Configuration

### Default Port: 7778

**Why 7778?**
- Not commonly used by other services
- Easy to remember
- High enough to avoid privileged ports

**Custom Port:**
During installation, you'll be prompted:
```
Port to use (press Enter for default 7778): 8080
```

**Change Port Later:**
1. Edit `deployment/.env`:
   ```
   PORT=8080
   BACKEND_PORT=8080
   ```
2. Restart services

---

## 📂 File Structure

```
LinkedinGateway-SaaS/
├── deployment/
│   ├── .env                    # ← Your real credentials (gitignored)
│   ├── .env.example            # ← Template with placeholders (in git)
│   ├── .env.saas.example       # ← SaaS-specific template (in git)
│   ├── docker-compose.yml      # ← Base config (in git)
│   ├── docker-compose.saas.yml # ← SaaS overrides (in git)
│   ├── Dockerfile              # ← App container (in git)
│   ├── scripts/
│   │   ├── install-core.sh     # ← Core install script (in git)
│   │   ├── install-core.bat    # ← Core install (Windows) (in git)
│   │   ├── install-saas.sh     # ← SaaS install script (in git)
│   │   ├── update-core.sh      # ← Core update script (in git)
│   │   └── update-core.bat     # ← Core update (Windows) (in git)
│   └── docs/
│       └── DEPLOYMENT_WORKFLOW.md  # ← This file
└── .gitignore                  # ← Includes deployment/.env
```

---

## ❓ FAQ

### Q: Should I commit `.env` to the private repo?
**A:** No. Even in private repos, real credentials should never be in git. Use the install script to generate `.env` on each deployment.

### Q: What if I lose my `.env` file?
**A:** You'll need to:
1. Re-run the install script (regenerates secrets)
2. Manually add LinkedIn OAuth credentials again
3. Database data is preserved (in Docker volume)

### Q: Can I use Railway environment variables instead?
**A:** Yes! Railway can inject env vars directly. In that case:
- Don't create `.env` file
- Set all variables in Railway dashboard
- Docker Compose will use Railway's env vars

### Q: How do I back up my configuration?
**A:** 
```bash
# Secure backup (encrypts .env)
gpg -c deployment/.env
# Creates deployment/.env.gpg (can be backed up safely)

# Restore
gpg deployment/.env.gpg
```

### Q: Different ports for SaaS and Core on same machine?
**A:**
```bash
# SaaS on 7778
cd deployment/scripts
./install-saas.sh
# Enter 7778 when prompted

# Core on 7779 (in different directory)
cd ../core-deployment/scripts
./install-core.sh
# Enter 7779 when prompted
```

---

## 🚀 Quick Reference

| Task | SaaS Command | Core Command |
|------|-------------|--------------|
| **Install** | `./install-saas.sh` | `./install-core.sh` |
| **Update** | `./update-saas.sh` | `./update-core.sh` |
| **Start** | `docker compose -f docker-compose.yml -f docker-compose.saas.yml up -d` | `docker compose up -d` |
| **Stop** | `docker compose -f docker-compose.yml -f docker-compose.saas.yml down` | `docker compose down` |
| **Restart** | `docker compose -f docker-compose.yml -f docker-compose.saas.yml restart` | `docker compose restart` |
| **Logs** | `docker compose -f docker-compose.yml -f docker-compose.saas.yml logs -f` | `docker compose logs -f` |
| **Edit Config** | `nano deployment/.env` | `nano deployment/.env` |

---

## ✅ Summary

**Simple Workflow:**
1. Run install script → generates `.env` with secure credentials
2. Edit `.env` → add LinkedIn OAuth credentials
3. Restart → done!

**Location:** `.env` stays in `deployment/.env` (no code changes needed)

**Security:** `.env` is gitignored, only `.env.example` is in git

**Same for Both:** SaaS and Core use identical workflow, just different scripts

