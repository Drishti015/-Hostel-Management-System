import os
from flask import Flask, render_template
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from app.config import config_by_name, validate_production_secret_key, mask_database_url, normalize_database_url
from app.models import db, User
from sqlalchemy.engine.url import make_url

# Initialize Extensions
login_manager = LoginManager()
csrf = CSRFProtect()


def sanitize_log_text(text: str) -> str:
    """
    Sanitizes log messages to ensure that database URLs, passwords, tokens,
    and sensitive parameters are never logged.
    """
    if not text:
        return ""
    import re
    # Mask full database URLs
    sanitized = re.sub(
        r'(?:postgresql(?:\+[a-zA-Z0-9_-]+)?|mysql(?:\+[a-zA-Z0-9_-]+)?|sqlite)://[^\s\'"<>]+',
        '[MASKED_DATABASE_URL]',
        str(text)
    )
    # Mask user:pass@host
    sanitized = re.sub(r':([^/@\s]+)@', ':***@', sanitized)
    # Mask password-like patterns
    sanitized = re.sub(
        r'(password|passwd|pwd|secret|token|api[_-]?key)(\s*[:=]\s*)(["\'][^"\']*["\']|[^\s;,\'"<>]+)',
        r'\1\2***',
        sanitized,
        flags=re.IGNORECASE
    )
    # Mask user/username patterns
    sanitized = re.sub(
        r'(username|user)(\s*[:=]\s*)([^\s;,\'"<>]+)',
        r'\1\2***',
        sanitized,
        flags=re.IGNORECASE
    )
    return sanitized


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


def verify_test_database_isolation(app, allow_temp_file_sqlite=False, temp_dir=None):
    """
    Safety Guard: Verifies that the testing application is strictly isolated to an in-memory
    or dedicated temporary SQLite database.
    Raises RuntimeError immediately before any database operation, db.create_all(), or commit if:
    1. The effective database URI is empty or not a string.
    2. The effective database URI is not SQLite (e.g. PostgreSQL, MySQL, Supabase).
    3. Any remote or shared production/development indicators are detected.
    4. An ambiguous SQLite URI form (e.g. 'sqlite://', 'sqlite:///') is provided.
    5. A file-backed SQLite database is used when allow_temp_file_sqlite is False (the default).
    6. When allow_temp_file_sqlite is True, the target database path is not demonstrably located
       inside a dedicated temporary directory, or targets an application database.
    """
    import os
    import tempfile
    from sqlalchemy.engine.url import make_url

    uri = app.config.get('SQLALCHEMY_DATABASE_URI', '')
    if not uri or not isinstance(uri, str) or not uri.strip():
        raise RuntimeError(
            "TEST DATABASE ISOLATION GUARD: SQLALCHEMY_DATABASE_URI is empty in testing mode! "
            "Testing requires an isolated in-memory SQLite database ('sqlite:///:memory:')."
        )

    clean_uri = uri.strip()

    # 1. Reject remote, cloud, or non-SQLite protocols
    forbidden_indicators = [
        'supabase', 'postgresql', 'postgres', 'psycopg2', 'mysql', 'pymysql',
        'aws-0', 'pooler', '6543', '5432', '3306'
    ]
    uri_lower = clean_uri.lower()
    for indicator in forbidden_indicators:
        if indicator in uri_lower:
            raise RuntimeError(
                "CRITICAL TEST ISOLATION GUARD: Remote or shared database configuration detected "
                "in testing mode! Aborting immediately to protect production/development data."
            )

    # Must start with sqlite://
    if not (clean_uri.startswith('sqlite:///') or clean_uri.startswith('sqlite://')):
        raise RuntimeError(
            "TEST DATABASE ISOLATION GUARD VIOLATION: Non-SQLite database URI detected in testing mode! "
            "Refusing to execute tests against non-isolated database."
        )

    # 2. Reject ambiguous SQLite URI forms
    ambiguous_forms = ('sqlite://', 'sqlite:///', 'sqlite:////', 'sqlite:///:')
    if clean_uri in ambiguous_forms:
        raise RuntimeError(
            "TEST DATABASE ISOLATION GUARD VIOLATION: Ambiguous SQLite URI form detected. "
            "Testing strictly requires explicit 'sqlite:///:memory:' to ensure predictable in-memory isolation."
        )

    # 3. Explicitly allow exact in-memory SQLite URI
    if clean_uri == 'sqlite:///:memory:':
        return True

    # 4. Reject all file-backed SQLite URIs by default
    if not allow_temp_file_sqlite:
        raise RuntimeError(
            "TEST DATABASE ISOLATION GUARD VIOLATION: File-backed SQLite URI "
            "is strictly rejected by default! Only 'sqlite:///:memory:' is permitted in testing mode. "
            "File-backed test databases require explicit authorization and dedicated temporary directory containment."
        )

    # 5. When allow_temp_file_sqlite=True, strictly verify dedicated temporary directory containment
    try:
        parsed_url = make_url(clean_uri)
        db_file_path = parsed_url.database
    except Exception as exc:
        exc_type = type(exc).__name__
        raise RuntimeError(
            f"TEST DATABASE ISOLATION GUARD VIOLATION: Unable to parse SQLite database URI [{exc_type}]."
        ) from None

    if not db_file_path or db_file_path == ':memory:':
        raise RuntimeError(
            "TEST DATABASE ISOLATION GUARD VIOLATION: Invalid or ambiguous file path in SQLite URI."
        )

    # Reject application or development database identifiers
    forbidden_app_dbs = [
        'hostel_management.db', 'hostel_management', 'hostel.db',
        'app.db', 'dev.db', 'development.db', 'prod.db', 'production.db',
        'main.db', 'database.db'
    ]
    filename = os.path.basename(db_file_path).lower()
    for forbidden in forbidden_app_dbs:
        if forbidden in filename:
            raise RuntimeError(
                "CRITICAL TEST ISOLATION GUARD VIOLATION: Application or development database "
                "detected in testing configuration! "
                "Normal development databases are strictly forbidden during tests."
            )

    # Verify containment within dedicated temporary directory
    target_temp_dir = os.path.realpath(os.path.abspath(temp_dir or tempfile.gettempdir()))
    resolved_db_path = os.path.realpath(os.path.abspath(db_file_path))

    try:
        common = os.path.commonpath([resolved_db_path, target_temp_dir])
    except ValueError:
        common = None

    if common != target_temp_dir or resolved_db_path == target_temp_dir:
        raise RuntimeError(
            "TEST DATABASE ISOLATION GUARD VIOLATION: File-backed SQLite database path "
            "is not inside the dedicated temporary directory! "
            "File-backed test databases must reside strictly within an authorized temporary directory."
        )

    return True


def create_app(config_name=None, enable_migrations=True):
    """
    Application Factory Pattern for Hostel Management System.
    Configures and assembles all extensions, blueprints, and error handlers.
    
    :param config_name: Target configuration environment name ('development', 'testing', 'production')
    :param enable_migrations: When False, strictly inhibits _ensure_schema_migrations() and all startup DDL.
                              Dedicated for read-only preflight inspections and immutable operational audits.
    """
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'development')

    app = Flask(__name__)
    config_obj = config_by_name.get(config_name, config_by_name['default'])
    app.config.from_object(config_obj)

    is_testing = bool(app.config.get('TESTING') or config_name == 'testing')
    is_production = (config_name == 'production') or (
        isinstance(config_obj, type) and issubclass(config_obj, config_by_name['production'])
    )

    # Production SECRET_KEY enforcement: require properly configured, strong secret key
    if is_production and not is_testing:
        # Re-evaluate SECRET_KEY at runtime from environment for production
        app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY')
        validate_production_secret_key(app.config.get('SECRET_KEY'))

    if is_testing:
        # STRICT TEST ISOLATION: Testing MUST always use isolated in-memory SQLite.
        # Environment variables like DATABASE_URL or .env MUST NEVER override the test database URI.
        app.config['TESTING'] = True
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        app.config['WTF_CSRF_ENABLED'] = False
        # Execute immediate safety guard validation
        verify_test_database_isolation(app)
    else:
        # Re-evaluate DATABASE_URL at runtime if present to ensure dynamic environment overrides (production/development)
        database_url = os.environ.get('DATABASE_URL')
        if database_url and database_url.strip():
            from app.config import normalize_database_url
            app.config['SQLALCHEMY_DATABASE_URI'] = normalize_database_url(database_url)

    # Serverless connection pooling (e.g. Vercel)
    is_serverless = bool(os.environ.get('VERCEL') or os.environ.get('AWS_LAMBDA_FUNCTION_NAME'))
    if is_serverless and not is_testing:
        from sqlalchemy.pool import NullPool
        app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
            'poolclass': NullPool,
            'pool_pre_ping': True,
        }

    # Initialize Extensions with App
    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

    # Configure Login Manager
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access this page.'
    login_manager.login_message_category = 'warning'

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # Register Blueprints
    from app.routes.main import main_bp
    from app.routes.auth import auth_bp
    from app.routes.admin import admin_bp
    from app.routes.warden import warden_bp
    from app.routes.student import student_bp
    from app.routes.security import security_bp
    from app.routes.parent import parent_bp
    from app.routes.mess_staff import mess_staff_bp
    from app.routes.mess_manager import mess_manager_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(warden_bp, url_prefix='/warden')
    app.register_blueprint(student_bp, url_prefix='/student')
    app.register_blueprint(security_bp, url_prefix='/security')
    app.register_blueprint(parent_bp, url_prefix='/parent')
    app.register_blueprint(mess_staff_bp, url_prefix='/mess-staff')
    app.register_blueprint(mess_manager_bp, url_prefix='/mess-manager')

    # Configure Upload Folder & Limits (with serverless read-only filesystem fallback)
    try:
        upload_folder = os.path.join(app.root_path, 'static', 'uploads', 'leave_documents')
        os.makedirs(upload_folder, exist_ok=True)
        os.makedirs(os.path.join(app.root_path, 'static', 'uploads', 'qrcodes'), exist_ok=True)
        app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'static', 'uploads')
    except OSError:
        import tempfile
        tmp_base = os.path.join(tempfile.gettempdir(), 'hostelease_uploads')
        os.makedirs(os.path.join(tmp_base, 'leave_documents'), exist_ok=True)
        os.makedirs(os.path.join(tmp_base, 'qrcodes'), exist_ok=True)
        app.config['UPLOAD_FOLDER'] = tmp_base
    app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024  # 5 MB max upload

    # Global Context Processors (available in all Jinja templates)
    @app.context_processor
    def inject_global_data():
        from flask_login import current_user
        unread_notifications_count = 0
        recent_notifications = []
        if current_user.is_authenticated:
            try:
                from app.services.notification_service import NotificationService
                unread_notifications_count = NotificationService.get_unread_count(current_user.id)
                recent_notifications = NotificationService.get_recent_notifications(current_user.id, limit=5)
            except Exception:
                pass

        return {
            'app_name': 'HostelEase HMS',
            'university_name': 'Dr. A.P.J. Abdul Kalam Technical University',
            'current_year': 2026,
            'unread_notifications_count': unread_notifications_count,
            'recent_notifications': recent_notifications
        }

    # Error Handlers
    @app.errorhandler(403)
    def forbidden_error(error):
        return render_template('components/error.html', code=403, message="Access Forbidden: You don't have permission to access this area."), 403

    @app.errorhandler(404)
    def not_found_error(error):
        return render_template('components/error.html', code=404, message="Page Not Found: The resource you requested could not be located."), 404

    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        orig_exc = getattr(error, 'original_exception', error)
        exc_type = type(orig_exc).__name__
        exc_module = getattr(type(orig_exc), '__module__', '').lower()

        # Database-related exception detection
        is_db_error = (
            'sqlalchemy' in exc_module or
            'psycopg' in exc_module or
            'sqlite' in exc_module or
            any(k in exc_type.lower() for k in ('operationalerror', 'databaseerror', 'sqldatabase', 'interfaceerror', 'integrityerror'))
        )

        if is_db_error:
            # Mask and sanitize: do not dump raw connection strings, URLs, passwords, or driver tracebacks
            app.logger.error(
                f"Internal Server Error (500): Database exception [{exc_type}] occurred. "
                "Transaction rolled back. (Sensitive connection details suppressed for security)."
            )
        else:
            # For general exceptions, sanitize message to strip any credentials or URLs
            sanitized_msg = sanitize_log_text(str(orig_exc))
            app.logger.error(f"Internal Server Error (500): [{exc_type}] {sanitized_msg}")

        return render_template('components/error.html', code=500, message="Internal Server Error: Something went wrong on the server."), 500

    # Ensure database schema is up-to-date in local dev, but avoid running DDL on every serverless invocation,
    # during testing, or when migrations are explicitly disabled (e.g. read-only preflight inspections)
    is_serverless = bool(os.environ.get('VERCEL') or os.environ.get('AWS_LAMBDA_FUNCTION_NAME'))
    if enable_migrations and not is_testing and (not is_serverless or os.environ.get('RUN_DB_MIGRATIONS') == '1'):
        _ensure_schema_migrations(app)

    return app


def create_preflight_app(config_name='production', db_url=None):
    """
    Dedicated, explicit no-schema-migration application factory for preflight inspections.
    Guarantees:
    - Never executes _ensure_schema_migrations(), db.create_all(), or any DDL.
    - Explicitly sets enable_migrations=False.
    - Sets app.config['PREFLIGHT_MODE'] = True.
    - Bypasses the ordinary startup path that can trigger schema alterations.
    - Restores os.environ['DATABASE_URL'] to its exact previous state in an unconditional finally block.
    """
    had_db_url = 'DATABASE_URL' in os.environ
    orig_db_url = os.environ.get('DATABASE_URL')
    try:
        if db_url is not None:
            os.environ['DATABASE_URL'] = db_url
        preflight_app = create_app(config_name=config_name, enable_migrations=False)
        preflight_app.config['PREFLIGHT_MODE'] = True
        return preflight_app
    finally:
        if db_url is not None:
            if had_db_url:
                os.environ['DATABASE_URL'] = orig_db_url
            else:
                os.environ.pop('DATABASE_URL', None)


def _ensure_schema_migrations(app):
    """Safely checks and adds any missing columns or tables on application startup"""
    with app.app_context():
        try:
            from sqlalchemy import inspect, text
            inspector = inspect(db.engine)

            # Ensure new tables (parent_profiles, parent_inquiries) are created if missing
            db.create_all()

            if inspector.has_table('digital_out_passes'):
                existing_cols = [c['name'] for c in inspector.get_columns('digital_out_passes')]
                with db.engine.connect() as conn:
                    col_type = 'TIMESTAMP' if db.engine.dialect.name == 'postgresql' else 'DATETIME'
                    if 'actual_departure_time' not in existing_cols:
                        conn.execute(text(f'ALTER TABLE digital_out_passes ADD COLUMN actual_departure_time {col_type}'))
                        conn.commit()
                    if 'actual_return_time' not in existing_cols:
                        conn.execute(text(f'ALTER TABLE digital_out_passes ADD COLUMN actual_return_time {col_type}'))
                        conn.commit()
        except Exception as e:
            # Sanitized error reporting: log the exception type only and omit raw messages
            # which could contain raw database URLs, credentials, or DSN connection parameters.
            app.logger.warning(
                f"Schema self-healing migration note: {type(e).__name__} encountered during startup schema verification. "
                "Database schema operations were skipped or deferred."
            )

