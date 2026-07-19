# AI Interview Coach — Backend (v0)

Voice mock-interview. **OpenRouter free models** run the adaptive interviewer
and the scoring pass (OpenAI-compatible API). Speech-to-text and text-to-speech
run **in the browser** via the Web Speech API (free, no key), so the server only
ever exchanges text. Total cost: **$0**.

This is plan step **Z**: one HR interview running end-to-end.

**Free-tier reality:** free models are shared and often rate-limited (HTTP 429),
so the provider walks a fallback list (`LLM_MODELS`) until one answers. Most free
models are reasoning models — the provider sends `reasoning.exclude` so their
chain-of-thought doesn't leak into the spoken answer. If turns feel slow or flaky,
add your own OpenRouter credits (raises rate limits) or swap in a paid model.

## Run

```bash
cd backend
python -m venv .venv
# Windows PowerShell:  .venv\Scripts\Activate.ps1
# Windows Git Bash:    source .venv/Scripts/activate
pip install -r requirements.txt

cp .env.example .env      # then put your real OPENROUTER_API_KEY in .env

uvicorn app.main:app --reload --port 8000
```

Open http://localhost:8000 in **Chrome or Edge** (Web Speech STT) → allow mic →
**Start interview** → talk, pause, listen, repeat → **End & get report**.

## How the call works

```
Start ─► AI greets (browser speaks) ─► you speak ─► browser STT ─► OpenRouter
        ▲                                                                │
        └──────────── browser TTS ◄──── next question (LLM) ◄────────────┘
End ─► LLM scores the full transcript ─► JSON report
```

Only text crosses the WebSocket. All audio stays in the browser.

## Layout

```
app/
  main.py                  FastAPI app + /ws/interview WebSocket (text-only)
  config.py                env-driven model list + OpenRouter key
  providers/
    base.py                LLMProvider interface (Protocol)
    openrouter_provider.py OpenRouter impl (turns + scoring, model fallback chain)
    __init__.py            wiring: swap a line to change model/vendor
  interview/
    prompts.py            HR persona + competency checklist + scorer JSON schema
    engine.py             per-session state, adaptive turn logic, report build
test_client.html          browser client (Web Speech STT + TTS, WebSocket)
```

## Notes / next (per plan)

- Web Speech STT/TTS is **Chrome/Edge only** and voice quality is basic. For
  production, swap to a paid STT/TTS later — the server stays text-only, so it's
  a browser-side change plus (optionally) proxying audio.
- Semantic end-of-turn instead of the browser's silence detection (E).
- Persist users/interviews/turns/scores to Postgres (L).
- Context summarization once interviews run long (P).
