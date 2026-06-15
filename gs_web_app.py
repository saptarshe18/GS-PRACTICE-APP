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
    st.session_state.user_id = None
    st.session_state.role = None

# =====================================================
# LOGIN PAGE
# =====================================================

if st.session_state.user_id is None:
    st.title("🔐 Login")
    username = st.text_input("Username")
    password = st.text_input("Password",type="password")

    if st.button("Login"):
        try:
            conn = get_connection()
            st.success("Database connected successfully")
            conn.close()
        except Exception as e:
            st.error(f"DB ERROR: {e}")

        user_id,role = login_user(username,password)
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
# SIDEBAR NAVIGATION (MODES Restructuring)
# =====================================================

st.sidebar.success(f"Logged in as {st.session_state.role}")

if st.sidebar.button("Logout"):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
        UPDATE users
        SET is_active=FALSE,
            last_active=%s
        WHERE id=%s
        """,(datetime.now(),st.session_state.user_id))
        conn.commit()
    st.session_state.clear()
    st.rerun()

# 1) Parent Mode Setup
parent_mode = st.sidebar.selectbox(
    "Select Mode",
    ["Notes", "Test/Practice", "User Management"]
)

# 2) Child Option Setup for Test/Practice
test_practice_option = None
if parent_mode == "Test/Practice":
    test_practice_option = st.sidebar.radio(
        "Test/Practice Options",
        [
            "Subject Practice", 
            "Mixed Practice", 
            "Bulk Practice", 
            "Analytics", 
            "Dashboard", 
            "Update Question", 
            "Insert Question", 
            "Import Question from txt", 
            "Marked Questions"
        ]
    )

# ============================================================
# NOTES METADATA UTILITIES & CONFIGURATIONS
# ============================================================
def add_subject(subject_name):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("INSERT INTO notes_subjects(subject_name) VALUES(%s)", (subject_name,))
    conn.commit()
    conn.close()

def get_all_subjects():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, subject_name FROM notes_subjects ORDER BY subject_name")
    rows = cur.fetchall()
    conn.close()
    return rows

def update_subject(subject_id, updated_name):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE notes_subjects SET subject_name=%s WHERE id=%s", (updated_name, subject_id))
    conn.commit()
    conn.close()

def delete_subject(subject_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM notes_subjects WHERE id=%s", (subject_id,))
    conn.commit()
    conn.close()

def add_chapter(subject_id, chapter_name):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("INSERT INTO notes_chapters(subject_id, chapter_name) VALUES(%s, %s)", (subject_id, chapter_name))
    conn.commit()
    conn.close()

def get_chapters(subject_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, subject_id, chapter_name FROM notes_chapters WHERE subject_id=%s ORDER BY chapter_name", (subject_id,))
    rows = cur.fetchall()
    conn.close()
    return rows

def update_chapter(chapter_id, updated_name):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE notes_chapters SET chapter_name=%s WHERE id=%s", (updated_name, chapter_id))
    conn.commit()
    conn.close()

def delete_chapter(chapter_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM notes_chapters WHERE id=%s", (chapter_id,))
    conn.commit()
    conn.close()

def add_note(chapter_id, new_text, image_url=None):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, note_text, image_path FROM notes_content WHERE chapter_id=%s", (chapter_id,))
    existing = cur.fetchone()

    if existing:
        note_id, old_text, old_image = existing
        combined_text = (old_text or "") + "\n\n" + (new_text or "")
        final_image = image_url or old_image
        cur.execute("UPDATE notes_content SET note_text=%s, image_path=%s WHERE id=%s", (combined_text, final_image, note_id))
    else:
        cur.execute("INSERT INTO notes_content(chapter_id, note_text, image_path) VALUES(%s,%s,%s)", (chapter_id, new_text, image_url))
    conn.commit()
    conn.close()

def get_notes(chapter_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, chapter_id, note_text, image_path, created_at FROM notes_content WHERE chapter_id=%s ORDER BY created_at", (chapter_id,))
    rows = cur.fetchall()
    conn.close()
    return rows

def update_note(note_id, note_text, image_url):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE notes_content SET note_text=%s, image_path=%s WHERE id=%s", (note_text, image_url, note_id))
    conn.commit()
    conn.close()

def delete_note(note_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM notes_content WHERE id=%s", (note_id,))
    conn.commit()
    conn.close()

def upload_note_image(uploaded_file):
    ext = uploaded_file.name.split(".")[-1]
    filename = f"{uuid.uuid4()}.{ext}"
    filepath = f"notes/{filename}"
    supabase.storage.from_("notes-images").upload(filepath, uploaded_file.getvalue())
    public_url = supabase.storage.from_("notes-images").get_public_url(filepath)
    return public_url

# =====================================================
# FETCH & PROCESS QUESTIONS UTILITIES
# =====================================================

def get_questions(
        subject=None,
        difficulty=None,
        chapter_code=None,
        order="random"
):
    with get_connection() as conn:
        cur = conn.cursor()

        query = """
        SELECT
            si_no,
            subject,
            question,
            answer,
            difficulty,
            COALESCE(reading_times,0),
            COALESCE(is_marked,0)
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

        if chapter_code:
            conditions.append("chapters=%s")
            params.append(chapter_code)

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        if order == "most":
            query += " ORDER BY reading_times DESC"

        elif order == "least":
            query += " ORDER BY reading_times ASC"

        cur.execute(query, params)
        rows = cur.fetchall()

    if order == "random":
        random.shuffle(rows)

    return rows
    
def update_question_chapter(si_no,chapter_name):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT chapter_code 
            FROM subject_chapters 
            WHERE chapter_name = %s
            """, (chapter_name,))
        code = cur.fetchone()
        conn.commit()
        
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
            UPDATE quiz 
            SET chapters = %s 
            WHERE si_no = %s
        """, (code, si_no))
        conn.commit()
        
def update_read_count(si_no, subject):
    today = datetime.now().date()
    column = SUBJECT_COLUMN_MAP.get(subject)
    if not column:
        return
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("UPDATE quiz SET reading_times = COALESCE(reading_times,0) + 1 WHERE si_no = %s", (si_no,))
        cur.execute("INSERT INTO practice_summary(user_id, practice_date) VALUES(%s,%s) ON CONFLICT (user_id, practice_date) DO NOTHING", (st.session_state.user_id, today))
        query = f"UPDATE practice_summary SET {column} = COALESCE({column},0) + 1 WHERE user_id = %s AND practice_date = %s"
        cur.execute(query, (st.session_state.user_id, today))
        conn.commit()

def update_bulk_read_count(question_list):
    today = datetime.now().date()
    ids = [q[0] for q in question_list]
    subject_counts = {}
    for q in question_list:
        subject = q[1]
        subject_counts[subject] = subject_counts.get(subject, 0) + 1

    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("UPDATE quiz SET reading_times = COALESCE(reading_times,0) + 1 WHERE si_no = ANY(%s)", (ids,))
        cur.execute("INSERT INTO practice_summary(user_id, practice_date) VALUES(%s,%s) ON CONFLICT (user_id, practice_date) DO NOTHING", (st.session_state.user_id, today))
        
        for subject, count in subject_counts.items():
            column = SUBJECT_COLUMN_MAP.get(subject)
            if not column:
                continue
            query = f"UPDATE practice_summary SET {column} = COALESCE({column},0) + %s WHERE user_id = %s AND practice_date = %s"
            cur.execute(query, (count, st.session_state.user_id, today))
        conn.commit()

def toggle_mark(si_no, current_status):
    conn = get_connection()
    cur = conn.cursor()
    new_status = 0 if current_status == 1 else 1
    cur.execute("UPDATE quiz SET is_marked=%s WHERE si_no=%s", (new_status, si_no))
    conn.commit()
    conn.close()

def delete_marked_question(si_no):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM quiz WHERE si_no=%s", (si_no,))
    conn.commit()
    conn.close()

# ============================================================
# 1) NOTES PARENT MODE
# ============================================================
if parent_mode == "Notes":
    st.title("📚 Notes Management")
    notes_menu = st.sidebar.radio(
        "Notes Menu",
        ["View Notes", "Manage Subjects", "Manage Chapters", "Manage Notes"]
    )

    if notes_menu == "View Notes":
        st.subheader("📖 View Notes")
        subjects = get_all_subjects()
        if not subjects:
            st.warning("No subjects available")
            st.stop()
        
        subject_map = {s[1]: s[0] for s in subjects}
        selected_subject = st.selectbox("Select Subject", list(subject_map.keys()))
        subject_id = subject_map[selected_subject]

        chapters = get_chapters(subject_id)
        if not chapters:
            st.warning("No chapters available")
            st.stop()
        
        chapter_map = {c[2]: c[0] for c in chapters}
        selected_chapter = st.selectbox("Select Chapter", list(chapter_map.keys()))
        chapter_id = chapter_map[selected_chapter]

        notes = get_notes(chapter_id)
        if not notes:
            st.info("No notes found")
            st.stop()
        
        st.markdown("---")
        if notes:
            note = notes[0]
            st.markdown("## 📝 Note")
            if note[2]:
                st.markdown(note[2])
            if note[3]:
                st.image(note[3])

    # Remaining management modes inside notes can extend below...

# ============================================================
# 2) TEST/PRACTICE PARENT MODE
# ============================================================
elif parent_mode == "Test/Practice":
    
    # 2.1) Subject Practice & 2.2) Mixed Practice
    if test_practice_option in ["Subject Practice", "Mixed Practice"]:
        st.title(f"✍️ {test_practice_option}")
        defaults = {
            "session_easy": 0, "session_moderate": 0, "session_difficult": 0,
            "show_summary": False, "practice_active": False, "reviewed": 0, "answer_shown": False
        }
        for k, v in defaults.items():
            if k not in st.session_state:
                st.session_state[k] = v

        subject = None
        difficulty = None
        order_type = "random"
        chapter_code = None

        if test_practice_option == "Mixed Practice":

            filter_chapter = st.checkbox(
                "Filter By Chapter"
            )

           if filter_chapter:

                subject = st.selectbox(
                    "Select Subject",
                    SUBJECTS
                )

                with get_connection() as conn:
                    cur = conn.cursor()

                    cur.execute("""
                        SELECT chapter_name,
                               chapter_code
                        FROM subject_chapters
                        WHERE subject=%s
                        ORDER BY chapter_name
                    """,(subject,))

                    rows = cur.fetchall()

                chapter_map = {
                    row[0]: row[1]
                    for row in rows
                }

                selected_chapter = st.selectbox(
                    "Select Chapter",
                    list(chapter_map.keys())
                )

                chapter_code = chapter_map[selected_chapter]

        if test_practice_option == "Subject Practice":
            with get_connection() as conn:
                cur = conn.cursor()
                cur.execute("SELECT subject, COUNT(*) FROM quiz GROUP BY subject ORDER BY subject")
                rows = cur.fetchall()
            subject_counts = {r[0]: r[1] for r in rows}
            if not subject_counts:
                st.warning("No questions available in database.")
                st.stop()

            subject_options = [f"{sub} ({count})" for sub, count in subject_counts.items()]
            selected_display = st.selectbox("Select Subject", subject_options)
            subject = selected_display.rsplit(" (", 1)[0]
            chapter_code = None

            with get_connection() as conn:
                cur = conn.cursor()

                cur.execute("""
                    SELECT chapter_name,
                           chapter_code
                    FROM subject_chapters
                    WHERE subject=%s
                    ORDER BY chapter_name
                """,(subject,))

                rows = cur.fetchall()

          chapter_map = {
                row[0]: row[1]
                for row in rows
                 }

          selected_chapter = st.selectbox(
                "Select Chapter",
                ["All Chapters"] + list(chapter_map.keys())
                )

          if selected_chapter != "All Chapters":
             chapter_code = chapter_map[selected_chapter]

        difficulty_option = st.selectbox("Difficulty", ["All", "Easy", "Moderate", "Difficult"])
        difficulty_map = {"Easy": 1, "Moderate": 2, "Difficult": 3}
        if difficulty_option != "All":
            difficulty = difficulty_map[difficulty_option]

        order_option = st.selectbox("Question Type", ["Random", "Most Read", "Least Read"])
        order_map = {"Random": "random", "Most Read": "most", "Least Read": "least"}
        order_type = order_map[order_option]

        if not st.session_state.practice_active:
            if st.button("▶ Start Practice"):
                questions = get_questions(subject=subject, difficulty=difficulty, chapter_code=chapter_code, order=order_type)
                if not questions:
                    st.warning("No questions found with selected filters.")
                    st.stop()
                st.session_state.questions = questions
                st.session_state.index = 0
                st.session_state.reviewed = 0
                st.session_state.practice_active = True
                st.rerun()
            st.stop()

        questions = st.session_state.questions
        if st.session_state.index >= len(questions):
            st.success("Session Complete")
            st.session_state.practice_active = False
            st.session_state.show_summary = True
            st.rerun()

        q = questions[st.session_state.index]
        # chapters column index loaded from quiz structure (mapping to string or None)
        si_no, subject, question, answer, diff, reads, marked = q

        st.info(f"Reviewed This Session: {st.session_state.reviewed}")
        st.write(f"**Question ID:** {si_no}")
        st.write(f"**Subject:** {subject}")
        st.write(f"**Reads:** {reads}")
        st.write(question)

        # ----------------------------------------------------
        # DYNAMIC CHAPTER DROPDOWN LOGIC FOR THIS QUESTION
        # ----------------------------------------------------
        st.markdown("### 🏷️ Map Chapter")
        
        # 1. First find the matching internal notes subject ID safely
        with get_connection() as conn:
            cur = conn.cursor()
            
            db_chapters = []
            # Fetch all chapters created under this subject
            cur.execute("""
                    SELECT chapter_name 
                    FROM subject_chapters 
                    WHERE subject = %s 
                    ORDER BY chapter_name
                """, (subject,))
            db_chapters = cur.fetchall()
            
            # Fetch current linked chapter text in quiz if it exists
            cur.execute("SELECT chapters FROM quiz WHERE si_no = %s", (si_no,))
            quiz_row = cur.fetchone()
            cur.execute("SELECT chapter_name FROM subject_chapters WHERE chapter_code = %s", (quiz_row,))
            sub_quiz = cur.fetchone()
            current_mapped_chapter = quiz_row[0] if sub_quiz else None

        # 2. Render Dropdown Menu safely
        chapter_options = ["None / Unassigned"] + [ch[0] for ch in db_chapters]
        
        # Pre-select index if it matches what is already inside the quiz DB
        default_idx = 0
        if current_mapped_chapter and current_mapped_chapter in chapter_options:
            default_idx = chapter_options.index(current_mapped_chapter)

        selected_chapter = st.selectbox(
            f"Select Chapter for Q-{si_no}", 
            options=chapter_options, 
            index=default_idx
        )

        st.markdown("---")

        # ----------------------------------------------------
        # INTERACTION BUTTONS
        # ----------------------------------------------------
        colA, colB = st.columns(2)
        with colA:
            if st.button("⭐ Mark / Unmark"):
                toggle_mark(si_no, marked)
                st.success("Updated")
        with colB:
            new_subject = st.selectbox("Change Subject", SUBJECTS, key=f"subject_change_{si_no}")

        if st.button("Update Subject"):
            with get_connection() as conn:
                cur = conn.cursor()
                cur.execute("UPDATE quiz SET subject=%s WHERE si_no=%s", (new_subject, si_no))
                conn.commit()
            st.success("Subject updated")

        if st.button("Show Answer"):
            st.success(answer)
            update_read_count(si_no, subject)
            st.session_state.reviewed += 1
            st.session_state.answer_shown = True
            if diff == 1: st.session_state.session_easy += 1
            elif diff == 2: st.session_state.session_moderate += 1
            elif diff == 3: st.session_state.session_difficult += 1

        col1, col2 = st.columns(2)
        with col1:
            if st.button("Next ➡️"):
                # AUTOMATIC SAVE ON MOVE NEXT
                final_chapter_val = None if selected_chapter == "None / Unassigned" else selected_chapter
                update_question_chapter(si_no,final_chapter_val)
                
                st.session_state.index += 1
                st.session_state.answer_shown = False
                st.rerun()
        with col2:
            if st.button("⏹ End Practice"):
                # AUTOMATIC SAVE ON FINISH
                final_chapter_val = None if selected_chapter == "None / Unassigned" else selected_chapter
                update_question_chapter(si_no, final_chapter_val)
                
                st.session_state.practice_active = False
                st.session_state.show_summary = True
                st.rerun()

    # 2.3) Bulk Practice
    elif test_practice_option == "Bulk Practice":
        defaults = {
            "bulk_started": False, "bulk_subject": "All", "bulk_q_count": 30,
            "bulk_index": 0, "practice_log": [], "reviewed": 0, "show_summary": False
        }
        for key, value in defaults.items():
            if key not in st.session_state:
                st.session_state[key] = value

        st.subheader("📚 Bulk Practice Mode")
        if not st.session_state.bulk_started:
            q_count = st.number_input("Enter number of questions per set", min_value=1, max_value=100, value=30)
            subject = st.selectbox("Select Subject (Optional)", ["All"] + SUBJECTS)
            chapter_code = None

            if subject != "All":

            with get_connection() as conn:
                cur = conn.cursor()

                cur.execute("""
                    SELECT chapter_name,
                           chapter_code
                    FROM subject_chapters
                    WHERE subject=%s
                    ORDER BY chapter_name
                    """,(subject,))

               rows = cur.fetchall()

            chapter_map = {
                row[0]: row[1]
                for row in rows
            }

            selected_chapter = st.selectbox(
                "Select Chapter",
                ["All Chapters"] + list(chapter_map.keys())
            )

           if selected_chapter != "All Chapters":
                chapter_code = chapter_map[selected_chapter]
            if st.button("Start Practice"):
                st.session_state.bulk_started = True
                st.session_state.bulk_q_count = q_count
                st.session_state.bulk_subject = subject
                st.session_state.bulk_chapter_code = chapter_code
                st.session_state.bulk_index = 0
                st.session_state.practice_log = []
                st.session_state.reviewed = 0
                st.session_state.show_summary = False
                for k in list(st.session_state.keys()):
                    if k.startswith("bulk_updated_"): del st.session_state[k]
                st.rerun()
            st.stop()

        subject = st.session_state.bulk_subject
        questions = get_questions(
                subject=None if subject == "All" else subject,
                chapter_code=st.session_state.bulk_chapter_code
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

        page_key = f"bulk_updated_{start}"
        if page_key not in st.session_state:
            update_bulk_read_count(chunk)
            for q in chunk:
                si_no, subject, *_ = q
                st.session_state.reviewed += 1
                st.session_state.practice_log.append((si_no, subject))
            st.session_state[page_key] = True

        for i, q in enumerate(chunk, start=1):
            si_no, subject, question, answer, diff, reads, marked = q
            st.markdown(f"### Q{i} (ID: {si_no})")
            st.markdown(f"**Subject:** `{subject}`")
            st.caption(f"👁️ Read Count: {reads or 0}")
            st.write(question)
            st.success(answer)
            mark_label = "⭐ Marked" if marked else "☆ Mark"
            if st.button(mark_label, key=f"mark_{si_no}"):
                toggle_mark(si_no, marked)
                st.rerun()
            st.markdown("---")

        col1, col2 = st.columns(2)
        with col1:
            if st.button("➡️ Next Set"):
                st.session_state.bulk_index += q_count
                st.rerun()
        with col2:
            if st.button("✅ Complete"):
                st.session_state.show_summary = True
                st.rerun()

    # 2.4) Analytics
    elif test_practice_option == "Analytics":
        st.title("📈 Analytics")
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT practice_date, SUM(ancient_medieval_history + modern_history + geography + polity + economics + biology + physics + chemistry + environment + static_part + west_bengal)
                FROM practice_summary WHERE user_id = %s GROUP BY practice_date ORDER BY practice_date
            """, (st.session_state.user_id,))
            rows = cur.fetchall()
        if rows:
            dates = [r[0] for r in rows]
            counts = [r[1] for r in rows]
            formatted_dates = [d.strftime("%d %b") if hasattr(d, "strftime") else str(d) for d in dates]
            df = pd.DataFrame({"Questions Practiced": counts}, index=formatted_dates)
            st.line_chart(df)
        else:
            st.info("No data yet")

    # 2.5) Dashboard
    elif test_practice_option == "Dashboard":
        st.subheader("📊 User Dashboard")
        user_id = st.session_state.user_id
        role = st.session_state.role

        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM quiz")
            total_questions = cur.fetchone()[0] or 0
            cur.execute("""
                SELECT subject, COUNT(*) FROM quiz GROUP BY subject ORDER BY 
                CASE subject 
                    WHEN 'Ancient and Medieval History' THEN 1 WHEN 'Modern History' THEN 2 WHEN 'Geography' THEN 3 
                    WHEN 'Polity' THEN 4 WHEN 'Economics' THEN 5 WHEN 'Environment' THEN 6 WHEN 'Physics' THEN 7 
                    WHEN 'Chemistry' THEN 8 WHEN 'Biology' THEN 9 WHEN 'Static Part' THEN 10 WHEN 'West Bengal' THEN 11 ELSE 12 
                END
            """)
            subject_question_counts = cur.fetchall()

        st.markdown("## 📘 Question Bank Overview")
        st.metric("Total Questions", total_questions)
        for subject, count in subject_question_counts:
            st.write(f"{subject} : {count}")

    # 2.6) Update Question
    elif test_practice_option == "Update Question":
        st.subheader("✏ Update / Delete Question")
        qid = st.number_input("Enter Question ID",min_value=1,step=1)
        if st.button("Load Question"):
            with get_connection() as conn:
                cur = conn.cursor()
                cur.execute("SELECT subject,question,answer,difficulty FROM quiz WHERE si_no = %s",(qid,))
                row = cur.fetchone()
            if row:
                st.session_state.edit_data = {"id":qid, "subject":row[0], "question":row[1], "answer":row[2], "difficulty":row[3]}
            else:
                st.error("Question not found.")
        
        if "edit_data" in st.session_state:
            data = st.session_state.edit_data
            new_question = st.text_area("Question",value=data["question"])
            new_answer = st.text_area("Answer",value=data["answer"])
            new_subject = st.selectbox("Subject", SUBJECTS, index=SUBJECTS.index(data["subject"]))
            difficulty_map = {"Easy":1,"Moderate":2,"Difficult":3}
            reverse_map = {1:"Easy",2:"Moderate",3:"Difficult"}
            difficulty_label = st.selectbox("Difficulty", ["Easy","Moderate","Difficult"], index=["Easy","Moderate","Difficult"].index(reverse_map[data["difficulty"]]))
            
            col1,col2 = st.columns(2)
            with col1:
                if st.button("Save Changes"):
                    with get_connection() as conn:
                        cur = conn.cursor()
                        cur.execute("UPDATE quiz SET subject=%s, question=%s, answer=%s, difficulty=%s WHERE si_no=%s",(new_subject, new_question.strip(), new_answer.strip(), difficulty_map[difficulty_label], data["id"]))
                        conn.commit()
                    st.success("Question updated successfully.")
                    st.session_state.pop("edit_data",None)
                    st.rerun()

    # 2.7) Insert Question
    elif test_practice_option == "Insert Question":
        st.subheader("➕ Insert New Question")
        question = st.text_area("Enter Question", key="insert_question")
        answer = st.text_area("Enter Answer", key="insert_answer")
        subject = st.selectbox("Select Subject", SUBJECTS)
        difficulty_label = st.selectbox("Difficulty", ["Easy", "Moderate", "Difficult"])
        difficulty_map = {"Easy":1,"Moderate":2,"Difficult":3}
        
        if st.button("💾 Save Question"):
            if not question.strip() or not answer.strip():
                st.error("Question and Answer cannot be empty.")
            else:
                with get_connection() as conn:
                    cur = conn.cursor()
                    cur.execute("INSERT INTO quiz (subject,question,answer,difficulty) VALUES (%s,%s,%s,%s) RETURNING si_no",(subject, question.strip(), answer.strip(), difficulty_map[difficulty_label]))
                    inserted_id = cur.fetchone()[0]
                    conn.commit()
                st.success(f"Question added successfully! ID: {inserted_id}")
                st.rerun()

    # 2.8) Import Question from txt
    elif test_practice_option == "Import Question from txt":
        st.subheader("📂 Import Questions from TXT")
        uploaded_file = st.file_uploader("Upload TXT File",type=["txt"])
        difficulty_label = st.selectbox("Difficulty", ["Easy","Moderate","Difficult"])
        difficulty_map = {"Easy":1,"Moderate":2,"Difficult":3}
        
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
                            cur.execute("INSERT INTO quiz (subject,question,answer,difficulty) VALUES (%s,%s,%s,%s)",(current_subject, question.strip(), answer.strip(), difficulty_map[difficulty_label]))
                            inserted += 1
                    conn.commit()
                st.success(f"{inserted} questions imported successfully.")
                st.rerun()

    # 2.9) Marked Questions (Only delete configuration mode)
    elif test_practice_option == "Marked Questions":
        st.subheader("⭐ Marked Questions (Management)")
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT si_no, subject, question, answer, difficulty FROM quiz WHERE is_marked = 1")
            rows = cur.fetchall()

        if not rows:
            st.warning("No marked questions.")
            st.stop()

        if "marked_index" not in st.session_state:
            st.session_state.marked_index = 0

        if st.session_state.marked_index >= len(rows):
            st.session_state.marked_index = 0

        q = rows[st.session_state.marked_index]
        si_no, subject, question, answer, diff = q

        st.write(f"**Question ID:** {si_no}")
        st.write(f"**Subject:** {subject}")
        st.write(question)

        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("Show Answer"):
                st.success(answer)
        with col2:
            if st.button("🗑️ Delete Question"):
                delete_marked_question(si_no)
                st.success("Question permanently deleted from system!")
                st.rerun()
        with col3:
            if st.button("Next Marked"):
                st.session_state.marked_index += 1
                st.rerun()

# =====================================================
# 3) USER MANAGEMENT PARENT MODE
# =====================================================
elif parent_mode == "User Management":
    if st.session_state.role != "admin":
        st.error("Admin access required")
        st.stop()
    st.subheader("👥 User Management Panel")
    
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id, username, role, is_active, last_active FROM users ORDER BY username")
        users = cur.fetchall()

    st.markdown("### 📋 All Users")
    for user_id, username, role, is_active, last_active in users:
        col1, col2, col3 = st.columns([3,2,2])
        with col1: st.write(f"**{username}** ({role})")
        with col2: st.write(f"Active: {is_active}")
        with col3:
            if st.button("Delete User", key=f"del_{user_id}"):
                with get_connection() as conn:
                    cur = conn.cursor()
                    cur.execute("DELETE FROM users WHERE id = %s", (user_id,))
                    conn.commit()
                st.success("User deleted")
                st.rerun()
