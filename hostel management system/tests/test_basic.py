import unittest
import os
import secrets
from app import create_app, db
from app.models import User, Student, Hostel

class BasicTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
        self.client = self.app.test_client()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_app_exists(self):
        self.assertFalse(self.app is None)

    def test_landing_page(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'HostelEase HMS', response.data)

    def test_login_page(self):
        response = self.client.get('/auth/login')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Portal Sign In', response.data)

    def test_user_password_hashing(self):
        u = User(username='test_user', email='test@aktu.ac.in', role='student')
        u.set_password('Pass1234')
        self.assertTrue(u.check_password('Pass1234'))
        self.assertFalse(u.check_password('WrongPass'))

    def test_test_database_is_isolated_in_memory_sqlite(self):
        """Verifies that create_app('testing') strictly uses an isolated in-memory SQLite database."""
        self.assertTrue(self.app.config.get('TESTING'))
        self.assertEqual(self.app.config.get('SQLALCHEMY_DATABASE_URI'), 'sqlite:///:memory:')
        self.assertEqual(db.engine.url.drivername, 'sqlite')
        self.assertEqual(db.engine.url.database, ':memory:')

    def test_environment_database_url_cannot_override_testing_uri(self):
        """Verifies that an environment DATABASE_URL or Config.DATABASE_URL cannot override the testing database URI."""
        import os
        from app.config import Config
        orig_env_db_url = os.environ.get('DATABASE_URL')
        orig_cls_db_url = getattr(Config, 'DATABASE_URL', None)
        try:
            os.environ['DATABASE_URL'] = 'postgresql://user:pass@fake.supabase.com:6543/proddb'
            Config.DATABASE_URL = 'postgresql://user:pass@fake.supabase.com:6543/proddb'
            test_app = create_app('testing')
            self.assertEqual(test_app.config.get('SQLALCHEMY_DATABASE_URI'), 'sqlite:///:memory:')
            self.assertEqual(test_app.config.get('TESTING'), True)
        finally:
            if orig_env_db_url is not None:
                os.environ['DATABASE_URL'] = orig_env_db_url
            else:
                os.environ.pop('DATABASE_URL', None)
            Config.DATABASE_URL = orig_cls_db_url

    def test_isolation_guard_accepts_in_memory_sqlite(self):
        """Verifies that sqlite:///:memory: is explicitly accepted by the guard."""
        from app import verify_test_database_isolation
        from flask import Flask
        app = Flask('memory_test_app')
        app.config['TESTING'] = True
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        self.assertTrue(verify_test_database_isolation(app))

    def test_isolation_guard_rejects_file_backed_by_default(self):
        """Verifies that all file-backed SQLite URIs are rejected by default."""
        from app import verify_test_database_isolation
        from flask import Flask
        app = Flask('file_backed_test_app')
        app.config['TESTING'] = True

        # Rejected by default even with 'test', 'tmp', or 'testing' in filename
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///test_temporary_unit.db'
        with self.assertRaises(RuntimeError) as ctx:
            verify_test_database_isolation(app)
        self.assertIn("File-backed SQLite URI", str(ctx.exception))
        self.assertIn("strictly rejected by default", str(ctx.exception))

        # Rejected by default for normal development DB
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///hostel_management.db'
        with self.assertRaises(RuntimeError) as ctx:
            verify_test_database_isolation(app)
        self.assertIn("strictly rejected by default", str(ctx.exception))

        # Rejected by default for other file paths
        for path in ('sqlite:///app_data.db', 'sqlite:///dev.db', 'sqlite:////tmp/test.db'):
            app.config['SQLALCHEMY_DATABASE_URI'] = path
            with self.assertRaises(RuntimeError) as ctx:
                verify_test_database_isolation(app)
            self.assertIn("strictly rejected by default", str(ctx.exception))

    def test_isolation_guard_rejects_ambiguous_sqlite_uris(self):
        """Verifies that ambiguous SQLite URIs without explicit :memory: are rejected."""
        from app import verify_test_database_isolation
        from flask import Flask
        app = Flask('ambiguous_uri_test_app')
        app.config['TESTING'] = True

        for ambiguous_uri in ('sqlite://', 'sqlite:///', 'sqlite:////', 'sqlite:///:', '   '):
            app.config['SQLALCHEMY_DATABASE_URI'] = ambiguous_uri
            with self.assertRaises(RuntimeError) as ctx:
                verify_test_database_isolation(app)
            self.assertTrue(
                "Ambiguous SQLite URI form" in str(ctx.exception) or
                "SQLALCHEMY_DATABASE_URI is empty" in str(ctx.exception)
            )

    def test_isolation_guard_dedicated_temp_dir_containment(self):
        """Verifies that file-backed SQLite is accepted ONLY when explicitly supported and inside a dedicated temp dir."""
        import os
        import tempfile
        import shutil
        from app import verify_test_database_isolation
        from flask import Flask

        app = Flask('temp_dir_containment_app')
        app.config['TESTING'] = True

        dedicated_temp_dir = tempfile.mkdtemp(prefix='hms_test_guard_')
        try:
            # 1. Valid temporary database inside dedicated directory
            valid_db_path = os.path.join(dedicated_temp_dir, 'isolated_test_run.db')
            # Normalize to forward slashes for SQLite URI
            uri_path = valid_db_path.replace('\\', '/')
            app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{uri_path}'

            # Must be accepted when explicitly authorized with allow_temp_file_sqlite=True and temp_dir
            self.assertTrue(verify_test_database_isolation(app, allow_temp_file_sqlite=True, temp_dir=dedicated_temp_dir))

            # Must still be rejected when allow_temp_file_sqlite is False (the default)
            with self.assertRaises(RuntimeError) as ctx:
                verify_test_database_isolation(app, allow_temp_file_sqlite=False, temp_dir=dedicated_temp_dir)
            self.assertIn("strictly rejected by default", str(ctx.exception))

            # 2. Database path outside dedicated directory must be rejected even if allow_temp_file_sqlite=True
            app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///outside_test.db'
            with self.assertRaises(RuntimeError) as ctx:
                verify_test_database_isolation(app, allow_temp_file_sqlite=True, temp_dir=dedicated_temp_dir)
            self.assertIn("is not inside the dedicated temporary directory", str(ctx.exception))

            # 3. Application database name must be rejected even inside dedicated temporary directory
            app_named_db = os.path.join(dedicated_temp_dir, 'hostel_management.db').replace('\\', '/')
            app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{app_named_db}'
            with self.assertRaises(RuntimeError) as ctx:
                verify_test_database_isolation(app, allow_temp_file_sqlite=True, temp_dir=dedicated_temp_dir)
            err_msg = str(ctx.exception)
            self.assertIn("Application or development database", err_msg)
            self.assertNotIn("hostel_management.db", err_msg)
            self.assertNotIn(dedicated_temp_dir, err_msg)
        finally:
            shutil.rmtree(dedicated_temp_dir, ignore_errors=True)

    def test_isolation_guard_rejects_supabase_and_postgres(self):
        """Verifies that Supabase / PostgreSQL URIs are strictly rejected."""
        from app import verify_test_database_isolation
        from flask import Flask
        app = Flask('postgres_test_app')
        app.config['TESTING'] = True

        app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql+psycopg2://user:pass@db.supabase.co:6543/postgres'
        with self.assertRaises(RuntimeError):
            verify_test_database_isolation(app)

        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///supabase_test.db'
        with self.assertRaises(RuntimeError):
            verify_test_database_isolation(app)

    def test_isolation_guard_rejects_empty_uri(self):
        """Verifies that an empty URI is strictly rejected."""
        from app import verify_test_database_isolation
        from flask import Flask
        app = Flask('empty_test_app')
        app.config['TESTING'] = True

        app.config['SQLALCHEMY_DATABASE_URI'] = ''
        with self.assertRaises(RuntimeError) as ctx:
            verify_test_database_isolation(app)
        self.assertIn("empty in testing mode", str(ctx.exception))

    def test_serverless_environment_does_not_affect_testing_engine(self):
        """Verifies serverless env vars do not inject NullPool into create_app('testing')."""
        import os
        orig_vercel = os.environ.get('VERCEL')
        orig_lambda = os.environ.get('AWS_LAMBDA_FUNCTION_NAME')
        try:
            os.environ['VERCEL'] = '1'
            os.environ['AWS_LAMBDA_FUNCTION_NAME'] = 'test-lambda-function'
            test_app = create_app('testing')
            engine_opts = test_app.config.get('SQLALCHEMY_ENGINE_OPTIONS') or {}
            self.assertNotIn('poolclass', engine_opts)
            self.assertEqual(test_app.config.get('SQLALCHEMY_DATABASE_URI'), 'sqlite:///:memory:')

            # Verify in-memory SQLite tables persist and query normally
            with test_app.app_context():
                db.create_all()
                u = User(username='pool_test', email='pool@test.com', role='student')
                u.set_password('PoolTestPass123!')
                db.session.add(u)
                db.session.commit()
                found = User.query.filter_by(username='pool_test').first()
                self.assertIsNotNone(found)
        finally:
            if orig_vercel is not None:
                os.environ['VERCEL'] = orig_vercel
            else:
                os.environ.pop('VERCEL', None)
            if orig_lambda is not None:
                os.environ['AWS_LAMBDA_FUNCTION_NAME'] = orig_lambda
            else:
                os.environ.pop('AWS_LAMBDA_FUNCTION_NAME', None)

    def test_production_secret_key_required_and_insecure_defaults_rejected(self):
        """Verifies validate_production_secret_key directly: heuristic checks vs cryptographic CSPRNG generation."""
        import secrets
        from app import validate_production_secret_key

        # 1. Missing or empty secret key
        for empty_val in (None, '', '   '):
            with self.assertRaises(RuntimeError) as ctx:
                validate_production_secret_key(empty_val)
            self.assertIn("CRITICAL SECURITY CONFIGURATION ERROR", str(ctx.exception))
            self.assertIn("missing or empty", str(ctx.exception))

        # 2. Short secret keys (< 32 characters)
        for short_val in ('short-secret', 'a' * 31, '12345678901234567890'):
            with self.assertRaises(RuntimeError) as ctx:
                validate_production_secret_key(short_val)
            self.assertIn("CRITICAL SECURITY CONFIGURATION ERROR", str(ctx.exception))
            self.assertIn("too short", str(ctx.exception))
            self.assertNotIn(short_val, str(ctx.exception))

        # 3. Known default secret keys
        for default_key in (
            'aktu-hms-secret-key-2026-super-secure',
            'dev-secret-key-only-for-local-development',
            'test-secret-key-for-unit-testing',
        ):
            with self.assertRaises(RuntimeError) as ctx:
                validate_production_secret_key(default_key)
            self.assertIn("CRITICAL SECURITY CONFIGURATION ERROR", str(ctx.exception))
            self.assertIn("Known default or insecure development SECRET_KEY", str(ctx.exception))
            self.assertNotIn(default_key, str(ctx.exception))

        # 4. Common weak / predictable values
        for weak_key in (
            'passwordpasswordpasswordpassword',
            '12345678901234567890123456789012',
            'changemechangemechangemechangeme',
        ):
            with self.assertRaises(RuntimeError) as ctx:
                validate_production_secret_key(weak_key)
            self.assertIn("CRITICAL SECURITY CONFIGURATION ERROR", str(ctx.exception))
            self.assertNotIn(weak_key, str(ctx.exception))

        # 5. Heuristic character diversity check (rejects repetitive character patterns)
        with self.assertRaises(RuntimeError) as ctx:
            validate_production_secret_key('a' * 64)
        self.assertIn("CRITICAL SECURITY CONFIGURATION ERROR", str(ctx.exception))
        self.assertIn("heuristic character diversity check", str(ctx.exception))

        # 6. Cryptographically generated secrets from CSPRNG (e.g. secrets.token_hex(32))
        # True 256 bits of cryptographic entropy are provided by the generator (CSPRNG),
        # while character distribution serves only as a heuristic sanity filter.
        strong_hex = secrets.token_hex(32)  # 64 hex characters (256 bits of entropy from CSPRNG)
        validate_production_secret_key(strong_hex)  # Must pass without exception

        strong_b64 = secrets.token_urlsafe(32)  # 43 base64 characters (> 256 bits of entropy from CSPRNG)
        validate_production_secret_key(strong_b64)  # Must pass without exception

    def test_database_url_precedence_and_empty_isolation(self):
        """Verifies explicit precedence: empty/whitespace os.environ['DATABASE_URL'] takes precedence over Config.DATABASE_URL."""
        import os
        from app.config import Config, ProductionConfig
        orig_env_db_url = os.environ.get('DATABASE_URL')
        orig_cls_db_url = getattr(Config, 'DATABASE_URL', None)
        try:
            # When Config.DATABASE_URL has a value (e.g. from .env at import time),
            # but os.environ['DATABASE_URL'] is explicitly set to empty or whitespace,
            # os.environ must take precedence and must NOT fall back to Config.DATABASE_URL.
            Config.DATABASE_URL = 'postgresql://pguser:pgpass@127.0.0.1:5432/hostel_prod'

            # Explicitly empty string in os.environ
            os.environ['DATABASE_URL'] = ''
            with self.assertRaises(ValueError) as ctx:
                Config.get_database_uri(default_to_sqlite=False)
            self.assertIn("missing or empty", str(ctx.exception))
            with self.assertRaises(ValueError) as ctx:
                _ = ProductionConfig.SQLALCHEMY_DATABASE_URI
            self.assertIn("missing or empty", str(ctx.exception))

            # Explicit whitespace in os.environ
            os.environ['DATABASE_URL'] = '   \t\n  '
            with self.assertRaises(ValueError) as ctx:
                Config.get_database_uri(default_to_sqlite=False)
            self.assertIn("missing or empty", str(ctx.exception))
            with self.assertRaises(ValueError) as ctx:
                _ = ProductionConfig.SQLALCHEMY_DATABASE_URI
            self.assertIn("missing or empty", str(ctx.exception))

            # When absent from os.environ, Config.DATABASE_URL is used as fallback
            os.environ.pop('DATABASE_URL', None)
            Config.DATABASE_URL = 'postgresql://pguser:pgpass@127.0.0.1:5432/hostel_prod'
            uri = Config.get_database_uri(default_to_sqlite=False)
            self.assertEqual(uri, 'postgresql+psycopg2://pguser:pgpass@127.0.0.1:5432/hostel_prod')
        finally:
            if orig_env_db_url is not None:
                os.environ['DATABASE_URL'] = orig_env_db_url
            else:
                os.environ.pop('DATABASE_URL', None)
            Config.DATABASE_URL = orig_cls_db_url

    def test_production_database_uri_fails_safely_when_missing_or_invalid(self):
        """Verifies Config.get_database_uri(default_to_sqlite=False) rejects absent, empty, whitespace, and non-PostgreSQL URLs."""
        import os
        from app.config import Config, ProductionConfig
        orig_env_db_url = os.environ.get('DATABASE_URL')
        orig_cls_db_url = getattr(Config, 'DATABASE_URL', None)
        try:
            # 1. DATABASE_URL absent (both os.environ and Config.DATABASE_URL are cleared)
            os.environ.pop('DATABASE_URL', None)
            Config.DATABASE_URL = None
            with self.assertRaises(ValueError) as ctx:
                Config.get_database_uri(default_to_sqlite=False)
            self.assertIn("CRITICAL PRODUCTION CONFIGURATION ERROR", str(ctx.exception))
            self.assertIn("missing or empty", str(ctx.exception))
            with self.assertRaises(ValueError) as ctx:
                _ = ProductionConfig.SQLALCHEMY_DATABASE_URI
            self.assertIn("missing or empty", str(ctx.exception))

            # 2. DATABASE_URL empty
            os.environ['DATABASE_URL'] = ''
            Config.DATABASE_URL = None
            with self.assertRaises(ValueError) as ctx:
                Config.get_database_uri(default_to_sqlite=False)
            self.assertIn("CRITICAL PRODUCTION CONFIGURATION ERROR", str(ctx.exception))
            self.assertIn("missing or empty", str(ctx.exception))
            with self.assertRaises(ValueError) as ctx:
                _ = ProductionConfig.SQLALCHEMY_DATABASE_URI
            self.assertIn("missing or empty", str(ctx.exception))

            # 3. DATABASE_URL containing whitespace
            os.environ['DATABASE_URL'] = '   \t\r\n   '
            Config.DATABASE_URL = None
            with self.assertRaises(ValueError) as ctx:
                Config.get_database_uri(default_to_sqlite=False)
            self.assertIn("CRITICAL PRODUCTION CONFIGURATION ERROR", str(ctx.exception))
            self.assertIn("missing or empty", str(ctx.exception))
            with self.assertRaises(ValueError) as ctx:
                _ = ProductionConfig.SQLALCHEMY_DATABASE_URI
            self.assertIn("missing or empty", str(ctx.exception))

            # 4. DATABASE_URL containing SQLite in production
            os.environ['DATABASE_URL'] = 'sqlite:///hostel_management.db'
            Config.DATABASE_URL = None
            with self.assertRaises(ValueError) as ctx:
                Config.get_database_uri(default_to_sqlite=False)
            self.assertIn("CRITICAL PRODUCTION CONFIGURATION ERROR", str(ctx.exception))
            self.assertIn("Invalid production database scheme", str(ctx.exception))
            with self.assertRaises(ValueError) as ctx:
                _ = ProductionConfig.SQLALCHEMY_DATABASE_URI
            self.assertIn("Invalid production database scheme", str(ctx.exception))

            # 5. DATABASE_URL containing MySQL in production
            os.environ['DATABASE_URL'] = 'mysql+pymysql://root:pass@localhost:3306/hostel_db'
            Config.DATABASE_URL = None
            with self.assertRaises(ValueError) as ctx:
                Config.get_database_uri(default_to_sqlite=False)
            self.assertIn("CRITICAL PRODUCTION CONFIGURATION ERROR", str(ctx.exception))
            self.assertIn("Invalid production database scheme", str(ctx.exception))
            with self.assertRaises(ValueError) as ctx:
                _ = ProductionConfig.SQLALCHEMY_DATABASE_URI
            self.assertIn("Invalid production database scheme", str(ctx.exception))

            # 5B. Malformed production database URL (e.g. invalid non-numeric port)
            secret_pwd = "P@ss:w%40rd#456!"
            os.environ['DATABASE_URL'] = f'postgresql://myuser:{secret_pwd}@myhost:abc/mydb'
            Config.DATABASE_URL = None
            with self.assertRaises(ValueError) as ctx:
                Config.get_database_uri(default_to_sqlite=False)
            self.assertIn("CRITICAL PRODUCTION CONFIGURATION ERROR", str(ctx.exception))
            self.assertIn("Malformed production database URL", str(ctx.exception))
            # Verify credentials and full URL are NEVER leaked in exception message
            self.assertNotIn(secret_pwd, str(ctx.exception))
            self.assertNotIn("myhost", str(ctx.exception))

            # 5C. Missing hostname in production database URL
            os.environ['DATABASE_URL'] = 'postgresql://myuser:mypass@/mydb'
            Config.DATABASE_URL = None
            with self.assertRaises(ValueError) as ctx:
                Config.get_database_uri(default_to_sqlite=False)
            self.assertIn("CRITICAL PRODUCTION CONFIGURATION ERROR", str(ctx.exception))
            self.assertIn("Missing hostname", str(ctx.exception))
            self.assertNotIn("mypass", str(ctx.exception))

            # 5D. Missing database name in production database URL
            os.environ['DATABASE_URL'] = 'postgresql://myuser:mypass@myhost:5432'
            Config.DATABASE_URL = None
            with self.assertRaises(ValueError) as ctx:
                Config.get_database_uri(default_to_sqlite=False)
            self.assertIn("CRITICAL PRODUCTION CONFIGURATION ERROR", str(ctx.exception))
            self.assertIn("Missing database name", str(ctx.exception))
            self.assertNotIn("mypass", str(ctx.exception))

            # 6. Valid PostgreSQL URL in production is accepted and normalized
            valid_pg = 'postgresql://pguser:pgpass@127.0.0.1:5432/hostel_prod'
            os.environ['DATABASE_URL'] = valid_pg
            Config.DATABASE_URL = None
            prod_uri = Config.get_database_uri(default_to_sqlite=False)
            self.assertEqual(prod_uri, 'postgresql+psycopg2://pguser:pgpass@127.0.0.1:5432/hostel_prod')
            self.assertEqual(ProductionConfig.SQLALCHEMY_DATABASE_URI, prod_uri)

            # 7. Development SQLite fallback (default_to_sqlite=True with absent/empty DATABASE_URL)
            os.environ.pop('DATABASE_URL', None)
            Config.DATABASE_URL = None
            dev_uri = Config.get_database_uri(default_to_sqlite=True)
            self.assertTrue(dev_uri.startswith('sqlite:///'))
            self.assertIn('instance/hostel.sqlite3', dev_uri.replace('\\', '/'))
        finally:
            if orig_env_db_url is not None:
                os.environ['DATABASE_URL'] = orig_env_db_url
            else:
                os.environ.pop('DATABASE_URL', None)
            Config.DATABASE_URL = orig_cls_db_url

    def test_production_config_from_object_fails_before_database_initialization(self):
        """Verifies Flask's app.config.from_object(ProductionConfig) evaluates dynamic property and fails before DB init."""
        from flask import Flask
        import os
        from app.config import Config, ProductionConfig
        orig_env_db_url = os.environ.get('DATABASE_URL')
        orig_cls_db_url = getattr(Config, 'DATABASE_URL', None)
        try:
            # A) With empty DATABASE_URL: from_object(ProductionConfig) must raise ValueError immediately
            os.environ['DATABASE_URL'] = ''
            Config.DATABASE_URL = None
            dummy_app_empty = Flask('from_object_empty_test')
            with self.assertRaises(ValueError) as ctx:
                dummy_app_empty.config.from_object(ProductionConfig)
            self.assertIn("missing or empty", str(ctx.exception))

            # B) With non-PostgreSQL (SQLite): from_object(ProductionConfig) must raise ValueError immediately
            os.environ['DATABASE_URL'] = 'sqlite:///hostel_management.db'
            Config.DATABASE_URL = None
            dummy_app_sqlite = Flask('from_object_sqlite_test')
            with self.assertRaises(ValueError) as ctx:
                dummy_app_sqlite.config.from_object(ProductionConfig)
            self.assertIn("Invalid production database scheme", str(ctx.exception))

            # C) With valid PostgreSQL URL: from_object(ProductionConfig) succeeds and populates SQLALCHEMY_DATABASE_URI
            os.environ['DATABASE_URL'] = 'postgresql://pguser:pgpass@127.0.0.1:5432/hostel_prod'
            Config.DATABASE_URL = None
            dummy_app_valid = Flask('from_object_valid_test')
            dummy_app_valid.config.from_object(ProductionConfig)
            self.assertEqual(
                dummy_app_valid.config['SQLALCHEMY_DATABASE_URI'],
                'postgresql+psycopg2://pguser:pgpass@127.0.0.1:5432/hostel_prod'
            )
        finally:
            if orig_env_db_url is not None:
                os.environ['DATABASE_URL'] = orig_env_db_url
            else:
                os.environ.pop('DATABASE_URL', None)
            Config.DATABASE_URL = orig_cls_db_url

    def test_application_factory_production_mode_isolated_with_mocks(self):
        """Proves that if create_app('production') is exercised, database init and migrations are mocked so no engine connection occurs."""
        from unittest.mock import patch
        import os
        import secrets
        from app.config import Config

        orig_secret = os.environ.get('SECRET_KEY')
        orig_db_url = os.environ.get('DATABASE_URL')
        orig_cls_db_url = getattr(Config, 'DATABASE_URL', None)
        try:
            os.environ['SECRET_KEY'] = secrets.token_hex(32)
            os.environ['DATABASE_URL'] = 'postgresql+psycopg2://mock_user:mock_pass@127.0.0.1:5432/mock_prod_db'
            Config.DATABASE_URL = None

            # Mock db.init_app, and _ensure_schema_migrations so no engine connection can occur
            with patch('app.models.db.init_app') as mock_db_init, \
                 patch('app._ensure_schema_migrations') as mock_migrations:
                prod_app = create_app('production')
                self.assertFalse(prod_app.config['TESTING'])
                self.assertEqual(
                    prod_app.config['SQLALCHEMY_DATABASE_URI'],
                    'postgresql+psycopg2://mock_user:mock_pass@127.0.0.1:5432/mock_prod_db'
                )
                mock_db_init.assert_called_once()
                mock_migrations.assert_called_once_with(prod_app)
        finally:
            if orig_secret is not None:
                os.environ['SECRET_KEY'] = orig_secret
            else:
                os.environ.pop('SECRET_KEY', None)
            if orig_db_url is not None:
                os.environ['DATABASE_URL'] = orig_db_url
            else:
                os.environ.pop('DATABASE_URL', None)
            Config.DATABASE_URL = orig_cls_db_url

    def test_regression_local_tests_cannot_initialize_production_database(self):
        """Regression test ensuring local test execution cannot connect to or initialize a production database."""
        from app import verify_test_database_isolation
        from flask import Flask

        # 1. create_app('testing') is locked to in-memory SQLite
        test_app = create_app('testing')
        self.assertEqual(test_app.config['SQLALCHEMY_DATABASE_URI'], 'sqlite:///:memory:')

        # 2. verify_test_database_isolation aborts immediately on production indicators
        fake_prod_app = Flask('fake_prod')
        fake_prod_app.config['TESTING'] = True
        fake_prod_app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql+psycopg2://user:pass@db.supabase.co:6543/postgres'

        with self.assertRaises(RuntimeError) as ctx:
            verify_test_database_isolation(fake_prod_app)
        err_msg = str(ctx.exception)
        self.assertIn("Remote or shared database configuration detected", err_msg)
        self.assertNotIn("supabase", err_msg)

    def test_development_and_testing_configs_have_safe_secrets(self):
        """Verifies development and testing config classes define safe default secrets when unset in environment."""
        import os
        from app.config import DevelopmentConfig, TestingConfig
        orig_secret = os.environ.get('SECRET_KEY')
        try:
            os.environ.pop('SECRET_KEY', None)
            self.assertTrue(bool(DevelopmentConfig.SECRET_KEY))
            self.assertTrue(bool(TestingConfig.SECRET_KEY))
            self.assertNotEqual(DevelopmentConfig.SECRET_KEY, TestingConfig.SECRET_KEY)
        finally:
            if orig_secret is not None:
                os.environ['SECRET_KEY'] = orig_secret
            else:
                os.environ.pop('SECRET_KEY', None)

    def test_schema_migrations_sanitized_exception_logging(self):
        """Verifies _ensure_schema_migrations logs sanitized error without exposing credentials."""
        from unittest.mock import patch
        from app import _ensure_schema_migrations
        import logging

        test_app = create_app('testing')
        sensitive_msg = "FATAL: password authentication failed for user 'sensitive_db_user': secret_db_password"
        with patch('app.models.db.create_all', side_effect=Exception(sensitive_msg)):
            with self.assertLogs(test_app.logger, level=logging.WARNING) as cm:
                _ensure_schema_migrations(test_app)

            log_output = " ".join(cm.output)
            self.assertIn("Schema self-healing migration note: Exception encountered", log_output)
            self.assertNotIn("secret_db_password", log_output)
            self.assertNotIn("sensitive_db_user", log_output)

    def test_mask_database_url_handles_complex_special_characters(self):
        """Verifies mask_database_url completely removes passwords with @, :, %, # and special characters."""
        from app.config import mask_database_url
        test_passwords = [
            "P@ssw0rd!123",
            "Pass:Word:123",
            "Pass%25Word%20",
            "My%40Pass%23%24Word",
            "P@ss:w%40rd#456!",
        ]
        for pwd in test_passwords:
            url = f"postgresql://pg_user:{pwd}@aws-0-ap-south-1.pooler.supabase.com:6543/proddb?sslmode=require"
            masked = mask_database_url(url)
            self.assertNotIn(pwd, masked)
            self.assertIn(":***@", masked)
            self.assertTrue(masked.startswith("postgresql://pg_user:***@"))

    def test_preflight_app_never_invokes_schema_migrations_or_ddl(self):
        """Proves preflight initialization via create_preflight_app never runs _ensure_schema_migrations() or DDL."""
        from unittest.mock import patch
        import os
        import secrets
        from app import create_preflight_app, create_app
        from app.config import Config

        orig_secret = os.environ.get('SECRET_KEY')
        orig_db_url = os.environ.get('DATABASE_URL')
        orig_vercel = os.environ.get('VERCEL')
        orig_lambda = os.environ.get('AWS_LAMBDA_FUNCTION_NAME')
        orig_cls_db_url = getattr(Config, 'DATABASE_URL', None)

        try:
            # Simulate non-serverless local/Windows production environment
            os.environ['SECRET_KEY'] = secrets.token_hex(32)
            os.environ['DATABASE_URL'] = 'postgresql+psycopg2://preflight_user:preflight_pass@127.0.0.1:5432/preflight_db'
            os.environ.pop('VERCEL', None)
            os.environ.pop('AWS_LAMBDA_FUNCTION_NAME', None)
            Config.DATABASE_URL = None

            with patch('app.models.db.init_app'), \
                 patch('app._ensure_schema_migrations') as mock_migrations, \
                 patch('app.models.db.create_all') as mock_create_all:

                # 1. create_preflight_app must not run schema migrations
                preflight_app = create_preflight_app('production')
                self.assertTrue(preflight_app.config.get('PREFLIGHT_MODE'))
                mock_migrations.assert_not_called()
                mock_create_all.assert_not_called()

                # 2. create_app with enable_migrations=False must also not run schema migrations
                preflight_app2 = create_app('production', enable_migrations=False)
                mock_migrations.assert_not_called()
                mock_create_all.assert_not_called()
        finally:
            if orig_secret is not None:
                os.environ['SECRET_KEY'] = orig_secret
            else:
                os.environ.pop('SECRET_KEY', None)
            if orig_db_url is not None:
                os.environ['DATABASE_URL'] = orig_db_url
            else:
                os.environ.pop('DATABASE_URL', None)
            if orig_vercel is not None:
                os.environ['VERCEL'] = orig_vercel
            else:
                os.environ.pop('VERCEL', None)
            if orig_lambda is not None:
                os.environ['AWS_LAMBDA_FUNCTION_NAME'] = orig_lambda
            else:
                os.environ.pop('AWS_LAMBDA_FUNCTION_NAME', None)
            Config.DATABASE_URL = orig_cls_db_url

    def test_preflight_read_only_guards_abort_write_and_ddl(self):
        """Proves preflight read-only guards allow SELECT but abort any write or DDL operations."""
        from sqlalchemy import text
        from migrate_demo_accounts_prod import configure_read_only_preflight_guards

        test_app = create_app('testing')
        with test_app.app_context():
            cleanup_guards = configure_read_only_preflight_guards(db.engine)
            try:
                # 1. SELECT query must execute normally
                res = db.session.execute(text("SELECT 1")).scalar()
                self.assertEqual(res, 1)

                # 2. INSERT statement must be intercepted and rejected
                with self.assertRaises(Exception) as ctx:
                    db.session.execute(text("INSERT INTO users (username) VALUES ('illegal_user')"))
                err_str = str(ctx.exception)
                self.assertTrue(
                    "PREFLIGHT SAFETY VIOLATION" in err_str or
                    "attempt to write a readonly database" in err_str.lower()
                )

                # 3. CREATE statement must be intercepted and rejected
                with self.assertRaises(Exception) as ctx:
                    db.session.execute(text("CREATE TABLE illegal_tbl (id INT)"))
                err_str = str(ctx.exception)
                self.assertTrue(
                    "PREFLIGHT SAFETY VIOLATION" in err_str or
                    "attempt to write a readonly database" in err_str.lower()
                )

                # 4. DROP statement must be intercepted and rejected
                with self.assertRaises(Exception) as ctx:
                    db.session.execute(text("DROP TABLE users"))
                err_str = str(ctx.exception)
                self.assertTrue(
                    "PREFLIGHT SAFETY VIOLATION" in err_str or
                    "attempt to write a readonly database" in err_str.lower()
                )
            finally:
                cleanup_guards()

    def test_preflight_database_credentials_never_appear_in_exceptions_or_logs(self):
        """Proves database credentials never appear in preflight exceptions or log messages."""
        import logging
        from app import sanitize_log_text
        from migrate_demo_accounts_prod import format_safe_exception_report

        secret_pass = "UltraSecretDBPasswordXYZ#999"
        raw_error_msg = f"psycopg2.OperationalError: password=\"{secret_pass}\" host=\"aws-0-ap-south-1.pooler.supabase.com\""

        # 1. format_safe_exception_report must completely strip credentials
        safe_report = format_safe_exception_report(Exception(raw_error_msg), "Preflight database connection")
        self.assertNotIn(secret_pass, safe_report)
        self.assertNotIn("password=", safe_report)

        # 2. sanitize_log_text must mask connection strings and credentials
        sanitized = sanitize_log_text(raw_error_msg)
        self.assertNotIn(secret_pass, sanitized)

    def test_mysql_url_construction_with_special_characters(self):
        """Verifies MySQL URL construction uses URL.create() and handles special characters in passwords."""
        import os
        from app.config import Config
        from sqlalchemy.engine.url import make_url

        orig_user = Config.MYSQL_USER
        orig_pwd = Config.MYSQL_PASSWORD
        orig_db = Config.MYSQL_DB
        orig_env_db = os.environ.get('DATABASE_URL')
        orig_cls_db = getattr(Config, 'DATABASE_URL', None)

        try:
            os.environ.pop('DATABASE_URL', None)
            Config.DATABASE_URL = None
            Config.MYSQL_USER = 'test_mysql_user'
            Config.MYSQL_PASSWORD = 'p@ss:w%40rd#123!'
            Config.MYSQL_DB = 'test_hostel_db'

            mysql_uri = Config.get_database_uri(default_to_sqlite=True)
            self.assertTrue(mysql_uri.startswith('mysql+pymysql://'))
            parsed = make_url(mysql_uri)
            self.assertEqual(parsed.username, 'test_mysql_user')
            self.assertEqual(parsed.password, 'p@ss:w%40rd#123!')
            self.assertEqual(parsed.database, 'test_hostel_db')
        finally:
            Config.MYSQL_USER = orig_user
            Config.MYSQL_PASSWORD = orig_pwd
            Config.MYSQL_DB = orig_db
            if orig_env_db is not None:
                os.environ['DATABASE_URL'] = orig_env_db
            else:
                os.environ.pop('DATABASE_URL', None)
            Config.DATABASE_URL = orig_cls_db

    def test_sql_statement_interception_leading_comments_ctes_and_multi_statement(self):
        """Verifies validate_readonly_sql rejects comments, CTEs, multi-statements, SELECT INTO, and unexpected statements."""
        from migrate_demo_accounts_prod import validate_readonly_sql

        # 1. Normal read-only statements
        self.assertTrue(validate_readonly_sql("SELECT * FROM users")[0])
        self.assertTrue(validate_readonly_sql("WITH normal AS (SELECT id, username FROM users) SELECT * FROM normal")[0])
        self.assertTrue(validate_readonly_sql("PRAGMA query_only")[0])
        self.assertTrue(validate_readonly_sql("SET TRANSACTION READ ONLY")[0])
        self.assertTrue(validate_readonly_sql("EXPLAIN SELECT count(*) FROM hostels")[0])
        self.assertTrue(validate_readonly_sql("SHOW search_path")[0])

        # 2. Leading multi-line comments before write commands
        safe, reason = validate_readonly_sql("/* audit bypass */ INSERT INTO users (username) VALUES ('test')")
        self.assertFalse(safe)

        # 3. Leading single-line comments before write commands
        safe, reason = validate_readonly_sql("-- leading comment\nDELETE FROM users")
        self.assertFalse(safe)
        safe, reason = validate_readonly_sql("# bash style comment\nUPDATE users SET role='admin'")
        self.assertFalse(safe)

        # 4. Multi-statement SQL
        safe, reason = validate_readonly_sql("SELECT 1; DROP TABLE users")
        self.assertFalse(safe)
        self.assertIn("Multi-statement", reason)
        safe, reason = validate_readonly_sql("SELECT 1; SELECT 2;")
        self.assertFalse(safe)
        self.assertIn("Multi-statement", reason)

        # 5. Data-modifying CTEs
        safe, reason = validate_readonly_sql("WITH updated AS (UPDATE users SET is_active=false RETURNING *) SELECT * FROM updated")
        self.assertFalse(safe)
        self.assertIn("Data-modifying CTE", reason)

        safe, reason = validate_readonly_sql("WITH ins AS (INSERT INTO users (username) VALUES ('test') RETURNING *) SELECT * FROM ins")
        self.assertFalse(safe)
        self.assertIn("Data-modifying CTE", reason)

        safe, reason = validate_readonly_sql("WITH del AS (DELETE FROM users RETURNING *) SELECT * FROM del")
        self.assertFalse(safe)
        self.assertIn("Data-modifying CTE", reason)

        # 6. SELECT INTO table creation
        safe, reason = validate_readonly_sql("SELECT * INTO new_table FROM users")
        self.assertFalse(safe)
        self.assertIn("SELECT INTO", reason)

        safe, reason = validate_readonly_sql("SELECT id, username INTO backup_users FROM users WHERE is_active=true")
        self.assertFalse(safe)
        self.assertIn("SELECT INTO", reason)

        # 7. Unexpected or procedural SQL statements
        unexpected_statements = [
            "CALL update_account_status()",
            "EXEC xp_cmdshell('whoami')",
            "EXECUTE custom_proc()",
            "COPY users TO '/tmp/data.csv'",
            "VACUUM FULL users",
            "GRANT ALL PRIVILEGES ON users TO attacker",
            "REVOKE ALL ON users FROM admin",
            "LOCK TABLE users IN EXCLUSIVE MODE",
        ]
        for stmt in unexpected_statements:
            safe, reason = validate_readonly_sql(stmt)
            self.assertFalse(safe, f"Expected '{stmt}' to be rejected as unexpected statement")

        # 8. State-changing PRAGMA statements and attempts to disable query_only (Finding 1)
        disallowed_pragmas = [
            # Assignment syntax disabling query_only
            "PRAGMA query_only = OFF",
            "PRAGMA query_only = 0",
            "PRAGMA query_only=OFF",
            "PRAGMA query_only = false",
            "PRAGMA query_only = NO",
            "/* bypass */ PRAGMA query_only = OFF",
            "-- line comment\nPRAGMA query_only = 0",
            # Function-call syntax disabling query_only
            "PRAGMA query_only(OFF)",
            "PRAGMA query_only(0)",
            "PRAGMA query_only(false)",
            "PRAGMA query_only(NO)",
            "PRAGMA query_only('OFF')",
            "PRAGMA query_only('0')",
            "PRAGMA query_only(\"OFF\")",
            "PRAGMA query_only(\"0\")",
            "/* bypass */ PRAGMA query_only(0)",
            "-- line comment\nPRAGMA query_only(OFF)",
            # Function-call syntax for non-inspection or state-changing pragmas
            "PRAGMA foreign_keys(0)",
            "PRAGMA writable_schema(1)",
            "PRAGMA foreign_keys = OFF",
            "PRAGMA writable_schema = ON",
            "PRAGMA journal_mode = MEMORY",
            "PRAGMA synchronous = OFF",
            "PRAGMA shrink_memory",
            "PRAGMA optimize",
            # Parenthesized args on bare inspection pragmas
            "PRAGMA database_list('illegal_arg')",
            "PRAGMA collation_list(0)",
            "PRAGMA compile_options('test')",
            # Malformed or SQL-injection parenthesized args on table inspection pragmas
            "PRAGMA table_info((SELECT 1))",
            "PRAGMA table_info(users; DROP TABLE users)",
        ]
        for pragma_stmt in disallowed_pragmas:
            safe, reason = validate_readonly_sql(pragma_stmt)
            self.assertFalse(safe, f"Expected '{pragma_stmt}' to be rejected")
            self.assertTrue(
                any(k in reason.lower() for k in ("pragma", "disallowed", "multi-statement", "unauthorized", "arbitrary")),
                f"Unexpected rejection reason for '{pragma_stmt}': {reason}"
            )

        # Disabling forms must specifically report disabling rejection
        disabling_query_only_forms = [
            "PRAGMA query_only = OFF",
            "PRAGMA query_only = 0",
            "PRAGMA query_only = false",
            "PRAGMA query_only = NO",
            "PRAGMA query_only(OFF)",
            "PRAGMA query_only(0)",
            "PRAGMA query_only(false)",
            "PRAGMA query_only(NO)",
            "PRAGMA query_only('OFF')",
            "PRAGMA query_only('0')",
        ]
        for pragma_stmt in disabling_query_only_forms:
            safe, reason = validate_readonly_sql(pragma_stmt)
            self.assertFalse(safe)
            self.assertIn("disabling", reason.lower())

        # Exact initialization statements permitted
        self.assertTrue(validate_readonly_sql("PRAGMA query_only = ON")[0])
        self.assertTrue(validate_readonly_sql("PRAGMA query_only = 1")[0])
        self.assertTrue(validate_readonly_sql("PRAGMA query_only")[0])
        self.assertTrue(validate_readonly_sql("PRAGMA table_info(users)")[0])
        self.assertTrue(validate_readonly_sql("PRAGMA table_info('users')")[0])
        self.assertTrue(validate_readonly_sql("PRAGMA index_list(users)")[0])
        self.assertTrue(validate_readonly_sql("PRAGMA foreign_key_list(users)")[0])
        self.assertTrue(validate_readonly_sql("PRAGMA database_list")[0])
        self.assertTrue(validate_readonly_sql("PRAGMA collation_list")[0])
        self.assertTrue(validate_readonly_sql("PRAGMA compile_options")[0])

        # 9. Arbitrary session-setting statements rejected; exact SET TRANSACTION READ ONLY permitted
        self.assertTrue(validate_readonly_sql("SET TRANSACTION READ ONLY")[0])
        self.assertTrue(validate_readonly_sql("set transaction read only")[0])
        self.assertTrue(validate_readonly_sql("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE READ ONLY")[0])

        disallowed_sets = [
            "SET session_replication_role = 'replica'",
            "SET search_path TO public",
            "SET work_mem = '64MB'",
            "SET client_min_messages = 'error'",
            "SET autocommit = 1",
            "/* comment */ SET role = 'superuser'",
        ]
        for set_stmt in disallowed_sets:
            safe, reason = validate_readonly_sql(set_stmt)
            self.assertFalse(safe, f"Expected '{set_stmt}' to be rejected as arbitrary SET")
            self.assertIn("Arbitrary session-setting", reason)

        # 10. Transaction-control statements rejected in cursor execution
        tx_control_stmts = ["BEGIN", "BEGIN TRANSACTION", "COMMIT", "ROLLBACK"]
        for tx_stmt in tx_control_stmts:
            safe, reason = validate_readonly_sql(tx_stmt)
            self.assertFalse(safe, f"Expected '{tx_stmt}' to be rejected as transaction control")
            self.assertIn("Transaction control statement", reason)

    def test_rejected_statement_error_message_sanitization_zero_excerpts(self):
        """Verifies that rejected statement error messages never interpolate SQL statement excerpts or parameters."""
        from sqlalchemy import text
        from migrate_demo_accounts_prod import configure_read_only_preflight_guards

        test_app = create_app('testing')
        with test_app.app_context():
            cleanup = configure_read_only_preflight_guards(db.engine)
            try:
                secret_param = "SUPER_SECRET_TOKEN_DO_NOT_LEAK_123"
                malicious_sql = f"INSERT INTO users (username) VALUES ('{secret_param}')"
                with self.assertRaises(RuntimeError) as ctx:
                    db.session.execute(text(malicious_sql))
                err_msg = str(ctx.exception)
                self.assertNotIn(secret_param, err_msg)
                self.assertNotIn("INSERT INTO", err_msg)
                self.assertIn("PREFLIGHT SAFETY VIOLATION", err_msg)
            finally:
                cleanup()

    def test_run_production_preflight_initialization_failure_restores_database_url(self):
        """Verifies that run_production_preflight restores DATABASE_URL even if target validation fails."""
        import os
        from migrate_demo_accounts_prod import run_production_preflight

        orig_db_url = "postgresql+psycopg2://orig_user:pass@remote:5432/orig_db"
        os.environ['DATABASE_URL'] = orig_db_url

        try:
            # Invalid URL will fail validate_production_target during initialization
            with self.assertRaises(ValueError):
                run_production_preflight(db_url="sqlite:///invalid_target.db")
            # Must be restored to orig_db_url
            self.assertEqual(os.environ.get('DATABASE_URL'), orig_db_url)
        finally:
            os.environ.pop('DATABASE_URL', None)

        # When previously absent
        os.environ.pop('DATABASE_URL', None)
        with self.assertRaises(ValueError):
            run_production_preflight(db_url="sqlite:///invalid_target.db")
        self.assertNotIn('DATABASE_URL', os.environ)

    def test_sqlite_query_only_lifecycle_restoration_and_listener_cleanup(self):
        """Verifies tracked SQLite DBAPI query-only restoration, detectable restoration failures, and finally cleanup."""
        from sqlalchemy import text, create_engine
        from unittest.mock import MagicMock
        from migrate_demo_accounts_prod import configure_read_only_preflight_guards

        test_app = create_app('testing')
        with test_app.app_context():
            cleanup_guards = configure_read_only_preflight_guards(db.engine)
            try:
                # Query-only must be 1 during preflight
                q_active = db.session.execute(text("PRAGMA query_only")).scalar()
                self.assertIn(q_active, (1, "1"))
            finally:
                cleanup_guards()

            # Query-only must be restored to 0 after cleanup
            q_restored = db.session.execute(text("PRAGMA query_only")).scalar()
            self.assertIn(q_restored, (0, "0"))

            # Write operations must succeed after cleanup
            db.session.execute(text("CREATE TABLE temp_lifecycle_check (id INT)"))
            db.session.execute(text("INSERT INTO temp_lifecycle_check VALUES (42)"))
            val = db.session.execute(text("SELECT id FROM temp_lifecycle_check")).scalar()
            self.assertEqual(val, 42)
            db.session.execute(text("DROP TABLE temp_lifecycle_check"))

        # Verify that if restoration fails on a raw connection, RuntimeError is raised and detectable
        mock_engine = create_engine("sqlite:///:memory:")
        cleanup_fail_test = configure_read_only_preflight_guards(mock_engine)
        broken_dbapi = MagicMock()
        broken_cursor = MagicMock()
        broken_cursor.fetchone.return_value = (1,)  # Still 1: restoration failed!
        broken_dbapi.cursor.return_value = broken_cursor

        # Inject into tracked raw connections
        cleanup_cell = [c for c in cleanup_fail_test.__closure__ if isinstance(c.cell_contents, set)]
        if cleanup_cell:
            cleanup_cell[0].cell_contents.add(broken_dbapi)
            with self.assertRaises(RuntimeError) as ctx:
                cleanup_fail_test()
            self.assertIn("verification failed", str(ctx.exception))

    def test_postgresql_read_only_setup_failure_aborts_preflight(self):
        """Verifies that triggering SQLAlchemy begin event simulates SET TRANSACTION READ ONLY failure, propagates, and aborts preflight."""
        import io
        import sys
        from sqlalchemy import create_engine
        from migrate_demo_accounts_prod import configure_read_only_preflight_guards, run_production_preflight

        # 1. Direct engine begin event verification
        # Attach read-only preflight guards to an engine, patch dialect to postgresql,
        # and verify that with engine.begin() triggers the event, executes SET TRANSACTION READ ONLY,
        # catches the DBAPI syntax error on non-Postgres, and propagates RuntimeError.
        engine = create_engine("sqlite:///:memory:")
        cleanup = configure_read_only_preflight_guards(engine)
        engine.dialect.name = "postgresql"
        try:
            with self.assertRaises(RuntimeError) as ctx:
                with engine.begin() as conn:
                    pass
            self.assertIn("Failed to set PostgreSQL transaction to READ ONLY mode", str(ctx.exception))
        finally:
            engine.dialect.name = "sqlite"
            cleanup()

        # 2. Verify that preflight application inspection immediately aborts and returns success=False
        test_app = create_app('testing')
        with test_app.app_context():
            orig_name = db.engine.dialect.name
            db.engine.dialect.name = "postgresql"
            old_stdout = sys.stdout
            sys.stdout = io.StringIO()
            try:
                res = run_production_preflight(app=test_app)
            finally:
                sys.stdout = old_stdout
                db.engine.dialect.name = orig_name

            self.assertFalse(res.get("success"))
            self.assertIn("read-only", res.get("error", "").lower())

    def test_preflight_app_never_invokes_schema_migrations_or_ddl(self):
        """Verifies that create_preflight_app strictly inhibits _ensure_schema_migrations, db.create_all, and DDL."""
        import secrets
        from unittest.mock import patch
        import app

        valid_prod_secret = secrets.token_hex(32)
        with patch('app._ensure_schema_migrations') as mock_migrations, \
             patch('app.models.db.create_all') as mock_create_all, \
             patch.dict('os.environ', {'SECRET_KEY': valid_prod_secret}):
            # 1. Testing preflight app
            preflight_test = app.create_preflight_app("testing")
            mock_migrations.assert_not_called()
            mock_create_all.assert_not_called()
            self.assertTrue(preflight_test.config.get('PREFLIGHT_MODE'))

            # 2. Production preflight app (with mock database URL)
            preflight_prod = app.create_preflight_app("production", db_url="postgresql+psycopg2://user:pass@localhost:5432/hostel_db")
            mock_migrations.assert_not_called()
            mock_create_all.assert_not_called()
            self.assertTrue(preflight_prod.config.get('PREFLIGHT_MODE'))

    def test_create_preflight_app_environment_database_url_restoration_lifecycle(self):
        """Verifies that create_preflight_app strictly restores os.environ['DATABASE_URL'] under all conditions."""
        import os
        import secrets
        import app
        from unittest.mock import patch

        valid_prod_secret = secrets.token_hex(32)
        target_test_url = "postgresql+psycopg2://temp_preflight:pass@localhost:5432/preflight_db"
        orig_val = "postgresql+psycopg2://existing_user:pass@remote:5432/existing_db"

        # Case 1: Existing DATABASE_URL is restored
        os.environ['DATABASE_URL'] = orig_val
        try:
            with patch.dict('os.environ', {'SECRET_KEY': valid_prod_secret}):
                preflight_prod = app.create_preflight_app("production", db_url=target_test_url)
            # Environment variable must be restored to its original value
            self.assertEqual(os.environ.get('DATABASE_URL'), orig_val)
            # Captured URI in returned app configuration is preserved
            self.assertEqual(preflight_prod.config.get('SQLALCHEMY_DATABASE_URI'), target_test_url)
        finally:
            os.environ.pop('DATABASE_URL', None)

        # Case 2: Previously absent DATABASE_URL is removed
        os.environ.pop('DATABASE_URL', None)
        with patch.dict('os.environ', {'SECRET_KEY': valid_prod_secret}):
            preflight_prod2 = app.create_preflight_app("production", db_url=target_test_url)
        self.assertNotIn('DATABASE_URL', os.environ)
        self.assertEqual(preflight_prod2.config.get('SQLALCHEMY_DATABASE_URI'), target_test_url)

        # Case 3: Environment restored when create_app raises an exception (with existing URL)
        os.environ['DATABASE_URL'] = orig_val
        try:
            with patch('app.create_app', side_effect=RuntimeError("Simulated app creation crash")):
                with self.assertRaises(RuntimeError):
                    app.create_preflight_app("testing", db_url=target_test_url)
            self.assertEqual(os.environ.get('DATABASE_URL'), orig_val)
        finally:
            os.environ.pop('DATABASE_URL', None)

        # Case 4: Environment restored when create_app raises an exception (with absent URL)
        os.environ.pop('DATABASE_URL', None)
        with patch('app.create_app', side_effect=RuntimeError("Simulated app creation crash")):
            with self.assertRaises(RuntimeError):
                app.create_preflight_app("testing", db_url=target_test_url)
        self.assertNotIn('DATABASE_URL', os.environ)

    def test_intended_accounts_identities_and_emails(self):
        """Verifies that INTENDED_ACCOUNTS contains exactly the eight specified accounts and correct emails."""
        from migrate_demo_accounts_prod import INTENDED_ACCOUNTS

        expected_accounts = {
            "admin": {"role": "admin", "email": "admin@aktu-hostel.edu.in"},
            "guard_main": {"role": "security", "email": "guard.main@aktu-hostel.edu.in"},
            "mess_manager": {"role": "mess_manager", "email": "manager.mess@aktu-hostel.edu.in"},
            "warden_boys": {"role": "warden", "email": "warden.boys@aktu-hostel.edu.in"},
            "warden_girls": {"role": "warden", "email": "warden.girls@aktu-hostel.edu.in"},
            "rahul_sharma": {"role": "student", "email": "rahul.cse@aktu.ac.in"},
            "parent_rahul": {"role": "parent", "email": "ramesh.sharma@parent.aktu.ac.in"},
            "mess_staff": {"role": "mess_staff", "email": "staff.counter@aktu-hostel.edu.in"},
        }

        self.assertEqual(len(INTENDED_ACCOUNTS), 8)
        self.assertEqual(len(expected_accounts), 8)

        actual_usernames = [a["username"] for a in INTENDED_ACCOUNTS]
        self.assertEqual(len(set(actual_usernames)), 8)
        self.assertEqual(set(actual_usernames), set(expected_accounts.keys()))

        for account in INTENDED_ACCOUNTS:
            u = account["username"]
            expected = expected_accounts[u]
            self.assertEqual(account["role"], expected["role"], f"Role mismatch for {u}")
            self.assertEqual(account["email"], expected["email"], f"Email mismatch for {u}")

    def test_sqlite_uri_parsing_error_sanitization_zero_raw_exc(self):
        """Verifies verify_test_database_isolation SQLite URI parsing error reports exception class name without raw exc."""
        from app import verify_test_database_isolation
        from flask import Flask
        from unittest.mock import patch

        fake_app = Flask('fake_test_app')
        fake_app.config['TESTING'] = True
        fake_app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///test_file.db'

        with patch('sqlalchemy.engine.url.make_url', side_effect=ValueError("Raw sensitive message: password='secret'")):
            with self.assertRaises(RuntimeError) as ctx:
                verify_test_database_isolation(fake_app, allow_temp_file_sqlite=True)
            err_msg = str(ctx.exception)
            self.assertIn("[ValueError]", err_msg)
            self.assertNotIn("Raw sensitive message", err_msg)
            self.assertNotIn("secret", err_msg)

    def test_database_url_validation_secret_query_params_never_leaked(self):
        """Verifies validate_production_target never leaks secret query parameter names or values in exceptions."""
        from migrate_demo_accounts_prod import validate_production_target

        secret_token = "SUPER_SECRET_LEAK_TOKEN_DO_NOT_EXPOSE_98765"
        leaking_urls = [
            f"postgresql://postgres.yjhapstttgilcbaxbbce:validPass123@aws-0-ap-south-1.pooler.supabase.com:6543/postgres?sslmode=require&token={secret_token}",
            f"postgresql://postgres.yjhapstttgilcbaxbbce:validPass123@aws-0-ap-south-1.pooler.supabase.com:6543/postgres?{secret_token}=malicious",
            f"postgresql://postgres.yjhapstttgilcbaxbbce:validPass123@aws-0-ap-south-1.pooler.supabase.com:6543/postgres?sslmode={secret_token}",
        ]
        for url in leaking_urls:
            with self.assertRaises(ValueError) as ctx:
                validate_production_target(url)
            err_msg = str(ctx.exception)
            self.assertNotIn(secret_token, err_msg)
            self.assertIn("SECURITY ERROR", err_msg)

    def test_run_production_preflight_session_remove_and_guards_cleanup_lifecycle_failures(self):
        """Verifies that preflight cleanup records db.session.remove and guards_cleanup failures, restores DATABASE_URL, and raises."""
        import os
        from unittest.mock import patch, MagicMock
        from migrate_demo_accounts_prod import run_production_preflight

        had_env_db_url = 'DATABASE_URL' in os.environ
        orig_env_db_url = os.environ.get('DATABASE_URL')

        test_db = "postgresql+psycopg2://keeper:pass@127.0.0.1:5432/keeper_db"
        os.environ['DATABASE_URL'] = test_db
        try:
            # 1. db.session.remove failure must not be swallowed; DATABASE_URL must be restored
            mock_app = create_app('testing')
            with patch('migrate_demo_accounts_prod.db.session.remove', side_effect=RuntimeError("Simulated session remove error")):
                with self.assertRaises(RuntimeError) as ctx:
                    run_production_preflight(app=mock_app)
                self.assertIn("PREFLIGHT CLEANUP FAILURE", str(ctx.exception))
                self.assertIn("db.session.remove failure [RuntimeError]", str(ctx.exception))
                self.assertEqual(os.environ.get('DATABASE_URL'), test_db)

            # 2. guards_cleanup failure must be recorded; DATABASE_URL must be restored
            with patch('migrate_demo_accounts_prod.configure_read_only_preflight_guards') as mock_cfg:
                broken_cleanup = MagicMock(side_effect=RuntimeError("Simulated guards cleanup error"))
                mock_cfg.return_value = broken_cleanup
                with self.assertRaises(RuntimeError) as ctx:
                    run_production_preflight(app=mock_app)
                self.assertIn("PREFLIGHT CLEANUP FAILURE", str(ctx.exception))
                self.assertIn("guards_cleanup failure [RuntimeError]", str(ctx.exception))
                self.assertEqual(os.environ.get('DATABASE_URL'), test_db)
        finally:
            try:
                db.session.execute(db.text("PRAGMA query_only = OFF"))
            except Exception:
                pass
            if had_env_db_url:
                os.environ['DATABASE_URL'] = orig_env_db_url
            else:
                os.environ.pop('DATABASE_URL', None)

    def test_postgresql_urls_with_encoded_passwords(self):
        """Verifies normalization, masking, and validation of PostgreSQL URLs with encoded passwords."""
        from app.config import Config, normalize_database_url, mask_database_url

        orig_env_db_url = os.environ.get('DATABASE_URL')
        orig_cls_db_url = getattr(Config, 'DATABASE_URL', None)
        try:
            # URL with URL-encoded special characters (%40 for @, %3A for :, %23 for #)
            encoded_url = "postgresql://dbuser:p%40ss%3Aw%23rd@dbhost:5432/dbname"
            normalized = normalize_database_url(encoded_url)
            self.assertEqual(normalized, "postgresql+psycopg2://dbuser:p%40ss%3Aw%23rd@dbhost:5432/dbname")

            # Verify Config.get_database_uri accepts it
            os.environ['DATABASE_URL'] = encoded_url
            Config.DATABASE_URL = None
            uri = Config.get_database_uri(default_to_sqlite=False)
            self.assertEqual(uri, "postgresql+psycopg2://dbuser:p%40ss%3Aw%23rd@dbhost:5432/dbname")

            # Verify password is masked in mask_database_url
            masked = mask_database_url(encoded_url)
            self.assertNotIn("p%40ss%3Aw%23rd", masked)
            self.assertIn("dbuser:***@dbhost:5432/dbname", masked)
        finally:
            if orig_env_db_url is not None:
                os.environ['DATABASE_URL'] = orig_env_db_url
            else:
                os.environ.pop('DATABASE_URL', None)
            Config.DATABASE_URL = orig_cls_db_url

    def test_urls_containing_query_parameters(self):
        """Verifies normalization, preservation, and sensitive parameter masking of URLs with query params."""
        from app.config import Config, normalize_database_url, mask_database_url

        orig_env_db_url = os.environ.get('DATABASE_URL')
        orig_cls_db_url = getattr(Config, 'DATABASE_URL', None)
        try:
            url_with_params = "postgresql://user:pass@host:5432/db?sslmode=require&connect_timeout=10&application_name=hms"
            normalized = normalize_database_url(url_with_params)
            self.assertTrue(normalized.startswith("postgresql+psycopg2://"))
            self.assertIn("sslmode=require", normalized)
            self.assertIn("connect_timeout=10", normalized)
            self.assertIn("application_name=hms", normalized)

            os.environ['DATABASE_URL'] = url_with_params
            Config.DATABASE_URL = None
            uri = Config.get_database_uri(default_to_sqlite=False)
            self.assertIn("sslmode=require", uri)
            self.assertIn("connect_timeout=10", uri)

            # Sensitive query parameter masking
            secret_token = "SUPER_SECRET_TOKEN_DO_NOT_EXPOSE_ABC"
            url_with_secret = f"postgresql://user:pass@host:5432/db?sslmode=require&token={secret_token}&api_key=SECRET999"
            masked = mask_database_url(url_with_secret)
            self.assertNotIn(secret_token, masked)
            self.assertNotIn("SECRET999", masked)
            self.assertIn("token=***", masked)
            self.assertIn("api_key=***", masked)
            self.assertIn("sslmode=require", masked)
        finally:
            if orig_env_db_url is not None:
                os.environ['DATABASE_URL'] = orig_env_db_url
            else:
                os.environ.pop('DATABASE_URL', None)
            Config.DATABASE_URL = orig_cls_db_url

    def test_invalid_pool_size_and_overflow_environment_values(self):
        """Verifies DB_POOL_SIZE and DB_MAX_OVERFLOW validate positive integers and reject invalid values with sanitized errors."""
        from app.config import ProductionConfig, validate_pool_setting

        orig_pool = os.environ.get('DB_POOL_SIZE')
        orig_overflow = os.environ.get('DB_MAX_OVERFLOW')
        orig_vercel = os.environ.get('VERCEL')
        orig_lambda = os.environ.get('AWS_LAMBDA_FUNCTION_NAME')

        try:
            os.environ.pop('VERCEL', None)
            os.environ.pop('AWS_LAMBDA_FUNCTION_NAME', None)

            # 1. Invalid DB_POOL_SIZE values: non-integer, negative, zero
            for invalid_val in ('abc', '-5', '0', '  ', '3.14'):
                os.environ['DB_POOL_SIZE'] = invalid_val
                with self.assertRaises(ValueError) as ctx:
                    _ = ProductionConfig.SQLALCHEMY_ENGINE_OPTIONS
                self.assertIn("CRITICAL PRODUCTION CONFIGURATION ERROR", str(ctx.exception))
                self.assertIn("Invalid DB_POOL_SIZE", str(ctx.exception))
                self.assertNotIn(invalid_val, str(ctx.exception))

            # 2. Invalid DB_MAX_OVERFLOW values: non-integer, negative (note: 0 is allowed)
            os.environ['DB_POOL_SIZE'] = '5'
            for invalid_val in ('xyz', '-1', '-10', '  ', '2.5'):
                os.environ['DB_MAX_OVERFLOW'] = invalid_val
                with self.assertRaises(ValueError) as ctx:
                    _ = ProductionConfig.SQLALCHEMY_ENGINE_OPTIONS
                self.assertIn("CRITICAL PRODUCTION CONFIGURATION ERROR", str(ctx.exception))
                self.assertIn("Invalid DB_MAX_OVERFLOW", str(ctx.exception))
                self.assertNotIn(invalid_val, str(ctx.exception))

            # 3. Valid positive integers, including DB_MAX_OVERFLOW=0
            os.environ['DB_POOL_SIZE'] = '15'
            os.environ['DB_MAX_OVERFLOW'] = '0'
            opts = ProductionConfig.SQLALCHEMY_ENGINE_OPTIONS
            self.assertEqual(opts['pool_size'], 15)
            self.assertEqual(opts['max_overflow'], 0)

            os.environ['DB_MAX_OVERFLOW'] = '25'
            opts = ProductionConfig.SQLALCHEMY_ENGINE_OPTIONS
            self.assertEqual(opts['pool_size'], 15)
            self.assertEqual(opts['max_overflow'], 25)
            self.assertEqual(opts['pool_recycle'], 300)
            self.assertTrue(opts['pool_pre_ping'])
        finally:
            if orig_pool is not None:
                os.environ['DB_POOL_SIZE'] = orig_pool
            else:
                os.environ.pop('DB_POOL_SIZE', None)
            if orig_overflow is not None:
                os.environ['DB_MAX_OVERFLOW'] = orig_overflow
            else:
                os.environ.pop('DB_MAX_OVERFLOW', None)
            if orig_vercel is not None:
                os.environ['VERCEL'] = orig_vercel
            else:
                os.environ.pop('VERCEL', None)
            if orig_lambda is not None:
                os.environ['AWS_LAMBDA_FUNCTION_NAME'] = orig_lambda
            else:
                os.environ.pop('AWS_LAMBDA_FUNCTION_NAME', None)

    def test_verify_test_database_isolation_error_messages_contain_no_paths_or_uris(self):
        """
        Verifies that verify_test_database_isolation error messages do not leak raw URIs, credentials,
        hostnames, database names, matched forbidden names, or filesystem paths across all failure modes:
        1. PostgreSQL / Supabase remote URI rejection
        2. Sensitive file-backed SQLite path rejection (default rejection)
        3. Forbidden application database filename inside an authorized temporary directory
        4. Temporary directory boundary containment violation
        """
        import tempfile
        import shutil
        from app import verify_test_database_isolation
        from flask import Flask

        app = Flask('leak_check_app')
        app.config['TESTING'] = True

        # 1. PostgreSQL / Supabase URI rejection
        sensitive_user = 'super_admin_user_x'
        sensitive_pass = 'super_secret_pw_999'
        sensitive_host = 'aws-0-ap-south-1.pooler.supabase.com'
        sensitive_db = 'prod_customer_database'
        sensitive_pg_uri = f'postgresql+psycopg2://{sensitive_user}:{sensitive_pass}@{sensitive_host}:6543/{sensitive_db}'
        app.config['SQLALCHEMY_DATABASE_URI'] = sensitive_pg_uri

        with self.assertRaises(RuntimeError) as ctx:
            verify_test_database_isolation(app)
        err1 = str(ctx.exception)
        self.assertIn("Remote or shared database configuration detected", err1)
        self.assertNotIn(sensitive_user, err1)
        self.assertNotIn(sensitive_pass, err1)
        self.assertNotIn(sensitive_host, err1)
        self.assertNotIn(sensitive_db, err1)
        self.assertNotIn('supabase', err1)
        self.assertNotIn('postgresql', err1)
        self.assertNotIn('6543', err1)

        # 2. Sensitive SQLite path rejection (default file-backed rejection)
        sensitive_vault_path = 'C:/very/private/customer_vault/confidential_store.sqlite'
        app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{sensitive_vault_path}'
        with self.assertRaises(RuntimeError) as ctx:
            verify_test_database_isolation(app, allow_temp_file_sqlite=False)
        err2 = str(ctx.exception)
        self.assertIn("File-backed SQLite URI is strictly rejected by default", err2)
        self.assertNotIn('customer_vault', err2)
        self.assertNotIn('confidential_store', err2)
        self.assertNotIn('private', err2)
        self.assertNotIn(sensitive_vault_path, err2)

        # Create temporary directory for containment tests
        temp_dir = tempfile.mkdtemp(prefix='hms_leak_test_')
        try:
            # 3. Forbidden application database filename inside authorized temporary directory
            forbidden_filename = 'hostel_management.db'
            forbidden_db_path = os.path.join(temp_dir, forbidden_filename).replace('\\', '/')
            app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{forbidden_db_path}'
            with self.assertRaises(RuntimeError) as ctx:
                verify_test_database_isolation(app, allow_temp_file_sqlite=True, temp_dir=temp_dir)
            err3 = str(ctx.exception)
            self.assertIn("Application or development database", err3)
            self.assertNotIn(forbidden_filename, err3)
            self.assertNotIn(temp_dir, err3)
            self.assertNotIn(forbidden_db_path, err3)

            # 4. Temporary-directory boundary rejection (path outside authorized temp dir)
            outside_db_path = 'C:/system_root/outside_boundary_data.db'
            app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{outside_db_path}'
            with self.assertRaises(RuntimeError) as ctx:
                verify_test_database_isolation(app, allow_temp_file_sqlite=True, temp_dir=temp_dir)
            err4 = str(ctx.exception)
            self.assertIn("File-backed SQLite database path is not inside the dedicated temporary directory", err4)
            self.assertNotIn('outside_boundary_data', err4)
            self.assertNotIn('system_root', err4)
            self.assertNotIn(temp_dir, err4)
            self.assertNotIn(outside_db_path, err4)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_mask_database_url_encoded_query_parameter_names(self):
        """Verifies that mask_database_url() decodes and normalizes encoded query parameter names to mask secrets."""
        from app.config import mask_database_url

        # 1. URL with various percent-encoded sensitive query parameter names
        secret_val_1 = "SUPER_SECRET_API_KEY_123"
        secret_val_2 = "TOP_SECRET_JWT_TOKEN_ABC"
        secret_val_3 = "PRIVATE_PASSWORD_999"
        secret_val_4 = "CONFIDENTIAL_KEY_XYZ"

        test_url = (
            f"postgresql://dbuser:mypass@dbhost:5432/dbname?"
            f"sslmode=require&"
            f"api%5Fkey={secret_val_1}&"
            f"t%6Fken={secret_val_2}&"
            f"p%61ssword={secret_val_3}&"
            f"auth%2Dtoken={secret_val_4}&"
            f"connect_timeout=10&"
            f"application_name=hms"
        )
        masked = mask_database_url(test_url)

        # Sensitive parameter values must be redacted
        self.assertNotIn(secret_val_1, masked)
        self.assertNotIn(secret_val_2, masked)
        self.assertNotIn(secret_val_3, masked)
        self.assertNotIn(secret_val_4, masked)

        # Passwords must be masked
        self.assertNotIn("mypass", masked)
        self.assertIn("dbuser:***@dbhost:5432/dbname", masked)

        # Sensitive parameter keys must be masked with ***
        self.assertIn("api%5Fkey=***", masked)
        self.assertIn("t%6Fken=***", masked)
        self.assertIn("p%61ssword=***", masked)
        self.assertIn("auth%2Dtoken=***", masked)

        # Non-sensitive parameters must be preserved
        self.assertIn("sslmode=require", masked)
        self.assertIn("connect_timeout=10", masked)
        self.assertIn("application_name=hms", masked)

        # 2. Uppercase and mixed-case percent encoding
        test_url_upper = f"postgresql://user:pass@host:5432/db?API%5FKEY=SECRET_VAL&SEC%72ET=CONF_VAL"
        masked_upper = mask_database_url(test_url_upper)
        self.assertNotIn("SECRET_VAL", masked_upper)
        self.assertNotIn("CONF_VAL", masked_upper)
        self.assertIn("API%5FKEY=***", masked_upper)
        self.assertIn("SEC%72ET=***", masked_upper)

    def test_serverless_nullpool_configuration(self):
        """Verifies serverless production configuration uses SQLAlchemy NullPool when VERCEL or AWS_LAMBDA is set."""
        from sqlalchemy.pool import NullPool
        from app.config import ProductionConfig

        orig_vercel = os.environ.get('VERCEL')
        orig_lambda = os.environ.get('AWS_LAMBDA_FUNCTION_NAME')
        try:
            # Case A: VERCEL is set
            os.environ['VERCEL'] = '1'
            os.environ.pop('AWS_LAMBDA_FUNCTION_NAME', None)
            self.assertTrue(ProductionConfig.is_serverless)
            opts_vercel = ProductionConfig.SQLALCHEMY_ENGINE_OPTIONS
            self.assertIs(opts_vercel.get('poolclass'), NullPool)
            self.assertTrue(opts_vercel.get('pool_pre_ping'))

            # Case B: AWS_LAMBDA_FUNCTION_NAME is set
            os.environ.pop('VERCEL', None)
            os.environ['AWS_LAMBDA_FUNCTION_NAME'] = 'hms-production-lambda'
            self.assertTrue(ProductionConfig.is_serverless)
            opts_lambda = ProductionConfig.SQLALCHEMY_ENGINE_OPTIONS
            self.assertIs(opts_lambda.get('poolclass'), NullPool)

            # Case C: Non-serverless environment
            os.environ.pop('VERCEL', None)
            os.environ.pop('AWS_LAMBDA_FUNCTION_NAME', None)
            self.assertFalse(ProductionConfig.is_serverless)
            opts_standard = ProductionConfig.SQLALCHEMY_ENGINE_OPTIONS
            self.assertNotIn('poolclass', opts_standard)
            self.assertEqual(opts_standard['pool_size'], 5)
            self.assertEqual(opts_standard['max_overflow'], 10)
        finally:
            if orig_vercel is not None:
                os.environ['VERCEL'] = orig_vercel
            else:
                os.environ.pop('VERCEL', None)
            if orig_lambda is not None:
                os.environ['AWS_LAMBDA_FUNCTION_NAME'] = orig_lambda
            else:
                os.environ.pop('AWS_LAMBDA_FUNCTION_NAME', None)

    def test_development_mysql_and_sqlite_fallback(self):
        """Verifies development environment safely falls back to explicitly configured MySQL or local SQLite."""
        from app.config import Config

        orig_env_db_url = os.environ.get('DATABASE_URL')
        orig_cls_db_url = getattr(Config, 'DATABASE_URL', None)
        orig_mysql_pwd = Config.MYSQL_PASSWORD
        try:
            os.environ.pop('DATABASE_URL', None)
            Config.DATABASE_URL = None

            # 1. Configured MySQL with password
            Config.MYSQL_PASSWORD = 'dev_mysql_password'
            dev_mysql_uri = Config.get_database_uri(default_to_sqlite=True)
            self.assertTrue(dev_mysql_uri.startswith('mysql+pymysql://'))
            self.assertIn('dev_mysql_password', dev_mysql_uri)

            # 2. Unconfigured MySQL (empty password) falls back to local SQLite
            Config.MYSQL_PASSWORD = ''
            dev_sqlite_uri = Config.get_database_uri(default_to_sqlite=True)
            self.assertTrue(dev_sqlite_uri.startswith('sqlite:///'))
            self.assertIn('hostel.sqlite3', dev_sqlite_uri)

            # 3. Production strictly forbids both fallbacks
            with self.assertRaises(ValueError) as ctx:
                Config.get_database_uri(default_to_sqlite=False)
            self.assertIn("CRITICAL PRODUCTION CONFIGURATION ERROR", str(ctx.exception))
            self.assertIn("cannot fall back to SQLite", str(ctx.exception))
        finally:
            Config.MYSQL_PASSWORD = orig_mysql_pwd
            if orig_env_db_url is not None:
                os.environ['DATABASE_URL'] = orig_env_db_url
            else:
                os.environ.pop('DATABASE_URL', None)
            Config.DATABASE_URL = orig_cls_db_url

    def test_testing_config_uses_in_memory_sqlite(self):
        """Verifies TestingConfig strictly uses in-memory SQLite and disables CSRF."""
        from app.config import TestingConfig

        self.assertTrue(TestingConfig.TESTING)
        self.assertTrue(TestingConfig.DEBUG)
        self.assertEqual(TestingConfig.SQLALCHEMY_DATABASE_URI, 'sqlite:///:memory:')
        self.assertFalse(TestingConfig.WTF_CSRF_ENABLED)

    # =========================================================================
    # PRODUCTION MIGRATION CLI SAFETY TESTS
    # =========================================================================
    def test_cli_fail_closed_no_args(self):
        """Verifies running the migration script without arguments is fail-closed and exits with code 1."""
        from unittest.mock import patch
        import migrate_demo_accounts_prod

        with patch('migrate_demo_accounts_prod.migrate_demo_accounts') as mock_migrate:
            code = migrate_demo_accounts_prod.main([])
            self.assertEqual(code, 1)
            mock_migrate.assert_not_called()

    def test_cli_requires_explicit_migration_flag(self):
        """Verifies unknown arguments or flags without --execute-production-migration fail closed."""
        from unittest.mock import patch
        import migrate_demo_accounts_prod

        with patch('migrate_demo_accounts_prod.migrate_demo_accounts') as mock_migrate:
            code = migrate_demo_accounts_prod.main(['--invalid-arg'])
            self.assertEqual(code, 1)
            mock_migrate.assert_not_called()

    def test_cli_confirmation_declined_aborts_safely(self):
        """Verifies production migration aborts safely if confirmation is rejected or missing."""
        from unittest.mock import patch
        import migrate_demo_accounts_prod

        with patch('builtins.input', return_value='no'):
            with patch('migrate_demo_accounts_prod.migrate_demo_accounts') as mock_migrate:
                code = migrate_demo_accounts_prod.main(['--execute-production-migration'])
                self.assertEqual(code, 1)
                mock_migrate.assert_not_called()

        with patch('builtins.input', side_effect=EOFError):
            with patch('migrate_demo_accounts_prod.migrate_demo_accounts') as mock_migrate:
                code = migrate_demo_accounts_prod.main(['--execute-production-migration'])
                self.assertEqual(code, 1)
                mock_migrate.assert_not_called()

    def test_cli_confirmation_accepted_proceeds(self):
        """Verifies production migration executes when explicitly confirmed."""
        from unittest.mock import patch
        import migrate_demo_accounts_prod

        with patch('builtins.input', return_value='CONFIRM PRODUCTION MIGRATION'):
            with patch('migrate_demo_accounts_prod.migrate_demo_accounts') as mock_migrate:
                code = migrate_demo_accounts_prod.main(['--execute-production-migration'])
                self.assertEqual(code, 0)
                mock_migrate.assert_called_once_with(rotate_passwords=False)

    def test_cli_confirmation_accepted_with_rotation(self):
        """Verifies rotation flag is passed to migration when confirmed."""
        from unittest.mock import patch
        import migrate_demo_accounts_prod

        with patch('builtins.input', return_value='CONFIRM PRODUCTION MIGRATION'):
            with patch('migrate_demo_accounts_prod.migrate_demo_accounts') as mock_migrate:
                code = migrate_demo_accounts_prod.main(['--execute-production-migration', '--rotate-existing-passwords'])
                self.assertEqual(code, 0)
                mock_migrate.assert_called_once_with(rotate_passwords=True)

    def test_cli_test_flags_do_not_run_migration(self):
        """Verifies test flags only run unit tests and never execute migration."""
        from unittest.mock import patch
        import migrate_demo_accounts_prod

        with patch('migrate_demo_accounts_prod.migrate_demo_accounts') as mock_migrate:
            with patch('migrate_demo_accounts_prod.run_masking_unit_tests', return_value=True):
                with patch('migrate_demo_accounts_prod.run_url_validation_unit_tests', return_value=True):
                    code = migrate_demo_accounts_prod.main(['--test-url'])
                    self.assertEqual(code, 0)
                    mock_migrate.assert_not_called()

    def test_cli_preflight_only_separate_from_migration(self):
        """Verifies --preflight-only runs preflight inspection and never calls migration."""
        from unittest.mock import patch
        import migrate_demo_accounts_prod

        with patch('migrate_demo_accounts_prod.migrate_demo_accounts') as mock_migrate:
            with patch('migrate_demo_accounts_prod.execute_production_preflight', return_value=True) as mock_preflight:
                code = migrate_demo_accounts_prod.main(['--preflight-only'])
                self.assertEqual(code, 0)
                mock_preflight.assert_called_once()
                mock_migrate.assert_not_called()

    # =========================================================================
    # MESSPROFILE HOSTEL_ID CROSS-DATABASE MAPPING TESTS
    # =========================================================================
    def test_resolve_mapped_mess_hostel_id_when_none(self):
        """Verifies that when local mess has hostel_id=None, mapped ID is None."""
        from migrate_demo_accounts_prod import resolve_mapped_mess_hostel_id

        mess_ref = {"mess_name": "Test Mess", "hostel_id": None}
        ref = {"mess": mess_ref}
        mapped_id = resolve_mapped_mess_hostel_id(mess_ref, ref, session=db.session)
        self.assertIsNone(mapped_id)

    def test_resolve_mapped_mess_hostel_id_maps_different_ids(self):
        """Verifies SQLite hostel ID 999 correctly maps to target hostel ID via unique hostel name."""
        from migrate_demo_accounts_prod import resolve_mapped_mess_hostel_id

        # Create hostel with whatever ID the database assigns
        h = Hostel(name="Aryabhatta Boys Hostel (Block A)", hostel_type="boys", total_floors=4, total_rooms=100)
        db.session.add(h)
        db.session.flush()
        target_hostel_id = h.id

        # Construct reference where local SQLite had hostel_id=999
        mess_ref = {
            "mess_name": "Central Dining Hall",
            "hostel_id": 999,
            "mess_hostel_ref": {"name": "Aryabhatta Boys Hostel (Block A)"}
        }
        ref = {"mess": mess_ref, "hostel_boys": {"id": 999, "name": "Aryabhatta Boys Hostel (Block A)"}}

        mapped_id = resolve_mapped_mess_hostel_id(mess_ref, ref, session=db.session)
        self.assertEqual(mapped_id, target_hostel_id)
        self.assertNotEqual(mapped_id, 999)

    def test_resolve_mapped_mess_hostel_id_missing_hostel_aborts(self):
        """Verifies aborting with ValueError when target hostel does not exist in destination DB."""
        from migrate_demo_accounts_prod import resolve_mapped_mess_hostel_id

        # Case A: Reference name resolved, but absent in target database
        mess_ref = {
            "mess_name": "Nonexistent Mess",
            "hostel_id": 42,
            "mess_hostel_ref": {"name": "Nonexistent Hostel Name"}
        }
        ref = {"mess": mess_ref}

        with self.assertRaises(ValueError) as ctx:
            resolve_mapped_mess_hostel_id(mess_ref, ref, session=db.session)
        self.assertIn("No matching PostgreSQL Hostel found", str(ctx.exception))

        # Case B: Reference hostel name cannot even be resolved from ref
        mess_ref_unresolvable = {
            "mess_name": "Unresolvable Mess",
            "hostel_id": 88
        }
        with self.assertRaises(ValueError) as ctx2:
            resolve_mapped_mess_hostel_id(mess_ref_unresolvable, {"mess": mess_ref_unresolvable}, session=db.session)
        self.assertIn("no corresponding reference hostel name could be resolved", str(ctx2.exception))

    def test_resolve_mapped_mess_hostel_id_duplicate_hostel_aborts(self):
        """Verifies aborting with ValueError when multiple hostels share the same name in destination DB."""
        from unittest.mock import patch, MagicMock
        from migrate_demo_accounts_prod import resolve_mapped_mess_hostel_id

        mock_h1 = MagicMock(id=101)
        mock_h2 = MagicMock(id=102)

        mess_ref = {
            "mess_name": "Ambiguous Mess",
            "hostel_id": 1,
            "mess_hostel_ref": {"name": "Ambiguous Hostel"}
        }
        ref = {"mess": mess_ref}

        mock_query = MagicMock()
        mock_query.filter_by.return_value.all.return_value = [mock_h1, mock_h2]
        with patch.object(Hostel, 'query', mock_query):
            with self.assertRaises(ValueError) as ctx:
                resolve_mapped_mess_hostel_id(mess_ref, ref, session=db.session)
            self.assertIn("AMBIGUOUS HOSTEL MAPPING", str(ctx.exception))

    # =========================================================================
    # PASSWORD HANDLING & REDUCTION TESTS
    # =========================================================================
    def test_collect_all_demo_credentials_selective(self):
        """Verifies collect_all_demo_credentials only collects for requested accounts."""
        from migrate_demo_accounts_prod import collect_all_demo_credentials, INTENDED_ACCOUNTS

        # Empty accounts list should return empty dict without prompting
        result_empty = collect_all_demo_credentials(accounts=[])
        self.assertEqual(result_empty, {})

        # Single account with environment variable set
        test_account = [INTENDED_ACCOUNTS[0]]
        uname = test_account[0]["username"]
        env_var = f"DEMO_PASSWORD_{uname.upper()}"
        orig_val = os.environ.get(env_var)
        try:
            os.environ[env_var] = "ValidPass123!@#"
            collected = collect_all_demo_credentials(accounts=test_account)
            self.assertIn(uname, collected)
            self.assertEqual(len(collected), 1)
            self.assertEqual(collected[uname], "ValidPass123!@#")
        finally:
            if orig_val is not None:
                os.environ[env_var] = orig_val
            else:
                os.environ.pop(env_var, None)

    def test_credential_cleanup_clears_memory(self):
        """Verifies cleanup_credential_dictionaries zeroes and clears dictionary entries."""
        from migrate_demo_accounts_prod import cleanup_credential_dictionaries

        d1 = {"admin": "SecretPass123!"}
        d2 = {"warden": "SecretPass456!"}
        cleanup_credential_dictionaries(d1, d2)
        self.assertEqual(len(d1), 0)
        self.assertEqual(len(d2), 0)

if __name__ == '__main__':
    unittest.main()

