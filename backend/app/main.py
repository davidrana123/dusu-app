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
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .config import settings
from .interview.engine import Session
from .interview.prompts import ASSESS_SYSTEM, LESSON_EVAL_SYSTEM, LEVEL_TEST_SYSTEM
from .providers import llm
from . import auth
from . import db

app = FastAPI(title="DuSu")


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


class AssessIn(BaseModel):
    token: str
    lang: str = "en"         # "hi" or "en" — language the learner took the test in
    goal: str = ""
    comfort: str = ""
    practice_time: str = ""
    intro: str = ""          # task 1 transcript
    repeat_target: str = ""  # task 2 target sentence
    repeat_said: str = ""    # task 2 what they said
    think_hindi: str = ""    # task 3 Hindi prompt
    think_said: str = ""     # task 3 their English attempt
    open_said: str = ""      # task 4 transcript


@app.get("/me")
async def me(token: str = ""):
    """Return the signed-in user's saved state (for reload / routing)."""
    claims = auth.read_session(token)
    if not claims:
        raise HTTPException(401, "Not signed in")
    if not db.db_enabled:
        return {"onboarded": None}
    try:
        return await db.login(claims)   # upsert row + return state (handles cached-token logins)
    except Exception as e:
        print(f"[me] db failed: {type(e).__name__}: {e}")
        return {"onboarded": False}


@app.post("/assessment")
async def assessment(inp: AssessIn):
    """Score the level assessment, save the profile, return it."""
    claims = auth.read_session(inp.token)
    if not claims:
        raise HTTPException(401, "Not signed in")
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
        result = await llm.assess(ASSESS_SYSTEM, payload)
    except Exception as e:
        print(f"[assess] llm failed: {type(e).__name__}: {e}")
        raise HTTPException(502, "Assessment scoring failed, please try again")

    data = {
        "goal": inp.goal, "comfort": inp.comfort, "practice_time": inp.practice_time,
        "level": result.get("level", "A1"),
        "scores": result.get("scores", {}),
        "weak_areas": result.get("weak_areas", []),
    }
    if db.db_enabled:
        try:
            await db.login(claims)   # ensure user+profile+progress rows exist (cached-token logins skip onGoogle)
            await db.save_assessment(claims["sub"], data, lang=inp.lang)
        except Exception as e:
            print(f"[assess] db save failed: {type(e).__name__}: {e}")
    return {"profile": data, "message": result.get("message", "")}


class LessonEvalIn(BaseModel):
    token: str
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
    if not auth.read_session(inp.token):
        raise HTTPException(401, "Not signed in")
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

    score = int(result.get("score", 0))
    out = {"score": score, "passed": result.get("passed", score >= 70),
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


@app.websocket("/ws/interview")
async def interview_ws(ws: WebSocket):
    await ws.accept()
    session: Session | None = None
    try:
        while True:
            data = json.loads(await ws.receive_text())
            mtype = data.get("type")

            if mtype == "start":
                if auth.auth_enabled and not auth.read_session(data.get("token", "")):
                    await _send(ws, type="auth_error", msg="Please sign in again")
                    break
                # Daily session cap is enforced client-side (localStorage) for the
                # no-DB preview stage. Turn caps below are still server-enforced.
                session = Session(
                    data.get("mode", "interview"),
                    data.get("name", ""),
                    data.get("role", ""),
                )
                if session.mode == "learning":
                    await _send(ws, type="ready")   # client greets in Hindi
                else:
                    await _send(ws, type="status", msg="starting")
                    greeting = await session.next_ai_turn()  # DuSu speaks first
                    await _send(ws, type="ai_text", text=greeting)

            elif mtype == "user_text":
                if session is None:
                    await _send(ws, type="error", msg="send start first")
                    continue
                text = (data.get("text") or "").strip()
                if not text:
                    continue
                if session.mode == "learning":
                    await _send(ws, type="status", msg="translating")
                    try:
                        english = await session.translate(text)
                    except Exception:
                        await _send(ws, type="translate_error")
                        continue
                    await _send(ws, type="translation", hindi=text, text=english)
                    continue
                session.add_user(text)
                await _send(ws, type="status", msg="thinking")
                line = await session.next_ai_turn()
                await _send(ws, type="ai_text", text=line)
                if session.done:  # interview mode only
                    await _send(ws, type="interview_done")
                    await _send(ws, type="report", data=await session.build_report())
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

            elif mtype == "close":
                break

    except WebSocketDisconnect:
        pass
    except Exception as e:  # keep the socket honest about failures
        try:
            await _send(ws, type="error", msg=str(e))
        except Exception:
            pass
