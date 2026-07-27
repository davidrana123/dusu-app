# DuSu — Cloudflare local-first + Render fallback (setup)

One stable URL `https://dusu.ranabrothers.online` that serves DuSu from **your PC** when
it's on, and **Render** when it's off. Same **Neon** DB either way (no data split).

```
app / users
      │
      ▼
https://dusu.ranabrothers.online   ← Cloudflare Worker (worker.js)
      │  PC up? ──yes──► https://pc.ranabrothers.online  → cloudflared → your PC :8000
      │           └─no──► https://dusu-app-1.onrender.com (Render)
      ▼
                     Neon Postgres  (single DB, used by BOTH)
```

Prereqs: Node (for `wrangler`), the backend `.venv`, a Cloudflare account with
`ranabrothers.online` added. The interactive login steps must be run by you.

---

## 1. Run the backend on your PC (points at the SAME Neon DB)

`backend/.env` must have the real `DATABASE_URL` (the Neon URL — same one Render uses) +
the LLM keys. Then:

```powershell
cd "C:\Personal Work\English Specking\backend"
.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Health check: open http://127.0.0.1:8000/health → should be OK.

---

## 2. Cloudflare Tunnel → your PC (`pc.ranabrothers.online`)

```powershell
winget install --id Cloudflare.cloudflared        # or scoop/choco
cloudflared tunnel login                          # opens browser → pick ranabrothers.online
cloudflared tunnel create dusu-pc                 # note the tunnel UUID it prints
cloudflared tunnel route dns dusu-pc pc.ranabrothers.online
```

Create `%USERPROFILE%\.cloudflared\config.yml`:

```yaml
tunnel: dusu-pc
credentials-file: C:\Users\LENOVO\.cloudflared\<TUNNEL-UUID>.json
ingress:
  - hostname: pc.ranabrothers.online
    service: http://localhost:8000
  - service: http_status:404
```

Run it (and install as an always-on service so it survives reboots):

```powershell
cloudflared tunnel run dusu-pc          # test in foreground
cloudflared service install             # then: auto-start on boot
```

Verify: https://pc.ranabrothers.online/health → OK (proves the tunnel reaches your PC).

---

## 3. Deploy the failover Worker (`dusu.ranabrothers.online`)

```powershell
npm install -g wrangler
cd "C:\Personal Work\English Specking\cloudflare"
wrangler login
wrangler deploy
```

The Worker route needs the hostname to resolve through Cloudflare. In the Cloudflare
dashboard → `ranabrothers.online` → DNS, add a **proxied** placeholder record so the
route binds (the Worker intercepts before it matters):

```
Type AAAA   Name dusu   Content 100::   Proxied (orange cloud) ON
```

Verify: `curl https://dusu.ranabrothers.online/health` → OK when PC is on; turn the PC
off (or stop the tunnel) and it should still answer via Render.

---

## 4. Point the app at the new origin (ONLY after steps 1–3 pass)

Edit `android-twa/app/src/main/res/values/strings.xml`:

```xml
<string name="launchUrl">https://dusu.ranabrothers.online/</string>
<string name="hostName">dusu.ranabrothers.online</string>
<string name="asset_statements">[{"relation":["delegate_permission/common.handle_all_urls"],"target":{"namespace":"web","site":"https://dusu.ranabrothers.online"}}]</string>
```

Digital Asset Links must be served at `https://dusu.ranabrothers.online/.well-known/assetlinks.json`
— the Worker proxies it from whichever origin is up (the FastAPI route already returns it
from `ANDROID_CERT_SHA256`). Confirm:

```
curl https://dusu.ranabrothers.online/.well-known/assetlinks.json
```

Then rebuild the APK (`android-twa/README.md` step 1) and reinstall.

---

## 5. Google Sign-In note

The Google OAuth **Authorized JavaScript origins** must include
`https://dusu.ranabrothers.online` (add it in Google Cloud Console → Credentials), or
sign-in will fail on the new origin. Keep the Render origin listed too.

---

## Cost

Domain (you have it) + Cloudflare Tunnel (free) + Workers (free tier: 100k req/day) +
Neon (free) + Render (free standby). Effectively $0 beyond the domain.
