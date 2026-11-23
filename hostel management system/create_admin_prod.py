"""
HostelEase HMS — Production Administrator Bootstrap Utility
Safely provisions the primary production administrator account.

Safety Guarantees:
- Never uses default demo credentials.
- Uses getpass for hidden, secure password input.
- Enforces minimum 8-character password complexity.
- Validates unique username and email constraints before inserting.
- Masks database connection strings in console output.
"""

import os
import sys
import getpass
from pathlib import Path

# Add project root to path
PROJECT_DIR = Path(__file__).resolve().parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from app import create_app, db
from app.models import User
from app.config import mask_database_url


def create_production_admin():
    print("=" * 70)
    print("HOSTELEASE HMS — SECURE PRODUCTION ADMINISTRATOR BOOTSTRAP")
    print("=" * 70)

    db_url = os.environ.get("DATABASE_URL")
    if not db_url or not db_url.strip():
        print("ERROR: DATABASE_URL environment variable is not set.")
        print("To safely create an administrator in production Supabase, DATABASE_URL must be specified.")
        print("This prevents accidentally modifying the local SQLite development database.")
        print("Example (PowerShell):")
        print('  $env:DATABASE_URL="postgresql://postgres.[REF]:[PASS]@aws-0-[REGION].pooler.supabase.com:6543/postgres?sslmode=require"')
        print("  python create_admin_prod.py")
        sys.exit(1)

    print(f"Target Database : {mask_database_url(db_url)}")

    app = create_app(os.environ.get("FLASK_ENV", "production"))

    with app.app_context():
        # Check if environment variables are provided (for automated CI/CD)
        username = os.environ.get("ADMIN_USERNAME")
        email = os.environ.get("ADMIN_EMAIL")
        password = os.environ.get("ADMIN_PASSWORD")

        # Interactive prompts if not provided via environment
        if not username:
            default_user = "admin"
            entered_user = input(f"Enter administrator username [{default_user}]: ").strip()
            username = entered_user if entered_user else default_user

        if not email:
            email = input("Enter administrator email address: ").strip()

        while not email or "@" not in email:
            print("ERROR: Please enter a valid email address.")
            email = input("Enter administrator email address: ").strip()

        # Check for existing user with same username or email
        existing_by_user = User.query.filter_by(username=username).first()
        if existing_by_user:
            print(f"\nERROR: A user with username '{username}' already exists in this database.")
            print("Aborting to prevent overwriting existing accounts.")
            sys.exit(1)

        existing_by_email = User.query.filter_by(email=email).first()
        if existing_by_email:
            print(f"\nERROR: A user with email '{email}' already exists in this database.")
            print("Aborting to prevent duplicate email conflicts.")
            sys.exit(1)

        # Secure password entry
        if not password:
            while True:
                p1 = getpass.getpass("Enter secure administrator password (min 8 characters): ")
                if len(p1) < 8:
                    print("ERROR: Password must be at least 8 characters long.")
                    continue
                p2 = getpass.getpass("Confirm administrator password: ")
                if p1 != p2:
                    print("ERROR: Passwords do not match. Please try again.")
                    continue
                password = p1
                break

        # Create production admin user record
        admin_user = User(
            username=username,
            email=email,
            role="admin",
            is_active=True
        )
        admin_user.set_password(password)

        db.session.add(admin_user)
        db.session.commit()

        print("-" * 70)
        print("SUCCESS: Production administrator account created successfully!")
        print(f"Username : {username}")
        print(f"Email    : {email}")
        print(f"Role     : admin")
        print("=" * 70)


if __name__ == "__main__":
    create_production_admin()
