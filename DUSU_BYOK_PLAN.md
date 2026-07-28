# DuSu — Bring-Your-Own-Token (Office vs Personal) — Plan

**Status:** PLAN ONLY (no code yet). Decide the open questions at the bottom before building.
**Why:** Company employees will use DuSu. Instead of everyone burning *our* free quota, an employee (Office mode) can plug in *their own* free API keys. Casual/personal users keep using our default keys.

---

## 1. User flow

```
New user → first launch
        ↓
   "How will you use DuSu?"
   ┌───────────────┬────────────────────────┐
   │  🏠 Personal   │  🏢 Office / My company │
   └───────────────┴────────────────────────┘
        │                     │
        │                     ▼
        │            "Add your free AI keys"
        │            ┌─────────────────────────┐
        │            │ Gemini API key   [____] │
        │            │ OpenRouter key   [____] │
        │            │ GitHub token     [____] │
        │            │ Groq API key     [____] │
        │            │        [ Verify & save ] │
        │            └─────────────────────────┘
        │            (add any/all — chain uses whichever are valid,
        │             tried in the same order as our default chain)
        ▼                     ▼
  use OUR default        use THEIR keys
  keys (from .env)       (per user)
```

- The choice is remembered (per user). Can be changed later in **More → Settings → AI keys**.
- Office mode with **no valid key** must fail gracefully → fall back to a clear "add a working key" message (NOT silently use our default, or one employee drains our quota — decide in open Q3).

---

## 2. How LLM keys work TODAY (baseline)

- `backend/app/config.py` → `Settings` loads global keys from **`.env`**: `GEMINI_API_KEY`, `GROQ_API_KEY`, `OPENROUTER_API_KEY`, `GITHUB_TOKEN`.
- `Settings.providers()` builds a **fixed fallback chain** (gemini → groq → openrouter → github). Each provider entry already hard-codes the **base_url, model list, headers, extra body** — only the **key** comes from env.
- `backend/app/providers/openrouter_provider.py` → `_complete()` walks `settings.providers()` (global, same for everyone) and calls the OpenAI-compatible endpoint.
- The WS/HTTP requests carry the **auth session token** (`auth.read_session`), NOT any API key.

**Implication:** today keys are **global + server-side**. BYOK means keys become **per-user** and must reach `_complete()` on a per-request basis.

---

## 3. Key question: "Is just a token enough?" — per provider

Because base_url / models / headers are already known in `providers()`, the user only needs to supply the **key** — *for the providers where that's literally all it is*. Details differ:

| Provider | What the user gives | Is a key alone enough? | Gotchas |
|---|---|---|---|
| **Gemini** | Google AI Studio API key | ✅ Yes | Free-tier quota is tied to *their* Google account. Endpoint rejects some params (we already dropped `reasoning_effort`). |
| **OpenRouter** | OpenRouter API key | ✅ Yes | We must keep sending `HTTP-Referer`/`X-Title`. Only `:free` models; some flip to paid (already saw 404) → key alone won't fix a model that's no longer free. |
| **GitHub Models** | GitHub **PAT** | ⚠️ Key + **correct scope** | The token must have the **`models`** permission. A normal PAT without it → 401/403. Needs clear instructions + validation. |
| **Groq** | Groq API key | ✅ Yes | **Included** (4th field). Fast + reliable; key alone works. |

**Office mode offers all 4** (Gemini · OpenRouter · GitHub · Groq) — same providers as our default chain, same order. User can fill any subset; the chain is built from whichever validate.

**Answer:** For Gemini + OpenRouter + Groq, a key alone works. For GitHub, the token must be a PAT with the `models` scope — so we **must validate** and **guide** the user, not just accept any string.

---

## 4. Where do we store the per-user keys? (the real design decision)

Three options, security-ranked:

**Option A — Client-only (localStorage), sent per request.**
- Keys never persisted on our server; sent over WSS/HTTPS with each LLM call; server builds a per-request chain and forgets them.
- ➕ We never hold employee secrets (low liability). ➖ Keys sit in browser localStorage → exposed to any XSS; lost on cache clear; re-enter per device.

**Option B — Server DB (Neon), encrypted at rest, per user.**
- Store `enc(key)` in a `user_keys` row; decrypt server-side per request.
- ➕ Works across devices; server controls access. ➖ We now hold employee API secrets → real liability; needs a real encryption key (KMS/secret), key rotation, audit, "never log" discipline.

**Option C — Hybrid:** client-only by default; optional "remember on this account" → Option B.

**DECIDED → Option B (server DB).** We already store user data, so office users' data + their AI keys are stored server-side too. The **only** difference between a Personal and an Office user is *which AI keys power their sessions* (ours vs their own). Keys are encrypted at rest (see §7). Everything else (profile, progress, activity) is identical and lives in the same DB.

---

## 5. Env vars & config changes

### 5.0 How our DEFAULT keys work today — local `.env` vs Render env vars (important)
You set the keys **manually in the Render dashboard → Environment**. That is correct and nothing here breaks it:

- `config.py` uses **pydantic-settings** (`SettingsConfigDict(env_file=".env")`). pydantic reads from the **process environment first**, and *also* loads a local `.env` file if present.
- **On Render:** there is no `.env` file — Render **injects** the dashboard variables (`GEMINI_API_KEY`, `GROQ_API_KEY`, `OPENROUTER_API_KEY`, `GITHUB_TOKEN`, `GOOGLE_CLIENT_ID`, `DATABASE_URL`, …) as real process env vars → `Settings()` picks them up automatically. Same variable names.
- **On local dev:** you keep a local `.env` file (git-ignored) with the same names → same `Settings()`.
- So: **local `.env` and Render env vars are the same variables, just two places they come from.** These are **DuSu's default keys = Personal mode**.

```
                 ┌── local dev:  backend/.env file ──┐
GEMINI_API_KEY   │                                    │→ os.environ → Settings() → default chain
GROQ_API_KEY     │── Render:   dashboard Env vars ────┘        (Personal mode)
...
```

### 5.1 What BYOK adds (does NOT touch Render env)
- **Render/`.env` keys stay exactly as they are** = the shared default for Personal mode. BYOK never writes to them.
- **Office keys are per-user, runtime** — supplied by the employee, held per Option A/B, and passed into the chain **per request**. They are *not* environment variables and are *never* added to Render.
- Rule of thumb: **env var = one shared default for everyone; BYOK = one set per user.** Two independent layers.

### 5.2 Config refactor
- **`.env` / Render vars stay** = our **default (Personal mode)** keys. Nothing about BYOK goes in env (env is global, BYOK is per-user).
- `Settings.providers()` refactor: split into
  - `providers()` → default chain (unchanged, from env), used for Personal.
  - `providers_from(keys: dict)` → build a chain from a **caller-supplied** `{gemini, openrouter, github, groq}` dict (reusing the same base_url/models/headers), used for Office. Missing keys are skipped; order matches the default chain.
- `_complete()` gains an optional `chain` argument (defaults to `settings.providers()`); every caller (WS handler, `/assessment`, `/letter`, `/greeting`, lesson/level endpoints) must thread through the per-user chain when present.
- Add a `/keys/verify` endpoint: given the 3 keys, do a tiny 1-token test call per provider, return `{gemini:ok, openrouter:ok, github:ok|scope_error}`.

---

## 6. Data / API surface

- Client persists `dusu_mode` = `personal|office` and (Option A) `dusu_keys` = `{gemini, openrouter, github, groq}` in localStorage.
- Requests that trigger the LLM include a `keys` object (Office) or nothing (Personal). WS `start` payload + each POST endpoint.
- Server: if `mode==office` and keys present → `providers_from(keys)`; else default chain. If Office but chain empty/invalid → return a clear error, do **not** fall back to our keys (Open Q3).

---

## 7. Security (CRITICAL — treat keys as secrets)

- **Transport:** only over HTTPS/WSS (already true in prod). Never in a URL/querystring — body only.
- **Never log** keys (scrub before any `print`/error). Today `_complete` logs errors — must ensure keys aren't in messages.
- **localStorage risk (Option A):** XSS would leak keys → tighten: no untrusted HTML injection, consider CSP. Keys are the user's own free keys (limited blast radius) but still secrets.
- **DB (Option B):** encrypt at rest with a server-held secret (env `DUSU_ENC_KEY`), decrypt only in memory per call, add access controls, rotation, and an audit note. This crosses into "handling user secrets" → **security review required** before shipping.
- **Validation call** must itself not leak the key in logs.

---

## 8. Validation flow (so it's not "paste anything")

1. User pastes keys → tap **Verify**.
2. `/keys/verify` runs a cheap `max_tokens:1` "say OK" call per provider (like the probe we already used).
3. Show per-field ✅ / ❌ with a specific reason ("GitHub token needs the *models* permission", "OpenRouter key invalid", "Gemini quota exhausted").
4. Save only the keys that pass; Office mode needs **≥1** working key.

---

## 9. Cost / quota / attribution

- BYOK's whole point: **each employee's usage hits their own free quota**, not ours. Verify the per-request chain truly uses their key (no accidental fallback to env).
- Personal mode still shares our quota → keep the existing daily session cap (`MAX_SESSIONS`).
- Optional: show "using your keys" vs "using DuSu's shared keys" indicator so users know.

---

## 10. Edge cases

- Key valid at save, dies mid-session (quota hit) → surface "your Gemini quota ran out, add another key / switch key", don't silently use ours.
- Only 1 of 3 keys provided → chain of 1 (fine).
- User switches Personal↔Office → re-render, re-route chain.
- New device (Option A) → keys not there → re-prompt.
- Employee shares a key across many logins → their quota, their problem (acceptable).
- Non-Chrome/Edge (no Web Speech) is unrelated but still applies.

---

## 11. Phased plan (once questions below are answered)

1. **DB migration** — extend `users` (role/status/mode), add `office_keys` (encrypted), `daily_usage`; seed owner + unlimited allowlist. (foundation)
2. **Config refactor** — `providers_from(keys)` + `_complete(chain=…)`; no behaviour change for Personal. (small, safe)
3. **/keys/verify** endpoint (reuse the probe pattern).
4. **Onboarding choice** UI (Personal/Office) + Office 4-key form + Verify + store server-side (Option B, encrypted).
5. **Thread keys** through WS start + all LLM POST endpoints (office → their chain; personal → default).
6. **Access gate** — server enforces `status` (pending/blocked → 403 + locked screen); auto-active for owner/unlimited.
7. **Admin dashboard** (owner-only APIs + `#admin` screen): users, activity, per-day usage, approve/block/set-role.
8. **Usage rollup + limits** — `daily_usage` writes; base caps for `user` role; unlimited for owner/allowlist (still shown). Detailed limit rules = follow-up plan.
9. **Settings → AI keys** (edit/replace/clear, re-verify; masked display).
10. **Security pass** (encrypt keys, log scrubbing, no-fallback rule, owner-gate on admin, CSP note) — mandatory review.

---

## 12. Roles & access control

Every user has a **role** and a **status**. Stored in the DB `users` row.

| Role | Who | AI keys | Usage limit | Admin dashboard |
|---|---|---|---|---|
| **owner** | `david123rana` | ours (or own if office) | **unlimited** | ✅ full access |
| **unlimited** | `shuhanisuhana037@gmail.com` (+ allowlist) | ours (or own if office) | **unlimited** (but usage still shown) | ❌ |
| **user** | everyone else | ours (personal) or own (office) | **limited** (needs approval + caps) | ❌ |

- **Owner** = `david123rana` (confirm exact email — is it `david123rana@gmail.com`?). Full admin.
- **Unlimited allowlist** = a small hard-list (starts with `shuhanisuhana037@gmail.com`). No caps, but we **still track & show** their usage.
- Allowlist lives server-side (env var `UNLIMITED_EMAILS` or a DB flag) so it's editable without a redeploy → prefer a DB `role` column the owner can set from the dashboard.

## 13. Approval & blocking

**Approval is required ONLY for Office mode. Personal is open** (no approval) — the owner can block a personal user later from the dashboard.

```
sign in (Personal, default) → status "active" → use immediately
        │
        └── user switches to OFFICE ──► status "pending"
                                        → owner sees them in dashboard
                                        → Approve → "active" (office keys now work)
                                          (unapproved office user cannot use office keys)
owner can Block anyone, anytime → status "blocked" → app locked with a message
```

- `status` ∈ `active | pending | blocked`.
- **Personal user →** `active` on first sign-in (no approval). Fully usable with our default keys.
- **Office user →** `pending` the moment they choose Office; needs owner **Approve** before their office keys are used. (Decide in Q17: while pending, do they stay usable on Personal, or fully locked?)
- **Owner + unlimited allowlist →** auto-`active`, never pending (even in Office).
- **Blocked →** any user; server rejects LLM calls (`403`), client shows "your access has been paused — contact admin".
- Enforced **server-side** on every LLM endpoint + WS start (never trust the client).

## 14. Admin dashboard (owner only)

A new **owner-only** screen (`/admin` route + `#admin` screen, or a separate page). Gated by `role == owner` server-side.

**Shows:**
- **All users**: email, name, role, status, mode (personal/office), joined date, last active.
- **Activity per user**: total sessions, total speaking minutes, XP/streak, **per-day usage** (sessions/minutes each day — a small bar/heatmap).
- **"Time invested"**: sum of session seconds per user per day.
- **Actions**: Approve · Block · Unblock · set role (user↔unlimited) · (optional) reset limits.
- **Overview**: today's active users, total users, pending count.

**Data source:** we already record sessions (`db.record_practice` / `bump_daily_stat` store seconds + turns). Add a per-day rollup + an admin read API (`/admin/users`, `/admin/user/:id`, `/admin/approve`, `/admin/block`, `/admin/role`) — all owner-gated.

## 15. Usage limits & tracking

- **owner + unlimited** → no cap; dashboard/app still **shows** how much they've used (transparency).
- **user (limited)** → capped. Reuse the existing daily cap (`MAX_SESSIONS`) as the base; exact limits (per-day sessions, minutes, cooldowns, lock rules) to be detailed in a **follow-up plan** (user said limits come later).
- **Office users** consume **their own** keys' quota → their AI cost is theirs; our per-user *session* cap may be relaxed for office (their keys, their quota) — decide later.
- Every session already logs seconds + turns; add a lightweight `daily_usage(user_id, date, sessions, seconds)` rollup for fast dashboard + limit checks.

## 16. Data model (DB — extends current schema)

- **users** (extend): `email, name, role[owner|unlimited|user], status[pending|active|blocked], mode[personal|office], created_at, last_active_at`.
- **office_keys** (new, Option B): `user_id, gemini_enc, openrouter_enc, github_enc, groq_enc, updated_at` — values **encrypted** with server secret `DUSU_ENC_KEY` (env). Never returned to client in plaintext (send only masked `••••1234` + verified-status).
- **daily_usage** (new rollup): `user_id, date, sessions, seconds` (for dashboard + limits).
- Sessions/summaries/progress: already exist — reused for activity.
- **Defaults:** new user → `role=user, mode=personal, status=active` (Personal is open). Choosing Office flips `mode=office, status=pending` (until owner approves), unless owner/unlimited.
- **Seeding:** on boot/login, force `role=owner` for `david123rana`, `role=unlimited` for the allowlist, both `status=active` always.

## 17. OPEN QUESTIONS / CHALLENGES (decide these first)

1. ~~Storage?~~ **DECIDED: Option B** — server DB stores user data + office keys (encrypted). Only difference office vs personal = which AI keys are used.
2. ~~Which providers in Office mode?~~ **DECIDED: all 4** — Gemini · OpenRouter · GitHub · Groq (fill any subset).
3. **Office with no/invalid key:** hard-fail with a message, or fall back to our default keys? (Falling back defeats the purpose + drains our quota → recommend hard-fail.)
4. **Who counts as "office"?** Just a self-selected toggle, or gated (e.g., company email domain / invite)? Any abuse risk if anyone picks Personal and uses our keys freely?
5. **Encryption (if Option B):** where does the encryption key live (env secret? KMS?) and who can decrypt? Rotation policy?
6. **Validation cost:** the verify call uses a tiny bit of the user's quota — acceptable? Cache "verified" status for how long?
7. **GitHub PAT UX:** users will fumble the `models` scope — do we add a step-by-step "how to create the token" help + link?
8. **Multiple employees, one shared company key** — allowed, or one-key-per-user? (Quota implications.)
9. **Key visibility:** mask in the UI (show •••• with reveal)? Never echo back a saved key from the server (Option B)?
10. **Migration:** existing users default to Personal automatically? Prompt them once?
11. **Do keys belong per-user or per-session?** (Affects whether we re-ask each login in Option A.)
12. **Legal/liability:** we hold employees' API keys (Option B) — confirm encryption + "never returned in plaintext" is enough; who can access the DB?
13. **Exact owner email:** is it `david123rana@gmail.com`? Confirm the string we hard-check for `role=owner`.
14. **Unlimited allowlist mechanism:** hard-coded env `UNLIMITED_EMAILS` (redeploy to change) vs owner sets `role=unlimited` from the dashboard (no redeploy)? *(Recommend dashboard/DB.)*
15. **Limit rules for `user` role** (later plan): per-day sessions? minutes? cooldown? lock after N? Office users capped or not (their own keys)?
16. **Admin dashboard surface:** a screen inside the app (`#admin`, owner-only) or a separate protected page? Any need to export/download usage?
17. **Office pending state:** while an Office user waits for approval, can they still use **Personal** (our keys), or are they fully locked until approved? *(Recommend: usable on Personal meanwhile — less friction.)*

---

*Next step: answer §12, then I'll build §11 phase 1 (config refactor) behind the same review gate.*
