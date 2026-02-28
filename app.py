import pymysql
pymysql.install_as_MySQLdb()
#hell all
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_mysqldb import MySQL
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import date, timedelta, datetime
import math
#hi
app = Flask(__name__)
app.secret_key = 'attendsmart3_secret_2024'
 
#hi welcome boy
 
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = 'qwe123'     
app.config['MYSQL_DB'] = 'attendsmart3'

mysql = MySQL(app)

DAY_NAMES = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
SLOT_TIMES = ['8:00 AM', '9:00 AM', '10:00 AM', '11:00 AM', '12:00 PM',
              '1:00 PM',  '2:00 PM',  '3:00 PM',  '4:00 PM',  '5:00 PM']

# ─────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────

def get_user(user_id):
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM users WHERE id=%s", (user_id,))
    user = cur.fetchone()
    cur.close()
    return user

def get_subjects(user_id):
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM subjects WHERE user_id=%s ORDER BY subject_name", (user_id,))
    rows = cur.fetchall()
    cur.close()
    return rows

def get_day_timetable(user_id, day_of_week):
    """Get all timetable slots for a given day, ordered by period."""
    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT t.id, t.period_number, t.slot_label, t.is_free,
               t.subject_id, COALESCE(s.subject_name,'Free Hour') as subject_name
        FROM timetable t
        LEFT JOIN subjects s ON t.subject_id = s.id
        WHERE t.user_id=%s AND t.day_of_week=%s
        ORDER BY t.period_number
    """, (user_id, day_of_week))
    rows = cur.fetchall()
    cur.close()
    return rows

def count_class_dates(start_date, end_date, day_of_week):
    """Count how many times a weekday appeared from start to today."""
    today = date.today()
    cap = min(end_date, today)
    count = 0
    current = start_date
    while current <= cap:
        if current.weekday() == day_of_week:
            count += 1
        current += timedelta(days=1)
    return count

def count_future_dates(end_date, day_of_week):
    """Count future occurrences of a weekday from tomorrow to end."""
    tomorrow = date.today() + timedelta(days=1)
    count = 0
    current = tomorrow
    while current <= end_date:
        if current.weekday() == day_of_week:
            count += 1
        current += timedelta(days=1)
    return count

def predict(attended, total_held, future_classes):
    total_at_end = total_held + future_classes
    if total_at_end == 0:
        return {"current_pct": 0, "risk": "NO DATA", "can_miss": 0,
                "need_to_attend": 0, "best_possible_pct": 0,
                "message": "No classes scheduled.", "total_at_end": 0, "min_needed_at_end": 0}

    current_pct = round(attended / total_held * 100, 1) if total_held > 0 else 0
    best_possible_pct = round((attended + future_classes) / total_at_end * 100, 1)
    min_needed_at_end = math.ceil(0.75 * total_at_end)
    need_to_attend = max(0, min_needed_at_end - attended)
    can_miss = future_classes - need_to_attend

    if best_possible_pct < 75:
        risk = "DANGER"
        message = f"🚨 Cannot reach 75% even attending all remaining. Best possible: {best_possible_pct}%."
    elif can_miss <= 0:
        risk = "HIGH"
        message = f"⚠️ Must attend ALL {future_classes} remaining classes. Don't miss even one!"
    elif can_miss <= 2:
        risk = "HIGH"
        message = f"⚠️ Only {can_miss} more miss(es) allowed. Attend next {need_to_attend} without fail."
    elif can_miss <= 5:
        risk = "MEDIUM"
        message = f"🔶 Be careful! Can miss {can_miss} more. Still need {need_to_attend} more classes."
    else:
        risk = "SAFE"
        message = f"✅ You're safe! Can miss up to {can_miss} more classes and stay above 75%."

    return {
        "current_pct": current_pct,
        "risk": risk,
        "can_miss": max(0, can_miss),
        "need_to_attend": need_to_attend,
        "best_possible_pct": best_possible_pct,
        "message": message,
        "total_at_end": total_at_end,
        "min_needed_at_end": min_needed_at_end
    }

# ─────────────────────────────────────────────────────
# AUTH
# ─────────────────────────────────────────────────────

@app.route('/')
def home():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = generate_password_hash(request.form['password'])
        semester = request.form['semester']
        branch = request.form['branch']
        sem_start = request.form['semester_start']
        sem_end = request.form['semester_end']
        cur = mysql.connection.cursor()
        try:
            cur.execute("""
                INSERT INTO users (name,email,password,semester,branch,semester_start,semester_end)
                VALUES (%s,%s,%s,%s,%s,%s,%s)
            """, (name, email, password, semester, branch, sem_start, sem_end))
            mysql.connection.commit()
            flash('Registered! Please login.', 'success')
            return redirect(url_for('login'))
        except:
            flash('Email already exists!', 'error')
        finally:
            cur.close()
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM users WHERE email=%s", (email,))
        user = cur.fetchone()
        cur.close()
        if user and check_password_hash(user[3], password):
            session['user_id'] = user[0]
            session['user_name'] = user[1]
            if not user[8]:
                return redirect(url_for('setup_step1'))
            return redirect(url_for('dashboard'))
        flash('Invalid credentials!', 'error')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# ─────────────────────────────────────────────────────
# SETUP STEP 1: Total periods per day + which days have class
# ─────────────────────────────────────────────────────

@app.route('/setup/step1', methods=['GET', 'POST'])
def setup_step1():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        user_id = session['user_id']
        cur = mysql.connection.cursor()
        cur.execute("DELETE FROM day_config WHERE user_id=%s", (user_id,))

        for day_idx in range(6):  # Mon-Sat
            has_class = request.form.get(f'has_class_{day_idx}', '0')
            total_periods = request.form.get(f'periods_{day_idx}', '0')
            if has_class == '1' and int(total_periods) > 0:
                cur.execute("""
                    INSERT INTO day_config (user_id, day_of_week, total_periods, has_classes)
                    VALUES (%s,%s,%s,1)
                """, (user_id, day_idx, int(total_periods)))

        mysql.connection.commit()
        cur.close()
        return redirect(url_for('setup_step2'))

    return render_template('setup_step1.html', days=DAY_NAMES)

# ─────────────────────────────────────────────────────
# SETUP STEP 2: Add subjects
# ─────────────────────────────────────────────────────

@app.route('/setup/step2', methods=['GET', 'POST'])
def setup_step2():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']

    if request.method == 'POST':
        cur = mysql.connection.cursor()
        cur.execute("DELETE FROM subjects WHERE user_id=%s", (user_id,))
        mysql.connection.commit()

        names = request.form.getlist('subject_name')
        names = [n.strip() for n in names if n.strip()]

        for name in names:
            cur.execute("INSERT INTO subjects (user_id, subject_name) VALUES (%s,%s)", (user_id, name))
        mysql.connection.commit()
        cur.close()
        return redirect(url_for('setup_step3'))

    return render_template('setup_step2.html')

# ─────────────────────────────────────────────────────
# SETUP STEP 3: Fill timetable grid
# ─────────────────────────────────────────────────────

@app.route('/setup/step3', methods=['GET', 'POST'])
def setup_step3():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    cur = mysql.connection.cursor()

    if request.method == 'POST':
        cur.execute("DELETE FROM timetable WHERE user_id=%s", (user_id,))

        # Get day configs
        cur.execute("SELECT day_of_week, total_periods FROM day_config WHERE user_id=%s AND has_classes=1", (user_id,))
        day_configs = {row[0]: row[1] for row in cur.fetchall()}

        # Get subjects
        cur.execute("SELECT id, subject_name FROM subjects WHERE user_id=%s", (user_id,))
        subj_map = {row[1]: row[0] for row in cur.fetchall()}

        for day_idx, total_periods in day_configs.items():
            for period in range(1, total_periods + 1):
                slot_time = SLOT_TIMES[period - 1] if period <= len(SLOT_TIMES) else f"Period {period}"
                field = f"slot_{day_idx}_{period}"
                val = request.form.get(field, '').strip()

                if val == 'FREE':
                    # Free hour
                    cur.execute("""
                        INSERT INTO timetable (user_id, subject_id, day_of_week, period_number, slot_label, is_free)
                        VALUES (%s, NULL, %s, %s, %s, 1)
                    """, (user_id, day_idx, period, slot_time))
                elif val and val in subj_map:
                    cur.execute("""
                        INSERT INTO timetable (user_id, subject_id, day_of_week, period_number, slot_label, is_free)
                        VALUES (%s, %s, %s, %s, %s, 0)
                    """, (user_id, subj_map[val], day_idx, period, slot_time))

        cur.execute("UPDATE users SET setup_done=1 WHERE id=%s", (user_id,))
        mysql.connection.commit()
        cur.close()
        flash('Timetable saved! You are all set.', 'success')
        return redirect(url_for('dashboard'))

    # Load day configs and subjects for template
    cur.execute("SELECT day_of_week, total_periods FROM day_config WHERE user_id=%s AND has_classes=1 ORDER BY day_of_week", (user_id,))
    day_configs = cur.fetchall()

    cur.execute("SELECT id, subject_name FROM subjects WHERE user_id=%s ORDER BY subject_name", (user_id,))
    subjects = cur.fetchall()
    cur.close()

    return render_template('setup_step3.html',
        day_configs=day_configs,
        subjects=subjects,
        day_names=DAY_NAMES,
        slot_times=SLOT_TIMES
    )

# ─────────────────────────────────────────────────────
# DASHBOARD
# ─────────────────────────────────────────────────────

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    user = get_user(user_id)

    if not user[8]:
        return redirect(url_for('setup_step1'))

    sem_start = user[6]
    sem_end = user[7]
    today = date.today()

    cur = mysql.connection.cursor()

    # Today submitted?
    cur.execute("SELECT id FROM daily_submissions WHERE user_id=%s AND submission_date=%s", (user_id, today))
    today_submitted = cur.fetchone()

    # Today's class count
    cur.execute("""
        SELECT COUNT(*) FROM timetable t
        JOIN day_config dc ON dc.user_id=t.user_id AND dc.day_of_week=t.day_of_week
        WHERE t.user_id=%s AND t.day_of_week=%s AND dc.has_classes=1
    """, (user_id, today.weekday()))
    today_class_count = cur.fetchone()[0]

    # All subjects with prediction
    subjects = get_subjects(user_id)
    results = []

    for subj in subjects:
        subj_id = subj[0]

        # Total held: count how many timetable slots for this subject × days occurred
        cur.execute("SELECT day_of_week FROM timetable WHERE user_id=%s AND subject_id=%s", (user_id, subj_id))
        slot_days = cur.fetchall()

        total_held = 0
        future_classes = 0
        for (dow,) in slot_days:
            total_held += count_class_dates(sem_start, sem_end, dow)
            future_classes += count_future_dates(sem_end, dow)

        # Also count free hours where this subject was chosen
        cur.execute("""
            SELECT COUNT(*) FROM attendance
            WHERE user_id=%s AND free_subject_id=%s AND is_free_hour=1
            AND class_date BETWEEN %s AND %s
        """, (user_id, subj_id, sem_start, today))
        free_held = cur.fetchone()[0]
        total_held += free_held

        # Attended
        cur.execute("""
            SELECT COUNT(*) FROM attendance
            WHERE user_id=%s AND status='present'
            AND (subject_id=%s OR free_subject_id=%s)
        """, (user_id, subj_id, subj_id))
        attended = cur.fetchone()[0]

        pred = predict(attended, total_held, future_classes)

        results.append({
            "id": subj_id,
            "name": subj[2],
            "attended": attended,
            "total_held": total_held,
            "prediction": pred
        })

    danger = sum(1 for r in results if r['prediction']['risk'] == 'DANGER')
    high   = sum(1 for r in results if r['prediction']['risk'] == 'HIGH')
    safe   = sum(1 for r in results if r['prediction']['risk'] == 'SAFE')

    # Pending past dates
    cur.execute("SELECT submission_date FROM daily_submissions WHERE user_id=%s", (user_id,))
    submitted_dates = {row[0] for row in cur.fetchall()}
    cur.execute("SELECT DISTINCT day_of_week FROM timetable WHERE user_id=%s", (user_id,))
    tt_days = {row[0] for row in cur.fetchall()}
    pending_count = 0
    d = sem_start
    while d < today:
        if d.weekday() in tt_days and d not in submitted_dates:
            pending_count += 1
        d += timedelta(days=1)

    cur.close()

    is_saturday = today.weekday() == 5
    is_sunday   = today.weekday() == 6
    has_pending = today_class_count > 0 and not today_submitted and sem_start <= today <= sem_end
    # Saturday banner: only show on actual Saturday
    # Sunday: never show reminder
    # Weekdays Mon-Fri: show if pending
    if is_sunday:
        show_reminder = False
    else:
        show_reminder = has_pending

    return render_template('dashboard.html',
        user=user, results=results,
        today=today, today_class_count=today_class_count,
        today_submitted=today_submitted,
        show_reminder=show_reminder,
        is_saturday=is_saturday,
        danger=danger, high=high, safe=safe,
        pending_count=pending_count
    )

# ─────────────────────────────────────────────────────
# MARK ATTENDANCE FOR A DATE (Period by Period)
# ─────────────────────────────────────────────────────

@app.route('/mark', methods=['GET', 'POST'])
def mark_attendance():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    user = get_user(user_id)
    subjects = get_subjects(user_id)

    mark_date_str = request.args.get('date', date.today().isoformat())
    mark_date = date.fromisoformat(mark_date_str)
    day_of_week = mark_date.weekday()
    day_name = DAY_NAMES[day_of_week] if day_of_week < 6 else 'Sunday'
    is_saturday = (day_of_week == 5)

    cur = mysql.connection.cursor()

    # Already submitted?
    cur.execute("SELECT id FROM daily_submissions WHERE user_id=%s AND submission_date=%s", (user_id, mark_date))
    already_submitted = cur.fetchone()

    # Get timetable for this day
    slots = get_day_timetable(user_id, day_of_week)

    if not slots:
        flash(f'No classes scheduled on {day_name}!', 'error')
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        for slot in slots:
            tt_id = slot[0]
            period = slot[1]
            is_free = slot[3]
            original_subj_id = slot[4]

            status = request.form.get(f'status_{tt_id}', 'absent')

            if is_free:
                # Free hour: which subject took it?
                free_subj_id = request.form.get(f'free_subject_{tt_id}', None)
                skip = request.form.get(f'skip_free_{tt_id}', '0')

                if skip == '1' or not free_subj_id:
                    # No class happened in free hour
                    continue

                free_subj_id = int(free_subj_id)
                cur.execute("""
                    INSERT INTO attendance (user_id, subject_id, timetable_id, class_date, status, is_free_hour, free_subject_id)
                    VALUES (%s,%s,%s,%s,%s,1,%s)
                    ON DUPLICATE KEY UPDATE status=%s, free_subject_id=%s, marked_at=NOW()
                """, (user_id, free_subj_id, tt_id, mark_date, status, free_subj_id, status, free_subj_id))
            else:
                cur.execute("""
                    INSERT INTO attendance (user_id, subject_id, timetable_id, class_date, status, is_free_hour)
                    VALUES (%s,%s,%s,%s,%s,0)
                    ON DUPLICATE KEY UPDATE status=%s, marked_at=NOW()
                """, (user_id, original_subj_id, tt_id, mark_date, status, status))

        # Mark day submitted
        cur.execute("""
            INSERT IGNORE INTO daily_submissions (user_id, submission_date)
            VALUES (%s,%s)
        """, (user_id, mark_date))
        mysql.connection.commit()
        cur.close()
        flash(f'Attendance saved for {mark_date.strftime("%A, %d %b %Y")}! ✅', 'success')
        return redirect(url_for('dashboard'))

    # Load existing records for editing
    existing = {}
    free_chosen = {}
    for slot in slots:
        tt_id = slot[0]
        cur.execute("""
            SELECT status, free_subject_id FROM attendance
            WHERE user_id=%s AND timetable_id=%s AND class_date=%s
        """, (user_id, tt_id, mark_date))
        row = cur.fetchone()
        if row:
            existing[tt_id] = row[0]
            free_chosen[tt_id] = row[1]

    cur.close()

    return render_template('mark_attendance.html',
        slots=slots,
        mark_date=mark_date,
        day_name=day_name,
        is_saturday=is_saturday,
        already_submitted=already_submitted,
        existing=existing,
        free_chosen=free_chosen,
        subjects=subjects,
        user=user,
        today=date.today()
    )

# ─────────────────────────────────────────────────────
# PAST PENDING DATES
# ─────────────────────────────────────────────────────

@app.route('/past_dates')
def past_dates():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    user = get_user(user_id)
    sem_start = user[6]
    today = date.today()

    cur = mysql.connection.cursor()
    cur.execute("SELECT submission_date FROM daily_submissions WHERE user_id=%s", (user_id,))
    submitted = {row[0] for row in cur.fetchall()}
    cur.execute("SELECT DISTINCT day_of_week FROM timetable WHERE user_id=%s", (user_id,))
    tt_days = {row[0] for row in cur.fetchall()}
    cur.close()

    pending = []
    d = sem_start
    while d < today:
        if d.weekday() in tt_days and d not in submitted:
            pending.append(d)
        d += timedelta(days=1)

    return render_template('past_dates.html', pending_dates=pending[-30:], user=user)

# ─────────────────────────────────────────────────────
# VIEW TIMETABLE
# ─────────────────────────────────────────────────────

@app.route('/timetable')
def view_timetable():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    user = get_user(user_id)

    cur = mysql.connection.cursor()
    cur.execute("SELECT day_of_week, total_periods FROM day_config WHERE user_id=%s AND has_classes=1 ORDER BY day_of_week", (user_id,))
    day_configs = {row[0]: row[1] for row in cur.fetchall()}

    # Build grid: {day: {period: {name, is_free}}}
    grid = {}
    for day_idx in day_configs:
        grid[day_idx] = {}
        for p in range(1, day_configs[day_idx] + 1):
            grid[day_idx][p] = None

    cur.execute("""
        SELECT t.day_of_week, t.period_number, t.slot_label, t.is_free,
               COALESCE(s.subject_name,'Free Hour') as subject_name
        FROM timetable t
        LEFT JOIN subjects s ON t.subject_id=s.id
        WHERE t.user_id=%s ORDER BY t.day_of_week, t.period_number
    """, (user_id,))
    for row in cur.fetchall():
        dow, period, time_label, is_free, subj_name = row
        if dow in grid:
            grid[dow][period] = {"name": subj_name, "is_free": is_free, "time": time_label}

    cur.close()

    max_periods = max(day_configs.values()) if day_configs else 0

    return render_template('timetable.html',
        grid=grid,
        day_configs=day_configs,
        day_names=DAY_NAMES,
        max_periods=max_periods,
        user=user
    )

# ─────────────────────────────────────────────────────
# API
# ─────────────────────────────────────────────────────

@app.route('/api/today_status')
def today_status():
    if 'user_id' not in session:
        return jsonify({"has_classes": False, "submitted": False, "is_saturday": False})

    user_id = session['user_id']
    today = date.today()
    cur = mysql.connection.cursor()

    cur.execute("SELECT COUNT(*) FROM timetable WHERE user_id=%s AND day_of_week=%s", (user_id, today.weekday()))
    has_classes = cur.fetchone()[0] > 0

    cur.execute("SELECT id FROM daily_submissions WHERE user_id=%s AND submission_date=%s", (user_id, today))
    submitted = cur.fetchone() is not None
    cur.close()

    return jsonify({
        "has_classes": has_classes,
        "submitted": submitted,
        "is_saturday": today.weekday() == 5,
        "date": today.isoformat()
    })

@app.route('/api/chart/<int:subject_id>')
def chart_data(subject_id):
    if 'user_id' not in session:
        return jsonify({})
    user_id = session['user_id']
    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT class_date, status FROM attendance
        WHERE user_id=%s AND (subject_id=%s OR free_subject_id=%s)
        ORDER BY class_date ASC LIMIT 30
    """, (user_id, subject_id, subject_id))
    rows = cur.fetchall()
    cur.close()

    labels, pcts = [], []
    attended = total = 0
    for r in rows:
        total += 1
        if r[1] == 'present':
            attended += 1
        labels.append(str(r[0]))
        pcts.append(round(attended / total * 100, 1))

    return jsonify({"labels": labels, "pcts": pcts})

if __name__ == '__main__':
    app.run(debug=True)
