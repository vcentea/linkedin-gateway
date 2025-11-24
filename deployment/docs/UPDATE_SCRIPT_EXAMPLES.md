# Update Script Usage Examples

## Basic Usage

### Standard Update (Most Common)
Pulls latest code from main branch and rebuilds:

**Windows:**
```cmd
cd deployment\scripts
update-backend.bat core
```

**Linux/Mac:**
```bash
cd deployment/scripts
./update-backend.sh core
```

**What happens:**
1. ✅ Fetches from Git remote (origin)
2. ✅ Checks for uncommitted changes (warns if found)
3. ✅ Pulls from origin/main
4. ✅ Rebuilds Docker image
5. ✅ Restarts backend container
6. ✅ Shows container status and logs

---

## Different Editions

### Update Core Edition (Open Source)
```bash
./update-backend.sh core
```

### Update SaaS Edition (Multi-tenant)
```bash
./update-backend.sh saas
```

---

## Branch Selection

### Update from Development Branch
```bash
./update-backend.sh core --branch develop
```

### Update from Feature Branch
```bash
./update-backend.sh core --branch feature/new-authentication
```

### Update from Specific Tag/Release
```bash
# First checkout the tag manually
git fetch --tags
git checkout v1.2.3

# Then update without pulling
./update-backend.sh core --no-pull
```

---

## Skip Git Pull

### Use Local Code (Already Pulled)
```bash
# If you already pulled manually:
git pull origin main

# Then rebuild without pulling again:
./update-backend.sh core --no-pull
```

### Use Uncommitted Changes
```bash
# You have local changes you want to test
# Skip pull to avoid conflicts:
./update-backend.sh core --no-pull
```

### Test Local Development
```bash
# You made changes locally and want to test in production mode
./update-backend.sh core --no-pull
```

---

## Combined Options

### SaaS Edition from Develop Branch
```bash
./update-backend.sh saas --branch develop
```

### Core Edition, Custom Branch, No Pull
```bash
./update-backend.sh core --branch hotfix/urgent-fix --no-pull
```

---

## Real-World Scenarios

### Scenario 1: Normal Production Update
**Situation:** Your CI/CD pushed new code to main, you want to deploy.

```bash
cd /path/to/LinkedinGateway-SaaS/deployment/scripts
./update-backend.sh core
```

**Script does:**
- Pulls latest from origin/main
- Checks for conflicts
- Rebuilds with latest code
- Restarts container

---

### Scenario 2: Hot Fix Deployment
**Situation:** Critical bug fix pushed to main, need immediate deployment.

```bash
cd /path/to/LinkedinGateway-SaaS/deployment/scripts
./update-backend.sh core --branch main
# Same as default, explicitly using main
```

---

### Scenario 3: Testing Feature Branch
**Situation:** QA wants to test a feature branch before merging.

```bash
# Method 1: Let script handle it
./update-backend.sh core --branch feature/user-api-improvements

# Method 2: Manual checkout
git fetch origin
git checkout feature/user-api-improvements
git pull origin feature/user-api-improvements
./update-backend.sh core --no-pull
```

---

### Scenario 4: You Have Local Uncommitted Changes
**Situation:** You edited files locally and want to include them in build.

```bash
# Check what you changed
git status
git diff

# Build with local changes
./update-backend.sh core --no-pull
```

**Script will:**
- Skip git pull
- Build with your local changes
- Deploy modified code

---

### Scenario 5: Rollback to Previous Version
**Situation:** New deployment has issues, need to rollback.

```bash
# Option 1: Use git tag
git fetch --tags
git checkout v1.2.2
./update-backend.sh core --no-pull

# Option 2: Use commit hash
git checkout abc123def456
./update-backend.sh core --no-pull

# Option 3: Use branch with previous code
git checkout main
git reset --hard HEAD~1  # Go back 1 commit
./update-backend.sh core --no-pull
```

---

### Scenario 6: Multi-Server Deployment
**Situation:** Deploying to multiple servers (server1, server2, server3).

```bash
# On each server:
ssh user@server1 "cd /path/to/app/deployment/scripts && ./update-backend.sh core"
ssh user@server2 "cd /path/to/app/deployment/scripts && ./update-backend.sh core"
ssh user@server3 "cd /path/to/app/deployment/scripts && ./update-backend.sh core"

# Or with a loop:
for server in server1 server2 server3; do
    ssh user@$server "cd /path/to/app/deployment/scripts && ./update-backend.sh core"
done
```

---

### Scenario 7: Scheduled Updates (Cron)
**Situation:** Automatic nightly updates.

```bash
# Add to crontab:
crontab -e

# Deploy every night at 2 AM
0 2 * * * cd /path/to/LinkedinGateway-SaaS/deployment/scripts && ./update-backend.sh core >> /var/log/linkedin-gateway-updates.log 2>&1
```

---

### Scenario 8: Update with Environment Changes
**Situation:** You updated .env file AND code.

```bash
# 1. Update .env file first
nano /path/to/LinkedinGateway-SaaS/deployment/.env

# 2. Run update script
cd /path/to/LinkedinGateway-SaaS/deployment/scripts
./update-backend.sh core

# 3. If .env changes only (no code changes):
cd /path/to/LinkedinGateway-SaaS/deployment
docker compose up -d --force-recreate backend
```

---

## Error Handling

### Git Fetch Failed
```
WARNING: Git fetch failed! Continuing with local code...
```
**Reason:** Network issue, Git remote not configured, or no internet.
**Solution:** Script continues with local code. Fix network and try again.

---

### Uncommitted Changes Warning
```
WARNING: You have uncommitted changes!
These changes will be included in the build.

Continue with build? (y/N):
```
**Action Required:** 
- Press `y` to continue with local changes
- Press `n` to cancel, commit changes, then retry

---

### Git Pull Failed
```
ERROR: Git pull failed! Please resolve conflicts manually.
```
**Reason:** Git conflicts between local and remote.
**Solution:**
```bash
# View conflicts
git status
git diff

# Resolve manually or reset
git reset --hard origin/main

# Then retry
./update-backend.sh core
```

---

### Docker Build Failed
```
ERROR: Build failed!
```
**Reason:** Syntax error in code, missing dependencies, or Dockerfile issue.
**Solution:**
```bash
# Check logs
cd ../deployment
docker compose logs backend

# View build output
docker compose build backend

# Fix issues and retry
```

---

## Best Practices

### ✅ Do's

1. **Test in staging first:**
   ```bash
   # On staging server
   ./update-backend.sh core --branch develop
   ```

2. **Backup database before major updates:**
   ```bash
   docker compose exec postgres pg_dump -U linkedin_gateway_user LinkedinGateway > backup-$(date +%Y%m%d).sql
   ```

3. **Check health after update:**
   ```bash
   ./update-backend.sh core
   curl http://localhost:7778/health
   docker compose logs -f backend
   ```

4. **Use branches for testing:**
   ```bash
   ./update-backend.sh core --branch feature/test
   ```

### ❌ Don'ts

1. **Don't use --no-pull without knowing what's deployed:**
   ```bash
   # Bad: You might deploy old code
   ./update-backend.sh core --no-pull
   ```

2. **Don't update during peak hours without planning**

3. **Don't skip checking logs after update**

4. **Don't force push to main then deploy:**
   ```bash
   # Bad workflow:
   git push --force origin main  # Dangerous!
   ./update-backend.sh core      # Might deploy broken code
   ```

---

## Monitoring Updates

### Watch Deployment in Real-Time
```bash
# Terminal 1: Run update
./update-backend.sh core

# Terminal 2: Watch logs
docker compose logs -f backend

# Terminal 3: Monitor resources
docker stats
```

### Post-Deployment Health Check
```bash
# Check container is running
docker compose ps backend

# Check health endpoint
curl http://localhost:7778/health

# Check version/info endpoint
curl http://localhost:7778/info

# Tail logs for errors
docker compose logs --tail=100 backend | grep -i error
```

---

## Automation Examples

### Update Script with Slack Notification
```bash
#!/bin/bash
cd /path/to/LinkedinGateway-SaaS/deployment/scripts

if ./update-backend.sh core; then
    curl -X POST -H 'Content-type: application/json' \
      --data '{"text":"✅ Backend updated successfully!"}' \
      YOUR_SLACK_WEBHOOK_URL
else
    curl -X POST -H 'Content-type: application/json' \
      --data '{"text":"❌ Backend update failed! Check logs."}' \
      YOUR_SLACK_WEBHOOK_URL
fi
```

### Update with Discord Webhook
```bash
#!/bin/bash
DISCORD_WEBHOOK="your_discord_webhook_url"

cd /path/to/LinkedinGateway-SaaS/deployment/scripts

if ./update-backend.sh core; then
    curl -H "Content-Type: application/json" \
      -d '{"content": "✅ LinkedIn Gateway updated successfully!"}' \
      $DISCORD_WEBHOOK
else
    curl -H "Content-Type: application/json" \
      -d '{"content": "❌ LinkedIn Gateway update failed!"}' \
      $DISCORD_WEBHOOK
fi
```

---

## Summary

| Command | Git Pull | Rebuild | Use Case |
|---------|----------|---------|----------|
| `./update-backend.sh core` | ✅ main | ✅ | Standard update |
| `./update-backend.sh saas` | ✅ main | ✅ | SaaS edition update |
| `./update-backend.sh core --branch develop` | ✅ develop | ✅ | Test dev branch |
| `./update-backend.sh core --no-pull` | ❌ | ✅ | Use local code |
| `./update-backend.sh saas --branch hotfix --no-pull` | ❌ | ✅ | SaaS with local code |

---

**Quick Reference:**
```bash
# Most common usage:
./update-backend.sh core               # Pull from main + rebuild

# Test different branch:
./update-backend.sh core --branch dev  # Pull from dev + rebuild

# Use local changes:
./update-backend.sh core --no-pull     # No pull + rebuild
```

