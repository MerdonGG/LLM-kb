import sqlite3
import hashlib
import secrets
import os
from datetime import datetime, timedelta
from typing import Optional

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "users.db")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            full_name TEXT NOT NULL,
            group_number TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'user',
            created_at TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            token TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            expires_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS chat_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            question TEXT NOT NULL,
            answer TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)
    # Создаём дефолтного админа если нет
    existing = conn.execute("SELECT id FROM users WHERE username = 'admin'").fetchone()
    if not existing:
        conn.execute(
            "INSERT INTO users (username, password_hash, full_name, group_number, role, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            ("admin", hash_password("admin123"), "Администратор", "—", "admin", datetime.now().isoformat())
        )
    conn.commit()
    conn.close()

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def register_user(username: str, password: str, full_name: str, group_number: str) -> dict:
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO users (username, password_hash, full_name, group_number, role, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (username, hash_password(password), full_name, group_number, "user", datetime.now().isoformat())
        )
        conn.commit()
        return {"success": True}
    except sqlite3.IntegrityError:
        return {"success": False, "error": "Пользователь с таким логином уже существует"}
    finally:
        conn.close()

def login_user(username: str, password: str) -> Optional[dict]:
    conn = get_db()
    user = conn.execute(
        "SELECT * FROM users WHERE username = ? AND password_hash = ?",
        (username, hash_password(password))
    ).fetchone()

    if not user:
        conn.close()
        return None

    token = secrets.token_hex(32)
    expires_at = (datetime.now() + timedelta(days=7)).isoformat()
    conn.execute(
        "INSERT INTO sessions (token, user_id, expires_at) VALUES (?, ?, ?)",
        (token, user["id"], expires_at)
    )
    conn.commit()
    conn.close()

    return {
        "token": token,
        "username": user["username"],
        "full_name": user["full_name"],
        "group_number": user["group_number"],
        "role": user["role"],
    }

def get_user_by_token(token: str) -> Optional[dict]:
    conn = get_db()
    result = conn.execute("""
        SELECT u.id, u.username, u.full_name, u.group_number, u.role
        FROM sessions s
        JOIN users u ON s.user_id = u.id
        WHERE s.token = ? AND s.expires_at > ?
    """, (token, datetime.now().isoformat())).fetchone()
    conn.close()
    return dict(result) if result else None

def logout_user(token: str):
    conn = get_db()
    conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
    conn.commit()
    conn.close()

def log_chat(user_id: int, question: str, answer: str):
    conn = get_db()
    conn.execute(
        "INSERT INTO chat_logs (user_id, question, answer, created_at) VALUES (?, ?, ?, ?)",
        (user_id, question, answer, datetime.now().isoformat())
    )
    conn.commit()
    conn.close()

def get_all_users():
    conn = get_db()
    users = conn.execute(
        "SELECT id, username, full_name, group_number, role, created_at FROM users WHERE role != 'admin' ORDER BY created_at DESC"
    ).fetchall()
    conn.close()
    return [dict(u) for u in users]

def get_user_chats(user_id: int):
    conn = get_db()
    logs = conn.execute(
        "SELECT question, answer, created_at FROM chat_logs WHERE user_id = ? ORDER BY created_at ASC",
        (user_id,)
    ).fetchall()
    conn.close()
    return [dict(l) for l in logs]
