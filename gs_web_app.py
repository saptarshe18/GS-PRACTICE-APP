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
    return psycopg2.connect(
        host=st.secrets["DB_HOST"],
        database=st.secrets["DB_NAME"],
        user=st.secrets["DB_USER"],
        password=st.secrets["DB_PASSWORD"],
        port=st.secrets["DB_PORT"],
        sslmode="require"
    )

# =====================================================
# SECURITY
# =====================================================

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# =====================================================
# LOGIN
# =====================================================

def login_user(username, password):

    with get_connection() as conn:
        cur = conn.cursor()

        cur.execute("""
        SELECT id,password_hash,role
        FROM users
        WHERE username=%s
        """,(username,))

        row = cur.fetchone()

        if row and row[1] == hash_password(password):

            cur.execute("""
            UPDATE users
            SET is_active=TRUE,
                last_active=%s
            WHERE id=%s
            """,(datetime.now(),row[0]))

            conn.commit()

            return row[0],row[2]

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

mode=st.sidebar.selectbox(
"Mode",
[
"Live Dashboard",
"Subject Practice",
"Mixed Practice",
"Insert Question",
"Update Question",
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

def update_read_count(si_no,subject):

    today=datetime.now().strftime("%Y-%m-%d")

    with get_connection() as conn:
        cur=conn.cursor()

        cur.execute(
        "UPDATE quiz SET reading_times=reading_times+1 WHERE si_no=%s",
        (si_no,)
        )

        cur.execute(
        "INSERT INTO practice_log(user_id,date,subject) VALUES(%s,%s,%s)",
        (st.session_state.user_id,today,subject)
        )

        conn.commit()

# =====================================================
# PRACTICE MODE
# =====================================================

if mode in ["Subject Practice","Mixed Practice"]:

    subject=None
    difficulty=None

    if mode=="Subject Practice":
        subject=st.selectbox("Subject",SUBJECTS)

    diff_label=st.selectbox("Difficulty",["All","Easy","Moderate","Difficult"])

    diff_map={"Easy":1,"Moderate":2,"Difficult":3}

    if diff_label!="All":
        difficulty=diff_map[diff_label]

    order=st.selectbox("Question Type",["Random","Most Read","Least Read"])

    order_map={
    "Random":"random",
    "Most Read":"most",
    "Least Read":"least"
    }

    if "practice_active" not in st.session_state:
        st.session_state.practice_active=False

    if not st.session_state.practice_active:

        if st.button("Start Practice"):

            st.session_state.questions=get_questions(
            subject,
            difficulty,
            order_map[order]
            )

            st.session_state.index=0
            st.session_state.reviewed=0
            st.session_state.practice_active=True
            st.rerun()

        st.stop()

    questions=st.session_state.questions

    if st.session_state.index>=len(questions):

        st.success("Session Complete")
        st.session_state.practice_active=False
        st.stop()

    q=questions[st.session_state.index]

    si_no,subject,question,answer,diff,reads,marked=q

    st.write(f"Question ID: {si_no}")
    st.write(question)

    if st.button("Show Answer"):

        st.success(answer)

        update_read_count(si_no,subject)

        st.session_state.reviewed+=1

    if st.button("Next"):

        st.session_state.index+=1
        st.rerun()

# =====================================================
# DASHBOARD
# =====================================================

elif mode=="Live Dashboard":

    st.header("User Dashboard")

    with get_connection() as conn:

        cur=conn.cursor()

        cur.execute("SELECT COUNT(*) FROM quiz")
        total_q=cur.fetchone()[0]

        cur.execute("""
        SELECT subject,COUNT(*)
        FROM quiz
        GROUP BY subject
        """)

        subject_counts=cur.fetchall()

    st.metric("Total Questions",total_q)

    for s,c in subject_counts:
        st.write(f"{s} : {c}")

    st.markdown("---")

    with get_connection() as conn:

        cur=conn.cursor()

        cur.execute("""
        SELECT COUNT(*)
        FROM practice_log
        WHERE user_id=%s
        """,(st.session_state.user_id,))

        total_reads=cur.fetchone()[0]

    st.metric("Total Questions Practiced",total_reads)

# =====================================================
# ANALYTICS
# =====================================================

elif mode=="Analytics":

    with get_connection() as conn:

        cur=conn.cursor()

        cur.execute("""
        SELECT date,COUNT(*)
        FROM practice_log
        WHERE user_id=%s
        GROUP BY date
        ORDER BY date
        """,(st.session_state.user_id,))

        rows=cur.fetchall()

    if rows:

        dates=[r[0] for r in rows]
        counts=[r[1] for r in rows]

        df=pd.DataFrame(
        {"Questions Practiced":counts},
        index=dates
        )

        st.bar_chart(df)

# =====================================================
# USER MANAGEMENT
# =====================================================

elif mode=="User Management":

    if st.session_state.role!="admin":

        st.error("Admin access required")
        st.stop()

    st.subheader("Users")

    with get_connection() as conn:

        cur=conn.cursor()

        cur.execute("""
        SELECT id,username,role,is_active,last_active
        FROM users
        ORDER BY username
        """)

        users=cur.fetchall()

    for uid,uname,role,active,last in users:

        st.write(f"{uname} | {role} | Active:{active} | Last:{last}")
