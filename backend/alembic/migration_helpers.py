"""
Helper utilities for creating idempotent Alembic migrations.

These helpers ensure migrations can be run multiple times safely,
whether columns/indexes already exist or not.

Usage Examples
--------------

1. Add a single column idempotently:

    from alembic import op
    import sqlalchemy as sa
    from alembic.migration_helpers import add_column_if_not_exists

    def upgrade():
        add_column_if_not_exists(
            'table_name',
            sa.Column('column_name', sa.String(length=255), nullable=True)
        )

2. Add multiple columns at once:

    from alembic import op
    import sqlalchemy as sa
    from alembic.migration_helpers import add_columns_if_not_exist

    def upgrade():
        add_columns_if_not_exist('api_keys', [
            sa.Column('webhook_url', sa.String(length=1024), nullable=True),
            sa.Column('webhook_headers', postgresql.JSONB(), nullable=False,
                     server_default=sa.text("'{}'::jsonb"))
        ])

3. Create an index idempotently:

    from alembic.migration_helpers import create_index_if_not_exists

    def upgrade():
        create_index_if_not_exists(
            'idx_name',
            'table_name',
            ['column1', 'column2'],
            unique=True,
            postgresql_where='column1 IS NOT NULL'
        )

4. Execute raw SQL idempotently:

    from alembic.migration_helpers import execute_if_not_exists

    def upgrade():
        # For custom index creation
        execute_if_not_exists(
            check_query="SELECT indexname FROM pg_indexes WHERE indexname='idx_name'",
            execute_statement=\"\"\"
                CREATE UNIQUE INDEX idx_name
                ON table_name (col1, col2)
                WHERE condition = true;
            \"\"\"
        )
"""

from alembic import op
import sqlalchemy as sa
from typing import List, Optional


def column_exists(table_name: str, column_name: str) -> bool:
    """
    Check if a column exists in a table.

    Args:
        table_name: Name of the table to check
        column_name: Name of the column to check

    Returns:
        True if column exists, False otherwise
    """
    conn = op.get_bind()
    result = conn.execute(sa.text("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = :table_name
        AND column_name = :column_name
    """), {"table_name": table_name, "column_name": column_name})

    return result.fetchone() is not None


def add_column_if_not_exists(table_name: str, column: sa.Column, schema: Optional[str] = None) -> bool:
    """
    Add a column to a table only if it doesn't already exist.

    Args:
        table_name: Name of the table
        column: SQLAlchemy Column object to add
        schema: Optional schema name

    Returns:
        True if column was added, False if it already existed

    Example:
        add_column_if_not_exists(
            'users',
            sa.Column('email', sa.String(255), nullable=False)
        )
    """
    if not column_exists(table_name, column.name):
        op.add_column(table_name, column, schema=schema)
        return True
    return False


def add_columns_if_not_exist(table_name: str, columns: List[sa.Column], schema: Optional[str] = None) -> int:
    """
    Add multiple columns to a table, skipping any that already exist.

    Args:
        table_name: Name of the table
        columns: List of SQLAlchemy Column objects to add
        schema: Optional schema name

    Returns:
        Number of columns that were added

    Example:
        add_columns_if_not_exist('api_keys', [
            sa.Column('webhook_url', sa.String(1024), nullable=True),
            sa.Column('webhook_headers', postgresql.JSONB(), nullable=False)
        ])
    """
    added_count = 0
    for column in columns:
        if add_column_if_not_exists(table_name, column, schema):
            added_count += 1
    return added_count


def index_exists(index_name: str) -> bool:
    """
    Check if an index exists in the database.

    Args:
        index_name: Name of the index to check

    Returns:
        True if index exists, False otherwise
    """
    conn = op.get_bind()
    # Works for PostgreSQL
    result = conn.execute(sa.text("""
        SELECT indexname
        FROM pg_indexes
        WHERE indexname = :index_name
    """), {"index_name": index_name})

    return result.fetchone() is not None


def create_index_if_not_exists(
    index_name: str,
    table_name: str,
    columns: List[str],
    unique: bool = False,
    postgresql_where: Optional[str] = None
) -> bool:
    """
    Create an index only if it doesn't already exist.

    Args:
        index_name: Name of the index
        table_name: Name of the table
        columns: List of column names
        unique: Whether the index should be unique
        postgresql_where: Optional WHERE clause for partial index (PostgreSQL)

    Returns:
        True if index was created, False if it already existed

    Example:
        create_index_if_not_exists(
            'idx_user_email',
            'users',
            ['email'],
            unique=True
        )
    """
    if not index_exists(index_name):
        op.create_index(
            index_name,
            table_name,
            columns,
            unique=unique,
            postgresql_where=postgresql_where
        )
        return True
    return False


def execute_if_not_exists(check_query: str, execute_statement: str, params: Optional[dict] = None) -> bool:
    """
    Execute a SQL statement only if a check query returns no results.
    Useful for custom DDL operations that need to be idempotent.

    Args:
        check_query: SQL query that returns rows if the object exists
        execute_statement: SQL statement to execute if check returns no rows
        params: Optional parameters for the check query

    Returns:
        True if statement was executed, False if check found existing object

    Example:
        # Create a custom constraint
        execute_if_not_exists(
            check_query="SELECT conname FROM pg_constraint WHERE conname='my_constraint'",
            execute_statement=\"\"\"
                ALTER TABLE my_table
                ADD CONSTRAINT my_constraint CHECK (value > 0)
            \"\"\"
        )
    """
    conn = op.get_bind()
    result = conn.execute(sa.text(check_query), params or {})

    if result.fetchone() is None:
        op.execute(execute_statement)
        return True
    return False


def drop_column_if_exists(table_name: str, column_name: str, schema: Optional[str] = None) -> bool:
    """
    Drop a column from a table only if it exists.
    Useful for downgrade() functions.

    Args:
        table_name: Name of the table
        column_name: Name of the column to drop
        schema: Optional schema name

    Returns:
        True if column was dropped, False if it didn't exist

    Example:
        def downgrade():
            drop_column_if_exists('users', 'email')
    """
    if column_exists(table_name, column_name):
        op.drop_column(table_name, column_name, schema=schema)
        return True
    return False


def drop_index_if_exists(index_name: str) -> bool:
    """
    Drop an index only if it exists.
    Useful for downgrade() functions.

    Args:
        index_name: Name of the index to drop

    Returns:
        True if index was dropped, False if it didn't exist

    Example:
        def downgrade():
            drop_index_if_exists('idx_user_email')
    """
    if index_exists(index_name):
        op.drop_index(index_name)
        return True
    return False
