"""Google Sign-In + lightweight session tokens + a tiny SQLite user store.

Flow:
  browser gets a Google ID token (JWT) from the "Sign in with Google" button
  -> POST /auth/google -> verify_google() checks it against Google's certs
  -> upsert_user() records the user (first login == signup)
  -> make_session() issues our own signed token the browser keeps.

Auth is enforced only when GOOGLE_CLIENT_ID is set; empty = dev fallback.
"""

import base64
import hashlib
import hmac
import json
import sqlite3
import time
from pathlib import Path

from google.auth.transport import requests as g_requests
from google.oauth2 import id_token

from .config import settings

_DB = Path(__file__).resolve().parent.parent / "users.db"

auth_enabled = bool(settings.google_client_id)


# ---------- user store (SQLite, stdlib) ----------
def _conn():
    c = sqlite3.connect(_DB)
    c.execute(
        """CREATE TABLE IF NOT EXISTS users(
            sub TEXT PRIMARY KEY, email TEXT, name TEXT, picture TEXT,
            created_at INTEGER, last_login INTEGER)"""
    )
    return c


def upsert_user(claims: dict) -> None:
    now = int(time.time())
    with _conn() as c:
        c.execute(
            """INSERT INTO users(sub,email,name,picture,created_at,last_login)
               VALUES(?,?,?,?,?,?)
               ON CONFLICT(sub) DO UPDATE SET
                 email=excluded.email, name=excluded.name,
                 picture=excluded.picture, last_login=excluded.last_login""",
            (claims["sub"], claims.get("email", ""), claims.get("name", ""),
             claims.get("picture", ""), now, now),
        )


# ---------- verify a Google ID token ----------
def verify_google(credential: str) -> dict:
    info = id_token.verify_oauth2_token(
        credential,
        g_requests.Request(),
        settings.google_client_id,
        clock_skew_in_seconds=60,  # tolerate a slightly-off system clock
    )
    return {
        "sub": info["sub"],
        "email": info.get("email", ""),
        "name": info.get("name", ""),
        "picture": info.get("picture", ""),
    }


# ---------- our own session token (HMAC-signed, stdlib) ----------
def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def _ub64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def make_session(user: dict, ttl: int = 7 * 86400) -> str:
    payload = {
        "sub": user["sub"], "email": user.get("email", ""),
        "name": user.get("name", ""), "exp": int(time.time()) + ttl,
    }
    body = _b64(json.dumps(payload, separators=(",", ":")).encode())
    sig = _b64(hmac.new(settings.session_secret.encode(), body.encode(), hashlib.sha256).digest())
    return f"{body}.{sig}"


def read_session(token: str) -> dict | None:
    try:
        body, sig = token.split(".")
        good = _b64(hmac.new(settings.session_secret.encode(), body.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(sig, good):
            return None
        payload = json.loads(_ub64(body))
        if payload.get("exp", 0) < time.time():
            return None
        return payload
    except Exception:
        return None
