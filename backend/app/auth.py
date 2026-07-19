"""Google Sign-In + stateless session tokens. NO server-side database.

Friends/preview stage: the server stores nothing. User info lives in the
browser (localStorage); the daily-session limit is tracked client-side too.
Session tokens are self-contained (HMAC-signed), so login needs no DB. A real
database comes at production time.
"""

import base64
import hashlib
import hmac
import json
import os
import time

from google.auth.transport import requests as g_requests
from google.oauth2 import id_token

from .config import settings

auth_enabled = bool(settings.google_client_id)

# Never sign tokens with the public default secret — that would let anyone forge
# a session and bypass Google login. If it's still the default, use a random
# per-process key (tokens just don't survive a restart, which is fine).
_SECRET = settings.session_secret
if _SECRET == "dev-change-me":
    _SECRET = base64.urlsafe_b64encode(os.urandom(32)).decode()
    if auth_enabled:
        print("[auth] WARNING: SESSION_SECRET not set — using a random per-process secret. "
              "Set SESSION_SECRET in the environment for stable sessions.")


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


# ---------- our own session token (HMAC-signed, stdlib, no DB) ----------
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
    sig = _b64(hmac.new(_SECRET.encode(), body.encode(), hashlib.sha256).digest())
    return f"{body}.{sig}"


def read_session(token: str) -> dict | None:
    try:
        body, sig = token.split(".")
        good = _b64(hmac.new(_SECRET.encode(), body.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(sig, good):
            return None
        payload = json.loads(_ub64(body))
        if payload.get("exp", 0) < time.time():
            return None
        return payload
    except Exception:
        return None
