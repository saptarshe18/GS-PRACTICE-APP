import streamlit as st
import psycopg2
import random
import hashlib
import pandas as pd
from datetime import datetime
import uuid
import time
from supabase import create_client

# =====================================================
# INITIALIZE SUPABASE
# =====================================================
if "SUPABASE_URL" in st.secrets and "SUPABASE_KEY" in st.secrets:
    supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
else:
    supabase = None

# =====================================================
# SUBJECT LIST
# =====================================================

SUBJECTS = [
    "Ancient and Medieval History",
    "Modern History",
    "Geography",
    "Polity",
    "Economics",
    "Physics",
    "Chemistry",
    "Biology",
    "Environment",
    "Static Part",
    "West Bengal"
]

SUBJECT_COLUMN_MAP = {
    "Ancient and Medieval History": "ancient_medieval_history",
    "Modern History": "modern_history",
    "Geography": "geography",
    "Polity": "polity",
    "Economics": "economics",
    "Biology": "biology",
    "Physics": "physics",
    "Chemistry": "chemistry",
    "Environment": "environment",
    "Static Part": "static_part",
    "West Bengal": "west_bengal"
}

# =====================================================
# DATABASE CONNECTION
# =====================================================

def get_connection():
    conn = psycopg2.connect(
        host=st.secrets["DB_HOST"],
        dbname=st.secrets["DB_NAME"],
        user=st.secrets["DB_USER"],
        password=st.secrets["DB_PASSWORD"],
        port=int(st.secrets["DB_PORT"]),
        sslmode="require"
    )
    return conn

# =====================================================
# SECURITY
# =====================================================

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# =====================================================
# LOGIN
# =====================================================

def login_user(username, password):
    st.write("🔎 Login attempt started")
    with get_connection() as conn:
        with conn.cursor() as cur:
            st.write("Username entered:", username)

            cur.execute("""
            SELECT id, password_hash, role
            FROM users
            WHERE username=%s
            """, (username,))

            row = cur.fetchone()
            st.write("Database row fetched:", row)

            if row:
                stored_password = row[1]
                hashed_input = hash_password(password)

                if stored_password == password:
                    st.success("Matched plain password")
                if stored_password == hashed_input:
                    st.success("Matched hashed password")
            else:
                st.error("No user found in database")

            if row and (row[1] == password or row[1] == hash_password(password)):
                st.success("Password verification passed")

                cur.execute("""
                UPDATE users
                SET is_active=TRUE, last_active=%s
                WHERE id=%s
                """, (datetime.now(), row[0]))

                conn.commit()
                st.write("User login updated in DB")
                return row[0], row[2]

            st.error("Password verification failed")
    return None, None

# =====================================================
# SESSION INIT
# =====================================================

if "user_id" not in st.session_state:
    st.session_state.user_id = None
    st.session_state.role = None

# =====================================================
# LOGIN PAGE
# =====================================================

if st.session_state.user_id is None:
    st.title("🔐 Login")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("Login"):
        try:
            conn = get_connection()
            st.success("Database connected successfully")
            conn.close()
        except Exception as e:
            st.error(f"DB ERROR: {e}")

        user_id, role = login_user(username, password)
        if user_id:
            st.session_state.user_id = user_id
            st.session_state.role = role
            st.rerun()
        else:
            st.error("Invalid credentials")
    st.stop()

# =====================================================
# SESSION STATE INITIALIZATION
# =====================================================

if "session_easy" not in st.session_state:
    st.session_state.session_easy = 0
if "session_moderate" not in st.session_state:
    st.session_state.session_moderate = 0
if "session_difficult" not in st.session_state:
    st.session_state.session_difficult = 0
if "reviewed" not in st.session_state:
    st.session_state.reviewed = 0

# =====================================================
# SIDEBAR
# =====================================================

st.sidebar.success(f"Logged in as {st.session_state.role}")

if st.sidebar.button("Logout"):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
            UPDATE users
            SET is_active=FALSE, last_active=%s
            WHERE id=%s
            """, (datetime.now(), st.session_state.user_id))
            conn.commit()
    st.session_state.clear()
    st.rerun()

mode = st.sidebar.selectbox(
    "Mode",
    [
        "Live Dashboard",
        "Subject Practice",
        "Mixed Practice",
        "Bulk View",
        "Exam Mode",
        "Update Question",
        "Insert Question",
        "Import from TXT",
        "Marked Questions",
        "Analytics",
        "User Management",
        "Notes"
    ]
)

# ============================================================
# NOTES METADATA & DATA PIPELINES
# ============================================================

def add_subject(subject_name):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO notes_subjects(subject_name) VALUES(%s)", (subject_name,))
            conn.commit()

def get_all_subjects():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, subject_name FROM notes_subjects ORDER BY subject_name")
            return cur.fetchall()

def update_subject(subject_id, updated_name):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE notes_subjects SET subject_name=%s WHERE id=%s", (updated_name, subject_id))
            conn.commit()

def delete_subject(subject_id):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM notes_subjects WHERE id=%s", (subject_id,))
            conn.commit()

def add_chapter(subject_id, chapter_name):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO notes_chapters(subject_id, chapter_name) VALUES(%s, %s)", (subject_id, chapter_name))
            conn.commit()

def get_chapters(subject_id):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, subject_id, chapter_name FROM notes_chapters WHERE subject_id=%s ORDER BY chapter_name", (subject_id,))
            return cur.fetchall()

def update_chapter(chapter_id, updated_name):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE notes_chapters SET chapter_name=%s WHERE id=%s", (updated_name, chapter_id))
            conn.commit()

def delete_chapter(chapter_id):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM notes_chapters WHERE id=%s", (chapter_id,))
            conn.commit()

def add_note(chapter_id, new_text, image_url=None):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, note_text, image_path FROM notes_content WHERE chapter_id=%s", (chapter_id,))
            existing = cur.fetchone()

            if existing:
                note_id, old_text, old_image = existing
                combined_text = (old_text or "") + "\n\n" + (new_text or "")
                final_image = image_url or old_image

                cur.execute("""
                UPDATE notes_content
                SET note_text=%s, image_path=%s
                WHERE id=%s
                """, (combined_text, final_image, note_id))
            else:
                cur.execute("""
                INSERT INTO notes_content(chapter_id, note_text, image_path)
                VALUES(%s, %s, %s)
                """, (chapter_id, new_text, image_url))
            conn.commit()

def get_notes(chapter_id):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
            SELECT id, chapter_id, note_text, image_path, created_at
            FROM notes_content
            WHERE chapter_id=%s
            ORDER BY created_at
            """, (chapter_id,))
            return cur.fetchall()

def update_note(note_id, note_text, image_url):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
            UPDATE notes_content
            SET note_text=%s, image_path=%s
            WHERE id=%s
            """, (note_text, image_url, note_id))
            conn.commit()

def delete_note(note_id):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM notes_content WHERE id=%s", (note_id,))
            conn.commit()

def upload_note_image(uploaded_file):
    if not supabase:
        st.error("Supabase configuration details missing from secrets.")
        return None
    ext = uploaded_file.name.split(".")[-1]
    filename = f"{uuid.uuid4()}.{ext}"
    filepath = f"notes/{filename}"

    supabase.storage.from_("notes-images").upload(filepath, uploaded_file.getvalue())
    public_url = supabase.storage.from_("notes-images").get_public_url(filepath)
    return public_url

# =====================================================
# FETCH QUESTIONS ENGINE
# =====================================================

def get_questions(subject=None, difficulty=None, order="random"):
    with get_connection() as conn:
        with conn.cursor() as cur:
            query = """
            SELECT si_no, subject, question, answer, difficulty,
            COALESCE(reading_times,0), COALESCE(is_marked,0)
            FROM quiz
            """
            conditions = []
            params = []

            if subject:
                conditions.append("subject=%s")
                params.append(subject)
            if difficulty:
                conditions.append("difficulty=%s")
                params.append(difficulty)

            if conditions:
                query += " WHERE " + " AND ".join(conditions)

            if order == "most":
                query += " ORDER BY reading_times DESC"
            elif order == "least":
                query += " ORDER BY reading_times ASC"

            cur.execute(query, params)
            rows = cur.fetchall()

    rows = [list(r) for r in rows]
    if order == "random":
        random.shuffle(rows)
    return rows

# =====================================================
# METRIC LOGGER UPDATES
# =====================================================

def update_read_count(si_no, subject):
    today = datetime.now().date()
    column = SUBJECT_COLUMN_MAP.get(subject)
    if not column:
        return

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
            UPDATE quiz
            SET reading_times = COALESCE(reading_times, 0) + 1
            WHERE si_no = %s
            """, (si_no,))

            cur.execute("""
            INSERT INTO practice_summary(user_id, practice_date)
            VALUES(%s, %s)
            ON CONFLICT (user_id, practice_date) DO NOTHING
            """, (st.session_state.user_id, today))

            query = f"""
            UPDATE practice_summary
            SET {column} = COALESCE({column}, 0) + 1
            WHERE user_id = %s AND practice_date = %s
            """
            cur.execute(query, (st.session_state.user_id, today))
            conn.commit()

def toggle_mark(si_no, current_status):
    new_status = 0 if current_status == 1 else 1
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
            UPDATE quiz
            SET is_marked=%s
            WHERE si_no=%s
            """, (new_status, si_no))
            conn.commit()

# ============================================================
# PRACTICE MODE (Subject + Mixed Unified Engine)
# ============================================================

if mode in ["Subject Practice", "Mixed Practice"]:

    defaults = {
        "session_easy": 0,
        "session_moderate": 0,
        "session_difficult": 0,
        "show_summary": False,
        "practice_active": False,
        "reviewed": 0,
        "answer_shown": False,
        "questions": [],
        "index": 0,
        "practice_log": []
    }

    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

    subject = None
    difficulty = None

    if mode == "Subject Practice":
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT subject, COUNT(*) FROM quiz GROUP BY subject ORDER BY subject")
                rows = cur.fetchall()

        subject_counts = {r[0]: r[1] for r in rows}
        if not subject_counts:
            st.warning("No questions available in database.")
            st.stop()

        subject_options = [f"{sub} ({count})" for sub, count in subject_counts.items()]
        selected_display = st.selectbox("Select Subject", subject_options)
        subject = selected_display.rsplit(" (", 1)[0]

    difficulty_option = st.selectbox("Difficulty", ["All", "Easy", "Moderate", "Difficult"])
    difficulty_map = {"Easy": 1, "Moderate": 2, "Difficult": 3}
    if difficulty_option != "All":
        difficulty = difficulty_map[difficulty_option]

    order_option = st.selectbox("Question Type", ["Random", "Most Read", "Least Read"])
    order_map = {"Random": "random", "Most Read": "most", "Least Read": "least"}
    order_type = order_map[order_option]

    if not st.session_state.practice_active and not st.session_state.show_summary:
        if st.button("▶ Start Practice"):
            questions = get_questions(subject=subject, difficulty=difficulty, order=order_type)
            if not questions:
                st.warning("No questions found with selected filters.")
                st.stop()

            st.session_state.questions = questions
            st.session_state.index = 0
            st.session_state.reviewed = 0
            st.session_state.session_easy = 0
            st.session_state.session_moderate = 0
            st.session_state.session_difficult = 0
            st.session_state.practice_log = []
            st.session_state.practice_active = True
            st.rerun()
        st.stop()

    # Active Interactive Practice View Loop
    if st.session_state.practice_active:
        questions = st.session_state.questions

        if st.session_state.index >= len(questions):
            st.success("Session Complete")
            st.session_state.practice_active = False
            st.session_state.show_summary = True
            st.rerun()

        q = questions[st.session_state.index]
        si_no, subject, question, answer, diff, reads, marked = q

        st.info(f"Reviewed This Session: {st.session_state.reviewed}")
        st.write(f"**Question ID:** {si_no} | **Subject:** {subject} | **Reads:** {reads}")
        st.write(question)

        colA, colB = st.columns(2)
        with colA:
            if st.button("⭐ Mark / Unmark"):
                toggle_mark(si_no, marked)
                st.success("Status Updated Successfully!")
        with colB:
            new_subject = st.selectbox("Change Subject", SUBJECTS, key=f"sub_change_{si_no}")

        if st.button("Update Subject"):
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("UPDATE quiz SET subject=%s WHERE si_no=%s", (new_subject, si_no))
                    conn.commit()
            st.success("Subject updated")

        if st.button("Show Answer"):
            st.success(answer)
            if not st.session_state.answer_shown:
                update_read_count(si_no, subject)
                st.session_state.reviewed += 1
                st.session_state.practice_log.append((si_no, subject))
                st.session_state.answer_shown = True

                if diff == 1:
                    st.session_state.session_easy += 1
                elif diff == 2:
                    st.session_state.session_moderate += 1
                elif diff == 3:
                    st.session_state.session_difficult += 1

        st.markdown("---")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Next"):
                st.session_state.index += 1
                st.session_state.answer_shown = False
                st.rerun()
        with col2:
            if st.button("⏹ End Practice"):
                st.session_state.practice_active = False
                st.session_state.show_summary = True
                st.rerun()

# ============================================================
# PRACTICE SUMMARY REPORT VIEW (CORRECTED)
# ============================================================

if st.session_state.get("show_summary", False):
    st.markdown("## 📊 Practice Session Summary")
    
    total_reviewed = st.session_state.get("reviewed", 0)
    st.metric("Total Questions Reviewed", total_reviewed)

    col1, col2, col3 = st.columns(3)
    col1.metric("Easy", st.session_state.get("session_easy", 0))
    col2.metric("Moderate", st.session_state.get("session_moderate", 0))
    col3.metric("Difficult", st.session_state.get("session_difficult", 0))

    practice_log = st.session_state.get("practice_log", [])
    if practice_log:
        st.markdown("### 📘 Subject-wise Distribution")
        subject_count = {}
        for _, sub in practice_log:
            subject_count[sub] = subject_count.get(sub, 0) + 1
        for sub, count in subject_count.items():
            st.write(f"- **{sub}**: {count}")

    if st.button("🔄 Start New Session"):
        reset_defaults = {
            "bulk_started": False,
            "bulk_subject": "All",
            "bulk_q_count": 30,
            "bulk_index": 0,
            "practice_active": False,
            "show_summary": False,
            "reviewed": 0,
            "session_easy": 0,
            "session_moderate": 0,
            "session_difficult": 0,
            "index": 0,
            "questions": [],
            "practice_log": [],
            "answer_shown": False
        }
        for key, value in reset_defaults.items():
            st.session_state[key] = value

        # Remove page tracking bulk dynamic keys
        for key in list(st.session_state.keys()):
            if key.startswith("bulk_updated_"):
                del st.session_state[key]
        st.rerun()

# =====================================================
# LIVE DASHBOARD
# =====================================================

elif mode == "Live Dashboard":
    st.subheader("📊 User Dashboard")
    user_id = st.session_state.user_id
    role = st.session_state.role

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM quiz")
            total_questions = cur.fetchone()[0] or 0

            cur.execute("""
            SELECT subject, COUNT(*)
            FROM quiz
            GROUP BY subject
            ORDER BY CASE subject
                WHEN 'Ancient and Medieval History' THEN 1
                WHEN 'Modern History' THEN 2
                WHEN 'Geography' THEN 3
                WHEN 'Polity' THEN 4
                WHEN 'Economics' THEN 5
                WHEN 'Environment' THEN 6
                WHEN 'Physics' THEN 7
                WHEN 'Chemistry' THEN 8
                WHEN 'Biology' THEN 9
                WHEN 'Static Part' THEN 10
                WHEN 'West Bengal' THEN 11
                ELSE 12
            END
            """)
            subject_question_counts = cur.fetchall()

    st.markdown("## 📘 Question Bank Overview")
    st.metric("Total Questions", total_questions)

    for subject, count in subject_question_counts:
        st.write(f"{subject} : {count}")

    st.markdown("---")

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
            SELECT COALESCE(SUM(
                ancient_medieval_history + modern_history + geography + polity + 
                economics + biology + physics + chemistry + environment + 
                static_part + west_bengal
            ), 0)
            FROM practice_summary WHERE user_id = %s
            """, (user_id,))
            user_total_reads = cur.fetchone()[0] or 0

    st.markdown("## 📈 Your Practice Stats")
    col1, col2 = st.columns([3, 1])
    with col1:
        st.metric("Total Questions Practiced", user_total_reads)
    with col2:
        if st.button("Reset Total Reads"):
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM practice_summary WHERE user_id = %s", (user_id,))
                    conn.commit()
            st.success("Your total practice data has been reset.")
            st.rerun()

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
            SELECT 
                ancient_medieval_history, modern_history, geography, polity, economics,
                biology, physics, chemistry, environment, static_part, west_bengal
            FROM practice_summary WHERE user_id = %s
            """, (user_id,))
            rows = cur.fetchall()

    subject_totals = {sub: 0 for sub in SUBJECTS}
    for row in rows:
        for idx, sub in enumerate(SUBJECTS):
            if idx < len(row):
                subject_totals[sub] += row[idx] or 0

    if rows:
        st.markdown("### 📊 Subject-wise Practice")
        for subject, count in subject_totals.items():
            st.write(f"{subject} : {count}")
    else:
        st.info("No practice data yet.")

    if role == "admin":
        st.markdown("## 👑 Admin: All Users Practice Stats")
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                SELECT u.username,
                       COALESCE(SUM(
                           p.ancient_medieval_history + p.modern_history + p.geography + 
                           p.polity + p.economics + p.biology + p.physics + p.chemistry + 
                           p.environment + p.static_part + p.west_bengal
                       ), 0)
                FROM users u
                LEFT JOIN practice_summary p ON u.id = p.user_id
                GROUP BY u.username ORDER BY 2 DESC
                """)
                user_stats = cur.fetchall()

        if user_stats:
            for username, total in user_stats:
                c1, c2 = st.columns([3, 1])
                with c1: st.write(f"{username}")
                with c2: st.metric("Total Practiced", total)
        else:
            st.info("No user practice data yet.")

# ============================================================
# MARKED QUESTIONS
# ============================================================

elif mode == "Marked Questions":
    st.subheader("⭐ Bookmarked Questions")
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
            SELECT si_no, subject, question, answer, difficulty,
                   COALESCE(reading_times,0), COALESCE(is_marked,0)
            FROM quiz WHERE is_marked = 1
            """)
            rows = cur.fetchall()

    if not rows:
        st.warning("No marked questions found.")
        st.stop()

    if "marked_index" not in st.session_state:
        st.session_state.marked_index = 0

    if st.session_state.marked_index >= len(rows):
        st.session_state.marked_index = 0

    q = rows[st.session_state.marked_index]
    si_no, subject, question, answer, diff, reads, marked = q

    st.write(f"**Question Table ID:** {si_no} | **Subject:** {subject}")
    st.write(question)

    if st.button("Show Answer", key="show_marked_ans"):
        st.success(answer)

    m_col1, m_col2 = st.columns(2)
    with m_col1:
        if st.button("Next Marked Question"):
            st.session_state.marked_index = (st.session_state.marked_index + 1) % len(rows)
            st.rerun()
    with m_col2:
        if st.button("Unmark Question"):
            toggle_mark(si_no, marked)
            st.success("Removed Bookmark Status!")
            st.rerun()
