"""Add csrf_token to api_keys

Revision ID: add_csrf_token
Revises:
Create Date: 2025-01-11

"""
from alembic import op
import sqlalchemy as sa
import sys
from pathlib import Path

# Add alembic directory to path to import migration_helpers
alembic_dir = Path(__file__).resolve().parent.parent
if str(alembic_dir) not in sys.path:
    sys.path.insert(0, str(alembic_dir))

from migration_helpers import add_column_if_not_exists, drop_column_if_exists


# revision identifiers, used by Alembic.
revision = 'add_csrf_token'
down_revision = None  # Update this with your latest migration
branch_labels = None
depends_on = None


def upgrade():
    """Add csrf_token column to api_keys table."""
    add_column_if_not_exists(
        'api_keys',
        sa.Column('csrf_token', sa.String(length=255), nullable=True)
    )


def downgrade():
    """Remove csrf_token column from api_keys table."""
    drop_column_if_exists('api_keys', 'csrf_token')

