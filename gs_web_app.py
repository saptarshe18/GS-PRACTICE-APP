import streamlit as st
import sqlite3
import random
import pandas as pd
import hashlib
import os
import time
from datetime import datetime

# ============================================================
# DATABASE CONFIG (Cloud Safe)
# ============================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(BASE_DIR, "wbcsgs.db")

def get_connection():
    return sqlite3.connect(DB_FILE, check_same_thread=False)

# ============================================================
# TABLE CREATION
# ============================================================

def hash_password(password):
    import hashlib
    return hashlib.sha256(password.encode()).hexdigest()

def create_tables():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password_hash TEXT,
            role TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS quiz (
            si_no INTEGER PRIMARY KEY AUTOINCREMENT,
            subject TEXT,
            question TEXT,
            answer TEXT,
            difficulty INTEGER,
            reading_times INTEGER DEFAULT 0,
            is_marked INTEGER DEFAULT 0
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS practice_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            date TEXT,
            subject TEXT
        )
    """)

    conn.commit()
    conn.close()

def create_default_admin():
    conn = get_connection()
    cur = conn.cursor()

    # Check if any admin exists
    cur.execute("SELECT COUNT(*) FROM users WHERE role = 'admin'")
    admin_count = cur.fetchone()[0]

    if admin_count == 0:
        default_username = "Admin"
        default_password = "Admin123"

        cur.execute("""
            INSERT INTO users (username, password_hash, role)
            VALUES (?, ?, ?)
        """, (
            default_username,
            hash_password(default_password),
            "admin"
        ))

        conn.commit()

    conn.close()

create_tables()
create_default_admin()

# ============================================================
# SECURITY
# ============================================================

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def login_user(username, password):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, password_hash, role FROM users WHERE username=?", (username,))
    row = cur.fetchone()
    conn.close()

    if row:
        user_id, stored_hash, role = row
        if stored_hash == hash_password(password):
            return user_id, role
    return None, None

# ============================================================
# SESSION INIT
# ============================================================

if "user_id" not in st.session_state:
    st.session_state.user_id = None
    st.session_state.role = None

# ============================================================
# LOGIN PAGE
# ============================================================

if st.session_state.user_id is None:

    st.title("🔐 Login")

    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("Login"):
        user_id, role = login_user(username, password)
        if user_id:
            st.session_state.user_id = user_id
            st.session_state.role = role
            st.rerun()
        else:
            st.error("Invalid credentials")

    st.stop()

# ============================================================
# SIDEBAR
# ============================================================

st.sidebar.success(f"Logged in as: {st.session_state.role}")

if st.sidebar.button("Logout"):
    st.session_state.clear()
    st.rerun()

mode = st.sidebar.selectbox(
    "Mode",
    [
        "Live Dashboard",
        "Subject Practice",
        "Mixed Practice",
        "Exam Mode",
        "Insert Question",
        "Import from TXT",
        "Marked Questions",
        "Analytics",
        "User Management"
    ]
)

# ============================================================
# COMMON FUNCTIONS
# ============================================================

def get_questions():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT si_no, subject, question, answer, difficulty,
               COALESCE(reading_times,0), COALESCE(is_marked,0)
        FROM quiz
    """)
    rows = cur.fetchall()
    conn.close()
    random.shuffle(rows)
    return rows

def update_read_count(si_no, subject):
    today = datetime.now().strftime("%Y-%m-%d")
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("UPDATE quiz SET reading_times = reading_times + 1 WHERE si_no=?", (si_no,))
    cur.execute(
        "INSERT INTO practice_log (user_id, date, subject) VALUES (?, ?, ?)",
        (st.session_state.user_id, today, subject)
    )

    conn.commit()
    conn.close()

def toggle_mark(si_no, current_status):
    conn = get_connection()
    cur = conn.cursor()
    new_status = 0 if current_status == 1 else 1
    cur.execute("UPDATE quiz SET is_marked=? WHERE si_no=?", (new_status, si_no))
    conn.commit()
    conn.close()

# ============================================================
# PRACTICE MODE
# ============================================================

if mode in ["Subject Practice", "Mixed Practice"]:

    if "questions" not in st.session_state:
        st.session_state.questions = get_questions()
        st.session_state.index = 0
        st.session_state.reviewed = 0

    questions = st.session_state.questions

    if st.session_state.index >= len(questions):
        st.success("Session Complete")
        st.stop()

    q = questions[st.session_state.index]
    si_no, subject, question, answer, diff, reads, marked = q

    st.info(f"Reviewed This Session: {st.session_state.reviewed}")
    st.write(f"**Question ID:** {si_no}")
    st.write(f"**Subject:** {subject}")
    st.write(question)

    col1, col2 = st.columns(2)

    with col1:
        if marked:
            if st.button("❌ Unmark"):
                toggle_mark(si_no, marked)
                st.rerun()
        else:
            if st.button("⭐ Mark"):
                toggle_mark(si_no, marked)
                st.rerun()

    if st.button("Show Answer"):
        st.success(answer)
        update_read_count(si_no, subject)
        st.session_state.reviewed += 1

    if st.button("Next"):
        st.session_state.index += 1
        st.rerun()

# ============================================================
# MARKED QUESTIONS
# ============================================================

elif mode == "Marked Questions":

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT si_no, subject, question, answer, difficulty,
               COALESCE(reading_times,0), COALESCE(is_marked,0)
        FROM quiz
        WHERE is_marked = 1
    """)
    rows = cur.fetchall()
    conn.close()

    if not rows:
        st.warning("No marked questions.")
        st.stop()

    if "marked_index" not in st.session_state:
        st.session_state.marked_index = 0

    q = rows[st.session_state.marked_index]
    si_no, subject, question, answer, diff, reads, marked = q

    st.write(f"**ID:** {si_no}")
    st.write(question)

    if st.button("Show Answer"):
        st.success(answer)

    if st.button("Unmark"):
        toggle_mark(si_no, marked)
        st.rerun()

    if st.button("Next"):
        st.session_state.marked_index += 1
        st.rerun()

# ============================================================
# EXAM MODE
# ============================================================

elif mode == "Exam Mode":

    duration = st.number_input("Duration (minutes)", 1, 180, 30)

    if st.button("Start Exam"):
        st.session_state.exam = get_questions()
        st.session_state.exam_index = 0
        st.session_state.start_time = datetime.now()
        st.session_state.duration = duration
        st.rerun()

    if "exam" in st.session_state:

        elapsed = (datetime.now() - st.session_state.start_time).total_seconds()
        remaining = st.session_state.duration * 60 - elapsed

        if remaining <= 0:
            st.error("Time Over")
            st.stop()

        minutes = int(remaining // 60)
        seconds = int(remaining % 60)
        st.markdown(f"## ⏳ {minutes:02d}:{seconds:02d}")

        q = st.session_state.exam[st.session_state.exam_index]
        st.write(q[2])

        if st.button("Next Question"):
            st.session_state.exam_index += 1
            st.rerun()

        time.sleep(1)
        st.rerun()

# ============================================================
# ANALYTICS (PER USER)
# ============================================================

elif mode == "Analytics":

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT date, COUNT(*)
        FROM practice_log
        WHERE user_id = ?
        GROUP BY date
        ORDER BY date
    """, (st.session_state.user_id,))

    rows = cur.fetchall()
    conn.close()

    if rows:
        dates = [r[0] for r in rows]
        counts = [r[1] for r in rows]

        formatted_dates = [
            datetime.strptime(d, "%Y-%m-%d").strftime("%d %b")
            for d in dates
        ]

        df = pd.DataFrame({"Questions Practiced": counts}, index=formatted_dates)
        st.bar_chart(df)
    else:
        st.info("No data yet")

# ============================================================
# LIVE DASHBOARD
# ============================================================

elif mode == "Live Dashboard":

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM quiz")
    total_questions = cur.fetchone()[0]

    # Total Reads (USER SPECIFIC)
    cur.execute("""
        SELECT COUNT(*)
        FROM practice_log
        WHERE user_id = ?
    """, (st.session_state.user_id,))
    user_total_reads = cur.fetchone()[0] or 0

    cur.execute("SELECT subject, COUNT(*) FROM quiz GROUP BY subject")
    subject_counts = cur.fetchall()

    cur.execute("""
    SELECT subject, COUNT(*)
    FROM practice_log
    WHERE user_id = ?
    GROUP BY subject
    ORDER BY COUNT(*) DESC
""", (st.session_state.user_id,))
subject_leaderboard = cur.fetchall()

    conn.close()

    col1, col2 = st.columns(2)
    col1.metric("Total Questions", total_questions)
    col2.metric("Total Reads", total_reads)

    st.subheader("Subject Distribution")
    for s in subject_counts:
        st.write(f"{s[0]} : {s[1]}")

    st.subheader("Most Practiced Subjects")
    for s in subject_leaderboard:
        st.write(f"{s[0]} : {s[1]} reads")

    # ========================================================
    # USER LEADERBOARD (ADMIN ONLY)
    # ========================================================

    if st.session_state.role == "admin":

        st.subheader("👥 User Leaderboard")

        conn = get_connection()
        cur = conn.cursor()

        cur.execute("""
            SELECT u.username, COUNT(p.id)
            FROM users u
            LEFT JOIN practice_log p ON u.id = p.user_id
            GROUP BY u.username
            ORDER BY COUNT(p.id) DESC
        """)

        user_rows = cur.fetchall()
        conn.close()

        for i, (username, count) in enumerate(user_rows, 1):
            st.write(f"{i}. {username} — {count} practices")

# ============================================================
# USER MANAGEMENT (ADMIN ONLY)
# ============================================================

elif mode == "User Management":

    if st.session_state.role != "admin":
        st.error("Admin access required")
        st.stop()

    conn = get_connection()
    cur = conn.cursor()

    st.subheader("Create User")

    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    role = st.selectbox("Role", ["student", "admin"])

    if st.button("Create User"):
        cur.execute(
            "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
            (username, hash_password(password), role)
        )
        conn.commit()
        st.success("User created")

    conn.close()


elif mode == "Insert Question":

    st.subheader("➕ Insert New Question")

    if "insert_question" not in st.session_state:
        st.session_state.insert_question = ""

    if "insert_answer" not in st.session_state:
        st.session_state.insert_answer = ""

    question = st.text_area(
        "Enter Question",
        key="insert_question"
    )

    answer = st.text_area(
        "Enter Answer",
        key="insert_answer"
    )

    subject = st.text_input("Subject")
    difficulty = st.selectbox("Difficulty", [1, 2, 3])

    if st.button("Save Question"):

        if not question.strip() or not answer.strip() or not subject.strip():
            st.error("All fields required.")
        else:
            conn = get_connection()
            cur = conn.cursor()

            cur.execute("""
                INSERT INTO quiz (subject, question, answer, difficulty)
                VALUES (?, ?, ?, ?)
            """, (
                subject.strip(),
                question.strip(),
                answer.strip(),
                difficulty
            ))

            conn.commit()
            conn.close()

            st.success("Question added successfully.")

            # Reset fields safely
            del st.session_state["insert_question"]
            del st.session_state["insert_answer"]
            st.rerun()

elif mode == "Import from TXT":

    st.subheader("📂 Import Questions from TXT")

    uploaded_file = st.file_uploader("Upload TXT File", type=["txt"])

    default_difficulty = st.selectbox("Default Difficulty", [1, 2, 3])

    if uploaded_file is not None:

        file_content = uploaded_file.read().decode("utf-8")
        lines = [l.strip() for l in file_content.split("\n") if l.strip()]

        inserted = 0
        current_subject = "General"

        if st.button("Import Now"):

            conn = get_connection()
            cur = conn.cursor()

            for line in lines:

                # Subject line
                if line.startswith("* "):
                    current_subject = line[2:].strip()
                    continue

                # Q --> A format
                if "-->" in line:
                    question, answer = line.split("-->", 1)
                    question = question.strip()
                    answer = answer.strip()
                else:
                    continue

                if question and answer:
                    cur.execute("""
                        INSERT INTO quiz (subject, question, answer, difficulty)
                        VALUES (?, ?, ?, ?)
                    """, (
                        current_subject,
                        question,
                        answer,
                        default_difficulty
                    ))
                    inserted += 1

            conn.commit()
            conn.close()

            st.success(f"{inserted} questions imported successfully.")
            st.rerun()



