import os
from flask import Flask, render_template
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from app.config import config_by_name
from app.models import db, User

# Initialize Extensions
login_manager = LoginManager()
csrf = CSRFProtect()

def create_app(config_name=None):
    """
    Application Factory Pattern for Hostel Management System.
    Configures and assembles all extensions, blueprints, and error handlers.
    """
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'development')

    app = Flask(__name__)
    app.config.from_object(config_by_name.get(config_name, config_by_name['default']))

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

    # Configure Upload Folder & Limits
    upload_folder = os.path.join(app.root_path, 'static', 'uploads', 'leave_documents')
    os.makedirs(upload_folder, exist_ok=True)
    os.makedirs(os.path.join(app.root_path, 'static', 'uploads', 'qrcodes'), exist_ok=True)
    app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'static', 'uploads')
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
        app.logger.error(f"Internal Server Error (500): {error}", exc_info=True)
        return render_template('components/error.html', code=500, message="Internal Server Error: Something went wrong on the server."), 500

    # Ensure database schema is up-to-date (self-healing migration)
    _ensure_schema_migrations(app)

    return app


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
                    if 'actual_departure_time' not in existing_cols:
                        conn.execute(text('ALTER TABLE digital_out_passes ADD COLUMN actual_departure_time DATETIME'))
                        conn.commit()
                    if 'actual_return_time' not in existing_cols:
                        conn.execute(text('ALTER TABLE digital_out_passes ADD COLUMN actual_return_time DATETIME'))
                        conn.commit()
        except Exception as e:
            app.logger.warning(f"Schema self-healing migration note: {e}")

