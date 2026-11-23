import os
import sqlite3
import json
from werkzeug.security import generate_password_hash, check_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_NAME = os.path.join(BASE_DIR, "enertrack.db")


def get_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            profile_name TEXT NOT NULL,
            utility_code TEXT NOT NULL,
            appliances_json TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        )
    """)

    # Auto-migrate legacy profiles table if user_id is missing
    cursor.execute("PRAGMA table_info(profiles)")
    columns = [col["name"] for col in cursor.fetchall()]
    if "user_id" not in columns:
        cursor.execute("DROP TABLE profiles")
        cursor.execute("""
            CREATE TABLE profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                profile_name TEXT NOT NULL,
                utility_code TEXT NOT NULL,
                appliances_json TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            )
        """)

    conn.commit()
    conn.close()


def create_user(full_name, email, password):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO users (full_name, email, password_hash) VALUES (?, ?, ?)",
            (full_name.strip(), email.lower().strip(), generate_password_hash(password))
        )
        conn.commit()
        return cursor.lastrowid
    except sqlite3.IntegrityError:
        return None
    finally:
        conn.close()


def authenticate_user(email, password):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE email = ?", (email.lower().strip(),))
    user = cursor.fetchone()
    conn.close()

    if user and check_password_hash(user["password_hash"], password):
        return {"id": user["id"], "full_name": user["full_name"], "email": user["email"]}
    return None


def save_profile(user_id, profile_name, utility_code, appliances):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO profiles (user_id, profile_name, utility_code, appliances_json) VALUES (?, ?, ?, ?)",
        (user_id, profile_name.strip(), utility_code, json.dumps(appliances))
    )
    conn.commit()
    profile_id = cursor.lastrowid
    conn.close()
    return profile_id


def get_user_profiles(user_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, profile_name, utility_code, appliances_json, created_at FROM profiles WHERE user_id = ? ORDER BY id DESC",
        (user_id,)
    )
    rows = cursor.fetchall()
    conn.close()

    return [
        {
            "id": row["id"],
            "profile_name": row["profile_name"],
            "utility_code": row["utility_code"],
            "appliances": json.loads(row["appliances_json"]),
            "created_at": row["created_at"]
        }
        for row in rows
    ]


def delete_profile(user_id, profile_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM profiles WHERE id = ? AND user_id = ?", (profile_id, user_id))
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted