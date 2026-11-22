import os
import secrets
import hashlib
import hmac
from datetime import datetime, date, time, timedelta
import qrcode
from flask import current_app
from app.models import db, DigitalOutPass, GateTransaction, LeaveApplication, Student, Hostel
from app.services.notification_service import NotificationService

class OutPassService:
    """Core Business Logic Service for Digital Out-Pass Lifecycle and Gate Verification"""

    @staticmethod
    def generate_outpass(leave_application, custom_token=None):
        """
        Generates a secure digital out-pass for an approved leave application.
        Only approved leaves are eligible. Prevents duplicate passes for the same leave.
        """
        if not leave_application or leave_application.status != 'Approved':
            return None

        # Check for existing pass
        existing = DigitalOutPass.query.filter_by(leave_application_id=leave_application.id).first()
        if existing:
            return existing

        # Generate cryptographically secure random token (32 bytes url-safe)
        raw_token = custom_token if custom_token else secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode('utf-8')).hexdigest()

        # Expiration deadline: expected return date at 23:59:59 + 2 hours grace period (01:59:59 next day)
        return_datetime = datetime.combine(leave_application.to_date, time(23, 59, 59))
        expires_at = return_datetime + timedelta(hours=2)

        # Generate QR code image
        upload_base = current_app.config.get('UPLOAD_FOLDER', os.path.join(current_app.root_path, 'static', 'uploads'))
        qr_dir = os.path.join(upload_base, 'qrcodes')
        os.makedirs(qr_dir, exist_ok=True)
        qr_filename = f"outpass_{leave_application.student_id}_{int(datetime.utcnow().timestamp())}_{secrets.token_hex(4)}.png"
        qr_path = os.path.join(qr_dir, qr_filename)

        # The QR payload contains only the secure verification token with standard protocol prefix
        qr_payload = f"HOSTELPASS:{raw_token}"
        qr_img = qrcode.make(qr_payload, box_size=8, border=2)
        qr_img.save(qr_path)

        outpass = DigitalOutPass(
            leave_application_id=leave_application.id,
            student_id=leave_application.student_id,
            pass_token_hash=token_hash,
            departure_date=leave_application.from_date,
            expected_return_date=leave_application.to_date,
            generated_at=datetime.utcnow(),
            expires_at=expires_at,
            qr_code_file=qr_filename,
            status='Active'
        )
        db.session.add(outpass)
        db.session.commit()

        # Notify student
        NotificationService.create_notification(
            user_id=leave_application.student.user_id,
            title='Digital Out-Pass Issued',
            message=f'Your official Digital Out-Pass (#PASS-{outpass.id}) with QR code is ready for departure on {outpass.departure_date.strftime("%d %b, %Y")}.',
            type='success',
            link=f'/student/outpasses/{outpass.id}'
        )
        db.session.commit()

        outpass.raw_token = raw_token
        return outpass

    @staticmethod
    def verify_and_record_scan(raw_token_input, guard_user_id, gate_location='Main Campus Gate', expected_event_type=None, remarks=None):
        """
        Server-side QR verification engine for security gate terminals.
        Validates token hash, enforces exit/entry constraints, updates out-pass state,
        and logs GateTransaction audit trail.
        """
        if not raw_token_input:
            return {
                'success': False,
                'error': 'Missing or empty verification token.',
                'code': 'INVALID_TOKEN'
            }

        # Strip protocol prefix if scanned from QR code
        cleaned_token = raw_token_input.strip()
        if cleaned_token.startswith('HOSTELPASS:'):
            cleaned_token = cleaned_token[len('HOSTELPASS:'):].strip()

        if not cleaned_token:
            return {
                'success': False,
                'error': 'Invalid QR code token content.',
                'code': 'EMPTY_TOKEN'
            }

        computed_hash = hashlib.sha256(cleaned_token.encode('utf-8')).hexdigest()

        # Retrieve out-pass by secure token hash
        outpass = DigitalOutPass.query.filter_by(pass_token_hash=computed_hash).first()
        if not outpass:
            return {
                'success': False,
                'error': 'Access Denied: Unrecognized or invalid QR out-pass code.',
                'code': 'NOT_FOUND'
            }

        # Constant-time comparison check
        if not hmac.compare_digest(outpass.pass_token_hash, computed_hash):
            return {
                'success': False,
                'error': 'Security Verification Failed: Token signature integrity error.',
                'code': 'SIGNATURE_MISMATCH'
            }

        student = outpass.student
        leave = outpass.leave_application

        # 1. Verify associated leave application is approved
        if leave.status != 'Approved':
            return {
                'success': False,
                'error': f'Access Denied: Associated leave application is {leave.status}, not Approved.',
                'code': 'LEAVE_NOT_APPROVED',
                'outpass': outpass,
                'student': student
            }

        # 2. Check revocation status
        if outpass.status == 'Revoked':
            return {
                'success': False,
                'error': f'Access Denied: This Out-Pass was REVOKED by warden ({outpass.revoked_reason or "Disciplinary / Administrative hold"}).',
                'code': 'PASS_REVOKED',
                'outpass': outpass,
                'student': student
            }

        today_date = date.today()
        target_event = expected_event_type.upper() if expected_event_type else ('ENTRY' if outpass.is_outside else 'EXIT')

        if target_event == 'EXIT':
            # EXIT VALIDATIONS:
            # 1. Student must not already be outside
            if outpass.is_outside:
                return {
                    'success': False,
                    'error': f'Duplicate Exit Denied: Student {student.full_name} is already logged as OUTSIDE campus.',
                    'code': 'ALREADY_OUTSIDE',
                    'outpass': outpass,
                    'student': student
                }

            # 2. Pass cannot be reused after completion
            if outpass.status == 'Completed':
                return {
                    'success': False,
                    'error': 'Access Denied: Out-Pass has already completed its round-trip entry cycle.',
                    'code': 'ALREADY_COMPLETED',
                    'outpass': outpass,
                    'student': student
                }

            # 3. Departure date constraint
            if today_date < outpass.departure_date:
                return {
                    'success': False,
                    'error': f'Premature Departure Denied: Out-Pass is valid starting {outpass.departure_date.strftime("%d %b, %Y")}.',
                    'code': 'PREMATURE_DEPARTURE',
                    'outpass': outpass,
                    'student': student
                }

            # 4. Expiration check for new departures
            if outpass.is_expired:
                outpass.status = 'Expired'
                db.session.commit()
                return {
                    'success': False,
                    'error': f'Access Denied: Out-Pass expired on {outpass.expires_at.strftime("%d %b, %Y at %I:%M %p")}. Cannot initiate departure.',
                    'code': 'PASS_EXPIRED',
                    'outpass': outpass,
                    'student': student
                }

            # Execute EXIT
            tx = GateTransaction(
                outpass_id=outpass.id,
                student_id=student.id,
                security_user_id=guard_user_id,
                event_type='EXIT',
                scanned_at=datetime.utcnow(),
                gate_location=gate_location,
                verification_status='Success',
                remarks=remarks or 'Campus exit verified at gate'
            )
            outpass.is_outside = True
            outpass.actual_departure_time = tx.scanned_at
            outpass.status = 'Used'
            outpass.updated_at = datetime.utcnow()
            db.session.add(tx)
            db.session.commit()

            # Notifications
            NotificationService.create_notification(
                user_id=student.user_id,
                title='Campus Exit Recorded',
                message=f'Your campus departure via {gate_location} was recorded on {tx.scanned_at.strftime("%d %b at %I:%M %p")}. Return deadline: {outpass.expected_return_date.strftime("%d %b, %Y")}.',
                type='info',
                link=f'/student/outpasses/{outpass.id}'
            )
            # Notify linked parents
            from app.services.parent_service import ParentService
            ParentService.notify_parents_of_student(
                student_id=student.id,
                title='Campus Exit Recorded',
                message=f'Student {student.full_name} departed campus via {gate_location} on {tx.scanned_at.strftime("%d %b at %I:%M %p")}. Expected return: {outpass.expected_return_date.strftime("%d %b, %Y")}.',
                type='info',
                link=f'/parent/outpasses/{outpass.id}'
            )
            if leave.hostel:
                for warden in leave.hostel.wardens:
                    NotificationService.create_notification(
                        user_id=warden.user_id,
                        title='Resident Campus Exit',
                        message=f'Resident {student.full_name} ({leave.hostel.name}) departed through {gate_location}.',
                        type='info',
                        link='/warden/outpasses'
                    )
            db.session.commit()

            return {
                'success': True,
                'event_type': 'EXIT',
                'code': 'EXIT_APPROVED',
                'message': 'EXIT APPROVED: Student departure authorized and logged.',
                'outpass': outpass,
                'student': student,
                'transaction': tx
            }

        elif target_event == 'ENTRY':
            # ENTRY VALIDATIONS:
            # 1. Student must have checked out previously
            if not outpass.is_outside:
                return {
                    'success': False,
                    'error': f'Invalid Entry: Student {student.full_name} does not have an active exit transaction logged.',
                    'code': 'NOT_OUTSIDE',
                    'outpass': outpass,
                    'student': student
                }

            is_overdue = datetime.utcnow() > outpass.expires_at
            entry_remarks = remarks or ('Late return recorded by security' if is_overdue else 'Normal campus entry')

            # Execute ENTRY
            tx = GateTransaction(
                outpass_id=outpass.id,
                student_id=student.id,
                security_user_id=guard_user_id,
                event_type='ENTRY',
                scanned_at=datetime.utcnow(),
                gate_location=gate_location,
                verification_status='Success',
                remarks=entry_remarks
            )
            outpass.is_outside = False
            outpass.actual_return_time = tx.scanned_at
            outpass.status = 'Completed'
            outpass.updated_at = datetime.utcnow()
            db.session.add(tx)
            db.session.commit()

            # Notifications
            NotificationService.create_notification(
                user_id=student.user_id,
                title='Campus Return Recorded' + (' (Late Arrival)' if is_overdue else ''),
                message=f'Your return through {gate_location} was recorded on {tx.scanned_at.strftime("%d %b at %I:%M %p")}. Out-pass #{outpass.id} is now Completed.',
                type='warning' if is_overdue else 'success',
                link=f'/student/outpasses/{outpass.id}'
            )
            # Notify linked parents
            from app.services.parent_service import ParentService
            ParentService.notify_parents_of_student(
                student_id=student.id,
                title='Campus Return Recorded' + (' [OVERDUE]' if is_overdue else ''),
                message=f'Student {student.full_name} safely checked back in at {gate_location} on {tx.scanned_at.strftime("%d %b at %I:%M %p")}.' + (' [Note: Late Arrival Recorded]' if is_overdue else ''),
                type='warning' if is_overdue else 'success',
                link=f'/parent/outpasses/{outpass.id}'
            )
            if leave.hostel:
                for warden in leave.hostel.wardens:
                    NotificationService.create_notification(
                        user_id=warden.user_id,
                        title='Resident Campus Return' + (' [OVERDUE]' if is_overdue else ''),
                        message=f'Resident {student.full_name} ({leave.hostel.name}) returned via {gate_location}' + (' AFTER return deadline.' if is_overdue else '.'),
                        type='warning' if is_overdue else 'success',
                        link='/warden/outpasses'
                    )
            db.session.commit()

            return {
                'success': True,
                'event_type': 'ENTRY',
                'code': 'ENTRY_APPROVED',
                'is_overdue': is_overdue,
                'message': 'ENTRY APPROVED: Student campus return authorized and completed.' + (' [NOTE: Late Return Logged]' if is_overdue else ''),
                'outpass': outpass,
                'student': student,
                'transaction': tx
            }

        return {
            'success': False,
            'error': f'Unrecognized transaction event: {target_event}',
            'code': 'INVALID_EVENT'
        }

    @staticmethod
    def revoke_outpass(outpass_id, revoked_by_warden_id, reason):
        """Allows wardens to revoke an active outpass with mandatory justification"""
        if isinstance(outpass_id, DigitalOutPass):
            outpass = outpass_id
        else:
            outpass = DigitalOutPass.query.get(outpass_id)
        if not outpass:
            return False, 'Out-Pass not found.'

        if outpass.status in ['Completed', 'Revoked']:
            return False, f'Cannot revoke a pass that is already {outpass.status}.'

        outpass.status = 'Revoked'
        outpass.revoked_reason = reason
        outpass.revoked_at = datetime.utcnow()
        outpass.updated_at = datetime.utcnow()
        db.session.commit()

        # Notify student
        NotificationService.create_notification(
            user_id=outpass.student.user_id,
            title='Out-Pass Revoked',
            message=f'Your Out-Pass #{outpass.id} has been REVOKED by hostel administration. Reason: {reason}',
            type='danger',
            link=f'/student/outpasses/{outpass.id}'
        )
        db.session.commit()
        return True, 'Out-Pass revoked successfully.'

    @staticmethod
    def get_today_metrics():
        """Returns statistics of today's gate traffic for security dashboard"""
        today_start = datetime.combine(date.today(), time.min)
        today_end = datetime.combine(date.today(), time.max)

        exits_today = GateTransaction.query.filter(
            GateTransaction.event_type == 'EXIT',
            GateTransaction.verification_status == 'Success',
            GateTransaction.scanned_at >= today_start,
            GateTransaction.scanned_at <= today_end
        ).count()

        entries_today = GateTransaction.query.filter(
            GateTransaction.event_type == 'ENTRY',
            GateTransaction.verification_status == 'Success',
            GateTransaction.scanned_at >= today_start,
            GateTransaction.scanned_at <= today_end
        ).count()

        currently_outside = DigitalOutPass.query.filter_by(is_outside=True).count()

        # Overdue students: currently outside and past expires_at
        overdue_count = DigitalOutPass.query.filter(
            DigitalOutPass.is_outside == True,
            DigitalOutPass.expires_at < datetime.utcnow()
        ).count()

        return {
            'exits_today': exits_today,
            'entries_today': entries_today,
            'currently_outside': currently_outside,
            'outside_count': currently_outside,
            'overdue_count': overdue_count,
            'overdue_students': overdue_count
        }

    @staticmethod
    def check_and_update_expired_passes():
        """Flags non-outside expired passes as Expired"""
        now = datetime.utcnow()
        DigitalOutPass.query.filter(
            DigitalOutPass.status == 'Active',
            DigitalOutPass.is_outside == False,
            DigitalOutPass.expires_at < now
        ).update({'status': 'Expired', 'updated_at': now})
        db.session.commit()

