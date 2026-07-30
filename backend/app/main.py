"""FastAPI app + the interview WebSocket.

Text-only protocol. The browser does speech-to-text and text-to-speech with
the Web Speech API, so the wire only ever carries text — Claude is the brain.

  client -> server
    {"type":"start","mode":"interview"|"conversation","name":..,"role":..}
    {"type":"user_text","text":..}          one finished spoken turn (transcribed)
    {"type":"end"}                          finish (interview -> report; convo -> just ends)

  server -> client
    {"type":"status","msg":..}
    {"type":"ai_text","text":..}            AI interviewer's line (browser speaks it)
    {"type":"interview_done"}               interviewer wrapped up
    {"type":"report","data":{..}}
    {"type":"error","msg":..}
"""

import json
import os
import time
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Header
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .config import settings
from .interview.engine import Session
from .interview.prompts import ASSESS_SYSTEM, LESSON_EVAL_SYSTEM, LEVEL_TEST_SYSTEM, LETTER_SYSTEM, GREETING_SYSTEM
from .providers import llm
from .providers.openrouter_provider import set_active_keys
from . import auth
from . import db

app = FastAPI(title="DuSu")

# --- Roles: owner (full admin + unlimited) and unlimited allowlist ---
OWNER_EMAILS = {"david123rana@gmail.com"}
UNLIMITED_EMAILS = {"shuhanisuhana037@gmail.com"}
def role_for(email: str) -> str:
    e = (email or "").strip().lower()
    if e in {x.lower() for x in OWNER_EMAILS}: return "owner"
    if e in {x.lower() for x in UNLIMITED_EMAILS}: return "unlimited"
    return "user"

# v2 access model:
#   owner / unlimited  → our keys, no quota
#   office-approved    → BYOK (their own keys), no quota
#   everyone else FREE → our keys, capped at PLAN_LIMITS[plan] requests/day
PLAN_LIMITS = {"free": 5, "starter": 50, "plus": 150, "pro": None}   # None = unlimited
FREE_LIMIT = 5         # free plan = 5 model requests per day
FREE_TRIAL_DAYS = 20   # free tier = a 20-day trial (5 requests/day); after that → subscribe


async def trial_left(uid: str | None) -> int:
    """Days left in the free 20-day trial (0 = expired)."""
    if not (uid and db.db_enabled):
        return FREE_TRIAL_DAYS
    try:
        return max(0, FREE_TRIAL_DAYS - await db.signup_day_count(uid))
    except Exception:
        return FREE_TRIAL_DAYS


async def is_office(email: str) -> bool:
    """Owner-approved for OFFICE = brings own keys (BYOK) + sees the Keys option."""
    try:
        return await db.office_has(email)
    except Exception:
        return False


async def is_unlimited(email: str) -> bool:
    """No daily quota: owner, unlimited allowlist, or office-approved (they pay via own keys)."""
    return role_for(email) in ("owner", "unlimited") or await is_office(email)


async def resolve_keys(email: str, keys: dict, uid: str | None = None):
    """Effective key chain. (ok, keys_or_None, reason). None = our default chain.
    FREE + owner/unlimited use OUR keys; OFFICE-approved must BYOK (client or stored)."""
    if role_for(email) in ("owner", "unlimited"):
        return True, None, ""                 # our keys
    if await is_office(email):                # BYOK required for office accounts
        if keys and any((str(v).strip() for v in (keys or {}).values())):
            return True, keys, ""
        if uid and db.db_enabled:
            try:
                stored = await db.get_user_keys(uid)
                if stored and any(str(v).strip() for v in stored.values()):
                    return True, stored, ""
            except Exception as e:
                print(f"[keys] load stored failed: {type(e).__name__}: {e}")
        return False, None, "keys_required"
    return True, None, ""                     # FREE tier → our keys (quota enforced separately)


async def charge_request(email: str, uid: str | None, day: str) -> dict:
    """Count one model request against the FREE daily quota. Unlimited users bypass.
    Returns {allowed, left, limit, unlimited}."""
    if await is_unlimited(email) or not (uid and db.db_enabled):
        return {"allowed": True, "left": None, "limit": None, "unlimited": True}
    plan = "free"
    try:
        plan = await db.get_plan(uid)
    except Exception:
        pass
    limit = PLAN_LIMITS.get(plan, FREE_LIMIT)
    if limit is None:                         # paid unlimited (pro)
        return {"allowed": True, "left": None, "limit": None, "unlimited": True}
    if plan == "free" and await trial_left(uid) <= 0:   # free trial expired → must subscribe
        return {"allowed": False, "left": 0, "limit": limit, "unlimited": False, "trial_over": True}
    r = await db.incr_request(uid, day, limit)
    return {"allowed": r["allowed"], "left": r["left"], "limit": limit, "unlimited": False,
            "trial_over": False}

def _is_quota(e) -> bool:
    """Does this error look like the user's keys hit their limit / all exhausted?"""
    s = str(e).lower()
    return any(k in s for k in ("429", "quota", "exhaust", "rate limit", "unavailable", "insufficient", "402"))


@app.on_event("startup")
async def _startup():
    await db.init_db()   # create tables if a database is configured (no-op otherwise)

_BACKEND = Path(__file__).resolve().parent.parent
_CLIENT_HTML = _BACKEND / "test_client.html"
_LOGO = _BACKEND / "logo.png"
_MANIFEST = _BACKEND / "manifest.webmanifest"
_SW = _BACKEND / "sw.js"

# Character art (the 8 anime PNG frames) lives here; served at /assets/...
_ASSETS = _BACKEND / "assets"
_ASSETS.mkdir(parents=True, exist_ok=True)
app.mount("/assets", StaticFiles(directory=str(_ASSETS)), name="assets")


@app.get("/logo.png")
async def logo():
    return FileResponse(_LOGO)


@app.get("/manifest.webmanifest")
async def manifest():
    return FileResponse(_MANIFEST, media_type="application/manifest+json")


@app.get("/sw.js")
async def service_worker():
    # Served from root so its scope covers the whole app.
    return FileResponse(_SW, media_type="application/javascript",
                        headers={"Cache-Control": "no-cache", "Service-Worker-Allowed": "/"})


# Android TWA package name + its signing-cert SHA-256(s). The APK's cert fingerprint
# must be listed here for Chrome to trust the app and drop the address bar (full-screen).
_TWA_PACKAGE = os.getenv("ANDROID_TWA_PACKAGE", "com.dusu.app")


@app.get("/.well-known/assetlinks.json")
async def assetlinks():
    """Digital Asset Links — proves the DuSu site trusts the TWA app so it runs
    full-screen (no browser chrome). Set ANDROID_CERT_SHA256 to the app's signing
    SHA-256 (comma-separated for multiple, e.g. upload + Play App Signing keys)."""
    raw = os.getenv("ANDROID_CERT_SHA256", "")
    fps = [f.strip().upper() for f in raw.replace("\n", ",").split(",") if f.strip()]
    statements = [{
        "relation": ["delegate_permission/common.handle_all_urls"],
        "target": {
            "namespace": "android_app",
            "package_name": _TWA_PACKAGE,
            "sha256_cert_fingerprints": fps,
        },
    }]
    return JSONResponse(statements, headers={"Cache-Control": "public, max-age=3600"})


@app.get("/health")
async def health():
    providers = settings.providers()
    return {"ok": True, "has_key": bool(providers), "providers": [p["name"] for p in providers]}


class GoogleIn(BaseModel):
    credential: str


@app.post("/auth/google")
async def auth_google(inp: GoogleIn):
    """Verify a Google ID token, upsert the user, return our session token."""
    if not auth.auth_enabled:
        raise HTTPException(500, "Google login not configured (set GOOGLE_CLIENT_ID)")
    try:
        claims = auth.verify_google(inp.credential)
    except Exception as e:
        print(f"[auth] google verify failed: {type(e).__name__}: {e}")
        raise HTTPException(401, "Invalid Google token")
    resp = {"token": auth.make_session(claims), "user": claims}
    if db.db_enabled:
        try:
            state = await db.login(claims)   # upsert user, load profile+progress
            resp["onboarded"] = state["onboarded"]
            resp["profile"] = state["profile"]
            resp["progress"] = state["progress"]
        except Exception as e:
            print(f"[db] login persist failed: {type(e).__name__}: {e}")
    return resp


class AboutIn(BaseModel):
    nickname: str = ""
    native_lang: str = ""
    profession: str = ""
    dream: str = ""
    interests: dict = {}


class AssessIn(BaseModel):
    token: str
    keys: dict = {}          # Office/BYOK keys (empty → default Personal chain)
    lang: str = "en"         # "hi" or "en" — language the learner took the test in
    about: AboutIn | None = None
    goal: str = ""
    comfort: str = ""
    practice_time: str = ""
    intro: str = ""          # task 1 transcript
    repeat_target: str = ""  # task 2 target sentence
    repeat_said: str = ""    # task 2 what they said
    think_hindi: str = ""    # task 3 Hindi prompt
    think_said: str = ""     # task 3 their English attempt
    open_said: str = ""      # task 4 transcript


def _bearer(header: str | None, token: str) -> str:
    """Prefer the Authorization: Bearer header; fall back to a ?token query."""
    if header and header.lower().startswith("bearer "):
        return header.split(" ", 1)[1].strip()
    return token


def _utc_day() -> str:
    import datetime as _d
    return _d.datetime.now(_d.timezone.utc).date().isoformat()


# Quota day is SERVER-authoritative in fixed IST (UTC+5:30). Client-sent day is IGNORED
# (was spoofable + caused day-bucket mismatch → false "instant reset"). Resets at IST
# midnight, i.e. right after 11:59 pm each day — one bucket per user per calendar day.
_IST = None
def _quota_day() -> str:
    import datetime as _d
    global _IST
    if _IST is None:
        _IST = _d.timezone(_d.timedelta(hours=5, minutes=30))
    return _d.datetime.now(_IST).date().isoformat()


@app.get("/me")
async def me(token: str = "", day: str = "", authorization: str | None = Header(None)):
    """Return the signed-in user's saved state (for reload / routing) + access + quota."""
    claims = auth.read_session(_bearer(authorization, token))
    if not claims:
        raise HTTPException(401, "Not signed in")
    email = claims.get("email", "")
    uid = claims.get("sub")
    _role = role_for(email)
    _office = await is_office(email)          # BYOK + Keys visibility
    _unlim = await is_unlimited(email)        # no quota
    plan, req_left, req_limit, trial_days, trial_over = "free", None, None, None, False
    if not _unlim and db.db_enabled and uid:
        try:
            plan = await db.get_plan(uid)
            req_limit = PLAN_LIMITS.get(plan, FREE_LIMIT)
            if req_limit is not None:
                used = await db.usage_today(uid, _quota_day())   # server IST day (ignore client `day`)
                req_left = max(0, req_limit - used)
            if plan == "free":
                trial_days = await trial_left(uid)
                trial_over = trial_days <= 0
        except Exception:
            pass
    # has_keys: office accounts must BYOK; everyone else rides our keys.
    _has_keys = True
    if _office and db.db_enabled and uid:
        try:
            _has_keys = await db.has_user_keys(uid)
        except Exception:
            _has_keys = False
    common = {"role": _role, "email": email, "office": _office, "office_allowed": _office,
              "unlimited": _unlim, "plan": plan, "requests_left": req_left,
              "request_limit": req_limit, "trial_days_left": trial_days, "trial_over": trial_over,
              "has_keys": _has_keys}
    if not db.db_enabled:
        return {"onboarded": None, **common}
    try:
        state = await db.login(claims)   # upsert row + bump last_seen + return state
        if isinstance(state, dict):
            state.update(common)
        if isinstance(state, dict) and state.get("onboarded"):
            try:
                uid_ = claims["sub"]
                state["today"] = await db.build_today(uid_)                    # S4 — Today's Home
                state["growth"] = await db.build_growth(uid_)                  # S6 — Growth signals
                state["opening"] = await db.build_opening(uid_)                # Companion Moment — greeting
                state["recommendations"] = await db.build_recommendations(uid_)  # Companion Moment — 3 recs
            except Exception as e:
                print(f"[home] build failed: {type(e).__name__}: {e}")
        return state
    except Exception as e:
        print(f"[me] db failed: {type(e).__name__}: {e}")
        return {"onboarded": False}


@app.get("/leaderboard")
async def leaderboard(token: str = "", authorization: str | None = Header(None)):
    """Top learners by all-time XP (private aliases) + your own rank."""
    claims = auth.read_session(_bearer(authorization, token))
    if not claims:
        raise HTTPException(401, "Not signed in")
    if not db.db_enabled:
        return {"top": [], "you": None}
    try:
        return await db.leaderboard(claims["sub"])
    except Exception as e:
        print(f"[leaderboard] failed: {type(e).__name__}: {e}")
        return {"top": [], "you": None}


class KeysIn(BaseModel):
    token: str = ""
    keys: dict = {}


@app.post("/keys/verify")
async def keys_verify(inp: KeysIn, authorization: str | None = Header(None)):
    """Office/BYOK: test each supplied key with a tiny call → per-provider ok/error.
    On >=2 working keys, persist them (sealed) so the user never re-enters on return."""
    claims = auth.read_session(_bearer(authorization, inp.token))
    if not claims:
        raise HTTPException(401, "Not signed in")
    from openai import AsyncOpenAI
    out = {}
    for p in settings.providers_from(inp.keys):
        ok, err = False, ""
        try:
            c = AsyncOpenAI(api_key=p["key"], base_url=p["base_url"], default_headers=p.get("headers") or {})
            await c.chat.completions.create(model=p["models"][0],
                messages=[{"role": "user", "content": "Reply OK"}],
                max_tokens=8, temperature=0, extra_body=p.get("extra") or {})
            ok = True                              # authenticated (content may be empty but key is valid)
        except Exception as e:
            s = str(e)
            if p["name"] == "github" and any(k in s.lower() for k in ("403", "permission", "scope", "models")):
                err = "This GitHub token needs the 'models' permission."
            elif any(k in s.lower() for k in ("401", "invalid", "unauthor", "api key")):
                err = "Invalid key."
            elif any(k in s.lower() for k in ("429", "quota", "exhaust", "rate")):
                err = "Key works but quota is exhausted right now."; ok = True
            else:
                err = s[:120]
        out[p["name"]] = {"ok": ok, "error": err}
    # Persist the keys server-side when >=2 verified (so returning users skip re-entry).
    ok_count = sum(1 for r in out.values() if r.get("ok"))
    if db.db_enabled and claims.get("sub"):
        try:
            await db.login(claims)   # ensure the user row exists (FK)
            await db.save_user_keys(claims["sub"], inp.keys, verified=(ok_count >= 2))
        except Exception as e:
            print(f"[keys] save failed: {type(e).__name__}: {e}")
    return {"results": out, "saved": ok_count >= 2}


class KeysGetIn(BaseModel):
    token: str = ""


@app.post("/keys/get")
async def keys_get(inp: KeysGetIn, authorization: str | None = Header(None)):
    """Return the signed-in user's own stored BYOK keys (so a returning device can
    reuse them without re-entry). Only ever returns the caller's OWN keys."""
    claims = auth.read_session(_bearer(authorization, inp.token))
    if not claims:
        raise HTTPException(401, "Not signed in")
    keys, verified = {}, False
    if db.db_enabled and claims.get("sub"):
        try:
            keys = await db.get_user_keys(claims["sub"])
            verified = await db.has_user_keys(claims["sub"])
        except Exception as e:
            print(f"[keys] get failed: {type(e).__name__}: {e}")
    return {"keys": keys, "verified": verified}


class FeedbackIn(BaseModel):
    token: str = ""
    kind: str = "feedback"     # feedback | help
    text: str = ""


@app.post("/feedback")
async def feedback(inp: FeedbackIn, authorization: str | None = Header(None)):
    """Store a Help/Feedback message from the signed-in user (+ optional owner webhook)."""
    claims = auth.read_session(_bearer(authorization, inp.token))
    if not claims:
        raise HTTPException(401, "Not signed in")
    text = (inp.text or "").strip()
    if not text:
        raise HTTPException(400, "empty")
    kind = "help" if inp.kind == "help" else "feedback"
    if db.db_enabled and claims.get("sub"):
        try:
            await db.login(claims)   # ensure user row exists (FK)
            await db.add_feedback(claims["sub"], claims.get("email", ""), kind, text)
        except Exception as e:
            print(f"[feedback] save failed: {type(e).__name__}: {e}")
    wh = os.getenv("FEEDBACK_WEBHOOK")   # optional: instant owner ping (e.g. Discord/Slack)
    if wh:
        try:
            import httpx
            async with httpx.AsyncClient(timeout=5) as c:
                await c.post(wh, json={"content": f"[DuSu {kind}] {claims.get('email','')}: {text[:500]}"})
        except Exception as e:
            print(f"[feedback] webhook failed: {type(e).__name__}: {e}")
    return {"ok": True}


# --- Super Admin portal (separate static-cred gate, server-side) ---
import hmac as _hmac
import hashlib as _hashlib
_SA_USER = os.getenv("SUPERADMIN_USER", "DuSuRuralAppAdmin")
_SA_PASS = os.getenv("SUPERADMIN_PASS", "Sup$#307Admin")


def _sa_make(ttl: int = 8 * 3600) -> str:
    """Signed super-admin session token (HMAC over expiry with the app secret)."""
    exp = int(time.time()) + ttl
    sig = _hmac.new(settings.session_secret.encode(), f"sa:{exp}".encode(), _hashlib.sha256).hexdigest()
    return f"{exp}.{sig}"


def _sa_check(token: str) -> bool:
    try:
        exp_s, sig = (token or "").split(".", 1)
        exp = int(exp_s)
        if exp < int(time.time()):
            return False
        good = _hmac.new(settings.session_secret.encode(), f"sa:{exp}".encode(), _hashlib.sha256).hexdigest()
        return _hmac.compare_digest(sig, good)
    except Exception:
        return False


def _require_sa(token: str):
    if not _sa_check(token):
        raise HTTPException(401, "Super admin session required")


class SuperAdminIn(BaseModel):
    username: str = ""
    password: str = ""


class SaTokenIn(BaseModel):
    token: str = ""


class SaApproveIn(BaseModel):
    token: str = ""
    email: str = ""
    on: bool = True


class SaActionIn(BaseModel):
    token: str = ""
    user_id: str = ""
    action: str = ""     # block | unblock | delete


@app.post("/superadmin/auth")
async def superadmin_auth(inp: SuperAdminIn):
    """Verify the static super-admin credentials SERVER-SIDE (constant-time) → issue a
    signed super-admin session token used by every /superadmin/* data endpoint."""
    ok = (_hmac.compare_digest(inp.username or "", _SA_USER)
          and _hmac.compare_digest(inp.password or "", _SA_PASS))
    if not ok:
        raise HTTPException(401, "Invalid credentials")
    return {"ok": True, "token": _sa_make()}


@app.post("/superadmin/overview")
async def superadmin_overview(inp: SaTokenIn):
    """All users + analytics (super-admin only)."""
    _require_sa(inp.token)
    if not db.db_enabled:
        return {"db": False, "users": [], "counts": {}}
    users = await db.admin_list_users()
    for u in users:
        u["role"] = role_for(u.get("email", ""))
    counts = {
        "total": len(users),
        "online": sum(1 for u in users if u.get("online")),
        "office": sum(1 for u in users if u.get("office")),
        "blocked": sum(1 for u in users if u.get("status") == "blocked"),
        "paid": sum(1 for u in users if (u.get("plan") or "free") != "free"),
    }
    return {"db": True, "users": users, "counts": counts, "office_emails": await db.office_list()}


@app.post("/superadmin/approve")
async def superadmin_approve(inp: SaApproveIn):
    """Approve (or revoke) an email for OFFICE use → grants BYOK + the Keys option."""
    _require_sa(inp.token)
    email = (inp.email or "").strip().lower()
    if not email:
        raise HTTPException(400, "email required")
    if inp.on:
        await db.office_add(email)
    else:
        await db.office_remove(email)
    return {"ok": True, "email": email, "office": inp.on}


@app.post("/superadmin/action")
async def superadmin_action(inp: SaActionIn):
    """Block / unblock / delete a user (super-admin only)."""
    _require_sa(inp.token)
    if inp.action == "delete":
        await db.delete_user(inp.user_id)
    elif inp.action == "block":
        await db.set_user_status(inp.user_id, "blocked")
    elif inp.action == "unblock":
        await db.set_user_status(inp.user_id, "active")
    else:
        raise HTTPException(400, "bad action")
    return {"ok": True}


def _require_owner(token: str, authorization: str | None):
    claims = auth.read_session(_bearer(authorization, token))
    if not claims:
        raise HTTPException(401, "Not signed in")
    if role_for(claims.get("email", "")) != "owner":
        raise HTTPException(403, "Owner only")
    return claims


@app.get("/admin/overview")
async def admin_overview(token: str = "", authorization: str | None = Header(None)):
    """Owner-only dashboard: every user's full info + activity."""
    claims = _require_owner(token, authorization)
    out = {"you": claims.get("email", ""), "role": "owner", "db": db.db_enabled, "users": []}
    if db.db_enabled:
        try:
            users = await db.admin_list_users()
            for u in users:                       # attach computed role
                u["role"] = role_for(u.get("email", ""))
            out["users"] = users
            out["counts"] = {
                "total": len(users),
                "active": sum(1 for u in users if u["status"] == "active"),
                "pending": sum(1 for u in users if u["status"] == "pending"),
                "blocked": sum(1 for u in users if u["status"] == "blocked"),
                "office": sum(1 for u in users if u["mode"] == "office"),
            }
            out["office_emails"] = await db.office_list()
            out["feedback"] = await db.list_feedback(50)
        except Exception as e:
            print(f"[admin] list failed: {type(e).__name__}: {e}")
    return out


class SettingsIn(BaseModel):
    token: str = ""
    require_own_keys: bool


@app.post("/admin/settings")
async def admin_settings(inp: SettingsIn, authorization: str | None = Header(None)):
    """Owner-only: flip the global 'require own keys' switch."""
    _require_owner(inp.token, authorization)
    await db.set_setting("require_own_keys", "1" if inp.require_own_keys else "0")
    return {"require_own_keys": inp.require_own_keys}


class WipeIn(BaseModel):
    token: str = ""


@app.post("/admin/wipe")
async def admin_wipe(inp: WipeIn, authorization: str | None = Header(None)):
    """Owner-only: delete all users EXCEPT owner + unlimited + free-access emails.
    (Testing reset.)"""
    _require_owner(inp.token, authorization)
    if not db.db_enabled:
        raise HTTPException(400, "Database required")
    keep = {e.lower() for e in OWNER_EMAILS} | {e.lower() for e in UNLIMITED_EMAILS}
    try:
        keep |= set(await db.office_list())
    except Exception:
        pass
    n = await db.admin_wipe_users(keep)
    return {"deleted": n, "kept": sorted(keep)}


class OfficeEmailIn(BaseModel):
    token: str = ""
    email: str
    action: str        # add | remove


@app.post("/admin/office")
async def admin_office(inp: OfficeEmailIn, authorization: str | None = Header(None)):
    """Owner-only: add / remove an email from the Office allowlist."""
    _require_owner(inp.token, authorization)
    if not db.db_enabled:
        raise HTTPException(400, "Database required")
    if inp.action == "add":
        ok = await db.office_add(inp.email)
    elif inp.action == "remove":
        ok = await db.office_remove(inp.email)
    else:
        raise HTTPException(400, "Unknown action")
    return {"ok": ok, "office_emails": await db.office_list()}


class AdminActionIn(BaseModel):
    token: str = ""
    target_id: str
    action: str        # approve | block | unblock


@app.post("/admin/action")
async def admin_action(inp: AdminActionIn, authorization: str | None = Header(None)):
    """Owner-only: approve / block / unblock a user."""
    _require_owner(inp.token, authorization)
    if not db.db_enabled:
        raise HTTPException(400, "Database required")
    if inp.action == "delete":
        ok = await db.delete_user(inp.target_id)
        return {"ok": ok, "deleted": True}
    status = {"approve": "active", "unblock": "active", "block": "blocked"}.get(inp.action)
    if not status:
        raise HTTPException(400, "Unknown action")
    ok = await db.set_user_status(inp.target_id, status)
    return {"ok": ok, "status": status}


class ModeIn(BaseModel):
    token: str
    mode: str          # personal | office


@app.post("/mode")
async def set_mode(inp: ModeIn):
    """User picks Personal/Office. Office for a normal user → pending (needs owner
    approval); owner/unlimited stay active. Personal → active."""
    claims = auth.read_session(inp.token)
    if not claims:
        raise HTTPException(401, "Not signed in")
    role = role_for(claims.get("email", ""))
    if inp.mode == "office" and role == "user":
        status = "pending"
    else:
        status = "active"
    if db.db_enabled:
        try:
            await db.set_user_mode(claims["sub"], inp.mode if inp.mode in ("personal", "office") else "personal", status)
        except Exception as e:
            print(f"[mode] failed: {type(e).__name__}: {e}")
    return {"mode": inp.mode, "status": status, "role": role}


class GenIn(BaseModel):
    token: str = ""
    keys: dict = {}


@app.post("/leveltest/gen")
async def leveltest_gen(inp: GenIn):
    """Dynamic level-check: the model (the user's keys) makes fresh questions each
    time — which also verifies their keys actually work."""
    claims = auth.read_session(inp.token)
    if not claims:
        raise HTTPException(401, "Not signed in")
    ok, eff, _r = await resolve_keys(claims.get("email", ""), inp.keys, claims.get("sub"))
    if not ok:
        raise HTTPException(402, "keys_required")
    set_active_keys(eff)
    sys = (
        "You design a SHORT, FRESH, fully-dynamic spoken-English level check for a Hindi-first "
        "learner. Vary ALL content every time (different everyday topics and phrasings) so it can "
        "never be memorized and repeated.\n"
        "Fill these values:\n"
        "- repeat: one natural English sentence, 6-10 words, for them to repeat.\n"
        "- think_hindi: one everyday Hindi sentence in Latin script for them to say in English.\n"
        "- open: one warm, open English question on an UNUSUAL everyday topic (not weekends/Sundays).\n"
        "- mcqs: exactly 3 questions. goal = why they want to learn English (4-6 short options). "
        "comfort = how comfortable they are speaking English (exactly 5 options, ordered from "
        "'cannot speak at all' up to 'fairly fluent'). practice_time = how much time daily (exactly "
        "4 options, ordered least-to-most).\n"
        "Return ONLY this JSON, filling every value (no comments, no markdown):\n"
        '{"repeat":"","think_hindi":"","open":"",'
        '"mcqs":[{"field":"goal","q":"","options":[]},'
        '{"field":"comfort","q":"","options":[]},'
        '{"field":"practice_time","q":"","options":[]}]}'
    )
    try:
        # bigger budget — the full JSON (voice tasks + 3 MCQs) must fit or it truncates → parse fail.
        # The model is occasionally chatty/truncates → retry a couple times before giving up
        # (the frontend still has a static fallback if all attempts fail).
        d = None
        for _ in range(3):
            d = await llm.assess(sys, "Generate a fresh level check now.", max_tokens=1200)
            if isinstance(d, dict) and not d.get("error") and isinstance(d.get("mcqs"), list) and d.get("repeat"):
                break
        if not isinstance(d, dict) or d.get("error"):
            raise RuntimeError("gen parse failed")
        mcqs = d.get("mcqs")
        if not isinstance(mcqs, list):
            mcqs = []
        # keep only well-formed MCQs (field + >=2 string options)
        clean = []
        for m in mcqs:
            if isinstance(m, dict) and m.get("field") in ("goal", "comfort", "practice_time"):
                opts = [str(o) for o in (m.get("options") or []) if str(o).strip()]
                if len(opts) >= 2:
                    clean.append({"field": m["field"], "q": str(m.get("q", "")).strip(), "options": opts})
        return {"repeat": d.get("repeat", ""), "think_hindi": d.get("think_hindi", ""),
                "open": d.get("open", ""), "mcqs": clean}
    except Exception as e:
        if _is_quota(e):
            raise HTTPException(429, "quota")
        print(f"[leveltest gen] {type(e).__name__}: {e}")
        raise HTTPException(502, "gen_failed")


@app.post("/assessment")
async def assessment(inp: AssessIn):
    """Score the level assessment, save the profile, return it."""
    claims = auth.read_session(inp.token)
    if not claims:
        raise HTTPException(401, "Not signed in")
    _ok, _eff, _r = await resolve_keys(claims.get("email", ""), inp.keys, claims.get("sub"))
    if not _ok:
        raise HTTPException(402, "keys_required")
    set_active_keys(_eff)
    payload = (
        f"goal: {inp.goal}\ncomfort: {inp.comfort}\npractice_time: {inp.practice_time}\n\n"
        f"TASK 1 (intro): {inp.intro or '(no answer)'}\n\n"
        f"TASK 2 (repeat)\n  target: {inp.repeat_target}\n  said: {inp.repeat_said or '(no answer)'}\n\n"
        f"TASK 3 (think)\n  hindi: {inp.think_hindi}\n  said in English: {inp.think_said or '(no answer)'}\n\n"
        f"TASK 4 (open): {inp.open_said or '(no answer)'}"
    )
    if inp.lang == "hi":
        payload += ("\n\nIMPORTANT: The learner chose HINDI. Write the 'message' field in "
                    "simple, warm Hindi written in Latin/Roman script (e.g. 'Aap bahut acche kar rahe hain'). "
                    "Keep all JSON keys and level/score values exactly as specified.")
    try:
        # bigger budget + retry — the model occasionally adds commentary/truncates,
        # which parse-fails → empty scores → all-zero report. Retry a few times.
        result = None
        for _ in range(3):
            result = await llm.assess(ASSESS_SYSTEM, payload, max_tokens=900)
            if isinstance(result, dict) and not result.get("error") and isinstance(result.get("scores"), dict) and result["scores"]:
                break
        if not (isinstance(result, dict) and isinstance(result.get("scores"), dict) and result["scores"]):
            raise RuntimeError("assess parse failed / empty scores")
    except Exception as e:
        print(f"[assess] llm failed: {type(e).__name__}: {e}")
        raise HTTPException(502, "Assessment scoring failed, please try again")

    data = {
        "goal": inp.goal, "comfort": inp.comfort, "practice_time": inp.practice_time,
        "level": result.get("level", "A1"),
        "scores": result.get("scores", {}),
        "weak_areas": result.get("weak_areas", []),
    }
    progress = None
    if db.db_enabled:
        try:
            await db.login(claims)   # ensure user+profile+progress rows exist (cached-token logins skip onGoogle)
            state = await db.save_assessment(claims["sub"], data, lang=inp.lang)
            progress = state.get("progress")   # seeded journey (start/current level) → return it so the roadmap is right now
            # Save the emotional "About you" facts + the Day-1 intro as the baseline.
            about = (inp.about.model_dump() if inp.about else {})
            about["native_lang"] = about.get("native_lang") or inp.lang
            about["intro_text"] = inp.intro or ""
            await db.save_about(claims["sub"], about)
        except Exception as e:
            print(f"[assess] db save failed: {type(e).__name__}: {e}")
    return {"profile": data, "message": result.get("message", ""), "progress": progress}


class CheckinIn(BaseModel):
    token: str
    mood: str


class TokenIn(BaseModel):
    token: str
    keys: dict = {}          # Office/BYOK keys (empty → default Personal chain)


class FutureMeIn(BaseModel):
    token: str
    text: str


@app.post("/checkin")
async def checkin(inp: CheckinIn):
    claims = auth.read_session(inp.token)
    if not claims:
        raise HTTPException(401, "Not signed in")
    if not db.db_enabled:
        return {"ok": True}
    try:
        facts = await db.save_checkin(claims["sub"], inp.mood)
        return {"ok": True, "memory": facts}
    except Exception as e:
        print(f"[checkin] failed: {type(e).__name__}: {e}")
        return {"ok": False}


@app.post("/greeting")
async def greeting(inp: TokenIn):
    """The Companion Moment — DuSu's AI-generated Hinglish greeting from memory."""
    claims = auth.read_session(inp.token)
    if not claims:
        raise HTTPException(401, "Not signed in")
    ok, eff, _r = await resolve_keys(claims.get("email", ""), inp.keys, claims.get("sub"))
    if not ok:
        raise HTTPException(402, "keys_required")
    set_active_keys(eff)
    if not db.db_enabled:
        return {"text": ""}
    try:
        uid = claims["sub"]
        ctx = await db.build_companion_context(uid)
        sums = await db.recent_summaries(uid, 1)
        payload = {
            "name": ctx["identity"].get("nickname", ""),
            "stage": ctx["stage"]["stage"],
            "days_together": ctx["stage"]["days"],
            "identity": ctx["identity"],
            "moments": ctx["moments"],
            "achievements": ctx["achievements"],
            "energy_today": ctx["energy_today"].get("value", ""),
            "next_hook": ctx.get("next_hook", ""),
            "world": ctx.get("world", ""),
            "last_session": sums[0] if sums else "",
        }
        text = await llm.next_question(GREETING_SYSTEM, [{"role": "user", "content": json.dumps(payload, ensure_ascii=False)}])
        return {"text": (text or "").strip()}
    except Exception as e:
        print(f"[greeting] failed: {type(e).__name__}: {e}")
        return {"text": ""}


@app.post("/futureme")
async def futureme(inp: FutureMeIn):
    claims = auth.read_session(inp.token)
    if not claims:
        raise HTTPException(401, "Not signed in")
    if not db.db_enabled or not (inp.text or "").strip():
        return {"ok": True}
    try:
        facts = await db.save_future_me(claims["sub"], inp.text.strip())
        return {"ok": True, "memory": facts}
    except Exception as e:
        print(f"[futureme] failed: {type(e).__name__}: {e}")
        return {"ok": False}


@app.post("/letter")
async def letter(inp: TokenIn):
    """Return this week's personal note from DuSu (generates one if stale)."""
    import datetime as _dt
    claims = auth.read_session(inp.token)
    if not claims:
        raise HTTPException(401, "Not signed in")
    ok, eff, _r = await resolve_keys(claims.get("email", ""), inp.keys, claims.get("sub"))
    if not ok:
        raise HTTPException(402, "keys_required")
    set_active_keys(eff)
    if not db.db_enabled:
        return {"letter": None}
    try:
        state = await db.get_state(claims["sub"]) or {}
        facts = state.get("memory", {}) or {}
        prog = state.get("progress", {}) or {}
        last = facts.get("last_letter") or {}
        today = _dt.date.today()
        # only (re)generate at most once every 7 days, and only with some activity
        if last.get("date"):
            try:
                if (today - _dt.date.fromisoformat(last["date"])).days < 7:
                    return {"letter": last, "fresh": False}
            except Exception:
                pass
        if int(prog.get("xp", 0)) < 20:
            return {"letter": last or None, "fresh": False}  # not enough activity yet
        name = facts.get("nickname") or state.get("user", {}).get("name", "there")
        summaries = await db.recent_summaries(claims["sub"], 5)
        prompt = (
            f"name: {name}\nnative_lang: {facts.get('native_lang','en')}\n"
            f"dream: {facts.get('dream','')}\ninterests: {facts.get('interests',{})}\n"
            f"level: {state.get('profile',{}).get('level','')}\n"
            f"xp: {prog.get('xp',0)}  streak_days: {prog.get('streak_days',0)}\n"
            f"recent chats: {' | '.join(summaries) if summaries else '(none yet)'}\n"
            f"recent facts: {'; '.join(facts.get('facts_learned',[])[-5:])}"
        )
        text = await llm.generate(LETTER_SYSTEM, prompt, max_tokens=350)
        text = (text or "").strip()
        if not text:
            return {"letter": last or None, "fresh": False}
        await db.save_letter(claims["sub"], text)
        return {"letter": {"date": today.isoformat(), "text": text}, "fresh": True}
    except Exception as e:
        print(f"[letter] failed: {type(e).__name__}: {e}")
        return {"letter": None}


class LessonEvalIn(BaseModel):
    token: str
    keys: dict = {}
    lang: str = "en"
    type: str = "speak"       # think | speak
    prompt: str = ""          # what the learner was asked
    target: str = ""          # ideal/expected answer
    said: str = ""            # their transcribed attempt


class LessonDoneIn(BaseModel):
    token: str
    level: int
    lesson_id: str
    lesson_type: str = ""


@app.post("/lesson/evaluate")
async def lesson_evaluate(inp: LessonEvalIn):
    """Score one spoken lesson answer, return warm feedback (no DB write)."""
    claims = auth.read_session(inp.token)
    if not claims:
        raise HTTPException(401, "Not signed in")
    ok, eff, _r = await resolve_keys(claims.get("email", ""), inp.keys, claims.get("sub"))
    if not ok:
        raise HTTPException(402, "keys_required")
    set_active_keys(eff)
    payload = (
        f"lang: {inp.lang}\ntype: {inp.type}\n"
        f"prompt: {inp.prompt}\ntarget: {inp.target or '(open answer)'}\n"
        f"learner said: {inp.said or '(no answer)'}"
    )
    try:
        return await llm.assess(LESSON_EVAL_SYSTEM, payload)
    except Exception as e:
        print(f"[lesson] eval failed: {type(e).__name__}: {e}")
        raise HTTPException(502, "Could not evaluate, please try again")


@app.post("/lesson/complete")
async def lesson_complete(inp: LessonDoneIn):
    """Mark a lesson complete → update journey/xp/streak/badges. Returns progress."""
    claims = auth.read_session(inp.token)
    if not claims:
        raise HTTPException(401, "Not signed in")
    if not db.db_enabled:
        return {"progress": None, "leveled_up": False, "new_badges": []}
    try:
        await db.login(claims)   # ensure rows exist
        return await db.complete_lesson(claims["sub"], inp.level, inp.lesson_id, inp.lesson_type)
    except Exception as e:
        print(f"[lesson] complete failed: {type(e).__name__}: {e}")
        raise HTTPException(500, "Could not save progress")


class LevelTestItem(BaseModel):
    prompt: str = ""
    target: str = ""
    said: str = ""


class LevelTestIn(BaseModel):
    token: str
    keys: dict = {}
    level: int
    lang: str = "en"
    items: list[LevelTestItem] = []


@app.post("/level/test/submit")
async def level_test_submit(inp: LevelTestIn):
    """Score a whole Level Test in one LLM call, persist the attempt, and
    unlock the next level if the learner passed (>=70)."""
    claims = auth.read_session(inp.token)
    if not claims:
        raise HTTPException(401, "Not signed in")
    ok, eff, _r = await resolve_keys(claims.get("email", ""), inp.keys, claims.get("sub"))
    if not ok:
        raise HTTPException(402, "keys_required")
    set_active_keys(eff)
    lines = "\n\n".join(
        f"Item {i+1}:\n  prompt: {it.prompt}\n  target: {it.target or '(open answer)'}\n  learner said: {it.said or '(no answer)'}"
        for i, it in enumerate(inp.items)
    )
    payload = f"lang: {inp.lang}\nlevel: {inp.level}\n\n{lines}"
    try:
        result = await llm.assess(LEVEL_TEST_SYSTEM, payload)
    except Exception as e:
        print(f"[level-test] eval failed: {type(e).__name__}: {e}")
        raise HTTPException(502, "Could not score the test, please try again")

    try:
        score = int(float(result.get("score") or 0))   # LLMs sometimes return null/"70%"/"eighty"
    except (TypeError, ValueError):
        import re as _re
        m = _re.search(r"\d+", str(result.get("score") or ""))
        score = int(m.group()) if m else 0
    score = max(0, min(100, score))
    out = {"score": score, "passed": bool(result.get("passed", score >= 70)),
           "items": result.get("items", []), "message": result.get("message", "")}
    if db.db_enabled:
        try:
            await db.login(claims)
            saved = await db.submit_level_test(claims["sub"], inp.level, score)
            out["leveled_up"] = saved["leveled_up"]
            out["new_badges"] = saved["new_badges"]
            out["progress"] = saved["progress"]
        except Exception as e:
            print(f"[level-test] db save failed: {type(e).__name__}: {e}")
    return out


@app.get("/")
async def index():
    if not _CLIENT_HTML.exists():
        return HTMLResponse("<h1>DuSu</h1><p>test_client.html missing</p>")
    html = _CLIENT_HTML.read_text(encoding="utf-8")
    # Inject config the client needs (Google client id + whether auth is on).
    html = html.replace("__GOOGLE_CLIENT_ID__", settings.google_client_id)
    html = html.replace("__AUTH_ENABLED__", "true" if auth.auth_enabled else "false")
    html = html.replace("__MAX_SESSIONS__", str(settings.max_sessions_per_day))
    return HTMLResponse(html)


async def _send(ws: WebSocket, **payload) -> None:
    await ws.send_text(json.dumps(payload))


# S3 — Relationship Journey → how DuSu should sound at each stage (never shown to user).
_STAGE_TONE = {
    "Guest":            "You've just met. Be warm, welcoming and encouraging; keep it light.",
    "Friend":           "You're becoming friends. Be friendly and personal; reference small things they told you.",
    "Practice Partner": "You're their regular practice partner. Relaxed and familiar; pick up where you left off.",
    "Coach":            "You're their coach now. Warmly push them a little; celebrate progress you've seen.",
    "Mentor":           "You're a trusted mentor. Speak with warmth and belief in them; reference their journey.",
    "Companion":        "You're a close companion. Warm and familiar; use natural callbacks; show you truly know them.",
}


def _facts_summary(facts: dict, summaries: list[str]) -> str:
    """Compact 'what DuSu remembers' block injected into the session persona."""
    lines = []
    if facts.get("nickname"):   lines.append(f"- Call them: {facts['nickname']}")
    if facts.get("profession"): lines.append(f"- Profession: {facts['profession']}")
    if facts.get("dream"):      lines.append(f"- Their dream: {facts['dream']}")
    interests = facts.get("interests") or {}
    if interests:
        lines.append("- Interests: " + ", ".join(f"{k}: {v}" for k, v in interests.items()))
    fl = facts.get("facts_learned") or []
    if fl:
        lines.append("- Known facts: " + "; ".join(fl[-5:]))
    ev = facts.get("events") or []
    if ev:
        lines.append("- Upcoming: " + "; ".join(f"{e.get('type','')} {e.get('date','')}".strip() for e in ev[-3:]))
    # S1/S3 — relationship traits, live emotional moments, achievements, today's energy
    rel = facts.get("relationship") or {}
    if rel:
        lines.append("- How to treat them: " + ", ".join(str(k).replace("_", " ") for k in rel.keys()))
    moments = facts.get("moments") or []
    if moments:
        lines.append("- Recent moments (care about / gently ask about these): " + "; ".join(
            (m.get("text", "") + (f" [{m.get('emotion')}]" if m.get("emotion") else "")) for m in moments[-4:]))
    achs = facts.get("achievements") or []
    if achs:
        lines.append("- Proud of: " + "; ".join(a.get("text", "") for a in achs[-4:]))
    energy = (facts.get("energy_today") or {}).get("value")
    if energy:
        lines.append(f"- Their energy today: {energy} (match it)")
    if facts.get("next_hook"):
        lines.append(f"- Last time you promised to: {facts['next_hook']} — pick up on it early.")
    if summaries:
        lines.append("- Recent chats: " + " | ".join(summaries))
    # Cross-mode continuity: the tail of the LAST conversation (any mode — Daily Talk in
    # Hindi, English Talk, or Interview). Lets DuSu pick up the exact thread instead of
    # restarting, so all three practice modes feel like ONE ongoing relationship.
    rturns = facts.get("recent_turns") or []
    if rturns:
        who = {"user": "them", "assistant": "you"}
        tail = "; ".join(f"{who.get(t.get('role'), t.get('role'))}: {t.get('content','')}"
                         for t in rturns[-6:] if t.get("content"))
        if tail:
            last_mode = rturns[-1].get("mode") or ""
            label = {"daily": "Daily Talk (Hindi)", "conversation": "English Talk",
                     "interview": "Interview"}.get(last_mode, "your last chat")
            lines.append(f"- Where you left off last time (during {label}) — continue THIS thread "
                         f"naturally, do NOT restart with a fresh greeting: {tail}")
    if lines:
        lines.append("- Show you remember and care; you may gently ask about ONE recent moment. "
                     "Never invent memories you don't actually have.")
    return "\n".join(lines)


def _daily_context_str(facts: dict) -> str:
    """Compact recent-days context (mood/plans/events) for the daily prompt."""
    out = []
    for e in (facts.get("daily_context") or []):
        bits = [e.get("date", "")]
        if e.get("mood"):    bits.append("mood=" + e["mood"])
        if e.get("plans"):   bits.append("plans=" + e["plans"])
        if e.get("weather"): bits.append("weather=" + e["weather"])
        for ev in (e.get("events") or []):
            bits.append(f"event={ev.get('type','')} {ev.get('date','')} {ev.get('note','')}".strip())
        for n in (e.get("notes") or []):
            bits.append("note=" + n)
        out.append(" · ".join(b for b in bits if b))
    return "\n".join(out)


@app.websocket("/ws/interview")
async def interview_ws(ws: WebSocket):
    await ws.accept()
    session: Session | None = None
    uid: str | None = None
    started_at = time.monotonic()
    persisted = False
    _email = ""
    quota_day = _quota_day()   # server IST day → deterministic reset at 11:59pm (client day ignored)

    async def _persist_session():
        """One combined LLM pass at session end → memory + courage badges."""
        nonlocal persisted
        if persisted or session is None or uid is None or not db.db_enabled:
            return
        if session.mode == "learning":
            return
        persisted = True
        # No real turns = nothing to remember/reward (prevents 0-turn XP/streak farming).
        if session.turns <= 0:
            return
        try:
            mem = await session.summarize_and_extract()
            if mem:
                await db.add_conversation(uid, session.mode, mem.get("summary", ""))
                await db.merge_facts(uid, mem.get("facts", {}) or {}, mem.get("events", []) or [])
                await db.set_next_hook(uid, mem.get("next_hook", ""))   # S5 story continuity
            # Cross-mode thread continuity: keep the raw tail of THIS chat so the next
            # session (any mode) picks up where we left off, not with a cold greeting.
            try:
                tail = [{"role": m.get("role"), "content": m.get("content"), "mode": session.mode}
                        for m in session.transcript[-10:]]
                await db.save_recent_turns(uid, tail)
            except Exception as e:
                print(f"[memory] recent_turns save failed: {type(e).__name__}: {e}")
            secs = int(time.monotonic() - started_at)
            if session.mode == "daily":
                await db.record_practice(uid, seconds=secs, sentences=session.turns, xp=20)
            else:
                await db.bump_daily_stat(uid, sentences=session.turns, seconds=secs)
            # S6 — grow spoken vocabulary from what the learner actually said
            try:
                said = " ".join(m["content"] for m in session.transcript if m.get("role") == "user")
                if said:
                    await db.add_vocab(uid, said.split())
            except Exception:
                pass
            badges = []
            if mem.get("no_hindi"):       badges.append("courage_no_hindi")
            if mem.get("asked_question"): badges.append("courage_question")
            if secs >= 300:               badges.append("courage_5min")
            if session.mode in ("conversation", "daily"): badges.append("courage_first_convo")
            if badges:
                await db.award_badges(uid, badges)
        except Exception as e:
            print(f"[memory] persist failed: {type(e).__name__}: {e}")

    try:
        while True:
            data = json.loads(await ws.receive_text())
            mtype = data.get("type")

            if mtype == "start":
                claims = auth.read_session(data.get("token", "")) if auth.auth_enabled else None
                if auth.auth_enabled and not claims:
                    await _send(ws, type="auth_error", msg="Please sign in again")
                    break
                uid = claims["sub"] if claims else None
                # Access gate + BYOK key routing.
                _keys = data.get("keys")
                _email = claims.get("email", "") if claims else ""
                if uid and db.db_enabled:
                    try:
                        flags = await db.get_user_flags(uid)
                        if flags.get("status") == "blocked":
                            await _send(ws, type="error", msg="Your access has been paused. Please contact the admin.")
                            break
                    except Exception as e:
                        print(f"[gate] {type(e).__name__}: {e}")
                ok, effkeys, reason = await resolve_keys(_email, _keys, uid)
                if not ok:
                    await _send(ws, type="keys_required", msg="Add your own API keys in Settings to use DuSu.")
                    break
                set_active_keys(effkeys)
                # Load emotional memory so DuSu greets/talks like it knows them.
                facts_summary = ""; facts = {}
                mode = data.get("mode", "interview")
                if uid and db.db_enabled and mode in ("conversation", "interview", "daily"):
                    try:
                        facts = await db.get_memory(uid)
                        summaries = await db.recent_summaries(uid, 6)   # richer "story so far" across ALL modes
                        facts_summary = _facts_summary(facts, summaries)
                        # S3 — prepend the Relationship Journey tone so DuSu behaves per stage.
                        st = await db.relationship_stage(uid)
                        tone = _STAGE_TONE.get(st.get("stage", ""), "")
                        if tone:
                            facts_summary = (f"- Relationship stage: {st['stage']}. {tone}\n"
                                             + facts_summary)
                    except Exception as e:
                        print(f"[memory] load failed: {type(e).__name__}: {e}")
                started_at = time.monotonic()
                persisted = False
                # time-of-day from the client's local hour (0-23)
                hour = data.get("hour")
                quota_day = _quota_day()   # server IST day for the request quota (client `day` ignored)
                tod = ""
                if isinstance(hour, (int, float)):
                    tod = "morning" if hour < 12 else "afternoon" if hour < 17 else "evening"
                session = Session(
                    mode,
                    data.get("name", ""),
                    data.get("role", ""),
                    facts_summary=facts_summary,
                    mood=data.get("mood", ""),
                    profession=facts.get("profession", ""),
                    time_of_day=tod,
                    level=(facts.get("level") or ""),
                    daily_context=_daily_context_str(facts),
                )
                if session.mode == "daily":
                    # Resume: seed the recent turns the client kept in localStorage so
                    # DuSu picks up the thread instead of opening cold.
                    resume = data.get("resume") or []
                    if isinstance(resume, list) and resume:
                        for m in resume[-12:]:
                            r = m.get("role"); c = (m.get("content") or "").strip()
                            if r in ("user", "assistant") and c:
                                session.transcript.append({"role": r, "content": c})
                        session.turns = sum(1 for m in session.transcript if m["role"] == "user")
                    opening = await session.daily_turn("", first=True)
                    q = (opening.get("reply_hindi") or opening.get("next_question_hindi")
                         or "आज आपका दिन कैसा रहा?")
                    await _send(ws, type="daily_question", question=q)
                elif session.mode == "learning":
                    await _send(ws, type="ready")   # client greets in Hindi
                else:
                    await _send(ws, type="status", msg="starting")
                    # Companion Moment: if the user already answered DuSu's greeting out loud,
                    # seed it so DuSu responds to their topic instead of greeting again.
                    seed = (data.get("seed") or "").strip()
                    if seed and session.mode == "conversation":
                        session.add_user(seed)
                    greeting = await session.next_ai_turn()  # DuSu speaks first (or replies to seed)
                    await _send(ws, type="ai_text", text=greeting)

            elif mtype == "user_text":
                if session is None:
                    await _send(ws, type="error", msg="send start first")
                    continue
                text = (data.get("text") or "").strip()
                if not text:
                    continue
                # FREE-tier request quota (owner/unlimited/office bypass inside charge_request).
                # One request = one model-generating user turn, across all modes.
                q = await charge_request(_email, uid, quota_day)
                if not q["allowed"]:
                    await _send(ws, type="quota_exceeded", left=0, limit=q.get("limit"),
                                trial_over=q.get("trial_over", False))
                    continue
                if not q.get("unlimited") and q.get("limit") is not None:
                    # live header update: tell the client the new remaining count for today
                    await _send(ws, type="quota_update", left=q["left"], limit=q["limit"])
                if session.mode == "learning":
                    await _send(ws, type="status", msg="translating")
                    try:
                        english = await session.translate(text)
                    except Exception as e:
                        if _is_quota(e): await _send(ws, type="quota", msg="Your API keys hit their limit. Add or replace a key in Settings.")
                        else: await _send(ws, type="translate_error")
                        continue
                    await _send(ws, type="translation", hindi=text, text=english)
                    continue
                if session.mode == "daily":
                    await _send(ws, type="status", msg="thinking")
                    try:
                        d = await session.daily_turn(text)
                    except Exception as e:
                        if _is_quota(e): await _send(ws, type="quota", msg="Your API keys hit their limit. Add or replace a key in Settings.")
                        else: await _send(ws, type="translate_error")
                        continue
                    await _send(ws, type="daily_turn", hindi=text,
                                english=d.get("english", ""), reply=d.get("reply_hindi", ""),
                                tip=d.get("tip", ""), next_question=d.get("next_question_hindi", ""))
                    if uid and db.db_enabled:
                        try:
                            ctx = d.get("context", {}) or {}
                            if d.get("mood"): ctx["mood"] = d["mood"]
                            await db.save_daily_context(uid, ctx)
                        except Exception as e:
                            print(f"[daily] ctx save failed: {type(e).__name__}: {e}")
                    continue
                session.add_user(text)
                await _send(ws, type="status", msg="thinking")
                line = await session.next_ai_turn()
                await _send(ws, type="ai_text", text=line)
                if session.done:  # interview mode only
                    await _send(ws, type="interview_done")
                    await _send(ws, type="report", data=await session.build_report())
                    await _persist_session()
                elif session.capped:  # conversation hit its turn cap
                    await _send(ws, type="limit",
                                msg="You've reached the length limit for this chat — start a fresh conversation anytime.")

            elif mtype == "end":
                if session is None:
                    await _send(ws, type="error", msg="no session")
                    continue
                if session.mode == "interview":
                    await _send(ws, type="status", msg="scoring")
                    await _send(ws, type="report", data=await session.build_report())
                else:
                    await _send(ws, type="ended")
                await _persist_session()   # remember this conversation

            elif mtype == "close":
                break

    except WebSocketDisconnect:
        pass
    except Exception as e:  # keep the socket honest about failures
        try:
            if _is_quota(e):
                await _send(ws, type="quota", msg="Your API keys hit their limit. Add or replace a key in Settings.")
            else:
                await _send(ws, type="error", msg=str(e))
        except Exception:
            pass
    finally:
        await _persist_session()   # also persist if the socket just dropped


# SPA fallback — MUST be the last route. Serves the app shell for client-side routes
# (/daily-talk, /face-to-face, /interview, /learning-journey, /practice, /leaderboard, /more)
# so deep-links and page refreshes work. Specific API/asset routes above are matched first;
# paths that look like a file (contain a dot) get a real 404 instead of the HTML shell.
@app.get("/{full_path:path}", include_in_schema=False)
async def spa_fallback(full_path: str):
    if "." in full_path.rsplit("/", 1)[-1]:
        raise HTTPException(404, "Not found")
    return await index()
