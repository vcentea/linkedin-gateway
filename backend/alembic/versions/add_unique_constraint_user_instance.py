"""Add unique constraint for user_id and instance_id

Revision ID: unique_user_instance
Revises: add_csrf_token
Create Date: 2025-01-15

This migration adds a partial unique index to ensure only one active API key
exists per (user_id, instance_id) combination. Legacy keys with NULL instance_id
are excluded from this constraint for backward compatibility.
"""
from alembic import op
import sqlalchemy as sa
import sys
from pathlib import Path

# Add alembic directory to path to import migration_helpers
alembic_dir = Path(__file__).resolve().parent.parent
if str(alembic_dir) not in sys.path:
    sys.path.insert(0, str(alembic_dir))

from migration_helpers import execute_if_not_exists, drop_index_if_exists


# revision identifiers, used by Alembic.
revision = 'unique_user_instance'
down_revision = 'add_csrf_token'
branch_labels = None
depends_on = None


def upgrade():
    """
    Add partial unique index to enforce one active key per (user_id, instance_id).
    Only applies where instance_id IS NOT NULL and is_active = true.
    """
    # Create partial unique index for PostgreSQL
    execute_if_not_exists(
        check_query="SELECT indexname FROM pg_indexes WHERE indexname = 'idx_unique_user_instance_active'",
        execute_statement="""
            CREATE UNIQUE INDEX idx_unique_user_instance_active
            ON api_keys (user_id, instance_id)
            WHERE instance_id IS NOT NULL AND is_active = true;
        """
    )


def downgrade():
    """Remove the unique constraint."""
    drop_index_if_exists('idx_unique_user_instance_active')

