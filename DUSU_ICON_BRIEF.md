# DuSu — Logo / App-Icon Requirement (final)

## 1. Product analysis (this drives every design choice)

| Factor | DuSu reality | Implication for the icon |
|---|---|---|
| What it is | AI **voice** coach — you *speak* English with an AI friend | Icon must say "voice / talking", not "book / school" |
| Who uses it | Indian learners, mostly **mobile-first, budget Android**, aspirational (job / interview / daily confidence) | Must read on small/cheap screens; look premium, not childish |
| Positioning | "**Speak with Confidence**" — a warm mentor, premium but friendly | Elegant, trustworthy, aspirational — not a flat cartoon |
| Emotional core | A **companion** who remembers you (close-friend tone) | A human/face cue works; pure abstract feels cold |
| Existing brand | Gold serif wordmark on deep navy; a **woman's face inside the "D" + speech-bubble + sound-waves** | Keep it — brand consistency across web + app + store |
| Competitors | Duolingo (green owl), Cambly, ELSA — mostly bright flat mascots | Gold-on-navy = **distinctive + premium**, stands apart |

**Verdict:** the *brand* is right; the *icon treatment* is wrong. The current icon
crams the whole wordmark + tagline into a square → unreadable at 48dp. The winning
symbol is already inside the logo: the **"D-mark"** (face-profile + speech-bubble +
sound-waves). It encodes person + voice + conversation in one ownable shape.

## 2. Icon strategy

- **App icon = the D-mark only.** No "uSu", no tagline. A symbol, not a wordmark.
- **Full wordmark stays** for splash screen, in-app header, website, store feature graphic.
- **Adaptive** (Android): separate foreground (mark) + background (navy) so every
  launcher masks it cleanly (circle / squircle / teardrop) — no square, no letterbox.
- One shape, one color story, works from 48dp → 512px.

## 3. The mark (what to draw)

A gold **serif "D"** whose **inner counter forms a woman's face in profile** (looking
left), with a small **speech-bubble tail** at the lower-left and **4–5 vertical
sound-wave bars** beside the face. Confident, minimal, symmetrical enough to sit in a
circle. (This is the existing left glyph of the logo — reuse it.)

## 4. Color (exact)

| Role | Hex |
|---|---|
| Background (navy) | `#070A14` |
| Gold — highlight | `#F0C75E` |
| Gold — core | `#D4AF37` |
| Gold — deep/shadow | `#A9812B` |
| Off-white (optional accent) | `#F3ECD8` |

- Mark fill = gold gradient **top-left `#F0C75E` → bottom-right `#A9812B`**, core `#D4AF37`.
- Background = **solid** `#070A14` (fills the entire square, no transparency).
- One subtle top highlight/shine is fine; avoid heavy 3D bevels (muddy at small size).

## 5. Composition rules

- **Square canvas, 1:1.** Master at **1024×1024** (min 512).
- **Safe zone:** keep the whole mark inside the centre **66%** (Android crops the outer
  ~18% per side for masking). Generous padding = never clipped.
- Optically centered; mark height ≈ 60–66% of canvas.
- High contrast (gold on navy passes). No fine lines < 3px at 512 (vanish at 48dp).
- No text, no tagline, no border, no drop-shadow on the outer square.

## 6. Deliverables (everywhere the icon/logo is used)

| Asset | Size | Format | Notes |
|---|---|---|---|
| **Icon master** | 1024×1024 | PNG (opaque navy bg) | I slice everything else from this |
| Adaptive foreground | 432×432 in 108dp | (I generate) | mark only, transparent bg |
| Adaptive background | navy | (I generate) | solid `#070A14` |
| Monochrome (Android 13 themed) | mark silhouette | (I generate) | single-color, transparent |
| Legacy mipmaps | 48/72/96/144/192 | PNG | (I generate) mdpi→xxxhdpi |
| Play Store icon | 512×512 | 32-bit PNG | store listing |
| PWA maskable | 192 + 512 | PNG | web install icon (manifest) |
| Favicon | 32 + 180 | PNG | browser tab / iOS home |
| Splash / in-app | use full wordmark | existing `logo.png` | large only |

## 7. AI-generation prompt (if making fresh art)

```
App icon, a single elegant gold serif letter "D" on a solid deep-navy background
(#070A14). The negative space inside the D forms a woman's face in profile looking
left, with a small speech-bubble tail at the lower-left and 4-5 vertical gold
sound-wave bars beside the face. Gold gradient #F0C75E to #A9812B with a subtle
top shine. Flat, minimal, centered, high contrast, generous padding, premium
app-icon style, 1:1 square, no text, no tagline, no border.
```

## 8. Do / Don't

- ✅ One symbol, solid navy, gold mark, big padding, opaque background.
- ✅ Consistent gold-on-navy with the web app + store.
- ❌ No wordmark or "SPEAK WITH CONFIDENCE" text in the icon.
- ❌ No transparency on the icon background; no thin details; no photo textures.
- ❌ Don't fill edge-to-edge (safe zone) — it'll get clipped by the mask.

## 9. What I need from you

**Either** send a `1024×1024` square master following §3–§5 (drop it at
`android-twa/icon-master.png`), **or** say "use the existing logo" and I'll crop the
D-mark out of `backend/logo.png` myself. Then I generate all of §6 and rebuild the APK.
