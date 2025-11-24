# Migration Rules - Quick Reference

**CRITICAL: Read this before creating any migrations!**

---

## 🏗️ Architecture Rule

### **Core is ALWAYS the Foundation**

```
ALL editions build on Core:

Core Edition:  [Core]
                  ↓
             Base layer

SaaS Edition:  [Core] ──> [SaaS]
                 ↑           ↑
            Runs first   Extends

Enterprise:    [Core] ──> [SaaS]
                 ↑           ↑
            Runs first   Extends
```

---

## ✅ DO's

### For Core Migrations (`alembic/versions/`)

✅ **Create for features that are:**
- Public/open-source functionality
- Base tables used by all editions
- Core business logic
- Authentication, users, basic data models

✅ **Example:**
```python
# versions/20241108_001_add_users.py
"""Add users table

Revision ID: abc123
Revises: None  # First migration or previous core migration
"""

def upgrade():
    op.create_table('users',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('email', sa.String(255), nullable=False),
        sa.Column('created_at', sa.DateTime())
    )
```

### For SaaS Migrations (`alembic/versions_saas/`)

✅ **Create for features that are:**
- SaaS-specific (billing, subscriptions, multi-tenancy)
- Commercial features not in open-source
- Extensions to core tables

✅ **MUST depend on a core migration:**
```python
# versions_saas/20241108_002_add_saas_billing.py
"""Add SaaS billing tables

Revision ID: xyz789
Revises: abc123  # ← MUST reference a core migration!
"""

def upgrade():
    # Option 1: Add new SaaS table
    op.create_table('saas_subscriptions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id')),  # References core
        sa.Column('tier', sa.String(50))
    )

    # Option 2: Extend core table
    op.add_column('users',  # Core table
        sa.Column('subscription_tier', sa.String(50))  # SaaS column
    )
```

---

## ❌ DON'Ts

### Never Do This:

❌ **SaaS migration without core dependency:**
```python
# versions_saas/xxxxx_bad_migration.py
"""BAD: No core dependency

Revision ID: xyz789
Revises: None  # ← WRONG! Must reference a core migration
"""
```

❌ **Replace core tables in SaaS:**
```python
# versions_saas/xxxxx_bad_migration.py
def upgrade():
    # WRONG! Don't drop or replace core tables
    op.drop_table('users')  # ← Core table!
    op.create_table('saas_users', ...)  # ← Don't replace core
```

❌ **Break core functionality:**
```python
# versions_saas/xxxxx_bad_migration.py
def upgrade():
    # WRONG! Don't make core columns nullable or change types
    op.alter_column('users', 'email',  # Core table
                   nullable=True)  # ← Breaks core expectation
```

---

## 📋 Quick Command Reference

### Creating Migrations

```bash
# Core migration (public features)
cd backend
alembic revision --autogenerate -m "add users table"
# → Creates: alembic/versions/xxxxx_add_users_table.py

# SaaS migration (private features)
cd backend
alembic revision --autogenerate \
    --version-path alembic/versions_saas \
    -m "add saas billing"
# → Creates: alembic/versions_saas/xxxxx_add_saas_billing.py
```

### Testing Migrations

```bash
# Test upgrade
alembic upgrade head

# Check current state
alembic current

# Test downgrade
alembic downgrade -1

# Test upgrade again
alembic upgrade head
```

### Running in Development

```bash
# All editions use same command
alembic upgrade head

# For SaaS, both core and SaaS migrations run automatically
```

### Running in Deployment

```bash
# Update scripts handle everything
./deployment/scripts/update_v2.sh core      # Core only
./deployment/scripts/update_v2.sh saas      # Core + SaaS
./deployment/scripts/update_v2.sh enterprise # Core + SaaS
```

---

## 🔍 Verification Checklist

Before committing a SaaS migration:

- [ ] Does it reference a core migration in `down_revision`?
- [ ] Does it extend (not replace) core tables?
- [ ] Can core edition still work without this migration?
- [ ] Have you tested both upgrade and downgrade?
- [ ] Have you tested with fresh database?
- [ ] Does it follow naming convention?

---

## 🎯 Migration Naming Convention

### Good Names:
```
✅ 20241108_001_add_users_table.py
✅ 20241108_002_add_email_verification.py
✅ 20241108_003_add_saas_billing_tables.py
✅ 20241109_001_add_subscription_tiers.py
```

### Bad Names:
```
❌ migration.py
❌ update.py
❌ abc123_changes.py
❌ temp_fix.py
```

---

## 🚨 Common Mistakes

### Mistake 1: Forgetting Dependency

```python
# WRONG
down_revision = None  # ← Missing core dependency
```

```python
# CORRECT
down_revision = 'abc123def456'  # ← Latest core migration
```

### Mistake 2: Modifying Core Schema in SaaS

```python
# WRONG - Don't modify core tables' structure
op.alter_column('users', 'email', type_=sa.Text())  # Changes core
```

```python
# CORRECT - Add new columns to core tables
op.add_column('users', sa.Column('saas_tier', sa.String(50)))  # Extends core
```

### Mistake 3: Creating Parallel Tables

```python
# WRONG - Don't create parallel versions
op.create_table('saas_users', ...)  # Parallel to 'users'
```

```python
# CORRECT - Extend existing table or create new feature table
op.add_column('users', ...)  # Extend
# OR
op.create_table('subscriptions', ...)  # New feature
```

---

## 📚 More Information

- **Full guide:** `backend/alembic/versions_saas/README.md`
- **Implementation details:** `SAAS_MIGRATIONS_FIX.md`
- **Update scripts:** `deployment/scripts/update_v2.sh` and `.bat`

---

## ⚡ TL;DR

1. **Core migrations** = Base for all editions (public)
2. **SaaS migrations** = Extend core (private)
3. **Every SaaS migration MUST reference a core migration**
4. **Never break core** - only extend it
5. **Update scripts handle everything automatically**

---

**Remember:** Core is the foundation. SaaS builds on top. Always.
