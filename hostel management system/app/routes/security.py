from datetime import datetime, date, time
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, abort
from flask_login import login_required, current_user
from app.utils.decorators import security_required
from app.models import db, DigitalOutPass, GateTransaction, Student, Hostel
from app.services.outpass_service import OutPassService

security_bp = Blueprint('security', __name__)

@security_bp.route('/dashboard')
@login_required
@security_required
def dashboard():
    """Security Guard Station Master Dashboard"""
    metrics = OutPassService.get_today_metrics()

    # Recent transactions
    recent_transactions = GateTransaction.query.order_by(GateTransaction.scanned_at.desc()).limit(10).all()

    # Students currently outside
    outside_passes = DigitalOutPass.query.filter_by(is_outside=True).order_by(DigitalOutPass.updated_at.desc()).limit(8).all()

    return render_template('security/dashboard.html',
                           metrics=metrics,
                           exits_today=metrics['exits_today'],
                           entries_today=metrics['entries_today'],
                           outside_count=metrics['outside_count'],
                           overdue_count=metrics['overdue_count'],
                           recent_transactions=recent_transactions,
                           outside_passes=outside_passes,
                           today_date=date.today().strftime('%d %B, %Y'))


@security_bp.route('/scan', endpoint='scan')
@security_bp.route('/scan-terminal', endpoint='scan_terminal')
@login_required
@security_required
def scan():
    """Interactive camera & barcode scanner terminal with mode selection (EXIT / ENTRY)"""
    initial_mode = request.args.get('mode', 'EXIT').upper()
    if initial_mode not in ['EXIT', 'ENTRY']:
        initial_mode = 'EXIT'

    gate_location = request.args.get('gate', 'Main Campus Gate')

    return render_template('security/scan.html',
                           mode=initial_mode,
                           initial_mode=initial_mode,
                           gate_location=gate_location)


@security_bp.route('/verify', methods=['POST'], endpoint='verify')
@security_bp.route('/verify-scan', methods=['POST'], endpoint='verify_scan')
@login_required
@security_required
def verify():
    """
    Central server-side QR verification API endpoint.
    Accepts both AJAX JSON requests from camera scanner and standard HTML form posts.
    """
    if request.is_json:
        data = request.get_json() or {}
        token = data.get('token', '').strip()
        event_type = data.get('event_type', 'EXIT').strip().upper()
        gate_location = data.get('gate_location', 'Main Campus Gate').strip()
        remarks = data.get('remarks', '').strip()
        is_ajax = True
    else:
        token = request.form.get('token', '').strip()
        event_type = request.form.get('event_type', 'EXIT').strip().upper()
        gate_location = request.form.get('gate_location', 'Main Campus Gate').strip()
        remarks = request.form.get('remarks', '').strip()
        is_ajax = False

    result = OutPassService.verify_and_record_scan(
        raw_token_input=token,
        guard_user_id=current_user.id,
        gate_location=gate_location,
        expected_event_type=event_type,
        remarks=remarks
    )

    if is_ajax:
        # Build JSON response payload
        response_payload = {
            'success': result['success'],
            'message': result.get('message', ''),
            'error': result.get('error', ''),
            'code': result.get('code', ''),
            'event_type': result.get('event_type', event_type),
            'is_overdue': result.get('is_overdue', False)
        }

        if 'outpass' in result and result['outpass']:
            outpass = result['outpass']
            student = result['student']
            alloc = student.current_allocation
            response_payload['data'] = {
                'outpass_id': outpass.id,
                'student_name': student.full_name,
                'enrollment_no': student.enrollment_no,
                'roll_no': student.roll_no or 'N/A',
                'branch': student.branch,
                'hostel': alloc.hostel.name if alloc else 'N/A',
                'room_number': alloc.room.room_number if alloc else 'N/A',
                'bed_number': alloc.bed.bed_number if alloc else 'N/A',
                'phone': student.phone,
                'guardian_phone': student.guardian_phone,
                'destination': outpass.leave_application.destination if outpass.leave_application else 'N/A',
                'departure_date': outpass.departure_date.strftime('%d %b, %Y'),
                'expected_return_date': outpass.expected_return_date.strftime('%d %b, %Y'),
                'pass_status': outpass.status,
                'is_outside': outpass.is_outside
            }

        return jsonify(response_payload)

    # Standard Form Submit response
    if result['success']:
        flash(result['message'], 'success')
    else:
        flash(result['error'], 'danger')

    return redirect(url_for('security.scan', mode=event_type, gate=gate_location))


@security_bp.route('/transactions', endpoint='transactions')
@security_bp.route('/transactions-list', endpoint='transactions_list')
@login_required
@security_required
def transactions():
    """Security audit log of gate transactions with filters"""
    event_filter = request.args.get('event_type') or request.args.get('event', '')
    status_filter = request.args.get('status', '')
    search_query = request.args.get('q', '').strip()
    start_date = request.args.get('start_date', '').strip()
    end_date = request.args.get('end_date', '').strip()
    page = request.args.get('page', 1, type=int)

    query = GateTransaction.query.join(Student)

    if event_filter in ['EXIT', 'ENTRY']:
        query = query.filter(GateTransaction.event_type == event_filter)

    if status_filter in ['Success', 'Failed']:
        query = query.filter(GateTransaction.verification_status == status_filter)

    if start_date:
        try:
            query = query.filter(GateTransaction.scanned_at >= datetime.strptime(start_date, '%Y-%m-%d'))
        except ValueError:
            pass

    if end_date:
        try:
            query = query.filter(GateTransaction.scanned_at <= datetime.combine(datetime.strptime(end_date, '%Y-%m-%d'), time.max))
        except ValueError:
            pass

    if search_query:
        query = query.filter(
            (Student.full_name.ilike(f'%{search_query}%')) |
            (Student.enrollment_no.ilike(f'%{search_query}%')) |
            (GateTransaction.gate_location.ilike(f'%{search_query}%'))
        )

    transactions_paginated = query.order_by(GateTransaction.scanned_at.desc()).paginate(page=page, per_page=20, error_out=False)

    return render_template('security/transactions.html',
                           transactions=transactions_paginated,
                           event_type=event_filter,
                           status=status_filter,
                           start_date=start_date,
                           end_date=end_date,
                           query=search_query)


@security_bp.route('/outside', endpoint='outside')
@security_bp.route('/outside-list', endpoint='outside_list')
@login_required
@security_required
def outside():
    """Active roster of residents currently outside the hostel campus"""
    outside_passes = DigitalOutPass.query.filter_by(is_outside=True).order_by(DigitalOutPass.updated_at.desc()).all()
    return render_template('security/outside.html', outside_passes=outside_passes)

