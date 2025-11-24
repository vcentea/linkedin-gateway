# Database Setup & Initialization

## 🔄 How Database Initialization Works

### Automatic Setup by PostgreSQL Docker Container

When you run the install script, **PostgreSQL automatically handles everything**:

```bash
./install-core.sh  # or install-saas.sh
```

#### What Happens Automatically:

1. **Docker Compose reads `.env` file** → Gets `DB_USER`, `DB_PASSWORD`, `DB_NAME`

2. **PostgreSQL container starts** with environment variables:
   ```yaml
   POSTGRES_USER: ${DB_USER}           # Creates this user
   POSTGRES_PASSWORD: ${DB_PASSWORD}   # Sets this password
   POSTGRES_DB: ${DB_NAME}             # Creates this database
   ```

3. **PostgreSQL automatically**:
   - ✅ Creates the user with the generated password
   - ✅ Creates the database
   - ✅ Grants ALL privileges to the user on the database
   - ✅ Runs all SQL scripts from `/docker-entrypoint-initdb.d/`

4. **Our init script (`01-create-schema.sql`) runs automatically**:
   - ✅ Creates all 13 tables
   - ✅ Creates all indexes
   - ✅ Sets up foreign keys
   - ✅ Creates triggers for timestamps
   - ✅ Inserts initial data (Free tier)

5. **Backend API waits** for PostgreSQL healthcheck to pass before starting

---

## 📝 Generated Password

### Where is it generated?

**Script Step [2/7]:**
```bash
[2/7] Generating secure credentials...
  → Generated secure DB password: Abc12...xyz
  ✓ DB_PASSWORD saved to .env
  ✓ Generated SECRET_KEY
  ✓ Generated JWT_SECRET_KEY
```

### Password Generation Logic:

```bash
# 20 alphanumeric characters (letters + digits only)
openssl rand -base64 32 | tr -dc 'a-zA-Z0-9' | head -c 20
```

**Example:** `Abc123XyzDef456Ghi78`

### Where is it saved?

1. **`deployment/.env`** → Used by Docker Compose
2. **`backend/.env`** → Copied there for the app to read
3. **Environment variable** → Passed to PostgreSQL container

---

## 🔍 How to View Database Initialization Logs

### View PostgreSQL Container Logs:

```bash
# Core deployment
docker compose -f deployment/docker-compose.yml logs postgres

# SaaS deployment
docker compose -f deployment/docker-compose.yml -f deployment/docker-compose.saas.yml logs postgres
```

### What you'll see:

```log
postgres_1  | PostgreSQL init process complete; ready for start up.
postgres_1  | 
postgres_1  | 2025-10-18 10:00:00.000 UTC [1] LOG:  database system is ready to accept connections
postgres_1  | 
postgres_1  | /docker-entrypoint-initdb.d/01-create-schema.sql: running /docker-entrypoint-initdb.sql
postgres_1  | CREATE EXTENSION
postgres_1  | CREATE TABLE
postgres_1  | CREATE TABLE
postgres_1  | CREATE INDEX
postgres_1  | ...
postgres_1  | INSERT 0 1
postgres_1  | 
postgres_1  | PostgreSQL Database initialized successfully!
```

### View Backend API Logs:

```bash
# Core
docker compose -f deployment/docker-compose.yml logs backend

# SaaS
docker compose -f deployment/docker-compose.yml -f deployment/docker-compose.saas.yml logs backend
```

### View All Logs Together:

```bash
# Core
docker compose -f deployment/docker-compose.yml logs -f

# SaaS
docker compose -f deployment/docker-compose.yml -f deployment/docker-compose.saas.yml logs -f
```

(`-f` follows logs in real-time, press Ctrl+C to exit)

---

## 🎯 Startup Order

Docker Compose ensures proper startup order:

```yaml
backend:
  depends_on:
    postgres:
      condition: service_healthy  # ← Backend waits for this!
```

### Timeline:

```
[0s]   PostgreSQL container starts
[0-10s] PostgreSQL initializes (creates user, DB, runs scripts)
[10s]  PostgreSQL healthcheck passes
[10s]  Backend API starts (can now connect to DB)
[40s]  Backend API healthcheck passes
[40s]  ✅ All services ready!
```

---

## 🔐 Database Credentials

### Where are they used?

| File | Purpose | Contains |
|------|---------|----------|
| `deployment/.env` | Docker Compose reads this | `DB_USER`, `DB_PASSWORD`, `DB_NAME`, `DB_PORT=5432` |
| `backend/.env` | FastAPI app reads this | Same values (copied from deployment/.env) |
| PostgreSQL container | Created with these credentials | User, password, database |

### Environment Variables in Docker Compose:

```yaml
postgres:
  environment:
    POSTGRES_USER: ${DB_USER}           # From .env
    POSTGRES_PASSWORD: ${DB_PASSWORD}   # From .env
    POSTGRES_DB: ${DB_NAME}             # From .env

backend:
  environment:
    DB_HOST: postgres                   # Container name
    DB_PORT: 5432                       # Internal port
    DB_USER: ${DB_USER}                 # From .env
    DB_PASSWORD: ${DB_PASSWORD}         # From .env
    DB_NAME: ${DB_NAME}                 # From .env
```

---

## 📊 Database Schema

### Tables Created by `01-create-schema.sql`:

1. **`billing_tiers`** - Subscription tiers (Free, Pro, Enterprise)
2. **`users`** - User accounts
3. **`user_sessions`** - Active sessions
4. **`user_subscriptions`** - User subscription info
5. **`billing_history`** - Payment history
6. **`api_keys`** - API key management
7. **`rate_limits`** - Rate limiting config
8. **`api_usage_logs`** - API usage tracking
9. **`profiles`** - LinkedIn profile cache
10. **`posts`** - LinkedIn posts
11. **`user_post_mapping`** - User-post relationships
12. **`message_histories`** - LinkedIn messages
13. **`connection_requests`** - Connection tracking

### Initial Data:

```sql
INSERT INTO billing_tiers (name, price, limits) 
VALUES ('Free', 0, '{"max_api_keys": 1, "max_requests_per_day": 100}');
```

---

## 🛠️ Manual Database Access

### Connect to PostgreSQL Container:

```bash
# Get container ID
docker ps | grep postgres

# Connect to psql
docker exec -it linkedin-gateway-core-db psql -U linkedin_gateway_user -d LinkedinGateway
```

### Check Tables:

```sql
-- List all tables
\dt

-- Describe a table
\d users

-- Query data
SELECT * FROM billing_tiers;

-- Exit
\q
```

---

## ❓ Troubleshooting

### Problem: "Password is just '+'"

**Cause:** Old buggy password generation  
**Fix:** Run install script again, it will regenerate:
```bash
rm deployment/.env backend/.env
./install-core.sh
```

### Problem: "Database connection failed"

**Check PostgreSQL health:**
```bash
docker ps  # Should show "healthy" status
docker compose logs postgres  # Check for errors
```

**Verify credentials:**
```bash
grep DB_PASSWORD deployment/.env
grep DB_PASSWORD backend/.env
# Should be the same 20-char alphanumeric password
```

### Problem: "Tables don't exist"

**Check if init script ran:**
```bash
docker compose logs postgres | grep "01-create-schema.sql"
```

**If not found, restart to trigger init:**
```bash
docker compose down -v  # ⚠️ Deletes all data!
./install-core.sh       # Runs init scripts again
```

### Problem: "Backend won't start"

**Check backend logs:**
```bash
docker compose logs backend
```

**Common issues:**
- Database not healthy yet → Wait 10-20 seconds
- Wrong credentials → Check .env files match
- Port conflict → Change PORT in .env

---

## 📖 Additional Commands

### Restart Services:

```bash
docker compose restart
```

### Stop Services:

```bash
docker compose down
```

### Stop & Remove All Data:

```bash
docker compose down -v  # ⚠️ Deletes database volume!
```

### View Service Status:

```bash
docker compose ps
```

### Rebuild Containers:

```bash
docker compose up -d --build
```

---

## ✅ What Install Script Does

### Summary of [2/7] - Generating Credentials:

```bash
[2/7] Generating secure credentials...
```

**Actions:**
1. ✅ Generates 20-char alphanumeric `DB_PASSWORD`
2. ✅ Shows preview: `Abc12...xyz`
3. ✅ Saves to `deployment/.env`
4. ✅ Generates 64-char hex `SECRET_KEY`
5. ✅ Generates 64-char hex `JWT_SECRET_KEY`
6. ✅ Sets `LG_BACKEND_EDITION` and `LG_CHANNEL`

### Summary of [3/7] - Copying Config:

```bash
[3/7] Copying configuration to backend...
```

**Actions:**
1. ✅ Copies `deployment/.env` → `backend/.env`
2. ✅ Both files now have the same credentials

### Summary of [5/7] - Database Initialization:

```bash
[5/7] Checking database initialization...
  → PostgreSQL will automatically:
    • Create user: linkedin_gateway_user
    • Create database: LinkedinGateway
    • Run init scripts from: deployment/init-scripts/
    • Set up all tables, indexes, and initial data

  💡 To view database logs:
     docker compose logs postgres
```

**This happens automatically via:**
- PostgreSQL Docker image entrypoint
- Volume mount: `./init-scripts:/docker-entrypoint-initdb.d`
- Environment variables from `.env`

---

## 🎉 Summary

**Everything is automatic!** You just need to:

1. Run install script
2. See the generated password preview
3. Wait for deployment to complete
4. Check logs if you want to verify: `docker compose logs postgres`

**No manual database setup required!** ✨

