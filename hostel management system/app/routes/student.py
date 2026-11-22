import os
import uuid
from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request, abort, current_app, send_from_directory
from flask_login import login_required, current_user
from app.utils.decorators import student_required
from app.models import db, Notice, Complaint, FeeRecord, Attendance, LeaveApplication, DigitalOutPass, GateTransaction
from app.forms.complaint_forms import SubmitComplaintForm
from app.forms.leave_forms import ApplyLeaveForm
from app.services.fee_service import FeeService
from app.services.notification_service import NotificationService

student_bp = Blueprint('student', __name__)

@student_bp.route('/dashboard')
@login_required
@student_required
def dashboard():
    """Student Self-Service Portal Dashboard"""
    student_profile = current_user.student_profile
    allocation = student_profile.current_allocation if student_profile else None
    
    fees = student_profile.fee_records.order_by(FeeRecord.payment_date.desc()).all() if student_profile else []
    complaints = student_profile.complaints.order_by(Complaint.created_at.desc()).limit(5).all() if student_profile else []
    recent_leaves = student_profile.leave_applications.order_by(LeaveApplication.created_at.desc()).limit(3).all() if student_profile else []
    
    gender_target = 'boys' if (student_profile and student_profile.gender == 'male') else 'girls'
    notices = Notice.query.filter(Notice.target_audience.in_(['all', gender_target])).order_by(Notice.created_at.desc()).limit(5).all()

    return render_template('student/dashboard.html',
                           student=student_profile,
                           allocation=allocation,
                           fees=fees,
                           complaints=complaints,
                           recent_leaves=recent_leaves,
                           notices=notices)


@student_bp.route('/fees')
@login_required
@student_required
def fees_view():
    """Student dues overview and receipt collection"""
    student = current_user.student_profile
    if not student:
        abort(404)

    summary = FeeService.get_student_fee_summary(student.id)
    return render_template('student/fees.html', student=student, fee_summary=summary)


@student_bp.route('/fees/<int:id>/receipt')
@login_required
@student_required
def print_receipt(id):
    """View and print personal fee receipt"""
    student = current_user.student_profile
    fee = FeeRecord.query.get_or_404(id)

    if fee.student_id != student.id:
        abort(403)

    return render_template('admin/fees/receipt.html', fee=fee)


@student_bp.route('/attendance')
@login_required
@student_required
def attendance_view():
    """Personal roll-call compliance log and percentage"""
    student = current_user.student_profile
    if not student:
        abort(404)

    records = student.attendance_records.order_by(Attendance.date.desc()).all()
    total_checks = len(records)
    leave_count = student.attendance_records.filter_by(status='leave').count()

    return render_template('student/attendance.html',
                           student=student,
                           records=records,
                           total_checks=total_checks,
                           leave_count=leave_count)


# =========================================================================
# MODULE 7: STUDENT COMPLAINT FILING & TRACKING
# =========================================================================

@student_bp.route('/complaints')
@login_required
@student_required
def complaints_list():
    """List of all complaints filed by logged-in student"""
    student = current_user.student_profile
    complaints = student.complaints.order_by(Complaint.created_at.desc()).all() if student else []
    return render_template('student/complaints/list.html', complaints=complaints)


@student_bp.route('/complaints/new', methods=['GET', 'POST'])
@login_required
@student_required
def new_complaint():
    """File a new maintenance issue ticket"""
    student = current_user.student_profile
    form = SubmitComplaintForm()

    if form.validate_on_submit():
        alloc = student.current_allocation
        room_id = alloc.room_id if alloc else None

        complaint = Complaint(
            student_id=student.id,
            room_id=room_id,
            title=form.title.data.strip(),
            category=form.category.data,
            priority=form.priority.data,
            description=form.description.data.strip(),
            status='pending'
        )
        db.session.add(complaint)
        db.session.commit()
        flash(f'Grievance ticket #{complaint.id} registered successfully. The warden has been notified.', 'success')
        return redirect(url_for('student.complaints_list'))

    return render_template('student/complaints/new.html', form=form)


@student_bp.route('/complaints/<int:id>')
@login_required
@student_required
def view_complaint(id):
    """Inspect status and staff response trail for personal complaint"""
    student = current_user.student_profile
    complaint = Complaint.query.get_or_404(id)

    if complaint.student_id != student.id:
        abort(403)

    return render_template('student/complaints/view.html', complaint=complaint)


# =========================================================================
# MODULE 8: STUDENT NOTICES
# =========================================================================

@student_bp.route('/notices')
@login_required
@student_required
def notices_view():
    """Bulletins and circulars for student's demographic category"""
    student = current_user.student_profile
    target_audience = ['all']
    if student:
        target_audience.append('boys' if student.gender == 'male' else 'girls')

    notices = Notice.query.filter(Notice.target_audience.in_(target_audience)).order_by(Notice.created_at.desc()).all()
    return render_template('student/notices.html', notices=notices)


# =========================================================================
# MODULE 9: STUDENT LEAVE APPLICATION SYSTEM
# =========================================================================

@student_bp.route('/leaves')
@login_required
@student_required
def leaves_list():
    """Leave management dashboard and application history for authenticated student"""
    student = current_user.student_profile
    if not student:
        abort(404)

    filter_status = request.args.get('status', 'all')
    query = student.leave_applications

    if filter_status in ['Pending', 'Approved', 'Rejected', 'Cancelled']:
        query = query.filter_by(status=filter_status)

    leaves = query.order_by(LeaveApplication.created_at.desc()).all()

    # Metric counts for stat cards
    total_count = student.leave_applications.count()
    pending_count = student.leave_applications.filter_by(status='Pending').count()
    approved_count = student.leave_applications.filter_by(status='Approved').count()
    rejected_count = student.leave_applications.filter_by(status='Rejected').count()
    cancelled_count = student.leave_applications.filter_by(status='Cancelled').count()

    return render_template('student/leaves/list.html',
                           student=student,
                           leaves=leaves,
                           current_filter=filter_status,
                           total_count=total_count,
                           pending_count=pending_count,
                           approved_count=approved_count,
                           rejected_count=rejected_count,
                           cancelled_count=cancelled_count)


@student_bp.route('/leaves/apply', methods=['GET', 'POST'])
@login_required
@student_required
def apply_leave():
    """Submit new student leave out-pass application"""
    student = current_user.student_profile
    if not student:
        abort(404)

    allocation = student.current_allocation
    form = ApplyLeaveForm()

    # Pre-fill emergency contact on GET if empty
    if request.method == 'GET' and not form.emergency_contact.data:
        form.emergency_contact.data = student.emergency_phone or student.guardian_phone or student.phone

    if form.validate_on_submit():
        # Check for duplicate pending leave request with overlapping or same dates
        existing_duplicate = LeaveApplication.query.filter_by(
            student_id=student.id,
            from_date=form.from_date.data,
            to_date=form.to_date.data,
            status='Pending'
        ).first()

        if existing_duplicate:
            flash('You already have a pending leave application for this exact date period.', 'warning')
            return render_template('student/leaves/apply.html', student=student, allocation=allocation, form=form)

        # Handle optional supporting document upload
        filename = None
        file = form.supporting_document.data
        if file and hasattr(file, 'filename') and file.filename:
            original_filename = file.filename
            ext = original_filename.rsplit('.', 1)[1].lower() if '.' in original_filename else ''
            if ext in {'pdf', 'png', 'jpg', 'jpeg'}:
                filename = f"leave_{student.id}_{int(datetime.utcnow().timestamp())}_{uuid.uuid4().hex[:8]}.{ext}"
                upload_dir = current_app.config.get('UPLOAD_FOLDER', os.path.join(current_app.root_path, 'static', 'uploads', 'leave_documents'))
                os.makedirs(upload_dir, exist_ok=True)
                file.save(os.path.join(upload_dir, filename))
            else:
                flash('Invalid file format. Only PDF, PNG, JPG, and JPEG documents are permitted.', 'danger')
                return render_template('student/leaves/apply.html', student=student, allocation=allocation, form=form)

        # Create leave record
        leave = LeaveApplication(
            student_id=student.id,
            hostel_id=allocation.hostel_id if allocation else None,
            leave_type=form.leave_type.data,
            from_date=form.from_date.data,
            to_date=form.to_date.data,
            reason=form.reason.data.strip(),
            destination=form.destination.data.strip(),
            emergency_contact=form.emergency_contact.data.strip(),
            supporting_document=filename,
            status='Pending'
        )
        db.session.add(leave)
        db.session.commit()

        # Send in-app notification to student
        NotificationService.create_notification(
            user_id=current_user.id,
            title='Leave Application Submitted',
            message=f'Your {leave.leave_type} request (#{leave.id}) from {leave.from_date.strftime("%d %b")} to {leave.to_date.strftime("%d %b, %Y")} has been forwarded to the hostel warden.',
            type='info',
            link=url_for('student.view_leave', id=leave.id)
        )

        # Send in-app notification to linked parent(s)
        from app.services.parent_service import ParentService
        ParentService.notify_parents_of_student(
            student_id=student.id,
            title='Leave Application Submitted',
            message=f'Your child {student.full_name} submitted a {leave.leave_type} request (#{leave.id}) from {leave.from_date.strftime("%d %b")} to {leave.to_date.strftime("%d %b, %Y")}.',
            type='info',
            link=url_for('parent.view_leave', id=leave.id)
        )

        # Send notification to assigned hostel warden(s)
        if allocation and allocation.hostel:
            for warden in allocation.hostel.wardens:
                NotificationService.create_notification(
                    user_id=warden.user_id,
                    title='New Leave Application',
                    message=f'Resident {student.full_name} ({allocation.room.room_number}) submitted a {leave.leave_type} request ({leave.number_of_days} days).',
                    type='warning',
                    link=url_for('warden.view_leave', id=leave.id)
                )
        db.session.commit()

        flash(f'Leave application #{leave.id} submitted successfully! Your warden has been notified.', 'success')
        return redirect(url_for('student.leaves_list'))

    return render_template('student/leaves/apply.html', student=student, allocation=allocation, form=form)


@student_bp.route('/leaves/<int:id>')
@login_required
@student_required
def view_leave(id):
    """View full details and audit log for a specific leave application"""
    student = current_user.student_profile
    leave = LeaveApplication.query.get_or_404(id)

    # Enforce IDOR protection: only the owner student can view
    if leave.student_id != student.id:
        abort(403)

    return render_template('student/leaves/view.html', leave=leave, student=student)


@student_bp.route('/leaves/<int:id>/cancel', methods=['POST'])
@login_required
@student_required
def cancel_leave(id):
    """Allow student to revoke pending leave applications"""
    student = current_user.student_profile
    leave = LeaveApplication.query.get_or_404(id)

    # Enforce IDOR authorization
    if leave.student_id != student.id:
        abort(403)

    # Cancellation business rule: only Pending applications can be cancelled
    if leave.status != 'Pending':
        flash('Only pending leave applications can be cancelled.', 'danger')
        return redirect(url_for('student.view_leave', id=leave.id))

    leave.status = 'Cancelled'
    leave.updated_at = datetime.utcnow()
    db.session.commit()

    # Notify student
    NotificationService.create_notification(
        user_id=current_user.id,
        title='Leave Application Cancelled',
        message=f'You cancelled leave application #{leave.id} ({leave.leave_type}).',
        type='secondary',
        link=url_for('student.view_leave', id=leave.id)
    )

    # Notify warden(s)
    if leave.hostel:
        for warden in leave.hostel.wardens:
            NotificationService.create_notification(
                user_id=warden.user_id,
                title='Leave Request Cancelled',
                message=f'Student {student.full_name} cancelled their pending leave request (#{leave.id}).',
                type='info',
                link=url_for('warden.leaves_list')
            )
    db.session.commit()

    flash(f'Leave application #{leave.id} has been cancelled.', 'info')
    return redirect(url_for('student.leaves_list'))


# =========================================================================
# MODULE 10: STUDENT DIGITAL QR OUT-PASS
# =========================================================================

@student_bp.route('/outpasses')
@login_required
@student_required
def outpasses_list():
    """Student Digital Out-Pass dashboard and active gate pass wallet"""
    try:
        student = current_user.student_profile
        if not student:
            flash('Student profile not found. Please contact administration.', 'warning')
            return redirect(url_for('student.dashboard'))

        status_filter = request.args.get('status', 'all')
        query = student.out_passes

        if status_filter in ['Active', 'Used', 'Completed', 'Revoked', 'Expired']:
            query = query.filter_by(status=status_filter)

        outpasses = query.order_by(DigitalOutPass.created_at.desc()).all()

        total_passes = student.out_passes.count()
        active_passes = student.out_passes.filter_by(status='Active').count()
        used_passes = student.out_passes.filter_by(status='Used').count()
        completed_passes = student.out_passes.filter_by(status='Completed').count()
        expired_passes = student.out_passes.filter_by(status='Expired').count()

        return render_template('student/outpasses/list.html',
                               student=student,
                               outpasses=outpasses,
                               current_filter=status_filter,
                               total_passes=total_passes,
                               active_passes=active_passes,
                               used_passes=used_passes,
                               completed_passes=completed_passes,
                               expired_passes=expired_passes)
    except Exception as e:
        current_app.logger.error(f"Error loading student outpasses wallet: {e}", exc_info=True)
        flash('An unexpected error occurred while loading your digital out-passes. Please try again.', 'danger')
        return redirect(url_for('student.dashboard'))


@student_bp.route('/outpasses/<int:id>')
@login_required
@student_required
def view_outpass(id):
    """Detailed view of a specific digital out-pass with prominent QR code and gate scan logs"""
    try:
        student = current_user.student_profile
        if not student:
            flash('Student profile not found.', 'warning')
            return redirect(url_for('student.dashboard'))

        outpass = DigitalOutPass.query.get_or_404(id)

        # IDOR check: student can only view their own out-pass
        if outpass.student_id != student.id:
            abort(403)

        return render_template('student/outpasses/view.html',
                               student=student,
                               outpass=outpass)
    except Exception as e:
        if hasattr(e, 'code') and e.code in [403, 404]:
            raise e
        current_app.logger.error(f"Error loading outpass #{id}: {e}", exc_info=True)
        flash('Unable to retrieve the requested out-pass slip.', 'danger')
        return redirect(url_for('student.outpasses_list'))


@student_bp.route('/outpasses/<int:id>/download')
@login_required
@student_required
def download_qr(id):
    """Directly download QR code image file for offline presentation at gate"""
    student = current_user.student_profile
    outpass = DigitalOutPass.query.get_or_404(id)

    # IDOR check
    if outpass.student_id != student.id:
        abort(403)

    if not outpass.qr_code_file:
        flash('QR Code image file not found.', 'danger')
        return redirect(url_for('student.view_outpass', id=outpass.id))

    upload_base = current_app.config.get('UPLOAD_FOLDER', os.path.join(current_app.root_path, 'static', 'uploads'))
    qr_dir = os.path.join(upload_base, 'qrcodes')
    return send_from_directory(qr_dir, outpass.qr_code_file, as_attachment=True, download_name=f"HostelEase_OutPass_{outpass.id}.png")
