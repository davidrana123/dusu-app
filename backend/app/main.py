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
from pydantic import BaseModel

from .config import settings
from .interview.engine import Session
from . import auth

app = FastAPI(title="DuSu")

_BACKEND = Path(__file__).resolve().parent.parent
_CLIENT_HTML = _BACKEND / "test_client.html"
_LOGO = _BACKEND / "logo.png"


@app.get("/logo.png")
async def logo():
    return FileResponse(_LOGO)


@app.get("/health")
async def health():
    return {"ok": True, "has_key": bool(settings.openrouter_api_key)}


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
    auth.upsert_user(claims)
    return {"token": auth.make_session(claims), "user": claims}


@app.get("/")
async def index():
    if not _CLIENT_HTML.exists():
        return HTMLResponse("<h1>DuSu</h1><p>test_client.html missing</p>")
    html = _CLIENT_HTML.read_text(encoding="utf-8")
    # Inject config the client needs (Google client id + whether auth is on).
    html = html.replace("__GOOGLE_CLIENT_ID__", settings.google_client_id)
    html = html.replace("__AUTH_ENABLED__", "true" if auth.auth_enabled else "false")
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
                session = Session(
                    data.get("mode", "interview"),
                    data.get("name", ""),
                    data.get("role", ""),
                )
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
                session.add_user(text)
                await _send(ws, type="status", msg="thinking")
                line = await session.next_ai_turn()
                await _send(ws, type="ai_text", text=line)
                if session.done:  # interview mode only
                    await _send(ws, type="interview_done")
                    await _send(ws, type="report", data=await session.build_report())

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
