import streamlit as st
import sqlite3
import random
from datetime import datetime, timedelta
import time
import pandas as pd

DB_FILE = "wbcsgs.db"

SUBJECTS = [
    "Ancient and Medieval History", "Modern History", "Geography", "Polity",
    "Economics", "Biology", "Physics", "Chemistry", "Environment",
    "Static Part", "West Bengal"
]

ADMIN_PASSWORD = "Gs123"

st.markdown("""
    <style>
    div[data-testid="stButton"] button[kind="secondary"] {
        background-color: #fff8cc !important;
        color: black !important;
        border: 1px solid #e6d88c !important;
    }
    </style>
""", unsafe_allow_html=True)

def check_admin_login():
    if "admin_logged_in" not in st.session_state:
        st.session_state.admin_logged_in = False

    if not st.session_state.admin_logged_in:
        password = st.text_input("Enter Admin Password", type="password")
        if st.button("Login"):
            if password == ADMIN_PASSWORD:
                st.session_state.admin_logged_in = True
                st.success("Admin Login Successful")
                st.rerun()
            else:
                st.error("Wrong Password")
        return False
    return True
# ---------------- DATABASE ----------------

def get_connection():
    return sqlite3.connect(DB_FILE, check_same_thread=False)

def normalize_subject_names():
    print("Inside normalisation function")
    conn = get_connection()
    cur = conn.cursor()

    updates = [
        ("Physics", "PHYSICS"),
        ("Economics", "ECONOMICS"),
        ("Static Part", "STATIC PART")
    ]

    for correct, wrong in updates:
        cur.execute(
            "UPDATE quiz SET subject = ? WHERE subject = ?",
            (correct, wrong)
        )
        print("Subject Names Changed")

    conn.commit()
    conn.close()


def get_questions(subject=None, difficulty=None, order="random"):
    conn = get_connection()
    cur = conn.cursor()

    query = """
        SELECT si_no, subject, question, answer,
        difficulty, COALESCE(reading_times,0),COALESCE(is_marked,0)
        FROM quiz
    """

    conditions = []
    params = []

    if subject:
        conditions.append("subject = ?")
        params.append(subject)

    if difficulty:
        conditions.append("difficulty = ?")
        params.append(difficulty)

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    if order == "least":
        query += " ORDER BY reading_times ASC"
    elif order == "most":
        query += " ORDER BY reading_times DESC"

    cur.execute(query, params)
    rows = cur.fetchall()
    conn.close()

    if order == "random":
        random.shuffle(rows)

    return rows


def update_read_count(si_no, subject):
    today = datetime.now().strftime("%Y-%m-%d")

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        UPDATE quiz
        SET reading_times = COALESCE(reading_times,0) + 1,
            last_practiced = ?
        WHERE si_no = ?
    """, (today, si_no))

    cur.execute(
        "INSERT INTO practice_log (date, subject) VALUES (?, ?)",
        (today, subject)
    )

    conn.commit()
    conn.close()


# ---------------- STREAK ----------------

def update_streak():
    today = datetime.now().date()
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT last_date, streak FROM streak_tracker WHERE id=1")
    row = cur.fetchone()

    if not row:
        cur.execute("INSERT INTO streak_tracker VALUES (1, ?, 1)", (str(today),))
        streak = 1
    else:
        last_date = datetime.strptime(row[0], "%Y-%m-%d").date()
        streak = row[1]

        if today == last_date + timedelta(days=1):
            streak += 1
        elif today != last_date:
            streak = 1

        cur.execute("UPDATE streak_tracker SET last_date=?, streak=? WHERE id=1",
                    (str(today), streak))

    conn.commit()
    conn.close()

    return streak

# ---------------- MARK ----------------
def toggle_mark(si_no, current_status):
    conn = get_connection()
    cur = conn.cursor()

    new_status = 0 if current_status == 1 else 1

    cur.execute("""
        UPDATE quiz
        SET is_marked = ?
        WHERE si_no = ?
    """, (new_status, si_no))

    conn.commit()
    conn.close()

    return new_status

def get_questions_marked(subject=None, difficulty=None, order="random", marked_only=False):
    conn = get_connection()
    cur = conn.cursor()

    query = """
        SELECT si_no, subject, question, answer,
        difficulty, COALESCE(reading_times,0), COALESCE(is_marked,1)
        FROM quiz
    """

    conditions = []
    params = []

    if subject:
        conditions.append("subject = ?")
        params.append(subject)

    if difficulty:
        conditions.append("difficulty = ?")
        params.append(difficulty)

    if marked_only:
        conditions.append("is_marked = 1")

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    if order == "least":
        query += " ORDER BY reading_times ASC"
    elif order == "most":
        query += " ORDER BY reading_times DESC"

    cur.execute(query, params)
    rows = cur.fetchall()
    conn.close()

    if order == "random":
        random.shuffle(rows)

    return rows


# ---------------- PAGE ----------------

st.set_page_config(layout="wide")
st.title("📘 LET US PRACTICE GENERAL STUDIES")
st.caption("Made by Saptarshe Bhattacharjee")

st.sidebar.header("You Can change your "
                  "Settings")

mode = st.sidebar.selectbox(
    "Mode",
    [
        "Live Dashboard",
        "Insert Question",
        "Edit / Delete Question",
        "Subject Practice",
        "Mixed Practice",
        "Exam Mode",
        "Leaderboard",
        "Analytics",
        "Import from TXT",
        "Browse Questions",
        "Marked Questions"
    ]
)

difficulty_map = {"Easy":1, "Moderate":2, "Difficult":3}

difficulty_choice = st.sidebar.selectbox(
    "Difficulty",
    ["All","Easy","Moderate","Difficult"]
)

order_choice = st.sidebar.selectbox(
    "Practice Order",
    ["Random","Least Read First","Most Read First"]
)

order_map = {
    "Random":"random",
    "Least Read First":"least",
    "Most Read First":"most"
}

difficulty_value = None
if difficulty_choice != "All":
    difficulty_value = difficulty_map[difficulty_choice]

# ---------------- PRACTICE MODES ----------------

if mode in ["Mixed Practice", "Subject Practice"]:

    if "session_reviewed" not in st.session_state:
        st.session_state.session_reviewed = 0

    if "session_easy" not in st.session_state:
        st.session_state.session_easy = 0

    if "session_moderate" not in st.session_state:
        st.session_state.session_moderate = 0

    if "session_difficult" not in st.session_state:
        st.session_state.session_difficult = 0

    if not check_admin_login():
        st.stop()

    if mode == "Subject Practice":
        subject = st.selectbox("Select Subject", SUBJECTS)
    else:
        subject = None

    if st.button("Start Practice"):
        st.session_state.questions = get_questions(
            subject,
            difficulty_value,
            order_map[order_choice]
        )
        st.session_state.q_index = 0

    if "questions" in st.session_state:

        questions = st.session_state.questions

        if st.session_state.q_index >= len(questions):
            st.success("🎉 Session Complete!")
            if st.button("Restart"):
                del st.session_state.questions
            st.stop()

        q = questions[st.session_state.q_index]
        si_no, subject, question, answer, diff, reads, is_marked = q

        st.markdown("---")
        st.info(f"📊 Reviewed This Session: {st.session_state.session_reviewed}")
        st.markdown(f"**Subject:** {subject}")
        st.markdown(f"**Difficulty:** {['Easy','Moderate','Difficult'][diff-1]}")
        st.markdown(f"**Reads:** {reads}")

        st.markdown(f"**Question ID:** {si_no}")

        st.markdown("### ❓ Question")
        st.write(question)

        mark_col1, mark_col2 = st.columns(2)

        with mark_col1:
            if is_marked:
                if st.button("❌ Unmark Question"):
                    toggle_mark(si_no, is_marked)
                    st.rerun()
            else:
                if st.button("⭐ Mark Question"):
                    toggle_mark(si_no, is_marked)
                    st.rerun()

        if st.button("Show Answer", type="secondary"):
            st.success(answer)
            update_read_count(si_no, subject)
            st.session_state.session_reviewed += 1

            if diff == 1:
                st.session_state.session_easy += 1
            elif diff == 2:
                st.session_state.session_moderate += 1
            else:
                st.session_state.session_difficult += 1

        if st.button("Next Question"):
            st.session_state.q_index += 1
            st.rerun()

    if st.button("End Practice Session"):
        st.session_state.show_summary = True
        st.rerun()

if st.session_state.get("show_summary", False):

    st.markdown("## 📊 Practice Session Summary")

    st.metric("Total Questions Reviewed", st.session_state.session_reviewed)

    col1, col2, col3 = st.columns(3)

    col1.metric("Easy", st.session_state.session_easy)
    col2.metric("Moderate", st.session_state.session_moderate)
    col3.metric("Difficult", st.session_state.session_difficult)

    # Weak subject
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT subject, SUM(reading_times)
        FROM quiz
        GROUP BY subject
        ORDER BY SUM(reading_times) ASC
        LIMIT 1
    """)

    weakest = cur.fetchone()
    conn.close()

    if weakest:
        st.error(f"Weakest Subject: {weakest[0]}")

    if st.button("Start New Session"):
        for key in [
            "session_reviewed",
            "session_easy",
            "session_moderate",
            "session_difficult",
            "show_summary"
        ]:
            st.session_state.pop(key, None)

        st.rerun()


# ---------------- EXAM MODE ----------------

elif mode == "Exam Mode":

    if not check_admin_login():
        st.stop()

    st.subheader("📝 Timed Exam Mode")

    # Select duration only
    exam_duration = st.number_input(
        "Exam Duration (Minutes)",
        min_value=1,
        max_value=180,
        value=30
    )

    questions = get_questions()

    # Start Exam
    if st.button("Start Exam"):
        st.session_state.exam = random.sample(questions, len(questions))
        st.session_state.exam_index = 0
        st.session_state.exam_start = datetime.now()
        st.session_state.exam_duration = exam_duration
        st.session_state.attempted = 0
        st.session_state.exam_active = True
        st.session_state.show_answer = False
        st.rerun()

    # If exam started
    if "exam" in st.session_state and st.session_state.get("exam_active", False):

        start_time = st.session_state.exam_start
        duration = st.session_state.exam_duration

        elapsed = (datetime.now() - start_time).total_seconds()
        remaining = duration * 60 - elapsed

        # ⛔ Time Over
        if remaining <= 0:
            st.error("⏰ Time Over!")
            st.success(f"📊 Questions Attempted: {st.session_state.attempted}")

            # Clear exam session
            for key in [
                "exam",
                "exam_index",
                "exam_start",
                "exam_duration",
                "attempted",
                "exam_active"
            ]:
                st.session_state.pop(key, None)

            st.stop()

        # ⏳ Timer Display
        minutes = int(remaining // 60)
        seconds = int(remaining % 60)

        timer_placeholder = st.empty()
        timer_placeholder.markdown(
            f"## ⏳ Time Left: {minutes:02d}:{seconds:02d}"
        )

        # Show Question
        if st.session_state.exam_index < len(st.session_state.exam):

            q = st.session_state.exam[st.session_state.exam_index]
            si_no, subject, question, answer, diff, reads, is_marked = q

            st.markdown(f"### Question {st.session_state.exam_index + 1}")
            st.write(question)

            if st.button("Reveal Answer"):
                st.session_state.show_answer = True
                st.session_state.attempted += 1

            if st.session_state.get("show_answer", False):
                st.success(answer)

            if st.button("Next Question"):
                st.session_state.exam_index += 1
                st.session_state.show_answer = False
                st.rerun()

        else:
            st.success("🎉 All Questions Attempted!")
            st.success(f"📊 Total Attempted: {st.session_state.attempted}")

            for key in [
                "exam",
                "exam_index",
                "exam_start",
                "exam_duration",
                "attempted",
                "exam_active"
            ]:
                st.session_state.pop(key, None)

            st.stop()

        # Auto-refresh every second
        time.sleep(1)
        st.rerun()


# ---------------- LEADERBOARD ----------------

elif mode == "Leaderboard":

    if not check_admin_login():
        st.stop()

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT subject, SUM(COALESCE(reading_times,0)) as total_reads
        FROM quiz
        GROUP BY subject
        ORDER BY total_reads DESC
    """)

    rows = cur.fetchall()

    cur.execute("""
            SELECT SUM(COALESCE(reading_times,0))
            FROM quiz
        """)
    total_reads = cur.fetchone()[0] or 0

    conn.close()

    st.subheader("🏆 Subject Leaderboard")

    st.metric("Total Reads (All Subjects)", total_reads)

    for i, (subject, reads) in enumerate(rows,1):
        st.write(f"{i}. {subject} — {reads} reads")


# ---------------- ANALYTICS ----------------

elif mode == "Analytics":

    if not check_admin_login():
        st.stop()

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT DATE(date), COUNT(*)
        FROM practice_log
        GROUP BY DATE(date)
        ORDER BY DATE(date)
    """)

    rows = cur.fetchall()
    conn.close()

    st.subheader("📊 Date-wise Practice")

    if rows:
        dates = [r[0] for r in rows]
        counts = [r[1] for r in rows]

        # Convert to clean label like "16 Feb"
        formatted_dates = [
            datetime.strptime(d, "%Y-%m-%d").strftime("%d %b (%a)")
            for d in dates
        ]

        df = pd.DataFrame({
            "Questions Practiced": counts
        }, index=formatted_dates)

        st.bar_chart(df)
    else:
        st.info("No practice data yet.")


# ---------------- INSERT QUESTION ----------------

elif mode == "Insert Question":

    if not check_admin_login():
        st.stop()

    if "insert_question" not in st.session_state:
        st.session_state.insert_question = ""

    if "insert_answer" not in st.session_state:
        st.session_state.insert_answer = ""

    st.subheader("➕ Insert New Question")

    question = st.text_area(
        "Enter Question",
        key="insert_question"
    )

    answer = st.text_area(
        "Enter Answer",
        key="insert_answer"
    )

    difficulty = st.selectbox(
        "Select Difficulty",
        ["Easy", "Moderate", "Difficult"]
    )

    subject = st.selectbox("Select Subject", SUBJECTS)

    difficulty_map = {"Easy":1, "Moderate":2, "Difficult":3}

    if st.button("Save Question"):

        if not question.strip() or not answer.strip():
            st.error("Question and Answer cannot be empty.")
        else:
            conn = get_connection()
            cur = conn.cursor()

            cur.execute("""
                INSERT INTO quiz (subject, question, answer, difficulty)
                VALUES (?, ?, ?, ?)
            """, (
                subject,
                question.strip(),
                answer.strip(),
                difficulty_map[difficulty]
            ))

            conn.commit()
            conn.close()

            st.success("✅ Question inserted successfully!")

    if st.button("🔄 Reset Fields"):
        del st.session_state["insert_question"]
        del st.session_state["insert_answer"]
        st.rerun()


# ---------------- IMPORT FROM TXT ----------------

elif mode == "Import from TXT":

    if not check_admin_login():
        st.stop()

    st.subheader("📂 Import Questions from TXT")

    uploaded_file = st.file_uploader("Upload TXT file", type=["txt"])

    default_difficulty = st.selectbox(
        "Default Difficulty",
        ["Easy", "Moderate", "Difficult"]
    )

    difficulty_map = {"Easy":1, "Moderate":2, "Difficult":3}

    if uploaded_file is not None:

        file_content = uploaded_file.read().decode("utf-8")
        lines = [l.strip() for l in file_content.split("\n") if l.strip()]

        inserted = 0
        current_subject = "Static Part"

        if st.button("Import Now"):

            conn = get_connection()
            cur = conn.cursor()

            for line in lines:

                # Subject line: * Subject Name
                if line.startswith("* "):
                    current_subject = line[2:].strip()
                    continue

                # Question --> Answer format
                if "-->" in line:
                    question, answer = [p.strip() for p in line.split("-->", 1)]
                else:
                    question = line
                    answer = "True"

                if not question:
                    continue

                cur.execute("""
                    INSERT INTO quiz (subject, question, answer, difficulty)
                    VALUES (?, ?, ?, ?)
                """, (
                    current_subject,
                    question,
                    answer,
                    difficulty_map[default_difficulty]
                ))

                inserted += 1

            conn.commit()
            conn.close()

            st.success(f"✅ Imported {inserted} questions successfully!")

elif mode == "Edit / Delete Question":

    if not check_admin_login():
        st.stop()

    st.subheader("🔍 Search Question by ID")

    qid = st.number_input("Enter Question ID", min_value=1, step=1)

    if st.button("Search"):

        conn = get_connection()
        cur = conn.cursor()

        cur.execute("""
            SELECT si_no, subject, question, answer, difficulty
            FROM quiz
            WHERE si_no = ?
        """, (qid,))

        row = cur.fetchone()
        conn.close()

        if row:
            st.session_state.edit_data = row
        else:
            st.error("Question not found")

    if "edit_data" in st.session_state:

        si_no, subject, question, answer, difficulty = st.session_state.edit_data

        new_question = st.text_area("Edit Question", question)
        new_answer = st.text_area("Edit Answer", answer)

        new_subject = st.selectbox("Subject", SUBJECTS, index=SUBJECTS.index(subject))
        new_diff = st.selectbox("Difficulty", [1, 2, 3], index=difficulty - 1)

        col1, col2 = st.columns(2)

        with col1:
            if st.button("Update Question"):
                conn = get_connection()
                cur = conn.cursor()

                cur.execute("""
                    UPDATE quiz
                    SET subject=?, question=?, answer=?, difficulty=?
                    WHERE si_no=?
                """, (new_subject, new_question, new_answer, new_diff, si_no))

                conn.commit()
                conn.close()

                st.success("Updated successfully")

        with col2:
            if st.button("Delete Question"):
                conn = get_connection()
                cur = conn.cursor()

                cur.execute("DELETE FROM quiz WHERE si_no=?", (si_no,))
                conn.commit()
                conn.close()

                st.warning("Deleted successfully")
                del st.session_state.edit_data


elif mode == "Browse Questions":

    if not check_admin_login():
        st.stop()

    st.subheader("📚 Browse Questions")

    subject_filter = st.selectbox("Filter by Subject", ["All"] + SUBJECTS)

    page_size = 10

    if "page" not in st.session_state:
        st.session_state.page = 0

    offset = st.session_state.page * page_size

    conn = get_connection()
    cur = conn.cursor()

    if subject_filter == "All":
        cur.execute("""
            SELECT si_no, subject, question, difficulty
            FROM quiz
            LIMIT ? OFFSET ?
        """, (page_size, offset))
    else:
        cur.execute("""
            SELECT si_no, subject, question, difficulty
            FROM quiz
            WHERE subject=?
            LIMIT ? OFFSET ?
        """, (subject_filter, page_size, offset))

    rows = cur.fetchall()
    conn.close()

    for r in rows:
        st.write(f"ID: {r[0]} | {r[1]} | Diff: {r[3]}")
        st.write(r[2])
        st.markdown("---")

    col1, col2 = st.columns(2)

    with col1:
        if st.button("Previous"):
            if st.session_state.page > 0:
                st.session_state.page -= 1
                st.rerun()

    with col2:
        if st.button("Next"):
            st.session_state.page += 1
            st.rerun()


elif mode == "Live Dashboard":

    if not check_admin_login():
        st.stop()

    st.subheader("📊 Live Dashboard")


    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM quiz")
    total_questions = cur.fetchone()[0]

    cur.execute("""
        SELECT subject, COUNT(*)
        FROM quiz
        GROUP BY subject
    """)
    subject_counts = cur.fetchall()

    cur.execute("""
        SELECT subject, SUM(reading_times)
        FROM quiz
        GROUP BY subject
        ORDER BY SUM(reading_times) DESC
    """)
    leaderboard = cur.fetchall()

    st.metric("Total Questions", total_questions)

    st.subheader("Subject Distribution")
    # Desired subject order
    ordered_subjects = [
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

    # Convert DB result into dictionary
    subject_dict = {s[0]: s[1] for s in subject_counts}

    # Display in required order
    for subject in ordered_subjects:
        count = subject_dict.get(subject, 0)
        st.write(f"{subject} : {count}")

    cur.execute("""
        SELECT SUM(COALESCE(reading_times,0))
        FROM quiz
    """)
    total_reads = cur.fetchone()[0] or 0

    conn.close()

    st.subheader("Most Practiced Subjects")

    st.metric("Total Reads (All Subjects)", total_reads)


    for l in leaderboard:
        st.write(f"{l[0]} : {l[1]} reads")

    st.markdown("---")
    st.subheader("🔄 Reset Subject Read Count")

    # Extract subject names from leaderboard or subject_counts
    available_subjects = [s[0] for s in subject_counts]

    reset_subject = st.selectbox(
        "Select Subject to Reset",
        available_subjects
    )

    if st.button("Reset Read Count"):
        conn = get_connection()
        cur = conn.cursor()

        cur.execute("""
            UPDATE quiz
            SET reading_times = 0
            WHERE subject = ?
        """, (reset_subject,))

        conn.commit()
        conn.close()

        st.success(f"Read count reset for {reset_subject}")
        st.rerun()



elif mode == "Marked Questions":

    if not check_admin_login():
        st.stop()

    if st.button("Start Marked Practice"):
        st.session_state.questions = get_questions_marked(
            difficulty=difficulty_value,
            order=order_map[order_choice],
            marked_only=True
        )
        st.session_state.q_index = 0

    if "questions" in st.session_state:

        questions = st.session_state.questions

        if not questions:
            st.warning("No marked questions yet.")
            st.stop()

        if st.session_state.q_index >= len(questions):
            st.success("🎉 Marked Session Complete!")
            if st.button("Restart"):
                del st.session_state.questions
            st.stop()

        q = questions[st.session_state.q_index]
        si_no, subject, question, answer, diff, reads, is_marked = q

        st.markdown("---")
        st.markdown(f"**Subject:** {subject}")
        st.markdown(f"**Difficulty:** {['Easy','Moderate','Difficult'][diff-1]}")
        st.markdown(f"**Reads:** {reads}")

        st.markdown("### ❓ Question")
        st.write(question)

        if st.button("Show Answer"):
            st.success(answer)

        if st.button("❌ Unmark This Question"):
            toggle_mark(si_no, is_marked)
            st.success("Removed from marked list")
            st.rerun()

        if st.button("Next Question"):
            st.session_state.q_index += 1
            st.rerun()

