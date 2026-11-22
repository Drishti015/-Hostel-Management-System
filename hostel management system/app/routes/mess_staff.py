from datetime import datetime, date
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, abort
from flask_login import login_required, current_user
from app.utils.decorators import mess_staff_required
from app.models import db, Student, User, BedAllocation
from app.models.mess import MessProfile, MealMenu, MealBooking, MealAttendance, MessStaffProfile
from app.services.mess_service import MessService

mess_staff_bp = Blueprint('mess_staff', __name__)

def _get_staff_mess():
    """Retrieves the mess assigned to the logged-in staff member or the active default mess"""
    if current_user.is_admin:
        return MessService.get_or_create_default_mess()
    
    staff_profile = MessStaffProfile.query.filter_by(user_id=current_user.id).first()
    if staff_profile and staff_profile.assigned_mess:
        return staff_profile.assigned_mess
    return MessService.get_or_create_default_mess()

@mess_staff_bp.route('/dashboard')
@login_required
@mess_staff_required
def dashboard():
    """Mess Staff Station Dashboard: live active meal overview and counters"""
    mess = _get_staff_mess()
    today = date.today()
    today_menus = MealMenu.query.filter_by(mess_id=mess.id, meal_date=today, is_published=True).all()

    # Determine active slot based on current time
    hour = datetime.now().hour
    if hour < 11:
        suggested_slot = 'Breakfast'
    elif hour < 16:
        suggested_slot = 'Lunch'
    elif hour < 19:
        suggested_slot = 'Snacks'
    else:
        suggested_slot = 'Dinner'

    active_menu = None
    for m in today_menus:
        if m.meal_type == suggested_slot:
            active_menu = m
            break
    if not active_menu and today_menus:
        active_menu = today_menus[0]

    # Slot attendance counts
    stats = {}
    for slot in ['Breakfast', 'Lunch', 'Snacks', 'Dinner']:
        menu = next((m for m in today_menus if m.meal_type == slot), None)
        if menu:
            stats[slot] = {
                'menu_id': menu.id,
                'title': menu.title,
                'timing': menu.meal_timing,
                'booked': menu.active_booking_count,
                'attended': menu.attendance_count,
                'capacity': menu.capacity
            }
        else:
            stats[slot] = None

    recent_attendances = MealAttendance.query.join(MealMenu).filter(
        MealMenu.mess_id == mess.id,
        MealMenu.meal_date == today
    ).order_by(MealAttendance.check_in_time.desc()).limit(8).all()

    return render_template('mess_staff/dashboard.html',
                           mess=mess,
                           active_menu=active_menu,
                           today_menus=today_menus,
                           stats=stats,
                           recent_attendances=recent_attendances)


@mess_staff_bp.route('/scanner')
@login_required
@mess_staff_required
def scanner():
    """Live Camera QR Scanner Terminal for dining hall staff"""
    mess = _get_staff_mess()
    today = date.today()
    published_menus = MealMenu.query.filter_by(
        mess_id=mess.id,
        meal_date=today,
        is_published=True
    ).all()

    menu_id = request.args.get('menu_id', type=int)
    active_menu = MealMenu.query.get(menu_id) if menu_id else None
    if not active_menu and published_menus:
        active_menu = published_menus[0]

    return render_template('mess_staff/scanner.html',
                           mess=mess,
                           active_menu=active_menu,
                           published_menus=published_menus)


@mess_staff_bp.route('/verify', methods=['POST'])
@login_required
@mess_staff_required
def verify_scan():
    """
    Central server-side meal QR verification and attendance recording API.
    Handles AJAX submissions from webcam scanner and manual form fallback.
    """
    if request.is_json:
        data = request.get_json() or {}
        raw_token = (data.get('token') or data.get('qr_data') or '').strip()
        menu_id = data.get('meal_menu_id')
        try:
            menu_id = int(menu_id) if menu_id is not None else None
        except (ValueError, TypeError):
            menu_id = None

        # Auto-match meal slot if slot name was provided
        if not menu_id and data.get('slot'):
            mess = _get_staff_mess()
            slot_menu = MealMenu.query.filter_by(
                mess_id=mess.id,
                meal_date=date.today(),
                meal_type=data.get('slot'),
                is_published=True
            ).first()
            if slot_menu:
                menu_id = slot_menu.id

        verification_method = data.get('verification_method', 'QR_Scan')
        remarks = (data.get('remarks') or '').strip()
        is_ajax = True
    else:
        raw_token = (request.form.get('token') or request.form.get('qr_data') or '').strip()
        menu_id = request.form.get('meal_menu_id', type=int)
        verification_method = 'Manual_ID'
        remarks = request.form.get('remarks', '').strip()
        is_ajax = False

    if not raw_token:
        response_payload = {'success': False, 'code': 'TOKEN_REQUIRED', 'status': 'REJECTED', 'message': 'Scan token or Student ID required.'}
        return jsonify(response_payload) if is_ajax else redirect(url_for('mess_staff.scanner'))

    if not menu_id:
        response_payload = {'success': False, 'code': 'MENU_REQUIRED', 'status': 'REJECTED', 'message': 'Select an active meal slot first.'}
        return jsonify(response_payload) if is_ajax else redirect(url_for('mess_staff.scanner'))

    # Verify student identity
    student = MessService.verify_student_qr_payload(raw_token)
    if not student:
        response_payload = {
            'success': False,
            'code': 'STUDENT_NOT_FOUND',
            'status': 'REJECTED',
            'message': f'Unrecognized QR payload or Student ID "{raw_token}".'
        }
        return jsonify(response_payload) if is_ajax else redirect(url_for('mess_staff.scanner'))

    # Record meal attendance
    result = MessService.record_meal_attendance(
        student_id=student.id,
        meal_menu_id=menu_id,
        staff_user_id=current_user.id,
        verification_method=verification_method,
        remarks=remarks
    )

    if is_ajax:
        result['status'] = 'VALID' if result['success'] else (
            'DUPLICATE' if result.get('code') == 'DUPLICATE_ATTENDANCE' else 'REJECTED'
        )
        result.pop('student', None)
        result.pop('menu', None)
        return jsonify(result)

    if result['success']:
        flash(result['message'], 'success')
    elif result.get('code') == 'DUPLICATE_ATTENDANCE':
        flash(result['message'], 'warning')
    else:
        flash(result['message'], 'danger')

    return redirect(url_for('mess_staff.scanner', menu_id=menu_id))


@mess_staff_bp.route('/attendance')
@login_required
@mess_staff_required
def attendance():
    """Audit log of meal attendances recorded by staff"""
    mess = _get_staff_mess()
    menu_id = request.args.get('menu_id', type=int)
    search_q = request.args.get('q', '').strip()
    selected_date = request.args.get('date', date.today().strftime('%Y-%m-%d'))

    try:
        filter_date = datetime.strptime(selected_date, '%Y-%m-%d').date()
    except ValueError:
        filter_date = date.today()

    query = MealAttendance.query.join(MealMenu).join(Student).filter(
        MealMenu.mess_id == mess.id,
        MealMenu.meal_date == filter_date
    )

    if menu_id:
        query = query.filter(MealAttendance.meal_menu_id == menu_id)

    if search_q:
        query = query.filter(
            (Student.full_name.ilike(f"%{search_q}%")) |
            (Student.enrollment_no.ilike(f"%{search_q}%")) |
            (Student.roll_no.ilike(f"%{search_q}%"))
        )

    attendances = query.order_by(MealAttendance.check_in_time.desc()).all()
    today_menus = MealMenu.query.filter_by(mess_id=mess.id, meal_date=filter_date).all()

    return render_template('mess_staff/attendance.html',
                           mess=mess,
                           attendances=attendances,
                           selected_date=filter_date,
                           today_menus=today_menus,
                           selected_menu_id=menu_id,
                           search_q=search_q)
