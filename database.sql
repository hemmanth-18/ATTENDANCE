CREATE DATABASE IF NOT EXISTS attendsmart3;
USE attendsmart3;
drop database attendsmart3;
CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    password VARCHAR(255) NOT NULL,
    semester INT DEFAULT 1,
    branch VARCHAR(100),
    semester_start DATE NOT NULL,
    semester_end DATE NOT NULL,
    setup_done TINYINT DEFAULT 0,
    total_semesters INT DEFAULT 8,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
select * from users;
ALTER TABLE users ADD COLUMN photo VARCHAR(255) DEFAULT NULL;
CREATE TABLE IF NOT EXISTS subjects (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    subject_name VARCHAR(100) NOT NULL,
    semester_id INT DEFAULT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Timetable slots
-- is_free = 1 means this is a Free Hour (optional, subject decided on the day)
-- day_of_week: 0=Mon,1=Tue,2=Wed,3=Thu,4=Fri,5=Sat
CREATE TABLE IF NOT EXISTS timetable (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    subject_id INT,                  -- NULL if free hour
    day_of_week INT NOT NULL,
    period_number INT NOT NULL,      -- 1,2,3...
    slot_label VARCHAR(20) DEFAULT '',
    is_free TINYINT DEFAULT 0,       -- 1 = free hour
    semester_id INT DEFAULT NULL,    -- links to semesters.id
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (subject_id) REFERENCES subjects(id) ON DELETE CASCADE
);

-- Attendance per class per date
-- free_subject_id: which subject actually took the free hour that day (nullable)
CREATE TABLE IF NOT EXISTS attendance (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    subject_id INT NOT NULL,          -- actual subject (could be free hour replacement)
    timetable_id INT NOT NULL,        -- which slot
    class_date DATE NOT NULL,
    status ENUM('present','absent') NOT NULL DEFAULT 'absent',
    is_free_hour TINYINT DEFAULT 0,
    free_subject_id INT DEFAULT NULL, -- which subject took free hour
    marked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY unique_class (user_id, timetable_id, class_date),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (subject_id) REFERENCES subjects(id) ON DELETE CASCADE
);

-- Track which days are fully submitted
CREATE TABLE IF NOT EXISTS daily_submissions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    submission_date DATE NOT NULL,
    submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY unique_submission (user_id, submission_date),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Day config: total periods per day
CREATE TABLE IF NOT EXISTS day_config (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    day_of_week INT NOT NULL,         -- 0=Mon ... 5=Sat
    total_periods INT NOT NULL DEFAULT 5,
    has_classes TINYINT DEFAULT 1,
    semester_id INT DEFAULT NULL,     -- links to semesters.id
    UNIQUE KEY unique_day_sem (user_id, day_of_week, semester_id),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Saturday working day config (per specific date, not per weekday)
CREATE TABLE IF NOT EXISTS saturday_config (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    sat_date DATE NOT NULL,
    is_working TINYINT DEFAULT 1,    -- 1=working day, 0=holiday
    total_periods INT DEFAULT 0,
    UNIQUE KEY unique_sat (user_id, sat_date),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Custom period-to-subject mapping for a specific Saturday
-- is_free = 1 means this period is a Free Hour (subject_id will be NULL)
CREATE TABLE IF NOT EXISTS saturday_slots (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    sat_date DATE NOT NULL,
    period_number INT NOT NULL,
    subject_id INT DEFAULT NULL,      -- NULL if free hour
    slot_label VARCHAR(20) DEFAULT '',
    is_free TINYINT DEFAULT 0,        -- 1 = free hour
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (subject_id) REFERENCES subjects(id) ON DELETE CASCADE
);

-- ─────────────────────────────────────────────────────
-- MIGRATION: Run this if upgrading an existing database
-- ─────────────────────────────────────────────────────
-- ALTER TABLE saturday_slots MODIFY COLUMN subject_id INT DEFAULT NULL;
-- ALTER TABLE saturday_slots ADD COLUMN IF NOT EXISTS is_free TINYINT DEFAULT 0;

-- ─────────────────────────────────────────────────────
-- PROFILE & MULTI-SEMESTER SUPPORT
-- ─────────────────────────────────────────────────────

-- Add profile photo to users
-- ALTER TABLE users ADD COLUMN IF NOT EXISTS photo VARCHAR(255) DEFAULT NULL;
	
-- Semesters table: each user can have multiple semesters
-- The "active" semester is used for current dashboard calculations
CREATE TABLE IF NOT EXISTS semesters (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    semester_number INT NOT NULL,       -- e.g. 1, 2, 3...
    semester_label VARCHAR(50) DEFAULT '', -- e.g. "Sem 3 - 2025"
    branch VARCHAR(100),
    sem_start DATE NOT NULL,
    sem_end DATE NOT NULL,
    is_active TINYINT DEFAULT 0,        -- 1 = currently active semester
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- MIGRATION for existing databases:
-- ALTER TABLE users ADD COLUMN IF NOT EXISTS photo VARCHAR(255) DEFAULT NULL;
-- INSERT INTO semesters (user_id, semester_number, semester_label, branch, sem_start, sem_end, is_active)
-- SELECT id, semester, CONCAT('Sem ', semester, ' (migrated)'), branch, semester_start, semester_end, 1
-- FROM users WHERE setup_done=1;

-- ─────────────────────────────────────────────────────
-- SEMESTER SNAPSHOTS: stores subjects+timetable per semester
-- so switching back to a previous semester restores its data
-- ─────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS semester_snapshots (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    semester_id INT NOT NULL,
    record_type ENUM('subject','day_config','timetable') NOT NULL,
    meta1 VARCHAR(255) DEFAULT NULL,  -- subject_name / day_of_week / subject_name
    meta2 VARCHAR(50)  DEFAULT NULL,  -- total_periods / day_of_week
    meta3 VARCHAR(50)  DEFAULT NULL,  -- period_number
    meta4 VARCHAR(50)  DEFAULT NULL,  -- slot_label
    meta5 VARCHAR(10)  DEFAULT NULL,  -- is_free
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- ─────────────────────────────────────────────────────
-- V6 MIGRATION: Run these if upgrading from V5 or earlier
-- Adds semester_id to subjects, timetable, day_config for full per-semester isolation
-- This fixes the bug where switching semesters lost all attendance data
-- ─────────────────────────────────────────────────────
-- ALTER TABLE subjects ADD COLUMN IF NOT EXISTS semester_id INT DEFAULT NULL;
-- ALTER TABLE timetable ADD COLUMN IF NOT EXISTS semester_id INT DEFAULT NULL;
-- ALTER TABLE day_config ADD COLUMN IF NOT EXISTS semester_id INT DEFAULT NULL;
-- ALTER TABLE day_config DROP INDEX IF EXISTS unique_day;
-- ALTER TABLE day_config ADD UNIQUE KEY IF NOT EXISTS unique_day_sem (user_id, day_of_week, semester_id);
-- Backfill existing data to the active semester:
-- UPDATE subjects s JOIN semesters sem ON sem.user_id = s.user_id AND sem.is_active = 1 SET s.semester_id = sem.id WHERE s.semester_id IS NULL;
-- UPDATE timetable t JOIN semesters sem ON sem.user_id = t.user_id AND sem.is_active = 1 SET t.semester_id = sem.id WHERE t.semester_id IS NULL;
-- UPDATE day_config dc JOIN semesters sem ON sem.user_id = dc.user_id AND sem.is_active = 1 SET dc.semester_id = sem.id WHERE dc.semester_id IS NULL;
