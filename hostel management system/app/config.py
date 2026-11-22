import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables
load_dotenv(BASE_DIR / '.env')

class Config:
    """Base Configuration Class"""
    SECRET_KEY = os.environ.get('SECRET_KEY', 'aktu-hms-secret-key-2026-super-secure')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Session & CSRF Security
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    WTF_CSRF_ENABLED = True
    
    # MySQL Database Connection Parameters
    MYSQL_USER = os.environ.get('MYSQL_USER', 'root')
    MYSQL_PASSWORD = os.environ.get('MYSQL_PASSWORD', '')
    MYSQL_HOST = os.environ.get('MYSQL_HOST', 'localhost')
    MYSQL_PORT = os.environ.get('MYSQL_PORT', '3306')
    MYSQL_DB = os.environ.get('MYSQL_DB', 'hostel_db')
    
    DATABASE_URL = os.environ.get('DATABASE_URL')

    @classmethod
    def get_database_uri(cls):
        """
        Dynamically constructs the database URI.
        1. If DATABASE_URL is set in .env, uses that.
        2. If MySQL credentials are provided, attempts MySQL connection.
        3. If MySQL is not reachable or password is empty/denied, falls back to SQLite.
        """
        if cls.DATABASE_URL:
            return cls.DATABASE_URL
        
        # Check if MySQL is accessible
        if cls.MYSQL_PASSWORD:
            user_pass = f"{cls.MYSQL_USER}:{cls.MYSQL_PASSWORD}"
            return f"mysql+pymysql://{user_pass}@{cls.MYSQL_HOST}:{cls.MYSQL_PORT}/{cls.MYSQL_DB}?charset=utf8mb4"
        
        # Test if empty password works on MySQL
        try:
            import pymysql
            conn = pymysql.connect(
                host=cls.MYSQL_HOST,
                port=int(cls.MYSQL_PORT),
                user=cls.MYSQL_USER,
                password='',
                connect_timeout=2
            )
            conn.close()
            return f"mysql+pymysql://{cls.MYSQL_USER}@{cls.MYSQL_HOST}:{cls.MYSQL_PORT}/{cls.MYSQL_DB}?charset=utf8mb4"
        except Exception:
            # Safe Fallback to SQLite so the student can immediately run & test the application
            # without getting blocked by a missing MySQL password.
            instance_dir = BASE_DIR / 'instance'
            instance_dir.mkdir(exist_ok=True)
            sqlite_path = instance_dir / 'hostel.sqlite3'
            return f"sqlite:///{sqlite_path}"

class DevelopmentConfig(Config):
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = Config.get_database_uri()
    
class TestingConfig(Config):
    TESTING = True
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False

class ProductionConfig(Config):
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = Config.get_database_uri()

config_by_name = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
