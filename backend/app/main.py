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
import time
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Header
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .config import settings
from .interview.engine import Session
from .interview.prompts import ASSESS_SYSTEM, LESSON_EVAL_SYSTEM, LEVEL_TEST_SYSTEM, LETTER_SYSTEM
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


class AboutIn(BaseModel):
    nickname: str = ""
    native_lang: str = ""
    profession: str = ""
    dream: str = ""
    interests: dict = {}


class AssessIn(BaseModel):
    token: str
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


@app.get("/me")
async def me(token: str = "", authorization: str | None = Header(None)):
    """Return the signed-in user's saved state (for reload / routing)."""
    claims = auth.read_session(_bearer(authorization, token))
    if not claims:
        raise HTTPException(401, "Not signed in")
    if not db.db_enabled:
        return {"onboarded": None}
    try:
        return await db.login(claims)   # upsert row + return state (handles cached-token logins)
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
    if summaries:
        lines.append("- Recent chats: " + " | ".join(summaries))
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
            secs = int(time.monotonic() - started_at)
            if session.mode == "daily":
                await db.record_practice(uid, seconds=secs, sentences=session.turns, xp=20)
            else:
                await db.bump_daily_stat(uid, sentences=session.turns, seconds=secs)
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
                # Load emotional memory so DuSu greets/talks like it knows them.
                facts_summary = ""; facts = {}
                mode = data.get("mode", "interview")
                if uid and db.db_enabled and mode in ("conversation", "interview", "daily"):
                    try:
                        facts = await db.get_memory(uid)
                        summaries = await db.recent_summaries(uid, 3)
                        facts_summary = _facts_summary(facts, summaries)
                    except Exception as e:
                        print(f"[memory] load failed: {type(e).__name__}: {e}")
                started_at = time.monotonic()
                persisted = False
                # time-of-day from the client's local hour (0-23)
                hour = data.get("hour")
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
                    opening = await session.daily_turn("", first=True)
                    await _send(ws, type="daily_question", question=opening.get("next_question_hindi", "Aaj aapka din kaisa raha?"))
                elif session.mode == "learning":
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
                if session.mode == "daily":
                    await _send(ws, type="status", msg="thinking")
                    try:
                        d = await session.daily_turn(text)
                    except Exception:
                        await _send(ws, type="translate_error")
                        continue
                    await _send(ws, type="daily_turn", hindi=text,
                                english=d.get("english", ""), praise=d.get("praise", ""),
                                next_question=d.get("next_question_hindi", ""))
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
            await _send(ws, type="error", msg=str(e))
        except Exception:
            pass
    finally:
        await _persist_session()   # also persist if the socket just dropped
