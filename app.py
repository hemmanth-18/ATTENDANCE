import pymysql
pymysql.install_as_MySQLdb()
#hell all
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_mysqldb import MySQL
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import date, timedelta, datetime
import math
#importing math
app = Flask(__name__)
app.secret_key = 'attendsmart3_secret_2024'

app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = 'qwe123'     # ← change this
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

def validate_session():
    """Returns user if session valid, else clears stale session and returns None."""
    if 'user_id' not in session:
        return None
    user = get_user(session['user_id'])
    if not user:
        session.clear()
        return None
    return user

def get_subjects(user_id):
    cur = mysql.connection.cursor()
    # Only select id, subject_name — SELECT * returns (id, user_id, subject_name)
    # which causes subj[1] to be user_id instead of the name
    cur.execute("SELECT id, subject_name FROM subjects WHERE user_id=%s ORDER BY subject_name", (user_id,))
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

    current_pct = min(100.0, round(attended / total_held * 100, 1)) if total_held > 0 else 0
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
        # Validate required fields
        if not sem_start or not sem_end:
            flash('Please fill in semester start and end dates!', 'error')
            return render_template('register.html')
        cur = mysql.connection.cursor()
        try:
            cur.execute("""
                INSERT INTO users (name,email,password,semester,branch,semester_start,semester_end)
                VALUES (%s,%s,%s,%s,%s,%s,%s)
            """, (name, email, password, semester, branch, sem_start, sem_end))
            mysql.connection.commit()
            flash('Registered! Please login.', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            mysql.connection.rollback()
            flash('Email already exists or invalid data. Please try again.', 'error')
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
    user = validate_session()
    if not user:
        return redirect(url_for('login'))
    user_id = user[0]

    if request.method == 'POST':
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
    user = validate_session()
    if not user:
        return redirect(url_for('login'))
    user_id = user[0]

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
    user = validate_session()
    if not user:
        return redirect(url_for('login'))
    user_id = user[0]
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
    user = validate_session()
    if not user:
        return redirect(url_for('login'))
    user_id = user[0]

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
    is_saturday = today.weekday() == 5
    if is_saturday:
        # For Saturday, check saturday_slots for today's date
        cur.execute("""
            SELECT COUNT(*) FROM saturday_slots
            WHERE user_id=%s AND sat_date=%s
        """, (user_id, today))
        today_class_count = cur.fetchone()[0]
        # If no slots set yet, check if saturday_config says working
        if today_class_count == 0:
            cur.execute("""
                SELECT is_working, total_periods FROM saturday_config
                WHERE user_id=%s AND sat_date=%s
            """, (user_id, today))
            sat_cfg = cur.fetchone()
            today_class_count = sat_cfg[1] if sat_cfg and sat_cfg[0] == 1 else -1
            # -1 means Saturday not yet configured — needs the saturday_check flow
    else:
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

        # Count free hours (weekday + saturday) where this subject was chosen
        cur.execute("""
            SELECT COUNT(*) FROM attendance
            WHERE user_id=%s AND free_subject_id=%s AND is_free_hour=1
            AND class_date BETWEEN %s AND %s
        """, (user_id, subj_id, sem_start, today))
        free_held = cur.fetchone()[0]
        total_held += free_held

        # Count Saturday regular slots for this subject (from saturday_slots, not attendance)
        # Only count Saturdays that were actually submitted (working day confirmed)
        cur.execute("""
            SELECT COUNT(*) FROM saturday_slots ss
            JOIN saturday_config sc ON ss.user_id=sc.user_id AND ss.sat_date=sc.sat_date
            JOIN daily_submissions ds ON ss.user_id=ds.user_id AND ss.sat_date=ds.submission_date
            WHERE ss.user_id=%s AND ss.subject_id=%s AND ss.is_free=0
            AND sc.is_working=1
            AND ss.sat_date BETWEEN %s AND %s
        """, (user_id, subj_id, sem_start, today))
        sat_held = cur.fetchone()[0]
        total_held += sat_held

        # Attended: weekday regular + saturday regular + free hours (weekday+sat)
        cur.execute("""
            SELECT COUNT(*) FROM attendance
            WHERE user_id=%s AND status='present'
            AND subject_id=%s AND is_free_hour=0
        """, (user_id, subj_id))
        attended_regular = cur.fetchone()[0]

        cur.execute("""
            SELECT COUNT(*) FROM attendance
            WHERE user_id=%s AND status='present'
            AND free_subject_id=%s AND is_free_hour=1
        """, (user_id, subj_id))
        attended_free = cur.fetchone()[0]

        attended = attended_regular + attended_free
        # Cap attended at total_held to prevent > 100%
        attended = min(attended, total_held)

        pred = predict(attended, total_held, future_classes)

        results.append({
            "id": subj_id,
            "name": subj[1],
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
    # Get all Saturdays that were configured as working days
    cur.execute("""
        SELECT sat_date FROM saturday_config
        WHERE user_id=%s AND is_working=1 AND sat_date < %s
    """, (user_id, today))
    working_saturdays = {row[0] for row in cur.fetchall()}
    pending_count = 0
    d = sem_start
    while d < today:
        if d not in submitted_dates:
            if d.weekday() in tt_days:  # regular weekday with class
                pending_count += 1
            elif d in working_saturdays:  # Saturday that was a working day
                pending_count += 1
        d += timedelta(days=1)

    cur.close()

    is_sunday = today.weekday() == 6
    # Saturday: show reminder if not yet submitted AND (slots configured OR not configured yet)
    # today_class_count == -1 means Saturday not configured yet → still show reminder to prompt user
    if is_saturday:
        has_pending = not today_submitted and sem_start <= today <= sem_end
        show_saturday_prompt = today_class_count == -1 and not today_submitted and sem_start <= today <= sem_end
    else:
        has_pending = today_class_count > 0 and not today_submitted and sem_start <= today <= sem_end
        show_saturday_prompt = False

    if is_sunday:
        show_reminder = False
    else:
        show_reminder = has_pending

    return render_template('dashboard.html',
        user=user, results=results,
        today=today, today_class_count=today_class_count,
        today_submitted=today_submitted,
        show_reminder=show_reminder,
        show_saturday_prompt=show_saturday_prompt,
        is_saturday=is_saturday,
        danger=danger, high=high, safe=safe,
        pending_count=pending_count
    )

# ─────────────────────────────────────────────────────
# MARK ATTENDANCE FOR A DATE (Period by Period)
# ─────────────────────────────────────────────────────

@app.route('/mark', methods=['GET', 'POST'])
def mark_attendance():
    user = validate_session()
    if not user:
        return redirect(url_for('login'))
    user_id = user[0]
    subjects = get_subjects(user_id)
    # subjects_dict {id: name} — safe lookup in templates, avoids tuple index bugs
    subjects_dict = {s[0]: s[1] for s in subjects}

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
            is_free = slot[3]
            original_subj_id = slot[4]

            status = request.form.get(f'status_{tt_id}', 'absent')

            if is_free:
                # Free hour: which subject took it?
                free_subj_id = request.form.get(f'free_subject_{tt_id}', None)
                skip = request.form.get(f'skip_free_{tt_id}', '0')

                if skip == '1' or not free_subj_id:
                    continue  # no class happened in free hour

                free_subj_id = int(free_subj_id)
                cur.execute("""
                    INSERT INTO attendance (user_id, subject_id, timetable_id, class_date, status, is_free_hour, free_subject_id)
                    VALUES (%s,%s,%s,%s,%s,1,%s)
                    ON DUPLICATE KEY UPDATE status=%s, free_subject_id=%s, marked_at=NOW()
                """, (user_id, free_subj_id, tt_id, mark_date, status, free_subj_id, status, free_subj_id))
            else:
                # Substitution: did a different teacher take this period?
                sub_val = request.form.get(f'sub_subject_{tt_id}', '')
                actual_subj_id = int(sub_val) if sub_val else original_subj_id
                # store substituted id in free_subject_id column so we can show it later
                sub_record = actual_subj_id if actual_subj_id != original_subj_id else None
                cur.execute("""
                    INSERT INTO attendance (user_id, subject_id, timetable_id, class_date, status, is_free_hour, free_subject_id)
                    VALUES (%s,%s,%s,%s,%s,0,%s)
                    ON DUPLICATE KEY UPDATE status=%s, subject_id=%s, free_subject_id=%s, marked_at=NOW()
                """, (user_id, actual_subj_id, tt_id, mark_date, status, sub_record,
                       status, actual_subj_id, sub_record))

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
    sub_chosen = {}  # which subject actually taught each regular period (for substitution display)
    for slot in slots:
        tt_id = slot[0]
        orig_id = slot[4]
        cur.execute("""
            SELECT status, free_subject_id, subject_id FROM attendance
            WHERE user_id=%s AND timetable_id=%s AND class_date=%s
        """, (user_id, tt_id, mark_date))
        row = cur.fetchone()
        if row:
            existing[tt_id] = row[0]
            free_chosen[tt_id] = row[1]
            sub_chosen[tt_id] = row[2]  # actual subject that taught this period

    cur.close()

    return render_template('mark_attendance.html',
        slots=slots,
        mark_date=mark_date,
        day_name=day_name,
        is_saturday=is_saturday,
        already_submitted=already_submitted,
        existing=existing,
        free_chosen=free_chosen,
        sub_chosen=sub_chosen,
        subjects=subjects,
        subjects_dict=subjects_dict,
        user=user,
        today=date.today()
    )

# ─────────────────────────────────────────────────────
# PAST PENDING DATES
# ─────────────────────────────────────────────────────

@app.route('/past_dates')
def past_dates():
    user = validate_session()
    if not user:
        return redirect(url_for('login'))
    user_id = user[0]
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
    user = validate_session()
    if not user:
        return redirect(url_for('login'))
    user_id = user[0]

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
# SATURDAY: Working day check + custom subject entry
# ─────────────────────────────────────────────────────

@app.route('/saturday', methods=['GET', 'POST'])
def saturday_check():
    user = validate_session()
    if not user:
        return redirect(url_for('login'))
    user_id = user[0]
    subjects = get_subjects(user_id)
    subjects_dict = {s[0]: s[1] for s in subjects}

    mark_date_str = request.args.get('date', date.today().isoformat())
    mark_date = date.fromisoformat(mark_date_str)

    cur = mysql.connection.cursor()

    # Load existing config for this Saturday if already set
    cur.execute("SELECT is_working, total_periods FROM saturday_config WHERE user_id=%s AND sat_date=%s",
                (user_id, mark_date))
    existing_config = cur.fetchone()

    existing_slots = []
    if existing_config and existing_config[0] == 1:
        cur.execute("""
            SELECT ss.id, ss.period_number, ss.slot_label, ss.subject_id, COALESCE(s.subject_name,'Free Hour') as subject_name, ss.is_free
            FROM saturday_slots ss LEFT JOIN subjects s ON ss.subject_id=s.id
            WHERE ss.user_id=%s AND ss.sat_date=%s ORDER BY ss.period_number
        """, (user_id, mark_date))
        existing_slots = cur.fetchall()

    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'holiday':
            cur.execute("""
                INSERT INTO saturday_config (user_id, sat_date, is_working, total_periods)
                VALUES (%s,%s,0,0)
                ON DUPLICATE KEY UPDATE is_working=0, total_periods=0
            """, (user_id, mark_date))
            # Mark as submitted so it won't show as pending
            cur.execute("INSERT IGNORE INTO daily_submissions (user_id, submission_date) VALUES (%s,%s)",
                        (user_id, mark_date))
            mysql.connection.commit()
            cur.close()
            flash(f'{mark_date.strftime("%d %b %Y")} marked as holiday — no attendance needed. 🏖️', 'success')
            return redirect(url_for('dashboard'))

        elif action == 'working':
            total_periods = int(request.form.get('total_periods', 0))
            if total_periods == 0:
                flash('Please select number of periods!', 'error')
                cur.close()
                return redirect(url_for('saturday_check', date=mark_date_str))

            cur.execute("""
                INSERT INTO saturday_config (user_id, sat_date, is_working, total_periods)
                VALUES (%s,%s,1,%s)
                ON DUPLICATE KEY UPDATE is_working=1, total_periods=%s
            """, (user_id, mark_date, total_periods, total_periods))

            # Clear old slots and insert new ones
            cur.execute("DELETE FROM saturday_slots WHERE user_id=%s AND sat_date=%s", (user_id, mark_date))
            for p in range(1, total_periods + 1):
                subj_id = request.form.get(f'period_{p}_subject', '')
                slot_label = SLOT_TIMES[p - 1] if p <= len(SLOT_TIMES) else f'Period {p}'
                if subj_id == 'FREE':
                    cur.execute("""
                        INSERT INTO saturday_slots (user_id, sat_date, period_number, subject_id, slot_label, is_free)
                        VALUES (%s,%s,%s,NULL,%s,1)
                    """, (user_id, mark_date, p, slot_label))
                elif subj_id:
                    cur.execute("""
                        INSERT INTO saturday_slots (user_id, sat_date, period_number, subject_id, slot_label, is_free)
                        VALUES (%s,%s,%s,%s,%s,0)
                    """, (user_id, mark_date, p, int(subj_id), slot_label))

            mysql.connection.commit()
            cur.close()
            flash('Saturday schedule saved! Now mark attendance.', 'success')
            return redirect(url_for('mark_saturday', date=mark_date_str))

    cur.close()
    return render_template('saturday_check.html',
        mark_date=mark_date,
        subjects=subjects,
        subjects_dict=subjects_dict,
        existing_config=existing_config,
        existing_slots=existing_slots,
        slot_times=SLOT_TIMES,
        user=user,
        today=date.today()
    )


@app.route('/mark_saturday', methods=['GET', 'POST'])
def mark_saturday():
    user = validate_session()
    if not user:
        return redirect(url_for('login'))
    user_id = user[0]
    subjects = get_subjects(user_id)
    subjects_dict = {s[0]: s[1] for s in subjects}

    mark_date_str = request.args.get('date', date.today().isoformat())
    mark_date = date.fromisoformat(mark_date_str)

    cur = mysql.connection.cursor()

    cur.execute("""
        SELECT ss.id, ss.period_number, ss.slot_label, ss.subject_id, COALESCE(s.subject_name,'Free Hour') as subject_name, ss.is_free
        FROM saturday_slots ss LEFT JOIN subjects s ON ss.subject_id=s.id
        WHERE ss.user_id=%s AND ss.sat_date=%s ORDER BY ss.period_number
    """, (user_id, mark_date))
    sat_slots = cur.fetchall()

    if not sat_slots:
        cur.close()
        return redirect(url_for('saturday_check', date=mark_date_str))

    cur.execute("SELECT id FROM daily_submissions WHERE user_id=%s AND submission_date=%s", (user_id, mark_date))
    already_submitted = cur.fetchone()

    # Allow editing even if already submitted (edit=1 in query params shows form)
    force_edit = request.args.get('edit') == '1'
    if force_edit and already_submitted:
        already_submitted = None  # treat as not submitted to show form

    if request.method == 'POST':
        for slot in sat_slots:
            slot_id, period, slot_label, orig_subj_id, orig_subj_name, is_free = slot
            fake_tt_id = -slot_id

            if is_free:
                # Free hour: only save if user chose a subject (not skipped)
                skip = request.form.get(f'skip_free_{slot_id}', '1')
                free_subj_id = request.form.get(f'free_subject_{slot_id}', None)
                if skip == '1' or not free_subj_id:
                    # Delete any existing record for this slot (in case editing)
                    cur.execute("DELETE FROM attendance WHERE user_id=%s AND timetable_id=%s AND class_date=%s",
                                (user_id, fake_tt_id, mark_date))
                    continue  # No class in free hour — don't record
                free_subj_id = int(free_subj_id)
                status = request.form.get(f'status_{slot_id}', 'absent')
                cur.execute("""
                    INSERT INTO attendance (user_id, subject_id, timetable_id, class_date, status, is_free_hour, free_subject_id)
                    VALUES (%s,%s,%s,%s,%s,1,%s)
                    ON DUPLICATE KEY UPDATE status=%s, free_subject_id=%s, marked_at=NOW()
                """, (user_id, free_subj_id, fake_tt_id, mark_date, status, free_subj_id,
                       status, free_subj_id))
            else:
                # Regular period — always save (present or absent)
                status = request.form.get(f'status_{slot_id}', 'absent')
                sub_val = request.form.get(f'sub_subject_{slot_id}', '')
                actual_subj_id = int(sub_val) if sub_val else orig_subj_id
                if not actual_subj_id:
                    continue
                sub_record = actual_subj_id if actual_subj_id != orig_subj_id else None
                cur.execute("""
                    INSERT INTO attendance (user_id, subject_id, timetable_id, class_date, status, is_free_hour, free_subject_id)
                    VALUES (%s,%s,%s,%s,%s,0,%s)
                    ON DUPLICATE KEY UPDATE status=%s, subject_id=%s, free_subject_id=%s, marked_at=NOW()
                """, (user_id, actual_subj_id, fake_tt_id, mark_date, status, sub_record,
                       status, actual_subj_id, sub_record))

        cur.execute("INSERT IGNORE INTO daily_submissions (user_id, submission_date) VALUES (%s,%s)",
                    (user_id, mark_date))
        mysql.connection.commit()
        cur.close()
        flash(f'Saturday attendance saved for {mark_date.strftime("%d %b %Y")}! ✅', 'success')
        return redirect(url_for('dashboard'))

    # Load existing attendance for display
    existing = {}
    sub_chosen = {}
    free_chosen = {}
    for slot in sat_slots:
        slot_id, period, slot_label, orig_subj_id, orig_subj_name, is_free = slot
        fake_tt_id = -slot_id
        cur.execute("""
            SELECT status, subject_id, free_subject_id FROM attendance
            WHERE user_id=%s AND timetable_id=%s AND class_date=%s
        """, (user_id, fake_tt_id, mark_date))
        row = cur.fetchone()
        if row:
            existing[slot_id] = row[0]
            sub_chosen[slot_id] = row[1]
            free_chosen[slot_id] = row[2]

    cur.close()
    return render_template('mark_saturday.html',
        sat_slots=sat_slots,
        mark_date=mark_date,
        already_submitted=already_submitted,
        existing=existing,
        sub_chosen=sub_chosen,
        free_chosen=free_chosen,
        subjects_dict=subjects_dict,
        subjects=subjects,
        user=user,
        today=date.today()
    )


# ─────────────────────────────────────────────────────
# API
# ─────────────────────────────────────────────────────

@app.route('/api/today_status')
def today_status():
    user = validate_session()
    if not user:
        return jsonify({"has_classes": False, "submitted": False, "is_saturday": False})
    user_id = user[0]
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
    user = validate_session()
    if not user:
        return jsonify({})
    user_id = user[0]
    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT class_date, status, is_free_hour, free_subject_id, subject_id FROM attendance
        WHERE user_id=%s AND (
            (subject_id=%s AND is_free_hour=0) OR
            (free_subject_id=%s AND is_free_hour=1)
        )
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
        pcts.append(min(100.0, round(attended / total * 100, 1)))

    return jsonify({"labels": labels, "pcts": pcts})

if __name__ == '__main__':
    app.run(debug=True)
