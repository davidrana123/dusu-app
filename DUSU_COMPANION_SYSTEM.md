# DuSu — The Companion System

> *How DuSu becomes someone you can't leave.*
> Companion to [DUSU_FEATURES.md](DUSU_FEATURES.md). Supersedes the old "Retention Plan" — the name matters: read "retention" and you optimize metrics; read "Companion System" and you optimize the **relationship**.
> Rewritten: 2026-07-21.

> **THE ONE LAW** — *Every interaction must leave the user emotionally better than when they opened DuSu.* More confident, more hopeful, less scared, proud, or curious. This is the final filter behind every decision below.

> **THE NORTH STAR** — after 90 days a new user should be able to say: *"I joined DuSu to learn English. I stayed because it felt like someone was helping me become more confident."* Every feature must serve that sentence.

---

## The one question

Users never think *"I'm returning because of a retention loop."*
They think:

> *"I miss talking to DuSu."*
> *"I want to finish today's challenge."*
> *"I wonder what DuSu remembered."*

**Design from that feeling — always the user's emotional POV, never the business metric.**

---

## The Emotion Ladder (build bottom-up)

| # | Feeling | User thinks | DuSu today |
|---|---|---|---|
| 1 | **Beauty** | "This is gorgeous / alive." | ✅ Strong (home/hero) |
| 2 | **Curiosity** | "What happens if I press this?" | 🟡 Home only |
| 3 | **Connection** | "DuSu knows me." | 🔴 Facts, not moments |
| 4 | **Belonging** | "This is *my* place." | 🔴 Missing |
| 5 | **Progress** | "I'm *becoming* better." | 🔴 Stats, not growth |
| 6 | **Identity** | "I *am* someone who speaks English." | 🔴 Missing |
| 7 | **Purpose** | "I'm doing this to become ___." | 🔴 Missing (highest) |

*(Belonging added before Identity — humans belong before they change. Purpose is the summit: "I learn English to become a software engineer / to speak to the world," not "to get vocabulary.")*

---

## THE FILTER (governs everything)

> **Every feature must make the user feel at least one of these. If it makes them feel none, don't build it.**
> 1. "I'm **curious** what's there."
> 2. "DuSu **gets me / cares**." *(relationship)*
> 3. "I **belong** here."
> 4. "I can **see myself growing**."
> 5. "I **can't wait** for tomorrow." *(anticipation)*
> 6. "This is **who I'm becoming**." *(identity/purpose)*

**Freeze net-new features** (no new modes/screens) until Connection → Belonging → Progress are real.

---

## The core insight

DuSu **remembers**. That's good. But:

> **Does DuSu *care*?**

That's the whole game. Memory is plumbing; **caring is the product.**

- Remembering: *"Good morning."*
- **Caring:** *"I've been thinking about your interview today. Let's practise for five minutes."*

Everything below exists to make DuSu feel like a **person**, then a journey — **person before game. Games create engagement; relationships create loyalty.**

---

## The Human Psychology Engine

Products become loved through **uncertainty + reward + emotion** working together — not through addictive tricks. Every system in this doc must pull at least one of these 10 human drivers. If a feature pulls none, it doesn't ship.

| # | Driver | The brain wants… | In DuSu |
|---|---|---|---|
| 1 | **Curiosity** | to close open loops | every session ends on a question / a locked tease |
| 2 | **Progress** | to see *movement* (not completion) | Confidence 45% → 48%, live growth |
| 3 | **Ownership** | "mine" | "my DuSu", my world, my journey |
| 4 | **Investment** | to value what it builds | personal history piles up (memories, timeline) |
| 5 | **Identity** | to *be* someone | "I'm a confident speaker" |
| 6 | **Surprise** | novelty | random letters, gifts, unexpected encouragement |
| 7 | **Completion** | to finish things | collections, maps, progress bars |
| 8 | **Emotional safety** | to not be judged | the safest place in the world to make mistakes ← **biggest** |
| 9 | **Belonging** | a place of its own | "this is *my* place" |
| 10 | **Purpose** | meaning | "I'm becoming ___" |

---

## Design rules (how we decide, before any pixel)

1. **Optimize the feeling, not the screen.** Never start with "Home Screen." Start with:
   > Feeling: *Curiosity* · Thought: *"I wonder what DuSu prepared today."* → *then* design.
2. **Safety first.** Most users are scared and feel judged. DuSu must be the safest place to fail — celebrate the attempt, never the error.
3. **The Smile Test.** Ask of every session: *did the user smile today?* No smile = no emotional memory.
4. **Every session must end with a feeling** — one of: *"I can't wait." · "I'm proud." · "I'm surprised." · "That was fun." · "I improved." · "I want tomorrow."* If none happened, the session failed emotionally, even if it "worked."
5. **Trust is earned through consistency.** Every remembered fact must be accurate; every callback must feel natural; the personality stays the same. DuSu **admits when it doesn't know, never invents memories, never contradicts itself, never shames a mistake.** No trust → no relationship.
6. **Never manipulate.** Create reasons to return through genuine value, progress, and connection — never fear, guilt, or artificial scarcity.
   - ✅ *"Tomorrow we'll continue your story."*  ❌ *"You'll lose everything if you don't return."*
   - ✅ Celebrate progress.  ❌ Punish absence.
7. **Learning quality is the multiplier.** The companion *amplifies* the coaching, never replaces it:
   > **Trust × Learning Quality × Relationship × Curiosity × Visible Progress = Long-term loyalty**
   Multiplication — if **Learning Quality = 0, the product = 0.** The English corrections must be genuinely excellent first.

---

## The Companion Checklist (design-review gate)

Before building any feature, ask — does it…
- [ ] make DuSu feel more human?
- [ ] increase trust?
- [ ] help the user actually improve?
- [ ] create curiosity?
- [ ] create a memorable moment?
- [ ] respect the user's time?
- [ ] leave the user feeling better than before?

**Fewer than 3 "yes" → don't build it.**

---

## The Systems

Each: **Feeling it serves · What · Where (real code) · How · Effort** (S=hrs, M=~day, L=multi-day).

### S1 — Memory that holds *moments & emotions* (foundation)
- **Feeling:** Connection
- **What:** Four memory stores, each row tagged with an **emotion** and the day's **energy**:
  | Type | Expires | Examples |
  |---|---|---|
  | **Identity** | never | name, dream, profession, college, hobbies |
  | **Relationship** | never | likes encouragement, prefers Hindi, practises at night, nervous in interviews |
  | **Moment** | 2–7 days | exam tomorrow, travelling, sister's wedding, feeling stressed |
  | **Achievement** | never | first conversation, first interview, 1000 sentences, world cleared |

  Plus two new variables:
  - **Emotion on a memory:** `interview → scared`. Enables *"Yesterday you sounded nervous — better today?"*
  - **Energy (today):** happy / tired / confident / lonely / excited / frustrated → **reshapes the whole session**.
- **Where:** `db.py` (Memory model, `merge_facts`, `get_memory`, `save_checkin`→energy), `main.py` (prompt injection)
- **How:** add `mem_type`, `emotion`, `expires_at`; energy on the daily check-in; prompt builder pulls Identity+Relationship always, unexpired Moments, Achievements for callbacks, energy for tone.
- **Effort:** L

### S2 — Capture moments after every session
- **Feeling:** Connection, Curiosity
- **What:** Session-end extraction of *emotional moments & achievements* (not just facts), stored via S1, surfaced later.
- **Where:** `main.py` session-end summary → `add_conversation`/`merge_facts`; `db.py`
- **How:** summary prompt emits `{facts, moments:[{text,emotion}], achievements}`; store tagged.
- **Effort:** M · **Needs:** S1

### S3 — Relationship: make DuSu *care* (the biggest missing system)
- **Feeling:** Connection, Belonging, Identity
- **What:** Three things:
  1. **Proactive caring** — DuSu opens on what matters to *you* ("I've been thinking about your interview").
  2. **The Relationship Journey** *(internal, invisible to user — "Meter" sounds technical)* — changes how DuSu talks:
     `Guest → Friend → Practice Partner → Coach → Mentor → Companion`
  3. **DuSu's own curiosity** — she asks: *"Yesterday you said something interesting — can I ask about it?"*
  4. **Emotional safety, always** — never judges a mistake; celebrates the attempt. The relationship is the safe place to fail.
- **Where:** `main.py` prompt builder (all modes); `db.py` `first_seen` + session count → derive stage
- **How:** compute `relationship_stage` from days-since-`first_seen` + sessions; inject a **tone directive + memory callback + one curiosity question** into the system prompt per stage. Week 1 warm-formal → Month 6 references old memories naturally.
- **Effort:** M · **Needs:** S1, S2

### S4 — Today's Home (the home belongs to *today*)
- **Feeling:** Curiosity, Belonging, Anticipation
- **What:** Home is literally different each day: Monday ≠ Friday ≠ festival ≠ birthday ≠ rainy ≠ exam day ≠ interview day. One **"Today" slot** shows ONE of: a challenge · a message from DuSu · a surprise · a remembered moment · a story continuation · a mini-celebration.
- **Where:** `home` hero (`setWelcome`/`renderGrowth` area), `/me` returns a `today` object
- **How:** server picks `today` by rules (streak state, unexpired moments, day-of-week, milestones); client renders it. Never the same two days running. *(Weather/festival/birthday layer in once the slot exists.)*
- **Effort:** M · **Needs:** S1, S2

### S5 — Anticipation & story continuity (one long story)
- **Feeling:** Anticipation, Connection
- **What:** The four modes become **one story**. Every session ends like an episode: *"By the way… tomorrow I'll teach you to explain this in English."* Next day opens: *"Yesterday you told me about your college — let's continue."* Daily notification carries the same hook.
- **Where:** session end (`leave()`), Daily Talk open (`greetDaily`), launcher `Notifications.kt`, home `today` slot
- **How:** store a `next_hook` at session end (topic + promise); home + notification read it; next session fulfils it.
- **Effort:** M · **Needs:** S4

### S6 — Growth signals (progress = becoming, not points)
- **Feeling:** Progress, Identity, Purpose
- **What:** Replace XP-first with felt **growth**:
  ```
  Confidence     52%   ↑3%
  Vocabulary   1,230   +18 today
  Thinking speed 4.8s → 2.7s   (sentence delay dropping)
  ```
  Plus the **Transformation Timeline** toward the dream:
  ```
  Day 1   ❌ Couldn't introduce yourself
  Day 8   ✅ Spoke 90 seconds
  Day 43  ✅ Finished first interview
  Dream: Software Engineer  ███████░░ 72%
  ```
- **Where:** `report`, `journey`, home strip; data from `record_practice` (**seconds already tracked!**) + `first_seen` + Achievement memory + new counters
- **How:** track unique words (vocabulary), STT-start latency (thinking speed), composite confidence; timeline from achievements; dream % from worlds cleared / target. XP/badges recede behind these.
- **Effort:** M · **Needs:** S1

### S7 — Worlds & Episodes (rename + gradual reveal)
- **Feeling:** Curiosity, Progress, Identity
- **What:** Levels become **places**, lessons become **episodes**:
  `The Village → The City → The Workplace → The Interview Hall → The Global Stage`
  Words: *Lesson→Episode, Complete→Challenge, Pass test→Unlock next world*. Show **only the next step** + tease what's locked ("I wonder what's inside").
- **Where:** `journey` + `lesson` screens, `CURRICULUM`, `BADGE_LABELS`, copy in `test_client.html`
- **How:** copy pass + collapse roadmap to current + next-locked teaser; each episode ends "Next episode…"; unlock reveal moment. Mostly client.
- **Effort:** M

### S8 — Screen-by-screen "I wonder…" redesign
- **Feeling:** Curiosity, Connection
- **What:** Every screen triggers one curiosity thought:
  | Screen | Target thought |
  |---|---|
  | home | "What does DuSu have for me today?" |
  | journey | "What's inside the next world?" |
  | episode | "Can I complete this challenge?" |
  | report | "How much did I improve?" |
  | daily | "What does DuSu remember?" |
  | session | "What will she say back?" |
  | setup | "My interviewer is waiting…" |
- **Where:** all non-home screens
- **How:** each = arrive → DuSu reacts → curiosity line → ONE action → reward reveal. Reuse hero patterns.
- **Effort:** L

### S9 — Surprise rewards & collectibles
- **Feeling:** Curiosity, Identity, Belonging
- **What:** **Unannounced** gifts (delight): after ~15 days DuSu says *"I made something for you"* → a personalized certificate / letter / memory collage / custom badge. Plus collections users finish for their own sake (Confidence Stars, Story Chapters, Word Collections).
- **Where:** new light UI in `journey`/home; `db.py` collection + gift state
- **How:** trigger gifts on hidden milestones; 1 collection first (Confidence Stars per world cleared); reveal animation.
- **Effort:** M · **Needs:** S6, S7

### S10 — Delight (always-on, not a phase)
- **Drivers:** Surprise, Ownership, Belonging
- **What:** tiny memorable moments that aren't *useful*, just *felt* — the Spotify/Apple/Discord/Google touch. Seasonal home skins, little animations, easter eggs, an unexpected *"you did great today,"* DuSu reacting with personality.
- **Where:** everywhere (micro-interactions, home, session, notifications)
- **How:** budget ~one delightful surprise every few sessions; seasonal skins; hidden reactions. A **standing habit on every screen**, not a task to finish.
- **Effort:** ongoing

### S11 — The Doorway (Start Speaking → smart, gamified options)  ⚠️ SUPERSEDED
> **Superseded by [DUSU_EXPERIENCE.md](DUSU_EXPERIENCE.md) — "The Companion Moment."** The Doorway still asked *"which mode?"* (a prettier 6-card menu). The new spec asks *"what should DuSu help me with?"* and answers it: memory-aware greeting → **3 curated recommendations (goals, with a why)** → scroll for everything. Build that instead. Kept below for reference.

- **Feeling:** Curiosity · Ownership · Belonging
- **The problem:** today "Start Speaking" jumps straight into Confidence Talk. No clear paths, DuSu doesn't *lead*, the moment feels flat and weak.
- **The fix:** tapping **Start Speaking** opens **The Doorway** — DuSu leans in, asks a warm question, and *deals out* a hand of clear path-cards. Choosing becomes the game.

#### The moment (on tap)
1. DuSu scales up + smiles (living face); hero copy fades; she "speaks" (voice + bubble):
   > "What are we doing today, {name}?"  *(rotates: "I've got a few ideas…" / "Where shall we go?")*
2. **6 path-cards deal onto the table** — staggered card-deal animation, soft pop + tick, haptic on mobile.
3. **One card glows** — `✨ DuSu recommends` (smart pick).
4. Two ways forward:
   - **Answer out loud** (mic already live) → flows straight into **Confidence Talk** with your answer as turn 1 (zero friction).
   - **Tap a path-card** → route.

#### The 6 paths (gamified game-cards)
```
┌─ 🔥 Continue Journey ─┐ ┌─ 🎁 Today's Challenge ─┐ ┌─ 🗺️ My Roadmap ──────┐
│ Pick up your story    │ │ 2 min, no Hindi        │ │ The Interview Hall → │
│ 🔥 5-day streak        │ │ ⭐ +20 XP · ~3 min      │ │ World 5 of 7          │
└───────────────────────┘ └────────────────────────┘ └──────────────────────┘
┌─ 📖 Learning Mode ────┐ ┌─ 💬 Confidence Talk ──┐ ┌─ 🎯 Interview Prep ──┐
│ Hindi → English       │ │ Just talk with me      │ │ Mock + scored report │
│ 🐢 Slow & clear        │ │ ✨ DuSu recommends      │ │ 💼 Any role           │
└───────────────────────┘ └────────────────────────┘ └──────────────────────┘
```
**Card anatomy:** orb icon (per-mode accent glow) · title · one-line outcome · **meta chip** (the reward/cost: XP · ~minutes · streak · world x/7) · **badge** (`✨ recommends` glowing ring / `NEW` / `🔒 locked teaser`). **Hover/press:** tilt-to-cursor, glow bloom, sheen sweep, lift; press = scale-down + tick.

**Routing (reuse existing):** Continue Journey→`startDaily` · Today's Challenge→`today.action` · My Roadmap→`openJourney` · Learning→`learning` · Confidence→`conversation` · Interview→`setup`.

#### Smart ordering — pick the ONE glowing card, float it first
1. `next_hook` exists → **Continue Journey** ("finish your story")
2. streak at risk (practised yesterday, none today) → **Continue Journey**
3. unexpired **moment** → **Today's Challenge / Daily** ("ask about it")
4. interview event ≤7 days (memory) → **Interview Prep**
5. **low energy** → Confidence (gentle) · **high energy** → Today's Challenge
6. new user / early world → **Learning Mode**
7. default → **Confidence Talk**
Order the rest by recent use; avoid the same recommendation two days running.

#### The "AI asks" warm-up (no cold start)
Choosing Confidence/Interview → DuSu asks ONE calibrating question as a friendly card + quick-pick chips + skip:
- **Confidence:** "What's on your mind today?" → *My day · My work · A movie · Surprise me* · 🎤 just talk
- **Interview:** "Which role today?" → recent-role chips · 🎤 tell me
Answering (tap or voice) seeds the opening so DuSu starts *on-topic*. "Surprise me / just talk" skips instantly.

#### Gamification layer (game, not menu)
Card-deal entrance (springy, staggered) · reward chips on every card · pulsing recommended-glow · locked teasers ("🔒 unlocks in The City") · press tick + haptic + DuSu nods/smiles at your pick · streak fire + Confidence Stars peeking on top · optional soft deal/select sound (after first tap; respect autoplay).

#### States
- **Desktop:** 3×2 grid on a dimmed hero stage; DuSu stays top-center, reacting.
- **Mobile:** single column, deals top→down; DuSu shrinks to a corner ("she's watching").
- **Back:** tap-outside/back → cards fold, hero returns.
- **Reduced motion:** fade in (no deal), no sound.
- **First-timers:** show fewer cards (Learning · Confidence · Today) — more unlock with worlds.

#### Build notes
- New `#doorway` overlay inside `#home`; reuse `.mode-card`/`.curio-card` styles for game-cards.
- Reuse `chooseMode`, `startDaily`, `openJourney`, `today.action`; recommendation from `/me` (`today`, `growth`, memory) — mostly client logic on data we already return.
- **Effort:** M–L.

### Later — Community (not now)
Friends · study partners · weekly challenges · college/office groups. Powerful, but only after the solo companion loop works.

---

## Build order (person before game)

> **S1 → S2 → S3 → S4 → S5 → S6 → S7 → S8 → S9 → S11 (Doorway)**
> *S1–S10 built. **S11 The Doorway is the next build** — it's what turns the strong home into a strong first tap.*

**Why this order:**
1. **S1 Memory + S2 Moments** — the spine. DuSu can't care about what it doesn't hold.
2. **S3 Relationship next** — the instant memory exists, DuSu must *behave differently* because of it, or the memory is invisible to the user. **This is the leap most apps skip.**
3. **S4 Today's Home + S5 Anticipation** — now every visit feels fresh and worth returning to.
4. **S6 Growth** — visible evidence they're becoming someone new.
5. **S7 Worlds/Episodes, S8 redesigns, S9 surprises** — polish the journey once the emotional core beats.

---

## Data model changes (consolidated)
`db.py` + `main.py`:
- Memory: `mem_type` (identity|relationship|moment|achievement), `emotion`, `expires_at`
- User: `first_seen`
- Daily energy on check-in; `next_hook`; derived `relationship_stage`
- Counters: unique-words (vocabulary), thinking-speed samples; surface `record_practice` **seconds** in `/me`
- Later: collections + gifts tables

---

## Effort roll-up

| System | Effort | Feeling it raises |
|---|---|---|
| S1 memory (moments+emotions) | L | Connection |
| S2 moment capture | M | Connection |
| S3 relationship + meter | M | Connection/Belonging |
| S4 today's home | M | Curiosity/Belonging |
| S5 anticipation + story | M | Anticipation |
| S6 growth signals | M | Progress/Identity/Purpose |
| S7 worlds & episodes | M | Curiosity/Identity |
| S8 screen redesigns | L | Curiosity |
| S9 surprises + collectibles | M | Identity/Belonging |
| S10 delight (always-on) | ongoing | Surprise/Ownership/Belonging |
| **S11 The Doorway (Start Speaking)** | M–L | Curiosity/Ownership/Belonging |

---

## What we DON'T do now
- No new speaking modes / screens (freeze per THE FILTER).
- Community; real anime PNG; spoken greeting — after the companion loop works.

---

## How we measure (forget DAU/MAU)

Retention is a lagging business number. Track **Emotional Moments** — the leading indicators. Per session, did the user:

- 😄 smile / laugh · 😮 say "wow" · 🔁 replay something · 📤 share something ·
- ✅ complete a challenge · ⏱️ talk **longer than they planned** · 🔙 come back tomorrow

More Emotional Moments → more love → retention follows on its own. A day with zero = an emotional miss to fix.

---

# ⬇ The shift

DuSu stops being *"a capable English app"* and becomes *"a companion I'm on a journey with."*
Feature-building pauses; **relationship-building begins.** Nothing gets built unless it pulls one of the 10 psychology drivers and obeys THE ONE LAW.

**📌 THIS DOCUMENT IS FROZEN.** No more planning passes. From here the highest-value work is **building, testing with real users, and iterating from observed behavior** — you learn more from 20 people using it than 20 more pages. The remaining risk is **execution quality + consistency**, not strategy.

**Recommended first milestone:** **S1 + S2 + S3** shipped together — memory that holds moments **and** a DuSu that visibly acts on them. That's the smallest thing that makes a user say *"DuSu actually gets me."* First concrete task: add `mem_type` + `emotion` + `expires_at` to `db.py` memory, capture moments at session-end, and inject a `relationship_stage` tone + one memory callback into the prompt.

**Decisions for you (review):**
1. **Approve build order** S1→S2→S3→S4→S5→S6→S7→S8→S9?
2. **First milestone = S1+S2+S3** (make DuSu *care*) — agree, or start smaller (S1+S2 only)?
3. **World names** — commit to Village/City/Workplace/Interview Hall/Global Stage? (name your 7)
4. **Growth metrics** — Confidence % + Vocabulary + Thinking speed the right three?
5. **Commit + push checkpoint** of today's work first?
6. Keep **local** or push to **Render** to test on phone?
7. **Sign-off to stop planning** — plan complete enough to start building **S1**? (yes = I begin)
