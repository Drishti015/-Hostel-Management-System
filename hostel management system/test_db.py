import os
import sys
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / '.env')

def test_mysql_connection():
    """
    Tests MySQL connection using PyMySQL and environment configuration.
    """
    import pymysql

    host = os.environ.get('MYSQL_HOST', 'localhost')
    port = int(os.environ.get('MYSQL_PORT', 3306))
    user = os.environ.get('MYSQL_USER', 'root')
    password = os.environ.get('MYSQL_PASSWORD', '')
    dbname = os.environ.get('MYSQL_DB', 'hostel_db')

    print("=" * 65)
    print("HOSTEL MANAGEMENT SYSTEM - DATABASE CONNECTIVITY VERIFIER")
    print("=" * 65)
    print(f"Target Host    : {host}:{port}")
    print(f"Target User    : {user}")
    print(f"Target Database: {dbname}")
    print("-" * 65)

    # 1. Connect to MySQL Server (without selecting database first)
    try:
        conn = pymysql.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor
        )
        print("✓ SUCCESS: Connected to MySQL Server successfully!")
        
        with conn.cursor() as cursor:
            cursor.execute("SELECT VERSION() AS ver;")
            res = cursor.fetchone()
            print(f"✓ MySQL Engine Version: {res['ver']}")

            # Check if database exists
            cursor.execute("SHOW DATABASES LIKE %s;", (dbname,))
            db_exists = cursor.fetchone()
            
            if db_exists:
                print(f"✓ Database '{dbname}' already exists.")
            else:
                print(f"! Database '{dbname}' not found. Creating it now...")
                cursor.execute(f"CREATE DATABASE `{dbname}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;")
                print(f"✓ Database '{dbname}' created successfully.")

        conn.close()

        # 2. Connect to the specific database
        conn_db = pymysql.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database=dbname,
            charset='utf8mb4'
        )
        with conn_db.cursor() as cursor:
            cursor.execute("SHOW TABLES;")
            tables = cursor.fetchall()
            print(f"✓ Found {len(tables)} tables currently in '{dbname}'.")
        conn_db.close()
        
        print("-" * 65)
        print("STATUS: Flask-MySQL connectivity is 100% operational!")
        print("=" * 65)
        return True

    except pymysql.err.OperationalError as e:
        code, msg = e.args
        print(f"✗ ERROR [{code}]: {msg}")
        print("-" * 65)
        if code == 1045:
            print("DIAGNOSIS: Access denied. The MySQL password for user 'root' is required.")
            print("FIX: Open your '.env' file and update MYSQL_PASSWORD=<your_mysql_password>")
        elif code == 2003:
            print("DIAGNOSIS: Can't connect to MySQL server on 'localhost:3306'.")
            print("FIX: Ensure the MySQL service (MySQL80) is started in Windows Services.")
        else:
            print(f"DIAGNOSIS: {msg}")
        print("=" * 65)
        return False

if __name__ == '__main__':
    success = test_mysql_connection()
    sys.exit(0 if success else 1)

