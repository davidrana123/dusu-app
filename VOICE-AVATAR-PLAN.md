# DuSu — Voice & Avatar Upgrade Plan

Two goals:
1. **A genuinely attractive, natural voice** (charming, warm, human) — with multiple selectable voice personas (female + male).
2. **A more attractive anime-style character** whose mouth actually syncs to the real voice.

Both require the same core change: **move TTS from the browser to a real neural TTS engine.** This one change fixes the robotic voice *and* enables real lip-sync for the anime face.

---

## Part A — Why the current voice is robotic (and the fix)

**Now:** DuSu speaks with `window.speechSynthesis` — the browser's built-in TTS. It uses whatever voice the OS ships (Windows → "Microsoft Zira"). It's free, but:
- Robotic, flat, dated.
- We can't choose a nicer voice — limited to what the user's OS has.
- No timing/viseme data → lip-sync is only *guessed*.

**Fix:** generate speech with a **neural TTS API** on the server, stream the audio to the browser, and play it. Result:
- Natural, warm, human-sounding voice.
- We pick the exact voice(s) — offer several personas.
- Real audio → real lip-sync (mouth follows actual sound).

> Tasteful note: "attractive/charming/warm" — DuSu is a coaching product, so we'll pick voices that are natural, friendly, and appealing (not gimmicky). Multiple personas let each user choose the one they like.

---

## Part B — Neural TTS options (free tiers)

| Provider | Free tier | Quality / vibe | Latency | India voices | Notes |
|----------|-----------|----------------|---------|--------------|-------|
| **Google Cloud TTS** ⭐ | **1M chars/mo** (Neural2/WaveNet) + 100 min Studio; Chirp3-HD | very natural, many voices | ~300–600ms | ✅ en-IN female & male | **You already have a GCP project (DuSu).** Huge free tier. Best free scale. |
| **ElevenLabs** | 10k chars/mo | **most charming/emotive** voices | ~300–800ms (streaming) | multilingual | Best "attractive natural" voices, but small free char cap |
| **Azure Neural TTS** | 500k chars/mo | very natural, expressive styles (cheerful, etc.) | ~300ms | ✅ en-IN (Neerja, Prabhat) | Great free tier, style control |
| **Deepgram Aura** | pay-as-you-go (cheap) | natural, low latency | ~200ms | limited | Fast, but not free-tier |

### Recommendation
- **Primary: Google Cloud TTS** — you already have the GCP project, and the **Chirp3-HD / Neural2 / Studio** female voices are natural and warm, with **Indian-English** options. 1M free chars/mo easily covers an MVP.
- **Premium option: ElevenLabs** — if you want the single most charming/emotive voice, add it as a "premium voice" persona (mind the 10k char/mo free cap).
- Keep **browser Web Speech as a zero-cost fallback** when no TTS key is set or the quota is hit.

### Voice personas (what the user picks)
Map friendly names → real neural voices, e.g. (Google Cloud):
| Persona | Gender | Voice id (example) | Vibe |
|---------|--------|--------------------|------|
| **Aria** | female | `en-US-Chirp3-HD-*` / `en-US-Studio-O` | warm, natural |
| **Sofia** | female | `en-IN-Chirp3-HD-*` | Indian-English, friendly |
| **Maya** | female | `en-US-Neural2-F` | soft, calm |
| **David** | male | `en-US-Neural2-D` | confident |
| **Arjun** | male | `en-IN-Neural2-B` | Indian-English |

Selector in the header replaces the ♀/♂ toggle with a small voice picker (name + gender).

---

## Part C — Architecture change (server-side TTS)

Today the wire is text-only; browser speaks. New flow:

```
you speak → browser STT → text → server
                                    │
                        LLM (OpenRouter) → reply text
                                    │
                        Neural TTS (server) → audio (mp3/opus)
                                    │
        server → browser:  {ai_text} + audio bytes
                                    │
   browser: play audio  +  Web Audio analyser → REAL lip-sync (mouth follows sound)
```

Key points:
- **STT stays in the browser** (still free). Only **TTS moves server-side.**
- Server streams audio over the existing WebSocket (base64 or binary frames).
- Browser plays via an `<audio>` / Web Audio node, and an **AnalyserNode** reads live amplitude → drives the mouth. This is *real* lip-sync, not the current guess.
- **Cache** common lines (greetings, "thinking…") so they're instant and don't burn quota.
- **Fallback:** if TTS key missing/over quota → use browser `speechSynthesis` (today's behavior).

Trade-offs: adds network + synth latency (~300–700ms before audio starts) and a quota to watch. Mitigate with streaming + caching + a fallback.

---

## Part D — Anime character redesign

Current face = a simple round cartoon. Target = an **appealing anime character** (big expressive eyes, hair, soft shading, blush) that lip-syncs and emotes.

### Build options
| Option | Look | Effort | Lip-sync | Verdict |
|--------|------|--------|----------|---------|
| **Upgraded SVG anime face** | stylized, big eyes, hair, blush; code-drawn | medium | viseme mouth shapes driven by audio | **Phase 1 — best control, lightweight, on-brand** |
| **Rive character** | fully rigged, lively, state machines | medium-high (needs art in Rive) | mouth states + amplitude | **Phase 2 — premium liveliness, still light** |
| **Live2D** | true anime "VTuber" feel, physics | high (art + runtime) | viseme params | Phase 3 — if we want a mascot |
| **AI-rendered portrait + mouth overlay** | photoreal-anime image | low look, hard sync | weak | not recommended (sync limited) |

### Recommendation
- **Phase 1: hand-crafted SVG anime face.** Big shiny eyes (with highlights), eyebrows, soft bangs/hair in brand gold accents, subtle blush, and a **viseme-based mouth** (several mouth shapes: closed, small, wide, "O", etc.) selected by the real audio amplitude/energy. Blink, breathe, head tilt, eye-look per state. Attractive, expressive, fully controllable, tiny file.
- **Phase 2: Rive.** Rig a real anime character in Rive with a state machine (idle/listen/think/speak + blink) — very lively, still lightweight, plays in-browser. Best "wow" without Live2D's weight.

### Expressions per state
- **Speaking:** viseme mouth shapes from audio + slight brow raise, eyes bright.
- **Listening:** attentive — eyes slightly wide, gentle head tilt, sparkle, closed smile.
- **Thinking:** eyes look up, small "hmm" mouth, finger-to-chin (optional), amber accent.
- **Idle:** breathe, blink, occasional soft smile.

### Lip-sync (real, not guessed)
- With neural-TTS audio, run a Web Audio **AnalyserNode**: sample loudness each frame → pick a viseme (0=closed … 4=wide open). Optional: use frequency bands for slightly better vowel shapes.
- If we use **Azure/ElevenLabs**, they can emit **viseme/timing events** → phoneme-accurate mouth shapes (best quality). Google → amplitude-based (still great).

---

## Part E — Roadmap

**P0 — Real voice (the big win)**
1. Pick provider (recommend **Google Cloud TTS** — you have GCP). Enable the API, get a key/service account.
2. Add server-side `synthesize(text, voice) → audio`. Stream audio over WS. Browser plays it.
3. Real lip-sync via Web Audio analyser (works with current face immediately).
4. Fallback to browser TTS when no key/quota.

**P1 — Voice personas**
5. Map 3–5 named voices (female + male, incl. Indian-English). Replace ♀/♂ toggle with a voice picker. Persist choice. Add a "preview" play button.

**P2 — Anime face**
6. Redesign the SVG as an anime character (eyes, hair, blush, visemes).
7. Wire visemes to the audio analyser + expressions per state.

**P3 — Premium character (optional)**
8. Rive-rigged character with a state machine, or Live2D mascot.
9. ElevenLabs "premium voice" persona for the most emotive option.

---

## Part F — What I need from you to start P0

Pick the voice provider (this decides the key/setup):
- **Google Cloud TTS** — you already have the GCP project; biggest free tier; natural voices incl. Indian-English. *(recommended)*
- **ElevenLabs** — most charming/emotive voice, but only 10k free chars/mo.
- **Azure Neural** — great free tier + expressive styles + Indian voices.

Once you choose, I'll: enable it, add the server TTS + audio streaming + real lip-sync, then the voice picker, then the anime face.

---

*One change (server-side neural TTS) fixes the robotic voice, adds voice personas, and powers real lip-sync for the new anime character. Everything else builds on it.*
