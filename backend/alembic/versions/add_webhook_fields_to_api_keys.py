"""Add webhook configuration columns to api_keys

Revision ID: add_webhook_fields
Revises: unique_user_instance
Create Date: 2025-02-14
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import sys
from pathlib import Path

# Add alembic directory to path to import migration_helpers
alembic_dir = Path(__file__).resolve().parent.parent
if str(alembic_dir) not in sys.path:
    sys.path.insert(0, str(alembic_dir))

from migration_helpers import add_columns_if_not_exist, drop_column_if_exists


# revision identifiers, used by Alembic.
revision = 'add_webhook_fields'
down_revision = 'unique_user_instance'
branch_labels = None
depends_on = None


def upgrade():
    """Add webhook_url and webhook_headers columns to api_keys table."""
    # Add columns only if they don't exist
    add_columns_if_not_exist('api_keys', [
        sa.Column('webhook_url', sa.String(length=1024), nullable=True),
        sa.Column(
            'webhook_headers',
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb")
        )
    ])

    # Normalize existing rows to ensure no NULL values remain
    op.execute("UPDATE api_keys SET webhook_headers = '{}'::jsonb WHERE webhook_headers IS NULL;")


def downgrade():
    """Remove webhook configuration columns."""
    drop_column_if_exists('api_keys', 'webhook_headers')
    drop_column_if_exists('api_keys', 'webhook_url')
