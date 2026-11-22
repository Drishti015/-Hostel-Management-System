from datetime import datetime, date
from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from app.utils.decorators import warden_required
from app.models import db, Student, Complaint, ComplaintResponse, Notice, Hostel, Attendance, LeaveApplication, DigitalOutPass, GateTransaction, BedAllocation
from app.services.attendance_service import AttendanceService
from app.services.notification_service import NotificationService
from app.services.outpass_service import OutPassService
from app.forms.complaint_forms import ComplaintResponseForm
from app.forms.notice_forms import NoticeForm
from app.forms.leave_forms import WardenReviewLeaveForm

warden_bp = Blueprint('warden', __name__)

@warden_bp.route('/dashboard')
@login_required
@warden_required
def dashboard():
    """Warden Operational Dashboard"""
    warden_profile = current_user.warden_profile
    assigned_hostel = warden_profile.assigned_hostel if warden_profile else None
    
    if assigned_hostel:
        hostel_students = Student.query.join(Student.allocations).filter_by(hostel_id=assigned_hostel.id, status='active').all()
        student_count = len(hostel_students)
        pending_complaints = Complaint.query.join(Complaint.room).filter_by(hostel_id=assigned_hostel.id).filter(Complaint.status.in_(['pending', 'in_progress'])).count()
        pending_leaves = LeaveApplication.query.filter_by(hostel_id=assigned_hostel.id, status='Pending').count()
    else:
        hostel_students = []
        student_count = Student.query.filter_by(status='active').count()
        pending_complaints = Complaint.query.filter(Complaint.status.in_(['pending', 'in_progress'])).count()
        pending_leaves = LeaveApplication.query.filter_by(status='Pending').count()

    today_str = date.today().strftime('%Y-%m-%d')
    notices = Notice.query.order_by(Notice.created_at.desc()).limit(5).all()

    return render_template('warden/dashboard.html',
                           warden_profile=warden_profile,
                           assigned_hostel=assigned_hostel,
                           student_count=student_count,
                           pending_complaints=pending_complaints,
                           pending_leaves=pending_leaves,
                           today_date=today_str,
                           notices=notices)


@warden_bp.route('/attendance')
@login_required
@warden_required
def attendance_view():
    """Daily night roll-call sheet for warden's assigned hostel"""
    warden_profile = current_user.warden_profile
    hostel = warden_profile.assigned_hostel if warden_profile else Hostel.query.first()
    
    date_str = request.args.get('date', date.today().strftime('%Y-%m-%d'))
    try:
        target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        target_date = date.today()

    if hostel:
        student_records = AttendanceService.get_hostel_attendance_for_date(hostel.id, target_date)
    else:
        student_records = []

    return render_template('warden/attendance.html',
                           hostel=hostel,
                           target_date=target_date.strftime('%Y-%m-%d'),
                           student_records=student_records)


@warden_bp.route('/attendance/submit', methods=['POST'])
@login_required
@warden_required
def submit_attendance():
    """Processes bulk roll-call submission"""
    hostel_id = int(request.form.get('hostel_id'))
    date_str = request.form.get('date')
    roll_date = datetime.strptime(date_str, '%Y-%m-%d').date()

    status_dict = {}
    for key, value in request.form.items():
        if key.startswith('status_'):
            student_id = key.split('_')[1]
            status_dict[student_id] = value

    warden_id = current_user.warden_profile.id if current_user.warden_profile else None
    count = AttendanceService.record_roll_call(
        hostel_id=hostel_id,
        roll_date=roll_date,
        status_dict=status_dict,
        marked_by_warden_id=warden_id
    )

    flash(f'Roll-call attendance for {count} residents saved for {roll_date.strftime("%d %B, %Y")}!', 'success')
    return redirect(url_for('warden.attendance_view', date=date_str))


@warden_bp.route('/complaints')
@login_required
@warden_required
def complaints_list():
    """Warden grievance review desk"""
    warden_profile = current_user.warden_profile
    assigned_hostel = warden_profile.assigned_hostel if warden_profile else None

    query = Complaint.query
    if assigned_hostel:
        query = query.join(Complaint.room).filter_by(hostel_id=assigned_hostel.id)

    complaints = query.order_by(Complaint.created_at.desc()).all()
    return render_template('admin/complaints/list.html', complaints=complaints)


@warden_bp.route('/complaints/<int:id>', methods=['GET', 'POST'])
@login_required
@warden_required
def view_complaint(id):
    """Warden resolves complaint and adds response remarks"""
    complaint = Complaint.query.get_or_404(id)
    form = ComplaintResponseForm()

    if form.validate_on_submit():
        response = ComplaintResponse(
            complaint_id=complaint.id,
            responder_user_id=current_user.id,
            response_text=form.response_text.data.strip(),
            status_updated_to=form.status.data
        )
        complaint.status = form.status.data
        db.session.add(response)
        db.session.commit()
        flash('Action response posted and complaint ticket updated.', 'success')
        return redirect(url_for('warden.view_complaint', id=complaint.id))

    return render_template('admin/complaints/view.html', complaint=complaint, form=form)


@warden_bp.route('/notices')
@login_required
@warden_required
def notices_list():
    """Warden circular management"""
    notices = Notice.query.order_by(Notice.created_at.desc()).all()
    return render_template('admin/notices/list.html', notices=notices)


@warden_bp.route('/notices/add', methods=['GET', 'POST'])
@login_required
@warden_required
def add_notice():
    """Warden posts circular to residents"""
    form = NoticeForm()
    if form.validate_on_submit():
        notice = Notice(
            posted_by_user_id=current_user.id,
            title=form.title.data.strip(),
            category=form.category.data,
            target_audience=form.target_audience.data,
            content=form.content.data.strip()
        )
        db.session.add(notice)
        db.session.commit()
        flash('Official circular posted successfully.', 'success')
        return redirect(url_for('warden.notices_list'))

    return render_template('admin/notices/form.html', form=form, title="Post Hostel Notice")


# =========================================================================
# MODULE 10: WARDEN LEAVE DESK & APPROVAL WORKFLOW
# =========================================================================

@warden_bp.route('/leaves', endpoint='leaves')
@warden_bp.route('/leaves-list', endpoint='leaves_list')
@login_required
@warden_required
def leaves_list():
    """Warden desk for managing resident leave applications within assigned hostel"""
    warden_profile = current_user.warden_profile
    assigned_hostel = warden_profile.assigned_hostel if warden_profile else None

    filter_status = request.args.get('status', 'all')
    query = LeaveApplication.query

    # Wardens can only review requests for their assigned hostel
    if assigned_hostel:
        query = query.filter(LeaveApplication.hostel_id == assigned_hostel.id)

    # Scoped metric counters
    base_query = LeaveApplication.query.filter(LeaveApplication.hostel_id == assigned_hostel.id) if assigned_hostel else LeaveApplication.query
    total_requests = base_query.count()
    pending_requests = base_query.filter_by(status='Pending').count()
    approved_requests = base_query.filter_by(status='Approved').count()
    rejected_requests = base_query.filter_by(status='Rejected').count()

    if filter_status in ['Pending', 'Approved', 'Rejected', 'Cancelled']:
        query = query.filter(LeaveApplication.status == filter_status)

    leaves = query.order_by(LeaveApplication.created_at.desc()).all()

    return render_template('warden/leaves/list.html',
                           warden_profile=warden_profile,
                           assigned_hostel=assigned_hostel,
                           leaves=leaves,
                           current_filter=filter_status,
                           total_requests=total_requests,
                           pending_requests=pending_requests,
                           approved_requests=approved_requests,
                           rejected_requests=rejected_requests)


@warden_bp.route('/leaves/<int:id>')
@login_required
@warden_required
def view_leave(id):
    """View complete application details and review form for a student leave request"""
    warden_profile = current_user.warden_profile
    leave = LeaveApplication.query.get_or_404(id)

    # Host-based access control: warden can only access applications from their assigned hostel
    if warden_profile and warden_profile.assigned_hostel_id:
        if leave.hostel_id and leave.hostel_id != warden_profile.assigned_hostel_id:
            abort(403)

    form = WardenReviewLeaveForm()
    return render_template('warden/leaves/view.html',
                           leave=leave,
                           warden_profile=warden_profile,
                           form=form)


@warden_bp.route('/leaves/<int:id>/action', methods=['POST'])
@login_required
@warden_required
def review_action(id):
    """Process approval or rejection decision with remarks"""
    warden_profile = current_user.warden_profile
    leave = LeaveApplication.query.get_or_404(id)

    # Host-based access control
    if warden_profile and warden_profile.assigned_hostel_id:
        if leave.hostel_id and leave.hostel_id != warden_profile.assigned_hostel_id:
            abort(403)

    decision = request.form.get('action')
    comment = request.form.get('review_comment', '').strip()

    if decision == 'reject':
        if not comment:
            flash('A rejection reason or remark is required to reject an application.', 'danger')
            return redirect(url_for('warden.view_leave', id=leave.id))

        leave.status = 'Rejected'
        leave.review_comment = comment
        leave.reviewed_by = warden_profile.id if warden_profile else None
        leave.reviewed_at = datetime.utcnow()
        leave.updated_at = datetime.utcnow()
        db.session.commit()

        # Send notification to student
        NotificationService.create_notification(
            user_id=leave.student.user_id,
            title='Leave Application Rejected',
            message=f'Your {leave.leave_type} application (#{leave.id}) was rejected by Warden. Reason: {comment}',
            type='danger',
            link=url_for('student.view_leave', id=leave.id)
        )
        # Send notification to linked parents
        from app.services.parent_service import ParentService
        ParentService.notify_parents_of_student(
            student_id=leave.student_id,
            title='Leave Application Rejected',
            message=f'Leave application (#{leave.id}) for {leave.student.full_name} was rejected by Warden. Reason: {comment}',
            type='danger',
            link=url_for('parent.view_leave', id=leave.id)
        )
        db.session.commit()

        flash(f'Leave application #{leave.id} has been rejected.', 'warning')

    elif decision == 'approve':
        leave.status = 'Approved'
        leave.review_comment = comment if comment else 'Approved by Hostel Warden'
        leave.reviewed_by = warden_profile.id if warden_profile else None
        leave.reviewed_at = datetime.utcnow()
        leave.updated_at = datetime.utcnow()
        db.session.commit()

        # Automatically generate digital QR out-pass for approved leave
        try:
            outpass = OutPassService.generate_outpass(leave)
        except Exception as e:
            current_app.logger.error(f"Error generating out-pass: {e}")
            outpass = None

        # Send notification to student
        NotificationService.create_notification(
            user_id=leave.student.user_id,
            title='Leave Application Approved',
            message=f'Your {leave.leave_type} application (#{leave.id}) was approved! Your Digital Out-Pass with QR code is now available.',
            type='success',
            link=url_for('student.view_outpass', id=outpass.id) if outpass else url_for('student.view_leave', id=leave.id)
        )
        # Send notification to linked parents
        from app.services.parent_service import ParentService
        ParentService.notify_parents_of_student(
            student_id=leave.student_id,
            title='Leave Application Approved',
            message=f'Leave application (#{leave.id}) for {leave.student.full_name} has been APPROVED by the hostel warden.',
            type='success',
            link=url_for('parent.view_outpass', id=outpass.id) if outpass else url_for('parent.view_leave', id=leave.id)
        )
        db.session.commit()

        flash(f'Leave application #{leave.id} approved successfully and Digital QR Out-Pass issued!', 'success')

    else:
        flash('Invalid action requested.', 'danger')

    return redirect(url_for('warden.leaves_list'))


# =========================================================================
# MODULE 11: WARDEN OUT-PASS & HOSTEL GATE MANAGEMENT
# =========================================================================

@warden_bp.route('/outpasses', endpoint='outpasses')
@warden_bp.route('/outpasses-list', endpoint='outpasses_list')
@login_required
@warden_required
def outpasses_list():
    """Warden desk for monitoring resident out-passes and gate activity"""
    warden_profile = current_user.warden_profile
    assigned_hostel = warden_profile.assigned_hostel if warden_profile else None

    status_filter = request.args.get('status', 'all')
    search_query = request.args.get('q', '').strip()
    page = request.args.get('page', 1, type=int)

    # Query out-passes scoped to warden's assigned hostel
    query = DigitalOutPass.query.join(LeaveApplication).join(Student)
    if assigned_hostel:
        query = query.filter(LeaveApplication.hostel_id == assigned_hostel.id)

    # Scoped metric counters
    base_query = DigitalOutPass.query.join(LeaveApplication)
    if assigned_hostel:
        base_query = base_query.filter(LeaveApplication.hostel_id == assigned_hostel.id)

    total_passes = base_query.count()
    active_passes = base_query.filter(DigitalOutPass.status == 'Active').count()
    outside_students = base_query.filter(DigitalOutPass.is_outside == True).count()
    overdue_students = base_query.filter(
        DigitalOutPass.is_outside == True,
        DigitalOutPass.expires_at < datetime.utcnow()
    ).count()
    completed_passes = base_query.filter(DigitalOutPass.status == 'Completed').count()
    revoked_passes = base_query.filter(DigitalOutPass.status == 'Revoked').count()

    # Apply filters
    if status_filter == 'outside':
        query = query.filter(DigitalOutPass.is_outside == True)
    elif status_filter == 'overdue':
        query = query.filter(
            DigitalOutPass.is_outside == True,
            DigitalOutPass.expires_at < datetime.utcnow()
        )
    elif status_filter in ['active', 'used', 'completed', 'revoked', 'expired']:
        query = query.filter(DigitalOutPass.status == status_filter.capitalize())
    elif status_filter in ['Active', 'Used', 'Completed', 'Revoked', 'Expired']:
        query = query.filter(DigitalOutPass.status == status_filter)

    if search_query:
        query = query.filter(
            (Student.full_name.ilike(f'%{search_query}%')) |
            (Student.enrollment_no.ilike(f'%{search_query}%')) |
            (LeaveApplication.destination.ilike(f'%{search_query}%'))
        )

    outpasses = query.order_by(DigitalOutPass.created_at.desc()).paginate(page=page, per_page=15, error_out=False)

    return render_template('warden/outpasses/list.html',
                           outpasses=outpasses,
                           assigned_hostel=assigned_hostel,
                           active_filter=status_filter,
                           current_filter=status_filter,
                           search_query=search_query,
                           total_count=total_passes,
                           active_count=active_passes,
                           outside_count=outside_students,
                           overdue_count=overdue_students,
                           completed_count=completed_passes,
                           revoked_count=revoked_passes)


@warden_bp.route('/outpasses/<int:id>')
@login_required
@warden_required
def view_outpass(id):
    """View details of a resident outpass and gate transaction audit trail"""
    warden_profile = current_user.warden_profile
    outpass = DigitalOutPass.query.get_or_404(id)

    if warden_profile and warden_profile.assigned_hostel_id:
        if outpass.leave_application.hostel_id and outpass.leave_application.hostel_id != warden_profile.assigned_hostel_id:
            abort(403)

    return render_template('warden/outpasses/view.html', outpass=outpass)


@warden_bp.route('/outpasses/<int:id>/revoke', methods=['POST'])
@login_required
@warden_required
def revoke_outpass(id):
    """Warden revocation of an active outpass with mandatory reason"""
    warden_profile = current_user.warden_profile
    outpass = DigitalOutPass.query.get_or_404(id)

    if warden_profile and warden_profile.assigned_hostel_id:
        if outpass.leave_application.hostel_id and outpass.leave_application.hostel_id != warden_profile.assigned_hostel_id:
            abort(403)

    reason = request.form.get('revocation_reason', '').strip() or request.form.get('reason', '').strip()
    if not reason:
        flash('A revocation reason is required to revoke an out-pass.', 'danger')
        return redirect(url_for('warden.view_outpass', id=outpass.id))

    success, msg = OutPassService.revoke_outpass(outpass.id, warden_profile.id if warden_profile else None, reason)
    if success:
        flash(f'Out-Pass #PASS-{outpass.id} has been revoked.', 'warning')
    else:
        flash(msg, 'danger')

    return redirect(url_for('warden.outpasses_list'))


@warden_bp.route('/inquiries')
@login_required
@warden_required
def parent_inquiries():
    """Warden view of parent inquiries for residents of their assigned hostel"""
    from app.models import ParentInquiry
    from app.forms.parent_forms import WardenReplyInquiryForm

    warden_profile = current_user.warden_profile
    assigned_hostel = warden_profile.assigned_hostel if warden_profile else None

    status_filter = request.args.get('status', 'all')
    query = ParentInquiry.query

    # Host-based filtering: filter inquiries by student allocations in warden's hostel
    if assigned_hostel:
        query = query.join(Student).join(BedAllocation).filter(
            BedAllocation.hostel_id == assigned_hostel.id,
            BedAllocation.status == 'active'
        )

    if status_filter in ['Pending', 'In Progress', 'Resolved']:
        query = query.filter(ParentInquiry.status == status_filter)

    inquiries = query.order_by(ParentInquiry.created_at.desc()).all()
    form = WardenReplyInquiryForm()

    return render_template('warden/inquiries/list.html',
                           inquiries=inquiries,
                           assigned_hostel=assigned_hostel,
                           current_filter=status_filter,
                           form=form)


@warden_bp.route('/inquiries/<int:id>/reply', methods=['POST'])
@login_required
@warden_required
def reply_inquiry(id):
    """Submit warden response to parent inquiry"""
    from app.models import ParentInquiry
    from app.forms.parent_forms import WardenReplyInquiryForm

    warden_profile = current_user.warden_profile
    inquiry = ParentInquiry.query.get_or_404(id)

    form = WardenReplyInquiryForm()
    if form.validate_on_submit():
        inquiry.response = form.response.data.strip()
        inquiry.status = form.status.data
        inquiry.responded_at = datetime.utcnow()
        inquiry.warden_id = warden_profile.id if warden_profile else inquiry.warden_id
        inquiry.updated_at = datetime.utcnow()
        db.session.commit()

        # Notify parent
        NotificationService.create_notification(
            user_id=inquiry.parent.user_id,
            title='Warden Responded to Your Inquiry',
            message=f'Hostel Warden posted a response regarding "{inquiry.subject}". Status: {inquiry.status}.',
            type='success',
            link=url_for('parent.inquiries_list')
        )
        db.session.commit()

        flash(f'Response successfully sent for Inquiry #{inquiry.id}.', 'success')
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f"{field.capitalize()}: {error}", 'danger')

    return redirect(url_for('warden.parent_inquiries'))


@warden_bp.route('/mess')
@login_required
@warden_required
def mess_view():
    """Warden Dining & Mess Monitoring Portal"""
    from app.models.mess import MessProfile, MealMenu, MealBooking, MealAttendance, MealFeedback, MessNotice, MessInventory
    from app.services.mess_service import MessService

    warden_profile = current_user.warden_profile
    assigned_hostel = warden_profile.assigned_hostel if warden_profile else None

    # Get mess corresponding to warden's hostel, or default mess
    if assigned_hostel and assigned_hostel.messes.first():
        mess = assigned_hostel.messes.first()
    else:
        mess = MessService.get_or_create_default_mess()

    today = date.today()
    today_menus = MealMenu.query.filter_by(mess_id=mess.id, meal_date=today).all()

    today_bookings = MealBooking.query.join(MealMenu).filter(
        MealMenu.mess_id == mess.id,
        MealMenu.meal_date == today
    ).count()

    today_attendance = MealAttendance.query.join(MealMenu).filter(
        MealMenu.mess_id == mess.id,
        MealMenu.meal_date == today,
        MealAttendance.attendance_status.in_(['Present', 'Walk-in'])
    ).count()

    recent_feedbacks = MealFeedback.query.join(MealMenu).filter(
        MealMenu.mess_id == mess.id
    ).order_by(MealFeedback.created_at.desc()).limit(5).all()

    notices = MessNotice.query.filter(
        (MessNotice.mess_id == mess.id) | (MessNotice.mess_id == None)
    ).order_by(MessNotice.created_at.desc()).limit(5).all()

    low_stock_items = MessInventory.query.filter(
        MessInventory.mess_id == mess.id,
        MessInventory.quantity <= MessInventory.minimum_stock_level
    ).all()

    return render_template('warden/mess.html',
                           mess=mess,
                           assigned_hostel=assigned_hostel,
                           today_menus=today_menus,
                           today_bookings=today_bookings,
                           today_attendance=today_attendance,
                           recent_feedbacks=recent_feedbacks,
                           notices=notices,
                           low_stock_items=low_stock_items,
                           today=today)

