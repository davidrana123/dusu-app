# DuSu character art — drop the 8 PNG frames here

Put these files in **this folder** (`backend/assets/assistant/`), exact names,
all lowercase, **transparent PNG**, **portrait 1536×2048**, identical
pose/framing/lighting/clothing — only the eyes/mouth change between frames.

| File | What changes (everything else identical) |
|------|--------------|
| `idle.png` | main — eyes open, mouth closed, small smile |
| `blink.png` | same as idle, **eyes closed** |
| `talk_01.png` | eyes open, mouth **slightly** open |
| `talk_02.png` | eyes open, mouth **medium** open |
| `talk_03.png` | eyes open, mouth **wide** open |
| `happy.png` | bigger smile, bright eyes |
| `thinking.png` | eyes looking slightly up, small smile |
| `listening.png` | gentle smile, attentive eyes |

**Consistency:** generate `idle.png` first, then EDIT only the eyes/mouth of that
same image for the other 7 (Photoshop Generative Fill or the model's edit mode) —
keeps hair/face/body pixel-identical so the animation doesn't flicker.

Once `idle.png` exists, the app auto-switches from the placeholder SVG to the
real animated character (breathing, blink, lip-sync, head tilt). No code change —
just refresh. Missing an optional frame → falls back to `idle.png`.

**Minimum to test:** `idle.png` + `talk_01.png` + `blink.png`.

Framing in the gold ring is tuned via 3 CSS vars (`--zoom / --shiftX / --shiftY`
on `.acore` in `test_client.html`) — tell me if it sits wrong and I'll adjust.

Served at: `/assets/assistant/<name>.png`.
