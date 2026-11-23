import os
import re
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

# Load local environment variables from .env if present
load_dotenv(BASE_DIR / '.env')


def normalize_database_url(url: str) -> str:
    """
    Normalizes database URL for SQLAlchemy compatibility:
    1. Replaces deprecated 'postgres://' with 'postgresql+psycopg2://'.
    2. Replaces plain 'postgresql://' with 'postgresql+psycopg2://' so the installed psycopg2 driver is used.
    3. Strips leading/trailing whitespace.
    """
    if not url:
        return url
    
    url = url.strip()
    
    # SQLAlchemy requires postgresql+psycopg2:// when using psycopg2
    if url.startswith('postgres://'):
        url = url.replace('postgres://', 'postgresql+psycopg2://', 1)
    elif url.startswith('postgresql://'):
        url = url.replace('postgresql://', 'postgresql+psycopg2://', 1)
        
    return url


def mask_database_url(url: str) -> str:
    """
    Safely masks passwords in database connection strings for leak-proof logging.
    Example: postgresql://user:pass@host:5432/db -> postgresql://user:***@host:5432/db
    """
    if not url:
        return "<not-set>"
    return re.sub(r':([^/@]+)@', ':***@', url)


class Config:
    """Base Configuration Class"""
    SECRET_KEY = os.environ.get('SECRET_KEY', 'aktu-hms-secret-key-2026-super-secure')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Session & CSRF Security
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    WTF_CSRF_ENABLED = True
    
    # MySQL Database Connection Parameters (for local development when explicitly configured)
    MYSQL_USER = os.environ.get('MYSQL_USER', 'root')
    MYSQL_PASSWORD = os.environ.get('MYSQL_PASSWORD', '')
    MYSQL_HOST = os.environ.get('MYSQL_HOST', 'localhost')
    MYSQL_PORT = os.environ.get('MYSQL_PORT', '3306')
    MYSQL_DB = os.environ.get('MYSQL_DB', 'hostel_db')
    
    DATABASE_URL = os.environ.get('DATABASE_URL')

    @classmethod
    def get_database_uri(cls, default_to_sqlite=True):
        """
        Dynamically constructs the database URI:
        1. If DATABASE_URL is set (e.g. Supabase PostgreSQL on production), normalize and use it.
        2. If MySQL credentials are provided and non-empty password, use MySQL.
        3. Otherwise, safely fall back to local SQLite (instance/hostel.sqlite3) so local development
           works seamlessly without external database servers.
        """
        raw_db_url = os.environ.get('DATABASE_URL') or cls.DATABASE_URL
        if raw_db_url and raw_db_url.strip():
            return normalize_database_url(raw_db_url)
        
        # Check if local MySQL is explicitly configured with password
        if cls.MYSQL_PASSWORD:
            user_pass = f"{cls.MYSQL_USER}:{cls.MYSQL_PASSWORD}"
            return f"mysql+pymysql://{user_pass}@{cls.MYSQL_HOST}:{cls.MYSQL_PORT}/{cls.MYSQL_DB}?charset=utf8mb4"
        
        # Default to local SQLite database (default for local development)
        instance_dir = BASE_DIR / 'instance'
        instance_dir.mkdir(exist_ok=True)
        sqlite_path = instance_dir / 'hostel.sqlite3'
        return f"sqlite:///{sqlite_path.as_posix()}"


class DevelopmentConfig(Config):
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = Config.get_database_uri(default_to_sqlite=True)
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
    }


class TestingConfig(Config):
    TESTING = True
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False


class ProductionConfig(Config):
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = Config.get_database_uri(default_to_sqlite=False)
    
    # Supabase PostgreSQL & Serverless (Vercel) Connection Pooling Configuration:
    # On serverless platforms (Vercel/AWS Lambda), NullPool or light connection pooling
    # is essential when using Supabase's Transaction Pooler (Supavisor port 6543)
    # to avoid exhausting database connections across ephemeral serverless invocations.
    is_serverless = bool(os.environ.get('VERCEL') or os.environ.get('AWS_LAMBDA_FUNCTION_NAME'))
    if is_serverless:
        from sqlalchemy.pool import NullPool
        SQLALCHEMY_ENGINE_OPTIONS = {
            'poolclass': NullPool,
            'pool_pre_ping': True,
        }
    else:
        SQLALCHEMY_ENGINE_OPTIONS = {
            'pool_pre_ping': True,
            'pool_recycle': 300,
            'pool_size': int(os.environ.get('DB_POOL_SIZE', 5)),
            'max_overflow': int(os.environ.get('DB_MAX_OVERFLOW', 10)),
        }


config_by_name = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
