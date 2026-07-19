# DuSu

> **Speak with confidence.**
> An AI voice partner that helps people get fluent and confident at speaking — through real conversation, not lessons.

---

## What is DuSu?

DuSu is a **voice-first AI speaking coach**. You talk out loud; DuSu listens, replies with a natural voice, and keeps the conversation going. No grammar drills, no flashcards — just real spoken practice that builds fluency and confidence.

Most "English apps" teach *English*. DuSu trains the thing people actually freeze up on: **speaking to another human** — in a chat, in an interview, under pressure.

**One line:** *Practice speaking, the way it really happens.*

---

## Who it's for

- Freshers and students preparing for **job interviews** and campus placements.
- People who *know* English but freeze when they have to **speak** it.
- Non-metro / non-native speakers who want low-pressure practice with no judgment.
- Anyone building confidence for interviews, IELTS speaking, presentations, or daily conversation.

Primary wedge: **India — freshers + placement season.**

---

## How it works

```
You speak  ──►  DuSu listens (speech→text)  ──►  DuSu thinks (AI)
    ▲                                                   │
    └────────  DuSu replies out loud (text→speech)  ◄───┘
```

- **Voice in, voice out.** No typing. Feels like a real conversation.
- **Adaptive.** DuSu reacts to what *you* said and follows your lead — never a fixed script.
- **Real-time state cues.** An animated orb always shows what's happening: *listening · thinking · speaking* — so you're never confused about whose turn it is.

---

## Modes

DuSu is built around **modes** — different ways to practice. Two are live now; more are planned.

### 🟢 Free Conversation *(live)*
Just talk. No goal, no ending. DuSu keeps the chat flowing, reacts warmly, and follows whatever you're excited about. If you go quiet, it gently offers an easy new topic. The point is simple: **get comfortable speaking** with zero pressure.

### 🟣 Interview Prep *(live)*
A realistic mock interview. DuSu plays a warm-but-professional interviewer, asks adaptive follow-ups (mentions a project → gets asked about it), and covers the competencies a real interview does. Ends with a **detailed scored report**:
- Overall score + breakdown (grammar, fluency, confidence, communication, vocabulary, professionalism)
- Filler words you used
- Your strengths
- Concrete fixes
- A stronger rewrite of your weakest answer

### 🔜 Coming soon
Group Discussion · IELTS Speaking · Sales Pitch · HR / Technical / Managerial rounds · Presentation practice.

---

## What makes DuSu different

The advantage is **not** "AI voice" — many apps have that. DuSu's edge is the **conversation intelligence**:

- **Adapts** to every answer instead of reading fixed questions.
- **Stays in character** (warm friend vs. professional interviewer).
- Evaluates both **what** you say (content) and **how** you say it (delivery).
- Makes progress **visible** — measurable improvement over time.
- Clear, calm UX so a nervous first-time user always knows what to do.

---

## Product principles

1. **Voice first.** Speaking is the skill; typing is a fallback, not the point.
2. **No judgment.** Encourage, model good English by example — never lecture or correct mid-flow.
3. **Show, don't confuse.** Every state (listening / thinking / speaking) is always visible.
4. **Outcome over lessons.** Sell confidence and interview readiness, not grammar.
5. **Start free, feel premium.** Zero-friction entry, polished experience.

---

## How DuSu is built (v0)

Fully working MVP, **$0 running cost**:

| Layer | Choice | Notes |
|-------|--------|-------|
| **Frontend** | Single premium web app | Dark, glass UI + animated voice orb; Chrome/Edge |
| **Speech-to-text** | Browser **Web Speech API** | Free, in-browser, no key |
| **Text-to-speech** | Browser **speechSynthesis** | Free, in-browser, no key |
| **Brain (AI)** | **OpenRouter free models** | OpenAI-compatible; fallback chain across free models |
| **Backend** | **FastAPI + WebSocket** | Text-only wire — audio never leaves the browser |

- Server only ever exchanges **text** — all audio stays local.
- Free models get rate-limited, so the backend walks a **fallback list** of models until one answers.
- Model is one env var → swap in a paid model later for higher quality with no code change.

> Details: see `backend/README.md`. Full go-to-market and roadmap: see `AI-Interview-Coach-Plan.md`.

---

## Roadmap (short)

- **Now:** two modes (Conversation, Interview) + scored report — ✅ live.
- **Next:** polish report UI, save history, add technical/HR interview rounds.
- **Later:** streaks & progress tracking, company-specific interview packs, video mode, institute/college dashboard (B2B2C).

---

## Brand

- **Name:** DuSu
- **Tagline:** *Speak with confidence.*
- **Logo:** `Logo.png` — gold + silver serif wordmark on deep navy, with a face-in-speech-bubble + voice-wave motif and a mic. Live in the app (header + hero); served at `/logo.png`.
- **Palette:** deep navy / near-black (`#070a14`–`#0e1428`) + **gold** gradient (`#f5d97a → #d4af37 → #b8860b`), champagne text. Accents: teal-green (listening), warm amber (thinking).
- **Type:** elegant serif display (Cormorant Garamond) + clean sans body (Inter) — matches the logo's serif wordmark.
- **Feel:** premium, luxurious, calm, encouraging. Dark glass surfaces with soft gold glow.
- **Voice of DuSu (personality):** warm, upbeat, supportive — like a friend who's genuinely rooting for you.

---

*This file is the living product overview for DuSu. Update it as modes, brand, and roadmap evolve.*
