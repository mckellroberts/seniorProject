"""
Authentication — registration, login, logout, session management.

Uses:
  - Flask-Login  : session management
  - Werkzeug     : password hashing (already a Flask dependency)
  - SQLite       : user storage (rag/data/users.db)

Routes (all under /auth):
  POST /auth/register  — create account
  POST /auth/login     — sign in
  POST /auth/logout    — sign out (requires login)
  GET  /auth/me        — return current user info or 401
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from flask import Blueprint, request, jsonify
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash

DB_PATH = Path(__file__).parent / "rag" / "data" / "users.db"

# ── User model ─────────────────────────────────────────────────────────────────

class User(UserMixin):
    def __init__(self, id: int, username: str):
        self.id = id
        self.username = username


# ── Database helpers ───────────────────────────────────────────────────────────

def _getDb():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def initDb() -> None:
    """Create the users table if it doesn't exist. Called once at app startup."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _getDb() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                username     TEXT    UNIQUE NOT NULL,
                password_hash TEXT   NOT NULL,
                created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)


def loadUser(userId: int) -> User | None:
    """Flask-Login callback — look up a user by their session ID."""
    with _getDb() as conn:
        row = conn.execute(
            "SELECT id, username FROM users WHERE id = ?", (userId,)
        ).fetchone()
    return User(row["id"], row["username"]) if row else None


# ── Blueprint ──────────────────────────────────────────────────────────────────

auth = Blueprint("auth", __name__, url_prefix="/auth")


@auth.route("/register", methods=["POST"])
def register():
    data     = request.json or {}
    username = data.get("username", "").strip()
    password = data.get("password", "")

    if not username or not password:
        return jsonify({"error": "Username and password are required"}), 400
    if len(username) < 3:
        return jsonify({"error": "Username must be at least 3 characters"}), 400
    if len(password) < 8:
        return jsonify({"error": "Password must be at least 8 characters"}), 400

    passwordHash = generate_password_hash(password)

    try:
        with _getDb() as conn:
            cursor = conn.execute(
                "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                (username, passwordHash),
            )
            userId = cursor.lastrowid
    except sqlite3.IntegrityError:
        return jsonify({"error": "Username already taken"}), 409

    login_user(User(userId, username), remember=True)
    return jsonify({"userId": userId, "username": username}), 201


@auth.route("/login", methods=["POST"])
def login():
    data     = request.json or {}
    username = data.get("username", "").strip()
    password = data.get("password", "")

    with _getDb() as conn:
        row = conn.execute(
            "SELECT id, username, password_hash FROM users WHERE username = ?",
            (username,),
        ).fetchone()

    if not row or not check_password_hash(row["password_hash"], password):
        return jsonify({"error": "Invalid username or password"}), 401

    login_user(User(row["id"], row["username"]), remember=True)
    return jsonify({"userId": row["id"], "username": row["username"]})


@auth.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    return jsonify({"message": "Logged out"})


@auth.route("/me", methods=["GET"])
def me():
    if not current_user.is_authenticated:
        return jsonify({"error": "Not authenticated"}), 401
    return jsonify({"userId": current_user.id, "username": current_user.username})
