# Alembic Database Migrations

This directory contains database migrations for the LinkedinGateway application using Alembic.

## Creating Idempotent Migrations

All migrations should be **idempotent** - they can be run multiple times safely without errors. This is essential because:

- Databases may already have some columns from manual changes
- Upgrades can be retried if they fail partway through
- Multiple environments may be at different migration states

### Helper Utilities

Use the helper functions in `migration_helpers.py` to create idempotent migrations automatically.

### Quick Start Templates

#### 1. Adding a Single Column

```python
"""Add email column to users

Revision ID: add_user_email
Revises: previous_migration_id
Create Date: 2025-01-15
"""
from alembic import op
import sqlalchemy as sa
from alembic.migration_helpers import add_column_if_not_exists, drop_column_if_exists

# revision identifiers
revision = 'add_user_email'
down_revision = 'previous_migration_id'

def upgrade():
    """Add email column to users table."""
    add_column_if_not_exists(
        'users',
        sa.Column('email', sa.String(length=255), nullable=False)
    )

def downgrade():
    """Remove email column from users table."""
    drop_column_if_exists('users', 'email')
```

#### 2. Adding Multiple Columns

```python
"""Add profile fields to users

Revision ID: add_user_profile
Revises: previous_migration_id
Create Date: 2025-01-15
"""
from alembic import op
import sqlalchemy as sa
from alembic.migration_helpers import add_columns_if_not_exist, drop_column_if_exists

revision = 'add_user_profile'
down_revision = 'previous_migration_id'

def upgrade():
    """Add profile columns to users table."""
    add_columns_if_not_exist('users', [
        sa.Column('bio', sa.Text(), nullable=True),
        sa.Column('avatar_url', sa.String(length=1024), nullable=True),
        sa.Column('location', sa.String(length=255), nullable=True)
    ])

def downgrade():
    """Remove profile columns from users table."""
    drop_column_if_exists('users', 'location')
    drop_column_if_exists('users', 'avatar_url')
    drop_column_if_exists('users', 'bio')
```

#### 3. Creating an Index

```python
"""Add index on user email

Revision ID: idx_user_email
Revises: previous_migration_id
Create Date: 2025-01-15
"""
from alembic import op
from alembic.migration_helpers import create_index_if_not_exists, drop_index_if_exists

revision = 'idx_user_email'
down_revision = 'previous_migration_id'

def upgrade():
    """Create index on user email."""
    create_index_if_not_exists(
        'idx_user_email',
        'users',
        ['email'],
        unique=True
    )

def downgrade():
    """Drop index on user email."""
    drop_index_if_exists('idx_user_email')
```

#### 4. Creating a Partial Index (PostgreSQL)

```python
"""Add partial index for active users

Revision ID: idx_active_users
Revises: previous_migration_id
Create Date: 2025-01-15
"""
from alembic import op
from alembic.migration_helpers import execute_if_not_exists, drop_index_if_exists

revision = 'idx_active_users'
down_revision = 'previous_migration_id'

def upgrade():
    """Create partial index for active users."""
    execute_if_not_exists(
        check_query="SELECT indexname FROM pg_indexes WHERE indexname = 'idx_active_users'",
        execute_statement="""
            CREATE UNIQUE INDEX idx_active_users
            ON users (email)
            WHERE is_active = true;
        """
    )

def downgrade():
    """Drop partial index."""
    drop_index_if_exists('idx_active_users')
```

#### 5. Complex Custom Migration

```python
"""Add custom constraint to orders

Revision ID: constraint_order_total
Revises: previous_migration_id
Create Date: 2025-01-15
"""
from alembic import op
from alembic.migration_helpers import execute_if_not_exists

revision = 'constraint_order_total'
down_revision = 'previous_migration_id'

def upgrade():
    """Add constraint ensuring order total is positive."""
    execute_if_not_exists(
        check_query="SELECT conname FROM pg_constraint WHERE conname = 'order_total_positive'",
        execute_statement="""
            ALTER TABLE orders
            ADD CONSTRAINT order_total_positive CHECK (total > 0)
        """
    )

def downgrade():
    """Remove constraint."""
    op.execute("ALTER TABLE orders DROP CONSTRAINT IF EXISTS order_total_positive")
```

## Common Patterns

### Adding JSONB Column (PostgreSQL)

```python
from sqlalchemy.dialects import postgresql

add_column_if_not_exists('users',
    sa.Column(
        'preferences',
        postgresql.JSONB(astext_type=sa.Text()),
        nullable=False,
        server_default=sa.text("'{}'::jsonb")
    )
)
```

### Adding Foreign Key

```python
# First add the column
add_column_if_not_exists('orders',
    sa.Column('user_id', sa.Integer(), nullable=False)
)

# Then add the foreign key constraint
execute_if_not_exists(
    check_query="SELECT conname FROM pg_constraint WHERE conname = 'fk_orders_user_id'",
    execute_statement="""
        ALTER TABLE orders
        ADD CONSTRAINT fk_orders_user_id
        FOREIGN KEY (user_id) REFERENCES users(id)
        ON DELETE CASCADE
    """
)
```

### Adding Enum Column

```python
# First create the enum type if it doesn't exist
op.execute("""
    DO $$ BEGIN
        CREATE TYPE status_enum AS ENUM ('pending', 'active', 'inactive');
    EXCEPTION
        WHEN duplicate_object THEN null;
    END $$;
""")

# Then add the column
add_column_if_not_exists('users',
    sa.Column('status', sa.Enum('pending', 'active', 'inactive', name='status_enum'),
              nullable=False, server_default='pending')
)
```

## Best Practices

1. **Always use helper functions** - Don't write raw column existence checks
2. **Test migrations both ways** - Run upgrade AND downgrade
3. **Make downgrade idempotent too** - Use `drop_column_if_exists` and `drop_index_if_exists`
4. **Document your migrations** - Add clear docstrings explaining what and why
5. **Keep migrations small** - One logical change per migration file
6. **Name migrations descriptively** - Use clear, specific revision IDs

## Available Helper Functions

| Function | Purpose |
|----------|---------|
| `add_column_if_not_exists()` | Add a single column idempotently |
| `add_columns_if_not_exist()` | Add multiple columns idempotently |
| `drop_column_if_exists()` | Remove a column idempotently |
| `create_index_if_not_exists()` | Create an index idempotently |
| `drop_index_if_exists()` | Remove an index idempotently |
| `column_exists()` | Check if a column exists |
| `index_exists()` | Check if an index exists |
| `execute_if_not_exists()` | Execute custom SQL conditionally |

See `migration_helpers.py` for full documentation and examples.

## Creating a New Migration

```bash
# Generate a new migration file
alembic revision -m "description of changes"

# Edit the generated file in backend/alembic/versions/
# Use the templates above as a guide

# Test the migration
alembic upgrade head
alembic downgrade -1
alembic upgrade head

# Commit the migration file
git add backend/alembic/versions/your_new_migration.py
git commit -m "feat: add database migration for..."
```

## Running Migrations

```bash
# Upgrade to latest
alembic upgrade head

# Downgrade one step
alembic downgrade -1

# Show current revision
alembic current

# Show migration history
alembic history
```
