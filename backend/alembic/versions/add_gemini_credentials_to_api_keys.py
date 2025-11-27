"""Add gemini_credentials column to api_keys

Revision ID: add_gemini_credentials
Revises: add_webhook_fields
Create Date: 2025-11-26

This migration adds the gemini_credentials JSONB column to store
Google OAuth 2.0 credentials for Gemini API access.

Expected JSON structure:
{
    "client_id": "...",
    "client_secret": "...",
    "token": "access_token",
    "refresh_token": "refresh_token",
    "scopes": ["https://www.googleapis.com/auth/cloud-platform", ...],
    "token_uri": "https://oauth2.googleapis.com/token",
    "expiry": "2025-...",
    "project_id": "optional-project-id"
}
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

from migration_helpers import add_column_if_not_exists, drop_column_if_exists


# revision identifiers, used by Alembic.
revision = 'add_gemini_credentials'
down_revision = 'add_webhook_fields'
branch_labels = None
depends_on = None


def upgrade():
    """Add gemini_credentials JSONB column to api_keys table."""
    add_column_if_not_exists(
        'api_keys',
        sa.Column(
            'gemini_credentials',
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            server_default=sa.text("'{}'::jsonb")
        )
    )


def downgrade():
    """Remove gemini_credentials column from api_keys table."""
    drop_column_if_exists('api_keys', 'gemini_credentials')

