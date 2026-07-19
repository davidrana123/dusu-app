# DuSu — Free Deployment Plan

Goal: get DuSu live on the internet, **$0/month**, with a public HTTPS URL anyone can open.

---

## 0. What we're deploying

**One service.** The FastAPI backend serves *everything*:
- the frontend (`GET /` → `test_client.html`)
- the logo (`/logo.png`)
- Google auth (`POST /auth/google`)
- the live interview (`/ws/interview` WebSocket)

Speech (STT/TTS) runs **in the user's browser** — nothing to host. The LLM is **OpenRouter** (called server-side). So deploying = deploying one Python web service. Simple.

### Hard requirements (why host choice matters)
| Need | Why | Rules out |
|------|-----|-----------|
| **WebSockets** | live interview stream | Vercel, Netlify (serverless) |
| **Always-on process** | WS + FastAPI | pure serverless / edge functions |
| **HTTPS** | mic (`getUserMedia`), Web Speech, Google Sign-In all require secure origin | plain http hosts |

---

## 1. Free host options (WebSocket-capable)

| Host | Free tier | WS | HTTPS | Sleeps? | Best for |
|------|-----------|----|-------|---------|----------|
| **Render** ⭐ | 750 hrs/mo web service | ✅ | ✅ (auto) | sleeps after ~15 min idle (cold start ~30–50s) | **easiest — recommended** |
| **Fly.io** | small shared VM allowance | ✅ | ✅ | can keep 1 always-on | best if you want no cold start (needs card) |
| **Koyeb** | 1 free service | ✅ | ✅ | sleeps on free | simple alternative |
| **Hugging Face Spaces** | free CPU (Docker) | ✅ | ✅ | sleeps after inactivity | good if you like HF |

**Recommendation: Render** — no card needed, Git-based deploy, HTTPS + WS out of the box. Cold start on the free tier is the only real downside (first visit after idle is slow). Fly.io if you want it always warm.

---

## 2. Pre-deploy checklist (do these first)

### 2.1 🔴 Security — rotate & never commit secrets
- The OpenRouter key was pasted in chat earlier → **rotate it** at openrouter.ai and use the new one.
- `.env` is git-ignored (good) — secrets go in the **host's env vars**, never in the repo.
- Confirm `.gitignore` excludes: `.env`, `.venv/`, `users.db`, `__pycache__/`. (It does.)
- `logo.png` **must** be committed (it's needed) — it is not ignored. Good.

### 2.2 Bind to the host's port
Free hosts inject a `$PORT`. Start command must use it:
```
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

### 2.3 Add deploy files (in `backend/`)
**`Procfile`** (Render/Koyeb read this):
```
web: uvicorn app.main:app --host 0.0.0.0 --port $PORT
```
**`runtime.txt`** (pin Python):
```
python-3.13.1
```
(Ask me — I'll generate both files.)

### 2.4 Put the code on GitHub
Render/Fly/HF deploy from Git. This folder isn't a repo yet.
```
git init
git add .
git commit -m "DuSu v0"
# create an empty repo on github.com, then:
git remote add origin https://github.com/<you>/dusu.git
git branch -M main
git push -u origin main
```
> The **root dir** for the service is `backend/` (that's where `app/`, `requirements.txt`, `Procfile` live). Set that as the "root directory" in the host, or move `backend/*` to repo root.

---

## 3. Deploy on Render (step by step)

1. **render.com** → sign up (GitHub login).
2. **New → Web Service** → connect your GitHub repo.
3. Settings:
   - **Root Directory:** `backend`
   - **Runtime:** Python
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   - **Instance Type:** Free
4. **Environment → add variables:**
   | Key | Value |
   |-----|-------|
   | `OPENROUTER_API_KEY` | your **new** OpenRouter key |
   | `OPENROUTER_BASE_URL` | `https://openrouter.ai/api/v1` |
   | `LLM_MODELS` | `openai/gpt-oss-20b:free,nvidia/nemotron-3-super-120b-a12b:free,meta-llama/llama-3.3-70b-instruct:free` |
   | `GOOGLE_CLIENT_ID` | your `...apps.googleusercontent.com` |
   | `SESSION_SECRET` | a long random string |
5. **Create Web Service** → wait for build → you get a URL like `https://dusu.onrender.com`.

---

## 4. Point Google OAuth at the live URL

Google Sign-In only works on **registered origins**. localhost won't cover prod.

1. console.cloud.google.com → project **DuSu** → **Google Auth Platform → Clients** → your Web client.
2. **Authorized JavaScript origins → + Add URI:**
   ```
   https://dusu.onrender.com
   ```
   (keep `http://localhost:8000` too, for local dev)
3. Save. (Changes can take a few minutes to propagate.)

No code change needed — the client already uses the current origin for `wss://` and same-origin API calls.

---

## 5. Data persistence (important caveat)

Free hosts have **ephemeral disk** — `users.db` (SQLite) is **wiped on every redeploy/restart**. Fine for a demo (users just sign in again — Google re-creates the row). For real persistence, add a free Postgres later:

- **Neon** or **Supabase** (free Postgres) → swap the SQLite store in `app/auth.py` for Postgres.
- Small change; do it when you have real users. Not needed to launch.

---

## 6. Post-deploy smoke test

Open `https://<your-app>` and check:
- [ ] Login screen loads (logo, "Continue with Google")
- [ ] Google sign-in works (origin registered)
- [ ] Home welcome speaks your name (needs the sign-in click gesture)
- [ ] Start a Conversation → mic prompt → DuSu replies with voice (face lip-syncs)
- [ ] Start an Interview → adaptive Qs → End → report renders
- [ ] `https://<app>/health` → `{"ok":true,"has_key":true}`

---

## 7. Known gotchas on free tier

- **Cold start (Render/Koyeb/HF):** first visit after ~15 min idle is slow (~30–50s) while the service wakes. Normal. Optional fix: a free cron pinger (e.g. cron-job.org) hitting `/health` every 10 min keeps it warm — but that partly defeats "free/idle". Or use **Fly.io** with 1 always-on machine.
- **OpenRouter free 429s:** free models are rate-limited harder from a shared server IP. The fallback chain helps; if it stalls often, add a few $ of OpenRouter credit (raises *your* limits) or drop one paid model into `LLM_MODELS`.
- **Web Speech quirks:** STT/TTS quality/voices vary by the *user's* browser (Chrome/Edge best) — unaffected by hosting.
- **HTTPS is mandatory** for mic + Google — every host above gives it automatically. Never serve DuSu over plain http in prod.

---

## 8. Optional polish (after it's live)

- **Custom domain** — Render/Fly let you attach `dusu.app` (domain costs money; subdomain is free).
- **Keep-alive cron** — if cold start annoys you.
- **Postgres** — real user persistence (§5).
- **Analytics** — a privacy-light counter to see usage.
- **OG/social card** — nice preview when the link is shared.

---

## 9. TL;DR fastest path

1. Rotate OpenRouter key.
2. I generate `Procfile` + `runtime.txt`.
3. Push `backend/` to GitHub.
4. Render → New Web Service → root `backend`, add 5 env vars, deploy.
5. Add `https://<app>.onrender.com` to Google OAuth origins.
6. Open the URL, sign in, talk to DuSu. 🎉

---

*Want me to generate the deploy files (`Procfile`, `runtime.txt`) and a `.gitignore` at repo root now? Say go.*
