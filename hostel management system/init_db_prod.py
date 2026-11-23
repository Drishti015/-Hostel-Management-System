"""
HostelEase HMS — Production Database Schema Migration Runner
Safely initializes tables in an empty Supabase PostgreSQL database.

Safety Guarantees:
- Idempotent: Uses SQLAlchemy db.create_all() (CREATE TABLE IF NOT EXISTS).
- Non-destructive: Never drops, truncates, or modifies existing tables or columns.
- Clean: Does NOT insert demo users, sample students, or local data.
- Leak-proof: Database credentials and passwords are never logged or printed.
"""

import os
import sys
from pathlib import Path

# Add project root to path
PROJECT_DIR = Path(__file__).resolve().parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from app import create_app, db
from app.config import mask_database_url
from sqlalchemy import inspect


def run_production_migration():
    print("=" * 70)
    print("HOSTELEASE HMS — PRODUCTION DATABASE MIGRATION RUNNER")
    print("=" * 70)

    db_url = os.environ.get("DATABASE_URL")
    if not db_url or not db_url.strip():
        print("ERROR: DATABASE_URL environment variable is not set.")
        print("Please set DATABASE_URL to your Supabase PostgreSQL connection string.")
        print("Example (Transaction Pooler):")
        print("  $env:DATABASE_URL=\"postgresql://postgres.[REF]:[PASS]@aws-0-[REGION].pooler.supabase.com:6543/postgres?sslmode=require\"")
        print("  python init_db_prod.py")
        sys.exit(1)

    masked_url = mask_database_url(db_url)
    print(f"Target Database URI: {masked_url}")

    # Instantiate production Flask app context
    app = create_app("production")

    with app.app_context():
        engine = db.engine
        dialect_name = engine.dialect.name
        print(f"Target Dialect     : {dialect_name.upper()}")

        if dialect_name != "postgresql" and "sqlite" in str(engine.url):
            print("\nWARNING: Target database appears to be local SQLite.")
            print("To migrate production Supabase, provide the PostgreSQL DATABASE_URL.")
            confirm = input("Continue anyway against this database? (yes/no): ").strip().lower()
            if confirm != "yes":
                print("Migration aborted.")
                sys.exit(0)

        inspector = inspect(engine)
        existing_tables_before = set(inspector.get_table_names())
        print(f"Existing tables before migration: {len(existing_tables_before)}")

        print("\nExecuting schema creation (db.create_all())...")
        # db.create_all() creates custom enums and tables that do not yet exist
        db.create_all()

        # Re-inspect to see new tables created
        inspector_after = inspect(engine)
        existing_tables_after = set(inspector_after.get_table_names())
        new_tables = existing_tables_after - existing_tables_before

        print("-" * 70)
        print(f"Total tables present in database : {len(existing_tables_after)} / 30")
        if new_tables:
            print(f"New tables created ({len(new_tables)}):")
            for t in sorted(new_tables):
                print(f"  + {t}")
        else:
            print("All tables already exist. No schema changes were required.")

        print("-" * 70)
        print("SUCCESS: Production schema migration completed safely and idempotently!")
        print("=" * 70)


if __name__ == "__main__":
    run_production_migration()
