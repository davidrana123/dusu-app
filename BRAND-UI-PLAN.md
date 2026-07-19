# DuSu — Branding & Premium UI Plan

> Goal: make DuSu **feel** like a premium product the moment it loads — luxurious, modern, calm, and alive. This doc is the single source of truth for brand identity, the design language, every UI upgrade, the footer, and the build order.

North star: *"A gold-standard voice coach."* Every pixel should whisper **confidence + craft**, never shout.

---

## 1. Brand Foundation

### 1.1 Positioning
DuSu is the **premium AI speaking partner**. Not a cheap "learn English" app — a polished, confidence-building coach you're proud to open. Think: Calm × Duolingo × a luxury concierge.

### 1.2 Personality (how DuSu behaves)
| Trait | Means | Shows up as |
|-------|-------|-------------|
| **Warm** | Encouraging, never judgy | Soft copy, gentle motion, friendly face |
| **Premium** | Considered, uncluttered | Gold accents, generous space, real type |
| **Calm** | Lowers anxiety | Slow fades, muted contrast, no clutter |
| **Alive** | Feels present | Lip-sync face, breathing glow, micro-motion |

### 1.3 Voice & tone (copy)
- Short, human, second person. "Let's practice," not "Commence session."
- Encourage effort, never grade harshly in-flow.
- One idea per line. Confidence, not corporate.
- Emoji sparingly (👋 ✨ 🎧) — never more than one per message.

### 1.4 Logo rules
- **Primary:** gold+silver "DuSu" wordmark on deep navy (`Logo.png`).
- **Clearspace:** keep padding ≥ the height of the "D" on all sides.
- **Min size:** 28px tall (wordmark), 40px (login/hero).
- **Don'ts:** don't recolor, stretch, add shadows beyond the built-in glow, or place on a busy/light background.
- **Favicon / app mark:** the "D-with-face" glyph alone (crop from logo) — build a clean SVG version later.

---

## 2. Color System

Deep navy canvas + **gold** as the single hero accent. Restraint is the luxury.

### 2.1 Core
| Token | Hex | Use |
|-------|-----|-----|
| `--bg-0` | `#070a14` | deepest background |
| `--bg-1` | `#0b1020` | panels base |
| `--bg-2` | `#0e1428` | raised surfaces |
| `--ink` | `#f3ecd8` | primary text (warm ivory) |
| `--ink-dim` | `#c8bd9e` | secondary text |
| `--ink-faint` | `#8a815f` | captions, hints |

### 2.2 Gold (the accent — use it *little*, make it *matter*)
| Token | Hex | Use |
|-------|-----|-----|
| `--gold-lt` | `#f7e08a` | highlights, top of gradient |
| `--gold` | `#d4af37` | primary accent |
| `--gold-dk` | `#9a6f14` | gradient base, pressed |
| `--gold-grad` | `linear-gradient(135deg,#f7e08a,#d4af37 48%,#9a6f14)` | CTAs, ring, wordmark |

### 2.3 Functional accents (state clarity)
| Token | Hex | Meaning |
|-------|-----|---------|
| `--speak` | gold | DuSu speaking |
| `--listen` | `#4fd6a0` | listening to you |
| `--think` | `#f0a952` | thinking |
| `--danger` | `#e08a7a` | end / errors |

### 2.4 Rules
- Gold covers **< 10%** of any screen — it's jewelry, not paint.
- Text is warm ivory (never pure white) so it feels expensive.
- One accent per action. No rainbow.

---

## 3. Typography

| Role | Font | Weights | Use |
|------|------|---------|-----|
| **Display** | Cormorant Garamond (serif) | 500–700 | headlines, DuSu wordmark, state labels, scores |
| **Body/UI** | Inter (sans) | 400–600 | paragraphs, buttons, inputs, chips |

Scale (rem): 12 / 13 / 15 (body) · 18 / 22 (subhead) · 28 / 34 / 44 (display).
Rules: tight tracking on display (`-0.02em`), roomy line-height on body (1.55). Never justify. Numbers in scores use the serif for elegance.

---

## 4. Design Language ("Gilded Glass")

The signature look = **dark glass + gold light + soft depth**.

1. **Glass surfaces** — translucent panels, 1px gold-tinted border, blur behind (`backdrop-filter: blur(18px)`).
2. **Gold rim-light** — hero elements get a faint gold edge glow, not a drop shadow.
3. **Aurora background** — slow-moving radial gradient blobs (navy → faint gold/teal) behind everything, very low opacity. Gives life without noise.
4. **Film grain** — a subtle noise overlay (2–3% opacity) kills banding and adds a tactile, premium feel.
5. **Depth via light, not lines** — layers separated by glow + blur, minimal hard borders.
6. **Generous space** — whitespace is the biggest premium signal. Don't crowd.

---

## 5. Component Upgrades

### 5.1 Buttons
- Primary = gold gradient, ivory-dark text, soft gold glow, `translateY(-1px)` + brighten on hover, `scale(.98)` press.
- Secondary = glass + gold-tint border, gold text on hover.
- Add a subtle **sheen sweep** (a light gradient that animates across) on primary CTAs on hover.

### 5.2 Cards (mode cards)
- Glass + gold border on hover, lift + gold glow.
- Add a faint **gradient corner glow** that follows the cursor (spotlight).
- Icon in a gold/teal rounded chip; title in serif.
- On hover, the arrow slides + a hairline gold underline animates in.

### 5.3 Inputs
- Glass field, gold focus ring (`box-shadow: 0 0 0 3px gold@18%`), floating/inline label in caps-faint.

### 5.4 The Orb + Face (signature)
- Keep the animated **gold cartoon face** with lip-sync.
- Add a **breathing** idle animation (scale 1 → 1.02, 4s) so it's never dead.
- State rings already color-coded (gold/teal/amber) — add a soft particle shimmer while speaking.
- Optional: a faint circular **audio-wave ring** around the orb that reacts to mouth openness.

### 5.5 Chat bubbles
- DuSu (left): glass, gold avatar chip "Du".
- You (right): gold-tinted glass.
- Fade+rise in; timestamp on hover; auto-scroll.

### 5.6 Report
- Animated gold **score ring** (already) + count-up number.
- Metric bars fill left→right with gold gradient + a tick label.
- Cards: Strengths (teal dot), Fixes (amber), Better answer (teal panel).
- **Delight:** a subtle gold **confetti/sparkle** burst when the report reveals if score ≥ 80. Share/Download buttons.

### 5.7 Header
- Wordmark left, user chip right (avatar/initials + name + Sign out).
- On scroll, header condenses with a blur bar.

---

## 6. Motion & Micro-interactions

Motion is where "premium" is won or lost. Rules: **ease-out, 150–450ms, purposeful, never bouncy-cheap.**

- Page/screen changes: fade + 10px rise (`.45s`).
- Buttons/cards: hover lift + glow (`.18s`), press `scale`.
- Orb: breathing idle, state cross-fades, mouth lip-sync, ring pulses.
- Cursor **spotlight** on cards (radial gold glow follows pointer).
- Aurora blobs drift slowly (20–30s loops).
- Report reveal: staggered bar fills + ring sweep + optional sparkle.
- **Sound design (optional, tasteful):** a soft chime on report reveal, a gentle "listening" cue. Off by default, toggle in settings.
- Respect `prefers-reduced-motion` → disable drift/parallax, keep essential state changes.

---

## 7. Premium Details Checklist (the 1% that reads as 10x)

- [ ] Aurora gradient-mesh background (animated, low opacity)
- [ ] Film-grain noise overlay
- [ ] Cursor-follow spotlight on interactive cards
- [ ] Gold sheen sweep on primary CTA hover
- [ ] Breathing orb idle + audio-reactive ring
- [ ] Count-up score + staggered report reveal + sparkle at ≥80
- [ ] Skeleton/loading shimmer (gold) instead of blank states
- [ ] Custom slim gold scrollbar
- [ ] Warm ivory text (never pure white)
- [ ] Rounded 16–26px radii everywhere, consistent
- [ ] Real favicon + page `<title>` + social/OpenGraph card
- [ ] Micro-copy pass (warm, human, short)
- [ ] Empty/error states designed (never a raw message)

---

## 8. Footer

A premium footer = quiet, structured, trustworthy. Dark, glass-topped divider, gold hairline.

### Layout (3 zones)
```
┌──────────────────────────────────────────────────────────┐
│  DuSu (wordmark)            Product        Company         │
│  Speak with confidence.     · Conversation · About        │
│  Small brand blurb.         · Interview     · Contact      │
│  [ social icons ]           · Modes (soon)  · Privacy      │
│                                             · Terms        │
├──────────────────────────────────────────────────────────┤
│  © 2026 DuSu · Made with ♥ in India        [ back to top ]│
└──────────────────────────────────────────────────────────┘
```

### Content
- **Brand column:** logo, tagline, one-line mission, social icons (LinkedIn, Instagram, X/Twitter, YouTube — placeholders).
- **Product column:** Free Conversation · Interview Prep · Coming soon modes.
- **Company column:** About · Contact · Privacy Policy · Terms.
- **Bottom bar:** `© 2026 DuSu` · "Made with ♥ in India" · "Speak with confidence." · Back-to-top.

### Style
- Sits on `--bg-0`, separated by a faint gold hairline (`border-top: 1px rgba(gold,.15)`).
- Link hover → gold. Faint text (`--ink-faint`), section titles in caps.
- Only on **home** (not inside a live session — sessions stay focused/immersive).

---

## 9. Accessibility & Responsive

- Contrast: body text ≥ 4.5:1 (ivory on navy passes). Don't put faint gold text on dark for essential info.
- Focus-visible rings (gold) on all interactive elements.
- Hit targets ≥ 44px.
- `prefers-reduced-motion` honored.
- Responsive: single-column < 640px; welcome bubble stacks; modes stack; footer columns stack.
- Voice/mic: clear Chrome/Edge note; graceful fallback text.

---

## 10. Build Order (roadmap)

**P0 — instant premium lift (fast, high impact)**
1. Aurora animated background + film grain.
2. Warm-ivory text pass + consistent radii/spacing.
3. Button/card hover polish (lift, glow, sheen sweep).
4. Cursor spotlight on mode cards.
5. Footer (home only).

**P1 — signature & delight**
6. Breathing orb idle + audio-reactive ring.
7. Report: count-up score, staggered reveal, sparkle ≥80, Share/Download.
8. Skeleton/loading shimmer + designed empty/error states.
9. Custom gold scrollbar, favicon, `<title>`, OG card.

**P2 — depth & brand system**
10. Settings (sound on/off, voice picker, theme).
11. Micro-copy rewrite pass.
12. Clean SVG app-mark (D-face glyph) + brand asset kit.
13. Optional sound design (chimes/cues).

---

## 11. Reference — current vs target

| Area | Now | Target |
|------|-----|--------|
| Background | flat radial gradients | animated aurora + grain |
| Accent use | gold, good | gold as rare jewelry, more restraint |
| Motion | fades + orb | + spotlight, sheen, breathing, reveal |
| Report | bars + ring | + count-up, stagger, sparkle, share |
| Footer | none | full premium footer (home) |
| States | raw messages | designed empty/error/loading |
| Polish | solid v0 | gilded-glass premium |

---

*Living doc. Implement top-down by priority. Every change should pass one test: does it make DuSu feel more premium, calm, and alive — without adding clutter?*
