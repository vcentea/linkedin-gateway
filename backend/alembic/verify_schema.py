#!/usr/bin/env python3
"""
Schema Verification Script

This script verifies that the database schema matches expectations,
regardless of what Alembic thinks the migration state is.

It can detect and fix cases where:
- Alembic says a migration ran, but columns are missing
- Partial migration failures
- Schema drift

Usage:
    python verify_schema.py [--fix]

Options:
    --fix    Automatically fix any schema issues found
"""

import sys
import asyncio
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from app.db.session import async_engine


# Define expected schema for each table
# Format: {table_name: {column_name: (column_type, nullable, default)}}
EXPECTED_SCHEMA = {
    'api_keys': {
        # Core columns
        'id': ('uuid', False, None),
        'user_id': ('uuid', False, None),
        'prefix': ('character varying', False, None),
        'key_hash': ('character varying', False, None),
        'name': ('character varying', True, None),
        'description': ('text', True, None),
        'csrf_token': ('character varying', True, None),
        'linkedin_cookies': ('jsonb', True, None),
        'last_used_at': ('timestamp without time zone', True, None),
        'is_active': ('boolean', False, 'true'),
        'rate_limit_config': ('jsonb', True, None),
        'permissions': ('jsonb', True, None),
        'api_metadata': ('jsonb', True, None),
        'instance_id': ('character varying', True, None),
        'instance_name': ('character varying', True, None),
        'browser_info': ('jsonb', True, None),
        'created_at': ('timestamp without time zone', False, None),
        'updated_at': ('timestamp without time zone', False, None),

        # Webhook columns (added in add_webhook_fields migration)
        'webhook_url': ('character varying', True, None),
        'webhook_headers': ('jsonb', False, "'{}'::jsonb"),
    }
}


async def get_table_schema(table_name: str) -> dict:
    """
    Get current schema for a table from the database.

    Returns:
        dict: {column_name: (data_type, is_nullable, column_default)}
    """
    async with async_engine.connect() as conn:
        result = await conn.execute(text("""
            SELECT
                column_name,
                data_type,
                is_nullable = 'YES' as is_nullable,
                column_default
            FROM information_schema.columns
            WHERE table_name = :table_name
            ORDER BY ordinal_position
        """), {"table_name": table_name})

        schema = {}
        for row in result:
            schema[row.column_name] = (
                row.data_type,
                row.is_nullable,
                row.column_default
            )
        return schema


async def verify_table(table_name: str, expected_columns: dict, fix: bool = False) -> tuple[bool, list]:
    """
    Verify a table's schema matches expectations.

    Args:
        table_name: Name of the table to check
        expected_columns: Expected column definitions
        fix: If True, automatically fix missing columns

    Returns:
        tuple: (is_valid, list_of_issues)
    """
    print(f"\n🔍 Checking table: {table_name}")

    current_schema = await get_table_schema(table_name)
    issues = []

    # Check for missing columns
    for col_name, (expected_type, expected_nullable, expected_default) in expected_columns.items():
        if col_name not in current_schema:
            issue = f"❌ Missing column: {col_name} ({expected_type})"
            print(f"  {issue}")
            issues.append({
                'type': 'missing_column',
                'table': table_name,
                'column': col_name,
                'expected_type': expected_type,
                'expected_nullable': expected_nullable,
                'expected_default': expected_default,
                'message': issue
            })
        else:
            print(f"  ✓ Column exists: {col_name}")

    # Check for extra columns (informational only)
    extra_columns = set(current_schema.keys()) - set(expected_columns.keys())
    if extra_columns:
        print(f"  ℹ️  Extra columns (not in spec): {', '.join(extra_columns)}")

    if fix and issues:
        print(f"\n🔧 Fixing issues for table: {table_name}")
        await fix_issues(issues)

    is_valid = len([i for i in issues if i['type'] == 'missing_column']) == 0
    return is_valid, issues


async def fix_issues(issues: list):
    """
    Automatically fix schema issues.

    Args:
        issues: List of issue dictionaries from verify_table
    """
    async with async_engine.begin() as conn:
        for issue in issues:
            if issue['type'] == 'missing_column':
                table = issue['table']
                column = issue['column']
                col_type = issue['expected_type']
                nullable = issue['expected_nullable']
                default = issue['expected_default']

                # Map generic types to PostgreSQL types
                type_mapping = {
                    'character varying': 'VARCHAR',
                    'text': 'TEXT',
                    'uuid': 'UUID',
                    'boolean': 'BOOLEAN',
                    'jsonb': 'JSONB',
                    'timestamp without time zone': 'TIMESTAMP',
                }

                pg_type = type_mapping.get(col_type, col_type.upper())

                # Handle special cases
                if column == 'webhook_url':
                    pg_type = 'VARCHAR(1024)'

                # Build ALTER TABLE statement
                null_clause = '' if nullable else 'NOT NULL'
                default_clause = f'DEFAULT {default}' if default else ''

                sql = f"""
                    ALTER TABLE {table}
                    ADD COLUMN IF NOT EXISTS {column} {pg_type} {null_clause} {default_clause}
                """.strip()

                print(f"  Executing: {sql}")
                await conn.execute(text(sql))

                # Special handling for webhook_headers - update existing NULL values
                if column == 'webhook_headers':
                    update_sql = f"UPDATE {table} SET {column} = '{{}}'::jsonb WHERE {column} IS NULL"
                    print(f"  Executing: {update_sql}")
                    await conn.execute(text(update_sql))

                print(f"  ✅ Fixed: {column}")


async def verify_schema(fix: bool = False) -> bool:
    """
    Verify the entire database schema.

    Args:
        fix: If True, automatically fix any issues found

    Returns:
        bool: True if schema is valid (or was fixed), False otherwise
    """
    print("=" * 60)
    print("🔍 LinkedIn Gateway - Database Schema Verification")
    print("=" * 60)

    all_valid = True
    all_issues = []

    for table_name, expected_columns in EXPECTED_SCHEMA.items():
        is_valid, issues = await verify_table(table_name, expected_columns, fix)
        if not is_valid:
            all_valid = False
        all_issues.extend(issues)

    print("\n" + "=" * 60)
    if all_valid:
        print("✅ Schema verification PASSED - All tables are correct!")
    else:
        print(f"❌ Schema verification FAILED - Found {len(all_issues)} issue(s)")
        if not fix:
            print("\n💡 Run with --fix to automatically fix these issues:")
            print("   python verify_schema.py --fix")
    print("=" * 60)

    return all_valid


async def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description='Verify database schema')
    parser.add_argument('--fix', action='store_true', help='Automatically fix schema issues')
    args = parser.parse_args()

    try:
        is_valid = await verify_schema(fix=args.fix)
        sys.exit(0 if is_valid else 1)
    except Exception as e:
        print(f"\n❌ Error during verification: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(2)
    finally:
        await async_engine.dispose()


if __name__ == '__main__':
    asyncio.run(main())
