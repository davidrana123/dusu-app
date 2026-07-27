# DuSu — Local-first (Cloudflare) + Render fallback — PLAN

Status: **plan / not yet built** (except App items 1 & 2, which ARE implemented — see bottom).
Date: 2026-07-27.

The goal in your words: run DuSu on **your own machine for free** (frontend + backend +
DB, local-first via Cloudflare), and **fall back to the cloud (Render + Neon)** when your
machine is off. Below is the honest, workable version — including the trap to avoid.

## DECISIONS (finalized 2026-07-27)

- **Domain:** `ranabrothers.online` (on Cloudflare ✅).
- **Product URL:** `https://dusu.ranabrothers.online` (a **subdomain** — recommended for a
  TWA/PWA: whole origin is the app, scope `/`, and `/.well-known/assetlinks.json` sits at
  the host root). You asked for `ranabrothers.online/dusu-talk` (a path) — that also works
  via the Worker but needs path-rewriting + the PWA served under `/dusu-talk/`; messier.
  **Going with the subdomain unless you say otherwise.**
- **DB = Option A (single Neon), FINAL.** Compute (frontend+backend) is local-first; the
  DB is always Neon so nothing splits. Local SQLite is intentionally NOT used (see §3).
- **Fallback:** Render (`dusu-app-1.onrender.com`) stays the cloud standby.
- **Failover front door:** a **Cloudflare Worker** at `dusu.ranabrothers.online` that tries
  your PC first, falls back to Render. Code: `cloudflare/worker.js`; setup: `cloudflare/README.md`.

Concrete hostnames:

| Host                          | What                                            |
|-------------------------------|-------------------------------------------------|
| `dusu.ranabrothers.online`    | Worker — the ONE URL the app + users hit        |
| `pc.ranabrothers.online`      | Cloudflare Tunnel → your PC's `localhost:8000`  |
| `dusu-app-1.onrender.com`     | Render — cloud fallback                         |
| Neon Postgres                 | the single DB (both PC and Render use it)       |

---

## 0. Two meanings of "offline" (must not mix them up)

1. **User's phone has no internet** → nothing can work (local-tunnel and Render both
   need the internet). → App shows a "turn on internet" screen. **(App item 1 — DONE.)**
2. **Your PC / tunnel is down** → the site should fall back to Render. → This is the
   Cloudflare failover below. It is a *server-side* concern, invisible to the phone.

---

## 1. App-side (android-twa) — DONE this round

- **Item 1 — Offline gate:** custom `MainActivity` checks connectivity before opening
  the TWA. No internet → 📡 "No Internet Connection · please turn it on" + **Retry**.
  Online → launches the in-app Chrome (TWA).
- **Item 2 — Notifications every 4 hours:** `AlarmManager` inexact repeat (battery
  friendly), rotating DuSu-voice messages, re-armed after reboot. Tap → opens the app.

These are independent of the hosting plan below.

---

## 2. The hosting idea, stated correctly

"SQLite deployed via Cloudflare" is not literally possible — **SQLite is a file**, read
by a backend process, not a network service. What you actually mean:

> Run the **FastAPI backend on my PC** (which uses a **local SQLite file**), expose it
> to the internet **free** with a **Cloudflare Tunnel**, and use **Render** only when my
> PC is off.

That IS doable. Pieces:

| Piece            | Primary (your PC, free)                  | Fallback (cloud)              |
|------------------|------------------------------------------|-------------------------------|
| Compute (API/WS) | FastAPI on PC via **cloudflared** tunnel | Render web service            |
| Database         | **SQLite file** on PC                    | Neon Postgres (Render)        |
| Frontend         | Served by the same FastAPI (one file)    | Render (or Vercel static)     |

---

## 3. ⚠️ The one real decision — the database split

If the **PC uses SQLite** and **Render uses Postgres**, they are **two separate
databases**. A user who talks to DuSu while your PC is on writes to SQLite; when your PC
is off they hit Render's Postgres — **their history, level, streak, keys are missing**,
then reappear later. Data silently diverges. For a login-based app with memory/streaks
this is a real bug, not a nitpick.

Pick ONE:

- **Option A — Single cloud DB, local compute (RECOMMENDED).** PC backend and Render
  backend BOTH point at the **same Neon Postgres**. Only *compute* is local/free; the DB
  is always consistent. You still save money (Neon free tier), the tunnel gives you a
  free front door, Render is a true hot standby. **No divergence.** Drop local SQLite.
- **Option B — Local SQLite is the source of truth; Render is read-only emergency.**
  Render can't write (or writes are lost). Simplest but Render becomes near-useless when
  your PC is off (no new sessions persist). Only OK if the app is basically single-user
  / your own testing.
- **Option C — SQLite primary + scheduled one-way sync SQLite→Postgres.** Real
  multi-DB. Most work, sync conflicts, eventual consistency. Not worth it for now.

**Recommendation: Option A.** It gives you "free local hosting + Render fallback" without
the data trap. If you truly want on-device SQLite later, revisit Option C.

> If you want Option B/C instead, say so and I'll redo section 4/5 accordingly.

---

## 4. Failover front door — one stable URL (Cloudflare Worker)

A TWA is locked to **one origin** (asset-links + trusted origin). It cannot flip between
`pc-tunnel.example.com` and `dusu-app-1.onrender.com` at runtime and stay full-screen.
So failover must happen **behind a single hostname**.

Cleanest free option: a **Cloudflare Worker** at e.g. `https://app.dusu.<domain>`:

```
request → Worker:
   try  fetch(PC_TUNNEL_ORIGIN)   with a short timeout / health gate
   on failure or 5xx → fetch(RENDER_ORIGIN)
   stream the response back (incl. WebSocket upgrade for /ws/interview)
```

- The **app + assetlinks live on the Worker domain** (`app.dusu.<domain>`), which never
  changes. The Worker decides PC-vs-Render per request.
- WebSocket: Workers support WS proxying; verify `/ws/interview` upgrades pass through.
- Needs a domain on Cloudflare (free plan) + Workers (free tier). No Load Balancer
  (that's paid) — the Worker does the health-fallback in code.

Alternative (no Worker): Cloudflare **Load Balancing** (paid ~$5/mo) with origin health
checks. Cleaner but not free. Skip for now.

---

## 5. Build steps (once Option A is chosen)

1. **DB driver:** `backend/app/db.py` currently assumes Postgres/asyncpg. For Option A it
   stays Postgres (Neon) — no change. (Local SQLite would need `aiosqlite` + a URL branch;
   only if Option B/C.)
2. **Run backend on PC:** `.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1
   --port 8000` with `DATABASE_URL` = the Neon URL (same as Render) + the LLM keys.
3. **Cloudflare Tunnel:**
   - Install `cloudflared`. `cloudflared tunnel login` (pick your CF domain).
   - `cloudflared tunnel create dusu-pc`
   - Route: `cloudflared tunnel route dns dusu-pc pc.dusu.<domain>`
   - Run: `cloudflared tunnel run dusu-pc` → maps `pc.dusu.<domain>` → `localhost:8000`.
   - Auto-start on boot: install as a Windows service (`cloudflared service install`).
4. **Worker** (section 4) at `app.dusu.<domain>` with
   `PC_TUNNEL_ORIGIN=https://pc.dusu.<domain>`, `RENDER_ORIGIN=https://dusu-app-1.onrender.com`.
5. **Point the app at the Worker:** in `android-twa/app/src/main/res/values/strings.xml`
   set `launchUrl` + `hostName` + `asset_statements` to `app.dusu.<domain>`. Serve
   `/.well-known/assetlinks.json` from that host (the FastAPI route already does; the
   Worker must pass it through from whichever origin is up — or the Worker serves it
   itself with the same JSON).
6. **Render env** unchanged (`ANDROID_CERT_SHA256`, `DATABASE_URL`, keys).

---

## 6. Open questions — RESOLVED

1. DB → **Option A** (single Neon). ✅
2. Domain → **ranabrothers.online** on Cloudflare. ✅
3. Fallback → **Render** (Vercel can't host the FastAPI WebSocket backend). ✅

Only remaining input: confirm **subdomain** `dusu.ranabrothers.online` vs the path
`ranabrothers.online/dusu-talk`. Plan assumes the subdomain.

---

## 7. Not-yet-built checklist

- [ ] Decide DB option (§3)
- [ ] Cloudflare domain + Tunnel to PC (§5.3)
- [ ] Cloudflare Worker failover + WS passthrough (§4)
- [ ] Point TWA at the Worker origin + assetlinks there (§5.5)
- [ ] cloudflared auto-start service on PC (§5.3)
- [x] App offline gate (item 1)
- [x] App 4-hour notifications (item 2)
