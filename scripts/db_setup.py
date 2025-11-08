#!/usr/bin/env python
"""
db_setup.py

Script to create PostgreSQL database, user, and tables for the LinkedinGateway project.
It reads database credentials from a .env file located at the project root.

Required .env variables:
  DB_HOST
  DB_PORT
  DB_SUPERUSER
  DB_SUPERUSER_PASSWORD
  DB_USER
  DB_PASSWORD
  DB_NAME

Usage:
  python scripts/db_setup.py
"""
import os
import sys
from pathlib import Path
import time

from dotenv import load_dotenv
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from sqlalchemy import create_engine, text

# Load environment variables from .env at project root
dotenv_path = Path(__file__).resolve().parent.parent / '.env'
print(f"Loading .env from: {dotenv_path}")
print(f"File exists: {dotenv_path.exists()}")
load_dotenv(dotenv_path)

# Database configuration from env
DB_HOST = '127.0.0.1'  # Use IP instead of localhost
DB_PORT = os.getenv('DB_PORT', '5432')
SUPERUSER = os.getenv('DB_SUPERUSER', 'postgres')
SUPERUSER_PASSWORD = os.getenv('DB_SUPERUSER_PASSWORD')
DB_USER = os.getenv('DB_USER')
DB_PASSWORD = os.getenv('DB_PASSWORD')
DB_NAME = os.getenv('DB_NAME', 'LinkedinGateway')  # Use exact case

print("\nLoaded environment variables:")
print(f"DB_HOST: {DB_HOST}")
print(f"DB_PORT: {DB_PORT}")
print(f"SUPERUSER: {SUPERUSER}")
print(f"SUPERUSER_PASSWORD: {'*' * len(SUPERUSER_PASSWORD) if SUPERUSER_PASSWORD else 'None'}")
print(f"DB_USER: {DB_USER}")
print(f"DB_PASSWORD: {'*' * len(DB_PASSWORD) if DB_PASSWORD else 'None'}")
print(f"DB_NAME: {DB_NAME}")

if not all([SUPERUSER_PASSWORD, DB_USER, DB_PASSWORD]):
    print("ERROR: Missing one of DB_SUPERUSER_PASSWORD, DB_USER, or DB_PASSWORD in .env")
    sys.exit(1)

def grant_privileges(cur, db_name, db_user):
    """Grant all necessary privileges to the database user."""
    print("\nGranting privileges...")
    
    # List of privilege commands
    privilege_commands = [
        f'GRANT ALL PRIVILEGES ON DATABASE "{db_name}" TO {db_user}',
        f"GRANT ALL ON SCHEMA public TO {db_user}",
        f"GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO {db_user}",
        f"GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO {db_user}",
        f"GRANT ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA public TO {db_user}",
        f"GRANT CREATE ON SCHEMA public TO {db_user}",
        f"ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL PRIVILEGES ON TABLES TO {db_user}",
        f"ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL PRIVILEGES ON SEQUENCES TO {db_user}",
        f"ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL PRIVILEGES ON FUNCTIONS TO {db_user}"
    ]
    
    for command in privilege_commands:
        try:
            cur.execute(command)
            print(f"Executed: {command}")
        except psycopg2.Error as e:
            print(f"Warning while executing '{command}': {e}")
            # Continue with other commands even if one fails

def setup_database():
    """Set up the database, user, and grant privileges."""
    print("\nAttempting to connect to PostgreSQL...")
    try:
        # Connect to default 'postgres' database as superuser
        conn = psycopg2.connect(
            dbname='postgres',
            user=SUPERUSER,
            password=SUPERUSER_PASSWORD,
            host=DB_HOST,
            port=DB_PORT
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cur = conn.cursor()

        # Create DB user if not exists
        try:
            cur.execute(f"CREATE USER {DB_USER} WITH PASSWORD %s;", (DB_PASSWORD,))
            print(f"User '{DB_USER}' created.")
        except psycopg2.errors.DuplicateObject:
            print(f"User '{DB_USER}' already exists.")
            conn.rollback()

        # Drop database if exists
        cur.execute("""
            SELECT pg_terminate_backend(pg_stat_activity.pid)
            FROM pg_stat_activity
            WHERE pg_stat_activity.datname = %s
            AND pid <> pg_backend_pid();
        """, (DB_NAME,))
        
        try:
            cur.execute(f'DROP DATABASE IF EXISTS "{DB_NAME}";')
            print(f"Dropped existing database '{DB_NAME}'.")
        except psycopg2.Error as e:
            print(f"Warning while dropping database: {e}")
            conn.rollback()

        # Create database
        try:
            cur.execute(f'CREATE DATABASE "{DB_NAME}" WITH OWNER = {DB_USER};')
            print(f"Database '{DB_NAME}' created.")
        except psycopg2.Error as e:
            print(f"Error creating database: {e}")
            return False

        # Grant initial privileges
        try:
            cur.execute(f'GRANT ALL PRIVILEGES ON DATABASE "{DB_NAME}" TO {DB_USER};')
            print(f"Granted initial privileges on '{DB_NAME}' to '{DB_USER}'")
        except psycopg2.Error as e:
            print(f"Warning while granting initial privileges: {e}")

        cur.close()
        conn.close()

        # Wait a moment for the database to be ready
        time.sleep(2)

        # Connect to the new database as superuser to grant remaining privileges
        conn = psycopg2.connect(
            dbname=DB_NAME,
            user=SUPERUSER,
            password=SUPERUSER_PASSWORD,
            host=DB_HOST,
            port=DB_PORT
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cur = conn.cursor()

        # Grant all necessary privileges
        grant_privileges(cur, DB_NAME, DB_USER)

        cur.close()
        conn.close()
        return True

    except psycopg2.Error as e:
        print(f"Error in database setup: {e}")
        return False

def create_tables():
    """Create all database tables."""
    print("\nCreating tables...")
    try:
        # Build SQLAlchemy database URL - use superuser for table creation
        db_url = f"postgresql://{SUPERUSER}:{SUPERUSER_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
        print(f"Connecting to database with URL: postgresql://{SUPERUSER}:***@{DB_HOST}:{DB_PORT}/{DB_NAME}")
        
        engine = create_engine(db_url)

        # Ensure our app path is in sys.path for imports
        project_root = Path(__file__).resolve().parent.parent
        backend_path = str(project_root / 'backend' / 'app')
        print(f"Adding {backend_path} to Python path")
        sys.path.append(backend_path)

        # Import Base and models to register them with metadata
        try:
            print("Importing models...")
            from db.base import Base
            # Import each models module to register
            import db.models.user
            import db.models.api_key
            import db.models.billing
            import db.models.profile
            import db.models.post
            import db.models.message
            print("Models imported successfully!")

            # Create all tables
            print("Creating database tables...")
            Base.metadata.create_all(bind=engine)
            print("Tables created successfully!")
            return True

        except ImportError as e:
            print(f"ERROR importing models: {e}")
            return False

    except Exception as e:
        print(f"Error creating tables: {e}")
        return False

if __name__ == '__main__':
    print("=== Setting up database and user ===")
    if setup_database():
        print("\n=== Creating tables ===")
        if create_tables():
            print("\nDatabase setup completed successfully!")
        else:
            print("\nFailed to create tables. Please check the error messages above.")
    else:
        print("\nFailed to setup database. Please check your PostgreSQL connection and credentials.") 