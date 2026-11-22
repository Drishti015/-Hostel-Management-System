import os
import sys
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / '.env')

def init_mysql_db():
    """
    Executes schema.sql and seed.sql directly into MySQL.
    """
    import pymysql

    host = os.environ.get('MYSQL_HOST', 'localhost')
    port = int(os.environ.get('MYSQL_PORT', 3306))
    user = os.environ.get('MYSQL_USER', 'root')
    password = os.environ.get('MYSQL_PASSWORD', '')
    dbname = os.environ.get('MYSQL_DB', 'hostel_db')

    print(f"Connecting to MySQL at {host}:{port} as user '{user}'...")
    try:
        conn = pymysql.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            charset='utf8mb4'
        )
    except Exception as e:
        print(f"Connection failed: {e}")
        print("Please check your .env file credentials.")
        return False

    schema_file = BASE_DIR / 'database' / 'schema.sql'
    seed_file = BASE_DIR / 'database' / 'seed.sql'

    with conn.cursor() as cursor:
        print(f"Creating database '{dbname}' if not exists...")
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{dbname}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;")
        cursor.execute(f"USE `{dbname}`;")

        # Execute schema
        print("Executing schema.sql (12 tables with constraints & indexes)...")
        with open(schema_file, 'r', encoding='utf-8') as f:
            schema_sql = f.read()
        
        # Split by semicolon (ignoring empty statements)
        for statement in schema_sql.split(';'):
            stmt = statement.strip()
            if stmt:
                cursor.execute(stmt)

        print("Executing seed.sql (Populating sample users, hostels, rooms, students, allocations)...")
        with open(seed_file, 'r', encoding='utf-8') as f:
            seed_sql = f.read()

        for statement in seed_sql.split(';'):
            stmt = statement.strip()
            if stmt:
                cursor.execute(stmt)

        conn.commit()

    conn.close()
    print("✓ All tables created and demo data seeded successfully in MySQL!")
    return True

if __name__ == '__main__':
    success = init_mysql_db()
    sys.exit(0 if success else 1)

