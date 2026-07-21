# DuSu — Home UI Map (mobile-first, app-like)

> Most users are on **mobile**. Rule: **feel like an app, not a website** — short labels, clear common terms + icons, no marketing sentences. Only one big worded button: **Start Speaking**. Everything else = short word + icon.
> This file is the source of truth for every home label. Finalized: 2026-07-21.

---

## Principles
- **Few words.** A label people understand at a glance (or by its icon). No full sentences on buttons.
- **Common terms.** "More", "Journey", "Leaderboard", "Practice" — not clever phrases.
- **Icons carry meaning.** Pair every option with a recognizable icon.
- **Mobile density.** Compact cards; two small cards sit side-by-side, never one full-width-alone.
- **Centered, bigger section titles** on mobile.

---

## HERO (always visible)
| Element | Text / icon | Action | Notes |
|---|---|---|---|
| Greeting bubble | "Welcome back, David 👋" (dynamic, spoken on login) | — | keep |
| Headline | rotates daily | — | keep |
| Today card | dynamic (streak/moment/challenge) | routes | keep |
| Growth chips | Confidence · Words · Streak | — | keep |
| **Primary button** | **Start Speaking** | Companion Moment | the ONE worded button |
| Reveal link | **More ▾**  *(was "See what DuSu can do →")* | reveal section | app term |

---

## REVEAL ("More ▾")  — app-like sections, top → bottom

### 1. Mood  *(keep — good)*
"Hi David! How are you feeling today?" + 5 emoji.

### 2. Note from DuSu
💌 **A note from DuSu** + preview. **Fix:** card background was too transparent → unreadable. Make it solid/readable.

### 3. Continue  *(was a wordy button)*
| Old | New |
|---|---|
| "Continue your Journey" / "Talk with DuSu about your day, David — and learn English from it" | 🌱 **Continue** · sub **"Talk about your day →"** |

### 4. Today's challenge  *(keep card, shorten copy)*
🎁 **Today's challenge** · **"Speak 2 min — no Hindi 🔥"**  *(was "Can you speak for 2 minutes — without switching to Hindi?")*

### 5. Practice  *(section title — centered + bigger on mobile)*
Header: **Practice**  *(was "More ways to improve")*. Three compact cards — **icon + short name + tiny chips**; the one-line description shows on desktop only, hidden on mobile.

| Card | Name | Chips | Desktop line |
|---|---|---|---|
| 📖 | **Learn** | 🇮🇳→🇬🇧 · 🐢 slow | "Speak Hindi, get English." |
| 💬 | **Talk** | 💬 free chat · 🔥 streak | "A free English chat." |
| 🎯 | **Interview** | 📊 scored · 💼 any role | "Mock + scored report." |

### 6. Your progress  *(section title — centered + bigger on mobile)*
Two **compact cards, side-by-side even on mobile** (never full-width-alone): icon + short word; subtitle desktop-only.

| Card | Label | Desktop sub | Action |
|---|---|---|---|
| 🗺️ | **Journey** | "Worlds & progress" | openJourney |
| 🏆 | **Leaderboard** | "Global ranks" | openLeaderboard |

---

## Mobile rules (CSS)
- Section labels (**Practice**, **Your progress**, **Free practice**): `text-align:center`, larger, more weight.
- `.nav-cards`: **stay 2 columns on mobile** (don't collapse to 1). Hide `.nav-sub` on mobile.
- `.mode-card p`: **hidden on mobile** (keep chips). Tighter padding.
- Keep particles/aurora off on mobile (already done) for speed.
- Everything tappable ≥44px.

---

## What we DON'T do
- No sentences on buttons (except the hero's "Start Speaking").
- No "See what DuSu can do", "More ways to improve", "See where you rank worldwide" — replaced by short common terms.

---

## Build checklist (to-do)
- [ ] Reveal link → **More ▾**
- [ ] Practice header (was "More ways to improve"); Your progress + Free practice → centered + bigger on mobile
- [ ] Mode cards → short names (Learn/Talk/Interview) + chips; hide `<p>` on mobile
- [ ] Nav cards → **Journey** / **Leaderboard** + icons; 2-col on mobile; sub desktop-only
- [ ] Continue banner → 🌱 Continue · "Talk about your day →"
- [ ] Today's challenge sub → "Speak 2 min — no Hindi 🔥"
- [ ] Note-from-DuSu card → readable background
