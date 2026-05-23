import streamlit as st
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import database
import time
import os
import logging
import sys

RUNTIME_ISSUES = []

if sys.version_info >= (3, 11):
    RUNTIME_ISSUES.append(
        "Python 3.13+ is not recommended for this app on Windows because "
        "`dlib` and `face_recognition` often fail to install there. Use Python 3.11."
    )

try:
    import face_recognition
except Exception as exc:
    face_recognition = None
    RUNTIME_ISSUES.append(f"`face_recognition` could not be imported: {exc}")

try:
    import cv2
except Exception as exc:
    cv2 = None
    RUNTIME_ISSUES.append(f"`opencv-python` could not be imported: {exc}")

try:
    import av
except Exception as exc:
    av = None
    RUNTIME_ISSUES.append(f"`av` could not be imported: {exc}")

try:
    from streamlit_webrtc import webrtc_streamer, RTCConfiguration, WebRtcMode
except Exception as exc:
    webrtc_streamer = None
    RTCConfiguration = None
    WebRtcMode = None
    RUNTIME_ISSUES.append(f"`streamlit-webrtc` could not be imported: {exc}")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

ADMIN_PASS = os.getenv("ADMIN_PASSWORD", "admin123")

st.set_page_config(
    page_title="Attendance Dashboard", 
    layout="wide", 
    page_icon="Attendance",
    initial_sidebar_state="expanded"
)

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Roboto:wght@300;400;500;700&display=swap');
    @import url('https://fonts.googleapis.com/css2?family=Google+Sans:wght@400;500;700&display=swap');
    
    html, body, [class*="css"] { 
        font-family: 'Google Sans', 'Roboto', sans-serif; 
    }
    
    /* MD3 Dark Background */
    .stApp {
        background-color: #0f1115;
    }

    /* Universal Text Color Fix */
    .stMarkdown, p, span, label, div, h1, h2, h3, h4, h5, h6 {
        color: #e3e2e6 !important;
    }

    /* MD3 Dark Surface - Card Style */
    [data-testid="stVerticalBlockBorderWrapper"] {
        background: #1b1d22 !important;
        padding: 2.5rem;
        border-radius: 28px !important;
        box-shadow: 0 4px 24px rgba(0,0,0,0.4);
        border: 1px solid #2d3038 !important;
        margin-bottom: 2rem;
    }

    /* Metrics Readability */
    [data-testid="stMetricValue"] {
        color: #a8c7fa !important;
        font-weight: 700 !important;
    }
    [data-testid="stMetricLabel"] p {
        color: #c4c6cf !important;
        font-size: 1rem !important;
    }

    /* Tabs Readability - Increased Contrast */
    .stTabs [data-baseweb="tab-list"] {
        gap: 1rem;
        padding: 0.5rem;
        background: transparent;
    }
    .stTabs [data-baseweb="tab"] {
        height: 48px;
        border-radius: 24px;
        padding: 0 2rem;
        font-weight: 500;
        color: #c4c6cf !important; /* Lighter grey for inactive tabs */
        border: none;
        background-color: transparent;
    }
    .stTabs [aria-selected="true"] {
        background-color: #d3e3fd !important;
        color: #041e49 !important; /* Dark text on light background */
    }
    .stTabs [aria-selected="true"] p {
        color: #041e49 !important;
    }

    /* Dataframe & Table Readability */
    [data-testid="stTable"] td, [data-testid="stTable"] th {
        color: #e3e2e6 !important;
        background-color: #1b1d22 !important;
        border-bottom: 1px solid #2d3038 !important;
    }
    .stDataFrame [data-testid="stTable"] {
        border: 1px solid #2d3038 !important;
    }

    /* Input & Selectbox Overrides */
    .stSelectbox div[data-baseweb="select"] > div {
        background-color: #24262d !important;
        border: 1px solid #44474e !important;
        border-radius: 12px !important;
    }
    .stSelectbox span, .stTextInput input {
        color: #e3e2e6 !important;
    }
    .stTextInput input {
        background-color: #24262d !important;
        border: 1px solid #44474e !important;
        border-radius: 12px !important;
    }

    /* Sidebar Readability */
    section[data-testid="stSidebar"] {
        background-color: #13151a !important;
        border-right: 1px solid #2d3038;
    }
    section[data-testid="stSidebar"] .stMarkdown p, section[data-testid="stSidebar"] strong {
        color: #e3e2e6 !important;
    }

    /* Success/Info/Warning/Error Block Text */
    .stAlert p {
        color: inherit !important;
    }

    /* Material Tonal Buttons - More subtle and integrated */
    .stButton > button {
        border-radius: 20px;
        background-color: #2d3038 !important; /* Tonal Surface */
        color: #a8c7fa !important; /* Primary Text */
        border: 1px solid #44474e !important;
        font-family: 'Google Sans', sans-serif;
        font-weight: 500;
        letter-spacing: 0.2px;
        padding: 0.5rem 1.5rem;
        height: 48px;
        transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
    }

    .stButton > button:hover {
        background-color: #3b4859 !important;
        border-color: #a8c7fa !important;
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
    }

    .stButton > button:active {
        transform: translateY(0px);
        background-color: #24262d !important;
    }
    </style>
""", unsafe_allow_html=True)

if RUNTIME_ISSUES:
    st.error("Windows setup is incomplete for this project.")
    st.markdown(
        """
        Complete the Windows setup first:

        1. Install Python 3.11 (64-bit).
        2. Run `powershell -ExecutionPolicy Bypass -File .\\setup_windows.ps1`
        3. Start the app with `run_windows.bat`
        """
    )
    for issue in RUNTIME_ISSUES:
        st.code(issue)
    st.stop()

@st.cache_resource
def startup_db():
    database.init_db()
    conn = database.get_connection()
    if conn:
        cursor = conn.cursor()
        
        # Check students table
        cursor.execute("PRAGMA table_info(students)")
        student_cols = [col[1] for col in cursor.fetchall()]
        if 'year' not in student_cols:
            cursor.execute("DROP TABLE IF EXISTS attendance") # Attendance depends on students
            cursor.execute("DROP TABLE IF EXISTS students")
            conn.commit()
            database.init_db()
            
        # Check attendance table (existing check)
        cursor.execute("PRAGMA table_info(attendance)")
        if 'subject' not in [col[1] for col in cursor.fetchall()]:
            cursor.execute("DROP TABLE IF EXISTS attendance")
            database.init_db()
        conn.close()
    return True

startup_db()

if not database.get_subjects():
    for sub in ["Mathematics", "Physics", "Chemistry", "Computer Science"]:
        database.add_subject(sub)

def format_teacher_text(subject_info):
    teachers = [teacher.strip() for teacher in subject_info.get("teachers", []) if str(teacher).strip()]
    teachers = [teacher for teacher in teachers if teacher]
    return " / ".join(teachers) if teachers else "Not assigned"

def ensure_teacher_inputs(prefix, teachers=None):
    teachers = teachers or [""]
    count_key = f"{prefix}_teacher_count"
    desired_count = max(len(teachers), 1)

    if count_key not in st.session_state:
        st.session_state[count_key] = desired_count
    elif st.session_state[count_key] < desired_count:
        st.session_state[count_key] = desired_count

    for idx in range(st.session_state[count_key]):
        input_key = f"{prefix}_teacher_{idx}"
        if input_key not in st.session_state:
            st.session_state[input_key] = teachers[idx] if idx < len(teachers) else ""

def collect_teacher_inputs(prefix):
    count = st.session_state.get(f"{prefix}_teacher_count", 1)
    teachers = []
    for idx in range(count):
        value = st.session_state.get(f"{prefix}_teacher_{idx}", "").strip()
        if value:
            teachers.append(value)
    return teachers

def reset_teacher_inputs(prefix):
    count = st.session_state.get(f"{prefix}_teacher_count", 1)
    for idx in range(count):
        st.session_state.pop(f"{prefix}_teacher_{idx}", None)
    st.session_state[f"{prefix}_teacher_count"] = 1
    st.session_state.pop(f"{prefix}_name", None)

SUBJECTS = database.get_subjects()
SUBJECT_CATALOG = database.get_subject_catalog()
SUBJECT_LOOKUP = {subject["name"]: subject for subject in SUBJECT_CATALOG}
RTC_CONFIG = RTCConfiguration({"iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]})

@st.cache_data
def load_student_data(): return database.get_all_students()

def load_attendance_logs():
    return database.get_attendance_logs()

def build_student_dataframe(students):
    if not students:
        return pd.DataFrame(columns=["ID", "Name", "Year"])
    return pd.DataFrame(
        [{"ID": s["id"], "Name": s["name"], "Year": s["year"]} for s in students]
    )

def build_attendance_dataframe(logs):
    if not logs:
        return pd.DataFrame(columns=["ID", "Name", "Year", "Date", "Time", "Subject", "Date_obj"])

    df = pd.DataFrame(logs, columns=["ID", "Name", "Year", "Date", "Time", "Subject"])
    df["Date_obj"] = pd.to_datetime(df["Date"], errors="coerce").dt.date
    df = df.dropna(subset=["Date_obj"]).copy()
    return df

def filter_students_df(students_df, year_filter):
    if students_df.empty:
        return students_df
    if year_filter != "All":
        return students_df[students_df["Year"] == year_filter].copy()
    return students_df.copy()

def filter_attendance_df(attendance_df, start_date, end_date, subject_filter, year_filter):
    if attendance_df.empty:
        return attendance_df

    filtered_df = attendance_df[
        (attendance_df["Date_obj"] >= start_date) & (attendance_df["Date_obj"] <= end_date)
    ].copy()

    if subject_filter != "All":
        filtered_df = filtered_df[filtered_df["Subject"] == subject_filter]
    if year_filter != "All":
        filtered_df = filtered_df[filtered_df["Year"] == year_filter]
    return filtered_df

def build_student_session_summary(eligible_students_df, filtered_df, session_keys):
    student_summary = eligible_students_df.copy()
    total_sessions = filtered_df[session_keys].drop_duplicates().shape[0] if not filtered_df.empty else 0

    if "Sessions Attended" not in student_summary.columns:
        student_summary["Sessions Attended"] = 0

    if total_sessions > 0:
        attendance_counts = (
            filtered_df.groupby(["ID", "Name", "Year"])[session_keys]
            .apply(lambda group: group.drop_duplicates().shape[0])
            .reset_index(name="Sessions Attended")
        )
        student_summary = student_summary.merge(
            attendance_counts,
            on=["ID", "Name", "Year"],
            how="left",
            suffixes=("", "_count")
        )
        if "Sessions Attended_count" in student_summary.columns:
            student_summary["Sessions Attended"] = student_summary["Sessions Attended_count"]
            student_summary = student_summary.drop(columns=["Sessions Attended_count"])

    student_summary["Sessions Attended"] = student_summary["Sessions Attended"].fillna(0).astype(int)
    student_summary["Attendance %"] = (
        (student_summary["Sessions Attended"] / total_sessions * 100).round(1)
        if total_sessions > 0 else 0.0
    )

    if filtered_df.empty:
        student_summary["Last Present"] = "Never"
    else:
        last_present = (
            filtered_df.groupby("ID")["Date_obj"]
            .max()
            .reset_index(name="Last Present")
        )
        last_present["Last Present"] = last_present["Last Present"].astype(str)
        student_summary = student_summary.merge(last_present, on="ID", how="left")
        student_summary["Last Present"] = student_summary["Last Present"].fillna("Never")

    return student_summary, total_sessions

class VideoProcessor:
    def __init__(self, enrolled_students, subject):
        self.enrolled_students = enrolled_students
        self.subject = subject
        self.known_encodings = [s['encoding'] for s in enrolled_students]
        self.known_names = [s['name'] for s in enrolled_students]
        self.known_ids = [s['id'] for s in enrolled_students]
        self.last_mark = {}
        self.msg_text = ""
        self.msg_expiry = 0
        self.msg_color = (208, 87, 11)
        self.marked_successfully = False
        self.marked_name = ""

    def recv(self, frame):
        img = frame.to_ndarray(format="bgr24")
        img = cv2.flip(img, 1)
        
        small_frame = cv2.resize(img, (0, 0), fx=0.25, fy=0.25)
        rgb_small = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)
        
        face_locs = face_recognition.face_locations(rgb_small)
        face_encs = face_recognition.face_encodings(rgb_small, face_locs)
        
        for (top, right, bottom, left), enc in zip(face_locs, face_encs):
            top *= 4; right *= 4; bottom *= 4; left *= 4
            matches = face_recognition.compare_faces(self.known_encodings, enc, 0.6)
            name, sid, color = "Unknown", "", (0, 0, 255)
            
            if True in matches:
                idx = np.argmin(face_recognition.face_distance(self.known_encodings, enc))
                name, sid, color = self.known_names[idx], self.known_ids[idx], (208, 87, 11)
                
                now = datetime.now()
                if (sid, self.subject, now.date()) not in self.last_mark:
                    if database.mark_attendance(sid, now.strftime("%Y-%m-%d"), now.strftime("%H:%M:%S"), self.subject):
                        self.last_mark[(sid, self.subject, now.date())] = True
                        self.msg_text = f"Marked: {name}"
                        self.msg_expiry = time.time() + 2
                        self.msg_color = (208, 87, 11)
                        self.marked_successfully = True
                        self.marked_name = name
                    else:
                        self.msg_text = f"Already Marked: {name}"
                        self.msg_expiry = time.time() + 2
                        self.msg_color = (0, 165, 255)
                        self.last_mark[(sid, self.subject, now.date())] = True
            
            cv2.rectangle(img, (left, top), (right, bottom), color, 3)
            cv2.rectangle(img, (left, top - 40), (right, top), color, cv2.FILLED)
            cv2.putText(img, name, (left + 10, top - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
        
        if self.msg_text and time.time() < self.msg_expiry:
            overlay = img.copy()
            cv2.rectangle(overlay, (0, 0), (img.shape[1], 70), self.msg_color, cv2.FILLED)
            cv2.addWeighted(overlay, 0.8, img, 0.2, 0, img)
            cv2.putText(img, self.msg_text, (30, 45), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (255, 255, 255), 3)
        
        return av.VideoFrame.from_ndarray(img, format="bgr24")

with st.sidebar:
    st.markdown("<h2 style='color: #0b57d0; font-family: Google Sans; margin-top: 1rem;'>Smart Attendance</h2>", unsafe_allow_html=True)
    st.markdown("<p style='color: #444746; font-size: 0.9rem;'>Google Cloud Identity Service</p>", unsafe_allow_html=True)
    st.divider()
    st.markdown("**Admin Access**")
    admin_pass = st.text_input("Enter credentials", type="password", placeholder="Password", label_visibility="collapsed")
    is_admin = (admin_pass == ADMIN_PASS)
    
    if is_admin:
        st.success("Authorized")
        st.divider()
        st.markdown("**Manage Subjects**")
        ensure_teacher_inputs("new_subject", [""])
        new_sub = st.text_input("New Subject", placeholder="e.g. Biology", key="new_subject_name")
        st.caption("Assigned Teachers")
        for idx in range(st.session_state["new_subject_teacher_count"]):
            st.text_input(
                f"Teacher {idx + 1}",
                placeholder="Teacher name",
                key=f"new_subject_teacher_{idx}"
            )
        add_teacher_col, add_subject_col = st.columns([1, 1.2])
        if add_teacher_col.button("+ Add Teacher", key="add_new_subject_teacher", use_container_width=True):
            st.session_state["new_subject_teacher_count"] += 1
            st.rerun()
        if add_subject_col.button("Add Subject", use_container_width=True):
            if new_sub:
                if database.add_subject(new_sub, collect_teacher_inputs("new_subject")):
                    reset_teacher_inputs("new_subject")
                    st.cache_data.clear(); st.rerun()
        
        with st.expander("Existing Subjects"):
            for subject in SUBJECT_CATALOG:
                subject_name = subject["name"]
                subject_prefix = f"subject_{subject_name}"
                ensure_teacher_inputs(subject_prefix, subject.get("teachers", []))
                st.markdown(f"**{subject_name}**")
                st.caption(f"Teachers: {format_teacher_text(subject)}")
                for idx in range(st.session_state[f"{subject_prefix}_teacher_count"]):
                    st.text_input(
                        f"{subject_name} Teacher {idx + 1}",
                        key=f"{subject_prefix}_teacher_{idx}",
                        label_visibility="collapsed"
                    )
                if st.button("+ Add Teacher", key=f"add_teacher_{subject_name}", use_container_width=True):
                    st.session_state[f"{subject_prefix}_teacher_count"] += 1
                    st.rerun()
                if st.button("Save Teachers", key=f"save_teachers_{subject_name}", use_container_width=True):
                    if database.update_subject_teachers(subject_name, collect_teacher_inputs(subject_prefix)):
                        reset_teacher_inputs(subject_prefix)
                        st.cache_data.clear(); st.rerun()
                if st.button("Delete Subject", key=f"del_{subject_name}", use_container_width=True):
                    reset_teacher_inputs(subject_prefix)
                    database.delete_subject(subject_name); st.cache_data.clear(); st.rerun()
                st.divider()
    else:
        st.info("Log in to manage database")

st.markdown("<h1 style='color: #1f1f1f; font-family: Google Sans; font-size: 2.5rem; margin-bottom: 2rem;'>Identity Dashboard</h1>", unsafe_allow_html=True)

tabs = st.tabs(["📸 Live View", "👥 Student Registry", "📊 Reports & Analytics"])

with tabs[0]:
    if 'current_scan' not in st.session_state: st.session_state.current_scan = None
    
    col_log, col_main = st.columns([1, 2.8])
    
    with col_log:
        with st.container(border=True):
            st.markdown('<p class="m3-header">Current Session</p>', unsafe_allow_html=True)
            selected_subject = st.selectbox("Select Subject", SUBJECTS, label_visibility="collapsed")
            selected_subject_info = SUBJECT_LOOKUP.get(selected_subject, {"name": selected_subject, "teachers": []})
            st.caption(f"Teachers: {format_teacher_text(selected_subject_info)}")
            st.write("")
            
            logs = database.get_attendance_logs(selected_subject)
            if logs:
                for log in logs[:6]:
                    st.markdown(f"""
                    <div class="m3-log">
                        <strong style="color: #e3e2e6; font-size: 1.1rem;">{log[1]}</strong><br>
                        <span style='font-size: 0.9rem; color: #c4c6cf;'>{log[4]} • {log[5]}</span>
                    </div>
                    """, unsafe_allow_html=True)
                st.markdown("<div style='margin-top: 1.5rem;'></div>", unsafe_allow_html=True)
                if st.button("Refresh Feed", use_container_width=True): st.rerun()
            else:
                st.info("System idle: No detections")

    with col_main:
        with st.container(border=True):
            st.markdown('<p class="m3-header">Biometric Identity Scanner</p>', unsafe_allow_html=True)
            
            enrolled = load_student_data()
            if enrolled:
                if st.session_state.current_scan:
                    st.success(f"Identity Verified: **{st.session_state.current_scan}**")
                    st.info("Attendance logged successfully. System ready for next student.")
                    if st.button("Next Student (Open Camera)", use_container_width=True):
                        st.session_state.current_scan = None; st.rerun()
                else:
                    ctx = webrtc_streamer(
                        key="m3-live", 
                        mode=WebRtcMode.SENDRECV, 
                        rtc_configuration=RTC_CONFIG,
                        video_processor_factory=lambda: VideoProcessor(enrolled, selected_subject),
                        async_processing=True
                    )
                    
                    if ctx.video_processor:
                        if ctx.video_processor.marked_successfully:
                            time.sleep(1.5)
                            st.session_state.current_scan = ctx.video_processor.marked_name
                            st.rerun()

                    st.markdown("<p style='text-align: center; color: #444746; margin-top: 1.5rem; font-size: 1rem;'>Detection active. Recognition will trigger auto-marking.</p>", unsafe_allow_html=True)
            else:
                st.warning("Enrollment Database Empty")

with tabs[1]:
    if is_admin:
        c_reg, c_list = st.columns([1, 2])
        
        with c_reg:
            with st.container(border=True):
                st.markdown('<p class="m3-header">New Registration</p>', unsafe_allow_html=True)
                with st.form("m3_enroll", clear_on_submit=True):
                    s_id = st.text_input("Student ID", placeholder="ID-12345")
                    s_name = st.text_input("Name", placeholder="Full Name")
                    s_year = st.selectbox("Current Year", ["1st Year", "2nd Year", "3rd Year", "4th Year"])
                    st.write("")
                    s_photo = st.camera_input("Capture Profile", label_visibility="collapsed")
                    st.write("")
                    if st.form_submit_button("Create Identity Profile", use_container_width=True):
                        if s_id and s_name and s_photo:
                            enc = face_recognition.face_encodings(face_recognition.load_image_file(s_photo))
                            if enc:
                                success, msg = database.add_student(s_id, s_name, s_year, enc[0])
                                if success:
                                    st.success("Profile Created")
                                    st.cache_data.clear(); time.sleep(1); st.rerun()
                                else: st.error(msg)
                            else: st.error("No biometrics detected")
            
        with c_list:
            with st.container(border=True):
                st.markdown('<p class="m3-header">Active Records</p>', unsafe_allow_html=True)
                students = database.get_all_students()
                if students:
                    for s in students:
                        edit_key = f"edit_{s['id']}"
                        if edit_key not in st.session_state: st.session_state[edit_key] = False
                        
                        r1, r2, r3 = st.columns([1, 2, 1.5])
                        r1.code(f"{s['id']}\n({s['year']})")
                        
                        if st.session_state[edit_key]:
                            new_n = r2.text_input("Name", s['name'], key=f"n_{s['id']}", label_visibility="collapsed")
                            if r3.button("Save", key=f"s_{s['id']}"):
                                if database.update_student_name(s['id'], new_n):
                                    st.session_state[edit_key] = False; st.cache_data.clear(); st.rerun()
                            if r3.button("Cancel", key=f"c_{s['id']}"):
                                st.session_state[edit_key] = False; st.rerun()
                        else:
                            r2.write(f"**{s['name']}**")
                            e_col, d_col = r3.columns(2)
                            if e_col.button("Edit", key=f"e_{s['id']}"):
                                st.session_state[edit_key] = True; st.rerun()
                            if d_col.button("Delete", key=f"d_{s['id']}"):
                                if database.delete_student(s['id']):
                                    st.cache_data.clear(); st.rerun()
                        st.divider()
    else:
        st.info("Admin authentication required for directory access")

with tabs[2]:
    if is_admin:
        all_s = database.get_all_students()
        all_l = load_attendance_logs()
        students_df = build_student_dataframe(all_s)
        attendance_df = build_attendance_dataframe(all_l)
        
        st.markdown('<p class="m3-header">Analytics Controls</p>', unsafe_allow_html=True)
        today = datetime.now().date()
        preset_options = {
            "This Month": (today.replace(day=1), today),
            "Today": (today, today),
            "Last 7 Days": (today - timedelta(days=6), today),
            "Last 30 Days": (today - timedelta(days=29), today),
            "This Year": (today.replace(month=1, day=1), today),
            "Custom": None,
        }
        default_preset = "This Month"
        date_preset = st.radio(
            "Quick Range",
            list(preset_options.keys()),
            horizontal=True,
            index=list(preset_options.keys()).index(default_preset)
        )
        default_range = preset_options[date_preset] or preset_options[default_preset]

        fc1, fc2, fc3, fc4, fc5 = st.columns(5)
        start_date = fc1.date_input("Start Date", default_range[0])
        end_date = fc2.date_input("End Date", default_range[1])
        subject_filter = fc3.selectbox("Filter Subject", ["All"] + SUBJECTS)
        year_filter = fc4.selectbox("Filter Year", ["All", "1st Year", "2nd Year", "3rd Year", "4th Year"])
        threshold_filter = fc5.slider("Risk Threshold %", 40, 95, 75, 5)
        if subject_filter != "All":
            st.caption(f"Teachers: {format_teacher_text(SUBJECT_LOOKUP.get(subject_filter, {'teachers': []}))}")

        if start_date > end_date:
            st.error("Start Date cannot be after End Date.")
        else:
            eligible_students_df = filter_students_df(students_df, year_filter)
            filtered_df = filter_attendance_df(attendance_df, start_date, end_date, subject_filter, year_filter)
            session_keys = ["Date", "Subject"]
            student_summary, total_sessions = build_student_session_summary(
                eligible_students_df, filtered_df, session_keys
            )

            m_col1, m_col2, m_col3, m_col4 = st.columns(4)
            m_col1.metric("Eligible Students", len(eligible_students_df))
            m_col2.metric("Attendance Records", len(filtered_df))

            unique_present = filtered_df["ID"].nunique() if not filtered_df.empty else 0
            m_col3.metric("Unique Presentees", unique_present)
            m_col4.metric("Sessions Covered", total_sessions)

            if not filtered_df.empty and not eligible_students_df.empty:
                session_sizes = filtered_df.groupby(session_keys)["ID"].nunique()
                average_session_attendance = (session_sizes / len(eligible_students_df) * 100).mean()
                overall_coverage = (unique_present / len(eligible_students_df)) * 100
            else:
                average_session_attendance = 0.0
                overall_coverage = 0.0

            sm_col1, sm_col2, sm_col3 = st.columns(3)
            sm_col1.metric("Avg Session Attendance", f"{average_session_attendance:.1f}%")
            sm_col2.metric("Student Coverage", f"{overall_coverage:.1f}%")
            sm_col3.metric(
                "Date Range",
                f"{(end_date - start_date).days + 1} day(s)"
            )

            if not filtered_df.empty:
                student_summary = student_summary.sort_values(
                    by=["Attendance %", "Sessions Attended", "Name"],
                    ascending=[False, False, True]
                )
                watchlist_df = student_summary.copy()
                watchlist_df["Status"] = np.select(
                    [
                        watchlist_df["Attendance %"] < 50,
                        watchlist_df["Attendance %"] < threshold_filter,
                    ],
                    ["Critical", "Warning"],
                    default="Safe"
                )
                watchlist_df = watchlist_df[watchlist_df["Attendance %"] < threshold_filter]
                watchlist_df = watchlist_df.sort_values(
                    by=["Attendance %", "Sessions Attended", "Name"],
                    ascending=[True, True, True]
                )

                available_sessions = (
                    filtered_df[session_keys]
                    .drop_duplicates()
                    .sort_values(by=["Date", "Subject"], ascending=[False, True])
                )
                session_labels = [
                    f"{row['Date']} | {row['Subject']}" for _, row in available_sessions.iterrows()
                ]
                selected_register_label = st.selectbox(
                    "Focus Session",
                    session_labels,
                    key="daily_register_session"
                )
                selected_register = available_sessions.iloc[
                    session_labels.index(selected_register_label)
                ]
                register_subject_info = SUBJECT_LOOKUP.get(
                    selected_register["Subject"],
                    {"name": selected_register["Subject"], "teachers": []}
                )
                session_present_df = filtered_df[
                    (filtered_df["Date"] == selected_register["Date"]) &
                    (filtered_df["Subject"] == selected_register["Subject"])
                ][["ID", "Name", "Year", "Time"]].drop_duplicates(subset=["ID"]).sort_values("Name")
                register_absentees = database.get_absentees(
                    selected_register["Date"], selected_register["Subject"]
                )
                register_absent_df = pd.DataFrame(register_absentees, columns=["ID", "Name", "Year"])
                if year_filter != "All" and not register_absent_df.empty:
                    register_absent_df = register_absent_df[
                        register_absent_df["Year"] == year_filter
                    ].reset_index(drop=True)

                report_tabs = st.tabs(["Overview", "Session Register", "Student Insights", "Ledger"])

                with report_tabs[0]:
                    top_col1, top_col2 = st.columns([1.2, 1])
                    with top_col1:
                        with st.container(border=True):
                            st.markdown('<p class="m3-header">Attendance Trend</p>', unsafe_allow_html=True)
                            daily_counts = filtered_df.groupby("Date_obj")["ID"].count()
                            st.line_chart(daily_counts)
                    with top_col2:
                        with st.container(border=True):
                            st.markdown('<p class="m3-header">Watchlist</p>', unsafe_allow_html=True)
                            if watchlist_df.empty:
                                st.success(f"No students are below {threshold_filter}% in the current context.")
                            else:
                                st.error(f"{len(watchlist_df)} student(s) need attention.")
                                st.dataframe(
                                    watchlist_df[["Name", "Year", "Attendance %", "Status", "Last Present"]],
                                    use_container_width=True,
                                    hide_index=True
                                )

                    with st.container(border=True):
                        st.markdown('<p class="m3-header">Student Performance</p>', unsafe_allow_html=True)
                        st.dataframe(
                            student_summary[["ID", "Name", "Year", "Sessions Attended", "Attendance %", "Last Present"]],
                            use_container_width=True,
                            hide_index=True
                        )

                with report_tabs[1]:
                    with st.container(border=True):
                        st.markdown('<p class="m3-header">Daily Class Register</p>', unsafe_allow_html=True)
                        reg_m1, reg_m2, reg_m3 = st.columns(3)
                        reg_m1.metric("Class Strength", len(eligible_students_df))
                        reg_m2.metric("Present", len(session_present_df))
                        reg_m3.metric("Absent", len(register_absent_df))
                        st.write(
                            f"Session: **{selected_register['Subject']}** on **{selected_register['Date']}**"
                        )
                        st.caption(f"Teachers: {format_teacher_text(register_subject_info)}")
                        register_col1, register_col2 = st.columns(2)
                        with register_col1:
                            st.markdown("**Present Students**")
                            st.dataframe(session_present_df, use_container_width=True, hide_index=True)
                        with register_col2:
                            st.markdown("**Absent Students**")
                            if register_absent_df.empty:
                                st.success("No absentees for this session.")
                            else:
                                st.dataframe(register_absent_df, use_container_width=True, hide_index=True)

                with report_tabs[2]:
                    with st.container(border=True):
                        st.markdown('<p class="m3-header">Student Drill-Down</p>', unsafe_allow_html=True)
                        student_options = student_summary.sort_values("Name")["Name"].tolist()
                        selected_student_name = st.selectbox("Select Student", student_options, key="student_drilldown")
                        selected_student = student_summary[student_summary["Name"] == selected_student_name].iloc[0]
                        student_records = filtered_df[filtered_df["ID"] == selected_student["ID"]].copy()

                        drill_m1, drill_m2, drill_m3, drill_m4 = st.columns(4)
                        drill_m1.metric("Attendance %", f"{selected_student['Attendance %']:.1f}%")
                        drill_m2.metric("Sessions Attended", int(selected_student["Sessions Attended"]))
                        drill_m3.metric("Last Present", str(selected_student["Last Present"]))
                        absent_sessions = max(total_sessions - int(selected_student["Sessions Attended"]), 0)
                        drill_m4.metric("Sessions Missed", absent_sessions)

                        drill_col1, drill_col2 = st.columns(2)
                        with drill_col1:
                            subject_breakdown = (
                                student_records.groupby("Subject")[session_keys]
                                .apply(lambda group: group.drop_duplicates().shape[0])
                                .reset_index(name="Sessions Attended")
                                .sort_values(by="Sessions Attended", ascending=False)
                            ) if not student_records.empty else pd.DataFrame(columns=["Subject", "Sessions Attended"])

                            if not subject_breakdown.empty:
                                subject_totals = (
                                    filtered_df.groupby("Subject")[session_keys]
                                    .apply(lambda group: group.drop_duplicates().shape[0])
                                    .reset_index(name="Total Sessions")
                                )
                                subject_breakdown = subject_breakdown.merge(
                                    subject_totals,
                                    on="Subject",
                                    how="left"
                                )
                                subject_breakdown["Attendance %"] = (
                                    subject_breakdown["Sessions Attended"] / subject_breakdown["Total Sessions"] * 100
                                ).fillna(0).round(1)
                            st.markdown("**Subject Breakdown**")
                            st.dataframe(subject_breakdown, use_container_width=True, hide_index=True)

                        with drill_col2:
                            recent_history = (
                                student_records.drop(columns=["Date_obj"])
                                .sort_values(by=["Date", "Time"], ascending=[False, False])
                            ) if not student_records.empty else pd.DataFrame(
                                columns=["ID", "Name", "Year", "Date", "Time", "Subject"]
                            )
                            st.markdown("**Recent Attendance History**")
                            st.dataframe(recent_history.head(10), use_container_width=True, hide_index=True)

                with report_tabs[3]:
                    with st.container(border=True):
                        st.markdown('<p class="m3-header">Activity Ledger</p>', unsafe_allow_html=True)
                        ledger_df = filtered_df.drop(columns=["Date_obj"]).copy()
                        st.dataframe(ledger_df, use_container_width=True, hide_index=True)
                        st.download_button(
                            "Export Dataset (CSV)",
                            ledger_df.to_csv(index=False),
                            "attendance_ledger.csv",
                            use_container_width=True
                        )
            else:
                if attendance_df.empty:
                    st.info("Ledger currently empty. Enroll students and start a session to see analytics.")
                else:
                    st.info("No attendance records match the selected filters.")
    else:
        st.info("Analytics restricted")
