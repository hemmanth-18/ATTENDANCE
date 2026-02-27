CREATE DATABASE IF NOT EXISTS attendsmart3;
USE attendsmart3;

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
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS subjects (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    subject_name VARCHAR(100) NOT NULL,
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
    UNIQUE KEY unique_day (user_id, day_of_week),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
