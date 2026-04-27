"""
Authentication — registration, login, logout, session management.

Uses:
  - Flask-Login  : session management
  - Werkzeug     : password hashing (already a Flask dependency)
  - SQLite       : user storage (rag/data/users.db)

Routes (all under /auth):
  POST /auth/send-code — send 6-digit verification code to email
  POST /auth/register  — create account (requires valid code)
  POST /auth/login     — sign in
  POST /auth/logout    — sign out (requires login)
  GET  /auth/me        — return current user info or 401

Email config (environment variables):
  SMTP_HOST  — e.g. smtp.gmail.com
  SMTP_PORT  — default 587
  SMTP_USER  — sender address / login
  SMTP_PASS  — password or app-password
  SMTP_FROM  — display address (falls back to SMTP_USER)

  If SMTP_HOST is not set, codes are printed to the console (dev mode).
"""

from __future__ import annotations

import hashlib
import os
import random
import smtplib
import sqlite3
from datetime import datetime, timedelta, timezone
from email.mime.text import MIMEText
from pathlib import Path

from flask import Blueprint, request, jsonify
from flask_login import UserMixin, login_user, logout_user, login_required, current_user
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
    """Create / migrate tables. Called once at app startup."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _getDb() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                username      TEXT    UNIQUE NOT NULL,
                email         TEXT    UNIQUE,
                password_hash TEXT    NOT NULL,
                created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Migration: add email column to existing installs
        cols = [r[1] for r in conn.execute("PRAGMA table_info(users)").fetchall()]
        if "email" not in cols:
            conn.execute("ALTER TABLE users ADD COLUMN email TEXT")
            conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email ON users (email)")

        conn.execute("""
            CREATE TABLE IF NOT EXISTS email_codes (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                email      TEXT    NOT NULL,
                code_hash  TEXT    NOT NULL,
                expires_at TEXT    NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS saved_ideas (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id    INTEGER NOT NULL,
                idea       TEXT    NOT NULL,
                hook       TEXT,
                fit        TEXT,
                topic      TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)


def loadUser(userId: int) -> User | None:
    """Flask-Login callback — look up a user by their session ID."""
    with _getDb() as conn:
        row = conn.execute(
            "SELECT id, username FROM users WHERE id = ?", (userId,)
        ).fetchone()
    return User(row["id"], row["username"]) if row else None


# ── Email helpers ──────────────────────────────────────────────────────────────

def _generateCode() -> str:
    """Return a zero-padded 6-digit string."""
    return f"{random.randint(0, 999999):06d}"


def _hashCode(code: str) -> str:
    return hashlib.sha256(code.encode()).hexdigest()


def _sendEmail(toEmail: str, code: str) -> None:
    """
    Send the verification code by email.
    Falls back to console logging when SMTP_HOST is not configured.
    """
    host = os.environ.get("SMTP_HOST", "").strip()
    if not host:
        print(f"[DEV] Verification code for {toEmail}: {code}", flush=True)
        return

    port     = int(os.environ.get("SMTP_PORT", "587"))
    user     = os.environ.get("SMTP_USER", "")
    password = os.environ.get("SMTP_PASS", "")
    fromAddr = os.environ.get("SMTP_FROM", user)

    body = (
        f"Your VoiceForge verification code is:\n\n"
        f"  {code}\n\n"
        f"Enter this code on the sign-up page. It expires in 10 minutes.\n\n"
        f"If you didn't request this, you can ignore this email."
    )
    msg = MIMEText(body)
    msg["Subject"] = f"{code} is your VoiceForge verification code"
    msg["From"]    = fromAddr
    msg["To"]      = toEmail

    with smtplib.SMTP(host, port) as smtp:
        smtp.ehlo()
        smtp.starttls()
        smtp.login(user, password)
        smtp.sendmail(fromAddr, [toEmail], msg.as_string())


# ── Blueprint ──────────────────────────────────────────────────────────────────

auth = Blueprint("auth", __name__, url_prefix="/auth")


@auth.route("/send-code", methods=["POST"])
def sendCode():
    """Generate and email a 6-digit verification code."""
    data  = request.json or {}
    email = data.get("email", "").strip().lower()

    if not email or "@" not in email or "." not in email.split("@")[-1]:
        return jsonify({"error": "A valid email address is required"}), 400

    # Reject if email is already registered
    with _getDb() as conn:
        row = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
    if row:
        return jsonify({"error": "An account with this email already exists"}), 409

    code      = _generateCode()
    codeHash  = _hashCode(code)
    expiresAt = (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()

    with _getDb() as conn:
        conn.execute("DELETE FROM email_codes WHERE email = ?", (email,))
        conn.execute(
            "INSERT INTO email_codes (email, code_hash, expires_at) VALUES (?, ?, ?)",
            (email, codeHash, expiresAt),
        )

    try:
        _sendEmail(email, code)
    except Exception as e:
        return jsonify({"error": f"Failed to send email: {e}"}), 500

    return jsonify({"message": "Code sent"})


@auth.route("/register", methods=["POST"])
def register():
    data     = request.json or {}
    username = data.get("username", "").strip()
    email    = data.get("email", "").strip().lower()
    password = data.get("password", "")
    code     = data.get("code", "").strip()

    if not all([username, email, password, code]):
        return jsonify({"error": "All fields are required"}), 400
    if len(username) < 3:
        return jsonify({"error": "Username must be at least 3 characters"}), 400
    if len(password) < 8:
        return jsonify({"error": "Password must be at least 8 characters"}), 400

    # Verify the code
    with _getDb() as conn:
        row = conn.execute(
            "SELECT code_hash, expires_at FROM email_codes WHERE email = ?", (email,)
        ).fetchone()

    if not row:
        return jsonify({"error": "No verification code was sent to this email — request one first"}), 400

    if datetime.now(timezone.utc) > datetime.fromisoformat(row["expires_at"]):
        return jsonify({"error": "Verification code has expired — please request a new one"}), 400

    if _hashCode(code) != row["code_hash"]:
        return jsonify({"error": "Incorrect verification code"}), 400

    # Code is valid — create the account
    passwordHash = generate_password_hash(password)
    try:
        with _getDb() as conn:
            cursor = conn.execute(
                "INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)",
                (username, email, passwordHash),
            )
            userId = cursor.lastrowid
            conn.execute("DELETE FROM email_codes WHERE email = ?", (email,))
    except sqlite3.IntegrityError as e:
        if "username" in str(e).lower():
            return jsonify({"error": "Username already taken"}), 409
        return jsonify({"error": "An account with this email already exists"}), 409

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
