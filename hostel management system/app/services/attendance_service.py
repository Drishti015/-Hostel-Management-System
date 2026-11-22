from datetime import date
from app.models import db, Attendance, Student, Hostel

class AttendanceService:
    """Service handling daily night roll-call attendance processing"""

    @staticmethod
    def record_roll_call(hostel_id, roll_date, status_dict, marked_by_warden_id=None):
        """
        Records or updates attendance for a list of students on a specific date.
        status_dict format: {student_id: 'present' | 'absent' | 'leave'}
        """
        records_processed = 0
        for student_id_str, status in status_dict.items():
            student_id = int(student_id_str)
            student = Student.query.get(student_id)
            if not student:
                continue

            # Check if record already exists for this date and student (upsert)
            existing = Attendance.query.filter_by(student_id=student.id, date=roll_date).first()
            if existing:
                existing.status = status
                existing.marked_by_warden_id = marked_by_warden_id
            else:
                att = Attendance(
                    student_id=student.id,
                    hostel_id=hostel_id,
                    date=roll_date,
                    status=status,
                    marked_by_warden_id=marked_by_warden_id
                )
                db.session.add(att)
            records_processed += 1

        db.session.commit()
        return records_processed

    @staticmethod
    def get_hostel_attendance_for_date(hostel_id, roll_date):
        """
        Returns list of active students in the hostel paired with their attendance status on that date.
        """
        hostel = Hostel.query.get(hostel_id)
        if not hostel:
            return []

        # Active students allocated to this hostel
        students = [
            alloc.student for alloc in hostel.allocations.filter_by(status='active').all()
            if alloc.student.status == 'active'
        ]

        # Existing marked records
        existing_records = {
            a.student_id: a.status for a in Attendance.query.filter_by(hostel_id=hostel_id, date=roll_date).all()
        }

        result = []
        for s in students:
            result.append({
                'student': s,
                'status': existing_records.get(s.id, 'present') # Default to present for quick marking
            })
        return result

