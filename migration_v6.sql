-- V6 MIGRATION: Add semester_id to subjects, timetable, day_config
-- This makes each semester have isolated data, fixing the attendance loss bug

-- Add semester_id columns (nullable for backward compat)
ALTER TABLE subjects ADD COLUMN IF NOT EXISTS semester_id INT DEFAULT NULL;
ALTER TABLE timetable ADD COLUMN IF NOT EXISTS semester_id INT DEFAULT NULL;
ALTER TABLE day_config ADD COLUMN IF NOT EXISTS semester_id INT DEFAULT NULL;

-- Drop old unique constraints that don't account for semester_id
ALTER TABLE day_config DROP INDEX IF EXISTS unique_day;

-- Add new unique constraints including semester_id
ALTER TABLE day_config ADD UNIQUE KEY IF NOT EXISTS unique_day_sem (user_id, day_of_week, semester_id);

-- Backfill: assign existing subjects/timetable/day_config to user's active semester
UPDATE subjects s
JOIN semesters sem ON sem.user_id = s.user_id AND sem.is_active = 1
SET s.semester_id = sem.id
WHERE s.semester_id IS NULL;

UPDATE timetable t
JOIN semesters sem ON sem.user_id = t.user_id AND sem.is_active = 1
SET t.semester_id = sem.id
WHERE t.semester_id IS NULL;

UPDATE day_config dc
JOIN semesters sem ON sem.user_id = dc.user_id AND sem.is_active = 1
SET dc.semester_id = sem.id
WHERE dc.semester_id IS NULL;
