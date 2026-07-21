# DuSu — Complete Feature Map

> Purpose of this doc: one place that lists **every feature**, **why it exists**, **where it lives (screen)**, **how a user reaches it**, and **how it works (frontend → backend → data)** — so functionality can be re-structured with full context.
>
> Last mapped: 2026-07-21. Source of truth: `backend/test_client.html` (single-file web app), `backend/app/*.py` (API), `android-launcher/` (APK).

---

## 0. Architecture at a glance

| Layer | Tech | Files |
|---|---|---|
| Web app (UI + all client logic) | Single HTML file, vanilla JS/CSS | `backend/test_client.html` (~2900 lines) |
| API server | FastAPI (Python) | `backend/app/main.py` |
| Auth | Google Sign-In + token | `backend/app/auth.py` |
| Data | DB layer (users, progress, memory) | `backend/app/db.py` |
| Config | providers/keys | `backend/app/config.py` |
| Voice | Browser Web Speech API (STT + TTS) | in `test_client.html` |
| AI | Multi-provider fallback: **gemini · groq · openrouter · github** | `main.py` |
| Real-time | WebSocket `/ws/interview` (drives all 4 speaking modes) | `main.py` |
| Android launcher | Native Kotlin app → opens web app in Chrome | `android-launcher/` |
| Hosting | Render (live) + local dev (`127.0.0.1:8000`) | — |

**Serving model:** `GET /` reads `test_client.html` per request, injects Google client id + auth flags. No build step.

---

## 1. Screens (the 11 "pages")

All screens are `<section class="screen">`; JS `show(id)` toggles the `.on` class. Single-page app.

| # | Screen id | Name | Reached from |
|---|---|---|---|
| 1 | `login` | Sign in | first load |
| 2 | `home` | Home / hero | after sign-in |
| 3 | `setup` | Interview setup (pick role) | home → Interview Prep card |
| 4 | `learning` | Learning Mode | home → Learning card |
| 5 | `daily` | Daily Talk with DuSu | home → Continue your Journey |
| 6 | `assessment` | Level assessment (onboarding) | first login (not onboarded) |
| 7 | `journey` | My Journey / roadmap | home → "View my roadmap" |
| 8 | `leaderboard` | Leaderboard | home → "Leaderboard" |
| 9 | `lesson` | A single lesson | journey → tap a lesson |
| 10 | `session` | Live speaking (Confidence Talk + Interview) | home → Start Speaking / Interview |
| 11 | `report` | Interview scored report | end of interview |

---

## 2. Feature inventory (~38 features, grouped)

### A. Core speaking modes — the product (WS `/ws/interview`, `mode` param)

| # | Feature | Purpose | Screen | How reached | How it works |
|---|---|---|---|---|---|
| 1 | **Learning Mode** | Beginner bridge: speak Hindi → get natural English → repeat | `learning` | Home → explore → Learning card | Mic (hi-IN STT) → WS `user_text` → server `translation` → DuSu says Hindi intro + English (slow 0.8x) + "mere baad dohraiye" + 3s gap + English again |
| 2 | **Confidence Talk** | Free-flow English chat, build fluency, no pressure | `session` | Home → **Start Speaking** (or Talk card / curio card) | WS `start mode=conversation` → `ai_text` turns; browser TTS speaks; animated face (FACE) |
| 3 | **Interview Prep** | Realistic mock interview + scored report | `setup`→`session`→`report` | Home → Interview card → role → start | WS `start mode=interview`; adaptive follow-ups; `report` event → `report` screen |
| 4 | **Daily Talk** | AI companion: talk about your day, learn from it | `daily` | Home → **Continue your Journey** | WS `start mode=daily` (sends mood + hour) → `daily_question`/`daily_turn`; DuSu praises + gives next question; DAILYFACE animates |

### B. Learning journey / roadmap

| # | Feature | Purpose | Screen | How reached | How it works |
|---|---|---|---|---|---|
| 5 | **Assessment** | Onboarding: find CEFR level, set start level + daily goal | `assessment` | first login | form → `POST /assessment` → `_start_level`, `_daily_goal` stored |
| 6 | **My Journey / roadmap** | 7-level path with lessons + boss challenges | `journey` | Home → roadmap link | `CURRICULUM` (7 levels, client) + `userState.progress.journey` (completed map) |
| 7 | **Lessons** | Bite-size speaking practice per level | `lesson` | journey → tap lesson | mic → `POST /lesson/evaluate` (scored) → `POST /lesson/complete` (XP, badges) |
| 8 | **Level tests** | Unlock next level | `journey`/`lesson` | end of a level | `POST /level/test/submit` (score) → unlock + XP |
| 9 | **Boss challenges** | Milestone goal per level ("Speak 2 min without stopping") | `journey` | within roadmap | flag in CURRICULUM; courage badges on success |

### C. Emotional / companion layer

| # | Feature | Purpose | Screen | How reached | How it works |
|---|---|---|---|---|---|
| 10 | **Daily mood check-in** | Personalize tone to how user feels | home (`moodRow`) | shown on home (onboarded) | buttons → `POST /checkin` → `todayMood` shapes greetings + session mood |
| 11 | **Weekly letter from DuSu** | Emotional retention: a written note | home (`letterCard`) | shown on home | `POST /letter` (AI-generated, saved) |
| 12 | **Letter to Future Me** | Motivation: message to future self | (onboarding/journey) | `POST /futureme` | `save_future_me` |
| 13 | **Memory** | DuSu "remembers" nickname, dream, facts | all | passed into prompts | `db.py` Memory (facts/events/summaries), `merge_facts` |
| 14 | **Event banner / greeting** | Contextual greeting hook | home (`eventBanner`) | shown on home | client renders from memory/events |
| 15 | **Courage badges** | Reward brave moments (spoke w/o Hindi, asked a Q, 5-min talk) | journey/badges | awarded in-session | `award_badges` (courage_*) |

### D. Progress / gamification

| # | Feature | Purpose | Screen | How reached | How it works |
|---|---|---|---|---|---|
| 16 | **XP** | Sense of earning | journey/leaderboard | after sessions/lessons | `record_practice(xp=20)`, `complete_lesson` |
| 17 | **Streak** | Habit / daily return | home strip, journey | derived | `progress.streak_days` |
| 18 | **Badges** | Milestones (first lesson, 100 sentences, level up…) | journey | awarded | `award_badges`, `BADGE_LABELS` |
| 19 | **Leaderboard** | Social competition | `leaderboard` | home → Leaderboard | `GET /leaderboard` (aliased names, podium + list + you) |
| 20 | **Daily goal** | Small daily target | journey | derived | `_daily_goal`, `sessions_today` |
| 21 | **Sentences spoken** | Volume of practice | home strip | derived | `journey.sentences_spoken`, `bump_daily_stat` |
| 22 | **Practice time (seconds)** | Time invested *(tracked, barely surfaced)* | — | recorded | `record_practice(seconds)` — **data exists, not shown yet** |

### E. Home / UX (recent work — the "alive" layer)

| # | Feature | Purpose | Screen | How reached | How it works |
|---|---|---|---|---|---|
| 23 | **Living DuSu** | Connection: she watches + reacts | home hero | move mouse / hover Start | JS moves `#hEyes` + `#hchar` toward cursor; `homeHappy()` swaps `#hSmile` + glow on Start hover |
| 24 | **Rotating daily headline + time greeting** | Curiosity + feels alive daily | home hero | on home load | `setWelcome()` picks `HERO_LINES[dayOfYear % n]` + morning/afternoon/evening + name |
| 25 | **Transformation strip** | Commitment: "becoming, not stats" | home hero | onboarded + has progress | `renderGrowth()` from streak/level/sentences → chips + italic line |
| 26 | **Curiosity card** | "🎁 Today's challenge" pull | home (reveal) | explore | routes to Confidence Talk |
| 27 | **Mode cards (3)** | Choose a path (as outcomes) | home (reveal) | explore | premium accent-tinted cards → chooseMode |
| 28 | **Progressive discovery** | Keep first paint pure | home | "See what DuSu can do →" | reveals `#moreHome` |
| 29 | **Voice gender toggle** | Preference | header | header ♀/♂ | picks TTS voice |
| 30 | **Session limit chip** | Usage / fair-use | header | shown | `MAX_SESSIONS` localStorage; owner unlimited |

### F. Account / infrastructure

| # | Feature | Purpose | How it works |
|---|---|---|---|
| 31 | **Google Sign-In** | Identity | GSI → `POST /auth/google` → token; `GET /me` restores state |
| 32 | **Daily session limit** | Cost control | `MAX_SESSIONS` (localStorage), `OWNER_EMAILS` unlimited |
| 33 | **PWA / installable** | App-like | `/manifest.webmanifest`, `/sw.js` |
| 34 | **Multi-provider AI fallback** | $0 uptime | gemini → groq → openrouter → github |
| 35 | **Browser voice (STT+TTS)** | $0 voice | Web Speech API (Chrome/Edge) |

### G. Android launcher (separate app: `android-launcher/`)

| # | Feature | Purpose | How it works |
|---|---|---|---|
| 36 | **Launcher app** | Home-screen icon → opens DuSu in Chrome (voice works) | Kotlin, no WebView |
| 37 | **Daily reminder notifications** | Retention | 10-message rotating pool, ~7PM, AlarmManager + boot re-schedule |
| 38 | **Offline detection** | Graceful | checks connectivity → "no internet" + Retry |

---

## 3. Navigation map

```
login ──(sign in)──> [first time?] ──yes──> assessment ──> home
                                     └─no──> home

home
 ├─ Start Speaking ─────────────> session (Confidence Talk) ─(interview only)─> report
 ├─ Continue your Journey ──────> daily
 ├─ See what DuSu can do ↓ (reveal)
 │    ├─ 🎁 Today's challenge ──> session (Confidence Talk)
 │    ├─ Learning card ─────────> learning
 │    ├─ Confidence Talk card ──> session
 │    ├─ Interview card ────────> setup ──> session ──> report
 │    ├─ roadmap link ──────────> journey ──> lesson
 │    └─ leaderboard link ──────> leaderboard
 └─ header: voice toggle · usage · sign out
```

---

## 4. API endpoints (`main.py`)

| Method | Path | Purpose |
|---|---|---|
| GET | `/` | serve web app |
| GET | `/health` | status + providers |
| GET | `/logo.png`, `/manifest.webmanifest`, `/sw.js` | assets / PWA |
| POST | `/auth/google` | sign in → token |
| GET | `/me` | restore user state |
| GET | `/leaderboard` | ranked users |
| POST | `/assessment` | onboarding result → level/goal |
| POST | `/checkin` | daily mood |
| POST | `/futureme` | letter to future self |
| POST | `/letter` | weekly letter from DuSu |
| POST | `/lesson/evaluate` | score a spoken answer |
| POST | `/lesson/complete` | finish lesson → XP/badges |
| POST | `/level/test/submit` | level test → unlock |
| WS | `/ws/interview` | **all 4 speaking modes** |

### WebSocket protocol
- **Client → server:** `{type:"start", mode, name, role, token, mood, hour}` · `{type:"user_text", text}` · `{type:"end"}`
- **Server → client:** `ready` · `translation{hindi,text}` · `daily_question{question}` · `daily_turn{hindi,english,praise,next_question}` · `ai_text{text}` · `report{data}` · `interview_done` · `ended` · `limit{msg}` · `auth_error` · `error{msg}`

---

## 5. Data model (`db.py`) — what's stored

- **User** (identity), **Profile** (CEFR, goals from assessment), **Progress** (xp, streak_days, sessions_today, daily_goal, badges, journey{start_level, current_level, completed, sentences_spoken})
- **Memory** (facts, nickname, dream, events, recent conversation summaries)
- **Practice** (`record_practice`: seconds + sentences + xp), **daily stats** (`bump_daily_stat`)
- **Letters** (`save_letter`), **Future Me** (`save_future_me`), **check-ins** (`save_checkin`), **daily context** (`save_daily_context`)

Key: `_state()` bundles user+profile+progress+memory → returned by `/me`, `/assessment`, etc. → client `userState`.

---

## 6. Curiosity audit (per feedback: home/hero strong, rest flat)

**Strong now (curiosity + connection):** `login` splash, `home` hero (living DuSu, rotating headline, transformation strip, curiosity card).

**Still "software-like" — candidates to re-structure:**

| Screen | Current feel | Curiosity gap |
|---|---|---|
| `journey` (roadmap) | list of levels/lessons | reads like a syllabus, not an adventure/map. No mystery, no "what's next unlock?" |
| `lesson` | prompt + mic | functional; no story framing or reward reveal |
| `session` (Confidence Talk) | face + mic + state label | good face, but bare; no "moment", no live reaction/insight |
| `report` | scores | stats-heavy; could be transformation-framed ("you improved X") |
| `leaderboard` | podium + list | generic; no personality/rivalry hooks |
| `daily` | face + Q&A | face now fixed; flow still linear/predictable |
| `setup` (interview) | role input | dry form; could tease "your interviewer is waiting" |

**Recurring pattern to fix:** every non-home screen *explains + shows controls immediately*. Apply the home philosophy — **arrive → DuSu reacts → curiosity → one clear action → reward reveal** — to each screen.

---

## 7. Known deferred / not built
- Deeper transformation ("Day 27, first-session date, minutes shown") — *data partly exists (`record_practice` seconds); not surfaced.*
- Festival/birthday/weather greetings
- Spoken "Hi {name}" on first tap · full wave · real anime PNG art
- "AI auto-picks mode after understanding you" (Start Speaking is hard-wired to Confidence Talk)

---

## 8. State of the code
- All recent work (indigo theme, hero rebuild, cards, living DuSu, both faces, learning-mode pacing, launcher notifications, APK) is **on local + web file, uncommitted** unless a commit was made after this doc.
- Live site: Render. Local: `127.0.0.1:8000` (`uvicorn app.main:app`).
