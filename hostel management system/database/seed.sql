-- =====================================================================
-- HOSTEL MANAGEMENT SYSTEM (HMS)
-- Seed Data for Testing & AKTU Practical Demonstration
-- =====================================================================

USE `hostel_db`;

-- 1. Insert Base Users (Passwords: Admin@123, Warden@123, Student@123)
-- Uses Werkzeug scrypt hash
INSERT INTO `users` (`id`, `username`, `email`, `password_hash`, `role`, `is_active`) VALUES
(1, 'admin', 'admin@aktu-hostel.edu.in', 'scrypt:32768:8:1$fgyJZdJi3m05Iaij$a6144a6eec8e75b06e3d3b0739ef5defcb8a32fcb3e2fdacbdd3034b7c4b3d7a9e0ba233120dbafaaff5c0579d438a9966faca0bb38346504f8bcf59defdb1eb', 'admin', 1),
(2, 'warden_boys', 'warden.boys@aktu-hostel.edu.in', 'scrypt:32768:8:1$t4IEdIceyR9IMs5o$2aecd48348ae933ea673aeabf7a8c5f5e85f5e41d7ac5585038a56972ec8b3b04e13d4521ef7a8943748a24ce7c48028d769b8d9264f63016ac9af70fbfc6cef', 'warden', 1),
(3, 'warden_girls', 'warden.girls@aktu-hostel.edu.in', 'scrypt:32768:8:1$t4IEdIceyR9IMs5o$2aecd48348ae933ea673aeabf7a8c5f5e85f5e41d7ac5585038a56972ec8b3b04e13d4521ef7a8943748a24ce7c48028d769b8d9264f63016ac9af70fbfc6cef', 'warden', 1),
(4, 'rahul_sharma', 'rahul.cse@aktu.ac.in', 'scrypt:32768:8:1$V0gT5egRISKpi5qV$ff88ff00e328309233085d92f2136808105cd111e2e8dc6fb8e65c52913b398f49138a9be9e86e3a503fccd36fdc5d5b66ce7f927df3e0ed5dabbc2933ae02a8', 'student', 1),
(5, 'priya_verma', 'priya.it@aktu.ac.in', 'scrypt:32768:8:1$V0gT5egRISKpi5qV$ff88ff00e328309233085d92f2136808105cd111e2e8dc6fb8e65c52913b398f49138a9be9e86e3a503fccd36fdc5d5b66ce7f927df3e0ed5dabbc2933ae02a8', 'student', 1),
(6, 'amit_kumar', 'amit.ece@aktu.ac.in', 'scrypt:32768:8:1$V0gT5egRISKpi5qV$ff88ff00e328309233085d92f2136808105cd111e2e8dc6fb8e65c52913b398f49138a9be9e86e3a503fccd36fdc5d5b66ce7f927df3e0ed5dabbc2933ae02a8', 'student', 1);

-- 2. Insert Hostels
INSERT INTO `hostels` (`id`, `name`, `hostel_type`, `total_floors`, `total_rooms`, `description`) VALUES
(1, 'Aryabhatta Boys Hostel (Block A)', 'boys', 3, 15, 'Main Boys Hostel campus block with Wi-Fi and solar geyser facility'),
(2, 'Gargi Girls Hostel (Block B)', 'girls', 3, 12, 'Girls Hostel block with 24/7 security and reading hall');

-- 3. Insert Wardens
INSERT INTO `wardens` (`id`, `user_id`, `employee_id`, `full_name`, `phone`, `designation`, `assigned_hostel_id`) VALUES
(1, 2, 'EMP-WRD-001', 'Dr. Ramesh Chandra', '+91 9876543210', 'Senior Chief Warden', 1),
(2, 3, 'EMP-WRD-002', 'Prof. Sunita Mishra', '+91 9876543211', 'Associate Warden', 2);

-- 4. Insert Students
INSERT INTO `students` (`id`, `user_id`, `enrollment_no`, `roll_no`, `full_name`, `phone`, `gender`, `branch`, `year`, `semester`, `guardian_name`, `guardian_phone`, `emergency_phone`, `address`, `blood_group`, `status`) VALUES
(1, 4, 'AKTU2023CSE0101', '23000101001', 'Rahul Sharma', '+91 9123456780', 'male', 'Computer Science & Engineering', 3, 5, 'Mr. Suresh Sharma', '+91 9123456789', '+91 9123456789', 'H.No 45, Civil Lines, Prayagraj, UP', 'B+', 'active'),
(2, 5, 'AKTU2023IT0204', '23000102004', 'Priya Verma', '+91 9123456781', 'female', 'Information Technology', 2, 3, 'Mr. Vinod Verma', '+91 9123456788', '+91 9123456788', 'Sector 12, Indiranagar, Lucknow, UP', 'O+', 'active'),
(3, 6, 'AKTU2023ECE0315', '23000103015', 'Amit Kumar', '+91 9123456782', 'male', 'Electronics & Communication', 3, 5, 'Mr. Rajender Kumar', '+91 9123456787', '+91 9123456787', 'Near Clock Tower, Kanpur, UP', 'A+', 'active');

-- 5. Insert Sample Rooms
INSERT INTO `rooms` (`id`, `hostel_id`, `room_number`, `floor`, `room_type`, `capacity`, `monthly_fee`, `status`) VALUES
(1, 1, 'A-101', 1, 'double', 2, 4500.00, 'active'),
(2, 1, 'A-102', 1, 'double', 2, 4500.00, 'active'),
(3, 1, 'A-103', 1, 'single', 1, 6000.00, 'active'),
(4, 2, 'B-101', 1, 'double', 2, 4500.00, 'active'),
(5, 2, 'B-102', 1, 'triple', 3, 3800.00, 'active');

-- 6. Insert Beds for Rooms
INSERT INTO `beds` (`id`, `room_id`, `bed_number`, `status`) VALUES
(1, 1, 'A-101-Bed1', 'occupied'),
(2, 1, 'A-101-Bed2', 'available'),
(3, 2, 'A-102-Bed1', 'occupied'),
(4, 2, 'A-102-Bed2', 'available'),
(5, 3, 'A-103-Bed1', 'available'),
(6, 4, 'B-101-Bed1', 'occupied'),
(7, 4, 'B-101-Bed2', 'available'),
(8, 5, 'B-102-Bed1', 'available'),
(9, 5, 'B-102-Bed2', 'available'),
(10, 5, 'B-102-Bed3', 'available');

-- 7. Insert Active Allocations
INSERT INTO `allocations` (`id`, `student_id`, `bed_id`, `room_id`, `hostel_id`, `allocated_from`, `allocated_to`, `status`) VALUES
(1, 1, 1, 1, 1, '2026-08-01', NULL, 'active'),
(2, 2, 6, 4, 2, '2026-08-01', NULL, 'active'),
(3, 3, 3, 2, 1, '2026-08-01', NULL, 'active');

-- 8. Insert Fee Records
INSERT INTO `fee_records` (`id`, `student_id`, `receipt_no`, `amount`, `payment_date`, `payment_method`, `transaction_id`, `fee_type`, `status`, `remarks`) VALUES
(1, 1, 'REC-2026-001', 27000.00, '2026-08-05', 'UPI', 'UPI/20260805123498/SBI', 'Hostel & Mess Fee (Semester 5)', 'paid', 'Semester fee paid successfully'),
(2, 2, 'REC-2026-002', 27000.00, '2026-08-06', 'Net Banking', 'HDFC-NB-98127391', 'Hostel & Mess Fee (Semester 3)', 'paid', 'Verified by accounts'),
(3, 3, 'REC-2026-003', 15000.00, '2026-08-10', 'UPI', 'UPI/20260810998822/PNB', 'Hostel Fee (1st Installment)', 'paid', 'Balance Rs 12,000 pending');

-- 9. Insert Sample Attendance
INSERT INTO `attendance` (`id`, `student_id`, `hostel_id`, `date`, `status`, `marked_by_warden_id`, `remarks`) VALUES
(1, 1, 1, '2026-11-20', 'present', 1, 'Present in room A-101'),
(2, 2, 2, '2026-11-20', 'present', 2, 'Present in room B-101'),
(3, 3, 1, '2026-11-20', 'present', 1, 'Present in room A-102'),
(4, 1, 1, '2026-11-21', 'present', 1, 'Present'),
(5, 2, 2, '2026-11-21', 'leave', 2, 'Approved gate pass to hometown'),
(6, 3, 1, '2026-11-21', 'absent', 1, 'Late return reported');

-- 10. Insert Sample Complaints
INSERT INTO `complaints` (`id`, `student_id`, `room_id`, `title`, `category`, `priority`, `description`, `status`) VALUES
(1, 1, 1, 'Ceiling fan making squeaking noise', 'electrical', 'medium', 'The fan regulator works but the fan produces high squeaking noise during night hours.', 'in_progress'),
(2, 2, 4, 'Bathroom water tap leaking continuously', 'plumbing', 'high', 'Tap in attached washroom is continuously dripping water and needs washer replacement.', 'pending'),
(3, 3, 2, 'Wi-Fi connectivity fluctuating', 'internet', 'low', 'Signal strength in corner desk is very low on 5GHz band.', 'resolved');

-- 11. Insert Complaint Response
INSERT INTO `complaint_responses` (`id`, `complaint_id`, `responder_user_id`, `response_text`, `status_updated_to`) VALUES
(1, 1, 2, 'Electrician informed. He will visit today between 4 PM and 6 PM.', 'in_progress'),
(2, 3, 2, 'Network team added an extra access point on 1st Floor corridor. Issue resolved.', 'resolved');

-- 12. Insert Sample Notices
INSERT INTO `notices` (`id`, `posted_by_user_id`, `title`, `content`, `category`, `target_audience`) VALUES
(1, 1, 'Hostel Mess Menu Revision for Winter Semester', 'Dear Students, the revised mess committee menu will come into effect from next Monday. Please review the noticeboard for daily schedules.', 'announcement', 'all'),
(2, 2, 'Night Curfew & Gate Closing Timing Notice', 'All boys hostel residents are strictly advised to report back by 9:30 PM. Late entries without prior warden approval will incur disciplinary fines.', 'urgent', 'boys'),
(3, 1, 'Periodic Electrical Maintenance Inspection', 'Routine inspection of power backup and room switchboards will be conducted on Saturday from 10:00 AM to 2:00 PM.', 'maintenance', 'all');

