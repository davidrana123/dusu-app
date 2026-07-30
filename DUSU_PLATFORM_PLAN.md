# DuSu — Platform v2 Plan (Super Admin · Free Quota · Subscription · Routing)

Date: 2026-07-30. Status: routing (Phase 1) done; this doc drives the rest.

## TL;DR / decisions
- **Framework:** stay **vanilla JS + a History-API router** now (Phase 1 — DONE). Migrate to React+Vite **later** when it pays off. The FastAPI backend is a clean API, so the migration is low-risk whenever we choose. (No users yet, but a working product — a rewrite now buys little vs. the router we already added.)
- **Access-model shift (the crux):**
  - **FREE** (default, everyone signed in): use **OUR keys**, capped at **10 model requests/day**; exhausted → subscription pop-up. This is the tier a brand-new user lands in after the test.
  - **OFFICE** (super-admin-approved emails): **BYOK** (their own keys), **no quota**; only these users see the **Keys** option.
  - **OWNER / UNLIMITED** (hard-coded emails): our keys, no quota.
  - This **replaces** today's "require_own_keys ON = everyone must BYOK." require_own_keys is retired; office-approval (the `office_emails` table) now means "BYOK-enabled," not "free access to our keys."
- **Onboarding:** login → level **test on OUR (owner) keys** → Home → FREE tier (10/day) → subscription upsell when exhausted.
- **Super Admin:** separate `/superadmin`, **static creds verified server-side** (`DuSuRuralAppAdmin` / `Sup$#307Admin`, env-overridable) → issues a signed super-admin session → full portal (all users, online status, usage, per-mode breakdown, session time, conversations, approve-office, block, delete). Desktop + mobile responsive.
- **Subscription:** 3 plans — Starter ₹299, Plus ₹599, Pro ₹899 — gate modes + daily request limit; select → Proceed → WIP payment (Razorpay later).

## Routes (v2)
`/` home · `/daily-talk` · `/face-to-face` · `/interview` · `/learn` · `/learning-journey` · `/practice` · `/leaderboard` · `/keys` (office only) · `/test` · `/more` · `/profile` · `/help-feedback` · `/dashboard` (owner) · `/superadmin` (static creds) · `/subscribe`. Guards: `auth` (all but `/superadmin`), `quota` (model routes, free tier), `office` (`/keys`).

## Data model additions (Neon, all new tables/columns — never mutate existing via create_all)
- **`usage_daily`** — `user_id, day (YYYY-MM-DD, local), requests (int)`. One row per user per local day. The quota counter.
- **`users.plan`** — `free|starter|plus|pro` (default `free`); **`users.plan_since`** (date). Added via `ALTER TABLE … ADD COLUMN IF NOT EXISTS`.
- **Office-approved** = present in existing **`office_emails`** (semantics flipped to "BYOK-enabled").
- **Analytics are derived** (no heavy new schema):
  - online = `users.last_seen` within 5 min (bump last_seen on /me, WS start, each turn).
  - conversations = count of `conversations` rows; **per-mode** = group `conversations.mode` (daily/conversation/interview/learning) per user.
  - usage = sum(`usage_daily.requests`) + today's; session time = `progress`/`daily_stats` seconds already recorded by `_persist_session`.

## Quota (request-based, server-enforced) — DONE
- **One request = one model-generating user turn** (each `user_text` on the WS that calls the LLM). "User gives answer → DuSu replies" = **1 request**. Server-opened first message (daily greeting) is **not** counted. The level **test itself is free/uncounted** (onboarding).
- Enforce **server-side** in the WS `user_text` handler: `charge_request(email, uid, day)` → OWNER/UNLIMITED/OFFICE bypass; FREE → trial check then `db.incr_request(uid, day, 10)`. If not allowed → `quota_exceeded` (with `trial_over` flag) and skip the LLM call.
- **20-day trial:** `FREE_TRIAL_DAYS = 20`, `trial_left(uid) = max(0, 20 - signup_day_count)`. Free tier = **10 requests/day for 20 days**; after day 20 → every turn blocked with `trial_over=true` → subscribe.
- **Reset:** per the user's **local day** (client sends `day` = `toLocaleDateString('en-CA')`; store `YYYY-MM-DD`; new local day = fresh 0). Fallback UTC.
- **Live header:** after each charged turn the WS pushes `quota_update {left, limit}`; client updates `userState.requests_left` + `updateReqChip()` so the header decrements **live** (no reload). Initial value from `/me` (`requests_left`, `request_limit`, `trial_days_left`, `trial_over`). Chip hidden for office/owner/unlimited; tooltip shows trial days left.
- **Limit / trial reached →** `quota_exceeded` (WS) or `gQuota` (route) → subscription pop-up → `/subscribe`. Message differs: daily-10 vs trial-ended.

## Subscription
- Plans: **Starter ₹299** (Daily + Journey + Face-to-Face, higher daily limit), **Plus ₹599** (+ Interview, more requests), **Pro ₹899** (all modes, unlimited). Stored in `users.plan`.
- Pop-up (quota hit / locked-mode tap) → `/subscribe` (3 cards) → select → **Proceed** (enabled on select) → **WIP** payment page (Razorpay TBD). On "purchase" (later) set `users.plan`; quota + mode-gates read the plan.

## Super Admin portal
- `POST /superadmin/auth` (static creds, constant-time) → returns a **signed super-admin token** (HMAC, short TTL). All `/superadmin/*` data endpoints require it (server-checked — never client-only).
- `GET /superadmin/overview` → every user with: email, name, online, plan, office?, status (active/blocked), joined, last_seen, XP/streak, total sessions/minutes, requests today + total, **per-mode counts** (daily/face-to-face/interview/journey), conversations.
- `POST /superadmin/approve` `{email,on}` → add/remove from `office_emails` (grants BYOK + Keys visibility).
- `POST /superadmin/action` `{user_id, block|unblock|delete}` (reuse `db.set_user_status` / `db.delete_user`).
- UI: responsive table (desktop) / stacked cards (mobile); per-user detail; approve-office toggle; block/delete.

## Office approval → Keys visibility
- Approved (in `office_emails`) → `officeAllowed()` true → **Keys** row + `/keys` visible + BYOK path + no quota.
- Not approved → Keys hidden, FREE tier + quota.

## Onboarding / access state machine
`new user signs in` → `/me onboarded=false` → **level test on our keys** (`/test`) → `/assessment` saves profile → **Home (FREE tier)** → uses modes counting against 10/day → **quota hit → subscribe pop-up** → (`/subscribe`) → paid plan raises/removes limit. `office-approved` → BYOK, no quota, Keys visible.

## Phased rollout (this build)
- **P1 — DB:** `usage_daily`, `users.plan/plan_since`, quota + analytics helpers.
- **P2 — Backend:** quota enforce (WS + LLM endpoints) + `/me` fields; last_seen bumps; super-admin session + `/superadmin/overview|approve|action`; per-mode analytics.
- **P3 — Frontend:** header counter, quota→subscribe pop-up, office-only Keys, onboarding on our keys, `/profile` `/help-feedback` `/dashboard` route aliases.
- **P4 — Super-admin portal UI** (responsive, full data + actions).
- **P5 — e2e Playwright:** quota+popup, superadmin approve-office, block/delete, all functional.
- **P6 — later:** Razorpay payments; React migration.

## Open decisions (owner)
- Exact per-plan daily limits (Starter/Plus numbers; Pro = unlimited).
- Reset timezone (assume user-local via client hour; fallback UTC).
- Payment provider (Razorpay assumed) — P6.
