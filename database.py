import sqlite3
import numpy as np
import io
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "attendance.db"

def normalize_teachers(teachers):
    if teachers is None:
        return []
    if isinstance(teachers, str):
        teachers = [teachers]

    cleaned = []
    seen = set()
    for teacher in teachers:
        name = str(teacher).strip()
        if not name:
            continue
        key = name.casefold()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(name)
    return cleaned

def get_connection():
    try:
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        conn.execute("PRAGMA foreign_keys = ON")
        return conn
    except sqlite3.Error as e:
        logger.error(f"Database connection error: {e}")
        return None

def init_db():
    conn = get_connection()
    if not conn: return
    try:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS students (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                year TEXT NOT NULL,
                encoding BLOB NOT NULL
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS subjects (
                name TEXT PRIMARY KEY,
                teacher_1 TEXT DEFAULT '',
                teacher_2 TEXT DEFAULT ''
            )
        ''')
        cursor.execute("PRAGMA table_info(subjects)")
        subject_cols = [col[1] for col in cursor.fetchall()]
        if 'teacher_1' not in subject_cols:
            cursor.execute("ALTER TABLE subjects ADD COLUMN teacher_1 TEXT DEFAULT ''")
        if 'teacher_2' not in subject_cols:
            cursor.execute("ALTER TABLE subjects ADD COLUMN teacher_2 TEXT DEFAULT ''")
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS subject_teachers (
                subject_name TEXT NOT NULL,
                teacher_name TEXT NOT NULL,
                FOREIGN KEY (subject_name) REFERENCES subjects (name) ON DELETE CASCADE,
                PRIMARY KEY (subject_name, teacher_name)
            )
        ''')
        cursor.execute("SELECT name, COALESCE(teacher_1, ''), COALESCE(teacher_2, '') FROM subjects")
        for subject_name, teacher_1, teacher_2 in cursor.fetchall():
            for teacher in normalize_teachers([teacher_1, teacher_2]):
                cursor.execute(
                    '''
                    INSERT OR IGNORE INTO subject_teachers (subject_name, teacher_name)
                    VALUES (?, ?)
                    ''',
                    (subject_name, teacher)
                )
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS attendance (
                student_id TEXT,
                date TEXT,
                time TEXT,
                subject TEXT,
                FOREIGN KEY (student_id) REFERENCES students (id),
                FOREIGN KEY (subject) REFERENCES subjects (name),
                PRIMARY KEY (student_id, date, subject)
            )
        ''')
        conn.commit()
    except sqlite3.Error as e:
        logger.error(f"Error initializing database: {e}")
    finally:
        conn.close()

def get_subjects():
    conn = get_connection()
    if not conn: return []
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM subjects ORDER BY name ASC")
        return [row[0] for row in cursor.fetchall()]
    except sqlite3.Error as e:
        logger.error(f"Error fetching subjects: {e}")
        return []
    finally:
        conn.close()

def get_subject_catalog():
    conn = get_connection()
    if not conn: return []
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM subjects ORDER BY name ASC")
        subjects = []
        for (name,) in cursor.fetchall():
            cursor.execute(
                '''
                SELECT teacher_name
                FROM subject_teachers
                WHERE subject_name = ?
                ORDER BY teacher_name COLLATE NOCASE ASC
                ''',
                (name,)
            )
            teachers = [row[0].strip() for row in cursor.fetchall() if row[0].strip()]
            subjects.append({"name": name, "teachers": teachers})
        return subjects
    except sqlite3.Error as e:
        logger.error(f"Error fetching subject catalog: {e}")
        return []
    finally:
        conn.close()

def add_subject(name, teachers=None):
    conn = get_connection()
    if not conn: return False
    try:
        cleaned_teachers = normalize_teachers(teachers)
        cursor = conn.cursor()
        subject_name = name.strip()
        cursor.execute(
            "INSERT INTO subjects (name) VALUES (?)",
            (subject_name,)
        )
        for teacher in cleaned_teachers:
            cursor.execute(
                '''
                INSERT INTO subject_teachers (subject_name, teacher_name)
                VALUES (?, ?)
                ''',
                (subject_name, teacher)
            )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    except sqlite3.Error as e:
        logger.error(f"Error adding subject: {e}")
        return False
    finally:
        conn.close()

def delete_subject(name):
    conn = get_connection()
    if not conn: return False
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM subjects WHERE name = ?", (name,))
        conn.commit()
        return True
    except sqlite3.Error as e:
        logger.error(f"Error deleting subject: {e}")
        return False
    finally:
        conn.close()

def update_subject_teachers(name, teachers=None):
    conn = get_connection()
    if not conn: return False
    try:
        cleaned_teachers = normalize_teachers(teachers)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM subject_teachers WHERE subject_name = ?", (name,))
        for teacher in cleaned_teachers:
            cursor.execute(
                '''
                INSERT INTO subject_teachers (subject_name, teacher_name)
                VALUES (?, ?)
                ''',
                (name, teacher)
            )
        cursor.execute(
            "UPDATE subjects SET teacher_1 = ?, teacher_2 = ? WHERE name = ?",
            (
                cleaned_teachers[0] if len(cleaned_teachers) > 0 else "",
                cleaned_teachers[1] if len(cleaned_teachers) > 1 else "",
                name
            )
        )
        conn.commit()
        return cursor.rowcount > 0
    except sqlite3.Error as e:
        logger.error(f"Error updating subject teachers: {e}")
        return False
    finally:
        conn.close()

def adapt_array(arr):
    out = io.BytesIO()
    np.save(out, arr)
    out.seek(0)
    return out.read()

def convert_array(blob):
    out = io.BytesIO(blob)
    out.seek(0)
    return np.load(out)

def add_student(student_id, name, year, encoding):
    conn = get_connection()
    if not conn: return False, "Database connection failed"
    try:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO students (id, name, year, encoding) VALUES (?, ?, ?, ?)",
            (student_id.strip(), name.strip(), year.strip(), adapt_array(encoding))
        )
        conn.commit()
        return True, "Success"
    except sqlite3.IntegrityError:
        return False, "Student ID already exists"
    except sqlite3.Error as e:
        logger.error(f"Error adding student: {e}")
        return False, str(e)
    finally:
        conn.close()

def get_all_students():
    conn = get_connection()
    if not conn: return []
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, year, encoding FROM students")
        rows = cursor.fetchall()
        students = []
        for row in rows:
            students.append({
                'id': row[0],
                'name': row[1],
                'year': row[2],
                'encoding': convert_array(row[3])
            })
        return students
    except sqlite3.Error as e:
        logger.error(f"Error fetching students: {e}")
        return []
    finally:
        conn.close()

def mark_attendance(student_id, date, time, subject):
    conn = get_connection()
    if not conn: return False
    try:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO attendance (student_id, date, time, subject) VALUES (?, ?, ?, ?)",
            (student_id, date, time, subject)
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    except sqlite3.Error as e:
        logger.error(f"Error marking attendance: {e}")
        return False
    finally:
        conn.close()

def delete_student(student_id):
    conn = get_connection()
    if not conn: return False
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM attendance WHERE student_id = ?", (student_id,))
        cursor.execute("DELETE FROM students WHERE id = ?", (student_id,))
        conn.commit()
        return True
    except sqlite3.Error as e:
        logger.error(f"Error deleting student: {e}")
        return False
    finally:
        conn.close()

def update_student_name(student_id, new_name):
    conn = get_connection()
    if not conn: return False
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE students SET name = ? WHERE id = ?", (new_name.strip(), student_id))
        conn.commit()
        return True
    except sqlite3.Error as e:
        logger.error(f"Error updating student: {e}")
        return False
    finally:
        conn.close()

def get_attendance_logs(subject=None):
    conn = get_connection()
    if not conn: return []
    try:
        cursor = conn.cursor()
        query = '''
            SELECT students.id, students.name, students.year, attendance.date, attendance.time, attendance.subject
            FROM attendance
            JOIN students ON attendance.student_id = students.id
        '''
        params = []
        if subject and subject != "All":
            query += " WHERE attendance.subject = ?"
            params.append(subject)
        query += " ORDER BY attendance.date DESC, attendance.time DESC"
        cursor.execute(query, params)
        return cursor.fetchall()
    except sqlite3.Error as e:
        logger.error(f"Error fetching logs: {e}")
        return []
    finally:
        conn.close()

def get_absentees(date, subject):
    conn = get_connection()
    if not conn: return []
    try:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, name, year FROM students 
            WHERE id NOT IN (SELECT student_id FROM attendance WHERE date = ? AND subject = ?)
        ''', (date, subject))
        return cursor.fetchall()
    except sqlite3.Error as e:
        logger.error(f"Error fetching absentees: {e}")
        return []
    finally:
        conn.close()
