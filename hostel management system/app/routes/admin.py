import csv
import io
from datetime import datetime, date
from flask import Blueprint, render_template, redirect, url_for, flash, request, Response, abort, jsonify
from flask_login import login_required, current_user
from app.utils.decorators import admin_required
from app.models import db, User, Student, Room, Bed, FeeRecord, Complaint, ComplaintResponse, Notice, Hostel, BedAllocation, Attendance, LeaveApplication, DigitalOutPass, GateTransaction
from app.forms.student_forms import AddStudentForm, EditStudentForm
from app.forms.room_forms import HostelForm, RoomForm, ManualAllocationForm
from app.forms.fee_forms import AddFeePaymentForm
from app.forms.complaint_forms import ComplaintResponseForm
from app.forms.notice_forms import NoticeForm
from app.services.allocation_service import AllocationService
from app.services.fee_service import FeeService
from app.services.report_service import ReportService
from sqlalchemy import func

admin_bp = Blueprint('admin', __name__)

@admin_bp.route('/dashboard')
@login_required
@admin_required
def dashboard():
    """Admin Executive Dashboard"""
    total_students = Student.query.filter_by(status='active').count()
    total_hostels = Hostel.query.count()
    total_rooms = Room.query.count()
    total_beds = Bed.query.count()
    occupied_beds = Bed.query.filter_by(status='occupied').count()
    available_beds = Bed.query.filter_by(status='available').count()
    
    occupancy_rate = round((occupied_beds / total_beds * 100), 1) if total_beds > 0 else 0
    total_fees_collected = db.session.query(func.sum(FeeRecord.amount)).filter_by(status='paid').scalar() or 0.0
    pending_complaints = Complaint.query.filter(Complaint.status.in_(['pending', 'in_progress'])).count()
    pending_leaves = LeaveApplication.query.filter_by(status='Pending').count()
    total_outpasses = DigitalOutPass.query.count()
    students_outside = DigitalOutPass.query.filter_by(is_outside=True).count()
    overdue_returns = DigitalOutPass.query.filter(DigitalOutPass.is_outside == True, DigitalOutPass.expires_at < datetime.utcnow()).count()

    recent_students = Student.query.order_by(Student.created_at.desc()).limit(5).all()
    recent_complaints = Complaint.query.order_by(Complaint.created_at.desc()).limit(5).all()
    notices = Notice.query.order_by(Notice.created_at.desc()).limit(5).all()

    return render_template('admin/dashboard.html',
                           total_students=total_students,
                           total_hostels=total_hostels,
                           total_rooms=total_rooms,
                           total_beds=total_beds,
                           occupied_beds=occupied_beds,
                           available_beds=available_beds,
                           occupancy_rate=occupancy_rate,
                           total_fees_collected=total_fees_collected,
                           pending_complaints=pending_complaints,
                           pending_leaves=pending_leaves,
                           total_outpasses=total_outpasses,
                           students_outside=students_outside,
                           overdue_returns=overdue_returns,
                           recent_students=recent_students,
                           recent_complaints=recent_complaints,
                           notices=notices)


@admin_bp.route('/api/analytics-data')
@login_required
@admin_required
def analytics_data():
    """JSON API endpoint powering Chart.js visual charts"""
    data = ReportService.get_dashboard_chart_data()
    return jsonify(data)

# =========================================================================
# MODULE 2: STUDENT MANAGEMENT CRUD
# =========================================================================

@admin_bp.route('/students')
@login_required
@admin_required
def students_list():
    search_query = request.args.get('q', '').strip()
    branch_filter = request.args.get('branch', '').strip()
    status_filter = request.args.get('status', '').strip()

    query = Student.query.join(User)
    if search_query:
        query = query.filter(
            (Student.full_name.ilike(f'%{search_query}%')) |
            (Student.enrollment_no.ilike(f'%{search_query}%')) |
            (Student.phone.ilike(f'%{search_query}%')) |
            (User.email.ilike(f'%{search_query}%'))
        )
    if branch_filter:
        query = query.filter(Student.branch == branch_filter)
    if status_filter:
        query = query.filter(Student.status == status_filter)

    students = query.order_by(Student.created_at.desc()).all()
    return render_template('admin/students/list.html',
                           students=students,
                           search_query=search_query,
                           selected_branch=branch_filter,
                           selected_status=status_filter)


@admin_bp.route('/students/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_student():
    form = AddStudentForm()
    if form.validate_on_submit():
        try:
            new_user = User(
                username=form.username.data.strip(),
                email=form.email.data.strip().lower(),
                role='student'
            )
            new_user.set_password(form.password.data)
            db.session.add(new_user)
            db.session.flush()

            new_student = Student(
                user_id=new_user.id,
                enrollment_no=form.enrollment_no.data.strip().upper(),
                roll_no=form.roll_no.data.strip() if form.roll_no.data else None,
                full_name=form.full_name.data.strip(),
                phone=form.phone.data.strip(),
                gender=form.gender.data,
                branch=form.branch.data,
                year=form.year.data,
                semester=form.semester.data,
                guardian_name=form.guardian_name.data.strip(),
                guardian_phone=form.guardian_phone.data.strip(),
                emergency_phone=form.emergency_phone.data.strip() if form.emergency_phone.data else None,
                blood_group=form.blood_group.data if form.blood_group.data else None,
                address=form.address.data.strip(),
                status='active'
            )
            db.session.add(new_student)
            db.session.commit()

            flash(f'Student {new_student.full_name} ({new_student.enrollment_no}) registered successfully!', 'success')
            return redirect(url_for('admin.students_list'))
        except Exception as e:
            db.session.rollback()
            flash(f'Failed to add student: {str(e)}', 'danger')

    return render_template('admin/students/add.html', form=form)


@admin_bp.route('/students/<int:id>')
@login_required
@admin_required
def view_student(id):
    student = Student.query.get_or_404(id)
    return render_template('admin/students/view.html', student=student)


@admin_bp.route('/students/<int:id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_student(id):
    student = Student.query.get_or_404(id)
    form = EditStudentForm(obj=student)
    if form.validate_on_submit():
        try:
            form.populate_obj(student)
            db.session.commit()
            flash(f'Profile for {student.full_name} updated successfully.', 'success')
            return redirect(url_for('admin.view_student', id=student.id))
        except Exception as e:
            db.session.rollback()
            flash(f'Failed to update student profile: {str(e)}', 'danger')

    return render_template('admin/students/edit.html', form=form, student=student)


@admin_bp.route('/students/<int:id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_student(id):
    student = Student.query.get_or_404(id)
    try:
        if student.current_allocation:
            alloc = student.current_allocation
            alloc.vacate(reason='Student record deleted/archived by Administrator')

        user_account = student.user_account
        db.session.delete(student)
        if user_account:
            db.session.delete(user_account)

        db.session.commit()
        flash('Student record removed and associated bed marked available.', 'info')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting student: {str(e)}', 'danger')

    return redirect(url_for('admin.students_list'))


@admin_bp.route('/students/export-csv')
@login_required
@admin_required
def export_students_csv():
    students = Student.query.order_by(Student.id.asc()).all()
    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow([
        'ID', 'Enrollment No', 'Full Name', 'Email', 'Phone',
        'Gender', 'Branch', 'Year', 'Semester', 'Hostel', 'Room & Bed',
        'Guardian Name', 'Guardian Phone', 'Blood Group', 'Status', 'Registered Date'
    ])

    for s in students:
        alloc = s.current_allocation
        hostel_name = alloc.hostel.name if alloc else 'Unassigned'
        room_bed = f"{alloc.room.room_number} ({alloc.bed.bed_number})" if alloc else 'Unassigned'

        writer.writerow([
            s.id, s.enrollment_no, s.full_name,
            s.user_account.email if s.user_account else 'N/A',
            s.phone, s.gender.capitalize(), s.branch, s.year, s.semester,
            hostel_name, room_bed, s.guardian_name, s.guardian_phone,
            s.blood_group or '', s.status.capitalize(), s.created_at.strftime('%Y-%m-%d')
        ])

    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=students_aktu_hms.csv'}
    )

# =========================================================================
# MODULE 3: HOSTEL BUILDINGS & ROOM MANAGEMENT
# =========================================================================

@admin_bp.route('/hostels')
@login_required
@admin_required
def hostels_list():
    hostels = Hostel.query.all()
    return render_template('admin/hostels/list.html', hostels=hostels)


@admin_bp.route('/hostels/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_hostel():
    form = HostelForm()
    if form.validate_on_submit():
        if Hostel.query.filter_by(name=form.name.data.strip()).first():
            flash('A hostel building with this name already exists.', 'danger')
            return render_template('admin/hostels/form.html', form=form, title="Add Hostel Block")

        hostel = Hostel(
            name=form.name.data.strip(),
            hostel_type=form.hostel_type.data,
            total_floors=form.total_floors.data,
            description=form.description.data.strip() if form.description.data else None
        )
        db.session.add(hostel)
        db.session.commit()
        flash(f'Hostel block "{hostel.name}" added successfully.', 'success')
        return redirect(url_for('admin.hostels_list'))

    return render_template('admin/hostels/form.html', form=form, title="Add Hostel Block")


@admin_bp.route('/hostels/<int:id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_hostel(id):
    hostel = Hostel.query.get_or_404(id)
    form = HostelForm(obj=hostel)
    if form.validate_on_submit():
        form.populate_obj(hostel)
        db.session.commit()
        flash(f'Hostel block "{hostel.name}" updated successfully.', 'success')
        return redirect(url_for('admin.hostels_list'))

    return render_template('admin/hostels/form.html', form=form, title="Edit Hostel Block")


@admin_bp.route('/hostels/<int:id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_hostel(id):
    hostel = Hostel.query.get_or_404(id)
    try:
        db.session.delete(hostel)
        db.session.commit()
        flash(f'Hostel "{hostel.name}" removed.', 'info')
    except Exception as e:
        db.session.rollback()
        flash(f'Failed to delete hostel: {str(e)}', 'danger')

    return redirect(url_for('admin.hostels_list'))


@admin_bp.route('/rooms')
@login_required
@admin_required
def rooms_list():
    hostel_id = request.args.get('hostel_id', type=int)
    room_type = request.args.get('room_type', '').strip()

    query = Room.query
    if hostel_id:
        query = query.filter_by(hostel_id=hostel_id)
    if room_type:
        query = query.filter_by(room_type=room_type)

    rooms = query.order_by(Room.floor.asc(), Room.room_number.asc()).all()
    hostels = Hostel.query.all()
    return render_template('admin/rooms/list.html', rooms=rooms, hostels=hostels, selected_hostel=hostel_id, selected_type=room_type)


@admin_bp.route('/rooms/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_room():
    form = RoomForm()
    form.hostel_id.choices = [(h.id, h.name) for h in Hostel.query.all()]

    if form.validate_on_submit():
        existing = Room.query.filter_by(hostel_id=form.hostel_id.data, room_number=form.room_number.data.strip()).first()
        if existing:
            flash(f'Room {form.room_number.data} already exists in this hostel building.', 'danger')
            return render_template('admin/rooms/add.html', form=form)

        capacity_map = {'single': 1, 'double': 2, 'triple': 3, 'four': 4}
        capacity = capacity_map.get(form.room_type.data, 2)

        try:
            new_room = Room(
                hostel_id=form.hostel_id.data,
                room_number=form.room_number.data.strip(),
                floor=form.floor.data,
                room_type=form.room_type.data,
                capacity=capacity,
                monthly_fee=form.monthly_fee.data,
                status=form.status.data
            )
            db.session.add(new_room)
            db.session.flush()

            bed_labels = ['Bed-A', 'Bed-B', 'Bed-C', 'Bed-D']
            for i in range(capacity):
                bed = Bed(room_id=new_room.id, bed_number=bed_labels[i], status='available')
                db.session.add(bed)

            db.session.commit()
            flash(f'Room {new_room.room_number} with {capacity} beds generated successfully!', 'success')
            return redirect(url_for('admin.rooms_list'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating room: {str(e)}', 'danger')

    return render_template('admin/rooms/add.html', form=form)


@admin_bp.route('/rooms/<int:id>')
@login_required
@admin_required
def view_room(id):
    room = Room.query.get_or_404(id)
    return render_template('admin/rooms/view.html', room=room)


@admin_bp.route('/rooms/<int:id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_room(id):
    room = Room.query.get_or_404(id)
    try:
        db.session.delete(room)
        db.session.commit()
        flash(f'Room {room.room_number} removed.', 'info')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting room: {str(e)}', 'danger')

    return redirect(url_for('admin.rooms_list'))

# =========================================================================
# MODULE 4: ALLOCATION ENGINE
# =========================================================================

@admin_bp.route('/allocations')
@login_required
@admin_required
def allocations_list():
    allocations = BedAllocation.query.order_by(BedAllocation.created_at.desc()).all()
    return render_template('admin/allocations/list.html', allocations=allocations)


@admin_bp.route('/allocations/new', methods=['GET', 'POST'])
@login_required
@admin_required
def new_allocation():
    form = ManualAllocationForm()
    unallocated_students = [s for s in Student.query.filter_by(status='active').all() if not s.has_active_allocation]
    form.student_id.choices = [(s.id, f"{s.full_name} ({s.enrollment_no}) - {s.gender.capitalize()}") for s in unallocated_students]

    available_beds = Bed.query.filter_by(status='available').join(Room).join(Hostel).all()
    form.bed_id.choices = [(b.id, f"{b.room.hostel.name} | Room {b.room.room_number} ({b.bed_number})") for b in available_beds]

    if form.validate_on_submit():
        success, message = AllocationService.allocate_bed(
            student_id=form.student_id.data,
            bed_id=form.bed_id.data,
            allocated_from=form.allocated_from.data
        )
        if success:
            flash(message, 'success')
            return redirect(url_for('admin.allocations_list'))
        else:
            flash(message, 'danger')

    return render_template('admin/allocations/new.html', form=form)


@admin_bp.route('/allocations/auto')
@login_required
@admin_required
def auto_allocate_view():
    unallocated = [s for s in Student.query.filter_by(status='active').all() if not s.has_active_allocation]
    return render_template('admin/allocations/auto.html', unallocated_students=unallocated)


@admin_bp.route('/allocations/auto/<int:student_id>', methods=['POST'])
@login_required
@admin_required
def trigger_auto_allocate(student_id):
    success, message = AllocationService.auto_allocate_student(student_id)
    if success:
        flash(message, 'success')
    else:
        flash(message, 'danger')
    return redirect(url_for('admin.auto_allocate_view'))


@admin_bp.route('/allocations/<int:id>/vacate', methods=['POST'])
@login_required
@admin_required
def vacate_allocation(id):
    reason = request.form.get('reason', 'Administrative Vacate Order')
    success, message = AllocationService.vacate_bed(id, reason=reason)
    if success:
        flash(message, 'success')
    else:
        flash(message, 'danger')
    return redirect(request.referrer or url_for('admin.allocations_list'))

# =========================================================================
# MODULE 5: FEE MANAGEMENT
# =========================================================================

@admin_bp.route('/fees')
@login_required
@admin_required
def fees_list():
    fee_records = FeeRecord.query.order_by(FeeRecord.payment_date.desc()).all()
    total_collections = db.session.query(func.sum(FeeRecord.amount)).filter_by(status='paid').scalar() or 0.0
    total_receipts = FeeRecord.query.count()
    pending_count = FeeRecord.query.filter_by(status='pending').count()
    return render_template('admin/fees/list.html',
                           fee_records=fee_records,
                           total_collections=total_collections,
                           total_receipts=total_receipts,
                           pending_count=pending_count)


@admin_bp.route('/fees/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_fee():
    form = AddFeePaymentForm()
    students = Student.query.filter_by(status='active').order_by(Student.full_name.asc()).all()
    form.student_id.choices = [(s.id, f"{s.full_name} ({s.enrollment_no})") for s in students]

    if form.validate_on_submit():
        record = FeeService.record_payment(
            student_id=form.student_id.data,
            amount=form.amount.data,
            payment_date=form.payment_date.data,
            payment_method=form.payment_method.data,
            fee_type=form.fee_type.data,
            status=form.status.data,
            transaction_id=form.transaction_id.data.strip() if form.transaction_id.data else None,
            remarks=form.remarks.data.strip() if form.remarks.data else None
        )
        flash(f'Payment of ₹{record.amount:,.2f} recorded! Receipt {record.receipt_no} generated.', 'success')
        return redirect(url_for('admin.fees_list'))

    return render_template('admin/fees/add.html', form=form)


@admin_bp.route('/fees/<int:id>/receipt')
@login_required
@admin_required
def print_receipt(id):
    fee = FeeRecord.query.get_or_404(id)
    return render_template('admin/fees/receipt.html', fee=fee)

# =========================================================================
# MODULE 6: ATTENDANCE
# =========================================================================

@admin_bp.route('/attendance')
@login_required
@admin_required
def attendance_list():
    attendance_logs = Attendance.query.order_by(Attendance.date.desc(), Attendance.id.desc()).limit(100).all()
    return render_template('admin/attendance/list.html', attendance_logs=attendance_logs)

# =========================================================================
# MODULE 7: GRIEVANCE REDRESSAL (COMPLAINTS)
# =========================================================================

@admin_bp.route('/complaints')
@login_required
@admin_required
def complaints_list():
    status_filter = request.args.get('status', '').strip()
    cat_filter = request.args.get('category', '').strip()

    query = Complaint.query
    if status_filter:
        query = query.filter_by(status=status_filter)
    if cat_filter:
        query = query.filter_by(category=cat_filter)

    complaints = query.order_by(Complaint.created_at.desc()).all()
    return render_template('admin/complaints/list.html',
                           complaints=complaints,
                           selected_status=status_filter,
                           selected_cat=cat_filter)


@admin_bp.route('/complaints/<int:id>', methods=['GET', 'POST'])
@login_required
@admin_required
def view_complaint(id):
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
        return redirect(url_for('admin.view_complaint', id=complaint.id))

    return render_template('admin/complaints/view.html', complaint=complaint, form=form)

# =========================================================================
# MODULE 8: NOTICES & CIRCULARS
# =========================================================================

@admin_bp.route('/notices')
@login_required
@admin_required
def notices_list():
    notices = Notice.query.order_by(Notice.created_at.desc()).all()
    return render_template('admin/notices/list.html', notices=notices)


@admin_bp.route('/notices/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_notice():
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
        flash('Official notice published successfully to target audience.', 'success')
        return redirect(url_for('admin.notices_list'))

    return render_template('admin/notices/form.html', form=form, title="Publish Official Notice")


@admin_bp.route('/notices/<int:id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_notice(id):
    notice = Notice.query.get_or_404(id)
    form = NoticeForm(obj=notice)
    if form.validate_on_submit():
        form.populate_obj(notice)
        db.session.commit()
        flash('Notice updated successfully.', 'success')
        return redirect(url_for('admin.notices_list'))

    return render_template('admin/notices/form.html', form=form, title="Edit Notice Bulletin")


@admin_bp.route('/notices/<int:id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_notice(id):
    notice = Notice.query.get_or_404(id)
    try:
        db.session.delete(notice)
        db.session.commit()
        flash('Notice removed from bulletin board.', 'info')
    except Exception as e:
        db.session.rollback()
        flash(f'Failed to delete notice: {str(e)}', 'danger')

    return redirect(url_for('admin.notices_list'))


# =========================================================================
# MODULE 11: ADMIN LEAVE OVERSIGHT & FILTERING
# =========================================================================

@admin_bp.route('/leaves')
@login_required
@admin_required
def leaves_list():
    """Administrator leave application monitor with multi-filter controls"""
    hostel_id = request.args.get('hostel_id', type=int)
    status_filter = request.args.get('status', 'all')
    search_query = request.args.get('q', '').strip()

    # Base query joined with Student
    query = LeaveApplication.query.join(Student)

    if hostel_id:
        query = query.filter(LeaveApplication.hostel_id == hostel_id)

    if status_filter in ['Pending', 'Approved', 'Rejected', 'Cancelled']:
        query = query.filter(LeaveApplication.status == status_filter)

    if search_query:
        query = query.filter(
            (Student.full_name.ilike(f'%{search_query}%')) |
            (Student.enrollment_no.ilike(f'%{search_query}%')) |
            (LeaveApplication.destination.ilike(f'%{search_query}%')) |
            (LeaveApplication.leave_type.ilike(f'%{search_query}%'))
        )

    leaves = query.order_by(LeaveApplication.created_at.desc()).all()

    # System-wide metrics
    total_leaves = LeaveApplication.query.count()
    pending_leaves = LeaveApplication.query.filter_by(status='Pending').count()
    approved_leaves = LeaveApplication.query.filter_by(status='Approved').count()
    rejected_leaves = LeaveApplication.query.filter_by(status='Rejected').count()
    cancelled_leaves = LeaveApplication.query.filter_by(status='Cancelled').count()

    hostels = Hostel.query.all()

    return render_template('admin/leaves/list.html',
                           leaves=leaves,
                           hostels=hostels,
                           selected_hostel=hostel_id,
                           selected_status=status_filter,
                           search_query=search_query,
                           total_leaves=total_leaves,
                           pending_leaves=pending_leaves,
                           approved_leaves=approved_leaves,
                           rejected_leaves=rejected_leaves,
                           cancelled_leaves=cancelled_leaves)


@admin_bp.route('/leaves/<int:id>')
@login_required
@admin_required
def view_leave(id):
    """Administrator detailed view of student leave application and audit log"""
    leave = LeaveApplication.query.get_or_404(id)
    return render_template('admin/leaves/view.html', leave=leave)


# =========================================================================
# MODULE 12: ADMIN OUT-PASS & GATE MANAGEMENT AUDIT
# =========================================================================

@admin_bp.route('/outpasses', endpoint='outpasses')
@admin_bp.route('/outpasses-list', endpoint='outpasses_list')
@login_required
@admin_required
def outpasses_list():
    """System-wide digital out-pass oversight with status and block filtering"""
    hostel_id = request.args.get('hostel_id', type=int)
    status_filter = request.args.get('status', 'all')
    search_query = request.args.get('q', '').strip()
    page = request.args.get('page', 1, type=int)

    query = DigitalOutPass.query.join(LeaveApplication).join(Student)

    if hostel_id:
        query = query.filter(LeaveApplication.hostel_id == hostel_id)

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

    # System metrics
    total_passes = DigitalOutPass.query.count()
    active_passes = DigitalOutPass.query.filter_by(status='Active').count()
    outside_students = DigitalOutPass.query.filter_by(is_outside=True).count()
    overdue_students = DigitalOutPass.query.filter(
        DigitalOutPass.is_outside == True,
        DigitalOutPass.expires_at < datetime.utcnow()
    ).count()

    hostels = Hostel.query.all()

    return render_template('admin/outpasses/list.html',
                           outpasses=outpasses,
                           hostels=hostels,
                           hostel_id=hostel_id,
                           selected_hostel=hostel_id,
                           active_filter=status_filter,
                           selected_status=status_filter,
                           search_query=search_query,
                           total_count=total_passes,
                           active_count=active_passes,
                           outside_count=outside_students,
                           overdue_count=overdue_students)


@admin_bp.route('/outpasses/<int:id>')
@login_required
@admin_required
def view_outpass(id):
    """Administrator inspection of an individual digital out-pass and gate transaction trail"""
    outpass = DigitalOutPass.query.get_or_404(id)
    return render_template('admin/outpasses/view.html', outpass=outpass)


@admin_bp.route('/gate-transactions')
@login_required
@admin_required
def gate_transactions():
    """Campus gate security log with filter controls and export functionality"""
    event_filter = request.args.get('event', 'all')
    status_filter = request.args.get('status', 'all')
    search_query = request.args.get('q', '').strip()

    query = GateTransaction.query.join(Student)

    if event_filter in ['EXIT', 'ENTRY']:
        query = query.filter(GateTransaction.event_type == event_filter)

    if status_filter in ['Success', 'Failed']:
        query = query.filter(GateTransaction.verification_status == status_filter)

    if search_query:
        query = query.filter(
            (Student.full_name.ilike(f'%{search_query}%')) |
            (Student.enrollment_no.ilike(f'%{search_query}%')) |
            (GateTransaction.gate_location.ilike(f'%{search_query}%'))
        )

    page = request.args.get('page', 1, type=int)
    transactions = query.order_by(GateTransaction.scanned_at.desc()).paginate(page=page, per_page=20, error_out=False)

    total_transactions = GateTransaction.query.count()
    exits_count = GateTransaction.query.filter_by(event_type='EXIT').count()
    entries_count = GateTransaction.query.filter_by(event_type='ENTRY').count()

    return render_template('admin/gate/transactions.html',
                           transactions=transactions,
                           event_filter=event_filter,
                           status_filter=status_filter,
                           search_query=search_query,
                           total_transactions=total_transactions,
                           exits_count=exits_count,
                           entries_count=entries_count)


@admin_bp.route('/gate-transactions/export')
@login_required
@admin_required
def export_gate_transactions():
    """Export complete gate transactions audit trail as CSV file"""
    transactions = GateTransaction.query.order_by(GateTransaction.scanned_at.desc()).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        'Transaction ID', 'Out-Pass ID', 'Student Name', 'Enrollment No',
        'Event Type', 'Gate Location', 'Timestamp (UTC)', 'Verification Status', 'Security Guard ID', 'Remarks'
    ])

    for tx in transactions:
        writer.writerow([
            tx.id,
            tx.outpass_id,
            tx.student.full_name,
            tx.student.enrollment_no,
            tx.event_type,
            tx.gate_location,
            tx.scanned_at.strftime('%Y-%m-%d %H:%M:%S'),
            tx.verification_status,
            tx.security_user_id or 'System',
            tx.remarks or ''
        ])

    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment;filename=HostelEase_Gate_Audit_{date.today().strftime('%Y%m%d')}.csv"}
    )


# =========================================================================
# PARENT & GUARDIAN MANAGEMENT
# =========================================================================

@admin_bp.route('/parents')
@login_required
@admin_required
def parents_list():
    """Administrator directory of parent accounts and student linkages"""
    from app.models import ParentProfile
    search_query = request.args.get('q', '').strip()
    status_filter = request.args.get('status', 'all')
    hostel_id = request.args.get('hostel_id', type=int)

    query = ParentProfile.query.join(User, ParentProfile.user_id == User.id)

    if status_filter in ['active', 'inactive']:
        query = query.filter(ParentProfile.account_status == status_filter)

    if hostel_id:
        query = query.join(Student, ParentProfile.student_id == Student.id).join(BedAllocation, Student.id == BedAllocation.student_id).filter(
            BedAllocation.hostel_id == hostel_id,
            BedAllocation.status == 'active'
        )

    if search_query:
        query = query.outerjoin(Student, ParentProfile.student_id == Student.id).filter(
            (ParentProfile.parent_name.ilike(f'%{search_query}%')) |
            (User.email.ilike(f'%{search_query}%')) |
            (ParentProfile.phone_number.ilike(f'%{search_query}%')) |
            (Student.full_name.ilike(f'%{search_query}%')) |
            (Student.enrollment_no.ilike(f'%{search_query}%'))
        )

    parents = query.order_by(ParentProfile.created_at.desc()).all()
    hostels = Hostel.query.all()

    total_parents = ParentProfile.query.count()
    active_parents = ParentProfile.query.filter_by(account_status='active').count()
    inactive_parents = ParentProfile.query.filter_by(account_status='inactive').count()

    return render_template('admin/parents/list.html',
                           parents=parents,
                           hostels=hostels,
                           selected_hostel=hostel_id,
                           status_filter=status_filter,
                           search_query=search_query,
                           total_parents=total_parents,
                           active_parents=active_parents,
                           inactive_parents=inactive_parents)


@admin_bp.route('/parents/create', methods=['GET', 'POST'])
@login_required
@admin_required
def create_parent():
    """Administrator creation of verified parent account and student link"""
    from app.models import ParentProfile
    from app.forms.parent_forms import AdminCreateParentForm

    form = AdminCreateParentForm()
    # Populate students dropdown: active students
    students = Student.query.filter_by(status='active').order_by(Student.full_name.asc()).all()
    form.student_id.choices = [(s.id, f"{s.full_name} ({s.enrollment_no} - {s.branch})") for s in students]

    if form.validate_on_submit():
        username = form.username.data.strip()
        email = form.email.data.strip().lower()

        if User.query.filter_by(username=username).first():
            flash('Username already in use. Please select a unique username.', 'danger')
            return render_template('admin/parents/create.html', form=form)

        if User.query.filter_by(email=email).first():
            flash('Email address already registered.', 'danger')
            return render_template('admin/parents/create.html', form=form)

        try:
            # Create user entity
            user = User(
                username=username,
                email=email,
                role='parent',
                is_active=(form.account_status.data == 'active')
            )
            user.set_password(form.password.data)
            db.session.add(user)
            db.session.flush()

            # Create parent profile entity
            profile = ParentProfile(
                user_id=user.id,
                parent_name=form.parent_name.data.strip(),
                phone_number=form.phone_number.data.strip(),
                relationship_to_student=form.relationship_to_student.data,
                student_id=form.student_id.data,
                account_status=form.account_status.data
            )
            db.session.add(profile)
            db.session.commit()

            flash(f'Parent account for "{profile.parent_name}" created and linked to student successfully!', 'success')
            return redirect(url_for('admin.parents_list'))
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error creating parent account: {e}", exc_info=True)
            flash('An unexpected error occurred while creating parent account.', 'danger')

    return render_template('admin/parents/create.html', form=form)


@admin_bp.route('/parents/<int:id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_parent(id):
    """Administrator modification of parent particulars and student linkage"""
    from app.models import ParentProfile
    from app.forms.parent_forms import AdminEditParentForm, AdminResetParentPasswordForm

    profile = ParentProfile.query.get_or_404(id)
    form = AdminEditParentForm(obj=profile)
    pwd_form = AdminResetParentPasswordForm()

    students = Student.query.filter_by(status='active').order_by(Student.full_name.asc()).all()
    form.student_id.choices = [(s.id, f"{s.full_name} ({s.enrollment_no} - {s.branch})") for s in students]

    if form.validate_on_submit():
        profile.parent_name = form.parent_name.data.strip()
        profile.phone_number = form.phone_number.data.strip()
        profile.relationship_to_student = form.relationship_to_student.data
        profile.student_id = form.student_id.data
        profile.account_status = form.account_status.data

        # Synchronize user active flag
        if profile.user_account:
            profile.user_account.is_active = (form.account_status.data == 'active')

        profile.updated_at = datetime.utcnow()
        db.session.commit()

        flash(f'Parent profile for "{profile.parent_name}" updated successfully.', 'success')
        return redirect(url_for('admin.parents_list'))

    return render_template('admin/parents/edit.html', parent=profile, form=form, pwd_form=pwd_form)


@admin_bp.route('/parents/<int:id>/toggle-status', methods=['POST'])
@login_required
@admin_required
def toggle_parent_status(id):
    """Administrator quick toggle to activate or deactivate a parent's portal access"""
    from app.models import ParentProfile
    profile = ParentProfile.query.get_or_404(id)

    new_status = 'inactive' if profile.account_status == 'active' else 'active'
    profile.account_status = new_status
    if profile.user_account:
        profile.user_account.is_active = (new_status == 'active')

    profile.updated_at = datetime.utcnow()
    db.session.commit()

    flash(f'Parent account #{profile.id} ({profile.parent_name}) is now {new_status.upper()}.', 'info')
    return redirect(url_for('admin.parents_list'))


@admin_bp.route('/parents/<int:id>/reset-password', methods=['POST'])
@login_required
@admin_required
def reset_parent_password(id):
    """Administrator secure password reset for parent account"""
    from app.models import ParentProfile
    from app.forms.parent_forms import AdminResetParentPasswordForm

    profile = ParentProfile.query.get_or_404(id)
    form = AdminResetParentPasswordForm()

    if form.validate_on_submit():
        if profile.user_account:
            profile.user_account.set_password(form.new_password.data)
            db.session.commit()
            flash(f'Password for parent user "{profile.user_account.username}" has been successfully reset.', 'success')
        else:
            flash('No associated user account found.', 'danger')
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f"{error}", 'danger')

    return redirect(url_for('admin.edit_parent', id=profile.id))


# =====================================================================
# MESS MANAGEMENT (ADMINISTRATION)
# =====================================================================

@admin_bp.route('/mess')
@login_required
@admin_required
def mess_dashboard():
    """Admin Master Mess Management Center"""
    from decimal import Decimal
    from app.models.mess import MessProfile, MealMenu, MealBooking, MealAttendance, MessExpense, MessStaffProfile
    from app.services.mess_service import MessService

    # Ensure at least default mess exists
    MessService.get_or_create_default_mess()

    messes = MessProfile.query.all()
    today = date.today()
    first_day_of_month = date(today.year, today.month, 1)

    today_bookings = MealBooking.query.join(MealMenu).filter(
        MealMenu.meal_date == today,
        MealBooking.booking_status == 'Booked'
    ).count()

    today_served = MealAttendance.query.join(MealMenu).filter(
        MealMenu.meal_date == today,
        MealAttendance.attendance_status.in_(['Present', 'Walk-in'])
    ).count()

    month_expenses = db.session.query(db.func.sum(MessExpense.amount)).filter(
        MessExpense.transaction_date >= first_day_of_month
    ).scalar() or Decimal('0.00')

    staff_members = MessStaffProfile.query.all()

    return render_template('admin/mess/dashboard.html',
                           messes=messes,
                           today_bookings=today_bookings,
                           today_served=today_served,
                           month_expenses=month_expenses,
                           staff_members=staff_members,
                           today=today)


@admin_bp.route('/mess/create', methods=['GET', 'POST'])
@login_required
@admin_required
def mess_create():
    """Create a new mess facility"""
    from app.models.mess import MessProfile
    from app.models import Hostel

    hostels = Hostel.query.all()

    if request.method == 'POST':
        mess_name = request.form.get('mess_name', '').strip()
        hostel_id = request.form.get('hostel_id', type=int) or None
        description = request.form.get('description', '').strip()
        contact_number = request.form.get('contact_number', '').strip()
        capacity = request.form.get('daily_capacity', 300, type=int)
        meal_policy = request.form.get('meal_policy', 'booking_required')
        operating_status = request.form.get('operating_status', 'Active')

        if not mess_name:
            flash('Mess Name is required.', 'danger')
            return redirect(url_for('admin.mess_create'))

        mess = MessProfile(
            mess_name=mess_name,
            hostel_id=hostel_id,
            description=description,
            contact_number=contact_number,
            daily_capacity=capacity,
            meal_policy=meal_policy,
            operating_status=operating_status
        )
        db.session.add(mess)
        db.session.commit()
        flash(f'Mess facility "{mess_name}" created successfully.', 'success')
        return redirect(url_for('admin.mess_dashboard'))

    return render_template('admin/mess/form.html', mess=None, hostels=hostels)


@admin_bp.route('/mess/<int:id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def mess_edit(id):
    """Update mess operating policies and capacity"""
    from app.models.mess import MessProfile
    from app.models import Hostel

    mess = MessProfile.query.get_or_404(id)
    hostels = Hostel.query.all()

    if request.method == 'POST':
        mess.mess_name = request.form.get('mess_name', mess.mess_name).strip()
        mess.hostel_id = request.form.get('hostel_id', type=int) or None
        mess.description = request.form.get('description', mess.description or '').strip()
        mess.contact_number = request.form.get('contact_number', mess.contact_number or '').strip()
        mess.daily_capacity = request.form.get('daily_capacity', mess.daily_capacity, type=int)
        mess.meal_policy = request.form.get('meal_policy', mess.meal_policy)
        mess.operating_status = request.form.get('operating_status', mess.operating_status)
        mess.updated_at = datetime.utcnow()

        db.session.commit()
        flash(f'Mess "{mess.mess_name}" updated successfully.', 'success')
        return redirect(url_for('admin.mess_dashboard'))

    return render_template('admin/mess/form.html', mess=mess, hostels=hostels)


@admin_bp.route('/mess/<int:id>/toggle-policy', methods=['POST'])
@login_required
@admin_required
def mess_toggle_policy(id):
    """Quickly switch dining entry policies (booking_required vs walk_in)"""
    from app.models.mess import MessProfile
    mess = MessProfile.query.get_or_404(id)
    if mess.meal_policy == 'booking_required':
        mess.meal_policy = 'walk_in'
    else:
        mess.meal_policy = 'booking_required'
    mess.updated_at = datetime.utcnow()
    db.session.commit()
    policy_label = "Pre-booking required" if mess.meal_policy == 'booking_required' else "Open walk-ins allowed"
    flash(f'{mess.mess_name} policy updated: {policy_label}.', 'info')
    return redirect(url_for('admin.mess_dashboard'))


@admin_bp.route('/mess/staff/create', methods=['GET', 'POST'])
@login_required
@admin_required
def mess_staff_create():
    """Provision a new mess staff user account"""
    from app.models.mess import MessProfile, MessStaffProfile

    messes = MessProfile.query.all()

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        full_name = request.form.get('full_name', '').strip()
        password = request.form.get('password', '').strip()
        mess_id = request.form.get('mess_id', type=int)
        designation = request.form.get('role_designation', 'Counter Staff')
        shift = request.form.get('shift_timing', 'General Shift (7 AM - 10 PM)')

        if not username or not password or not full_name:
            flash('Username, Full Name, and Password are required.', 'danger')
            return redirect(url_for('admin.mess_staff_create'))

        if User.query.filter((User.username == username) | (User.email == email)).first():
            flash('Username or Email is already registered in the system.', 'danger')
            return redirect(url_for('admin.mess_staff_create'))

        user = User(
            username=username,
            email=email,
            role='mess_staff',
            is_active=True
        )
        user.set_password(password)
        db.session.add(user)
        db.session.flush()

        staff_profile = MessStaffProfile(
            user_id=user.id,
            mess_id=mess_id,
            staff_name=full_name,
            role_designation=designation,
            employment_status='Active'
        )
        db.session.add(staff_profile)
        db.session.commit()

        flash(f'Mess Staff account for "{full_name}" (@{username}) provisioned successfully.', 'success')
        return redirect(url_for('admin.mess_dashboard'))

    return render_template('admin/mess/staff_create.html', messes=messes)


@admin_bp.route('/mess/billing/generate', methods=['POST'])
@login_required
@admin_required
def mess_billing_generate():
    """Trigger automated monthly mess billing with approved leave rebates"""
    from app.services.mess_service import MessService

    month = request.form.get('month', type=int) or date.today().month
    year = request.form.get('year', type=int) or date.today().year

    result = MessService.generate_monthly_billing(month, year)
    if result['success']:
        flash(result['message'], 'success')
    else:
        flash(result['message'], 'danger')

    return redirect(url_for('admin.mess_dashboard'))

