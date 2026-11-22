from functools import wraps
from flask import flash, redirect, url_for, abort, request
from flask_login import current_user

def role_required(*roles):
    """
    Decorator to restrict view access to specific user roles.
    Usage: @role_required('admin') or @role_required('admin', 'warden')
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                flash('Please log in to access this page.', 'warning')
                return redirect(url_for('auth.login', next=request.url))
            if current_user.role not in roles:
                flash('Unauthorized access: You do not have permission to view this resource.', 'danger')
                return abort(403)
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def admin_required(f):
    """Decorator to restrict access strictly to Admin role"""
    return role_required('admin')(f)

def warden_required(f):
    """Decorator to restrict access to Warden role (or Admin)"""
    return role_required('admin', 'warden')(f)

def student_required(f):
    """Decorator to restrict access to Student role"""
    return role_required('student')(f)

def security_required(f):
    """Decorator to restrict access strictly to Security Guard or Admin"""
    return role_required('admin', 'security')(f)

def guard_or_admin_required(f):
    """Decorator for security staff and administrators"""
    return role_required('admin', 'security')(f)

def parent_required(f):
    """Decorator to restrict access strictly to Parent role"""
    return role_required('parent')(f)


