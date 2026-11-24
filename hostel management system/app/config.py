import os
import re
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy.engine.url import make_url, URL
from sqlalchemy.pool import NullPool
from urllib.parse import unquote_plus

BASE_DIR = Path(__file__).resolve().parent.parent

# Load local environment variables from .env if present
load_dotenv(BASE_DIR / '.env')


def normalize_database_url(url: str) -> str:
    """
    Normalizes database URL for SQLAlchemy compatibility using SQLAlchemy URL parsing:
    1. Replaces deprecated 'postgres://' with 'postgresql+psycopg2://'.
    2. Replaces plain 'postgresql://' with 'postgresql+psycopg2://' so the installed psycopg2 driver is used.
    3. Preserves valid usernames, passwords, encoded special characters, hostnames, ports,
       database names, and query parameters.
    4. Strips leading/trailing whitespace.
    """
    if not url or not isinstance(url, str):
        return url

    clean_url = url.strip()
    if not clean_url:
        return clean_url

    # Normalize PostgreSQL schemes to use psycopg2 driver via SQLAlchemy make_url
    if clean_url.startswith('postgres://') or clean_url.startswith('postgresql://'):
        try:
            parsed = make_url(clean_url)
            # Update drivername to postgresql+psycopg2 while preserving all components
            return parsed.set(drivername='postgresql+psycopg2').render_as_string(hide_password=False)
        except Exception:
            # Fall back to safe string prefix replacement if make_url cannot parse it directly
            if clean_url.startswith('postgres://'):
                return 'postgresql+psycopg2://' + clean_url[len('postgres://'):]
            elif clean_url.startswith('postgresql://'):
                return 'postgresql+psycopg2://' + clean_url[len('postgresql://'):]

    return clean_url


def mask_database_url(url: str) -> str:
    """
    Safely and completely masks passwords, tokens, and sensitive query parameters
    in database connection strings for leak-proof logging and exceptions,
    including passwords containing special characters (@, :, %, #, etc.)
    and encoded sensitive query parameter names (e.g. api%5Fkey, sec%72et, t%6Fken).
    Example: postgresql://user:p@ss:w%40rd#123@host:5432/db?sslmode=require&api%5Fkey=secret
             -> postgresql://user:***@host:5432/db?sslmode=require&api%5Fkey=***
    """
    if not url:
        return "<not-set>"
    try:
        url_str = str(url).strip()
        if "://" not in url_str:
            return "<masked-url>"

        scheme, rest = url_str.split("://", 1)

        # Separate query string if present
        path_part, sep, query_part = rest.partition("?")

        # Mask user credentials
        if "@" in path_part:
            creds, host_part = path_part.rsplit("@", 1)
            if ":" in creds:
                user, _ = creds.split(":", 1)
                masked_path = f"{user}:***@{host_part}"
            else:
                masked_path = f"***@{host_part}"
        else:
            masked_path = path_part

        # Mask sensitive query parameters if present
        if query_part:
            sensitive_terms = (
                'token', 'secret', 'password', 'passwd', 'pwd',
                'key', 'apikey', 'auth', 'access_token', 'credential'
            )
            params = query_part.split("&")
            masked_params = []
            for p in params:
                if "=" in p:
                    k, v = p.split("=", 1)
                    decoded_k = unquote_plus(k).strip().lower()
                    normalized_k = decoded_k.replace('-', '_').replace(' ', '_')
                    if (
                        any(term in normalized_k for term in sensitive_terms)
                        or normalized_k.endswith('_key')
                        or normalized_k.startswith('key_')
                        or normalized_k == 'key'
                    ):
                        masked_params.append(f"{k}=***")
                    else:
                        masked_params.append(p)
                else:
                    decoded_p = unquote_plus(p).strip().lower()
                    normalized_p = decoded_p.replace('-', '_').replace(' ', '_')
                    if (
                        any(term in normalized_p for term in sensitive_terms)
                        or normalized_p.endswith('_key')
                        or normalized_p.startswith('key_')
                        or normalized_p == 'key'
                    ):
                        masked_params.append(f"{p}=***")
                    else:
                        masked_params.append(p)
            return f"{scheme}://{masked_path}?{'&'.join(masked_params)}"

        return f"{scheme}://{masked_path}"
    except Exception:
        return "<masked-url>"


def validate_production_secret_key(secret: str) -> None:
    """
    Validates that the production SECRET_KEY is set, non-empty, of sufficient length (>= 32 chars),
    and free from known defaults or obvious low-entropy patterns.

    IMPORTANT CRYPTOGRAPHIC DISTINCTION:
    Empirical metrics (such as character diversity and Shannon character entropy) are heuristic
    sanity checks only. Character distribution in a realized string does not prove cryptographic
    entropy or unpredictable keyspace randomness. Production secrets MUST be generated using a
    cryptographically secure pseudo-random number generator (CSPRNG), for example:
        python -c "import secrets; print(secrets.token_hex(32))"
    which guarantees 32 bytes (256 bits) of true cryptographic entropy from the OS entropy pool.

    Raises RuntimeError on failure. Never prints or logs the secret.
    """
    if not secret or not isinstance(secret, str) or not secret.strip():
        raise RuntimeError(
            "CRITICAL SECURITY CONFIGURATION ERROR: SECRET_KEY environment variable is missing or empty! "
            "Production application startup is aborted. A dedicated secret generated via a cryptographically "
            "secure generator (e.g. python -c \"import secrets; print(secrets.token_hex(32))\") must be set."
        )

    clean_secret = secret.strip()

    # 1. Minimum length check: at least 32 characters
    if len(clean_secret) < 32:
        raise RuntimeError(
            "CRITICAL SECURITY CONFIGURATION ERROR: Production SECRET_KEY is too short! "
            f"Expected at least 32 characters, got {len(clean_secret)}. "
            "Production secrets must be generated using a cryptographically secure generator "
            "(e.g. python -c \"import secrets; print(secrets.token_hex(32))\")."
        )

    # 2. Known defaults check
    known_defaults = [
        'aktu-hms-secret-key',
        'dev-secret-key',
        'test-secret-key',
        'super-secure',
        'hostelease-secret',
    ]
    secret_lower = clean_secret.lower()
    for default in known_defaults:
        if default in secret_lower:
            raise RuntimeError(
                "CRITICAL SECURITY CONFIGURATION ERROR: Known default or insecure development SECRET_KEY "
                "detected in production configuration! Production application startup is aborted. "
                "Production secrets must be generated using a CSPRNG (e.g. secrets.token_hex(32))."
            )

    # 3. Common weak values / predictable prefix patterns
    weak_patterns = [
        'password', 'changeme', 'change-me', 'secret', 'admin',
        '1234567890', 'abcdefghijklmnopqrstuvwxyz', 'qwertyuiop'
    ]
    for weak in weak_patterns:
        if secret_lower == weak or secret_lower.startswith(weak):
            raise RuntimeError(
                "CRITICAL SECURITY CONFIGURATION ERROR: Common weak or predictable SECRET_KEY pattern "
                "detected in production! Production application startup is aborted."
            )

    # 4. Heuristic character diversity check (rejects simple repetitive character patterns)
    if len(set(clean_secret)) < 10:
        raise RuntimeError(
            "CRITICAL SECURITY CONFIGURATION ERROR: Production SECRET_KEY failed heuristic character diversity check "
            "(repetitive character pattern detected). Generate a fresh secret using a CSPRNG "
            "(e.g. python -c \"import secrets; print(secrets.token_hex(32))\")."
        )

    # 5. Heuristic Shannon character entropy check (rejects low-distribution strings)
    import math
    from collections import Counter
    counts = Counter(clean_secret)
    shannon_entropy = -sum((c / len(clean_secret)) * math.log2(c / len(clean_secret)) for c in counts.values())
    if shannon_entropy < 2.8:
        raise RuntimeError(
            "CRITICAL SECURITY CONFIGURATION ERROR: Production SECRET_KEY failed heuristic character entropy threshold. "
            "Production secrets must be generated using a cryptographically secure generator "
            "(e.g. python -c \"import secrets; print(secrets.token_hex(32))\")."
        )


def validate_pool_setting(name: str, val, default: int, allow_zero: bool = False) -> int:
    """
    Validates connection pool size and overflow settings.
    pool_size requires positive integer (> 0).
    max_overflow requires non-negative integer (>= 0 when allow_zero=True).
    Returns sanitized configuration errors for invalid, negative, or non-integer values.
    Does not leak arbitrary input strings or credentials in exception messages.
    """
    if val is None:
        return default

    val_str = str(val).strip()
    if not val_str:
        raise ValueError(
            f"CRITICAL PRODUCTION CONFIGURATION ERROR: Invalid {name} setting. "
            f"{name} cannot be empty or whitespace."
        )

    try:
        parsed_int = int(val_str)
    except (ValueError, TypeError):
        raise ValueError(
            f"CRITICAL PRODUCTION CONFIGURATION ERROR: Invalid {name} setting. "
            f"{name} must be a valid integer."
        )

    min_val = 0 if allow_zero else 1
    if parsed_int < min_val:
        limit_desc = "greater than or equal to zero" if allow_zero else "greater than zero"
        raise ValueError(
            f"CRITICAL PRODUCTION CONFIGURATION ERROR: Invalid {name} setting. "
            f"{name} must be a valid integer {limit_desc}."
        )

    return parsed_int


class Config:
    """Base Configuration Class"""
    SECRET_KEY = os.environ.get('SECRET_KEY')
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
        Dynamically constructs the database URI with explicit precedence:
        1. os.environ['DATABASE_URL'] takes precedence if present (even if explicitly empty).
        2. If 'DATABASE_URL' is absent from os.environ, check cls.DATABASE_URL.
        3. If present and non-empty, normalize and validate it using SQLAlchemy's URL parser.
        4. If default_to_sqlite=False (production), strictly require PostgreSQL and reject
           missing, empty, whitespace-only, malformed, or incomplete non-PostgreSQL URIs.
           Connection strings and credentials are NEVER leaked in exception messages.
        5. If default_to_sqlite=True (development), safely fall back to local MySQL (if configured)
           or local SQLite (instance/hostel.sqlite3).
        """
        # Explicit precedence: os.environ takes precedence over cls.DATABASE_URL
        if 'DATABASE_URL' in os.environ:
            raw_db_url = os.environ['DATABASE_URL']
        else:
            raw_db_url = getattr(cls, 'DATABASE_URL', None)

        if raw_db_url is not None and str(raw_db_url).strip():
            clean_db_url = str(raw_db_url).strip()
            normalized = normalize_database_url(clean_db_url)
            if not default_to_sqlite:
                # Production strictly requires PostgreSQL validated via SQLAlchemy make_url
                try:
                    parsed_url = make_url(normalized)
                except Exception:
                    raise ValueError(
                        "CRITICAL PRODUCTION CONFIGURATION ERROR: Malformed production database URL. "
                        "Production requires a valid PostgreSQL database URI."
                    )

                if parsed_url.get_backend_name() != 'postgresql':
                    raise ValueError(
                        "CRITICAL PRODUCTION CONFIGURATION ERROR: Invalid production database scheme. "
                        "Production requires a PostgreSQL database URI (postgresql+psycopg2://)."
                    )

                if not parsed_url.host or not str(parsed_url.host).strip():
                    raise ValueError(
                        "CRITICAL PRODUCTION CONFIGURATION ERROR: Missing hostname in production database URL. "
                        "Production requires a valid PostgreSQL URL with an explicit hostname."
                    )

                if not parsed_url.database or not str(parsed_url.database).strip():
                    raise ValueError(
                        "CRITICAL PRODUCTION CONFIGURATION ERROR: Missing database name in production database URL. "
                        "Production requires a valid PostgreSQL URL with an explicit database name."
                    )

            return normalized

        # If raw_db_url is absent, empty, or whitespace-only:
        # Check if local MySQL is explicitly configured with password (development only)
        if default_to_sqlite and cls.MYSQL_PASSWORD:
            port = int(cls.MYSQL_PORT) if cls.MYSQL_PORT and str(cls.MYSQL_PORT).isdigit() else 3306
            mysql_url = URL.create(
                drivername="mysql+pymysql",
                username=cls.MYSQL_USER,
                password=cls.MYSQL_PASSWORD,
                host=cls.MYSQL_HOST,
                port=port,
                database=cls.MYSQL_DB,
                query={"charset": "utf8mb4"}
            )
            return mysql_url.render_as_string(hide_password=False)

        # If fallback to SQLite is NOT allowed (production), reject missing/empty/whitespace DATABASE_URL
        if not default_to_sqlite:
            raise ValueError(
                "CRITICAL PRODUCTION CONFIGURATION ERROR: DATABASE_URL environment variable is missing or empty! "
                "Production requires a valid PostgreSQL DATABASE_URL and cannot fall back to SQLite."
            )

        # Default to local SQLite database (default for local development only)
        instance_dir = BASE_DIR / 'instance'
        instance_dir.mkdir(exist_ok=True)
        sqlite_path = instance_dir / 'hostel.sqlite3'
        return f"sqlite:///{sqlite_path.as_posix()}"


class DevelopmentConfig(Config):
    DEBUG = True
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-only-for-local-development')
    SQLALCHEMY_DATABASE_URI = Config.get_database_uri(default_to_sqlite=True)
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
    }


class TestingConfig(Config):
    TESTING = True
    DEBUG = True
    SECRET_KEY = 'test-secret-key-for-unit-testing'
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False


class _ProductionConfigMeta(type):
    @property
    def SQLALCHEMY_DATABASE_URI(cls):
        return cls.get_database_uri(default_to_sqlite=False)

    @property
    def SQLALCHEMY_ENGINE_OPTIONS(cls):
        return cls.get_engine_options()

    @property
    def is_serverless(cls):
        return bool(os.environ.get('VERCEL') or os.environ.get('AWS_LAMBDA_FUNCTION_NAME'))

    def __dir__(cls):
        return list(super().__dir__()) + ['SQLALCHEMY_DATABASE_URI', 'SQLALCHEMY_ENGINE_OPTIONS']


class ProductionConfig(Config, metaclass=_ProductionConfigMeta):
    DEBUG = False
    SECRET_KEY = os.environ.get('SECRET_KEY')  # Must be set in environment; no fallback!

    @classmethod
    def get_engine_options(cls) -> dict:
        """
        Dynamically returns connection pool engine options:
        1. On serverless environments (Vercel / AWS Lambda), returns NullPool
           to avoid connection exhaustion across ephemeral invocations.
        2. In standard production, returns pooled connection settings with validated
           positive integers for DB_POOL_SIZE and DB_MAX_OVERFLOW.
        """
        is_serverless = bool(os.environ.get('VERCEL') or os.environ.get('AWS_LAMBDA_FUNCTION_NAME'))
        if is_serverless:
            return {
                'poolclass': NullPool,
                'pool_pre_ping': True,
            }

        pool_size = validate_pool_setting('DB_POOL_SIZE', os.environ.get('DB_POOL_SIZE'), default=5, allow_zero=False)
        max_overflow = validate_pool_setting('DB_MAX_OVERFLOW', os.environ.get('DB_MAX_OVERFLOW'), default=10, allow_zero=True)

        return {
            'pool_pre_ping': True,
            'pool_recycle': 300,
            'pool_size': pool_size,
            'max_overflow': max_overflow,
        }

    @classmethod
    def validate_production_startup(cls) -> None:
        """Validates all production startup requirements (SECRET_KEY, DATABASE_URL, pool settings)."""
        secret = os.environ.get('SECRET_KEY')
        validate_production_secret_key(secret)
        cls.get_database_uri(default_to_sqlite=False)
        cls.get_engine_options()


config_by_name = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
