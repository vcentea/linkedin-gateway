# Database Password Authentication Error Fix

## The Problem

You're seeing this error in your logs:

```
asyncpg.exceptions.InvalidPasswordError: password authentication failed for user "linkedin_gateway_user"
```

**Root Cause:** The password in your `.env.prod.saas` file doesn't match the password stored in the PostgreSQL database container.

## Why This Happens

1. PostgreSQL initializes with credentials when the container is **first created**
2. Those credentials are stored in the Docker volume
3. Changing the password in `.env` later **doesn't update** the database
4. Backend tries to connect with the new `.env` password
5. Database rejects it with the old password

## 🔧 Solution 1: Update Database Password (Recommended)

**Use this if:** You want to keep your existing data

```bash
cd /path/to/LinkedinGateway-SaaS/deployment/scripts
./fix-db-password.sh
```

This will:
- Read the password from `.env.prod.saas`
- Update the PostgreSQL database to match
- Restart the backend
- ✅ Keep all your data

---

## 🔧 Solution 2: Reset Database (Clean Slate)

**Use this if:** Option 1 fails, or you're okay losing data

```bash
cd /path/to/LinkedinGateway-SaaS/deployment/scripts
./reset-db-saas.sh
```

⚠️ **WARNING:** This deletes ALL data:
- All users
- All posts  
- All profiles
- All API keys

---

## 🔧 Solution 3: Manual Fix (If Scripts Don't Work)

### On Linux/Ubuntu Production Server:

```bash
cd /path/to/LinkedinGateway-SaaS/deployment

# Get the password from .env
DB_PASSWORD=$(grep "^DB_PASSWORD=" .env.prod.saas | cut -d'=' -f2)

# Connect to PostgreSQL container and update password
docker compose -f docker-compose.yml -f docker-compose.saas.yml --env-file .env.prod.saas exec postgres psql -U linkedin_gateway_user -d LinkedinGateway

# Inside PostgreSQL prompt, run:
ALTER USER linkedin_gateway_user WITH PASSWORD 'YOUR_PASSWORD_FROM_ENV';
\q

# Restart backend
docker compose -f docker-compose.yml -f docker-compose.saas.yml --env-file .env.prod.saas restart backend
```

---

## How to Prevent This

### ✅ **Never Change Database Passwords After Deployment**

If you MUST change the password:

1. **Update the database first:**
   ```bash
   ./fix-db-password.sh  # Before changing .env
   ```

2. **Then update .env:**
   ```bash
   nano .env.prod.saas
   # Change DB_PASSWORD
   ```

3. **Restart services:**
   ```bash
   cd deployment/scripts
   ./update-saas.sh
   ```

---

## Verifying the Fix

After running the fix:

1. **Check backend logs:**
   ```bash
   cd deployment
   docker compose -f docker-compose.yml -f docker-compose.saas.yml --env-file .env.prod.saas logs -f backend
   ```

2. **Look for successful database connection:**
   ```
   ✓ Should see: "Connected to database"
   ❌ Should NOT see: "password authentication failed"
   ```

3. **Test authentication:**
   - Try logging in to your application
   - Check if OAuth callback works
   - Verify API endpoints work

---

## Still Not Working?

If you still get password errors after trying Solution 1 and 2:

1. **Check if .env.prod.saas is being read:**
   ```bash
   docker compose -f docker-compose.yml -f docker-compose.saas.yml --env-file .env.prod.saas config | grep DB_PASSWORD
   ```

2. **Check backend environment:**
   ```bash
   docker compose -f docker-compose.yml -f docker-compose.saas.yml --env-file .env.prod.saas exec backend env | grep DB_
   ```

3. **Check PostgreSQL logs:**
   ```bash
   docker compose -f docker-compose.yml -f docker-compose.saas.yml --env-file .env.prod.saas logs postgres
   ```

---

## Common Mistakes

❌ **Changing .env without updating database**
✅ Use `fix-db-password.sh` after changing .env

❌ **Using wrong .env file**
✅ Make sure you're editing `.env.prod.saas` not `.env`

❌ **Not restarting backend after fix**
✅ Always restart backend: `docker compose restart backend`

❌ **Database volume from old installation**
✅ Use `reset-db-saas.sh` for clean slate

