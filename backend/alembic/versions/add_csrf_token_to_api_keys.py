"""Add csrf_token to api_keys

Revision ID: add_csrf_token
Revises: 
Create Date: 2025-01-11

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_csrf_token'
down_revision = None  # Update this with your latest migration
branch_labels = None
depends_on = None


def upgrade():
    """Add csrf_token column to api_keys table."""
    op.add_column('api_keys', sa.Column('csrf_token', sa.String(length=255), nullable=True))


def downgrade():
    """Remove csrf_token column from api_keys table."""
    op.drop_column('api_keys', 'csrf_token')

