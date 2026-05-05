import streamlit as st
import psycopg2
import random
import hashlib
import pandas as pd
from datetime import datetime

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
        cur = conn.cursor()

        st.write("Username entered:", username)
        st.write("Password entered:", password)

        cur.execute("""
        SELECT id,password_hash,role
        FROM users
        WHERE username=%s
        """,(username,))

        row = cur.fetchone()

        st.write("Database row fetched:", row)

        if row:

            stored_password = row[1]
            hashed_input = hash_password(password)

            st.write("Stored password in DB:", stored_password)
            st.write("Hashed input password:", hashed_input)

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
            SET is_active=TRUE,
                last_active=%s
            WHERE id=%s
            """,(datetime.now(),row[0]))

            conn.commit()

            st.write("User login updated in DB")

            return row[0],row[2]

        st.error("Password verification failed")

    return None,None

# =====================================================
# SESSION INIT
# =====================================================

if "user_id" not in st.session_state:
    st.session_state.user_id=None
    st.session_state.role=None

# =====================================================
# LOGIN PAGE
# =====================================================

if st.session_state.user_id is None:

    st.title("🔐 Login")

    username=st.text_input("Username")
    password=st.text_input("Password",type="password")

    if st.button("Login"):

        try:
            conn = get_connection()
            st.success("Database connected successfully")
            conn.close()
        except Exception as e:
            st.error(f"DB ERROR: {e}")

        user_id,role=login_user(username,password)

        if user_id:
            st.session_state.user_id=user_id
            st.session_state.role=role
            st.rerun()

        else:
            st.error("Invalid credentials")

    st.stop()

# =====================================================
# SIDEBAR
# =====================================================

st.sidebar.success(f"Logged in as {st.session_state.role}")

if st.sidebar.button("Logout"):

    with get_connection() as conn:
        cur=conn.cursor()

        cur.execute("""
        UPDATE users
        SET is_active=FALSE,
            last_active=%s
        WHERE id=%s
        """,(datetime.now(),st.session_state.user_id))

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
        "User Management"
    ]
)

# =====================================================
# FETCH QUESTIONS
# =====================================================

def get_questions(subject=None,difficulty=None,order="random"):

    with get_connection() as conn:
        cur=conn.cursor()

        query="""
        SELECT si_no,subject,question,answer,difficulty,
        COALESCE(reading_times,0),COALESCE(is_marked,0)
        FROM quiz
        """

        conditions=[]
        params=[]

        if subject:
            conditions.append("subject=%s")
            params.append(subject)

        if difficulty:
            conditions.append("difficulty=%s")
            params.append(difficulty)

        if conditions:
            query+=" WHERE "+" AND ".join(conditions)

        if order=="most":
            query+=" ORDER BY reading_times DESC"

        if order=="least":
            query+=" ORDER BY reading_times ASC"

        cur.execute(query,params)
        rows=cur.fetchall()

    if order=="random":
        random.shuffle(rows)

    return rows

# =====================================================
# UPDATE READ COUNT
# =====================================================

def update_read_count(si_no, subject):

    today = datetime.now().strftime("%Y-%m-%d")

    with get_connection() as conn:
        cur = conn.cursor()

        # Update question read counter
        cur.execute(
            """
            UPDATE quiz
            SET reading_times = reading_times + 1
            WHERE si_no = %s
            """,
            (si_no,)
        )

        # Log every practice event
        cur.execute(
            """
            INSERT INTO practice_log(user_id,date,subject,question_id)
            VALUES(%s,%s,%s,%s)
            """,
            (
                st.session_state.user_id,
                today,
                subject,
                si_no
            )
        )
                
        conn.commit()

def update_bulk_read_count(question_list):

    today = datetime.now().strftime("%Y-%m-%d")

    ids = [q[0] for q in question_list]

    with get_connection() as conn:
        cur = conn.cursor()

        # Bulk update
        cur.execute(
            """
            UPDATE quiz
            SET reading_times = reading_times + 1
            WHERE si_no = ANY(%s)
            """,
            (ids,)
        )

        # Bulk insert logs
        log_data = [
            (
                st.session_state.user_id,
                today,
                q[1],
                q[0]
            )
            for q in question_list
        ]

        cur.executemany(
            """
            INSERT INTO practice_log(user_id,date,subject,question_id)
            VALUES(%s,%s,%s,%s)
            """,
            log_data
        )

        conn.commit()
        
def toggle_mark(si_no, current_status):
    conn = get_connection()
    cur = conn.cursor()
    new_status = 0 if current_status == 1 else 1
    cur.execute("UPDATE quiz SET is_marked=? WHERE si_no=?", (new_status, si_no))
    conn.commit()
    conn.close()


# ============================================================
# PRACTICE MODE (Subject + Mixed Unified Engine)
# ============================================================

if mode in ["Subject Practice", "Mixed Practice"]:

    # ---------------- SESSION STATE INIT ----------------

    defaults = {
        "session_easy": 0,
        "session_moderate": 0,
        "session_difficult": 0,
        "show_summary": False,
        "practice_active": False,
        "reviewed": 0,
        "answer_shown": False
    }

    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

    subject = None
    difficulty = None
    order_type = "random"

    # ========================================================
    # SUBJECT FILTER (Only in Subject Practice)
    # ========================================================

    if mode == "Subject Practice":

        with get_connection() as conn:
            cur = conn.cursor()

            cur.execute("""
                SELECT subject, COUNT(*)
                FROM quiz
                GROUP BY subject
                ORDER BY subject
            """)

            rows = cur.fetchall()

        subject_counts = {r[0]: r[1] for r in rows}

        if not subject_counts:
            st.warning("No questions available in database.")
            st.stop()

        subject_options = [
            f"{sub} ({count})"
            for sub, count in subject_counts.items()
        ]

        selected_display = st.selectbox(
            "Select Subject",
            subject_options
        )

        subject = selected_display.rsplit(" (", 1)[0]

    # ========================================================
    # DIFFICULTY FILTER
    # ========================================================

    difficulty_option = st.selectbox(
        "Difficulty",
        ["All", "Easy", "Moderate", "Difficult"]
    )

    difficulty_map = {
        "Easy": 1,
        "Moderate": 2,
        "Difficult": 3
    }

    if difficulty_option != "All":
        difficulty = difficulty_map[difficulty_option]

    # ========================================================
    # QUESTION TYPE
    # ========================================================

    order_option = st.selectbox(
        "Question Type",
        ["Random", "Most Read", "Least Read"]
    )

    order_map = {
        "Random": "random",
        "Most Read": "most",
        "Least Read": "least"
    }

    order_type = order_map[order_option]

    # ========================================================
    # START PRACTICE
    # ========================================================

    if not st.session_state.practice_active:

        if st.button("▶ Start Practice"):

            questions = get_questions(
                subject=subject,
                difficulty=difficulty,
                order=order_type
            )

            if not questions:
                st.warning("No questions found with selected filters.")
                st.stop()

            st.session_state.questions = questions
            st.session_state.index = 0
            st.session_state.reviewed = 0
            st.session_state.practice_active = True

            st.rerun()

        st.stop()

    # ========================================================
    # ACTIVE SESSION
    # ========================================================

    questions = st.session_state.questions

    if st.session_state.index >= len(questions):
        st.success("Session Complete")
        st.session_state.practice_active = False
        st.session_state.show_summary = True
        st.rerun()

    q = questions[st.session_state.index]

    si_no, subject, question, answer, diff, reads, marked = q

    st.info(f"Reviewed This Session: {st.session_state.reviewed}")

    st.write(f"**Question ID:** {si_no}")
    st.write(f"**Subject:** {subject}")
    st.write(f"**Reads:** {reads}")

    st.write(question)
    
    colA, colB = st.columns(2)

    with colA:
        if st.button("⭐ Mark / Unmark"):
            toggle_mark(si_no, marked)
            st.success("Updated")

    with colB:
        new_subject = st.selectbox(
            "Change Subject",
            SUBJECTS,
            key=f"subject_change_{si_no}"
        )

    if st.button("Update Subject"):
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "UPDATE quiz SET subject=%s WHERE si_no=%s",
                (new_subject, si_no)
            )
            conn.commit()
        st.success("Subject updated")

    # -------------------------------------------------------

    if st.button("Show Answer"):

        st.success(answer)

        update_read_count(si_no, subject)

        st.session_state.reviewed += 1
        st.session_state.answer_shown = True

        if diff == 1:
            st.session_state.session_easy += 1
        elif diff == 2:
            st.session_state.session_moderate += 1
        elif diff == 3:
            st.session_state.session_difficult += 1

    # -------------------------------------------------------

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
# PRACTICE SUMMARY
# ============================================================

if st.session_state.get("show_summary", False):

    st.markdown("## 📊 Practice Session Summary")

    st.metric(
        "Total Questions Reviewed",
        len(st.session_state.get("reviewed", []))
    )

    col1, col2, col3 = st.columns(3)

    col1.metric("Easy", st.session_state.session_easy)
    col2.metric("Moderate", st.session_state.session_moderate)
    col3.metric("Difficult", st.session_state.session_difficult)

    if st.button("Start New Session"):

        for key in [
            "practice_active",
            "reviewed",
            "session_easy",
            "session_moderate",
            "session_difficult",
            "show_summary"
        ]:
            st.session_state[key] = 0 if "session" in key else False

        st.rerun()
# =====================================================
# LIVE DASHBOARD
# =====================================================

elif mode == "Live Dashboard":

    st.subheader("📊 User Dashboard")

    user_id = st.session_state.user_id
    role = st.session_state.role

    # ====================================================
    # 1️⃣ TOTAL QUESTIONS (GLOBAL)
    # ====================================================

    with get_connection() as conn:
        cur = conn.cursor()

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

    # ====================================================
    # 2️⃣ USER TOTAL READ COUNT
    # ====================================================

    with get_connection() as conn:
        cur = conn.cursor()

        cur.execute("""
            SELECT COUNT(*)
            FROM practice_log
            WHERE user_id = %s
        """, (user_id,))

        user_total_reads = cur.fetchone()[0] or 0

    st.markdown("## 📈 Your Practice Stats")

    col1, col2 = st.columns([3,1])

    with col1:
        st.metric("Total Questions Practiced", user_total_reads)

    with col2:
        if st.button("Reset Total Reads"):

            with get_connection() as conn:
                cur = conn.cursor()

                cur.execute("""
                    DELETE FROM practice_log
                    WHERE user_id = %s
                """, (user_id,))

                conn.commit()

            st.success("Your total practice data has been reset.")
            st.rerun()

    # ====================================================
    # 3️⃣ SUBJECT-WISE USER READ COUNT
    # ====================================================

    with get_connection() as conn:
        cur = conn.cursor()

        cur.execute("""
            SELECT subject, COUNT(*)
            FROM practice_log
            WHERE user_id = %s
            GROUP BY subject
            ORDER BY COUNT(*) DESC
        """, (user_id,))

        subject_reads = cur.fetchall()

    if subject_reads:

        st.markdown("### 📊 Subject-wise Practice")

        for subject, count in subject_reads:

            col1, col2 = st.columns([3,1])

            with col1:
                st.write(f"{subject} : {count}")

            with col2:
                if st.button(f"Reset {subject}", key=f"reset_{subject}"):

                    with get_connection() as conn:
                        cur = conn.cursor()

                        cur.execute("""
                            DELETE FROM practice_log
                            WHERE user_id = %s
                            AND subject = %s
                        """, (user_id, subject))

                        conn.commit()

                    st.success(f"{subject} data reset.")
                    st.rerun()

    else:
        st.info("No practice data yet.")

    st.markdown("---")

    if role == "admin":

        st.markdown("## 👑 Admin: All Users Practice Stats")

        with get_connection() as conn:
            cur = conn.cursor()

            cur.execute("""
                SELECT u.username, COUNT(p.question_id)
                FROM users u
                LEFT JOIN practice_log p
                ON u.id = p.user_id
                GROUP BY u.username
                ORDER BY COUNT(p.question_id) DESC
            """)

            user_stats = cur.fetchall()

        if user_stats:

            for username, total in user_stats:

                col1, col2 = st.columns([3,1])

                with col1:
                    st.write(f"{username}")

                with col2:
                    st.metric("Total Practiced", total)

        else:
            st.info("No user practice data yet.")

# ============================================================
# MARKED QUESTIONS
# ============================================================

elif mode == "Marked Questions":

    with get_connection() as conn:
        cur = conn.cursor()

        cur.execute("""
            SELECT si_no, subject, question, answer, difficulty,
                   COALESCE(reading_times,0), COALESCE(is_marked,0)
            FROM quiz
            WHERE is_marked = 1
        """)

        rows = cur.fetchall()

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

    with get_connection() as conn:
        cur = conn.cursor()

        cur.execute("""
            SELECT date, COUNT(*)
            FROM practice_log
            WHERE user_id = %s
            GROUP BY date
            ORDER BY date
        """, (st.session_state.user_id,))

        rows = cur.fetchall()

    if rows:

        dates = [r[0] for r in rows]
        counts = [r[1] for r in rows]

        formatted_dates = [
            d.strftime("%d %b") if hasattr(d, "strftime") else str(d)
            for d in dates
        ]

        df = pd.DataFrame(
            {"Questions Practiced": counts},
            index=formatted_dates
        )

        st.line_chart(df)

    else:
        st.info("No data yet")

# =====================================================
# USER MANAGEMENT
# =====================================================

elif mode == "User Management":

    if st.session_state.role != "admin":
        st.error("Admin access required")
        st.stop()

    st.subheader("👥 User Management Panel")

    # ========================================================
    # 1️⃣ LIST USERS
    # ========================================================

    with get_connection() as conn:
        cur = conn.cursor()

        cur.execute("""
            SELECT id, username, role, is_active, last_active
            FROM users
            ORDER BY username
        """)
        users = cur.fetchall()

    st.markdown("### 📋 All Users")

    for user_id, username, role, is_active, last_active in users:

        col1, col2, col3, col4, col5 = st.columns([2,1,1,2,2])

        with col1:
            st.write(username)

        with col2:
            st.write(role)

        with col3:
            if is_active:
                st.success("Active")
            else:
                st.error("Inactive")

        with col4:
            st.write(last_active if last_active else "Never")

        with col5:
            if st.button("Delete", key=f"delete_{user_id}"):

                with get_connection() as conn:
                    cur = conn.cursor()

                    cur.execute(
                        "DELETE FROM users WHERE id = %s",
                        (user_id,)
                    )

                    cur.execute(
                        "DELETE FROM practice_log WHERE user_id = %s",
                        (user_id,)
                    )

                    conn.commit()

                st.success("User deleted")
                st.rerun()

    st.markdown("---")

    # ========================================================
    # 2️⃣ CREATE USER
    # ========================================================

    st.markdown("### ➕ Create New User")

    new_username = st.text_input("Username")
    new_password = st.text_input("Password", type="password")
    new_role = st.selectbox("Role", ["student", "admin"])

    if st.button("Create User"):

        try:
            with get_connection() as conn:
                cur = conn.cursor()

                cur.execute("""
                    INSERT INTO users (username, password_hash, role)
                    VALUES (%s, %s, %s)
                """, (
                    new_username,
                    hash_password(new_password),
                    new_role
                ))

                conn.commit()

            st.success("User created successfully")
            st.rerun()

        except Exception as e:
            st.error("Username already exists")

    st.markdown("---")

    # ========================================================
    # 3️⃣ MODIFY USER
    # ========================================================

    st.markdown("### ✏ Modify User")

    usernames = [u[1] for u in users]

    selected_user = st.selectbox("Select User", usernames)

    new_password = st.text_input(
        "New Password (leave blank to keep same)",
        type="password"
    )

    new_role = st.selectbox("New Role", ["student", "admin"])

    if st.button("Update User"):

        with get_connection() as conn:
            cur = conn.cursor()

            if new_password:

                cur.execute("""
                    UPDATE users
                    SET password_hash = %s,
                        role = %s
                    WHERE username = %s
                """, (
                    hash_password(new_password),
                    new_role,
                    selected_user
                ))

            else:

                cur.execute("""
                    UPDATE users
                    SET role = %s
                    WHERE username = %s
                """, (
                    new_role,
                    selected_user
                ))

            conn.commit()

        st.success("User updated successfully")
        st.rerun()

# ========================================================
# INSERT QUESTION
# ========================================================

elif mode == "Insert Question":

    st.subheader("➕ Insert New Question")

    if "insert_question" not in st.session_state:
        st.session_state.insert_question = ""

    if "insert_answer" not in st.session_state:
        st.session_state.insert_answer = ""

    question = st.text_area("Enter Question", key="insert_question")
    answer = st.text_area("Enter Answer", key="insert_answer")

    subject = st.selectbox("Select Subject", SUBJECTS)

    difficulty_label = st.selectbox(
        "Difficulty",
        ["Easy", "Moderate", "Difficult"]
    )

    difficulty_map = {"Easy":1,"Moderate":2,"Difficult":3}
    difficulty = difficulty_map[difficulty_label]

    col1,col2 = st.columns(2)

    with col1:

        if st.button("💾 Save Question"):

            if not question.strip() or not answer.strip():
                st.error("Question and Answer cannot be empty.")

            else:

                with get_connection() as conn:
                    cur = conn.cursor()

                    cur.execute("""
                        INSERT INTO quiz (subject,question,answer,difficulty)
                        VALUES (%s,%s,%s,%s)
                        RETURNING si_no
                    """,(
                        subject,
                        question.strip(),
                        answer.strip(),
                        difficulty
                    ))

                    inserted_id = cur.fetchone()[0]

                    conn.commit()

                st.success(f"Question added successfully! 🆔 ID: {inserted_id}")
                st.info(f"New Question ID: {inserted_id}")

                st.session_state.pop("insert_question",None)
                st.session_state.pop("insert_answer",None)
                st.rerun()

    with col2:

        if st.button("🔄 Reset Fields"):

            st.session_state.pop("insert_question",None)
            st.session_state.pop("insert_answer",None)
            st.rerun()


# ========================================================
# IMPORT FROM TXT
# ========================================================

elif mode == "Import from TXT":

    st.subheader("📂 Import Questions from TXT")

    uploaded_file = st.file_uploader("Upload TXT File",type=["txt"])

    difficulty_label = st.selectbox(
        "Difficulty",
        ["Easy","Moderate","Difficult"]
    )

    difficulty_map = {"Easy":1,"Moderate":2,"Difficult":3}
    difficulty = difficulty_map[difficulty_label]

    if uploaded_file is not None:

        file_content = uploaded_file.read().decode("utf-8")
        lines = [l.strip() for l in file_content.split("\n") if l.strip()]

        inserted = 0
        current_subject = "General"

        if st.button("Import Now"):

            with get_connection() as conn:
                cur = conn.cursor()

                for line in lines:

                    if line.startswith("* "):
                        current_subject = line[2:].strip()
                        continue

                    if "-->" in line:
                        question,answer = line.split("-->",1)
                        question = question.strip()
                        answer = answer.strip()
                    else:
                        continue

                    if question and answer:

                        cur.execute("""
                            INSERT INTO quiz (subject,question,answer,difficulty)
                            VALUES (%s,%s,%s,%s)
                        """,(
                            current_subject,
                            question,
                            answer,
                            difficulty
                        ))

                        inserted += 1

                conn.commit()

            st.success(f"{inserted} questions imported successfully.")
            st.rerun()


# ========================================================
# UPDATE / DELETE QUESTION
# ========================================================

elif mode == "Update Question":

    st.subheader("✏ Update / Delete Question")

    qid = st.number_input("Enter Question ID",min_value=1,step=1)

    if st.button("Load Question"):

        with get_connection() as conn:
            cur = conn.cursor()

            cur.execute("""
                SELECT subject,question,answer,difficulty
                FROM quiz
                WHERE si_no = %s
            """,(qid,))

            row = cur.fetchone()

        if row:

            st.session_state.edit_data = {
                "id":qid,
                "subject":row[0],
                "question":row[1],
                "answer":row[2],
                "difficulty":row[3]
            }

        else:
            st.error("Question not found.")

    if "edit_data" in st.session_state:

        data = st.session_state.edit_data

        new_question = st.text_area("Question",value=data["question"])
        new_answer = st.text_area("Answer",value=data["answer"])

        new_subject = st.selectbox(
            "Subject",
            SUBJECTS,
            index=SUBJECTS.index(data["subject"])
        )

        difficulty_map = {"Easy":1,"Moderate":2,"Difficult":3}
        reverse_map = {1:"Easy",2:"Moderate",3:"Difficult"}

        difficulty_label = st.selectbox(
            "Difficulty",
            ["Easy","Moderate","Difficult"],
            index=["Easy","Moderate","Difficult"].index(
                reverse_map[data["difficulty"]]
            )
        )

        col1,col2 = st.columns(2)

        with col1:

            if st.button("Save Changes"):

                if not new_question.strip() and not new_answer.strip():

                    with get_connection() as conn:
                        cur = conn.cursor()

                        cur.execute(
                            "DELETE FROM quiz WHERE si_no = %s",
                            (data["id"],)
                        )

                        conn.commit()

                    st.success("Question deleted successfully.")
                    st.session_state.pop("edit_data",None)
                    st.rerun()

                else:

                    with get_connection() as conn:
                        cur = conn.cursor()

                        cur.execute("""
                            UPDATE quiz
                            SET subject=%s,
                                question=%s,
                                answer=%s,
                                difficulty=%s
                            WHERE si_no=%s
                        """,(
                            new_subject,
                            new_question.strip(),
                            new_answer.strip(),
                            difficulty_map[difficulty_label],
                            data["id"]
                        ))

                        conn.commit()

                    st.success("Question updated successfully.")
                    st.session_state.pop("edit_data",None)
                    st.rerun()

        with col2:

            if st.button("Cancel"):
                st.session_state.pop("edit_data",None)
                st.rerun()

# ========================================================
#  BULK VIEW (SESSION BASED - CLEAN VERSION)
# ========================================================

elif mode == "Bulk View":

    # ====================================================
    # 🔹 SESSION STATE INITIALIZATION
    # ====================================================
    defaults = {
        "bulk_started": False,
        "bulk_subject": "All",
        "bulk_q_count": 30,
        "bulk_index": 0,
        "practice_log": [],
        "reviewed": [],
        "show_summary": False,
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

    st.subheader("📚 Bulk Practice Mode")

    # ====================================================
    # 🔹 STEP 1: INPUT PANEL (FIXED)
    # ====================================================
    if not st.session_state.bulk_started:

        q_count = st.number_input(
            "Enter number of questions per set",
            min_value=1,
            max_value=100,
            value=30
        )

        subject = st.selectbox(
            "Select Subject (Optional)",
            ["All"] + SUBJECTS
        )

        if st.button("Start Practice"):
            st.session_state.bulk_started = True
            st.session_state.bulk_q_count = q_count
            st.session_state.bulk_subject = subject
            st.session_state.bulk_index = 0
            st.session_state.practice_log = []
            st.session_state.reviewed = []
            st.session_state.show_summary = False

            # 🔹 Clear old page keys
            for key in list(st.session_state.keys()):
                if key.startswith("bulk_updated_"):
                    del st.session_state[key]

            st.rerun()

        st.stop()

    # ====================================================
    # 🔹 STEP 2: LOAD QUESTIONS
    # ====================================================
    subject = st.session_state.bulk_subject

    questions = get_questions(
        subject=None if subject == "All" else subject
    )

    if not questions:
        st.warning("No questions found")
        st.stop()

    q_count = st.session_state.bulk_q_count
    start = st.session_state.bulk_index
    end = start + q_count

    chunk = questions[start:end]

    if not chunk:
        st.info("No more questions available.")
        st.session_state.show_summary = True

    # ====================================================
    # 🔹 STEP 3: TRACK PRACTICE (SAFE)
    # ====================================================
    page_key = f"bulk_updated_{start}"

    if page_key not in st.session_state:

        update_bulk_read_count(chunk)

        for q in chunk:
            si_no, subject, *_ = q

            # avoid duplicates
            if si_no not in st.session_state.reviewed:
                st.session_state.reviewed.append(si_no)
                st.session_state.practice_log.append((si_no, subject))

        st.session_state[page_key] = True

    # ====================================================
    # 🔹 STEP 4: DISPLAY QUESTIONS
    # ====================================================
    for i, q in enumerate(chunk, start=1):
        si_no, subject, question, answer, diff, reads, marked = q

        st.markdown(f"### Q{i} (ID: {si_no})")
        st.markdown(f"**Subject:** `{subject}`")
        st.write(question)
        st.success(answer)

        colA, colB = st.columns([1, 3])

        with colA:
            mark_label = "⭐ Marked" if marked else "☆ Mark"
            if st.button(mark_label, key=f"mark_{si_no}"):
                toggle_mark_question(si_no, not marked)
                st.rerun()

        st.markdown("---")

    # ====================================================
    # 🔹 STEP 5: NAVIGATION
    # ====================================================
    col1, col2 = st.columns(2)

    with col1:
        if st.button("➡️ Next Set"):
            st.session_state.bulk_index += q_count
            st.rerun()

    with col2:
        if st.button("✅ Complete"):
            st.session_state.show_summary = True
            st.rerun()

    # ====================================================
    # 🔹 STEP 6: SUMMARY
    # ====================================================
    if st.session_state.show_summary:

        st.subheader("📊 Practice Summary")

        total = len(st.session_state.reviewed)

        # ✅ FIXED METRIC (no crash)
        st.metric("Total Questions Reviewed", total)

        # Subject-wise distribution
        subject_count = {}
        for _, sub in st.session_state.practice_log:
            subject_count[sub] = subject_count.get(sub, 0) + 1

        st.write("### Subject-wise Distribution")
        for sub, cnt in subject_count.items():
            st.write(f"- {sub}: {cnt}")

        # ====================================================
        # 🔹 RESET BUTTON
        # ====================================================
        if st.button("🔄 Start New Session"):

            keys_to_delete = [
                "bulk_started",
                "bulk_subject",
                "bulk_q_count",
                "bulk_index",
                "practice_log",
                "reviewed",
                "show_summary",
            ]

            for key in keys_to_delete:
                if key in st.session_state:
                    del st.session_state[key]

            # clear page keys
            for key in list(st.session_state.keys()):
                if key.startswith("bulk_updated_"):
                    del st.session_state[key]

            st.rerun()










