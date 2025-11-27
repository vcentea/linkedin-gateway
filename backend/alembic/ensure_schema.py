#!/usr/bin/env python3
"""
Simple Schema Enforcement Script

Just checks if required columns exist and adds them if they don't.
No migration tracking, no complex logic - just make sure the schema is correct.

Usage:
    python ensure_schema.py
"""

import sys
import asyncio
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from app.db.session import engine


async def ensure_column(table: str, column: str, column_def: str):
    """
    Ensure a column exists in a table. Add it if it doesn't.

    Args:
        table: Table name
        column: Column name
        column_def: Full column definition (e.g., "VARCHAR(1024)", "JSONB NOT NULL DEFAULT '{}'::jsonb")
    """
    try:
        async with engine.begin() as conn:
            # Check if column exists
            result = await conn.execute(text("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = :table_name
                AND column_name = :column_name
            """), {"table_name": table, "column_name": column})

            exists = result.fetchone() is not None

            if exists:
                print(f"  [OK] {table}.{column} exists")
                return False
            else:
                print(f"  [!] {table}.{column} missing - adding now...")

                # Add the column
                sql = f"ALTER TABLE {table} ADD COLUMN {column} {column_def}"
                print(f"  SQL: {sql}")
                await conn.execute(text(sql))

                print(f"  [OK] {table}.{column} added successfully")
                return True
    except Exception as e:
        print(f"  [ERROR] Error ensuring column {table}.{column}: {e}")
        raise


async def ensure_index(index_name: str, table: str, index_def: str):
    """
    Ensure an index exists. Create it if it doesn't.

    Args:
        index_name: Name of the index
        table: Table name
        index_def: Index definition (e.g., "ON users (email)")
    """
    try:
        async with engine.begin() as conn:
            # Check if index exists
            result = await conn.execute(text("""
                SELECT indexname
                FROM pg_indexes
                WHERE indexname = :index_name
            """), {"index_name": index_name})

            exists = result.fetchone() is not None

            if exists:
                print(f"  [OK] Index {index_name} exists")
                return False
            else:
                print(f"  [!] Index {index_name} missing - creating now...")

                # Create the index
                sql = f"CREATE INDEX IF NOT EXISTS {index_name} {index_def}"
                print(f"  SQL: {sql}")
                await conn.execute(text(sql))

                print(f"  [OK] Index {index_name} created successfully")
                return True
    except Exception as e:
        print(f"  [ERROR] Error ensuring index {index_name}: {e}")
        raise


async def ensure_schema():
    """
    Ensure all required schema elements exist.
    Simple and direct - just add what's missing.
    """
    print("=" * 60)
    print("Ensuring Database Schema")
    print("=" * 60)
    print()

    fixed_count = 0

    # API Keys table columns
    print("Checking api_keys table...")

    # Multi-key support columns (instance tracking)
    if await ensure_column(
        "api_keys",
        "instance_id",
        "VARCHAR(255)"
    ):
        fixed_count += 1

    if await ensure_column(
        "api_keys",
        "instance_name",
        "VARCHAR(255)"
    ):
        fixed_count += 1

    if await ensure_column(
        "api_keys",
        "browser_info",
        "JSONB DEFAULT '{}'::jsonb"
    ):
        fixed_count += 1

    # Webhook columns
    if await ensure_column(
        "api_keys",
        "webhook_url",
        "VARCHAR(1024)"
    ):
        fixed_count += 1

    if await ensure_column(
        "api_keys",
        "webhook_headers",
        "JSONB NOT NULL DEFAULT '{}'::jsonb"
    ):
        fixed_count += 1

        # Update any NULL values to empty JSONB
        async with engine.begin() as conn:
            await conn.execute(text(
                "UPDATE api_keys SET webhook_headers = '{}'::jsonb WHERE webhook_headers IS NULL"
            ))

    # Gemini AI credentials column (v1.2.0)
    if await ensure_column(
        "api_keys",
        "gemini_credentials",
        "JSONB DEFAULT '{}'::jsonb"
    ):
        fixed_count += 1

    # Ensure indexes exist
    print("Checking indexes...")

    # Index on instance_id for multi-key lookups
    if await ensure_index(
        "ix_api_keys_instance_id",
        "api_keys",
        "ON api_keys (instance_id)"
    ):
        fixed_count += 1

    # Unique constraint for (user_id, instance_id) where instance_id is not null
    if await ensure_index(
        "idx_unique_user_instance_active",
        "api_keys",
        "ON api_keys (user_id, instance_id) WHERE instance_id IS NOT NULL AND is_active = true"
    ):
        fixed_count += 1

    print()
    print("=" * 60)
    if fixed_count == 0:
        print("[SUCCESS] Schema is correct - no changes needed")
    else:
        print(f"[SUCCESS] Schema fixed - {fixed_count} item(s) added")
    print("=" * 60)

    return fixed_count


async def main():
    """Main entry point."""
    try:
        print("Starting schema enforcement...")
        print(f"Python version: {sys.version}")
        print(f"Script path: {Path(__file__).resolve()}")
        print()

        fixed_count = await ensure_schema()

        print()
        print("Schema enforcement completed successfully")
        sys.exit(0)
    except Exception as e:
        print(f"\n[ERROR] Error during schema enforcement: {e}")
        print(f"Error type: {type(e).__name__}")
        import traceback
        print("\nFull traceback:")
        traceback.print_exc()
        sys.exit(1)
    finally:
        try:
            await engine.dispose()
        except Exception as e:
            print(f"Warning: Error disposing engine: {e}")


if __name__ == '__main__':
    asyncio.run(main())
