-- =====================================================================
-- HOSTEL MANAGEMENT SYSTEM (HMS)
-- Database: hostel_db
-- Relational Database Schema (MySQL 8.0+)
-- Designed for B.Tech CSE AKTU Examination Standards
-- =====================================================================

-- Step 1: Create Database with UTF-8 Unicode Support
CREATE DATABASE IF NOT EXISTS `hostel_db`
CHARACTER SET utf8mb4
COLLATE utf8mb4_unicode_ci;

USE `hostel_db`;

-- Disable Foreign Key Checks during setup
SET FOREIGN_KEY_CHECKS = 0;

-- Drop tables if they already exist (Clean Migration Order)
DROP TABLE IF EXISTS `gate_transactions`;
DROP TABLE IF EXISTS `digital_out_passes`;
DROP TABLE IF EXISTS `notifications`;
DROP TABLE IF EXISTS `leave_applications`;
DROP TABLE IF EXISTS `complaint_responses`;
DROP TABLE IF EXISTS `complaints`;
DROP TABLE IF EXISTS `attendance`;
DROP TABLE IF EXISTS `fee_records`;
DROP TABLE IF EXISTS `allocations`;
DROP TABLE IF EXISTS `beds`;
DROP TABLE IF EXISTS `rooms`;
DROP TABLE IF EXISTS `wardens`;
DROP TABLE IF EXISTS `students`;
DROP TABLE IF EXISTS `notices`;
DROP TABLE IF EXISTS `users`;

-- =====================================================================
-- TABLE 1: users (Core Authentication & Role Management)
-- =====================================================================
CREATE TABLE `users` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `username` VARCHAR(50) NOT NULL UNIQUE,
    `email` VARCHAR(120) NOT NULL UNIQUE,
    `password_hash` VARCHAR(255) NOT NULL,
    `role` ENUM('admin', 'warden', 'student', 'security', 'parent') NOT NULL DEFAULT 'student',
    `is_active` BOOLEAN NOT NULL DEFAULT TRUE,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX `idx_users_role` (`role`),
    INDEX `idx_users_email` (`email`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- =====================================================================
-- TABLE 2: hostels (Hostel Buildings / Blocks)
-- =====================================================================
CREATE TABLE `hostels` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `name` VARCHAR(100) NOT NULL UNIQUE,
    `hostel_type` ENUM('boys', 'girls', 'co-ed') NOT NULL DEFAULT 'boys',
    `total_floors` INT NOT NULL DEFAULT 3,
    `total_rooms` INT NOT NULL DEFAULT 0,
    `description` VARCHAR(255) NULL,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- =====================================================================
-- TABLE 3: rooms (Rooms per Hostel & Floor)
-- =====================================================================
CREATE TABLE `rooms` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `hostel_id` INT NOT NULL,
    `room_number` VARCHAR(20) NOT NULL,
    `floor` INT NOT NULL DEFAULT 1,
    `room_type` ENUM('single', 'double', 'triple', 'four') NOT NULL DEFAULT 'double',
    `capacity` INT NOT NULL DEFAULT 2,
    `monthly_fee` DECIMAL(10, 2) NOT NULL DEFAULT 5000.00,
    `status` ENUM('active', 'maintenance') NOT NULL DEFAULT 'active',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY `unique_hostel_room` (`hostel_id`, `room_number`),
    CONSTRAINT `fk_rooms_hostel` FOREIGN KEY (`hostel_id`) 
        REFERENCES `hostels` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
    INDEX `idx_rooms_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- =====================================================================
-- TABLE 4: beds (Discrete Bed Units within Rooms)
-- =====================================================================
CREATE TABLE `beds` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `room_id` INT NOT NULL,
    `bed_number` VARCHAR(10) NOT NULL, -- e.g., 'Bed-A', 'Bed-B'
    `status` ENUM('available', 'occupied', 'maintenance') NOT NULL DEFAULT 'available',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY `unique_room_bed` (`room_id`, `bed_number`),
    CONSTRAINT `fk_beds_room` FOREIGN KEY (`room_id`) 
        REFERENCES `rooms` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
    INDEX `idx_beds_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- =====================================================================
-- TABLE 5: students (Student Profile Details)
-- =====================================================================
CREATE TABLE `students` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `user_id` INT NOT NULL UNIQUE,
    `enrollment_no` VARCHAR(30) NOT NULL UNIQUE,
    `roll_no` VARCHAR(30) NULL,
    `full_name` VARCHAR(100) NOT NULL,
    `phone` VARCHAR(15) NOT NULL,
    `gender` ENUM('male', 'female', 'other') NOT NULL DEFAULT 'male',
    `branch` VARCHAR(50) NOT NULL, -- e.g., 'Computer Science & Engineering'
    `year` INT NOT NULL DEFAULT 1, -- 1, 2, 3, 4
    `semester` INT NOT NULL DEFAULT 1,
    `guardian_name` VARCHAR(100) NOT NULL,
    `guardian_phone` VARCHAR(15) NOT NULL,
    `emergency_phone` VARCHAR(15) NULL,
    `address` TEXT NOT NULL,
    `blood_group` VARCHAR(10) NULL,
    `status` ENUM('active', 'suspended', 'vacated') NOT NULL DEFAULT 'active',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT `fk_students_user` FOREIGN KEY (`user_id`) 
        REFERENCES `users` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
    INDEX `idx_students_enrollment` (`enrollment_no`),
    INDEX `idx_students_branch` (`branch`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- =====================================================================
-- TABLE 6: wardens (Warden Profile & Assigned Hostels)
-- =====================================================================
CREATE TABLE `wardens` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `user_id` INT NOT NULL UNIQUE,
    `employee_id` VARCHAR(30) NOT NULL UNIQUE,
    `full_name` VARCHAR(100) NOT NULL,
    `phone` VARCHAR(15) NOT NULL,
    `designation` VARCHAR(50) NOT NULL DEFAULT 'Hostel Warden',
    `assigned_hostel_id` INT NULL,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT `fk_wardens_user` FOREIGN KEY (`user_id`) 
        REFERENCES `users` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT `fk_wardens_hostel` FOREIGN KEY (`assigned_hostel_id`) 
        REFERENCES `hostels` (`id`) ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- =====================================================================
-- TABLE 7: allocations (Room/Bed Allocation History & Current Status)
-- =====================================================================
CREATE TABLE `allocations` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `student_id` INT NOT NULL,
    `bed_id` INT NOT NULL,
    `room_id` INT NOT NULL,
    `hostel_id` INT NOT NULL,
    `allocated_from` DATE NOT NULL,
    `allocated_to` DATE NULL,
    `status` ENUM('active', 'vacated', 'transferred') NOT NULL DEFAULT 'active',
    `vacated_reason` VARCHAR(255) NULL,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT `fk_alloc_student` FOREIGN KEY (`student_id`) 
        REFERENCES `students` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT `fk_alloc_bed` FOREIGN KEY (`bed_id`) 
        REFERENCES `beds` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT `fk_alloc_room` FOREIGN KEY (`room_id`) 
        REFERENCES `rooms` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT `fk_alloc_hostel` FOREIGN KEY (`hostel_id`) 
        REFERENCES `hostels` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
    INDEX `idx_alloc_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- =====================================================================
-- TABLE 8: fee_records (Fee Ledger, Dues, and Payment Receipts)
-- =====================================================================
CREATE TABLE `fee_records` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `student_id` INT NOT NULL,
    `receipt_no` VARCHAR(50) NOT NULL UNIQUE,
    `amount` DECIMAL(10, 2) NOT NULL,
    `payment_date` DATE NOT NULL,
    `payment_method` ENUM('UPI', 'Cash', 'Net Banking', 'Cheque/DD') NOT NULL DEFAULT 'UPI',
    `transaction_id` VARCHAR(100) NULL,
    `fee_type` VARCHAR(50) NOT NULL DEFAULT 'Hostel & Mess Fee',
    `status` ENUM('paid', 'pending', 'overdue') NOT NULL DEFAULT 'paid',
    `remarks` VARCHAR(255) NULL,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT `fk_fees_student` FOREIGN KEY (`student_id`) 
        REFERENCES `students` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
    INDEX `idx_fees_status` (`status`),
    INDEX `idx_fees_receipt` (`receipt_no`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- =====================================================================
-- TABLE 9: attendance (Daily Student Night Roll-Call)
-- =====================================================================
CREATE TABLE `attendance` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `student_id` INT NOT NULL,
    `hostel_id` INT NOT NULL,
    `date` DATE NOT NULL,
    `status` ENUM('present', 'absent', 'leave') NOT NULL DEFAULT 'present',
    `marked_by_warden_id` INT NULL,
    `remarks` VARCHAR(200) NULL,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY `unique_student_date_att` (`student_id`, `date`),
    CONSTRAINT `fk_att_student` FOREIGN KEY (`student_id`) 
        REFERENCES `students` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT `fk_att_hostel` FOREIGN KEY (`hostel_id`) 
        REFERENCES `hostels` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT `fk_att_warden` FOREIGN KEY (`marked_by_warden_id`) 
        REFERENCES `wardens` (`id`) ON DELETE SET NULL ON UPDATE CASCADE,
    INDEX `idx_att_date` (`date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- =====================================================================
-- TABLE 10: complaints (Student Grievance Logging)
-- =====================================================================
CREATE TABLE `complaints` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `student_id` INT NOT NULL,
    `room_id` INT NULL,
    `title` VARCHAR(150) NOT NULL,
    `category` ENUM('electrical', 'plumbing', 'cleanliness', 'internet', 'mess', 'other') NOT NULL DEFAULT 'other',
    `priority` ENUM('low', 'medium', 'high', 'emergency') NOT NULL DEFAULT 'medium',
    `description` TEXT NOT NULL,
    `status` ENUM('pending', 'in_progress', 'resolved') NOT NULL DEFAULT 'pending',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT `fk_complaints_student` FOREIGN KEY (`student_id`) 
        REFERENCES `students` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT `fk_complaints_room` FOREIGN KEY (`room_id`) 
        REFERENCES `rooms` (`id`) ON DELETE SET NULL ON UPDATE CASCADE,
    INDEX `idx_complaints_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- =====================================================================
-- TABLE 11: complaint_responses (Audit Trail for Complaint Updates)
-- =====================================================================
CREATE TABLE `complaint_responses` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `complaint_id` INT NOT NULL,
    `responder_user_id` INT NOT NULL,
    `response_text` TEXT NOT NULL,
    `status_updated_to` ENUM('pending', 'in_progress', 'resolved') NOT NULL,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT `fk_cr_complaint` FOREIGN KEY (`complaint_id`) 
        REFERENCES `complaints` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT `fk_cr_user` FOREIGN KEY (`responder_user_id`) 
        REFERENCES `users` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- =====================================================================
-- TABLE 12: notices (Hostel Bulletins & Announcements)
-- =====================================================================
CREATE TABLE `notices` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `posted_by_user_id` INT NOT NULL,
    `title` VARCHAR(200) NOT NULL,
    `content` TEXT NOT NULL,
    `category` ENUM('announcement', 'event', 'urgent', 'maintenance') NOT NULL DEFAULT 'announcement',
    `target_audience` ENUM('all', 'boys', 'girls', 'wardens') NOT NULL DEFAULT 'all',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT `fk_notices_user` FOREIGN KEY (`posted_by_user_id`) 
        REFERENCES `users` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
    INDEX `idx_notices_target` (`target_audience`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- =====================================================================
-- TABLE 13: leave_applications (Student Out-Pass & Leave Requests)
-- =====================================================================
CREATE TABLE `leave_applications` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `student_id` INT NOT NULL,
    `hostel_id` INT NULL,
    `leave_type` VARCHAR(50) NOT NULL,
    `from_date` DATE NOT NULL,
    `to_date` DATE NOT NULL,
    `reason` TEXT NOT NULL,
    `destination` VARCHAR(255) NOT NULL,
    `emergency_contact` VARCHAR(20) NOT NULL,
    `supporting_document` VARCHAR(255) NULL,
    `status` ENUM('Pending', 'Approved', 'Rejected', 'Cancelled') NOT NULL DEFAULT 'Pending',
    `reviewed_by` INT NULL,
    `review_comment` TEXT NULL,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    `reviewed_at` DATETIME NULL,
    CONSTRAINT `fk_leave_student` FOREIGN KEY (`student_id`) 
        REFERENCES `students` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT `fk_leave_hostel` FOREIGN KEY (`hostel_id`) 
        REFERENCES `hostels` (`id`) ON DELETE SET NULL ON UPDATE CASCADE,
    CONSTRAINT `fk_leave_warden` FOREIGN KEY (`reviewed_by`) 
        REFERENCES `wardens` (`id`) ON DELETE SET NULL ON UPDATE CASCADE,
    INDEX `idx_leave_status` (`status`),
    INDEX `idx_leave_student` (`student_id`),
    INDEX `idx_leave_hostel` (`hostel_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- =====================================================================
-- TABLE 14: notifications (In-App Notification Feed)
-- =====================================================================
CREATE TABLE `notifications` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `user_id` INT NOT NULL,
    `title` VARCHAR(150) NOT NULL,
    `message` TEXT NOT NULL,
    `type` VARCHAR(20) NOT NULL DEFAULT 'info',
    `is_read` BOOLEAN NOT NULL DEFAULT FALSE,
    `link` VARCHAR(255) NULL,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT `fk_notifications_user` FOREIGN KEY (`user_id`) 
        REFERENCES `users` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
    INDEX `idx_notifications_user` (`user_id`),
    INDEX `idx_notifications_unread` (`is_read`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- =====================================================================
-- TABLE 15: digital_out_passes (Cryptographic QR Out-Passes)
-- =====================================================================
CREATE TABLE `digital_out_passes` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `pass_token_hash` VARCHAR(64) NOT NULL UNIQUE,
    `leave_application_id` INT NOT NULL,
    `student_id` INT NOT NULL,
    `hostel_id` INT NULL,
    `departure_date` DATE NOT NULL,
    `expected_return_date` DATE NOT NULL,
    `status` ENUM('Active', 'Used', 'Expired', 'Revoked', 'Completed') NOT NULL DEFAULT 'Active',
    `generated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `expires_at` DATETIME NOT NULL,
    `qr_code_path` VARCHAR(255) NULL,
    `is_outside` BOOLEAN NOT NULL DEFAULT FALSE,
    `actual_departure_time` DATETIME NULL,
    `actual_return_time` DATETIME NULL,
    `revoked_by` INT NULL,
    `revoked_at` DATETIME NULL,
    `revocation_reason` TEXT NULL,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT `fk_outpass_leave` FOREIGN KEY (`leave_application_id`) 
        REFERENCES `leave_applications` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT `fk_outpass_student` FOREIGN KEY (`student_id`) 
        REFERENCES `students` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT `fk_outpass_hostel` FOREIGN KEY (`hostel_id`) 
        REFERENCES `hostels` (`id`) ON DELETE SET NULL ON UPDATE CASCADE,
    CONSTRAINT `fk_outpass_revoker` FOREIGN KEY (`revoked_by`) 
        REFERENCES `users` (`id`) ON DELETE SET NULL ON UPDATE CASCADE,
    INDEX `idx_outpass_status` (`status`),
    INDEX `idx_outpass_student` (`student_id`),
    INDEX `idx_outpass_token_hash` (`pass_token_hash`),
    INDEX `idx_outpass_expires_at` (`expires_at`),
    INDEX `idx_outpass_outside` (`is_outside`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- =====================================================================
-- TABLE 16: gate_transactions (Security Gate Entry/Exit Audit Trail)
-- =====================================================================
CREATE TABLE `gate_transactions` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `outpass_id` INT NULL,
    `student_id` INT NOT NULL,
    `security_user_id` INT NOT NULL,
    `event_type` ENUM('EXIT', 'ENTRY') NOT NULL,
    `scanned_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `gate_location` VARCHAR(100) NOT NULL DEFAULT 'Main Campus Gate',
    `verification_status` ENUM('Success', 'Failed') NOT NULL DEFAULT 'Success',
    `is_overdue` BOOLEAN NOT NULL DEFAULT FALSE,
    `remarks` TEXT NULL,
    `failure_reason` VARCHAR(255) NULL,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT `fk_gate_outpass` FOREIGN KEY (`outpass_id`) 
        REFERENCES `digital_out_passes` (`id`) ON DELETE SET NULL ON UPDATE CASCADE,
    CONSTRAINT `fk_gate_student` FOREIGN KEY (`student_id`) 
        REFERENCES `students` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT `fk_gate_security` FOREIGN KEY (`security_user_id`) 
        REFERENCES `users` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
    INDEX `idx_gate_event_type` (`event_type`),
    INDEX `idx_gate_scanned_at` (`scanned_at`),
    INDEX `idx_gate_verification_status` (`verification_status`),
    INDEX `idx_gate_student` (`student_id`),
    INDEX `idx_gate_outpass` (`outpass_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- =====================================================================
-- TABLE 17: parent_profiles (Demographics & Verified Student Links)
-- =====================================================================
CREATE TABLE `parent_profiles` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `user_id` INT NOT NULL UNIQUE,
    `parent_name` VARCHAR(100) NOT NULL,
    `phone_number` VARCHAR(20) NOT NULL,
    `relationship_to_student` VARCHAR(50) NOT NULL DEFAULT 'Father',
    `student_id` INT NULL,
    `account_status` ENUM('active', 'inactive') NOT NULL DEFAULT 'active',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT `fk_parents_user` FOREIGN KEY (`user_id`) 
        REFERENCES `users` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT `fk_parents_student` FOREIGN KEY (`student_id`) 
        REFERENCES `students` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
    INDEX `idx_parents_student` (`student_id`),
    INDEX `idx_parents_status` (`account_status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- =====================================================================
-- TABLE 18: parent_inquiries (Direct Communication Desk to Warden)
-- =====================================================================
CREATE TABLE `parent_inquiries` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `parent_id` INT NOT NULL,
    `student_id` INT NOT NULL,
    `warden_id` INT NULL,
    `subject` VARCHAR(150) NOT NULL,
    `message` TEXT NOT NULL,
    `response` TEXT NULL,
    `responded_at` DATETIME NULL,
    `status` ENUM('Pending', 'In Progress', 'Resolved') NOT NULL DEFAULT 'Pending',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT `fk_inquiries_parent` FOREIGN KEY (`parent_id`) 
        REFERENCES `parent_profiles` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT `fk_inquiries_student` FOREIGN KEY (`student_id`) 
        REFERENCES `students` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT `fk_inquiries_warden` FOREIGN KEY (`warden_id`) 
        REFERENCES `wardens` (`id`) ON DELETE SET NULL ON UPDATE CASCADE,
    INDEX `idx_inquiries_parent` (`parent_id`),
    INDEX `idx_inquiries_student` (`student_id`),
    INDEX `idx_inquiries_warden` (`warden_id`),
    INDEX `idx_inquiries_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Re-enable Foreign Key Checks
SET FOREIGN_KEY_CHECKS = 1;

-- =====================================================================
-- Schema Complete
-- Total Tables: 18 (All with InnoDB Engine, UTF-8, FKs, and Indexes)
-- =====================================================================

