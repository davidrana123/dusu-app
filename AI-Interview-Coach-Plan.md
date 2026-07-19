# AI Interview Coach — A→Z Plan

> Not another English app. A **confidence-for-interviews** app.
> Sell the outcome (a job), not the skill (grammar).

---

## A. Thesis

Not an English app — a **confidence-for-interviews** app. Sell the outcome (job), not the skill (grammar). India TAM is huge: freshers + college placement + IELTS + non-metro English anxiety. The wedge is a voice interview that feels human.

## B. One Killer Metric

**Turn latency** = user stops talking → AI voice starts.

- Target: **< 800 ms**
- Hard ceiling: **1.2 s**

Above that, it feels dead and users churn. Everything below serves this number.

## C. MVP Cut (Be Ruthless)

The temptation is 15 interview types + video + eye contact. Cut all of it.

MVP = **one type: HR / "Tell me about yourself" round for freshers**.

- One persona (friendly HR)
- Voice in, voice out, 3–5 follow-ups, end report
- No gamification, no leaderboard, no premium yet

Ship this in 6 weeks. Everything else is Phase 2+.

## D. Core Loop (the only thing that matters in v1)

```
mic → STT (streaming) → end-of-turn detect → LLM (1 turn) → TTS (stream) → speaker → repeat
```

## E. End-of-Turn Detection (the hidden hard part)

Silence-timeout alone is bad — the user pauses to think, the AI interrupts. Use:

- VAD (voice activity) + ~700 ms silence, **plus**
- A semantic check: is the utterance a complete thought? (cheap fast model or an endpointing model)

Get this wrong and the product feels rude. Budget real engineering time here.

## F. Pipeline Choice — Cascade vs Speech-to-Speech

Two paths:

1. **Cascade** (STT → LLM → TTS): cheap, controllable, you own the scoring/transcript. More latency to engineer away.
2. **Realtime speech-to-speech** (e.g. Gemini Live / OpenAI Realtime): lowest latency, natural interrupts, but pricier + less control over scoring + vendor lock-in.

**Decision: cascade for MVP.** Control + cost + you need the transcript for scoring anyway. Revisit realtime once there is revenue.

## G. AI Stack (concrete)

| Layer | Primary | Notes |
|-------|---------|-------|
| **STT** | Deepgram (streaming) | low latency, cheap. Whisper as batch/scoring fallback |
| **LLM (interviewer)** | small-fast model (Gemini Flash / Haiku / GPT-mini class) | escalate to a large model only for hard technical follow-ups + final report. Routing = your margin |
| **TTS** | OpenAI TTS or Cartesia | ElevenLabs only for premium voices later — too pricey as default |

## H. Latency Budget (allocate the 800 ms)

```
STT partial→final flush   120 ms
end-of-turn decision      150 ms
LLM first token           250 ms   (small model, streamed)
TTS first audio chunk     200 ms
network/buffer             80 ms
--------------------------------
~800 ms to first sound
```

Stream everything. Start TTS on the first LLM sentence, not the full response.

## I. Interviewer Intelligence (the real moat — not "AI voice")

Everyone has voice. The moat is an **adaptive question engine**:

- reads the last answer, picks the next question by rubric (did they cover: role fit, project depth, communication?)
- persona state machine (warmth, strictness)
- covers a **competency checklist** so the report is grounded, not vibes

Store this as a small graph/rubric, not a fixed question list.

## J. Scoring (do it AFTER the call, cheap)

Post-interview batch job over the full transcript + audio:

- **Content:** relevance, structure (STAR), technical correctness
- **Delivery:** fluency, filler words, pace (WPM), pronunciation (from STT confidence), grammar

Use one big-model call over the transcript → JSON scores. Cheap because it is one call, not per-turn.

## K. Report (the shareable artifact)

Score /100 + 6 bars + 3 concrete fixes + 1 "better answer" rewrite + replay of their audio. This is what users screenshot and share = free growth.

## L. Data Model (core tables)

```sql
users(id, name, role, exp, weaknesses_json, avg_score)
interviews(id, user_id, type, persona, started, ended, score)
turns(id, interview_id, role, text, audio_url, ts, latency_ms)
scores(interview_id, grammar, fluency, confidence, technical, ...)
```

Postgres + Redis (session/live state) + S3 (audio).

## M. Backend Architecture

```
Mobile ──WebSocket──> Session Manager (Redis state)
                           │
        ┌──────────────────┼──────────────────┐
     STT stream      Conversation Engine     Moderation
                           │
                     LLM (routed)
                           │
                    TTS stream ─────> Mobile
   (async) Scoring worker ──> Report ──> Postgres/S3
```

WebSocket is non-negotiable for latency. FastAPI + async workers.

## N. Frontend

Flutter or React Native — pick whichever ships fastest. MVP screens:

`Login → Pick interview → Live call UI (waveform + "AI speaking/listening") → Report → History`

That's it. 5 screens.

## O. Cost per Interview (real math, ~10 min call)

Rough, streaming, cascade:

| Component | Cost (USD) |
|-----------|-----------|
| STT ~10 min | $0.04–0.07 |
| LLM turns (routed small, ~15) | $0.03–0.08 |
| TTS ~1500 words | $0.10–0.25 (biggest voice cost) |
| Scoring (1 big call) | $0.02–0.05 |
| **Total** | **≈ $0.20–0.45 (~₹17–38)** |

Pricing and free-tier limits must respect this number.

## P. Cost Control Levers

Model routing, stream + early TTS cutoff, summarize context (don't resend the full transcript each turn), cache static intros/prompts, cheaper TTS voice on the free tier, cap free-tier minutes.

## Q. Monetization (India-calibrated)

- **Free:** 2 interviews/week, basic report, standard voice
- **Pro ₹299–499/mo:** unlimited, all rounds, detailed report, progress tracking, better voice
- **Placement / Institute B2B2C:** sell seats to colleges/coaching centers — likely where real revenue is in India. Recruiter/college dashboard.
- **Later:** company-specific packs (TCS/Infosys/Amazon), resume review, IELTS speaking

## R. India GTM

- **Wedge audience:** final-year students + freshers (placement-season pain)
- **Channels:** college placement cells (B2B2C), YouTube/Insta reels of "AI roasted my interview" report screenshots, Telegram/WhatsApp job-prep groups
- **Language:** allow Hinglish answers, evaluate for English improvement — don't punish, coach

## S. Growth Loop

Report screenshot → social share → "try it" → free interview → paywall at the value moment (after they see their improvement chart). Streaks drive daily retention (Phase 2).

## T. Trust / Safety

Consent for audio storage, easy delete, no video/emotion analysis in MVP (privacy + hard + low ROI). Moderation on both user and AI text. India DPDP compliance for personal data.

## U. Metrics That Matter

- Turn latency p50/p95 (product-alive metric)
- Interview completion rate (do they finish?)
- D7 retention, interviews/user/week
- Free → Pro conversion
- Cost per interview (guard the margin)

## V. Team (lean)

1 full-stack (backend + WS + AI glue), 1 mobile, 1 you (product/AI/GTM). Optional part-time ML for the scoring rubric. Don't over-hire pre-revenue.

## W. Build Timeline

| Week | Deliverable |
|------|-------------|
| **1–2** | WS session mgr, STT stream, end-of-turn, echo LLM, TTS out. Get a laggy call working end-to-end. |
| **3** | Adaptive question engine (HR round), persona, context summarization |
| **4** | Scoring worker + report screen |
| **5** | Latency tuning to <1s, mobile polish, history |
| **6** | Closed beta with 30 students, fix, ship |

## X. Phase 2 / 3 (only after MVP retains)

- **Phase 2:** technical rounds, adaptive difficulty, streaks/progress, company packs, Pro paywall
- **Phase 3:** video + confidence analysis (opt-in), GD mode, resume-aware questions, institute dashboard, IELTS/UPSC modes

## Y. Top Risks + Kills

| Risk | Mitigation |
|------|-----------|
| **Latency** → feels dead | streaming everything, cascade, measure p95 from day 1 |
| **Cost blowout** | routing + TTS discipline + free caps |
| **Feels scripted** | adaptive engine + persona, not a fixed Q list |
| **No moat** | double down on the intelligence engine + India distribution (colleges), not voice |

## Z. First Step This Week

Build **E + F + H** together: get one HR interview running end-to-end at any latency, then tune. Don't build screens, gamification, or 15 interview types.

**One good call > ten features.**

---

### Next options

- **(a)** WebSocket + STT/LLM/TTS streaming skeleton (FastAPI)
- **(b)** Adaptive question-engine rubric design
- **(c)** Cost model as a spreadsheet
