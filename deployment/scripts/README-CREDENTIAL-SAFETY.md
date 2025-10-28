# Credential Safety in Install/Update Scripts

## 🔒 Important: Credentials Are Never Overwritten

All install and update scripts have been designed to **NEVER overwrite existing credentials** unless they are exact placeholder values.

## How It Works

### ✅ Safe - Credentials Are Kept

The scripts will **KEEP** your existing credentials if they contain **ANY custom value**:

```bash
DB_PASSWORD=LinkedinGW202500213350525672   # ✅ KEPT
DB_PASSWORD=myP@ssw0rd123                  # ✅ KEPT
DB_PASSWORD=SuperSecure!2024               # ✅ KEPT
SECRET_KEY=abc123xyz789                    # ✅ KEPT
```

### 🔄 Regenerated - Only Exact Placeholders

The scripts will **ONLY regenerate** if the value is **EXACTLY** one of these:

```bash
DB_PASSWORD=CHANGE_THIS_TO_A_RANDOM_SECRET_KEY  # 🔄 Regenerated
DB_PASSWORD=change_this_password                # 🔄 Regenerated
DB_PASSWORD=your_strong_password_here           # 🔄 Regenerated
DB_PASSWORD=postgres                            # 🔄 Regenerated
DB_PASSWORD=                                    # 🔄 Regenerated (empty)

SECRET_KEY=CHANGE_THIS_TO_A_RANDOM_SECRET_KEY   # 🔄 Regenerated
SECRET_KEY=change_this_secret_key               # 🔄 Regenerated
SECRET_KEY=                                     # 🔄 Regenerated (empty)

JWT_SECRET_KEY=CHANGE_THIS_TO_A_RANDOM_SECRET_KEY  # 🔄 Regenerated
JWT_SECRET_KEY=change_this_secret_key              # 🔄 Regenerated
JWT_SECRET_KEY=                                    # 🔄 Regenerated (empty)
```

## Protected Credentials

The following credentials in `.env` files are protected:

1. **`DB_PASSWORD`** - Database password
2. **`SECRET_KEY`** - Application secret key
3. **`JWT_SECRET_KEY`** - JWT signing key

## Scripts That Handle Credentials

### Installation Scripts

- **`install.sh`** - Generates credentials **ONLY on first install**
- **`install-core.sh`** - Wrapper for install.sh
- **`install-saas.sh`** - Wrapper for install.sh

**Behavior:**
- Checks if credentials exist
- Only generates if empty or exact placeholder
- Shows which credentials were kept vs generated

### Update Scripts  

- **`update-saas.sh`** - Does **NOT** touch credentials at all
- **`update-core.sh`** - Does **NOT** touch credentials at all
- **`update-backend.sh`** - Does **NOT** touch credentials at all

**Behavior:**
- Never modifies `.env` file
- Only pulls code and rebuilds containers
- Existing credentials remain unchanged

## What If I Need to Change Credentials?

### Option 1: Manual Edit (Recommended)

```bash
# Edit the .env file
nano deployment/.env.prod.saas

# Update the password
DB_PASSWORD=YourNewPassword123

# Fix the database to match
cd deployment/scripts
./fix-db-password.sh
```

### Option 2: Delete and Regenerate

⚠️ **WARNING: This will delete all data!**

```bash
# Remove the .env file
rm deployment/.env.prod.saas

# Run install again to regenerate
cd deployment/scripts
./install-saas.sh
```

## Verification

After running install scripts, you should see output like:

```
[2/6] Generating secure credentials...
  ✓ DB_PASSWORD already set (keeping existing: LinkedinGW***)
  ✓ SECRET_KEY already set (keeping existing)
  ✓ JWT_SECRET_KEY already set (keeping existing)
```

If you see "Generating new" instead of "already set", that means the old value was a placeholder.

## Common Scenarios

### Scenario 1: First Time Install
```bash
./install-saas.sh
```
**Result:** All credentials are generated ✅

### Scenario 2: Reinstall with Existing .env
```bash
# .env exists with real passwords
./install-saas.sh
```
**Result:** Existing credentials are kept ✅

### Scenario 3: Update Production
```bash
./update-saas.sh
```
**Result:** Credentials are never touched ✅

### Scenario 4: .env Has Placeholders
```bash
# .env has: DB_PASSWORD=CHANGE_THIS_TO_A_RANDOM_SECRET_KEY
./install-saas.sh
```
**Result:** Only placeholders are regenerated ✅

## Troubleshooting

### "My password was overwritten!"

**Before the fix (OLD behavior):**
- Scripts used regex patterns like `grep -Eq "CHANGE|change"`
- This would match ANY password containing "change" or "CHANGE"
- Example: `MyPasswordChanged123` would be regenerated ❌

**After the fix (NEW behavior):**
- Scripts use exact string matching: `[ "$DB_PASSWORD" = "CHANGE_THIS_TO_A_RANDOM_SECRET_KEY" ]`
- Only EXACT placeholders are regenerated
- Example: `MyPasswordChanged123` is kept ✅

### "I accidentally ran install on production"

**No problem!** The install script now:
1. Detects existing credentials
2. Shows what it's keeping vs regenerating
3. Never overwrites custom values

### "How do I verify my credentials are safe?"

```bash
# Check what's in your .env
grep "^DB_PASSWORD=" deployment/.env.prod.saas
grep "^SECRET_KEY=" deployment/.env.prod.saas
grep "^JWT_SECRET_KEY=" deployment/.env.prod.saas

# Run install in dry-run mode (just check, don't change)
# (scripts will show what they would do without actually changing)
```

## Safety Guarantees

✅ **Existing production passwords are NEVER overwritten**
✅ **Scripts only regenerate exact placeholder values**
✅ **Update scripts NEVER touch credentials**
✅ **You'll see clear messages about what's kept vs generated**
✅ **Database integrity is preserved**

## Files Modified

- `deployment/scripts/install.sh` - Fixed credential detection
- `deployment/scripts/update-saas.sh` - Never touches .env
- `deployment/scripts/update-core.sh` - Never touches .env
- `deployment/scripts/update-backend.sh` - Never touches .env

## Questions?

If a script regenerated your password when it shouldn't have:
1. Check if the old password contained EXACTLY a placeholder string
2. Use `fix-db-password.sh` to sync database with current .env
3. Report the issue so we can add more safety checks

