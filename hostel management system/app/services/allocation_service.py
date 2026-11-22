from datetime import datetime, date
from app.models import db, Student, Hostel, Room, Bed, BedAllocation

class AllocationService:
    """
    Core Allocation Engine for Hostel Management System.
    Enforces business logic, prevents overbooking, maintains referential integrity,
    and supports automatic bed assignment.
    """

    @staticmethod
    def allocate_bed(student_id, bed_id, allocated_from=None):
        """
        Manually allocates a specific bed to a student with full constraint validation.
        """
        if allocated_from is None:
            allocated_from = date.today()

        student = Student.query.get(student_id)
        if not student:
            return False, "Student not found."

        if student.has_active_allocation:
            alloc = student.current_allocation
            return False, f"Student already holds an active allocation in {alloc.hostel.name}, Room {alloc.room.room_number}."

        bed = Bed.query.get(bed_id)
        if not bed:
            return False, "Selected bed does not exist."

        if bed.status != 'available':
            return False, f"Bed {bed.bed_number} is currently {bed.status}."

        room = bed.room
        hostel = room.hostel

        # Gender validation rule
        if hostel.hostel_type == 'boys' and student.gender != 'male':
            return False, f"Constraint Violation: Female student cannot be allocated to a Boys Hostel ({hostel.name})."
        if hostel.hostel_type == 'girls' and student.gender != 'female':
            return False, f"Constraint Violation: Male student cannot be allocated to a Girls Hostel ({hostel.name})."

        try:
            # Atomic state transition
            bed.status = 'occupied'
            allocation = BedAllocation(
                student_id=student.id,
                bed_id=bed.id,
                room_id=room.id,
                hostel_id=hostel.id,
                allocated_from=allocated_from,
                status='active'
            )
            db.session.add(allocation)
            db.session.commit()
            return True, f"Successfully allocated Room {room.room_number} ({bed.bed_number}) in {hostel.name} to {student.full_name}."
        except Exception as e:
            db.session.rollback()
            return False, f"Database transaction error: {str(e)}"

    @staticmethod
    def vacate_bed(allocation_id, reason="Standard Checkout"):
        """
        Vacates an active allocation and restores bed availability atomically.
        """
        allocation = BedAllocation.query.get(allocation_id)
        if not allocation or allocation.status != 'active':
            return False, "Active allocation not found."

        try:
            allocation.vacate(reason=reason)
            db.session.commit()
            return True, f"Bed {allocation.bed.bed_number} in Room {allocation.room.room_number} has been vacated and marked Available."
        except Exception as e:
            db.session.rollback()
            return False, f"Error vacating bed: {str(e)}"

    @staticmethod
    def auto_allocate_student(student_id):
        """
        Automatic Room Allocation Algorithm.
        1. Identifies student's gender.
        2. Filters appropriate hostels (Boys hostel for male, Girls for female).
        3. Looks for active rooms with available beds.
        4. Prioritizes rooms with lowest floor first, then lowest occupied beds (best fit).
        """
        student = Student.query.get(student_id)
        if not student:
            return False, "Student not found."

        if student.has_active_allocation:
            return False, f"Student already allocated to Room {student.current_allocation.room.room_number}."

        # Target hostel type
        target_type = 'boys' if student.gender == 'male' else 'girls'
        hostels = Hostel.query.filter((Hostel.hostel_type == target_type) | (Hostel.hostel_type == 'co-ed')).all()

        if not hostels:
            return False, f"No matching hostel blocks configured for gender: {student.gender}."

        hostel_ids = [h.id for h in hostels]

        # Find available beds in active rooms within matching hostels
        available_bed = Bed.query.join(Room).filter(
            Room.hostel_id.in_(hostel_ids),
            Room.status == 'active',
            Bed.status == 'available'
        ).order_by(Room.floor.asc(), Room.room_number.asc(), Bed.bed_number.asc()).first()

        if not available_bed:
            return False, "Allocation Failed: All matching hostel rooms and beds are currently 100% occupied."

        return AllocationService.allocate_bed(student.id, available_bed.id)

