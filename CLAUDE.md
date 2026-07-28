# DuSu — Project Guide (CLAUDE.md)

> **Read me first.** This is the single onboarding doc for a fresh Claude Code session (e.g. after moving the repo to another laptop). It explains the whole product, architecture, backend, frontend, database, LLM, mobile apps, Cloudflare plan, and dev/deploy workflow. Repo: `git@github.com:davidrana123/dusu-app.git`. Live: <https://dusu-app-1.onrender.com>. Also note: run the backend from `backend/.venv`; secrets live in `backend/.env` (**never commit**); Render **auto-deploys on push to `main`**.

## Table of Contents

1. [Product Overview](#1-product-overview)
2. [Architecture & Repo Layout](#2-architecture--repo-layout)
3. [Backend API (`backend/app/main.py`)](#3-backend-api-backendappmainpy)
4. [Database (backend/app/db.py)](#4-database-backendappdbpy)
5. [LLM Brain, Providers & Prompts](#5-llm-brain-providers--prompts)
6. [Frontend — Shell, Auth & Routing (backend/test_client.html)](#6-frontend--shell-auth--routing-backendtest_clienthtml)
7. [Frontend — Flows & Screens (backend/test_client.html)](#7-frontend--flows--screens-backendtest_clienthtml)
8. [Mobile Apps, Cloudflare, Deploy & Dev/Ops](#8-mobile-apps-cloudflare-deploy--devops)

---

## 1. Product Overview

### What DuSu is

**DuSu** is a **voice-first AI English-speaking coach** — tagline **"Speak with Confidence."** The user talks out loud; DuSu listens (browser speech-to-text), thinks (an LLM), and replies with a spoken voice (browser text-to-speech). It is deliberately positioned as a **companion, not a lesson app** — a warm mentor who remembers you, notices your mood, and holds ONE ongoing relationship across all practice modes. There are no grammar drills or flashcards; the product trains the thing people actually freeze on: *speaking to another human under pressure*.

The app ships as a **single-file web app** (`backend/test_client.html`, ~4,200 lines of vanilla HTML/JS/CSS — no build step) served by a **FastAPI** backend (`backend/app/`). Speech never leaves the browser; the WebSocket wire carries **text only**. It is installable as a **PWA** (`manifest.webmanifest` + `sw.js`) and wrapped as an Android **TWA/APK** (`android-twa/`, older `android-launcher/`; shipped artifacts `DuSu-app.apk`, `DuSu.apk` at repo root).

- Live URL referenced throughout the code: `https://dusu-app-1.onrender.com` (Render). Planned custom domain: `dusu.ranabrothers.online` (Cloudflare, not yet cut over).
- Cost model: **$0 running cost** — free LLM tiers + free browser speech.

### Target users

Indian, **mobile-first, budget-Android** learners who *know* some English but freeze when they must speak it — freshers/students prepping for **job interviews and campus placements**, non-metro/non-native speakers wanting low-pressure practice, and anyone building **daily speaking confidence**. Primary wedge: **India — freshers + placement season.** The icon/brand brief explicitly targets "budget Android, aspirational (job / interview / daily confidence)."

### The companion / emotional angle

This is the product's core differentiator, implemented in real code (not just planned):

- **Persistent emotional memory** — a per-user JSONB `memory.facts` doc stores nickname, profession, dream, interests, `facts_learned`, `moments` (time-boxed life events with an emotion, 2–7 day shelf life via `_prune_moments`), `achievements`, `energy_today`, `next_hook` (a promise to continue next time), `daily_context`, and `recent_turns` (raw tail of the last chat for **cross-mode continuity**).
- **Relationship Journey (internal, never shown)** — `relationship_stage()` promotes the user through 6 stages based on days + session count: **Guest → Friend → Practice Partner → Coach → Mentor → Companion** (`_REL_STAGES`). Each stage injects a different tone into DuSu's system prompt (`_STAGE_TONE` in `main.py`).
- **Companion Moment** — on Start Speaking, DuSu speaks *first* from memory. `POST /greeting` generates a warm **Hinglish** greeting (Devanagari for Hindi words so TTS pronounces them naturally) via `GREETING_SYSTEM`.
- **Weekly letter** — `POST /letter` generates a personal mentor note at most once every 7 days (needs xp ≥ 20), via `LETTER_SYSTEM`.
- Session end runs ONE combined LLM pass (`summarize_and_extract` → `SESSION_MEMORY_SYSTEM`) that writes a summary, merges facts/events, sets the next hook, saves recent turns, records practice stats, and awards **courage badges**.

### The modes

All four speaking modes run over the single WebSocket `/ws/interview`; `mode` is set in the `start` message. Modes live in `interview/engine.py` (`MODES = ("interview", "conversation", "learning", "daily")`) and `test_client.html`.

| Mode (code name) | UI name | Language | What it does | Ends? / Report |
|---|---|---|---|---|
| `conversation` | **Talk** / Confidence Talk / Start Speaking | English | Free, warm English chat that never ends; follows the user's interests, gently offers new topics if they go quiet. `conversation_system` prompt. | Soft cap at `conversation_max_turns` = 40 (`capped` → gentle wrap-up) |
| `interview` | **Interview** / Interview Prep | English | Adaptive mock HR interview; covers competencies (`self_introduction, role_motivation, project_depth, communication, strengths_weakness`), self-ends with `INTERVIEW_COMPLETE:` marker (~6–8 turns), hard cap `interview_max_turns` = 15. `interviewer_system` prompt. | **Scored report** via `SCORER_SYSTEM`: overall + grammar/fluency/confidence/communication/vocabulary/professionalism, filler words, strengths, fixes, and a rewritten "better_answer" |
| `learning` | **Learn** | Hindi/Hinglish → English | User says a Hindi/Hinglish sentence; DuSu returns the natural spoken-English translation (`TRANSLATE_SYSTEM`). Practice translating on demand, no persona. | No report; not persisted to memory |
| `daily` | **Daily Talk** | Hindi-first (Latin-script Hinglish reply) | Hindi-first "close friend" day chat. One JSON call (`DAILY_TURN_SYSTEM`) returns: `english` (clean translation of what they said), `reply_hindi` (warm friend reply), `next_question_hindi`, a tiny `tip`, sensed `mood`, and `context` (plans/weather/events). Resumes from `dusu_daily_resume` localStorage. | No report; records practice (+20 xp), saves daily context |

### The dynamic level test (onboarding assessment)

First-time users (server `onboarded == false`) are routed into a **dynamic, model-generated level check** — not a fixed quiz:

1. `POST /leveltest/gen` — the LLM freshly generates the test items each time (`repeat` sentence, `think_hindi` prompt, `open` question). This doubles as a **key verification** step (it fails if the user's keys don't work).
2. Four spoken tasks are transcribed in-browser: **Task 1** self-intro, **Task 2** repeat-after-me (listening/pronunciation), **Task 3** Hindi→English (thinking), **Task 4** open question (confidence/vocab), plus 3 MCQs (goal / comfort / practice_time).
3. `POST /assessment` scores 6 skills 0–100 (confidence, pronunciation, listening, vocabulary, grammar, thinking) and assigns a **CEFR level A0–B2** (`ASSESS_SYSTEM`). Result seeds the profile + the 7-level roadmap. Message can be returned in Hindi (`lang="hi"`, Latin script).

Deterministic post-login gate (`routeAfterLogin`): **keys → test → home**.

There is also a **7-level curriculum** ("worlds") with per-level lessons and a boss/Level Test that gates level-up (`POST /level/test/submit`, pass ≥ 70 via `LEVEL_TEST_SYSTEM`; individual lessons via `/lesson/evaluate` + `/lesson/complete`). Worlds (`_WORLD_NAMES` / client `WORLD_NAMES`): **The Village → The Street → The City → The Workplace → The Interview Hall → The Boardroom → The Global Stage**. Levels: Thinking in English, Simple Speaking, Daily Conversation, Confidence, Interview, Professional English, Fluency (`CURRICULUM` in the client; `LEVEL_LESSON_COUNTS`/`MAX_LEVEL=7`/`XP_PER_LESSON=20` on the server). Gamification: xp, coins, streak_days, daily_goal, and badges (`BADGE_LABELS`: first_lesson, first_converse, streak_7, sentences_100, level_up, and courage_* badges).

### BYOK / Office vs Personal, and roles

DuSu runs on shared free LLM quota, so there is a **Bring-Your-Own-Keys** system to stop the shared quota from being drained:

- **Personal mode** — uses OUR default key chain (from `.env`).
- **Office / BYOK mode** — the user supplies their own free API keys (Gemini / Groq / OpenRouter / GitHub), stored in browser localStorage (`dusu_office_keys`) and routed per-request via `set_active_keys()` (contextvar-isolated per connection). **Minimum 2 verified keys** to start (`hasOwnKeys()` → `keyCount() >= 2 && keysVerified()`). Keys are tested with a tiny live call at `POST /keys/verify`.
- **Global switch** — owner-controlled `require_own_keys` setting (default ON). When ON, any non-free user MUST BYOK before the test or any talk (`resolve_keys()` → HTTP 402 `keys_required`).

**Roles** (`role_for()` in `main.py`):

| Role | Who | Access |
|---|---|---|
| `owner` | `david123rana@gmail.com` (hard-coded `OWNER_EMAILS`) | Full admin + unlimited default-key use |
| `unlimited` | `shuhanisuhana037@gmail.com` (`UNLIMITED_EMAILS`) | Unlimited default-key use |
| `user` (default) | Everyone else | Must BYOK when `require_own_keys` is ON |
| **free-access** | Any email the owner adds to the "Office/free" allowlist (`office_add`, e.g. "Surendri") | May use OUR default keys even in require-own-keys mode |

Owner-only admin endpoints: `/admin/overview`, `/admin/settings` (flip the switch), `/admin/action` (approve/block/unblock/delete), `/admin/office` (add/remove free-access email), `/admin/wipe` (reset all test users except owner/unlimited/free-access). Normal users choosing Office go to `pending` (needs owner approval). User `status`: active / pending / blocked.

### Monetization notes

The plans frame DuSu as a **premium confidence product** ("Calm × Duolingo × a luxury concierge"), selling the *outcome* (a job / interview readiness), not grammar. Principle: **start free, feel premium**; zero-friction entry. Current stack is intentionally **$0**; the roadmap (`AI-Interview-Coach-Plan.md`, `DUSU.md`) lists future paths: paid model swap for quality, saved history, company-specific interview packs, streaks/progress, video mode, and **institute/college dashboards (B2B2C)**. No payment code exists yet; the BYOK/Office split is the current cost-control mechanism. Killer metric per the plan: **turn latency < 800 ms** (hard ceiling 1.2 s).

### Tech stack (as shipped)

| Layer | Choice | Where |
|---|---|---|
| Frontend | Single HTML file, vanilla JS/CSS, PWA + Android TWA | `backend/test_client.html`, `manifest.webmanifest`, `sw.js`, `android-twa/` |
| Backend | FastAPI + one WebSocket `/ws/interview` | `backend/app/main.py` (~1,045 lines) |
| Speech | Browser **Web Speech API** (STT) + **speechSynthesis** (TTS) — Chrome/Edge | in `test_client.html` |
| LLM | Multi-provider OpenAI-compatible fallback chain: **gemini → groq → openrouter → github**, with per-provider cooldowns | `config.py`, `providers/openrouter_provider.py` (`_complete`) |
| Auth | Google Sign-In → HMAC-signed 30-day stateless session token | `auth.py` |
| DB | Neon Postgres via SQLAlchemy 2.0 async + asyncpg; **graceful degrade** if `DATABASE_URL` empty (`db_enabled`) | `db.py` (~1,199 lines) |
| Hosting | Render (live) + Neon; Cloudflare/local-first planned | `Procfile`, `DEPLOY.md` |

**DB tables** (`db.py`): `users` (id=Google sub, email, name, picture, status, mode), `profiles` (onboarded, goal, comfort, practice_time, CEFR level, scores JSONB, weak_areas), `progress` (xp, coins, streak_days, sessions_today, daily_goal, badges, journey JSONB), `memory` (single JSONB `facts` doc — the emotional layer), `conversations` (one summary row per finished session), plus a key/value `settings` table.

**Key env vars** (`config.py` / `.env.example`): `OPENROUTER_API_KEY`, `GEMINI_API_KEY`, `GROQ_API_KEY`, `GITHUB_TOKEN`, `GOOGLE_CLIENT_ID`, `SESSION_SECRET`, `DATABASE_URL`, `ANDROID_TWA_PACKAGE` (default `com.dusu.app`), `ANDROID_CERT_SHA256`, `HOST`, `PORT`, plus limits `MAX_SESSIONS_PER_DAY` (20), `CONVERSATION_MAX_TURNS` (40), `INTERVIEW_MAX_TURNS` (15).

**WebSocket protocol** — client→server: `start` (mode, token, keys, name, role, mood, hour, seed, resume), `user_text`, `end`, `close`. Server→client: `status`, `ai_text`, `daily_question`, `daily_turn`, `translation`, `ready`, `interview_done`, `report`, `limit`, `quota`, `keys_required`, `auth_error`, `error`, `ended`.

**localStorage keys** (client): `dusu_token`, `dusu_user`, `dusu_state`, `dusu_onboarded`, `dusu_usemode` (personal|office), `dusu_office_keys`, `dusu_keys_ok`, `dusu_voice`, `dusu_daily_resume`, `dusu_letter`, `dusu_think`, `dusu_usage`.

### The `.md` files at repo root (what each is)

> These are planning/spec docs. Several predate the shipped code — the sections above reflect the **code as it actually is now**; the docs are noted where they diverge.

| File | What it is | Current vs code |
|---|---|---|
| `DUSU.md` | Living product overview — vision, modes, brand, $0 stack | Mostly accurate, but lists only 2 live modes; code now has **4** (adds Learn + Daily Talk) |
| `DUSU-JOURNEY.md` | Plan for turning DuSu into a coach with DB + assessment + 7-level journey + gamification | Largely **shipped** (Neon, assessment, journey, badges) |
| `DUSU_FEATURES.md` | Complete feature map: 11 screens, every feature → screen → frontend/backend/data. Best single "where things live" doc | Closely matches code (dated 2026-07-21) |
| `DUSU_EXPERIENCE.md` | "S11 — The Living Conversation" flagship spec for the Start-Speaking / Companion Moment; defines premium Hinglish (~55/45) | Reflects the shipped `/greeting` + Companion Moment |
| `DUSU_COMPANION_SYSTEM.md` | The emotional retention/relationship system — Emotion Ladder, relationship stages, moments, the "One Law" | Core ideas (stages, moments, memory) are **implemented** in `db.py`/`main.py` |
| `DUSU_HOME_UI.md` | Mobile-first Home UI label map — one worded button ("Start Speaking"), "More ▾" reveal, icons | Matches the shipped home |
| `BRAND-UI-PLAN.md` | Brand + premium UI system: positioning, palette (navy + gold), type (Cormorant Garamond + Inter), logo rules | Design source of truth |
| `DUSU_BYOK_PLAN.md` | Office vs Personal BYOK plan (marked "PLAN ONLY") | Now **shipped** — BYOK, `/keys/verify`, `require_own_keys`, 2-key minimum all exist |
| `DUSU_ICON_BRIEF.md` | App-icon/logo brief — the "D-mark" (face + speech-bubble + sound-waves), gold-on-navy | Design brief |
| `DUSU_LOCAL_CLOUDFLARE_PLAN.md` | Plan to run local-first via Cloudflare with Render/Neon fallback; domain `dusu.ranabrothers.online` | **Not built** except PWA/TWA items; Render+Neon is current |
| `AI-Interview-Coach-Plan.md` | Original A→Z go-to-market + roadmap (the "confidence-for-interviews" thesis, latency metric) | Foundational/historical |
| `VOICE-AVATAR-PLAN.md` | Plan to move TTS server-side (neural voice + lip-synced anime avatar) | **Not built** — TTS is still browser `speechSynthesis` |
| `DEPLOY.md` | Free-deploy guide — why Render (WebSockets, always-on, HTTPS), $0 host comparison | Deployment reference |
| `backend/README.md` | Backend v0 run/setup docs (interview MVP era) | Setup accurate; describes pre-DB single-interview state |

Note: the `backend/README.md` and some plans still describe the earlier "interview-only, OpenRouter-only, no-DB" MVP; the code has since grown to 4 modes, a 4-provider chain, Neon persistence, the companion/memory system, BYOK, roles/admin, the 7-level journey, and PWA/TWA packaging.

---

## 2. Architecture & Repo Layout

DuSu is a **$0-stack, browser-first spoken-English coach**. All speech (STT + TTS) happens in the user's browser via the Web Speech API; the server is text-only and stateless-capable. One FastAPI process serves both the single-file HTML frontend and the WebSocket/HTTP API, backed by a free LLM fallback chain and (optionally) Neon Postgres.

### Component diagram

```
┌──────────────────────────────────────────────────────────────────────────┐
│  BROWSER (Chrome/Edge only — Web Speech API)                               │
│                                                                            │
│   mic ─► SpeechRecognition (STT)  ─┐          ┌─► SpeechSynthesis (TTS) ─► speaker
│                                    │  text     │   (window.speechSynthesis)│
│   backend/test_client.html  ◄──────┴───────────┘                           │
│   (ONE 4135-line file: HTML+CSS+JS; all screens, all state)                │
│   • Google Identity Services (GIS) sign-in widget                          │
│   • localStorage: dusu_token, dusu_user, dusu_state, dusu_onboarded, …     │
└───────────────┬───────────────────────────────┬───────────────────────────┘
      WSS text-only │  /ws/interview     HTTPS JSON │ /auth,/me,/assessment,/lesson,…
                    ▼                               ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  FastAPI  (backend/app/main.py)  — uvicorn, served on Render / local PC    │
│  • WebSocket /ws/interview → interview/engine.py (Session per socket)      │
│  • HTTP endpoints (auth, home, roadmap, admin, BYOK keys)                  │
│  • auth.py  (Google ID-token verify + HMAC session tokens, no DB needed)   │
│  • config.py Settings → LLM provider chain                                 │
└───────────────┬───────────────────────────────┬───────────────────────────┘
                ▼                                 ▼
┌───────────────────────────────┐   ┌────────────────────────────────────────┐
│ FREE LLM CHAIN (OpenAI-compat) │   │ Neon Postgres (SQLAlchemy 2.0 async /   │
│ providers/openrouter_provider  │   │ asyncpg)  — backend/app/db.py           │
│ tried in order, auto-failover: │   │ Tables: users, profiles, progress,      │
│  1 gemini  2 groq              │   │ memory(JSONB), conversations,            │
│  3 openrouter  4 github        │   │ office_emails, settings                  │
│ (per-provider cooldown on 429) │   │ EMPTY DATABASE_URL ⇒ app still runs      │
│ BYOK: per-request key override │   │ fully, just stateless (db_enabled=False) │
└───────────────────────────────┘   └────────────────────────────────────────┘
```

Optional edge layer: a **Cloudflare Worker** (`cloudflare/worker.js`) fronts one stable hostname (`dusu.ranabrothers.online`) and routes to the local PC (via cloudflared tunnel) when healthy, else to Render — both share the same Neon DB so failover never splits data.

### The text-only WebSocket protocol (`/ws/interview`)

The browser does all audio. Only **text JSON frames** cross the wire — the LLM is the brain, never the ears/voice. One `Session` object (`interview/engine.py`) lives per socket and holds the full transcript in memory. Four modes multiplex over the same socket: `interview`, `conversation`, `learning`, `daily`.

**Client → server**

| Frame | Fields | Notes |
|---|---|---|
| `start` | `mode`, `name`, `role`, `token`, `mood`, `seed`, `keys`, `hour`, `resume` | Opens a session. `keys` = BYOK dict `{gemini,groq,openrouter,github}`. `seed` = user's spoken reply to the Companion greeting (conversation). `resume` = last localStorage turns (daily). `hour` (0–23) → time-of-day. |
| `user_text` | `text` | One finished spoken turn (already transcribed by browser STT). |
| `end` | — | Finish: interview → report; others → `ended`. Also fires `_persist_session()`. |
| `close` | — | Break the loop. |

**Server → client**

| Frame | Fields | Meaning |
|---|---|---|
| `status` | `msg` | e.g. `"starting"`, `"thinking"`, `"scoring"`, `"translating"`. |
| `ai_text` | `text` | DuSu's spoken line (interview/conversation); browser TTS speaks it. |
| `ready` | — | Learning mode ready (client greets in Hindi). |
| `translation` | `hindi`, `text` | Learning mode: Hindi input → English. |
| `translate_error` | — | Learning/daily failure (non-quota). |
| `daily_question` | `question` | Daily mode opener (Hindi/Hinglish). |
| `daily_turn` | `hindi`, `english`, `reply`, `tip`, `next_question` | Daily mode reply bundle. |
| `interview_done` | — | Interviewer wrapped up (`INTERVIEW_COMPLETE:` marker or turn cap). |
| `report` | `data` | Scored interview JSON (rubric in `SCORER_SYSTEM`). |
| `ended` | — | Non-interview session ended. |
| `limit` | `msg` | Conversation hit `conversation_max_turns` (40). |
| `quota` | `msg` | All keys hit their rate limit (429/402/etc.). |
| `keys_required` | `msg` | BYOK required but none supplied → must add keys in Settings. |
| `auth_error` | `msg` | Session invalid → client logs out. |
| `error` | `msg` | Generic failure. |

WS URL is derived client-side: `(https→wss)://<host>/ws/interview`. HTTP endpoints exist for everything non-conversational (auth, onboarding assessment, roadmap lessons/tests, home cards, admin, BYOK key verification) — see the `@app.get/post` handlers in `main.py`.

### Repo directory tree

Root is a git repo (`main` branch). Build artifacts, `.venv`, and `.env` are git-ignored (`DuSu.apk`, `**/.env`, `**/.venv/`, `__pycache__`, `backend/users.db`).

```
c:\Personal Work\English Specking\
├── backend/                         THE APP — FastAPI server + PWA frontend + assets
│   ├── app/
│   │   ├── main.py                  FastAPI app: all HTTP endpoints + /ws/interview WS; role/access
│   │   │                            gating (OWNER_EMAILS, UNLIMITED_EMAILS), BYOK key routing,
│   │   │                            assetlinks.json, config injection into index HTML
│   │   ├── config.py                pydantic Settings from .env; providers()/providers_from() build the
│   │   │                            4-provider LLM chain (gemini→groq→openrouter→github); usage caps
│   │   ├── auth.py                  Google ID-token verify + HMAC-signed stateless session tokens (30-day)
│   │   ├── db.py                    Neon Postgres (SQLAlchemy 2.0 async). Tables: users, profiles,
│   │   │                            progress, memory(JSONB), conversations, office_emails, settings.
│   │   │                            Roadmap logic (7 levels), XP/streak/badges, emotional memory,
│   │   │                            leaderboard, relationship stages, admin ops. No-op if no DATABASE_URL
│   │   ├── interview/
│   │   │   ├── engine.py            Session class: per-socket transcript + turn logic for all 4 modes;
│   │   │   │                        interview self-end (INTERVIEW_COMPLETE:), turn caps, daily_turn(),
│   │   │   │                        summarize_and_extract() (end-of-session memory)
│   │   │   └── prompts.py           All system prompts + personas: DUSU_PERSONA, interviewer/conversation,
│   │   │                            SCORER, ASSESS, DAILY_TURN, GREETING, LETTER, TRANSLATE, LEVEL_TEST,
│   │   │                            LESSON_EVAL, SESSION_MEMORY; COMPETENCIES list
│   │   ├── providers/
│   │   │   ├── base.py              LLMProvider Protocol (next_question / score) — vendor-agnostic
│   │   │   ├── openrouter_provider.py  OpenAI-client impl driving ALL providers; _complete() walks the
│   │   │   │                        chain+models with cooldown; set_active_keys() (BYOK via contextvar);
│   │   │   │                        _extract_json() for messy LLM JSON
│   │   │   └── __init__.py          Wiring: `llm = OpenRouterLLM()`
│   │   └── __init__.py
│   ├── test_client.html             ENTIRE FRONTEND — one 4135-line file (HTML+CSS+JS). All screens:
│   │                                onboarding, level test, home/companion, conversation, daily talk,
│   │                                learning, 7-level roadmap CURRICULUM, leaderboard, settings, admin.
│   │                                Web Speech STT/TTS, GIS login. Placeholders __GOOGLE_CLIENT_ID__,
│   │                                __AUTH_ENABLED__, __MAX_SESSIONS__ injected at GET /
│   ├── manifest.webmanifest         PWA manifest (name DuSu, standalone, #070a14, /logo.png icons)
│   ├── sw.js                        Service worker (cache "dusu-v5"); network-first navigations,
│   │                                never caches /ws,/auth,/me,/lesson,/level,/assessment,/admin,/keys,…
│   ├── logo.png                     App icon / PWA icon (served at /logo.png)
│   ├── assets/assistant/            8 anime character PNG frames (idle, blink, happy, listening,
│   │                                thinking, talk_01-03) served at /assets/… (mostly unused now)
│   ├── requirements.txt             fastapi 0.115.6, uvicorn, openai 1.59.6, pydantic 2, sqlalchemy 2,
│   │                                asyncpg, google-auth, greenlet
│   ├── runtime.txt                  python-3.12.7 (Render)
│   ├── Procfile                     `web: uvicorn app.main:app --host 0.0.0.0 --port $PORT`
│   ├── .env                         REAL secrets (git-ignored): GEMINI/GROQ/OPENROUTER/GITHUB keys,
│   │                                GOOGLE_CLIENT_ID, SESSION_SECRET, DATABASE_URL (Neon), HOST, PORT
│   ├── .env.example                 Template (note: mentions older single-OpenRouter setup — code truth
│   │                                is config.py's 4-provider chain)
│   └── README.md                    Backend run instructions + call-flow diagram (v0-era)
│
├── android-launcher/                Android app #1 (pkg com.dusu.launcher): thin launcher that opens
│   │                                DuSu in the phone's REAL Chrome (external browser, so Web Speech works)
│   ├── app/src/main/AndroidManifest.xml, MainActivity.kt, Notifications.kt, BootReceiver.kt,
│   │   ReminderReceiver.kt          Offline gate + daily reminder notification + boot re-arm
│   ├── app/src/main/res/…           strings.xml (dusu_url = https://dusu-app-1.onrender.com), icons, layout
│   ├── build.gradle.kts, settings.gradle.kts, gradlew(.bat), gradle/…  Gradle build
│   └── README.md                    (build/ .gradle/ .idea/ present locally = git-ignored build output)
│
├── android-twa/                     Android app #2 (pkg com.dusu.app): Trusted Web Activity — runs DuSu
│   │                                full-screen INSIDE the app on Chrome's engine (Web Speech works, no
│   │                                address bar once assetlinks verified). Installs side-by-side with launcher
│   ├── app/src/main/AndroidManifest.xml   TWA + LauncherActivity, asset_statements, 4-hourly reminder
│   ├── app/src/main/java/com/dusu/app/MainActivity.kt  Offline check → TwaLauncher; crash-to-file screen
│   │   Notifications.kt, BootReceiver.kt, ReminderReceiver.kt
│   ├── app/src/main/res/…           strings.xml (launchUrl + hostName = dusu-app-1.onrender.com,
│   │                                asset_statements JSON), adaptive icons
│   ├── gen_icons.py, icon-master.png, play-icon-512.png   Icon generation source
│   ├── build.gradle.kts, settings.gradle.kts, gradlew…
│   └── README.md                    TWA build + assetlinks setup (needs ANDROID_CERT_SHA256 env on server)
│
├── cloudflare/                      Local-first edge failover
│   ├── worker.js                    Worker: route to PC_ORIGIN (pc.ranabrothers.online tunnel) if /health
│   │                                OK, else CLOUD_ORIGIN (Render); WS pass-through; 10s health cache
│   ├── wrangler.toml                Worker config: route dusu.ranabrothers.online/*, PC/CLOUD origin vars
│   └── README.md                    cloudflared tunnel + wrangler deploy steps
│
├── .github/workflows/build-apk.yml  CI: builds android-LAUNCHER debug APK (JDK17, SDK 34) on push,
│                                     uploads artifact (does NOT build the TWA module)
├── image/                           Two ChatGPT-generated brand mockup PNGs
│
├── DuSu-app.apk                     Built TWA APK (~3 MB, com.dusu.app) — committed
├── DuSu.apk                         Older launcher APK (~6 MB) — GIT-IGNORED (in .gitignore)
├── Logo.png                         Master brand logo (~1.3 MB, root copy)
│
├── *.md  (planning/spec docs — SOME ARE OLD PLANS; verify against code):
│   ├── AI-Interview-Coach-Plan.md   Original A→Z build plan (interview-app origin)
│   ├── DUSU.md                      Product one-pager ("Speak with confidence")
│   ├── DUSU-JOURNEY.md              Plan: translator/interview bot → personal AI coach with a journey
│   ├── DUSU_FEATURES.md             Complete feature map (feature → screen → frontend/backend/data)
│   ├── DUSU_COMPANION_SYSTEM.md     The 4-type memory + relationship-stage "companion" design (S1–S6)
│   ├── DUSU_EXPERIENCE.md           S11 "Living Conversation" final experience spec
│   ├── DUSU_HOME_UI.md              Mobile-first home UI map (one big "Start Speaking" button)
│   ├── DUSU_BYOK_PLAN.md            Bring-Your-Own-Token (Office vs Personal) plan — now implemented
│   ├── DUSU_LOCAL_CLOUDFLARE_PLAN.md  Local-first + Render fallback plan (matches cloudflare/)
│   ├── DUSU_ICON_BRIEF.md           Logo / app-icon design brief
│   ├── BRAND-UI-PLAN.md             Branding + premium UI design language
│   ├── VOICE-AVATAR-PLAN.md         Voice + animated-avatar upgrade plan
│   └── DEPLOY.md                    Free ($0) deployment plan (Render + PWA)
│
├── .gitignore                       Ignores .env, .venv, __pycache__, users.db, DuSu.apk
└── .claude/settings.local.json      Local Claude Code settings
```

### Key runtime facts (verified in code)

- **LLM provider chain order** (`config.py`): `gemini` → `groq` → `openrouter` → `github`, each with its own model fallback list; a provider hit with 429/quota is cooled down (90s, or 1800s for daily-quota errors). `.env` var names: `GEMINI_API_KEY`, `GROQ_API_KEY`, `OPENROUTER_API_KEY`, `GITHUB_TOKEN`.
- **Other env vars**: `GOOGLE_CLIENT_ID` (enables login), `SESSION_SECRET` (HMAC token signing — falls back to random per-process if left as `dev-change-me`), `DATABASE_URL` (Neon; empty ⇒ stateless), `HOST`, `PORT`; plus `ANDROID_TWA_PACKAGE` and `ANDROID_CERT_SHA256` (read by `main.py` for `/.well-known/assetlinks.json`). Usage caps `max_sessions_per_day=20`, `conversation_max_turns=40`, `interview_max_turns=15`.
- **Access model** (`main.py`): `OWNER_EMAILS = {david123rana@gmail.com}`, `UNLIMITED_EMAILS = {shuhanisuhana037@gmail.com}`; a DB-backed `office_emails` allowlist grants "free access" to the default keys; a global `require_own_keys` setting (owner-toggled) forces everyone else into BYOK.
- **Frontend localStorage keys**: `dusu_token`, `dusu_user`, `dusu_state`, `dusu_onboarded`, `dusu_usemode`, `dusu_office_keys`, `dusu_keys_ok`, `dusu_voice`, `dusu_daily_resume`, `dusu_letter`, `dusu_usage`, `dusu_think`.
- **Live origins**: Render app `https://dusu-app-1.onrender.com`; stable Cloudflare front door `https://dusu.ranabrothers.online`; PC tunnel `https://pc.ranabrothers.online`.

---

## 3. Backend API (`backend/app/main.py`)

The single FastAPI application. Text-only wire protocol — the browser does STT/TTS via the Web Speech API, so the server only ever exchanges text; Claude/LLM is the "brain". File header docstring (lines 1–17) documents the core WS shapes. App object: `app = FastAPI(title="DuSu")` (line 37).

Key imports/wiring:
- `from .config import settings` — provider chains, limits, Google client id, secrets (see `backend/app/config.py`).
- `from .interview.engine import Session` — the per-connection conversation state machine used by `/ws/interview`.
- `from .interview.prompts import ASSESS_SYSTEM, LESSON_EVAL_SYSTEM, LEVEL_TEST_SYSTEM, LETTER_SYSTEM, GREETING_SYSTEM` — system prompts.
- `from .providers import llm` — `llm.assess()`, `llm.next_question()`, `llm.generate()`.
- `from .providers.openrouter_provider import set_active_keys` — sets the effective key chain for the current request/connection (BYOK routing).
- `from . import auth` and `from . import db`.

Startup hook `@app.on_event("startup") _startup()` (lines 86–88) calls `await db.init_db()` (no-op when no `DATABASE_URL`).

### Roles & access gating (module-level, lines 39–83)

| Name | Kind | Definition / behavior |
|---|---|---|
| `OWNER_EMAILS` | `set` | `{"david123rana@gmail.com"}` — full admin + unlimited. |
| `UNLIMITED_EMAILS` | `set` | `{"shuhanisuhana037@gmail.com"}` — unlimited, no admin. |
| `role_for(email) -> str` | fn | Lowercases/strips; returns `"owner"`, `"unlimited"`, or `"user"`. |
| `free_access(email) -> bool` | async fn | May use OUR default keys? True for owner/unlimited, or if `db.office_has(email)` (owner-added free/Office email). Aliased as `office_allowed = free_access`. |
| `require_own_keys_on() -> bool` | async fn | Global owner switch; reads `db.get_setting("require_own_keys", "1")`; `"1"` → ON. Defaults True on any error. |
| `resolve_keys(email, keys) -> (ok, effective_keys_or_None, reason)` | async fn | The BYOK gate. If switch OFF **or** user is free → `(True, None, "")` (use default chain). Else if `keys` has any non-empty value → `(True, keys, "")` (use their keys only). Else `(False, None, "keys_required")`. |
| `_is_quota(e) -> bool` | fn | True if error string contains any of `429`, `quota`, `exhaust`, `rate limit`, `unavailable`, `insufficient`, `402`. Used to distinguish "keys hit limit" from real errors. |

`_bearer(header, token)` (lines 198–202): prefers `Authorization: Bearer <t>` header, else falls back to a `token` query/body value.

`_require_owner(token, authorization)` (lines 289–295): reads session, 401 if not signed in, 403 `"Owner only"` if `role_for != "owner"`.

`_send(ws, **payload)` (lines 746–747): `ws.send_text(json.dumps(payload))`.

### Authentication (`backend/app/auth.py`)

Google Sign-In + **stateless HMAC** session tokens; no server-side session store.
- `auth_enabled = bool(settings.google_client_id)`.
- `_SECRET = settings.session_secret`; if it's still the default `"dev-change-me"`, a random per-process secret is generated (warns to set `SESSION_SECRET` for stable sessions).
- `verify_google(credential)` — `google.oauth2.id_token.verify_oauth2_token` against `GOOGLE_CLIENT_ID`, `clock_skew_in_seconds=60`; returns `{sub, email, name, picture}`.
- `make_session(user, ttl=30*86400)` — 30-day token, payload `{sub, email, name, exp}`, encoded `base64url(payload).base64url(HMAC-SHA256(secret, body))`, joined by `.`.
- `read_session(token)` — splits on `.`, verifies HMAC with `hmac.compare_digest`, checks `exp`; returns claims dict or `None`.

### Static / well-known routes

| Method | Path | Serves | Notes |
|---|---|---|---|
| GET | `/` | `backend/test_client.html` (`_CLIENT_HTML`) | Reads file, replaces placeholders `__GOOGLE_CLIENT_ID__` → `settings.google_client_id`, `__AUTH_ENABLED__` → `"true"/"false"`, `__MAX_SESSIONS__` → `settings.max_sessions_per_day`. Fallback stub HTML if file missing. |
| — (mount) | `/assets/*` | `backend/assets/` (`_ASSETS`, `StaticFiles`) | Directory created at import; holds the anime character PNG frames. |
| GET | `/logo.png` | `backend/logo.png` (`_LOGO`) | `FileResponse`. |
| GET | `/manifest.webmanifest` | `backend/manifest.webmanifest` (`_MANIFEST`) | media type `application/manifest+json`. |
| GET | `/sw.js` | `backend/sw.js` (`_SW`) | media type `application/javascript`; headers `Cache-Control: no-cache`, `Service-Worker-Allowed: /` (root scope). |
| GET | `/.well-known/assetlinks.json` | JSON | Digital Asset Links for the Android TWA. Reads env `ANDROID_CERT_SHA256` (comma/newline-separated SHA-256 fingerprints, upper-cased) and `ANDROID_TWA_PACKAGE` (`_TWA_PACKAGE`, default `"com.dusu.app"`). Returns one statement: `relation ["delegate_permission/common.handle_all_urls"]`, `target {namespace:"android_app", package_name, sha256_cert_fingerprints}`. Header `Cache-Control: public, max-age=3600`. |
| GET | `/health` | `{ok, has_key, providers}` | `providers = settings.providers()`; `has_key=bool(providers)`; `providers` = list of active provider names. |

Path constants (lines 90–97): `_BACKEND = <repo>/backend`, and the four static files + `_ASSETS` all live directly under `backend/`.

### HTTP endpoints

All request bodies are Pydantic models. Most write endpoints carry `token` in the body; read endpoints (`/me`, `/leaderboard`, admin GET) accept `token` query **or** `Authorization: Bearer` header via `_bearer`.

#### `POST /auth/google` — `GoogleIn{credential:str}`
Verifies Google ID token. 500 if `auth_enabled` false; 401 on verify failure. Returns `{token: <session>, user: <claims>}`. If DB enabled, calls `db.login(claims)` and adds `onboarded`, `profile`, `progress`.

#### `GET /me` — query `token` / Bearer
Signed-in user's full state for reload/routing. 401 if no session. Always injects `role` (`role_for`), `email`, `office_allowed` & `free_access` (both = `free_access(email)`), `require_own_keys` (`require_own_keys_on()`). If no DB → returns those flags with `onboarded: None`. With DB → `db.login(claims)` state; if `onboarded`, also builds `today` (`db.build_today`), `growth` (`db.build_growth`), `opening` (`db.build_opening`), `recommendations` (`db.build_recommendations`). On DB error returns `{onboarded: False}`.

#### `GET /leaderboard` — query `token` / Bearer
Top learners by all-time XP (private aliases) + caller's rank. 401 if no session. No DB → `{top:[], you:null}`. Else `db.leaderboard(claims["sub"])`.

#### `POST /keys/verify` — `KeysIn{token:str="", keys:dict={}}` (+ Bearer)
BYOK key tester. 401 if no session. For each `settings.providers_from(keys)` entry, makes a tiny `AsyncOpenAI` chat call ("Reply OK", `max_tokens=8`). Returns `{results: {<provider>: {ok:bool, error:str}}}`. Special error text for GitHub token missing `models` permission; distinguishes invalid key vs quota-exhausted (`ok=True` with a "quota exhausted" note).

#### `POST /assessment` — `AssessIn`
Scores the onboarding level assessment. Fields: `token`, `keys={}`, `lang="en"` (`"hi"`/`"en"`), `about: AboutIn|None`, `goal`, `comfort`, `practice_time`, `intro` (task 1), `repeat_target`/`repeat_said` (task 2), `think_hindi`/`think_said` (task 3), `open_said` (task 4). `AboutIn{nickname, native_lang, profession, dream, interests:dict}`.
Flow: 401 if no session → `resolve_keys` gate (402 `"keys_required"` if fails) → `set_active_keys(eff)` → build text payload (Hindi note appended if `lang=="hi"`) → `llm.assess(ASSESS_SYSTEM, payload)` (502 on failure). Persists via `db.login` + `db.save_assessment` (returns seeded `progress`) + `db.save_about` (adds `native_lang`, `intro_text`). Returns `{profile:{goal,comfort,practice_time,level,scores,weak_areas}, message, progress}`.

#### `POST /leveltest/gen` — `GenIn{token:str="", keys:dict={}}`
Dynamic level-check generator (also verifies the user's keys work). 401 if no session → `resolve_keys` (402 `"keys_required"`) → `set_active_keys(eff)`. Inline system prompt asks for fresh JSON `{repeat, think_hindi, open}` for a Hindi-L1 learner. `llm.assess(sys, "Generate a fresh level check now.")`. On quota → 429 `"quota"`; other errors → 502 `"gen_failed"`. Returns `{repeat, think_hindi, open}`.

#### `POST /checkin` — `CheckinIn{token, mood}`
401 if no session. No DB → `{ok:True}`. Else `db.save_checkin(sub, mood)` → `{ok:True, memory: facts}` (or `{ok:False}`).

#### `POST /greeting` — `TokenIn{token, keys={}}`
The "Companion Moment" Hinglish greeting from memory. `set_active_keys(inp.keys)` then 401 check. No DB → `{text:""}`. Builds payload from `db.build_companion_context` + `db.recent_summaries(uid,1)` (name, stage, days_together, identity, moments, achievements, energy_today, next_hook, world, last_session) → `llm.next_question(GREETING_SYSTEM, [...])`. Returns `{text}`.

#### `POST /futureme` — `FutureMeIn{token, text}`
401 if no session. No DB or empty text → `{ok:True}`. Else `db.save_future_me(sub, text)` → `{ok:True, memory: facts}` / `{ok:False}`.

#### `POST /letter` — `TokenIn{token, keys={}}`
This week's personal note from DuSu. `set_active_keys(inp.keys)` then 401. No DB → `{letter:None}`. Regenerates at most once per 7 days and only if `progress.xp >= 20`; otherwise returns cached `last_letter` with `fresh:False`. Builds prompt from memory/progress/`db.recent_summaries(sub,5)` → `llm.generate(LETTER_SYSTEM, prompt, max_tokens=350)` → `db.save_letter` → `{letter:{date,text}, fresh:True}`.

#### `POST /lesson/evaluate` — `LessonEvalIn{token, keys={}, lang="en", type="speak", prompt, target, said}`
Scores one spoken lesson answer, no DB write. `set_active_keys(keys)` then 401. `llm.assess(LESSON_EVAL_SYSTEM, payload)` (502 on failure). Returns the LLM's JSON directly.

#### `POST /lesson/complete` — `LessonDoneIn{token, level:int, lesson_id, lesson_type=""}`
401 if no session. No DB → `{progress:None, leveled_up:False, new_badges:[]}`. Else `db.login` + `db.complete_lesson(sub, level, lesson_id, lesson_type)` (updates journey/xp/streak/badges); 500 on failure.

#### `POST /level/test/submit` — `LevelTestIn{token, keys={}, level:int, lang="en", items:[LevelTestItem]}`
`LevelTestItem{prompt="", target="", said=""}`. Scores a whole Level Test in one call. `set_active_keys(keys)` then 401. `llm.assess(LEVEL_TEST_SYSTEM, payload)` (502 on failure). Robust score parsing (handles null/`"70%"`/`"eighty"`), clamps 0–100. Returns `{score, passed(score>=70), items, message}`; with DB adds `leveled_up`, `new_badges`, `progress` via `db.submit_level_test`.

#### `POST /mode` — `ModeIn{token, mode}` (`personal` | `office`)
401 if no session. Normal `user` choosing `office` → `status="pending"` (needs owner approval); owner/unlimited or `personal` → `"active"`. Persists `db.set_user_mode(sub, mode, status)` (mode coerced to `personal`/`office`). Returns `{mode, status, role}`.

#### Admin (owner only, all via `_require_owner`)

| Method | Path | Body | Behavior |
|---|---|---|---|
| GET | `/admin/overview` | query `token`/Bearer | Dashboard: `{you, role:"owner", db, users:[…(+role each)], counts:{total,active,pending,blocked,office}, office_emails, require_own_keys}`. Users from `db.admin_list_users`, office from `db.office_list`. |
| POST | `/admin/settings` | `SettingsIn{token="", require_own_keys:bool}` | Flips global switch → `db.set_setting("require_own_keys","1"/"0")`. Returns `{require_own_keys}`. |
| POST | `/admin/action` | `AdminActionIn{token="", target_id, action}` | `action`: `approve`/`unblock`→status `active`, `block`→`blocked`, `delete`→`db.delete_user`. 400 `"Database required"` if no DB, 400 `"Unknown action"` otherwise. |
| POST | `/admin/office` | `OfficeEmailIn{token="", email, action}` | `action` `add`→`db.office_add`, `remove`→`db.office_remove`; else 400. Returns `{ok, office_emails}`. |
| POST | `/admin/wipe` | `WipeIn{token=""}` | Testing reset: `db.admin_wipe_users(keep)` deleting everyone except `OWNER_EMAILS ∪ UNLIMITED_EMAILS ∪ db.office_list()`. Returns `{deleted:n, kept:[…]}`. 400 if no DB. |

### WebSocket `/ws/interview` (lines 830–1046)

`ws.accept()`; per-connection locals: `session: Session|None`, `uid`, `started_at` (monotonic), `persisted` flag. Reads JSON text frames in a loop; dispatches on `data["type"]`.

**Inbound message types**

| `type` | Fields | Handling |
|---|---|---|
| `start` | `token`, `keys`, `mode` (default `"interview"`; also `"conversation"`, `"daily"`, `"learning"`), `name`, `role`, `hour` (int 0–23, → `time_of_day` morning/afternoon/evening), `mood`, `resume` (list, daily only — replays up to last 12 turns into `session.transcript`), `seed` (conversation only — pre-answer the greeting) | Auth (if `auth_enabled` and no claims → `auth_error`, break). Blocked-user gate via `db.get_user_flags` (status `blocked` → `error`, break). `resolve_keys` gate (fail → `keys_required`, break) then `set_active_keys(effkeys)`. Loads emotional memory for conversation/interview/daily: `db.get_memory`, `db.recent_summaries(uid,6)`, `_facts_summary`, `db.relationship_stage` → prepends stage tone. Builds `Session(mode, name, role, facts_summary=, mood=, profession=, time_of_day=, level=, daily_context=)`. Then: `daily`→emits `daily_question`; `learning`→emits `ready`; else→emits `status "starting"` then DuSu's opening `ai_text`. |
| `user_text` | `text` | Requires a live session (else `error "send start first"`). `learning`→`status "translating"` then `translation`. `daily`→`status "thinking"` then `daily_turn` (+ `db.save_daily_context`). Else (conversation/interview)→`session.add_user`, `status "thinking"`, `ai_text`; if `session.done`→`interview_done`+`report`+persist; if `session.capped`→`limit`. |
| `end` | — | `interview`→`status "scoring"` + `report`; other modes→`ended`. Then `_persist_session()`. |
| `close` | — | Breaks the loop. |

**Outbound message types**

| `type` | Fields | Meaning |
|---|---|---|
| `ready` | — | Learning mode: client should greet in Hindi. |
| `status` | `msg` | Progress ping: `"starting"`, `"thinking"`, `"translating"`, `"scoring"`. |
| `ai_text` | `text` | DuSu's spoken line (interview/conversation); browser TTS speaks it. |
| `translation` | `hindi`, `text` | Learning mode: echo of their Hindi + the English translation. |
| `translate_error` | — | Learning/daily non-quota failure (present in code; not in header docstring). |
| `daily_question` | `question` | Daily Talk opening Hindi question. |
| `daily_turn` | `hindi`, `english`, `reply`, `tip`, `next_question` | Daily Talk turn result. |
| `report` | `data` | Interview scorecard from `session.build_report()`. |
| `interview_done` | — | Interviewer wrapped up (`session.done`). |
| `limit` | `msg` | Conversation hit its turn cap (`session.capped`). |
| `quota` | `msg` | User's keys hit their limit (`_is_quota` true). |
| `keys_required` | `msg` | BYOK gate failed at `start` — must add own keys. |
| `auth_error` | `msg` | Not signed in (auth enabled). |
| `error` | `msg` | Blocked access, missing session, or generic failure. |
| `ended` | — | Non-interview session ended via `end`. |

**`_persist_session()`** (lines 838–883): one combined LLM pass at session end. No-op if already persisted / no session / no uid / no DB / mode `learning`, or `session.turns <= 0` (prevents 0-turn XP farming). Calls `session.summarize_and_extract()` → `db.add_conversation`, `db.merge_facts`, `db.set_next_hook`; saves cross-mode tail via `db.save_recent_turns` (last 10 turns tagged with mode). Records practice: `daily`→`db.record_practice(seconds, sentences, xp=20)`, else `db.bump_daily_stat`. Grows vocab via `db.add_vocab`. Awards badges: `courage_no_hindi`, `courage_question`, `courage_5min` (>=300s), `courage_first_convo` (conversation/daily). Called on the `end` branch, the interview-done branch, and in `finally` (so a dropped socket still persists).

### Cross-mode memory injection

`_STAGE_TONE` (lines 751–758): dict mapping relationship stage → tone instruction (`Guest`, `Friend`, `Practice Partner`, `Coach`, `Mentor`, `Companion`); prepended to the persona at `start`.

`_facts_summary(facts, summaries)` (lines 761–811): builds the "what DuSu remembers" block injected into the session persona. Emits lines for `nickname`, `profession`, `dream`, `interests`, `facts_learned` (last 5), `events` (last 3), `relationship` traits, `moments` (last 4, with emotion), `achievements` (last 4), `energy_today.value`, `next_hook`, and `recent chats` (summaries). **Cross-mode continuity**: reads `facts["recent_turns"]` (each `{role, content, mode}`), renders the last 6 as "them:/you:" and labels the last mode (`daily`→"Daily Talk (Hindi)", `conversation`→"English Talk", `interview`→"Interview") into a "Where you left off last time… continue THIS thread, do NOT restart" instruction. Closes with a "show you remember; never invent memories" guard.

`_daily_context_str(facts)` (lines 814–827): compact recent-days context from `facts["daily_context"]` — each entry rendered as `date · mood=… · plans=… · weather=… · event=… · note=…`; passed to `Session(daily_context=…)`.

### Related config (`backend/app/config.py`)

`settings` (from `.env`, `pydantic-settings`). Env-backed fields: LLM keys `GEMINI_API_KEY`, `GROQ_API_KEY`, `OPENROUTER_API_KEY`, `GITHUB_TOKEN`; `GOOGLE_CLIENT_ID`, `SESSION_SECRET` (default `"dev-change-me"`); `DATABASE_URL` (empty = stateless); limits `MAX_SESSIONS_PER_DAY=20`, `CONVERSATION_MAX_TURNS=40`, `INTERVIEW_MAX_TURNS=15`; `HOST=0.0.0.0`, `PORT=8000`. `providers()` builds the default fallback chain (gemini → groq → openrouter → github, each with base_url/models/headers/extra); `providers_from(keys)` builds the same chain from BYOK keys `{gemini, groq, openrouter, github}`. OpenRouter headers reference `https://dusu-app-1.onrender.com`.

---

## 4. Database (backend/app/db.py)

The entire persistence layer lives in a single module: `backend/app/db.py`. It uses **SQLAlchemy 2.0 async** (declarative `Mapped[...]` models) against **Neon Postgres** via the `asyncpg` driver. The design principle is *graceful degradation*: if no database is configured the app still runs fully, just statelessly.

### 4.1 Connection & the `db_enabled` switch

| Symbol | Definition | Meaning |
|---|---|---|
| `db_enabled` | `bool(settings.database_url)` (line 63) | `True` only when the `DATABASE_URL` env var is non-empty. Empty locally ⇒ `db_enabled = False` ⇒ the app is **stateless** (no user rows, no memory, no progress persisted). |
| `settings.database_url` | Pydantic field `database_url: str = ""` in `backend/app/config.py` (line 24), loaded from `.env` env var **`DATABASE_URL`** | The Neon connection string. |
| `_engine` | `create_async_engine(...)` — only built when `db_enabled` (lines 64, 67-72); otherwise `None` | Async engine with `pool_pre_ping=True` and `connect_args={"ssl": True}` (Neon requires TLS). |
| `_Session` | `async_sessionmaker(_engine, expire_on_commit=False)` — `None` when DB disabled (lines 65, 73) | Session factory used by every public function via `async with _Session() as s:`. |

Every public function that touches the DB opens `async with _Session() as s:`. When `db_enabled` is `False`, `_Session` is `None`; the admin/office/settings helpers guard with `if not db_enabled: return <empty>` first, but the core user functions (`login`, `save_assessment`, etc.) assume the caller only invokes them when the DB is on — the router layer is responsible for that gate.

#### `_normalize_url(url)` (lines 50-60)

Neon hands out URLs like `postgresql://user:pass@host/db?sslmode=require&channel_binding=require`. asyncpg needs the `+asyncpg` driver and **rejects** those query params (SSL is supplied via `connect_args` instead). The function:

1. `postgres://` → `postgresql://`
2. `postgresql://` → `postgresql+asyncpg://`
3. Strips everything after `?` (drops `sslmode`, `channel_binding`, etc.)

```python
_normalize_url("postgres://u:p@h/db?sslmode=require")
# -> "postgresql+asyncpg://u:p@h/db"
```

`_now()` (line 76) returns timezone-aware UTC (`dt.datetime.now(dt.timezone.utc)`) and is the default for every timestamp column.

### 4.2 Roadmap / gamification constants (lines 24-30)

| Constant | Value | Purpose |
|---|---|---|
| `LEVEL_LESSON_COUNTS` | `{1:5, 2:5, 3:5, 4:5, 5:5, 6:5, 7:5}` | Lessons per level (mirrors the client CURRICULUM) so the server can detect level completion. |
| `MAX_LEVEL` | `7` | Top of the roadmap. |
| `XP_PER_LESSON` | `20` | XP awarded per first-time lesson completion. |
| `LEVELS_WITH_TEST` | `{1,2,3,4,5,6,7}` | Every level ends with a Boss/Level Test that gates level-up (so `complete_lesson` never auto-levels — `submit_level_test` does). |

Two helper mappers:
- `_start_level(cefr)` (33-35): `{"A0":1,"A1":1,"A2":2,"B1":3,"B2":4}`, default `1`.
- `_daily_goal(practice_time)` (38-47): `"30"→7`, `"20"→5`, `"10"→3`, else `2`.

### 4.3 Models — every table, every column

All models inherit `Base(DeclarativeBase)` (line 80). Primary keys on the per-user tables are the Google `sub` string (`user_id`), so there is one row per Google account per table.

#### `User` — table `users` (lines 84-93)

| Column | Type | Default / notes |
|---|---|---|
| `id` | `String(64)` **PK** | Google `"sub"` claim (falls back to email in `login`). |
| `email` | `String(255)` | `""` |
| `name` | `String(255)` | `""` |
| `picture` | `String(512)` | `""` |
| `created_at` | `DateTime(timezone=True)` | `_now` |
| `last_seen` | `DateTime(timezone=True)` | `_now` (bumped every `login`) |
| `status` | `String(16)` | `"active"` — one of `active` \| `pending` \| `blocked` |
| `mode` | `String(16)` | `"personal"` — one of `personal` \| `office` |

`status` and `mode` were added later; they are back-filled at boot by `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` (see `init_db`).

#### `Profile` — table `profiles` (lines 96-107)

| Column | Type | Default |
|---|---|---|
| `user_id` | `String` **PK**, `ForeignKey("users.id")` | — |
| `onboarded` | `Boolean` | `False` (drives first-run assessment) |
| `goal` | `String(64)` | `""` |
| `comfort` | `String(64)` | `""` |
| `practice_time` | `String(32)` | `""` |
| `level` | `String(8)` | `"A0"` (CEFR) |
| `scores` | `JSONB` | `dict` — skill scores 0-100 |
| `weak_areas` | `JSONB` | `list` |
| `assessed_at` | `DateTime(timezone=True)`, nullable | `None` |

#### `Progress` — table `progress` (lines 110-120)

| Column | Type | Default / notes |
|---|---|---|
| `user_id` | `String` **PK**, FK `users.id` | — |
| `xp` | `Integer`, **indexed** | `0` — leaderboard sort/rank |
| `coins` | `Integer` | `0` |
| `streak_days` | `Integer` | `0` |
| `last_active` | `Date`, nullable | `None` |
| `sessions_today` | `Integer` | `0` |
| `daily_goal` | `Integer` | `5` |
| `badges` | `JSONB` | `list` |
| `journey` | `JSONB` | `dict` |

`journey` is the roadmap doc: `{start_level, current_level, completed:{ "<level>":[lesson_ids] }, lang, sentences_spoken, test_scores:{ "<level>":{best, attempts, passed} }}`.

#### `Memory` — table `memory` (lines 123-128)

One JSONB doc per user — the "emotional layer."

| Column | Type | Default |
|---|---|---|
| `user_id` | `String` **PK**, FK `users.id` | — |
| `facts` | `JSONB` | `dict` |

**`facts` JSON keys actually written by the code** (the whole doc is a schemaless bag; keys below are all the ones the code reads/writes):

| Key | Shape | Written by |
|---|---|---|
| `nickname`, `native_lang`, `profession`, `dream` | strings | `save_about`, `merge_facts` |
| `interests` | dict (merged) | `save_about`, `merge_facts` |
| `facts_learned` | list of strings, dedup, capped `_MAX_FACTS`=40 | `merge_facts` |
| `events` | list of `{type, date, ...}`, capped 20 | `merge_facts` |
| `relationship` | dict (traits, never expire) | `merge_facts` |
| `moments` | list `{text, emotion, created, expires}`, TTL 7d (`_MOMENT_TTL_DAYS`), capped 40 (`_MAX_MOMENTS`) | `_add_moments` via `merge_facts` |
| `achievements` | list `{text, date}`, permanent, capped 60 (`_MAX_ACHIEVEMENTS`) | `_add_achievements` via `merge_facts` |
| `energy_today` | `{date, value}` | `save_checkin` |
| `checkins` | list `{date, mood, energy}`, capped 30 (`_MAX_CHECKINS`) | `save_checkin` |
| `next_hook` | string ≤200 | `set_next_hook`, cleared/consumed by openings |
| `daily_context` | list `{date, mood, plans, weather, events, notes}` — 48h sliding window (today+yesterday) | `save_daily_context` |
| `recent_turns` | list `{role, content≤400, mode}`, last 10 | `save_recent_turns` |
| `baseline` | `{intro_text, date}` | `save_about` |
| `future_me` | `{day1_text, latest_text, latest_date}` | `save_about`, `save_future_me` |
| `daily_stats` | `{ "<date>": {sentences, seconds, sessions, new_words} }`, last ~14d | `bump_daily_stat`, `add_vocab` |
| `total_sentences`, `total_seconds` | ints (lifetime) | `bump_daily_stat` |
| `longest_convo_sec` | int | `bump_daily_stat` |
| `vocab` | list of words, capped 500 (`_MAX_VOCAB`) | `add_vocab` |
| `vocab_total` | int | `add_vocab` |
| `last_confidence` | int (Growth baseline) | `build_growth` |
| `last_letter` | `{date, text}` | `save_letter` |

#### `Conversation` — table `conversations` (lines 131-139)

One row per finished session; an LLM summary DuSu recalls later.

| Column | Type | Default / notes |
|---|---|---|
| `id` | `Integer` **PK**, autoincrement | — |
| `user_id` | `String`, FK `users.id`, **indexed** | — |
| `mode` | `String(32)` | `""` |
| `created_at` | `DateTime(timezone=True)` | `_now` |
| `summary` | `Text` | `""` |

#### `OfficeEmail` — table `office_emails` (lines 1100-1103)

| Column | Type | Notes |
|---|---|---|
| `email` | `String(255)` **PK** | stored lowercased |
| `added_at` | `DateTime(timezone=True)` | `_now` |

#### `Setting` — table `settings` (lines 1144-1147)

Owner toggle key/value store.

| Column | Type | Default |
|---|---|---|
| `key` | `String(64)` **PK** | — |
| `value` | `String(255)` | `""` |

### 4.4 `init_db()` — schema creation + migrations (lines 142-152)

Called at startup. No-op when `db_enabled` is `False`. Inside one `_engine.begin()` transaction:

1. `Base.metadata.create_all` — creates any **missing** tables.
2. `CREATE INDEX IF NOT EXISTS ix_progress_xp ON progress (xp DESC)` — `create_all` won't add an index to an already-existing table, so it's added explicitly (leaderboard sort).
3. `ALTER TABLE users ADD COLUMN IF NOT EXISTS status varchar(16) DEFAULT 'active'`
4. `ALTER TABLE users ADD COLUMN IF NOT EXISTS mode varchar(16) DEFAULT 'personal'`

> **CRITICAL SCHEMA RULE:** `create_all` **only creates missing tables — it NEVER adds a column to a table that already exists.** So new columns on an existing table are invisible in production unless you also add an explicit `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` here (as `status`/`mode` demonstrate). When evolving the schema: **never rely on `create_all` to add a column to an existing table.** Either add an `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` migration in `init_db`, or put the new data in a brand-new table (which `create_all` will create). New JSON fields inside `Memory.facts` / `Progress.journey` need no migration at all since those are schemaless JSONB bags.

### 4.5 Internal helpers

- `_state(user, prof, prog, mem=None)` (155-173) — builds the full client state dict: `{user, status, mode, onboarded, profile{goal,comfort,practice_time,level,scores,weak_areas}, progress{xp,coins,streak_days,sessions_today,daily_goal,badges,journey}, memory}`. Used by `login`/`save_assessment`/`get_state`/leaderboard.
- `_get_or_make_memory(s, user_id)` (488-498) — fetches the `Memory` row **with `with_for_update=True`** (row-lock) so concurrent writers (WS-finally + `/checkin`, two tabs) don't lose-update the full-doc JSONB write; creates the row if missing. Every `facts`-mutating function goes through this and uses `flag_modified(mem, "facts")` so SQLAlchemy detects the in-place JSON change.
- `_prune_moments` / `_add_moments` / `_add_achievements` (448-485) — moment TTL & achievement dedup.
- Leaderboard aliasing: `_ALIAS_ADJ`, `_ALIAS_ANIMAL`, `_alias(user_id)` (367-376) — deterministic playful alias (e.g. `BraveTiger`) from a char-sum hash, so no per-process randomness.
- Companion constants: `_REL_STAGES` (Guest→Companion, 442), `_WORLD_NAMES` (The Village→The Global Stage, 444-445), `_TODAY_CHALLENGES` (per-weekday, 549-557), `_GOALS` / `_goal_card` (611-626).

### 4.6 Public async functions by area

#### Auth / state
| Function | Lines | Behavior |
|---|---|---|
| `login(claims)` | 176-204 | Upsert `User` from Google claims (`sub`/`email`/`name`/`picture`), bump `last_seen`; create `Profile`+`Progress`+`Memory` if new; returns full `_state`. |
| `get_state(user_id)` | 419-427 | Returns `_state` for an existing user or `None` if no `User` row. |

#### Assessment / onboarding
| Function | Lines | Behavior |
|---|---|---|
| `save_assessment(user_id, data, lang="en")` | 207-242 | Persist goal/comfort/practice_time/level/scores/weak_areas, set `onboarded=True`+`assessed_at`; **seed** `Progress.journey` from `_start_level`, set `daily_goal` from `_daily_goal`. |
| `save_about(user_id, about)` | 755-779 | Store onboarding identity facts (nickname/native_lang/profession/dream/interests) + Day-1 `future_me.day1_text` & `baseline.intro_text`. |

#### Progress / XP / streak / badges / lessons / vocab
| Function | Lines | Behavior |
|---|---|---|
| `complete_lesson(user_id, level, lesson_id, lesson_type="")` | 245-313 | First-time lesson → +`XP_PER_LESSON`, `sentences_spoken`++, daily count & streak; level-up **only if the level is not in `LEVELS_WITH_TEST`**; awards `first_lesson`/`first_converse`/`streak_7`/`sentences_100`/`level_up`. Returns `{progress, leveled_up, new_badges}`. |
| `submit_level_test(user_id, level, score)` | 316-362 | Records attempt into `journey.test_scores`; **pass = score≥70**; unlocks next level if `level==current_level`; awards `level_up` and `courage_confident` (≥90). Returns `{progress, leveled_up, new_badges, passed}`. |
| `record_practice(user_id, seconds=0, sentences=0, xp=20)` | 905-925 | A Daily/Talk session = practice: +xp, streak, `sessions_today`++, then folds into `bump_daily_stat`. |
| `bump_daily_stat(user_id, sentences=0, seconds=0)` | 928-948 | Updates `daily_stats[today]`, `longest_convo_sec`, lifetime `total_sentences`/`total_seconds`. |
| `add_vocab(user_id, words)` | 951-974 | Adds new alpha words (≥2 chars) to `vocab` (cap 500), bumps `vocab_total` and `daily_stats[today].new_words`. |
| `award_badges(user_id, ids)` | 987-1002 | Adds badge ids not already present; returns newly-added. |
| `leaderboard(me_id, limit=20)` | 379-416 | Top-N by all-time `xp` (aliased), plus caller's own row+rank (via `COUNT(xp > mine)`). |
| `save_future_me(user_id, text)` | 1005-1018 | Sets `future_me.day1_text` (if unset) + `latest_text`/`latest_date`. |
| `save_letter(user_id, text)` | 977-984 | Stores `last_letter = {date, text}`. |

#### Memory / facts
| Function | Lines | Behavior |
|---|---|---|
| `get_memory(user_id)` | 501-507 | Returns `facts` dict, pruning expired moments first. |
| `merge_facts(user_id, facts, events)` | 782-817 | Merge LLM-extracted identity/interests/notes(`facts_learned`)/relationship/moments/achievements and dedup events. |
| `set_next_hook(user_id, hook)` | 820-832 | Store/clear `next_hook` (≤200 chars) — the "promise for next time." |
| `save_checkin(user_id, mood, energy="")` | 864-877 | Upsert today's checkin + set `energy_today`. |

#### Companion / recommendations (derived, read-mostly)
| Function | Lines | Behavior |
|---|---|---|
| `relationship_stage(user_id)` | 510-524 | Internal Guest→Companion stage from session count + days (never shown). |
| `build_companion_context(user_id)` | 527-546 | Identity + relationship + recent moments/achievements + energy + stage + world + level + next_hook. |
| `build_growth(user_id)` | 560-607 | Confidence composite (persists `last_confidence`), vocabulary, streak, transformation timeline, dream %. |
| `build_opening(user_id)` | 629-646 | DuSu's memory-aware first line (next_hook → last summary → achievement → moment → stage default). |
| `build_recommendations(user_id)` | 649-705 | Ranks intent → 3 goal cards (primary carries a "why"). |
| `build_today(user_id)` | 708-743 | The single dynamic "today" card (story/streak/moment/celebrate/weekday-challenge). |

#### Conversations (recent summaries / turns)
| Function | Lines | Behavior |
|---|---|---|
| `add_conversation(user_id, mode, summary)` | 856-861 | Insert one `Conversation` row (skips empty summary). |
| `recent_summaries(user_id, limit=3)` | 746-752 | Latest N non-empty summaries, newest first. |
| `save_recent_turns(user_id, turns)` | 835-853 | Store last 10 raw turns (`role`/`content≤400`/`mode`) into `facts.recent_turns` for cross-mode thread continuity. |

#### Daily context
| Function | Lines | Behavior |
|---|---|---|
| `save_daily_context(user_id, ctx)` | 880-902 | Merge today's mood/plans/weather/note/events into `facts.daily_context`, keeping only today + yesterday (48h window). |

#### Admin (owner dashboard) — all guard `if not db_enabled`
| Function | Lines | Behavior |
|---|---|---|
| `admin_list_users()` | 1022-1058 | Full per-user rows (identity, status/mode, level/goal, xp/streak, sessions_today/daily_goal, total_sessions from `Conversation` count, total_minutes, words, `daily_stats`), ordered by `last_seen desc`. |
| `set_user_status(user_id, status)` | 1061-1070 | Set `status` ∈ {active, pending, blocked}. Returns bool. |
| `set_user_mode(user_id, mode, status=None)` | 1073-1084 | Set `mode` ∈ {personal, office}, optional status. Returns bool. |
| `get_user_flags(user_id)` | 1087-1096 | Cheap `{status, mode}` for the access gate (defaults `active`/`personal` when DB off or user missing). |
| `admin_wipe_users(keep_emails)` | 1170-1185 | Delete every user (+ Conversation/Memory/Progress/Profile) whose lowercased email is **not** in `keep_emails`. Owner test reset. Returns count. |
| `delete_user(user_id)` | 1188-1199 | Delete a single user + all their child rows. |

#### Office allowlist & settings — all guard `if not db_enabled`
| Function | Lines | Behavior |
|---|---|---|
| `office_list()` | 1106-1111 | All allowlisted emails, newest first. |
| `office_has(email)` | 1114-1119 | Membership check (lowercased). |
| `office_add(email)` | 1122-1129 | Insert if valid (`@` present) and not present. |
| `office_remove(email)` | 1132-1140 | Delete if present. |
| `get_setting(key, default="")` | 1150-1155 | Read a `Setting` value (returns `default` when DB off/missing). |
| `set_setting(key, value)` | 1158-1167 | Upsert a `Setting`. |

---

## 5. LLM Brain, Providers & Prompts

DuSu's "brain" is a single **OpenAI-compatible chat-completions client that fans out across a chain of free LLM providers**. There is no local model and no vendor SDK beyond `openai` — every provider (Gemini, Groq, OpenRouter, GitHub Models) speaks the OpenAI Chat Completions shape, so one `AsyncOpenAI` client per provider (differing only in `base_url` + `key` + `default_headers`) drives them all. Speech (STT/TTS) is entirely browser-side; the model only ever sees and emits **text**.

### 5.1 Files at a glance

| File | Role |
|---|---|
| `backend/app/config.py` | `Settings` (pydantic-settings): env keys, usage caps, and the two chain builders `providers()` / `providers_from(keys)`. |
| `backend/app/providers/base.py` | `LLMProvider` `Protocol` (structural interface: `next_question`, `score`). App depends on this, never a concrete vendor. |
| `backend/app/providers/openrouter_provider.py` | The actual engine: chain walker `_complete`, cooldown logic, `_extract_json`, per-request routing (`_active_chain` / `set_active_keys`), and the `OpenRouterLLM` class with `next_question` / `translate` / `generate` / `assess` / `score`. |
| `backend/app/providers/__init__.py` | Wiring point. Instantiates `llm = OpenRouterLLM()` and exports it. **There is no `llm.py`** — `from ..providers import llm` resolves to this singleton. |
| `backend/app/interview/engine.py` | `Session` class: per-session state + turn logic for all four modes. |
| `backend/app/interview/prompts.py` | All system prompts + `interviewer_system()` / `conversation_system()` builders and the `COMPETENCIES` / `DUSU_PERSONA` constants. |
| `backend/app/main.py` | HTTP/WS endpoints that call `llm.*` directly for one-shot tasks (level test, greeting, letter, lesson eval) and set per-request keys. |

### 5.2 Settings / config (`config.py`)

Loaded once from `.env` (`SettingsConfigDict(env_file=".env", extra="ignore")`); the module-level singleton is `settings = Settings()`.

**Env-var fields** (empty string default → skipped in the chain):

| Field / env var | Purpose |
|---|---|
| `gemini_api_key` | Google Gemini (OpenAI-compat endpoint) key |
| `groq_api_key` | Groq key |
| `openrouter_api_key` | OpenRouter key |
| `github_token` | GitHub Models inference key |
| `google_client_id` | Google Sign-In |
| `session_secret` (default `"dev-change-me"`) | session signing |
| `database_url` (default `""`) | Neon Postgres; empty = app runs stateless |
| `host` (`0.0.0.0`), `port` (`8000`) | server bind |

**Usage caps** (protect the shared free quota):

| Field | Default | Meaning |
|---|---|---|
| `max_sessions_per_day` | `20` | per user; resets daily |
| `conversation_max_turns` | `40` | free chat gently wraps up |
| `interview_max_turns` | `15` | hard cap (interview self-ends ~8 exchanges) |

### 5.3 The FREE provider failover chain — `settings.providers()`

Returns a list of provider dicts **in fallback order**. Each dict: `name`, `base_url`, `key`, `models` (tried in order), `headers`, `extra` (per-provider request body merged as `extra_body`). Empty keys are skipped, so the live chain is whatever subset of keys is configured.

| Order | name | base_url | env key | models (in order) | headers / extra |
|---|---|---|---|---|---|
| 1 | `gemini` | `https://generativelanguage.googleapis.com/v1beta/openai/` | `gemini_api_key` | `gemini-flash-latest`, `gemini-flash-lite-latest` | `extra={}` — **Gemini's OpenAI-compat rejects `reasoning_effort` (400), so extra must stay empty** |
| 2 | `groq` | `https://api.groq.com/openai/v1` | `groq_api_key` | `llama-3.3-70b-versatile`, `llama-3.1-8b-instant` | `extra={}` |
| 3 | `openrouter` | `https://openrouter.ai/api/v1` | `openrouter_api_key` | `openai/gpt-oss-20b:free`, `nvidia/nemotron-3-super-120b-a12b:free` | `headers={HTTP-Referer: https://dusu-app-1.onrender.com, X-Title: DuSu}`, `extra={"reasoning":{"exclude":True,"effort":"low"}}` |
| 4 | `github` | `https://models.github.ai/inference` | `github_token` | `openai/gpt-4o-mini`, `meta/Llama-3.3-70B-Instruct` | `extra={}` |

Note in code: `meta-llama/llama-3.3-70b-instruct:free` was dropped from OpenRouter (now paid-only → 404).

### 5.4 BYOK / "Office mode" chain — `settings.providers_from(keys)`

Builds the **same** base_urls / models / headers / order as `providers()`, but from caller-supplied keys instead of env. Input `keys` is a dict `{gemini, groq, openrouter, github}`; each value is coerced to a stripped string (`str(vv or "").strip()`) and missing/empty keys are skipped. Used both to build a per-request chain and (in `main.py:267`) to validate the shape of user-provided keys.

### 5.5 Per-request routing — `_active_chain` contextvar + `set_active_keys(keys)`

In `openrouter_provider.py`:

```python
_active_chain: ContextVar[list | None] = ContextVar("_active_chain", default=None)

def set_active_keys(keys: dict | None) -> None:
    chain = settings.providers_from(keys) if keys else None
    _active_chain.set(chain or None)
```

- `contextvars` are per-task, so **each WebSocket connection / HTTP request is isolated** — one user's BYOK keys never leak into another's request.
- `_complete` picks the chain with `chain = _active_chain.get() or settings.providers()` — Office/BYOK keys if set for this request, otherwise the default env chain.
- `main.py` calls `set_active_keys(...)` at the top of every key-scoped endpoint (`leveltest_gen` line 439, `assess` line 466, `greeting` line 539, `letter` line 587, `lesson eval` line 649, `leveltest grade` line 698, and the WS handler line 911) before invoking `llm.*`.

### 5.6 The chain walker — `_complete(messages, max_tokens)`

Core loop that every helper funnels through. Behavior:

- **Clients are cached** per provider name in `_clients` (`_client(p)` lazily builds `AsyncOpenAI(api_key, base_url, default_headers)`).
- **Cooldown map** `_cooldown: {provider_name -> skip-until-epoch}`. `_mark_cooldown(name, err)` sets a **1800s (30 min)** skip if the error text looks like a daily/quota exhaustion (`"day"`, `"quota"`, `"free_tier"`, `"free-models"`), else **90s**.
- Two passes: `for ignore_cd in (False, True)` — first pass skips providers still on cooldown; if **every** provider is cooling down (nothing attempted), the second pass tries them anyway rather than failing.
- For each provider it walks `p["models"]` in order, calling `client.chat.completions.create(model, messages, max_tokens, temperature=0.7, extra_body=p["extra"])`.
- On a non-empty `resp.choices[0].message.content`, returns the stripped text.
- On exception: if the error string contains `429/rate/quota/exceed/exhaust` → `_mark_cooldown` the whole provider and `break` (skip its remaining models); any other error → `continue` to the next model.
- If nothing answers: `raise RuntimeError(f"all providers/models unavailable: {last_err}")`.

### 5.7 Robust JSON extraction — `_extract_json(text)`

Hardened parser used by every JSON-returning helper (`assess`, `score`), because models don't always emit clean JSON:

1. Strips leading/trailing whitespace.
2. **Strips ```` ```json ```` / ```` ``` ```` code fences** via regex (`^```(?:json)?\s*` and `\s*```$`).
3. `json.loads` the cleaned text.
4. On `JSONDecodeError`, greedily regexes the first `\{.*\}` block (`re.DOTALL`, to the last closing brace) and retries.
5. On total failure returns a sentinel `{"error": "scoring_parse_failed", "raw": text[:500]}` — callers check `d.get("error")` (e.g. `leveltest_gen`).

### 5.8 `llm` helper methods (`OpenRouterLLM`)

| Method | Signature | max_tokens | Returns | Notes |
|---|---|---|---|---|
| `next_question` | `(system, transcript)` | **250** | `str` | Builds `[{system}, *transcript]`. **If transcript has no user turn**, appends a seed user turn `"Let's begin. Greet me and ask your first question."` — some providers (Gemini) reject a system-only request, and DuSu speaks first. |
| `translate` | `(system, text)` | **120** | `str` | `[{system}, {user: text}]`. |
| `generate` | `(system, prompt, max_tokens=500)` | 500 default | `str` | Free-form prose (weekly letters, summaries). Raw text. |
| `assess` | `(system, payload, max_tokens=700)` | **700 default** | `dict` | Appends `"\n\nReturn ONLY the JSON object."` to payload, then `_extract_json`. |
| `score` | `(system, transcript)` | **1200** | `dict` | Flattens transcript to `role: content` lines, appends `"\n\nReturn ONLY the JSON object."`, then `_extract_json`. |

**The 700→1100 daily fix:** `assess` defaults to 700 tokens, but `Session.daily_turn` overrides it with `max_tokens=1100` (`engine.py:84`). The daily reply must fit the full friend-reply plus the whole JSON payload (`english` + `reply_hindi` + `next_question_hindi` + `tip` + `mood` + `context`) — at 700 it truncated mid-JSON and produced an empty reply.

### 5.9 `Session` class (`interview/engine.py`)

- `END_MARKER = "INTERVIEW_COMPLETE:"`
- `MODES = ("interview", "conversation", "learning", "daily")`

**Constructor** `__init__(mode, name, role, facts_summary="", mood="", profession="", time_of_day="", level="", daily_context="")`:
- `mode` falls back to `"interview"` if not in `MODES`; `name` defaults to `"there"`, `role` to `"general"`.
- Builds the static system prompt per mode: `interview` → `interviewer_system(name, role, facts_summary, mood)`; `conversation` → `conversation_system(name, facts_summary, mood)`; **`learning` and `daily` get `self.system = ""`** (daily builds its prompt per-turn via `assess`; learning is one-shot `translate`).
- State: `self.transcript: list[dict]` (`{role: "user"|"assistant", content}`), `self.done=False`, `self.capped=False` (conversation hit cap), `self.turns=0` (user turns so far).

**Methods:**

| Method | What it does |
|---|---|
| `add_user(text)` | Appends `{role:"user", content:text}` to transcript, `turns += 1`. |
| `next_ai_turn()` | Calls `llm.next_question(self.system, transcript)`. **Interview:** if `END_MARKER` in the raw reply → `done=True`, spoken = text after the marker (or a default closer); else if `turns >= interview_max_turns` (15) → `done=True` with a "that's all the questions" wrap. **Conversation:** if `turns >= conversation_max_turns` (40) → `capped=True` with a "let's pause here" line. Appends the assistant line and returns `spoken`. |
| `translate(text)` | Learning mode: `llm.translate(TRANSLATE_SYSTEM, text)` → Hindi/Hinglish → spoken English. |
| `daily_turn(answer, first=False)` | Daily Companion. Builds a text `payload` with **LEARNER FACTS**, `profession`, `time_of_day`, `english_level` (defaults `A1`), recent `daily_context`, and the `conversation so far`. If `first=True`, instructs the model to open warmly and leave english/praise empty; else appends `learner just said (in Hindi/Hinglish): {answer}`. Calls `llm.assess(DAILY_TURN_SYSTEM, payload, max_tokens=1100)`. When not first, appends the user answer (`turns += 1`); then stores `reply = data["reply_hindi"] or data["next_question_hindi"]` as the assistant turn. Returns the full `data` dict (`english`, `reply_hindi`, `next_question_hindi`, `tip`, `mood`, `context`). The convo-so-far in the payload is how it **resumes**. |
| `build_report()` | Interview only (else `{}`): `llm.score(SCORER_SYSTEM, transcript)`. |
| `summarize_and_extract()` | ONE call at session end → summary + facts + events + signals. Returns `{}` for learning mode or if no user turn exists. Flattens transcript and calls `llm.assess(SESSION_MEMORY_SYSTEM, convo)`, swallowing exceptions to `{}`. |

### 5.10 Prompts (`interview/prompts.py`)

Shared building blocks: `COMPETENCIES` (list: `self_introduction`, `role_motivation`, `project_depth`, `communication`, `strengths_weakness`); `DUSU_PERSONA` (the consistent patient/warm/never-judging coach voice, prepended to interview + conversation prompts); `_memory_block(facts_summary, mood)` (compact "what you remember about this learner" + mood-adjustment text injected into both builders).

| Prompt | Used by | Output shape | What it produces |
|---|---|---|---|
| `interviewer_system(name, role, facts_summary, mood)` | `Session` (interview) | plain text | DUSU_PERSONA + rules for a spoken mock interview: one question at a time, <2 sentences, adapt to answers, cover the 5 competencies, **no grammar correction during**, end with a line starting exactly `INTERVIEW_COMPLETE:` after ~6-8 exchanges. |
| `conversation_system(name, facts_summary, mood)` | `Session` (conversation) | plain text | DUSU_PERSONA + rules for warm spoken English chat: 1-2 sentences, react + one open follow-up, follow their interests, **never end / never say goodbye**, no lecturing, read the feeling behind words, continue the one ongoing cross-mode relationship thread from memory. |
| `GREETING_SYSTEM` | `main.py:561` via `llm.next_question` (payload = memory JSON) | plain text (≤45 words) | ONE short spoken greeting in **Devanagari-mixed Hinglish** (~55% Hindi Devanagari + Latin English so TTS pronounces it) — greet by name, exactly one real memory callback, one encouragement, place them in their journey, end with one open question. |
| `SESSION_MEMORY_SYSTEM` | `Session.summarize_and_extract` via `assess` | JSON | Durable memory extraction: `summary`, `facts` (`interests`, `profession`, `dream`, `notes`, `relationship`, `moments`, `achievements`), `events[]`, `no_hindi` bool, `asked_question` bool, `next_hook` string. Only keys actually found. |
| `DAILY_TURN_SYSTEM` | `Session.daily_turn` via `assess(max_tokens=1100)` | JSON | The Daily Companion "close friend" reply. Internal reasoning about dominant/hidden emotion, then a 50-90-word Hinglish (Latin script) reply in a 6-step shape ending in exactly one follow-up question. Returns `english` (learner's line translated to natural English), `reply_hindi`, `next_question_hindi`, `tip`, `mood`, `context{plans,weather,events[]}`. Hard rules: use their real name (never "bhai/yaar"), forbidden filler phrases, never re-ask. |
| `LETTER_SYSTEM` | `main.py:618` via `llm.generate(max_tokens=350)` | plain text | A warm 4-6 line weekly mentor note starting `Hi <name>,`, referencing real facts/progress; may add one Hindi (Latin) line for Hindi beginners. |
| `TRANSLATE_SYSTEM` | `Session.translate` via `llm.translate` | plain text (one sentence) | Hindi/Hinglish → natural spoken English, output only the English sentence (no quotes/explanation), meaning-based not literal. Includes few-shot examples. |
| `ASSESS_SYSTEM` | `main.py:479` via `assess` (onboarding level test) | JSON | CEFR level assessment from MCQ answers + 4 spoken task transcripts (intro/repeat/think/open). Scores 6 skills 0-100 (`confidence`, `pronunciation`, `listening`, `vocabulary`, `grammar`, `thinking`), picks `level` (A0-B2), `weak_areas` (≤3), warm `message`. |
| `LESSON_EVAL_SYSTEM` | `main.py:658` via `assess` | JSON | Grades one short spoken lesson answer kindly: `pass` bool, `correct_english`, `feedback` (Hindi Latin if `lang==hi`), `encouragement`. |
| `LEVEL_TEST_SYSTEM` | `main.py:708` via `assess` | JSON | Grades a whole end-of-level test set generously: `score` 0-100, `passed` (≥70), per-item `items[]` (`pass`+`feedback`), warm `message`. (Note: the level-test **questions** are generated dynamically by an inline prompt in `leveltest_gen`, `main.py:440-444`, not by this graded prompt.) |
| `SCORER_SYSTEM` | `Session.build_report` via `llm.score` | JSON | Full interview evaluation: `overall` 0-100, `scores{grammar,fluency,confidence,communication,vocabulary,professionalism}`, `filler_words[]`, `strengths[]` (≤3), `fixes[]` (≤3), `better_answer{question, their_answer, improved}`. |

All JSON prompts explicitly instruct "Return ONLY a JSON object (no markdown)", which pairs with `_extract_json`'s fence-stripping defense in depth.

---

## 6. Frontend — Shell, Auth & Routing (backend/test_client.html)

The entire DuSu web app is **one self-contained file**: `backend/test_client.html` (~4135 lines). There is **no build step, no framework, no bundler, no modules** — a single top `<style>` block, the HTML body (all screens stacked), and one bottom `<script>` running in a single global scope. It is served verbatim by FastAPI.

### 6.1 How it is served (server-side placeholder injection)

`GET /` in `backend/app/main.py` (line 734, `index()`) reads the file and does three literal string replacements before returning `HTMLResponse`:

| Placeholder in HTML | Replaced with | Source |
|---|---|---|
| `__GOOGLE_CLIENT_ID__` | Google OAuth client id | `settings.google_client_id` |
| `__AUTH_ENABLED__` | `true` / `false` (unquoted JS boolean) | `auth.auth_enabled` |
| `__MAX_SESSIONS__` | daily session cap (default `20`) | `settings.max_sessions_per_day` |

In JS these become: `const GOOGLE_CLIENT_ID = "__GOOGLE_CLIENT_ID__";` (line 3826), `const AUTH_ENABLED = __AUTH_ENABLED__;` (line 3827), `const MAX_SESSIONS = Number("__MAX_SESSIONS__") || 20;` (line 3857). Global helper: `const $ = id => document.getElementById(id);` (line 1744). Speech is 100% browser-side (Web Speech API `SpeechRecognition`/`speechSynthesis`); the server only ever receives text. `WS_URL` (line 1743) is derived from `location`: `(https→wss / http→ws) + location.host + "/ws/interview"`.

### 6.2 App-shell CSS (fixed viewport, one scroll region, phone frame)

The shell is a flex column pinned to the viewport height; only the middle `.wrap` scrolls, and `.bnav` is a genuine flex child at the bottom (not `position:fixed`).

```css
body { height:100vh; height:100dvh; display:flex; flex-direction:column;
       overflow-x:hidden; overscroll-behavior-y:none; }          /* line 47 */
.wrap { max-width:440px; width:100%; flex:1 1 auto;
        overflow-y:auto; overflow-x:hidden;                       /* the ONLY scroll region */
        -webkit-overflow-scrolling:touch; margin:0 auto;          /* centered → phone frame on desktop */
        padding: max(24px,env(safe-area-inset-top)) … ; }         /* line 54; notch-safe */
.bnav { flex:0 0 auto; width:100%; max-width:440px; height:76px;  /* line 961; REAL bottom bar */
        margin:0 auto; background:rgba(10,14,26,.94); backdrop-filter:blur(14px);
        border-top:1px solid rgba(255,255,255,.07);
        padding-bottom:env(safe-area-inset-bottom); }
.bnav.hide { display:none; }                                      /* hidden on login/onboarding */
.screen   { display:none; animation:fade .45s ease both; }        /* line 142 */
.screen.on{ display:block; }
```

- The 440px `max-width` + `margin:0 auto` on both `.wrap` and `.bnav` produces a **centered phone-width column** on desktop; on mobile it fills the width. A `@media (max-width:480px)` block (line 60) tightens padding/logo/hero sizes.
- Custom thin scrollbar styling is applied only to `.wrap` (lines 1013–1017, Firefox `scrollbar-*` + WebKit `::-webkit-scrollbar`).
- The notification bar (`.notif`, line 1021) and More sheet (`.msheet`/`.msheet-bg`, lines 1036–1042) are the only `position:fixed` chrome, each also `max-width:440px` and centered with `left:50%; transform:translateX(-50%)`.

### 6.3 Screen system

Every screen is a `<section class="screen">` with a unique id. Exactly one carries `.on` at a time.

| Section id | Purpose | NAV_TAB → tab |
|---|---|---|
| `login` | Google sign-in card (`#gbtn`, `#loginNote`) | (nav hidden) |
| `home` | Hero, Today card, growth strip, mode cards | `home` |
| `keys` | BYOK / Office-mode key entry + verify | `more` |
| `admin` | Owner dashboard (users & activity) | `more` |
| `practice` | Mode picker landing | `practice` |
| `setup` | Interview setup (role/name) | `practice` |
| `learning` | "Learn" voice loop | `practice` |
| `daily` | "Talk about your day" voice loop | `daily` |
| `assessment` | Dynamic level test | (nav hidden) |
| `journey` | Journey/dashboard (also reused as "Profile") | `journey` |
| `leaderboard` | Ranks | `leaderboard` |
| `lesson` | Level-test lesson runner | `practice` |
| `session` | Live conversation/interview voice loop | `practice` |
| `report` | Post-session report | `practice` |

**`show(id)`** (line 1887) is the router:
1. If leaving a live voice screen (`cur ∈ VOICE_SCREENS` and `cur !== id`) it calls **`stopAllVoice()`** first, so DuSu never keeps talking on another tab.
2. Removes `.on` from all `.screen`, adds it to `$(id)`.
3. On `home`: hides `#moreHome`, re-renders `renderHomeJourney()` + `renderHomeExtras2()`.
4. Calls `syncNav(id)`.

```js
const VOICE_SCREENS = new Set(["session","daily","learning"]);   // line 1872
function currentScreen(){ const el=document.querySelector(".screen.on"); return el?el.id:""; }
```

**`stopAllVoice()`** (line 1875) is the teardown: `running=false; aiSpeaking=false`, stops conversation STT (`stopListening()`), stops daily STT (`drec.stop()`), `speechSynthesis.cancel()`, stops face/assistant lip-sync, `dMicActive(false)`, and closes the WebSocket (`ws.onclose=null; ws.close(); ws=null` — the server persists state on disconnect). A `visibilitychange` listener (line 1910) also calls `stopAllVoice()` when the tab is hidden while a voice loop is running.

**`syncNav(id)`** (line 1904) toggles `.bnav.hide` for `login`/`assessment`, then looks up `NAV_TAB[id]` and lights the matching `.btab.active`:

```js
const NAV_TAB = { home:"home", journey:"journey", daily:"daily", practice:"practice",
  learning:"practice", session:"practice", setup:"practice", lesson:"practice", report:"practice",
  leaderboard:"leaderboard", profile:"more", keys:"more", admin:"more" };   // line 1901
```

**Bottom-nav wiring** (line 1915) — six `.btab[data-tab]` buttons (`home`, `journey`, `daily`, `practice`, `leaderboard`, `more`):
- `home → goHome()`, `journey → openJourney()`, `daily → startDaily("speak")`, `practice → show("practice")`, `leaderboard → openLeaderboard()`.
- `more` opens the sheet via `toggleSheet(true)`, and reveals the owner-only Dashboard row (`#mrowAdmin`) only when `userState.role === "owner"`.

**More sheet** (`#msheet` / `#msheetBg`, HTML line 1721): `toggleSheet(o)` (line 1913) toggles `.on`. Rows are `.mrow[data-more]` (handler line 1928): `leaderboard`, `profile` (→ `openJourney()`, reused as Profile), `leveltest` (→ `startAssessment()`), `keys` (→ `show("keys"); loadKeysUI()`), `admin` (→ `openAdmin()`), `signout` (→ `logout()`). Tapping the backdrop closes it and re-syncs nav to home/practice.

### 6.4 Auth (Google Sign-In + HMAC token)

Config/state globals (lines 3826–3830): `GOOGLE_CLIENT_ID`, `AUTH_ENABLED`, `authToken = localStorage.getItem("dusu_token")`, `authUser = JSON.parse(localStorage.getItem("dusu_user"))`, `userState = null`.

**`onGoogle(resp)`** (line 4075) — the GIS callback. POSTs `{credential}` to **`/auth/google`**, then on success:
- `authToken = d.token`, persists `dusu_token`, `dusu_user`, `dusu_onboarded`.
- Seeds `userState` from the response, calls `applyUser(d.user)`.
- Always `show("home")` immediately, then `refreshMe()`. Brand-new users (`d.onboarded === false`) rely on `refreshMe()` → `routeAfterLogin()` to reach the level test; returning users additionally get `speakWelcome()` (needs the sign-in click as the audio gesture).

**`applyUser(u)`** (line 3832): reveals `#hdrRight`, hides tagline, fills `#uName`, and swaps Google `#uAvatar` photo vs `#uInit` initials (`av.onerror → useInit`). Also prefills the interview name field, `setWelcome()`, `refreshUsage()`.

The **session token is HMAC-signed server-side** (`backend/app/auth.py`, `make_session`, line 59): `base64url(JSON payload).base64url(HMAC-SHA256(payload, SECRET))` with a 30-day `exp`. It is self-contained (no DB lookup); `read_session()` recomputes the signature with `hmac.compare_digest` and checks `exp`. The client just stores the opaque string in `dusu_token` and sends it as `Authorization: Bearer <token>` (for `/me`) or inside JSON/WS payloads as `token`.

### 6.5 The deterministic login gate

**`routeAfterLogin()`** (line 4045) is the single source of truth for "which screen after login", in strict priority order:

```
1. needsKeys() && !hasOwnKeys()   → force Office mode, show("keys"), loadKeysUI(),
                                     status "🔒 Add your own free API keys (at least 2) to start."
2. userState.onboarded === false  → startAssessment()      (level/test not done)
3. otherwise                      → show("home") + setWelcome() + renderHomeJourney()
```

**`initAuth()`** (line 4101, called once at the bottom): if `!AUTH_ENABLED` it skips login (`show("home")`, dev fallback). If a cached `authToken`+`authUser` exist it: `applyUser`, restores cached `userState` from `dusu_state` **before first paint**, optimistically routes via `routeAfterLogin()` from cached state, then calls `refreshMe()` to re-confirm. Otherwise `show("login")`. Finally it polls until `google.accounts.id` is ready, then `initialize({client_id, callback:onGoogle})` and renders the button into `#gbtn`.

**`refreshMe()`** (line 4060): `fetch("/me", {cache:"no-store", Authorization:Bearer})`. On `401` → `logout()` (real sign-out). On success it sets `userState`, persists `dusu_onboarded` and the whole state to `dusu_state`, then calls `routeAfterLogin()`. On network failure it returns `null` and keeps the cached home (never strands the user offline).

**`logout()`** (line 4034): clears `authToken`/`authUser`, removes `dusu_token`, `dusu_user`, `dusu_state`, `dusu_letter`, `dusu_daily_resume`, `dusu_keys_ok`, closes the WS, disables Google auto-select, `show("login")`.

### 6.6 Every localStorage key

| Key | Written by | Meaning |
|---|---|---|
| `dusu_token` | `onGoogle` | HMAC session token; sent as Bearer / `token`. Cleared on logout. |
| `dusu_user` | `onGoogle` | Cached Google user `{sub,email,name,picture}` for instant boot. Cleared on logout. |
| `dusu_onboarded` | `onGoogle`, `refreshMe`, assessment finish | `"true"`/`"false"` — has the level test been completed. |
| `dusu_state` | `refreshMe`, assessment finish | Full `/me` state JSON (today, growth, opening, recommendations) cached for zero-wait first paint. Cleared on logout. |
| `dusu_letter` | `openJourney`/letter fetch (line 3417) | Cached "letter to future self" text. Cleared on logout. |
| `dusu_daily_resume` | `saveDailyResume` (line 2621) | `{date, turns:last12, lastQuestion}` to resume the Daily chat; only reused if ≤ 2 days old, else discarded. Cleared on logout. |
| `dusu_office_keys` | key verify (line 1985) | JSON of BYOK keys `{gemini, openrouter, github, groq}`. |
| `dusu_usemode` | mode toggle / gate | `"personal"` (our keys) or `"office"` (user's own keys). Default `"personal"`. |
| `dusu_keys_ok` | key verify | `"1"` once ≥2 keys passed `/keys/verify`. Removed whenever a key input is edited (line 1968) and on logout. |
| `dusu_voice` | voice `♀/♂` toggle (line 2400) | Preferred TTS gender. **Note: written but never read back on init** — `voiceGender` always defaults to `"female"` (line 2370). |
| `dusu_usage` | `usageInc` (line 3871) | `{d:YYYY-MM-DD, n}` daily session counter for the free-tier cap. |
| `dusu_think` | `pushThink` (line 3950) | Rolling array (last 30) of "thinking speed" seconds → home growth chip. |

### 6.7 BYOK / Office-mode helpers

All defined around lines 1746–1773. "Office mode" means the user supplies their own free AI keys; "Personal" uses the app's keys.

| Function | Line | Behavior |
|---|---|---|
| `officeKeys()` | 1747 | `{}` in Personal mode; else parsed `dusu_office_keys`. This is the object sent to the server on every start/lesson/report request (see call sites below). |
| `officeAllowed()` | 1752 | True if `userState.office_allowed \|\| free_access \|\| role === "owner"/"unlimited"` — i.e. this user may use **our** keys. |
| `savedKeys()` | 1753 | Parsed `dusu_office_keys` (regardless of mode). |
| `keyCount()` | 1754 | Count of non-empty saved key values. |
| `keysVerified()` | 1755 | `dusu_keys_ok === "1"`. |
| `hasOwnKeys()` | 1756 | `keyCount() >= 2 && keysVerified()` — the hard requirement. |
| `needsKeys()` | 1762 | `userState.require_own_keys && !officeAllowed()` — global BYOK switch is ON and this user isn't free-access. |
| `mustAddKeys()` | 1763 | `needsKeys() && !hasOwnKeys()`. |
| `guardKeys()` | 1765 | If `mustAddKeys()`: force Office mode, `show("keys")`, `loadKeysUI()`, set lock status, return `true` (blocked). Called at the top of `chooseMode()` (2088), `startDaily()` (2649), `startAssessment()` (2913). |
| `showNotif(msg)` | 1759 | Fills `#notifTxt`, shows the fixed `#notifBar`, auto-hides after 10s. Triggered on WS `"quota"` message (line 2351) and HTTP `429` (lines 3036/…). |

**Keys UI**: `loadKeysUI()` (1947) fills the four inputs (`#kGemini #kOpenrouter #kGithub #kGroq`) from `dusu_office_keys`, and when `needsKeys()` hides the "Personal" option and shows the lock note. `#verifyKeys` (1971) POSTs `{token, keys}` to **`/keys/verify`**; per-key status shows ✅/❌; on **≥2 working keys** it saves `dusu_office_keys`, sets `dusu_usemode="office"` + `dusu_keys_ok="1"`, and calls `routeAfterLogin()` to continue; otherwise it removes `dusu_keys_ok` and stays locked. Editing any input clears `dusu_keys_ok` (must re-verify). Mode toggles (`#modePersonal`/`#modeOffice`, lines 1965–1966) also POST to **`/mode`** via `postMode()`.

`officeKeys()` is threaded into the server on: WS `start` (conversation line 2285, learning 2566, daily 2671), and HTTP bodies for report/lesson/level endpoints (lines 2194, 3030, 3088, 3584, 3782).

### 6.8 Service worker (PWA) & versioning

Registered at the very end of the script (line 4128): on `window load`, `navigator.serviceWorker.register("/sw.js")`. The SW file is `backend/sw.js`, served by `main.py` at `GET /sw.js` (line 112).

- **Cache name / version**: `const CACHE = "dusu-v5";` (line 5). Bump this string to invalidate the cache on deploy; `activate` deletes every cache key that isn't the current `CACHE`.
- **Shell precache**: `["/", "/logo.png", "/manifest.webmanifest"]`.
- **Strategy**: navigations are **network-first** (always fetch fresh HTML so new deploys appear, falling back to cached `/` offline); static assets are **cache-first** then network. `install` calls `skipWaiting()`, `activate` calls `clients.claim()`.
- **Never cached** (returned early, always live): any path starting with `/ws`, `/auth`, `/me`, `/health`, `/lesson`, `/level`, `/assessment`, `/admin`, `/keys`, `/mode`, `/.well-known`, and all non-GET methods. (`/me` was explicitly excluded to stop a stale `onboarded` flag being served forever.)

---

## 7. Frontend — Flows & Screens (backend/test_client.html)

The entire client is a **single 4135-line file** `backend/test_client.html` — one inline `<style>` block and one inline `<script>`, no build step, no framework. It is served by the FastAPI backend, which substitutes three placeholders at serve time: `__MAX_SESSIONS__` (line 3857), `__GOOGLE_CLIENT_ID__` (3826), `__AUTH_ENABLED__` (3827). Speech is 100% browser-side (Web Speech API — `SpeechRecognition`/`speechSynthesis`); the server only ever exchanges **text** over one WebSocket: `WS_URL = (https?→wss/ws)://<host>/ws/interview` (line 1743).

### 7.0 App shell, screens & navigation

Every view is a `<section class="screen">`; exactly one carries `.on`. `show(id)` (1887) removes `.on` from all and adds it to `#id`. **Crucially, if the screen being left is in `VOICE_SCREENS = {"session","daily","learning"}` (1872), `show()` calls `stopAllVoice()` first** so the AI never keeps talking on another tab.

| `<section id>` | Line | Purpose |
|---|---|---|
| `login` | 1098 | Google Sign-In (`#gbtn`, `#loginNote`) |
| `home` | 1109 | Hero + living DuSu face + Companion Moment + `#moreHome` extras |
| `keys` | 1259 | Personal/Office mode + BYOK key form |
| `admin` | 1283 | Owner dashboard (`#adminBody`) |
| `practice` | 1292 | 3 headed practice pills |
| `setup` | 1344 | Interview role entry (`#role`) |
| `learning` | 1397 | Translate mode (Hindi→English) |
| `daily` | 1433 | Daily Talk companion |
| `assessment` | 1522 | First-time level test (`#assessStep`, `#assessBar`) |
| `journey` | 1533 | Roadmap/dashboard |
| `leaderboard` | 1555 | Global ranks |
| `lesson` | 1571 | Curriculum think/speak lesson |
| `session` | 1605 | Conversation + Interview voice loop (`#orb`, `#feed`) |
| `report` | 1700 | Scored interview report |

**Bottom nav** `#bnav` (1730) has tabs `home / journey / daily / practice / leaderboard / more`. `NAV_TAB` (1901) maps each screen to the tab that lights up (e.g. `session`→`practice`). `syncNav(id)` (1904) hides the nav only on `login`/`assessment`. Tab handlers (1915): home→`goHome()`, journey→`openJourney()`, daily→`startDaily("speak")`, practice→`show("practice")`, leaderboard→`openLeaderboard()`, more→opens the `#msheet` sheet (`toggleSheet`) and reveals `#mrowAdmin` only when `userState.role === "owner"`. The **More sheet** rows (1928): profile→`openJourney()`, keys→`show("keys")+loadKeysUI()`, leveltest→`startAssessment()`, admin→`openAdmin()`, signout→`logout()`.

Global voice state (1778-1782): `ws, recog, running=false, currentMode="conversation", aiSpeaking=false, lastReport, srFails=0, LISTEN_DELAY=450`.

### 7.a Level test / assessment (first-time onboarding)

Entry: `startAssessment()` (2911). Guards: `if(aActive) return` (double-`routeAfterLogin` guard, line 2912/2822), `guardKeys()`, and requires `SR`. Sets `aActive=true` and seeds `aData` (2916) — `{ lang, about:{interests}, goal, comfort, practice_time, intro, repeat_said, think_said, open_said, repeat_target:"My name is Sarah.", think_hindi:"Kal mujhe market jaana hai." }`.

Step chain (each renders into `#assessStep`, advances `#assessBar` via `aBar(pct)`):
1. **`aLangPick()`** (2923) — asked in Hindi; sets `aData.lang` = `hi`|`en`, then `aWelcome()`.
2. `aWelcome → aAboutName → aAboutWork → aDream → aInterests` — "About you" profile, written into `aData.about[field]` (`aChoiceAbout`, `aText`, 2969-3009).
3. `aGoal → aComfort → aPractice` (3020-3022) — `aChoice` writing to `aData.goal/comfort/practice_time`.
4. **`aStartVoice()`** (3025) — `POST /leveltest/gen {token, keys}` for **dynamic questions**; response overrides `aData.repeat_target` (`d.repeat`), `aData.think_hindi` (`d.think_hindi`), `aData._open` (`d.open`). On `402`→keys screen; `429`→`showNotif`; any failure silently falls back to built-in prompts. Then `aVoice(0)`.
5. **`aVoice(n)`** (3041) — iterates `A_VTASKS` (2827): `[{pct:52,field:"intro",kind:"open"}, {pct:66,field:"repeat_said",kind:"repeat"}, {pct:80,field:"think_said",kind:"think"}, {pct:92,field:"open_said",kind:"open"}]`. It renders the **same** sentence it speaks (`showLine` from `repeat_target`/`think_hindi`/`_open`, no hardcoded string). Speaking rules (3074-3077): `repeat`→say `v.intro` then `aData.repeat_target` in `ENG_SLOW()`; `think`→say `v.instr` then `aData.think_hindi` in `HI()`; `open_said`→say `aData._open || v.say`; `intro`→say `v.say`. Mic uses `listenOnce("en-US")` (learner always answers in English), writes transcript to `aData[t.field]`. `aSkip`/`aNext`→`goNext` → next task or `aEvaluate()`.
6. **`aEvaluate()`** (3081) — `POST /assessment {token, keys, ...aData}`; on failure shows retry / skip-all. On success → `aReveal()`.
7. **`aReveal(d)`** (3100) — sets `userState.onboarded=true`, `userState.profile`, `userState.progress`; **persists** `localStorage.dusu_state` and `dusu_onboarded="true"` (line 3105); renders `A_METRIC_LABELS` bars (confidence/pronunciation/listening/vocabulary/grammar/thinking), level badge, and speaks the profile message. `aDone`→`goHomeAfterAssess()` (3125) which sets `aActive=false`, `setWelcome()`, `renderHomeJourney()`, `refreshMe()`.

All copy is dual-language in `A_L.en` / `A_L.hi` (2835); `aL()` picks the object, `AL2(en,hi)` picks a string, `aVoiceProfile()` = `HI()` for hi else `ENG_NORM()`.

### 7.b Daily Talk (AI companion)

Entry: **`startDaily(from)`** (2648) with `from` ∈ `"speak"` (Start-Speaking hero / Daily nav tab), `"banner"` (Journey/"Continue" banner), or `""`. Guards `guardKeys()`, `SR`, `overLimit()`. State vars (2618): `drec, dLastEng, dLastNext, dailyTurns, dailyFrom, dailyInputs`. Opens WS and on `open` sends:
```js
{ type:"start", mode:"daily", token:authToken, mood:todayMood,
  hour:new Date().getHours(), resume:dailyTurns, keys:officeKeys() }
```
`dailyTurns = loadDailyResume()` (2625) restores recent turns from `localStorage.dusu_daily_resume` **only if ≤2 days old** (else removes it). `saveDailyResume()` (2621) stores `{date, turns:last-12, lastQuestion}`.

WS protocol handled in `onMessage` (2334): `daily_question`→**`greetDaily(m.question)`** (2714) — hides loader, pushes assistant turn, speaks question via `sayFace(question, HI())`, enables mic. `daily_turn`→**`handleDailyTurn(hindi, english, reply, tip, next_question)`** (2739): shows `#dailyCard`, sets tip (`setDailyTip`), then (1) says `HINDI.intro` + learner's line in `ENG_SLOW()` so they hear their sentence in English, (2) says DuSu's `reply` in `HI()` (never silent — falls back to `nextQ` then a canned line). Records both turns and `saveDailyResume()`. **Every 3 inputs** (only `dailyFrom==="speak"`, counted via `dailyInputs`) it speaks a Hindi reminder nudging the learning options and scrolls to `#dailyMore` (2760).

Listen loop: **`startDailyListen()`** (2723) — `SR` with `lang="hi-IN"`, sends `{type:"user_text", text}`; on no-speech says `HINDI.noSpeech`. `dcReplay` replays `dLastEng` in `ENG_SLOW()`; `dcNext`→`dailyContinue()` (2779) hides card and listens again. Orb animation via `dailyOrb(state)` (2639) driving `DAILYFACE`.

Options: **`renderDailyRecs()`** (2689) renders only **Talk** (`conversation`, 💬) and **Learn** (`learning`, 🎓) buttons — **"Day" was removed** (comment line 2694) as redundant on the daily page. `pickDailyRec(action)` (2706) → `leaveDaily()` then `chooseMode(action)`. Shown from the start only when `dailyFrom==="speak"` (2663).

Teardown: **`stopDaily()`** (2774) stops `drec` + cancels speech; **`leaveDaily()`** (2701) closes WS with `{type:"end"}`; **`finishDaily()`** (2785) — bound to both `#dailyFinish` and `#dailyBack` — ends WS, hides options, celebrates ("+20 XP · streak"), returns home.

### 7.c Conversation + Interview (session screen)

Entry: **`startSession(mode)`** (2265), `mode` ∈ `"conversation"|"interview"`. Interview first goes through `#setup` (`chooseMode` line 2087 → `show("setup")`; `#startInterview`→`startSession("interview")`). Guards `SR` and `overLimit()`. Sets titles (`#sessTitle`, `#sessSub`, `#endBtn` label/class differ per mode), `show("session")`, `orb("connecting", …)`.

`ws.onopen` (2282): `running=true`, `usageInc()+refreshUsage()`, then sends:
```js
{ type:"start", mode, name:$("name").value, role:$("role").value,
  token:authToken, mood:todayMood, seed:_convSeed, keys:officeKeys() }
```
`_convSeed` (Companion-Moment spoken answer) is one-shot, cleared after send (2286).

**`onMessage(ev)`** (2334) switch — cases used by session: `ai_text`→`addMsg(m.text,"ai")` + `speak(m.text)`; `interview_done`→`addSys`; `report`→`showReport(m.data)` (and completes a roadmap lesson if `currentLesson`); `ended`→`leave()`; `limit`→stop + orb idle; `quota`→`showNotif`; `keys_required`→force office mode + keys screen; `auth_error`→`logout()`; `error`→orb error. Client→server messages: `{type:"user_text", text}` and `{type:"end"}`.

**Voice loop** (`speak`↔`startListening`):
- **`speak(text)`** (2412): `stopListening()` (mic off — kills echo), `aiSpeaking=true`, orb "speaking", `FACE.startTalking()`, `u.onboundary` pulses the mouth. Has a 4s+`len*70`ms watchdog for Chrome's missing `onend` bug; on done → `delayedListen()` (waits `LISTEN_DELAY`).
- **`startListening()`** (2435): `SR` `lang="en-US"`; `onresult` (drops bleed if `aiSpeaking`) → `addMsg(text,"user")`, `pushThink()` (thinking-speed metric), sends `user_text`, orb "thinking". `onerror` `not-allowed`→stop; else `onend` retries with backoff (`safeRestart`, `srFails` capped at 8).
- Flags `running` (loop alive) + `aiSpeaking` (echo guard) gate the whole loop. `stopListening()` (2467) nulls `recog`.

`#endBtn` (2327) sends `{type:"end"}` and orb "Scoring…". `#backBtn`→`leave()` (2298).

**Report** `showReport(d)` (2488): animated count-up on `#ovVal`, SVG ring `#ringArc` fill, per-metric bars from `METRIC_LABELS` (grammar/fluency/confidence/communication/vocabulary/professionalism), filler-word chips, strengths/fixes lists, `better_answer` (Q + improved). `sparkle()` + `Assistant.happy()` if overall ≥80. **Share** (`#shareBtn`, 2314): builds a text summary, uses `navigator.share` or falls back to clipboard ("Copied ✓"). `#againBtn`→home + `speakWelcome()`.

### 7.d Learning (translate mode)

Entry: **`startLearning()`** (2555) — `chooseMode("learning")`. WS `start` payload `{type:"start", mode:"learning", token, keys}`. On `ready`→`greetLearn()` (2571) speaks `HINDI.greet`. `#micBtn`→`startHindiListen()` (2576): `SR` `lang="hi-IN"`, sends `{type:"user_text", text}`. Server replies `translation {hindi, text}`→**`handleTranslation(hindi, english)`** (2594): fills `#transCard` (`#tcHindi`/`#tcEng`), says `HINDI.intro` then the English in `ENG_SLOW()` **once** (no "repeat after me"). `#replayBtn` replays `lastEnglish`; `#continueBtn`→`startHindiListen()` again. `translate_error` case (2341) shows retry. `stopLearn()` (2603) nulls `lrec`.

### 7.e Practice section (hub)

`#practice` (1292) has three `.prac-block` (each = big centered `.prac-h` heading + one pill `.mode-card`):

| Heading (`.prac-h`) | `data-mode` | `<h3>` | Accent |
|---|---|---|---|
| **Convey your thoughts in English** | `learning` | Learn | `.learn` `#8f97e0` |
| **Face to Face English Talk** | `conversation` | Talk | `.talk` `#5fd0b0` |
| **Get Ready for Interview** | `interview` | Interview | `.interview` `#e6a99b` |

Styles (255-352): `.prac-block` is a centered flex column; `.prac-h` uses gradient-clipped ink + `drop-shadow` glow + an `::after` accent underline; `.mode-card` is a compact rounded pill (label + `.mc-orb` icon + `.mc-cta` arrow) — the verbose `p / .mc-chips / .mc-badge / .mc-wm` are `display:none` (336). Cards animate in with staggered `cardIn` delays and have a cursor-follow spotlight (`::before`, `--mx/--my` set in mousemove, 2096) + hover sheen (`::after`). Click handler `chooseMode(c.dataset.mode)` (2094).

`chooseMode(mode)` (2087): `guardKeys()` first; `interview`→`show("setup")`; `learning`→`startLearning()`; `daily`→`startDaily("banner")`; else `startSession("conversation")`.

### 7.f Voice teardown

**`stopAllVoice()`** (1875) is the single kill-switch for **both** loops: sets `running=aiSpeaking=false`, `stopListening()` (conversation `recog`), stops+nulls daily `drec`, `speechSynthesis.cancel()`, `FACE/Assistant.stopTalking()`, `dMicActive(false)`, and closes `ws` (nulling `ws.onclose` so the server persists state on disconnect). Called from `show()` when leaving any `VOICE_SCREENS`. **`visibilitychange`** listener (1910): when `document.hidden` and (`running` or on a voice screen) → `stopAllVoice()` — so switching browser tab / minimizing stops the AI.

### 7.g Home / Journey / Curriculum, Companion Moment, mood check-in

**Home hero**: `#startSpeak` "Start Speaking" → `startDaily("speak")` (2104). The living DuSu SVG face (`#hchar`, `HOMEFACE`) — eyes/lean follow the cursor (2120), smiles on Start hover (`homeHappy`), and tapping it plays a random `_DELIGHT` line (`dusuGiggle`, 2155). `goHome()` (2106) ends any WS, cancels speech, `closeMoment(false)`, `show("home")`. `setWelcome()` (3890) sets a time-of-day greeting + a day-rotated `HERO_LINES` headline and calls `renderToday/renderGrowth/renderTimeline/renderHomeExtras2`.

**`renderHomeJourney()`** (3256): gated on `onboarded` (cached `dusu_onboarded` flag, no `/me` wait); renders the "Where we left off" `#journeyBanner` (→`startDaily("banner")`), reveals `#roadmapLink`/`#leaderboardLink`, then `renderHomeExtras()` + `renderTimeline()`. **`renderHomeExtras2()`** (3907) paints `#homeChips` (streak/confidence/words from `userState.growth`) and the `#homeGoal` today card.

**Companion Moment** (`#moment`, 1171; still coded but hero now jumps straight to Daily): `openMoment()` (2177) adds `.moment-on` to `.hstage` (hides hero via CSS 396), fetches `POST /greeting {token,keys}` for a Hinglish line spoken on `GREET_VOICE()` (hi-IN), then `showRecs()` (2215) renders 3 `_recCard`s from `userState.recommendations` (primary/second/third, with fallback). `closeMoment(keepSpeech)` (2233) tears it down.

**Mood check-in**: `renderHomeExtras()` (3339) shows `#moodRow` once/day (`MOODS` = great/good/okay/low/tired, 3336) if no `checkins` entry for `todayStr()`. `doCheckin(mood)` (3386) sets `todayMood`, `POST /checkin {token,mood}`, speaks a per-mood line. Also renders `#eventBanner` (upcoming interview/exam) and `loadLetter()` (weekly "note from DuSu" via `POST /letter`, cached in `dusu_letter`). `todayMood` is fed into `daily`/`conversation` `start` payloads and biases lesson phrase choice (3656).

**Journey** (`openJourney()`→`renderJourney()`, 3434): stats chips (level/XP/streak/today from `jProg()`), focus tip from weakest `profile.weak_areas`, skills dashboard, roadmap. **Curriculum**: `CURRICULUM` array (3139) of 7 levels with `lessons[{id,en,hi,vocab,phrases}]`; `WORLD_NAMES`/`LEVEL_ICONS`/`BADGE_LABELS` (3128-3135). **Leaderboard** (`openLeaderboard()`, 3285): `GET /leaderboard` (Bearer auth) → `renderLeaderboard()` podium (top 3) + rows + pinned "you".

### 7.h Dashboard / admin (owner only)

**`openAdmin()`** (2004): `show("admin")`, `GET /admin/overview?token=…`. Renders owner name, counts (`total/active/pending/blocked`), a **"Require own keys"** switch `#reqKeysSw`, a **"Reset test users"** wipe button `#wipeBtn`, a **free-access email** manager (`#offEmail`/`#offAddBtn` + per-email Remove), and a per-user card list. Each user card shows role/status/mode/level/XP/streak/sessions/minutes/words + last-7-days activity, with action buttons: **Approve** (if not active), **Block/Unblock**, **Delete** (not for owner). Actions:
- `adminAction(id, action)` (1998) → `POST /admin/action {token, target_id, action}` (delete confirms first), then refresh.
- `#reqKeysSw` onchange (2050) → `POST /admin/settings {token, require_own_keys}`.
- `officeEmail(email, action)` (2061) → `POST /admin/office {token, email, action}` (add/remove).
- `#wipeBtn` (2054) → `POST /admin/wipe {token}` (deletes all except david, shuhani & free-access).

**Keys / BYOK** (`#keys`, `loadKeysUI()` 1947): Personal vs Office toggle (`useMode` in `localStorage.dusu_usemode`, `postMode()`→`POST /mode`). Key inputs Gemini/OpenRouter/GitHub/Groq. **`#verifyKeys`** (1971) → `POST /keys/verify {token, keys}`; needs **≥2 working keys** to pass — on success sets `localStorage.dusu_keys_ok="1"`, saves `dusu_office_keys`, and `routeAfterLogin()`. Gating helpers (1747-1773): `officeKeys()`, `officeAllowed()` (free_access/owner/unlimited), `keyCount()`, `keysVerified()`, `hasOwnKeys()` (≥2 & verified), `needsKeys()` (global switch on & not free), `mustAddKeys()`, and `guardKeys()` which redirects to the keys screen and returns `true` to block a session start.

### 7.i speak/say + SpeechRecognition + `speakable()`

- **`speakable(t)`** (2361): strips emoji/pictograph/arrow Unicode ranges so TTS doesn't read icon names, collapses `____` blanks and `----`/`====`/`**` markdown runs, and squeezes whitespace. Applied by every speak path.
- **`speak(text)`** (2412): the conversation-loop speaker (echo-guarded, watchdog'd, animates `FACE`/`Assistant`, auto-listens after).
- **`say(text, opts)`** (2538): a single **awaitable** utterance (returns a Promise) with its own watchdog and no pre-cancel — used everywhere sequencing matters (assessment, learning, daily). Voice profiles: `HI()` = `hi-IN`/rate 0.95, `ENG_SLOW()` = `en-IN`/rate 0.8, `ENG_NORM()` = `en-US`/rate 1.0 (3533-3535).
- Voice selection (2370-2410): `loadVoices()`/`pickVoice()` prefer **local (offline)** English voices (Edge "Natural" online voices often play silent), match `FEMALE_RE`/`MALE_RE`, and pick a natural `hindiVoice`. The header `.voicebar` `.vbtn` toggles `voiceGender` (persisted in `dusu_voice`; male button is `display:none`).
- Cartoon faces via `makeFace()` (1785): `FACE` (session `#eyes`), `HOMEFACE` (`#hEyes`), `DAILYFACE` (`#dEyes`) — procedural lip-sync (`startTalking/boundary/stopTalking`) + auto-blink. `Assistant` (1821) is the PNG-portrait path, disabled (`USE_PNG=false`) so the animated SVG is used.

### 7.j Auth, routing & localStorage keys

Boot: `authToken`=`dusu_token`, `authUser`=`dusu_user`, `userState`=null (3828-3830). `initAuth()` (4101): if `!AUTH_ENABLED` skip to home; else if token cached → `applyUser` + restore `dusu_state` + `routeAfterLogin()` + `refreshMe()`; else `show("login")`. Google callback `onGoogle(resp)` (4075) → `POST /auth/google {credential}` → stores token/user/onboarded; new user (`onboarded===false`) → `refreshMe()` (which routes to the guarded test), else `speakWelcome()` + `refreshMe()`. **`routeAfterLogin()`** (4045) is the one gate: keys (if `needsKeys() && !hasOwnKeys()`) → level test (if `onboarded===false`) → home. `refreshMe()` (4060) `GET /me` (Bearer; 401→`logout()`), caches full state to `dusu_state`. `logout()` (4034) clears all `dusu_*` keys and returns to login.

**localStorage keys used:** `dusu_token`, `dusu_user`, `dusu_state`, `dusu_onboarded`, `dusu_letter`, `dusu_daily_resume`, `dusu_keys_ok`, `dusu_usemode`, `dusu_office_keys`, `dusu_voice`, `dusu_usage`, `dusu_think`.

**Session limit:** `MAX_SESSIONS = Number("__MAX_SESSIONS__") || 20` (3857), tracked client-side in `dusu_usage` (`{d:date, n:count}`); `overLimit()`/`usageInc()`/`refreshUsage()` (3864-3877). `isUnlimited()` true for role owner/unlimited or `OWNER_EMAILS=["david123rana@gmail.com"]`.

**Backend endpoints the client calls:** WS `/ws/interview`; `POST /auth/google`, `GET /me`, `POST /mode`, `POST /keys/verify`, `POST /leveltest/gen`, `POST /assessment`, `POST /greeting`, `POST /letter`, `POST /checkin`, `GET /leaderboard`, `GET /admin/overview`, `POST /admin/action`, `POST /admin/settings`, `POST /admin/office`, `POST /admin/wipe`. **WS server→client message types** (`onMessage`, 2334): `ready`, `translation`, `daily_question`, `daily_turn`, `translate_error`, `ai_text`, `interview_done`, `report`, `ended`, `limit`, `quota`, `keys_required`, `auth_error`, `error`. **WS client→server:** `{type:"start", …}`, `{type:"user_text", text}`, `{type:"end"}`. PWA: `/manifest.webmanifest` + `/sw.js` registered on load (4128).

---

## 8. Mobile Apps, Cloudflare, Deploy & Dev/Ops

DuSu is a **single FastAPI service** (`backend/app/main.py`) that serves the frontend (`GET /` → `test_client.html`), the PWA manifest/service-worker, Google auth, and the `/ws/interview` WebSocket. Speech (STT/TTS) runs in the user's browser via the Web Speech API; the LLM is **OpenRouter** (called server-side). Everything below wraps that one service in a phone app, an edge front-door, and a $0 deploy.

### 8.1 Why a TWA, not a WebView (the whole reason `android-twa` exists)

DuSu's core feature is voice: mic speech-to-text + text-to-speech via the browser **Web Speech API**. A plain Android **WebView does not implement `SpeechRecognition`** — mic input silently breaks. The fix is a **Trusted Web Activity (TWA)**: it renders the live site full-screen *on the device's own Chrome engine*, so Web Speech STT/TTS behave exactly as in the browser.

Two Android modules exist; only the TWA is current:

| Module | Package | Status | What it does |
|---|---|---|---|
| `android-twa/` | `com.dusu.app` | **CURRENT** | Runs the site full-screen inside the app on Chrome's engine (TWA). Voice works. |
| `android-launcher/` | `com.dusu.launcher` | **DEPRECATED** | Old shim: a "Start DuSu" button that kicks the user out to *external* Chrome. minSdk 26. Has a `.github/workflows/build-apk.yml` cloud build. Kept only for side-by-side install (distinct package id). Do not develop further. |

Repo-root APKs: `DuSu-app.apk` (~3.1 MB, the TWA — this is the one you ship) and `DuSu.apk` (~5.9 MB, older). The build output is manually copied to `DuSu-app.apk` at repo root.

### 8.2 `android-twa` — the app

- **Loads:** `https://dusu-app-1.onrender.com/` (`strings.xml` → `launchUrl` / `hostName`).
- **IDs & SDK:** `applicationId = com.dusu.app`, `namespace = com.dusu.app`, `minSdk 21` (TWA runs on the device's Chrome, so old Android is fine), `compileSdk 34`, `targetSdk 34`, `versionCode 1` / `versionName "1.0"`, portrait-locked.
- **Toolchain (all version-locked, do NOT bump casually):**

| Thing | Version | Why pinned |
|---|---|---|
| `com.google.androidbrowserhelper:androidbrowserhelper` | **2.5.0** | 2.7.x pulls androidx.browser 1.10 / core 1.17 which demand **AGP 8.9.1 + compileSdk 36**. 2.5.0 (browser 1.4, core 1.7) builds clean on AGP 8.5.2 / SDK 34 and has every TWA feature used. |
| Android Gradle Plugin | 8.5.2 | matches SDK 34 setup |
| Kotlin | 1.9.24 | |
| `androidx.core:core-ktx` | 1.13.1 | `NotificationCompat` for reminders |
| Gradle wrapper | 9.3.0 | needs JDK 17+ |

**Launch path (critical, non-obvious):** `MainActivity` is the real `LAUNCHER` activity and it starts the TWA **directly** with `TwaLauncher(this).launch(url)` (see `MainActivity.kt` `launchDuSu()`). The manifest still *declares* `com.google.androidbrowserhelper.trusted.LauncherActivity` (with `DEFAULT_URL`, status/nav-bar color meta-data, `FALLBACK_STRATEGY=customtabs`, `autoVerify` intent-filter) — but that sub-activity is **not** used as the entry point; relying on it as the launcher no-ops for our flow. `MainActivity` is what runs.

**What `MainActivity.kt` does on start:**
1. Installs an uncaught-exception handler that writes the stack trace to `filesDir/last_crash.txt`. On next launch, if that file exists, it shows a **scrollable on-screen crash reporter** (white text on `#070A14`, selectable, "Clear & retry" button) instead of launching — lets you screenshot a crash with no USB/adb.
2. Shows a **splash** (`activity_main.xml` → `dusu_logo` + "Speak with Confidence" tagline) for ~1.2 s.
3. **Offline gate:** `isOnline()` checks `ConnectivityManager` for `NET_CAPABILITY_INTERNET`. Offline → 📡 "No Internet Connection" screen with a gold **Retry** button (`decide()` re-checks). Online → `launchDuSu()`.
4. `Notifications.createChannel()` + `scheduleEvery4Hours()` + requests `POST_NOTIFICATIONS` (Android 13+).
5. On return from the TWA (`onResume` with `launched=true`) it `finish()`es the shim.

**4-hour reminders** (`Notifications.kt`, `ReminderReceiver.kt`, `BootReceiver.kt`): local, no server. `AlarmManager.setInexactRepeating(RTC_WAKEUP, first=+4h, FOUR_HOURS_MS)`, channel id `dusu_reminders`, notif id `1001`. Message rotates by 4-hour slot from `strings.xml` `notif_messages` (`"title||body"` split on `||`, 6 messages). `BootReceiver` re-arms after `BOOT_COMPLETED` (alarms clear on reboot). Tapping opens `MainActivity`.

**Manifest permissions:** `INTERNET`, `ACCESS_NETWORK_STATE`, `POST_NOTIFICATIONS`, `RECEIVE_BOOT_COMPLETED`; a `<queries>` for `CustomTabsService` (Android 11+ package visibility, required to bind Chrome's Custom Tabs).

**Icon** (`gen_icons.py`, run via `backend/.venv/Scripts/python.exe android-twa/gen_icons.py`): slices `android-twa/icon-master.png` (the gold "D-mark" — a serif D whose counter is a woman's face + speech-bubble + sound-waves, per `DUSU_ICON_BRIEF.md`) into legacy mipmaps (48→192), adaptive **foreground** layers (108dp canvases 108→432), the splash `drawable/dusu_logo.png` (512), and `play-icon-512.png`. **Adaptive icon** = `mipmap-anydpi-v26/ic_launcher.xml` (+ `_round`): `<background>` = solid navy `@color/twaBackground` (`#070A14`), `<foreground>` = the mark. Theme (`themes.xml`) sets dark `windowBackground` + status/nav bar to `#070A14` to avoid a white flash.

### 8.3 Building the APK

```bash
cd android-twa
./gradlew assembleDebug     # → app/build/outputs/apk/debug/app-debug.apk (self-signed, installable now)
./gradlew assembleRelease   # needs keystore.properties → app-release.apk
./gradlew bundleRelease     # AAB for Play Store
adb install -r app/build/outputs/apk/debug/app-debug.apk
# then copy the built APK to repo root as DuSu-app.apk
```

**BUILD GOTCHA — `JAVA_HOME` must be a real JDK 17.** Point `JAVA_HOME` at a standalone JDK 17 (e.g. `C:\Program Files\Microsoft\jdk-17...`), **not** the Android Studio bundled JBR. The bundled `jbr` causes Gradle/AGP toolchain failures here; the build config compiles against `VERSION_17` / `jvmTarget "17"` and Gradle 9.3.0 requires JDK 17+.

- `local.properties` → `sdk.dir=C:\Users\LENOVO\AppData\Local\Android\Sdk` (git-ignored, machine-specific — recreate on a new laptop).
- Release signing is **optional & lazy**: create `android-twa/keystore.properties` (git-ignored) with `storeFile`/`storePassword`/`keyAlias`/`keyPassword`. If absent, `assembleRelease` still runs but the APK is unsigned; use debug for testing. `gradle.properties`: `-Xmx2048m`, `useAndroidX=true`, `nonTransitiveRClass=true`.

**Full-screen (drop the Chrome address bar) needs Digital Asset Links — a two-sided handshake:**
- **App side** (already declared): `strings.xml` `asset_statements` trusts `https://dusu-app-1.onrender.com`.
- **Server side:** backend serves `GET /.well-known/assetlinks.json` (`main.py`) built from env `ANDROID_CERT_SHA256` (comma/newline-separated SHA-256 fingerprints, upper-cased) and `ANDROID_TWA_PACKAGE` (default `com.dusu.app`). Get the fingerprint via `keytool -list -v` on the debug or release keystore, set it on Render, then `curl -s https://dusu-app-1.onrender.com/.well-known/assetlinks.json` to verify. Reinstall the app; Chrome verifies both directions and runs edge-to-edge. Until verified it still opens — inside a Custom Tab bar (speech already works, the bar just isn't hidden). For Play App Signing, add **both** the upload-key and the Play-issued app-signing SHA-256.

### 8.4 Cloudflare failover (`cloudflare/` — PLANNED, not yet deployed)

Goal: one stable origin `https://dusu.ranabrothers.online` (a Cloudflare **Worker**) that serves DuSu from **your PC** when it's on and **Render** when it's off — same DB either way.

```
app / users → https://dusu.ranabrothers.online   (Worker: cloudflare/worker.js)
                 │ PC healthy? ──yes─► https://pc.ranabrothers.online → cloudflared → PC :8000
                 │              └─no─► https://dusu-app-1.onrender.com  (Render fallback)
                 ▼
              Neon Postgres   (single DB used by BOTH — no data split)
```

- `worker.js`: `pcHealthy(PC)` probes `PC_ORIGIN/health` with a 1.5 s timeout, result cached ~10 s in the edge cache (`caches.default`). Picks PC else CLOUD, forwards the original request **verbatim** (headers + body + WS `Upgrade`). Mid-flight failure retries CLOUD **only for plain HTTP** (a WebSocket can't be retried after upgrade); otherwise returns a 502 text. WS (`/ws/interview`) passes through.
- `wrangler.toml`: `name = dusu-failover`, route `dusu.ranabrothers.online/*` on zone `ranabrothers.online`; `[vars] PC_ORIGIN = https://pc.ranabrothers.online`, `CLOUD_ORIGIN = https://dusu-app-1.onrender.com`.
- **DB decision = Option A (single Neon), FINAL** (`DUSU_LOCAL_CLOUDFLARE_PLAN.md`): only *compute* is local-first; the DB is always Neon so PC/Render never diverge. Local SQLite is intentionally NOT used. The PC backend must point `DATABASE_URL` at the **same Neon URL** Render uses.
- Setup (all interactive, run by the human — see `cloudflare/README.md`): run backend on PC → `cloudflared` tunnel `dusu-pc` routed to `pc.ranabrothers.online` (installed as an always-on Windows service) → `wrangler deploy` + a **proxied** placeholder DNS record for `dusu` → only then repoint the app's `strings.xml` (`launchUrl`/`hostName`/`asset_statements`) to the Worker origin and add that origin to Google OAuth JS origins. Cost ≈ $0 (domain + free Cloudflare/Neon/Render tiers).
- **Status: none of the Cloudflare infra is deployed yet.** Only the app-side items (offline gate, 4h notifications) from that plan are built.

### 8.5 Deploy (Render — live, $0)

- **Repo:** `git@github.com:davidrana123/dusu-app.git`, branch **`main`**. **Render auto-deploys on every push to `main`.**
- **Live URL:** `https://dusu-app-1.onrender.com`.
- **Root dir:** `backend/`. **Build:** `pip install -r requirements.txt`. **Start:** from `backend/Procfile` → `web: uvicorn app.main:app --host 0.0.0.0 --port $PORT`. **Python:** `backend/runtime.txt` → `python-3.12.7`. No `render.yaml` (config is in the Render dashboard).
- `backend/requirements.txt`: fastapi 0.115.6, uvicorn[standard] 0.34.0, websockets 14.1, openai 1.59.6 (OpenRouter is OpenAI-compatible), pydantic 2.10.4, pydantic-settings 2.7.1, python-dotenv 1.0.1, google-auth 2.38.0, requests 2.32.3, sqlalchemy 2.0.36, asyncpg 0.30.0, greenlet 3.1.1.

**Required Render env vars:**

| Var | Purpose |
|---|---|
| `DATABASE_URL` | Neon Postgres URL (asyncpg). Absent → DB features no-op. |
| `OPENROUTER_API_KEY` + `OPENROUTER_BASE_URL` | LLM (OpenRouter, `https://openrouter.ai/api/v1`) |
| `LLM_MODELS` | comma-separated free-model fallback chain |
| `GOOGLE_CLIENT_ID` | Google Sign-In (login required when set) |
| `SESSION_SECRET` | signs DuSu session tokens |
| `ANDROID_CERT_SHA256` | APK signing fingerprint(s) → served in `/.well-known/assetlinks.json` |
| `ANDROID_TWA_PACKAGE` | optional, defaults to `com.dusu.app` |

`.env.example` documents these; real secrets go in `backend/.env` (git-ignored via `backend/.gitignore` → `.env`, `.venv/`, `users.db`, `__pycache__/`). Free tier caveat: the service **sleeps after ~15 min idle** (cold start ~30–50 s).

**Service worker / cache busting** (`backend/sw.js`, served at `/sw.js` with `Cache-Control: no-cache` + `Service-Worker-Allowed: /`; registered from `test_client.html` line ~4130): cache name is **`dusu-v5`** — **bump this constant** on any shell/asset change or clients keep the old cache. `activate` deletes all other caches. Navigations are **network-first** (so a new deploy shows immediately, falling back to cached `/` offline); static assets are cache-first-then-network. **Never cached** (live/per-user): paths starting `/ws`, `/auth`, `/me`, `/health`, `/lesson`, `/level`, `/assessment`, `/admin`, `/keys`, `/mode`, `/.well-known` (and all non-GET). PWA install comes from `manifest.webmanifest` (standalone, portrait, `#070a14`, icons from `/logo.png`).

### 8.6 Local dev

```powershell
# backend (from repo root)
cd "C:\Personal Work\English Specking\backend"
.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
# → open http://127.0.0.1:8000/  (health: /health → {"ok":true,"has_key":..,"providers":[..]})
```

Secrets in `backend/.env` (never committed). For local-first parity, `DATABASE_URL` should be the same Neon URL as prod.

### 8.7 Verification workflow & hard-won lessons

- **`import app.main` before every deploy.** Run the module import (e.g. `python -c "import app.main"` in the backend venv) to catch **runtime import / `NameError`s that `ast.parse` (syntax check) does NOT catch**. A `TokenIn` `NameError` once crashed the deploy on boot because it passed a syntax check but blew up at import time — always do the real import.
- **Frontend inline JS:** validate `test_client.html`'s inline `<script>` with **`node --check`** / a `vm.Script` compile, not by eye — a single syntax error white-screens the whole app.
- **Poll live after deploy:** `curl` the live URL (or `/health`) for a known marker string to confirm the new build actually went out before declaring success (Render auto-deploy + cold start means "pushed" ≠ "live yet").
- **LF/CRLF git warnings are harmless** on this Windows repo — ignore them.

### 8.8 Known issues / Pending / Deferred

- **App crash diagnosis** relies on the on-screen crash reporter (`last_crash.txt`); root-cause of any TWA launch crash still to be confirmed on a real device.
- **Cloudflare local-first infra is NOT deployed** — Worker, `cloudflared` tunnel, `pc.ranabrothers.online` DNS, and repointing the app to `dusu.ranabrothers.online` are all pending. App still points at Render directly.
- **Full lock screen for blocked/quota-exhausted users** not implemented app-side.
- **DB-encrypted key storage (BYOK)** — user-supplied LLM keys are not yet encrypted at rest (see `DUSU_BYOK_PLAN.md`).
- **Play Store** listing not published (AAB build path exists; needs both upload + Play App Signing SHA-256 in `ANDROID_CERT_SHA256`).
- **`android-launcher` is deprecated** and should be removed once the TWA is fully validated.
- Free-tier **Render cold starts** (~30–50 s) remain; no keep-alive pinger configured.

---

## Quick command reference

```powershell
# Local run — from repo root, backend served on 127.0.0.1:8000
cd "C:\Personal Work\English Specking\backend"
.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
# health check: http://127.0.0.1:8000/health
```

```bash
# Import check — run from backend/; catches runtime import / NameErrors a syntax check misses
backend/.venv/Scripts/python -c "import app.main"
```

```bash
# Android build — from android-twa/; JAVA_HOME must be a real standalone JDK 17 (not the Studio JBR)
export JAVA_HOME="/c/Program Files/Microsoft/jdk-17..."   # PowerShell: $env:JAVA_HOME = "C:\Program Files\Microsoft\jdk-17..."
cd android-twa
./gradlew assembleDebug        # → app/build/outputs/apk/debug/app-debug.apk  (copy to repo root as DuSu-app.apk)
```

```bash
# Deploy — Render auto-deploys on push to main; then poll the live URL to confirm it went out
git push origin main
curl -s https://dusu-app-1.onrender.com/health
```
