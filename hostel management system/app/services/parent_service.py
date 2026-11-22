from datetime import datetime, date, timedelta
from app.models import db, Student, ParentProfile, DigitalOutPass, GateTransaction, LeaveApplication, Attendance, FeeRecord, Notice
from app.services.fee_service import FeeService
from app.services.notification_service import NotificationService

class ParentService:
    """Business logic service for Parent Portal data aggregation and movement monitoring"""

    @staticmethod
    def get_student_movement_status(student_id):
        """
        Determines real-time movement status of a student based on actual Gate transactions
        and DigitalOutPass records.
        """
        outpass = DigitalOutPass.query.filter_by(student_id=student_id).order_by(DigitalOutPass.created_at.desc()).first()
        last_txn = GateTransaction.query.filter_by(student_id=student_id).order_by(GateTransaction.scanned_at.desc()).first()

        now = datetime.utcnow()

        if outpass and outpass.is_outside:
            if now > outpass.expires_at:
                return {
                    'code': 'OVERDUE',
                    'badge_text': 'Overdue Return',
                    'badge_class': 'bg-danger text-white',
                    'icon': 'fa-triangle-exclamation',
                    'description': f'Student is currently OUTSIDE and exceeded the expected return date ({outpass.expected_return_date.strftime("%d %b, %Y")}).',
                    'outpass': outpass,
                    'last_txn': last_txn,
                    'is_outside': True
                }
            else:
                dep_time_str = outpass.actual_departure_time.strftime("%d %b at %I:%M %p") if outpass.actual_departure_time else "Recently"
                return {
                    'code': 'OUTSIDE',
                    'badge_text': 'Currently Outside Hostel',
                    'badge_class': 'bg-warning text-dark',
                    'icon': 'fa-person-walking-arrow-right',
                    'description': f'Student departed campus on {dep_time_str}. Expected return: {outpass.expected_return_date.strftime("%d %b, %Y")}.',
                    'outpass': outpass,
                    'last_txn': last_txn,
                    'is_outside': True
                }
        elif outpass and outpass.status == 'Active' and not outpass.actual_departure_time and outpass.departure_date >= date.today():
            return {
                'code': 'APPROVED_PENDING_EXIT',
                'badge_text': 'Leave Approved – Not Yet Exited',
                'badge_class': 'bg-info text-dark',
                'icon': 'fa-id-card',
                'description': f'Out-Pass #{outpass.id} is approved for departure on {outpass.departure_date.strftime("%d %b, %Y")}. Gate exit not yet recorded.',
                'outpass': outpass,
                'last_txn': last_txn,
                'is_outside': False
            }
        elif outpass and outpass.status == 'Completed' and outpass.actual_return_time and (now - outpass.actual_return_time).total_seconds() < 86400 * 3:
            ret_time_str = outpass.actual_return_time.strftime("%d %b at %I:%M %p")
            return {
                'code': 'RETURNED',
                'badge_text': 'Returned Successfully',
                'badge_class': 'bg-success text-white',
                'icon': 'fa-circle-check',
                'description': f'Student safely checked back in at campus gate on {ret_time_str}. Currently inside hostel.',
                'outpass': outpass,
                'last_txn': last_txn,
                'is_outside': False
            }
        else:
            return {
                'code': 'INSIDE',
                'badge_text': 'Currently Inside Hostel',
                'badge_class': 'bg-success text-white',
                'icon': 'fa-house-user',
                'description': 'Student is resident and currently inside the hostel premises.',
                'outpass': outpass,
                'last_txn': last_txn,
                'is_outside': False
            }

    @staticmethod
    def get_parent_dashboard_data(parent_profile):
        """
        Gathers complete, aggregated dashboard statistics and recent activity feeds
        for a verified parent profile.
        """
        if not parent_profile or not parent_profile.student_id or not parent_profile.is_active:
            return None

        student = parent_profile.student
        if not student:
            return None

        allocation = student.current_allocation
        hostel = allocation.hostel if allocation else None
        room = allocation.room if allocation else None
        bed = allocation.bed if allocation else None

        # Primary warden
        warden = hostel.wardens.first() if (hostel and hostel.wardens) else None

        # Movement status
        movement = ParentService.get_student_movement_status(student.id)

        # Attendance calculation
        total_days = student.attendance_records.count()
        present_days = student.attendance_records.filter_by(status='present').count()
        absent_days = student.attendance_records.filter_by(status='absent').count()
        leave_days = student.attendance_records.filter_by(status='leave').count()
        attendance_pct = student.attendance_percentage

        # Fee calculations
        fee_summary = FeeService.get_student_fee_summary(student.id) or {
            'total_fee': 27000.0,
            'total_paid': 0.0,
            'balance_due': 27000.0,
            'status': 'Due',
            'records': []
        }

        # Leave summary
        total_leaves = student.leave_applications.count()
        pending_leaves = student.leave_applications.filter_by(status='Pending').count()
        approved_leaves = student.leave_applications.filter_by(status='Approved').count()
        rejected_leaves = student.leave_applications.filter_by(status='Rejected').count()

        # Recent activities
        recent_leaves = student.leave_applications.order_by(LeaveApplication.created_at.desc()).limit(5).all()
        recent_txns = GateTransaction.query.filter_by(student_id=student.id).order_by(GateTransaction.scanned_at.desc()).limit(5).all()
        recent_attendance = student.attendance_records.order_by(Attendance.date.desc()).limit(7).all()
        recent_fees = student.fee_records.order_by(FeeRecord.payment_date.desc()).limit(3).all()
        recent_notices = Notice.query.order_by(Notice.created_at.desc()).limit(4).all()

        return {
            'student': student,
            'allocation': allocation,
            'hostel': hostel,
            'room': room,
            'bed': bed,
            'warden': warden,
            'movement': movement,
            'attendance': {
                'total_days': total_days,
                'present_days': present_days,
                'absent_days': absent_days,
                'leave_days': leave_days,
                'percentage': attendance_pct
            },
            'fees': fee_summary,
            'leaves': {
                'total': total_leaves,
                'pending': pending_leaves,
                'approved': approved_leaves,
                'rejected': rejected_leaves
            },
            'recent_leaves': recent_leaves,
            'recent_transactions': recent_txns,
            'recent_attendance': recent_attendance,
            'recent_fees': recent_fees,
            'recent_notices': recent_notices
        }

    @staticmethod
    def notify_parents_of_student(student_id, title, message, type='info', link=None):
        """
        Dispatches in-app notifications to all active verified parents linked to a student.
        """
        if not student_id:
            return 0

        parents = ParentProfile.query.filter_by(student_id=student_id, account_status='active').all()
        count = 0
        for p in parents:
            if p.user_account and p.user_account.is_active:
                NotificationService.create_notification(
                    user_id=p.user_id,
                    title=title,
                    message=message,
                    type=type,
                    link=link
                )
                count += 1
        if count > 0:
            db.session.commit()
        return count

