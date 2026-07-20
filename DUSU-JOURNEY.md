# DuSu — AI Learning Journey (Core Feature) Plan

Turn DuSu from a translator/interview bot into a **personal AI English coach** that
knows each learner, tracks progress, and adapts every lesson. Needs a **database**
(current app has none — stateless + localStorage only).

---

## 0. Database (foundation — must be free forever + persist)

Render free disk is **ephemeral** (wiped on every deploy) → SQLite won't survive.
Need an external free Postgres.

| Option | Free? | Persist? | Notes |
|---|---|---|---|
| **Neon** (recommended) | ✅ free forever | ✅ | Serverless Postgres, 0.5GB, scales to zero, one connection string |
| Supabase | ✅ free | ✅ | Postgres + extras; pauses after 1wk idle, auto-resumes |
| MongoDB Atlas | ✅ free 512MB | ✅ | NoSQL; more code change |
| Render Postgres | ⚠️ | ❌ free tier expires ~30 days | avoid |

**Pick: Neon.** You create a free account → give me the connection string → I wire it.
Stack: SQLAlchemy 2.0 async + asyncpg. Tables auto-created on startup (no migrations tool yet).

### Schema (v1)
- **users**: id (google sub), email, name, picture, created_at, last_seen
- **profiles**: user_id, onboarded, goal, comfort, practice_time, level (A0/A1/A2/B1…),
  scores {confidence, pronunciation, listening, vocabulary, grammar, thinking} 0-100,
  weak_areas (JSON), assessed_at
- **progress**: user_id, xp, coins, streak_days, last_active_date, badges (JSON),
  journey (JSON: 7 levels + % each), daily_goal, daily_done
- **sessions** (history): user_id, mode, started_at, turns, summary

---

## Phases

### Phase 1 — DB + persistence (do first)
- Connect Neon, create tables on startup.
- On Google login: upsert user, load/create profile+progress → return `onboarded` flag.
- Move usage limits from localStorage → DB (server-authoritative).
- Client routes new user → Assessment; returning onboarded user → Home/Journey.

### Phase 2 — AI Level Assessment (first-time, ~2 min, once)
Flow: Welcome → 3 quick MCQs (goal / comfort / practice time) → 4 voice tasks:
1. "Tell me your name + about yourself" (fluency, vocab, confidence)
2. "Repeat after me: My name is Sarah." (listening, pronunciation)
3. Hindi→English: "Kal mujhe market jaana hai." → say in English (thinking)
4. "Tell me about your favorite food." (confidence, hesitation)

Browser transcribes each → LLM scores 6 dimensions + CEFR level + builds roadmap +
warm persona message. Save profile. No harsh "you are beginner" — encouraging.

### Phase 3 — My Journey + Dashboard
- **My Journey**: 7-level roadmap w/ progress bars (Thinking → Simple Speaking →
  Daily Convo → Confidence → Interview → Professional → Fluency). "You are here."
- **Dashboard**: current level, today's goal (x/5), 6 skill bars, streak, XP, next-level XP.

### Phase 4 — Gamification
XP, coins, streak (daily), badges (🎤 First Conversation, 🔥 7-Day Streak,
⭐ 100 Sentences, 💬 First 10-min Chat, 🚀 Level Up), daily goal progress.
Computed server-side after each session, stored in progress.

### Phase 5 — Adaptive learning
After each session, update the learner model:
- weak pronunciation → more pronunciation drills
- weak listening → more listening
- weak vocab → simpler words
- low confidence → shorter, more encouraging sessions
Next lesson picked from weakest area instead of fixed curriculum.

---

## Order
DB (P1) → Assessment (P2) → Journey/Dashboard (P3) → Gamification (P4) → Adaptive (P5).
Each phase deploys + testable before the next.
