import os
from flask import Blueprint, render_template, redirect, url_for, request, abort, current_app, send_from_directory, flash
from flask_login import current_user, login_required
from app.models.notice import Notice
from app.models.hostel import Hostel
from app.models.leave import LeaveApplication
from app.services.notification_service import NotificationService

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    """Public Landing Page"""
    if current_user.is_authenticated:
        if current_user.is_admin:
            return redirect(url_for('admin.dashboard'))
        elif current_user.is_warden:
            return redirect(url_for('warden.dashboard'))
        elif current_user.is_security:
            return redirect(url_for('security.dashboard'))
        else:
            return redirect(url_for('student.dashboard'))
            
    recent_notices = Notice.query.filter(Notice.target_audience.in_(['all', 'boys', 'girls'])).order_by(Notice.created_at.desc()).limit(3).all()
    hostels = Hostel.query.all()
    return render_template('main/index.html', recent_notices=recent_notices, hostels=hostels)

@main_bp.route('/about')
def about():
    """About & Amenities Page"""
    return render_template('main/about.html')

@main_bp.route('/contact')
def contact():
    """Emergency Contacts & Warden Directory"""
    return render_template('main/contact.html')

@main_bp.route('/notifications/mark-read/<int:id>')
@login_required
def mark_notification_read(id):
    """Mark single notification as read and redirect to target resource"""
    from app.models.notification import Notification
    notif = Notification.query.filter_by(id=id, user_id=current_user.id).first_or_404()
    notif.is_read = True
    from app.models import db
    db.session.commit()
    if notif.link:
        return redirect(notif.link)
    return redirect(request.referrer or url_for('main.index'))

@main_bp.route('/notifications/mark-all-read')
@login_required
def mark_all_notifications_read():
    """Mark all unread notifications for current user as read"""
    NotificationService.mark_all_as_read(current_user.id)
    flash('All notifications marked as read.', 'info')
    return redirect(request.referrer or url_for('main.index'))

@main_bp.route('/leaves/document/<filename>')
@login_required
def download_leave_document(filename):
    """Securely serve uploaded leave supporting documents with role-based authorization"""
    leave = LeaveApplication.query.filter_by(supporting_document=filename).first_or_404()
    
    # Authorization checks
    if current_user.is_admin:
        pass
    elif current_user.is_student:
        if not current_user.student_profile or leave.student_id != current_user.student_profile.id:
            abort(403)
    elif current_user.is_warden:
        if current_user.warden_profile and leave.hostel_id and leave.hostel_id != current_user.warden_profile.assigned_hostel_id:
            abort(403)
    else:
        abort(403)
        
    upload_dir = current_app.config.get('UPLOAD_FOLDER', os.path.join(current_app.root_path, 'static', 'uploads', 'leave_documents'))
    return send_from_directory(upload_dir, filename)

