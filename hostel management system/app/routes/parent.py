from datetime import datetime, date
from flask import Blueprint, render_template, redirect, url_for, flash, request, abort, current_app
from flask_login import login_required, current_user
from app.models import db, Student, LeaveApplication, DigitalOutPass, GateTransaction, Attendance, FeeRecord, Notice, Notification, ParentProfile, ParentInquiry, Warden
from app.utils.decorators import parent_required
from app.services.parent_service import ParentService
from app.services.fee_service import FeeService
from app.services.notification_service import NotificationService
from app.forms.parent_forms import ParentInquiryForm

parent_bp = Blueprint('parent', __name__)

def _get_verified_parent_and_child():
    """Helper to verify parent profile and linked child isolation"""
    parent = current_user.parent_profile
    if not parent or not parent.is_active:
        return None, None
    student = parent.student
    return parent, student


@parent_bp.route('/dashboard')
@login_required
@parent_required
def dashboard():
    """Parent Dashboard - Comprehensive resident ward overview"""
    parent, student = _get_verified_parent_and_child()
    if not parent or not student:
        return render_template('parent/unlinked.html', parent=parent)

    dashboard_data = ParentService.get_parent_dashboard_data(parent)
    return render_template('parent/dashboard.html', parent=parent, data=dashboard_data)


@parent_bp.route('/child')
@login_required
@parent_required
def child_profile():
    """Detailed Profile & Residential Particulars of Linked Student"""
    parent, student = _get_verified_parent_and_child()
    if not parent or not student:
        flash('Parent account is not currently linked to an active student record.', 'warning')
        return redirect(url_for('parent.dashboard'))

    allocation = student.current_allocation
    hostel = allocation.hostel if allocation else None
    room = allocation.room if allocation else None
    bed = allocation.bed if allocation else None
    warden = hostel.wardens.first() if (hostel and hostel.wardens) else None

    return render_template('parent/child_profile.html',
                           parent=parent,
                           student=student,
                           allocation=allocation,
                           hostel=hostel,
                           room=room,
                           bed=bed,
                           warden=warden)


@parent_bp.route('/leaves', endpoint='leaves')
@parent_bp.route('/leave-applications', endpoint='leaves_list')
@login_required
@parent_required
def leaves_list():
    """Leave Application Tracking for Linked Student"""
    parent, student = _get_verified_parent_and_child()
    if not parent or not student:
        flash('Linked student record unavailable.', 'warning')
        return redirect(url_for('parent.dashboard'))

    status_filter = request.args.get('status', 'all')
    query = student.leave_applications

    if status_filter in ['Pending', 'Approved', 'Rejected', 'Cancelled']:
        query = query.filter_by(status=status_filter)

    leaves = query.order_by(LeaveApplication.created_at.desc()).all()

    total_count = student.leave_applications.count()
    pending_count = student.leave_applications.filter_by(status='Pending').count()
    approved_count = student.leave_applications.filter_by(status='Approved').count()
    rejected_count = student.leave_applications.filter_by(status='Rejected').count()
    cancelled_count = student.leave_applications.filter_by(status='Cancelled').count()

    return render_template('parent/leaves/list.html',
                           parent=parent,
                           student=student,
                           leaves=leaves,
                           current_filter=status_filter,
                           total_count=total_count,
                           pending_count=pending_count,
                           approved_count=approved_count,
                           rejected_count=rejected_count,
                           cancelled_count=cancelled_count)


@parent_bp.route('/leave-applications/<int:id>')
@login_required
@parent_required
def view_leave(id):
    """Detailed Read-Only View of a Child's Leave Application"""
    parent, student = _get_verified_parent_and_child()
    if not parent or not student:
        abort(403)

    leave = LeaveApplication.query.get_or_404(id)

    # Strict IDOR Access Control
    if leave.student_id != student.id:
        abort(403)

    return render_template('parent/leaves/view.html',
                           parent=parent,
                           student=student,
                           leave=leave)


@parent_bp.route('/outpasses')
@login_required
@parent_required
def outpasses_list():
    """Digital Out-Pass and Real-Time Gate Movement Tracking"""
    parent, student = _get_verified_parent_and_child()
    if not parent or not student:
        flash('Linked student record unavailable.', 'warning')
        return redirect(url_for('parent.dashboard'))

    status_filter = request.args.get('status', 'all')
    query = DigitalOutPass.query.filter_by(student_id=student.id)

    if status_filter in ['Active', 'Used', 'Completed', 'Revoked', 'Expired']:
        query = query.filter_by(status=status_filter)

    outpasses = query.order_by(DigitalOutPass.created_at.desc()).all()
    movement = ParentService.get_student_movement_status(student.id)

    total_passes = DigitalOutPass.query.filter_by(student_id=student.id).count()
    active_passes = DigitalOutPass.query.filter_by(student_id=student.id, status='Active').count()
    used_passes = DigitalOutPass.query.filter_by(student_id=student.id, status='Used').count()
    completed_passes = DigitalOutPass.query.filter_by(student_id=student.id, status='Completed').count()

    return render_template('parent/outpasses/list.html',
                           parent=parent,
                           student=student,
                           outpasses=outpasses,
                           movement=movement,
                           current_filter=status_filter,
                           total_passes=total_passes,
                           active_passes=active_passes,
                           used_passes=used_passes,
                           completed_passes=completed_passes)


@parent_bp.route('/outpasses/<int:id>')
@login_required
@parent_required
def view_outpass(id):
    """Detailed View of Child's Out-Pass with Gate Movement Audit History"""
    parent, student = _get_verified_parent_and_child()
    if not parent or not student:
        abort(403)

    outpass = DigitalOutPass.query.get_or_404(id)

    # IDOR check
    if outpass.student_id != student.id:
        abort(403)

    transactions = GateTransaction.query.filter_by(outpass_id=outpass.id).order_by(GateTransaction.scanned_at.asc()).all()

    return render_template('parent/outpasses/view.html',
                           parent=parent,
                           student=student,
                           outpass=outpass,
                           transactions=transactions)


@parent_bp.route('/attendance')
@login_required
@parent_required
def attendance_view():
    """Attendance Logs, Statistics, and Monthly Graph for Linked Student"""
    parent, student = _get_verified_parent_and_child()
    if not parent or not student:
        flash('Linked student record unavailable.', 'warning')
        return redirect(url_for('parent.dashboard'))

    month_filter = request.args.get('month', '') # format YYYY-MM
    query = student.attendance_records

    if month_filter:
        try:
            parts = month_filter.split('-')
            year = int(parts[0])
            month = int(parts[1])
            # filter for this year and month
            start_date = date(year, month, 1)
            next_month = month + 1 if month < 12 else 1
            next_year = year if month < 12 else year + 1
            end_date = date(next_year, next_month, 1)
            query = query.filter(Attendance.date >= start_date, Attendance.date < end_date)
        except Exception:
            pass

    records = query.order_by(Attendance.date.desc()).all()

    # Metrics
    all_records = student.attendance_records.all()
    total_days = len(all_records)
    present_days = sum(1 for r in all_records if r.status == 'present')
    absent_days = sum(1 for r in all_records if r.status == 'absent')
    leave_days = sum(1 for r in all_records if r.status == 'leave')
    percentage = student.attendance_percentage

    # Monthly graph aggregation for Chart.js (last 6 months)
    month_stats = {}
    for r in all_records:
        m_key = r.date.strftime('%b %Y')
        if m_key not in month_stats:
            month_stats[m_key] = {'present': 0, 'total': 0}
        month_stats[m_key]['total'] += 1
        if r.status == 'present':
            month_stats[m_key]['present'] += 1

    chart_labels = list(month_stats.keys())[-6:]
    chart_values = [
        round((month_stats[k]['present'] / month_stats[k]['total']) * 100, 1) if month_stats[k]['total'] > 0 else 100
        for k in chart_labels
    ]

    return render_template('parent/attendance.html',
                           parent=parent,
                           student=student,
                           records=records,
                           total_days=total_days,
                           present_days=present_days,
                           absent_days=absent_days,
                           leave_days=leave_days,
                           percentage=percentage,
                           month_filter=month_filter,
                           chart_labels=chart_labels,
                           chart_values=chart_values)


@parent_bp.route('/fees')
@login_required
@parent_required
def fees_view():
    """Fee Ledger and Payment History for Linked Student"""
    parent, student = _get_verified_parent_and_child()
    if not parent or not student:
        flash('Linked student record unavailable.', 'warning')
        return redirect(url_for('parent.dashboard'))

    fee_summary = FeeService.get_student_fee_summary(student.id) or {
        'total_fee': 27000.0,
        'total_paid': 0.0,
        'balance_due': 27000.0,
        'status': 'Due',
        'records': []
    }

    return render_template('parent/fees.html',
                           parent=parent,
                           student=student,
                           fees=fee_summary)


@parent_bp.route('/fees/receipt/<int:id>')
@login_required
@parent_required
def view_receipt(id):
    """View and Print Official Payment Receipt"""
    parent, student = _get_verified_parent_and_child()
    if not parent or not student:
        abort(403)

    fee_record = FeeRecord.query.get_or_404(id)

    # IDOR check
    if fee_record.student_id != student.id:
        abort(403)

    allocation = student.current_allocation
    hostel = allocation.hostel if allocation else None

    return render_template('parent/receipt.html',
                           parent=parent,
                           student=student,
                           fee=fee_record,
                           allocation=allocation,
                           hostel=hostel)


@parent_bp.route('/inquiries', methods=['GET', 'POST'])
@login_required
@parent_required
def inquiries_list():
    """Contact Assigned Warden & Parent Inquiries Desk"""
    parent, student = _get_verified_parent_and_child()
    if not parent or not student:
        flash('Linked student record unavailable.', 'warning')
        return redirect(url_for('parent.dashboard'))

    allocation = student.current_allocation
    hostel = allocation.hostel if allocation else None
    warden = hostel.wardens.first() if (hostel and hostel.wardens) else None

    form = ParentInquiryForm()

    if form.validate_on_submit():
        inquiry = ParentInquiry(
            parent_id=parent.id,
            student_id=student.id,
            warden_id=warden.id if warden else None,
            subject=form.subject.data.strip(),
            message=form.message.data.strip(),
            status='Pending'
        )
        db.session.add(inquiry)
        db.session.commit()

        # Notify warden if assigned
        if warden:
            NotificationService.create_notification(
                user_id=warden.user_id,
                title='New Parent Inquiry',
                message=f'Parent {parent.parent_name} ({parent.relationship_to_student} of {student.full_name}) submitted an inquiry: "{inquiry.subject}".',
                type='info',
                link=url_for('warden.parent_inquiries')
            )
            db.session.commit()

        flash('Your inquiry has been submitted to the hostel warden. You will be notified when a response is posted.', 'success')
        return redirect(url_for('parent.inquiries_list'))

    inquiries = parent.inquiries.order_by(ParentInquiry.created_at.desc()).all()

    return render_template('parent/inquiries.html',
                           parent=parent,
                           student=student,
                           warden=warden,
                           hostel=hostel,
                           form=form,
                           inquiries=inquiries)


@parent_bp.route('/notifications')
@login_required
@parent_required
def notifications_list():
    """Parent In-App Notifications History"""
    notifications = Notification.query.filter_by(user_id=current_user.id).order_by(Notification.created_at.desc()).all()
    # Mark unread as read
    Notification.query.filter_by(user_id=current_user.id, is_read=False).update({'is_read': True})
    db.session.commit()

    return render_template('parent/notifications.html', notifications=notifications)

