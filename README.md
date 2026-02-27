# 📊 AttendSmart v2 — Timetable-Based Attendance Predictor

## How It Works
1. Register → Enter semester start & end date
2. Setup timetable → Add subjects + assign to day/time slots
3. Every day at 9 PM → App asks you to mark attendance for all classes that day
4. Dashboard → Auto calculates all percentages and predictions based on your timetable

## Setup

```bash
pip install -r requirements.txt
mysql -u root -p < database.sql
# Edit MYSQL_PASSWORD in app.py
python app.py
```
Open: http://localhost:5000

## Features
- Timetable grid setup (Mon-Sat, 10 time slots)
- Auto calculates total classes held based on semester start date + timetable
- 9 PM browser popup reminder to mark attendance
- Mark all today's classes in one screen (Present/Absent toggle)
- Mark missed past dates from "Past Dates" page
- Dashboard with risk prediction per subject
- Trend chart per subject
- Safe / Medium / High / Danger risk levels with smart messages
