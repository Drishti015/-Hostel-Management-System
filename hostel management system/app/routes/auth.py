from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from app.models import db, User, Student
from werkzeug.security import check_password_hash

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Unified login for Admin, Warden, and Student"""
    if current_user.is_authenticated:
        if current_user.is_admin:
            return redirect(url_for('admin.dashboard'))
        elif current_user.is_warden:
            return redirect(url_for('warden.dashboard'))
        elif current_user.is_security:
            return redirect(url_for('security.dashboard'))
        elif current_user.is_parent:
            return redirect(url_for('parent.dashboard'))
        return redirect(url_for('student.dashboard'))

    if request.method == 'POST':
        identity = request.form.get('identity', '').strip() # username or email
        password = request.form.get('password', '')
        remember = True if request.form.get('remember') else False

        user = User.query.filter((User.username == identity) | (User.email == identity)).first()

        if user and user.check_password(password):
            if not user.is_active:
                flash('Your account has been deactivated. Please contact the Hostel Administration.', 'danger')
                return redirect(url_for('auth.login'))

            login_user(user, remember=remember)
            flash(f'Welcome back, {user.username}!', 'success')

            # Role-based redirection
            next_page = request.args.get('next')
            if next_page:
                return redirect(next_page)
            if user.is_admin:
                return redirect(url_for('admin.dashboard'))
            elif user.is_warden:
                return redirect(url_for('warden.dashboard'))
            elif user.is_security:
                return redirect(url_for('security.dashboard'))
            elif user.is_parent:
                return redirect(url_for('parent.dashboard'))
            else:
                return redirect(url_for('student.dashboard'))
        else:
            flash('Invalid username/email or password. Please verify your credentials.', 'danger')

    return render_template('auth/login.html')

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """Student Self-Registration Portal"""
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        
        # Student details
        full_name = request.form.get('full_name', '').strip()
        enrollment_no = request.form.get('enrollment_no', '').strip().upper()
        roll_no = request.form.get('roll_no', '').strip()
        phone = request.form.get('phone', '').strip()
        gender = request.form.get('gender', 'male')
        branch = request.form.get('branch', '').strip()
        year = int(request.form.get('year', 1))
        semester = int(request.form.get('semester', 1))
        guardian_name = request.form.get('guardian_name', '').strip()
        guardian_phone = request.form.get('guardian_phone', '').strip()
        emergency_phone = request.form.get('emergency_phone', '').strip()
        address = request.form.get('address', '').strip()
        blood_group = request.form.get('blood_group', '').strip()

        # Validation
        if password != confirm_password:
            flash('Passwords do not match.', 'danger')
            return redirect(url_for('auth.register'))

        if User.query.filter_by(username=username).first():
            flash('Username is already taken. Please choose another.', 'danger')
            return redirect(url_for('auth.register'))

        if User.query.filter_by(email=email).first():
            flash('Email address is already registered. Please login.', 'danger')
            return redirect(url_for('auth.register'))

        if Student.query.filter_by(enrollment_no=enrollment_no).first():
            flash('Enrollment Number is already registered in the system.', 'danger')
            return redirect(url_for('auth.register'))

        try:
            # Atomic transaction to create User and Student profile
            new_user = User(username=username, email=email, role='student')
            new_user.set_password(password)
            db.session.add(new_user)
            db.session.flush() # Generates new_user.id

            new_student = Student(
                user_id=new_user.id,
                enrollment_no=enrollment_no,
                roll_no=roll_no,
                full_name=full_name,
                phone=phone,
                gender=gender,
                branch=branch,
                year=year,
                semester=semester,
                guardian_name=guardian_name,
                guardian_phone=guardian_phone,
                emergency_phone=emergency_phone,
                address=address,
                blood_group=blood_group,
                status='active'
            )
            db.session.add(new_student)
            db.session.commit()

            flash('Registration successful! You can now log in to your student portal.', 'success')
            return redirect(url_for('auth.login'))

        except Exception as e:
            db.session.rollback()
            flash(f'An error occurred during registration: {str(e)}', 'danger')
            return redirect(url_for('auth.register'))

    return render_template('auth/register.html')

@auth_bp.route('/logout')
@login_required
def logout():
    """End User Session"""
    logout_user()
    flash('You have been successfully logged out.', 'info')
    return redirect(url_for('auth.login'))

