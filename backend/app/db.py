"""Database layer — Neon Postgres via SQLAlchemy 2.0 async.

Graceful: if DATABASE_URL is empty the app still runs fully (stateless, as
before) — `db_enabled` is False and callers fall back to no-persistence.

Tables (v1):
  users     — one row per Google account
  profiles  — level + skill scores + learning goal (built by the assessment)
  progress  — xp, coins, streak, badges, roadmap %  (gamification)
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import String, Integer, Boolean, DateTime, Date, Text, ForeignKey, select, desc, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.orm.attributes import flag_modified

from .config import settings

# Roadmap constants (mirror the client CURRICULUM so the server can detect
# level completion). One entry per level → number of lessons in it.
LEVEL_LESSON_COUNTS = {1: 5, 2: 5, 3: 5, 4: 5, 5: 5, 6: 5, 7: 5}
MAX_LEVEL = 7
XP_PER_LESSON = 20
# Every level now ends with a Boss Challenge (scored test) that gates level-up.
LEVELS_WITH_TEST = {1, 2, 3, 4, 5, 6, 7}


def _start_level(cefr: str) -> int:
    """Assessment CEFR level → roadmap starting level."""
    return {"A0": 1, "A1": 1, "A2": 2, "B1": 3, "B2": 4}.get((cefr or "A1").upper(), 1)


def _daily_goal(practice_time: str) -> int:
    """practice_time answer → lessons/day target."""
    p = practice_time or ""
    if "30" in p:
        return 7
    if "20" in p:
        return 5
    if "10" in p:
        return 3
    return 2  # 5 min/day or unknown


def _normalize_url(url: str) -> str:
    """Neon hands out `postgresql://...?sslmode=require&channel_binding=...`.
    asyncpg needs the `+asyncpg` driver and rejects those query params (SSL is
    passed via connect_args instead), so strip them."""
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        url = "postgresql+asyncpg://" + url[len("postgresql://"):]
    if "?" in url:
        url = url.split("?", 1)[0]
    return url


db_enabled = bool(settings.database_url)
_engine = None
_Session: async_sessionmaker[AsyncSession] | None = None

if db_enabled:
    _engine = create_async_engine(
        _normalize_url(settings.database_url),
        pool_pre_ping=True,
        connect_args={"ssl": True},   # Neon requires TLS
    )
    _Session = async_sessionmaker(_engine, expire_on_commit=False)


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)   # Google "sub"
    email: Mapped[str] = mapped_column(String(255), default="")
    name: Mapped[str] = mapped_column(String(255), default="")
    picture: Mapped[str] = mapped_column(String(512), default="")
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)
    last_seen: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)
    status: Mapped[str] = mapped_column(String(16), default="active")     # active | pending | blocked
    mode: Mapped[str] = mapped_column(String(16), default="personal")    # personal | office


class Profile(Base):
    __tablename__ = "profiles"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), primary_key=True)
    onboarded: Mapped[bool] = mapped_column(Boolean, default=False)
    goal: Mapped[str] = mapped_column(String(64), default="")
    comfort: Mapped[str] = mapped_column(String(64), default="")
    practice_time: Mapped[str] = mapped_column(String(32), default="")
    level: Mapped[str] = mapped_column(String(8), default="A0")
    # skill scores 0-100
    scores: Mapped[dict] = mapped_column(JSONB, default=dict)
    weak_areas: Mapped[list] = mapped_column(JSONB, default=list)
    assessed_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Progress(Base):
    __tablename__ = "progress"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), primary_key=True)
    xp: Mapped[int] = mapped_column(Integer, default=0, index=True)   # leaderboard sort/rank
    coins: Mapped[int] = mapped_column(Integer, default=0)
    streak_days: Mapped[int] = mapped_column(Integer, default=0)
    last_active: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    sessions_today: Mapped[int] = mapped_column(Integer, default=0)
    daily_goal: Mapped[int] = mapped_column(Integer, default=5)
    badges: Mapped[list] = mapped_column(JSONB, default=list)
    journey: Mapped[dict] = mapped_column(JSONB, default=dict)


class Memory(Base):
    """The emotional layer: one JSONB doc per user — nickname, interests, dream,
    events, check-ins, daily stats, baseline/future-me, learned facts, last letter."""
    __tablename__ = "memory"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), primary_key=True)
    facts: Mapped[dict] = mapped_column(JSONB, default=dict)


class Conversation(Base):
    """One row per finished conversation/interview/free-practice session — a
    short LLM summary DuSu can recall later ('last time we talked about...')."""
    __tablename__ = "conversations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    mode: Mapped[str] = mapped_column(String(32), default="")
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)
    summary: Mapped[str] = mapped_column(Text, default="")


async def init_db() -> None:
    if not db_enabled:
        return
    from sqlalchemy import text as _text
    async with _engine.begin() as conn:      # type: ignore[union-attr]
        await conn.run_sync(Base.metadata.create_all)
        # create_all won't add an index to an already-existing table → do it explicitly
        await conn.execute(_text("CREATE INDEX IF NOT EXISTS ix_progress_xp ON progress (xp DESC)"))
        # add new columns to an already-existing users table (create_all won't ALTER)
        await conn.execute(_text("ALTER TABLE users ADD COLUMN IF NOT EXISTS status varchar(16) DEFAULT 'active'"))
        await conn.execute(_text("ALTER TABLE users ADD COLUMN IF NOT EXISTS mode varchar(16) DEFAULT 'personal'"))


def _state(user: User, prof: Profile, prog: Progress, mem: "Memory | None" = None) -> dict:
    """Everything the client needs about a returning user (incl. emotional memory)."""
    return {
        "user": {"id": user.id, "email": user.email, "name": user.name, "picture": user.picture,
                 "created_at": user.created_at.isoformat() if user.created_at else None},
        "status": getattr(user, "status", "active") or "active",
        "mode": getattr(user, "mode", "personal") or "personal",
        "onboarded": prof.onboarded,
        "profile": {
            "goal": prof.goal, "comfort": prof.comfort, "practice_time": prof.practice_time,
            "level": prof.level, "scores": prof.scores or {}, "weak_areas": prof.weak_areas or [],
        },
        "progress": {
            "xp": prog.xp, "coins": prog.coins, "streak_days": prog.streak_days,
            "sessions_today": prog.sessions_today, "daily_goal": prog.daily_goal,
            "badges": prog.badges or [], "journey": prog.journey or {},
        },
        "memory": (mem.facts or {}) if mem else {},
    }


async def login(claims: dict) -> dict:
    """Upsert the user on Google login; create profile+progress if new.
    Returns the full state dict (onboarded flag drives first-run assessment)."""
    uid = claims.get("sub") or claims.get("email")
    async with _Session() as s:               # type: ignore[misc]
        user = await s.get(User, uid)
        if user is None:
            user = User(id=uid)
            s.add(user)
        user.email = claims.get("email", user.email or "")
        user.name = claims.get("name", user.name or "")
        user.picture = claims.get("picture", user.picture or "")
        user.last_seen = _now()

        prof = await s.get(Profile, uid)
        if prof is None:
            prof = Profile(user_id=uid, scores={}, weak_areas=[])
            s.add(prof)
        prog = await s.get(Progress, uid)
        if prog is None:
            prog = Progress(user_id=uid, badges=[], journey={})
            s.add(prog)
        mem = await s.get(Memory, uid)
        if mem is None:
            mem = Memory(user_id=uid, facts={})
            s.add(mem)

        await s.commit()
        return _state(user, prof, prog, mem)


async def save_assessment(user_id: str, data: dict, lang: str = "en") -> dict:
    """Persist assessment results → mark onboarded, and SEED the roadmap journey.
    `data` has goal, comfort, practice_time, level, scores{}, weak_areas[]."""
    async with _Session() as s:               # type: ignore[misc]
        prof = await s.get(Profile, user_id)
        if prof is None:
            prof = Profile(user_id=user_id)
            s.add(prof)
        prof.goal = data.get("goal", prof.goal)
        prof.comfort = data.get("comfort", prof.comfort)
        prof.practice_time = data.get("practice_time", prof.practice_time)
        prof.level = data.get("level", prof.level)
        prof.scores = data.get("scores", {}) or {}
        prof.weak_areas = data.get("weak_areas", []) or []
        prof.onboarded = True
        prof.assessed_at = _now()

        # Seed the roadmap from the assessment (starting level + daily goal + lang).
        prog = await s.get(Progress, user_id)
        if prog is None:
            prog = Progress(user_id=user_id, badges=[], journey={})
            s.add(prog)
        start = _start_level(prof.level)
        prog.journey = {
            "start_level": start,
            "current_level": start,
            "completed": {},
            "lang": lang,
            "sentences_spoken": 0,
        }
        prog.daily_goal = _daily_goal(prof.practice_time)
        flag_modified(prog, "journey")

        await s.commit()
        user = await s.get(User, user_id)
        return _state(user, prof, prog)


async def complete_lesson(user_id: str, level: int, lesson_id: str, lesson_type: str = "") -> dict:
    """Mark a lesson done: update journey, award XP, streak, daily count, badges,
    and unlock the next level when the current one is finished."""
    async with _Session() as s:               # type: ignore[misc]
        prog = await s.get(Progress, user_id)
        if prog is None:
            prog = Progress(user_id=user_id, badges=[], journey={})
            s.add(prog)
        j = dict(prog.journey or {})
        j.setdefault("start_level", 1)
        j.setdefault("current_level", 1)
        j.setdefault("completed", {})
        j.setdefault("sentences_spoken", 0)

        completed = dict(j["completed"])
        done = list(completed.get(str(level), []))
        first_time = lesson_id not in done
        if first_time:
            done.append(lesson_id)
            completed[str(level)] = done
            j["completed"] = completed
            j["sentences_spoken"] = int(j["sentences_spoken"]) + 1
            prog.xp = (prog.xp or 0) + XP_PER_LESSON

        # daily count + streak (only advance on the first lesson of a new day)
        today = dt.date.today()
        if prog.last_active != today:
            if prog.last_active == today - dt.timedelta(days=1):
                prog.streak_days = (prog.streak_days or 0) + 1
            else:
                prog.streak_days = 1
            prog.sessions_today = 0
            prog.last_active = today
        if first_time:
            prog.sessions_today = (prog.sessions_today or 0) + 1

        # Level-up: finishing every lesson unlocks the next level, UNLESS this
        # level has a Level Test — those levels wait for submit_level_test.
        leveled_up = False
        cur = int(j["current_level"])
        total = LEVEL_LESSON_COUNTS.get(cur, 5)
        if (level == cur and len(completed.get(str(cur), [])) >= total
                and cur < MAX_LEVEL and cur not in LEVELS_WITH_TEST):
            j["current_level"] = cur + 1
            leveled_up = True

        # badges
        badges = list(prog.badges or [])
        new_badges = []
        def _award(bid):
            if bid not in badges:
                badges.append(bid); new_badges.append(bid)
        total_done = sum(len(v) for v in completed.values())
        if total_done >= 1: _award("first_lesson")
        if lesson_type == "converse": _award("first_converse")
        if (prog.streak_days or 0) >= 7: _award("streak_7")
        if int(j["sentences_spoken"]) >= 100: _award("sentences_100")
        if leveled_up: _award("level_up")

        prog.journey = j
        prog.badges = badges
        flag_modified(prog, "journey")
        flag_modified(prog, "badges")
        await s.commit()

        user = await s.get(User, user_id)
        prof = await s.get(Profile, user_id) or Profile(user_id=user_id)
        return {"progress": _state(user, prof, prog)["progress"],
                "leveled_up": leveled_up, "new_badges": new_badges}


async def submit_level_test(user_id: str, level: int, score: int) -> dict:
    """Record a Level Test attempt. Passing (score>=70) unlocks the next level
    (only if this was the level the learner is currently on)."""
    passed = score >= 70
    async with _Session() as s:               # type: ignore[misc]
        prog = await s.get(Progress, user_id)
        if prog is None:
            prog = Progress(user_id=user_id, badges=[], journey={})
            s.add(prog)
        j = dict(prog.journey or {})
        j.setdefault("start_level", 1)
        j.setdefault("current_level", 1)
        j.setdefault("completed", {})
        j.setdefault("sentences_spoken", 0)
        test_scores = dict(j.get("test_scores", {}))
        prev = test_scores.get(str(level), {"best": 0, "attempts": 0, "passed": False})
        test_scores[str(level)] = {
            "best": max(int(prev.get("best", 0)), score),
            "attempts": int(prev.get("attempts", 0)) + 1,
            "passed": bool(prev.get("passed", False)) or passed,
        }
        j["test_scores"] = test_scores

        leveled_up = False
        cur = int(j["current_level"])
        if passed and level == cur and cur < MAX_LEVEL:
            j["current_level"] = cur + 1
            leveled_up = True

        badges = list(prog.badges or [])
        new_badges = []
        def _award(bid):
            if bid not in badges:
                badges.append(bid); new_badges.append(bid)
        if leveled_up: _award("level_up")
        if score >= 90: _award("courage_confident")   # aced a challenge

        prog.journey = j
        prog.badges = badges
        flag_modified(prog, "journey")
        flag_modified(prog, "badges")
        await s.commit()

        user = await s.get(User, user_id)
        prof = await s.get(Profile, user_id) or Profile(user_id=user_id)
        return {"progress": _state(user, prof, prog)["progress"],
                "leveled_up": leveled_up, "new_badges": new_badges, "passed": passed}


# ---------------- Leaderboard (all-time XP, private aliases) ----------------

_ALIAS_ADJ = ["Brave", "Swift", "Bright", "Bold", "Clever", "Calm", "Mighty", "Noble",
              "Kind", "Sharp", "Sunny", "Lucky", "Royal", "Golden", "Cosmic", "Fierce"]
_ALIAS_ANIMAL = ["Tiger", "Fox", "Eagle", "Lion", "Panda", "Hawk", "Wolf", "Owl",
                 "Falcon", "Otter", "Dolphin", "Cheetah", "Bear", "Deer", "Sparrow", "Cobra"]


def _alias(user_id: str) -> str:
    """Stable, deterministic playful alias per user (no per-process randomness)."""
    n = sum(ord(c) for c in (user_id or "x"))
    return f"{_ALIAS_ADJ[n % len(_ALIAS_ADJ)]}{_ALIAS_ANIMAL[(n // 7) % len(_ALIAS_ANIMAL)]}"


async def leaderboard(me_id: str, limit: int = 20) -> dict:
    """Top-N users by all-time XP (private aliases) + the caller's own rank."""
    async with _Session() as s:               # type: ignore[misc]
        rows = (await s.execute(
            select(User.id, Progress.xp, Progress.streak_days, Progress.journey)
            .join(Progress, Progress.user_id == User.id)
            .order_by(desc(Progress.xp)).limit(limit)
        )).all()
        top = []
        for i, r in enumerate(rows):
            j = r.journey or {}
            top.append({
                "rank": i + 1,
                "alias": _alias(r.id),
                "xp": r.xp or 0,
                "streak": r.streak_days or 0,
                "level": (j.get("current_level") if isinstance(j, dict) else None) or 1,
                "is_me": r.id == me_id,
            })
        # caller's own row + rank (even if outside the top-N)
        me_prog = await s.get(Progress, me_id)
        me_user = await s.get(User, me_id)
        me_mem = await s.get(Memory, me_id)
        you = None
        if me_prog is not None:
            my_xp = me_prog.xp or 0
            higher = (await s.execute(
                select(func.count()).select_from(Progress).where(Progress.xp > my_xp)
            )).scalar() or 0
            mf = (me_mem.facts if me_mem else {}) or {}
            you = {
                "rank": higher + 1,
                "name": mf.get("nickname") or (me_user.name if me_user else "You"),
                "xp": my_xp,
                "streak": me_prog.streak_days or 0,
                "level": (me_prog.journey or {}).get("current_level", 1) if isinstance(me_prog.journey, dict) else 1,
            }
        return {"top": top, "you": you}


async def get_state(user_id: str) -> dict | None:
    async with _Session() as s:               # type: ignore[misc]
        user = await s.get(User, user_id)
        if user is None:
            return None
        prof = await s.get(Profile, user_id) or Profile(user_id=user_id)
        prog = await s.get(Progress, user_id) or Progress(user_id=user_id)
        mem = await s.get(Memory, user_id)
        return _state(user, prof, prog, mem)


# ---------------- Emotional memory helpers ----------------

_MAX_CHECKINS = 30
_MAX_VOCAB = 500
_MAX_FACTS = 40

# --- S1: 4-type memory (Companion System) ---
# Identity + Relationship live in facts (never expire). Moments expire; Achievements never.
_MOMENT_TTL_DAYS = 7          # emotional moments fade after a week
_MAX_MOMENTS = 40
_MAX_ACHIEVEMENTS = 60
# Relationship Journey (internal, invisible to the user) — drives DuSu's tone.
_REL_STAGES = ["Guest", "Friend", "Practice Partner", "Coach", "Mentor", "Companion"]
# Journey worlds (mirror the client) — story, not level numbers.
_WORLD_NAMES = ["The Village", "The Street", "The City", "The Workplace",
                "The Interview Hall", "The Boardroom", "The Global Stage"]


def _prune_moments(moms: list) -> list:
    """Drop expired moments (Moment memory = 2–7 day shelf life)."""
    today = _now().date().isoformat()
    return [m for m in (moms or [])
            if isinstance(m, dict) and (m.get("expires") or "9999-12-31") >= today]


def _add_moments(f: dict, moms: list) -> None:
    cur = list(f.get("moments") or [])
    now = _now()
    exp = (now + dt.timedelta(days=_MOMENT_TTL_DAYS)).date().isoformat()
    for m in moms:
        if isinstance(m, str):
            m = {"text": m}
        if not isinstance(m, dict) or not (m.get("text") or "").strip():
            continue
        cur.append({"text": m["text"].strip(),
                    "emotion": (m.get("emotion") or "").strip(),
                    "created": now.date().isoformat(),
                    "expires": m.get("expires") or exp})
    f["moments"] = _prune_moments(cur)[-_MAX_MOMENTS:]


def _add_achievements(f: dict, achs: list) -> None:
    cur = list(f.get("achievements") or [])
    have = {a.get("text") for a in cur if isinstance(a, dict)}
    today = _now().date().isoformat()
    for a in achs:
        if isinstance(a, str):
            a = {"text": a}
        if not isinstance(a, dict):
            continue
        t = (a.get("text") or "").strip()
        if not t or t in have:
            continue
        cur.append({"text": t, "date": a.get("date") or today})
        have.add(t)
    f["achievements"] = cur[-_MAX_ACHIEVEMENTS:]


async def _get_or_make_memory(s, user_id: str) -> "Memory":
    # row-lock so concurrent writers (WS finally + /checkin, two tabs) don't
    # clobber each other's full-doc JSONB write (lost-update race).
    try:
        mem = await s.get(Memory, user_id, with_for_update=True)
    except Exception:
        mem = await s.get(Memory, user_id)
    if mem is None:
        mem = Memory(user_id=user_id, facts={})
        s.add(mem)
    return mem


async def get_memory(user_id: str) -> dict:
    async with _Session() as s:               # type: ignore[misc]
        mem = await s.get(Memory, user_id)
        f = dict(mem.facts) if mem and mem.facts else {}
        if f.get("moments"):                  # never surface expired moments
            f["moments"] = _prune_moments(f["moments"])
        return f


async def relationship_stage(user_id: str) -> dict:
    """S3 — internal Relationship Journey (Guest→Companion). Drives DuSu's tone. Never shown."""
    async with _Session() as s:               # type: ignore[misc]
        u = await s.get(User, user_id)
        sessions = (await s.execute(
            select(func.count(Conversation.id)).where(Conversation.user_id == user_id)
        )).scalar() or 0
    days = (_now() - u.created_at).days if (u and u.created_at) else 0
    if   sessions <= 1 and days < 1: idx = 0
    elif sessions < 4:               idx = 1
    elif sessions < 10:              idx = 2
    elif sessions < 25:              idx = 3
    elif sessions < 60:              idx = 4
    else:                            idx = 5
    return {"stage": _REL_STAGES[idx], "idx": idx, "days": days, "sessions": sessions}


async def build_companion_context(user_id: str) -> dict:
    """S3 — everything DuSu needs to sound like she knows + cares about this user."""
    f = await get_memory(user_id)
    stage = await relationship_stage(user_id)
    async with _Session() as s:               # type: ignore[misc]
        prog = await s.get(Progress, user_id)
    cur = int(((prog.journey if prog else {}) or {}).get("current_level", 1) or 1)
    world = _WORLD_NAMES[cur - 1] if 0 <= cur - 1 < len(_WORLD_NAMES) else ""
    identity = {k: f[k] for k in ("nickname", "profession", "dream", "native_lang") if f.get(k)}
    if f.get("interests"):
        identity["interests"] = f["interests"]
    return {
        "identity": identity,
        "relationship": f.get("relationship") or {},
        "moments": _prune_moments(f.get("moments") or [])[-6:],
        "achievements": (f.get("achievements") or [])[-6:],
        "energy_today": f.get("energy_today") or {},
        "stage": stage, "world": world, "level": cur,
        "next_hook": f.get("next_hook", ""),
    }


_TODAY_CHALLENGES = [   # by weekday (0=Mon) — the home belongs to *today*
    ("Monday reset", "New week — introduce the 'new you' in English.", "conversation"),
    ("Tell me a story", "Something small that made you smile recently.", "conversation"),
    ("Two-minute challenge", "Can you speak for 2 minutes — no Hindi?", "conversation"),
    ("Interview muscle", "One tough interview question, together.", "interview"),
    ("Friday win", "Tell me about a small victory this week.", "conversation"),
    ("Weekend talk", "Relax — chat with me about anything.", "daily"),
    ("Sunday dream", "Picture your dream. Say it out loud in English.", "conversation"),
]


async def build_growth(user_id: str) -> dict:
    """S6 — growth as *becoming*, not points: confidence, vocabulary, transformation timeline."""
    async with _Session() as s:               # type: ignore[misc]
        u = await s.get(User, user_id)
        prog = await s.get(Progress, user_id)
        mem = await s.get(Memory, user_id)
    f = dict(mem.facts) if mem and mem.facts else {}
    streak = (prog.streak_days if prog else 0) or 0
    journey = (prog.journey if prog else {}) or {}
    cur_level = int(journey.get("current_level", 1) or 1)
    total_sent = int(f.get("total_sentences", 0))
    total_min = int(f.get("total_seconds", 0)) // 60
    vocab_total = int(f.get("vocab_total", 0))
    today = _now().date().isoformat()
    vocab_today = int(((f.get("daily_stats") or {}).get(today) or {}).get("new_words", 0))

    # Confidence — a felt composite (0-96), with a delta vs last time.
    conf = min(96, 28 + streak * 3 + min(30, total_sent // 8)
               + (cur_level - 1) * 6 + vocab_total // 40)
    last = int(f.get("last_confidence", 0))
    delta = conf - last
    if conf != last:                          # persist the new baseline (best-effort)
        try:
            async with _Session() as s:       # type: ignore[misc]
                m2 = await _get_or_make_memory(s, user_id)
                g = dict(m2.facts or {}); g["last_confidence"] = conf
                m2.facts = g; flag_modified(m2, "facts"); await s.commit()
        except Exception:
            pass

    # Transformation timeline — Day 1 join + real achievements, by day number.
    first = (u.created_at.date() if (u and u.created_at) else _now().date())
    items = [{"day": 1, "icon": "✨", "text": "You met DuSu"}]
    for a in (f.get("achievements") or []):
        try:
            ad = dt.date.fromisoformat(a.get("date"))
            items.append({"day": (ad - first).days + 1, "icon": "✅", "text": a.get("text", "")})
        except Exception:
            continue
    items = sorted(items, key=lambda x: x["day"])[-6:]

    return {
        "confidence": {"value": conf, "delta": delta},
        "vocabulary": {"total": vocab_total, "today": vocab_today},
        "streak": streak, "sentences": total_sent, "minutes": total_min,
        "dream": f.get("dream", ""), "dream_pct": round(cur_level / MAX_LEVEL * 100),
        "timeline": items,
    }


# A clear, well-named activity (name, action, plain what-you'll-do, icon, meta)
_GOALS = {
    "talk":      ("Talk with me, face to face", "conversation", "A relaxed English chat — just speak, I'll keep it going.", "💬", "~5 min"),
    "journey":   ("Tell me about your day",      "daily",        "Chat in Hinglish about your life — learn as we go.",        "🌱", "~5 min"),
    "learn":     ("Continue your learning",      "learning",     "Say it in Hindi → I say it in English → you repeat.",       "📖", "~4 min"),
    "roadmap":   ("Pick up your lessons",        "journey",      "Your guided path — one step at a time.",                    "🗺️", "guided"),
    "interview": ("Prepare for your interview",  "interview",    "A real mock interview, then a scored report.",              "🎯", "mock + score"),
    "challenge": ("Today's challenge",           "conversation", "Speak for 2 minutes — no Hindi. Can you?",                  "⭐", "2 min"),
}


def _goal_card(key: str, why: str = "") -> dict:
    g = _GOALS[key]
    c = {"key": key, "goal": g[0], "action": g[1], "desc": g[2], "icon": g[3], "meta": g[4]}
    if why:
        c["why"] = why
    return c


async def build_opening(user_id: str) -> str:
    """The Companion Moment — DuSu's memory-aware first line on Start Speaking."""
    f = await get_memory(user_id)
    if f.get("next_hook"):
        return f"Last time we started something — {f['next_hook']}. Shall we pick it up?"
    sums = await recent_summaries(user_id, 1)
    if sums:
        return f"I was just thinking about last time — {sums[0]}"
    achs = f.get("achievements") or []
    if achs:
        return f"You did something great recently: {achs[-1].get('text','')}. Ready for more?"
    moms = _prune_moments(f.get("moments") or [])
    if moms:
        return f"You mentioned {moms[-1].get('text','')}. How's that going?"
    stage = await relationship_stage(user_id)
    if stage["idx"] == 0:
        return "I'm really glad you're here. Let's find your voice together."
    return "Good to see you again. What shall we work on today?"


async def build_recommendations(user_id: str) -> dict:
    """Invisible ranking → 3 curated goals (primary carries a 'why'). Intent → feature."""
    f = await get_memory(user_id)
    async with _Session() as s:               # type: ignore[misc]
        prog = await s.get(Progress, user_id)
        prof = await s.get(Profile, user_id)
    streak = (prog.streak_days if prog else 0) or 0
    last = prog.last_active if prog else None
    journey = (prog.journey if prog else {}) or {}
    cur_level = int(journey.get("current_level", 1) or 1)
    today = _now().date()
    gap = (today - last).days if last else 99
    energy = (f.get("energy_today") or {}).get("value", "")
    onboarded = bool(prof and prof.onboarded)

    # interview event within a week?
    iv_days = None
    for e in (f.get("events") or []):
        if e.get("type") == "interview" and e.get("date"):
            try:
                d = (dt.date.fromisoformat(e["date"]) - today).days
                if 0 <= d <= 7 and (iv_days is None or d < iv_days):
                    iv_days = d
            except Exception:
                pass

    if iv_days is not None:
        primary = _goal_card("interview", f"your interview is only {iv_days} day{'s' if iv_days != 1 else ''} away")
    elif f.get("next_hook"):
        primary = _goal_card("journey", "let's pick up where we left off")
    elif gap >= 3:
        primary = _goal_card("talk", "it's been a few days — let's ease back in")
    elif energy in ("low", "tired", "sad"):
        primary = _goal_card("talk", "let's take it gentle today")
    elif streak >= 2:
        primary = _goal_card("learn", f"you're on a {streak}-day roll — keep it going")
    elif energy in ("great", "confident", "excited"):
        primary = _goal_card("challenge", "you sound confident today — let's push a little")
    elif not onboarded or cur_level <= 1:
        primary = _goal_card("learn", "let's build your foundation")
    else:
        primary = _goal_card("talk", "a few minutes keeps you sharp")

    # Always show a clear trio: primary + one "connect" + one "learn".
    picks = [primary["key"]]
    def _add(k):
        if k not in picks and len(picks) < 3:
            picks.append(k)
    if not any(p in ("talk", "journey") for p in picks):            # ensure a connect option
        _add("journey" if primary["key"] != "journey" else "talk")
    if not any(p in ("learn", "roadmap", "interview", "challenge") for p in picks):  # ensure a learn option
        for k in (["interview"] if iv_days is not None else []) + ["learn", "roadmap"]:
            _add(k); break
    for k in ["talk", "journey", "learn", "roadmap", "interview", "challenge"]:      # fill if needed
        _add(k)
    cards = [primary if k == primary["key"] else _goal_card(k) for k in picks[:3]]
    return {"primary": cards[0], "second": cards[1], "third": cards[2]}


async def build_today(user_id: str) -> dict:
    """S4 — the one dynamic 'today' card. Never the same two days running."""
    ctx = await build_companion_context(user_id)
    async with _Session() as s:               # type: ignore[misc]
        prog = await s.get(Progress, user_id)
        mem = await s.get(Memory, user_id)
    f = dict(mem.facts) if mem and mem.facts else {}
    streak = (prog.streak_days if prog else 0) or 0
    sessions_today = (prog.sessions_today if prog else 0) or 0
    last = prog.last_active if prog else None
    today = _now().date()

    # 1. A promise DuSu made last time (S5 story hook) — highest priority.
    hook = f.get("next_hook")
    if hook and sessions_today == 0:
        return {"type": "story", "emoji": "📖", "title": "Where we left off",
                "body": hook, "cta": "Continue", "action": "daily"}
    # 2. Streak about to break (practised yesterday, nothing today).
    if streak > 0 and last == today - dt.timedelta(days=1) and sessions_today == 0:
        return {"type": "streak", "emoji": "🔥", "title": f"Keep your {streak}-day streak alive",
                "body": "A few minutes today and it lives on.", "cta": "Continue", "action": "daily"}
    # 3. A live moment to care about.
    moments = ctx.get("moments") or []
    if moments and sessions_today == 0:
        m = moments[-1]
        return {"type": "moment", "emoji": "💭", "title": "I've been thinking…",
                "body": f"You mentioned {m.get('text','')}. How's that going?",
                "cta": "Tell DuSu", "action": "daily"}
    # 4. Celebrate a recent achievement.
    achs = ctx.get("achievements") or []
    if achs and sessions_today == 0:
        return {"type": "celebrate", "emoji": "⭐", "title": "Look what you did",
                "body": f"{achs[-1].get('text','')} — proud of you.", "cta": "Keep going", "action": "daily"}
    # 5. Day-of-week challenge (variety).
    t, b, action = _TODAY_CHALLENGES[today.weekday()]
    return {"type": "challenge", "emoji": "🎯", "title": t, "body": b, "cta": "Start", "action": action}


async def recent_summaries(user_id: str, limit: int = 3) -> list[str]:
    async with _Session() as s:               # type: ignore[misc]
        rows = (await s.execute(
            select(Conversation.summary).where(Conversation.user_id == user_id)
            .order_by(desc(Conversation.created_at)).limit(limit)
        )).scalars().all()
        return [r for r in rows if r]


async def save_about(user_id: str, about: dict) -> dict:
    """Persist the onboarding 'About you' facts + the Day-1 intro baseline."""
    async with _Session() as s:               # type: ignore[misc]
        mem = await _get_or_make_memory(s, user_id)
        f = dict(mem.facts or {})
        for k in ("nickname", "native_lang", "profession", "dream"):
            if about.get(k):
                f[k] = about[k]
        if about.get("interests"):
            f["interests"] = {**(f.get("interests") or {}), **about["interests"]}
        intro = (about.get("intro_text") or "").strip()
        if intro:
            fm = f.get("future_me") or {}
            if not fm.get("day1_text"):
                fm["day1_text"] = intro
                f["future_me"] = fm
            base = f.get("baseline") or {}
            if not base.get("intro_text"):
                base["intro_text"] = intro
                base["date"] = _now().date().isoformat()
                f["baseline"] = base
        mem.facts = f
        flag_modified(mem, "facts")
        await s.commit()
        return f


async def merge_facts(user_id: str, facts: dict, events: list) -> None:
    """Merge LLM-extracted facts/events from a finished conversation into memory."""
    async with _Session() as s:               # type: ignore[misc]
        mem = await _get_or_make_memory(s, user_id)
        f = dict(mem.facts or {})
        if isinstance(facts, dict):
            for k in ("nickname", "native_lang", "profession", "dream"):
                if facts.get(k):
                    f[k] = facts[k]
            if facts.get("interests"):
                f["interests"] = {**(f.get("interests") or {}), **facts["interests"]}
            notes = facts.get("notes") or facts.get("facts") or []
            if isinstance(notes, str):
                notes = [notes]
            if notes:
                learned = (f.get("facts_learned") or []) + [n for n in notes if n]
                f["facts_learned"] = list(dict.fromkeys(learned))[-_MAX_FACTS:]
            # S1/S2 — Relationship traits (never expire): how DuSu should behave.
            rel = facts.get("relationship")
            if isinstance(rel, dict) and rel:
                f["relationship"] = {**(f.get("relationship") or {}), **rel}
            # S1/S2 — emotional Moments (2–7 day shelf life) + Achievements (permanent).
            if isinstance(facts.get("moments"), list) and facts["moments"]:
                _add_moments(f, facts["moments"])
            if isinstance(facts.get("achievements"), list) and facts["achievements"]:
                _add_achievements(f, facts["achievements"])
        if isinstance(events, list) and events:
            cur = f.get("events") or []
            seen = {(e.get("type"), e.get("date")) for e in cur}
            for e in events:
                if isinstance(e, dict) and (e.get("type"), e.get("date")) not in seen:
                    cur.append(e)
            f["events"] = cur[-20:]
        mem.facts = f
        flag_modified(mem, "facts")
        await s.commit()


async def set_next_hook(user_id: str, hook: str) -> None:
    """S5 — store the promise DuSu made for next time (story continuity)."""
    hook = (hook or "").strip()
    async with _Session() as s:               # type: ignore[misc]
        mem = await _get_or_make_memory(s, user_id)
        f = dict(mem.facts or {})
        if hook:
            f["next_hook"] = hook[:200]
        else:
            f.pop("next_hook", None)
        mem.facts = f
        flag_modified(mem, "facts")
        await s.commit()


async def add_conversation(user_id: str, mode: str, summary: str) -> None:
    if not (summary or "").strip():
        return
    async with _Session() as s:               # type: ignore[misc]
        s.add(Conversation(user_id=user_id, mode=mode, summary=summary.strip()))
        await s.commit()


async def save_checkin(user_id: str, mood: str, energy: str = "") -> dict:
    async with _Session() as s:               # type: ignore[misc]
        mem = await _get_or_make_memory(s, user_id)
        f = dict(mem.facts or {})
        today = _now().date().isoformat()
        checkins = [c for c in (f.get("checkins") or []) if c.get("date") != today]
        checkins.append({"date": today, "mood": mood, "energy": energy or mood})
        f["checkins"] = checkins[-_MAX_CHECKINS:]
        # S1 — today's energy reshapes the whole session (read by the prompt builder).
        f["energy_today"] = {"date": today, "value": energy or mood}
        mem.facts = f
        flag_modified(mem, "facts")
        await s.commit()
        return f


async def save_daily_context(user_id: str, ctx: dict) -> None:
    """Merge today's context into a 48h sliding window (today + yesterday only)."""
    async with _Session() as s:               # type: ignore[misc]
        mem = await _get_or_make_memory(s, user_id)
        f = dict(mem.facts or {})
        today = _now().date()
        keep = {today.isoformat(), (today - dt.timedelta(days=1)).isoformat()}
        dc = [e for e in (f.get("daily_context") or []) if e.get("date") in keep]
        cur = next((e for e in dc if e.get("date") == today.isoformat()), None)
        if cur is None:
            cur = {"date": today.isoformat(), "mood": "", "plans": "", "weather": "", "events": [], "notes": []}
            dc.append(cur)
        if ctx.get("mood"):    cur["mood"] = ctx["mood"]
        if ctx.get("plans"):   cur["plans"] = ctx["plans"]
        if ctx.get("weather"): cur["weather"] = ctx["weather"]
        if ctx.get("note"):    cur["notes"] = ((cur.get("notes") or []) + [ctx["note"]])[-8:]
        for e in (ctx.get("events") or []):
            if isinstance(e, dict) and e not in (cur.get("events") or []):
                cur.setdefault("events", []).append(e)
        f["daily_context"] = dc
        mem.facts = f
        flag_modified(mem, "facts")
        await s.commit()


async def record_practice(user_id: str, seconds: int = 0, sentences: int = 0, xp: int = 20) -> dict:
    """A Daily-Talk / conversation session counts as practice: XP + streak + daily stat."""
    async with _Session() as s:               # type: ignore[misc]
        prog = await s.get(Progress, user_id)
        if prog is None:
            prog = Progress(user_id=user_id, badges=[], journey={})
            s.add(prog)
        prog.xp = (prog.xp or 0) + xp
        today = dt.date.today()
        if prog.last_active != today:
            if prog.last_active == today - dt.timedelta(days=1):
                prog.streak_days = (prog.streak_days or 0) + 1
            else:
                prog.streak_days = 1
            prog.sessions_today = 0
            prog.last_active = today
        prog.sessions_today = (prog.sessions_today or 0) + 1
        await s.commit()
        # also fold into memory daily_stats + longest
        await bump_daily_stat(user_id, sentences=sentences, seconds=seconds)
        return {"xp": prog.xp, "streak_days": prog.streak_days, "sessions_today": prog.sessions_today}


async def bump_daily_stat(user_id: str, sentences: int = 0, seconds: int = 0) -> None:
    async with _Session() as s:               # type: ignore[misc]
        mem = await _get_or_make_memory(s, user_id)
        f = dict(mem.facts or {})
        today = _now().date().isoformat()
        stats = dict(f.get("daily_stats") or {})
        d = dict(stats.get(today) or {"sentences": 0, "seconds": 0, "sessions": 0})
        d["sentences"] += sentences
        d["seconds"] += seconds
        d["sessions"] += 1
        stats[today] = d
        # keep only the last ~14 days
        f["daily_stats"] = dict(sorted(stats.items())[-14:])
        if seconds > int(f.get("longest_convo_sec", 0)):
            f["longest_convo_sec"] = seconds
        # S6 — lifetime totals for Growth signals
        f["total_sentences"] = int(f.get("total_sentences", 0)) + sentences
        f["total_seconds"] = int(f.get("total_seconds", 0)) + seconds
        mem.facts = f
        flag_modified(mem, "facts")
        await s.commit()


async def add_vocab(user_id: str, words: list[str]) -> None:
    """S6 — grow the learner's spoken-vocabulary set; count new words per day."""
    clean = {w for w in ((x or "").lower().strip(".,!?;:\"'") for x in words)
             if w.isalpha() and len(w) >= 2}
    if not clean:
        return
    async with _Session() as s:               # type: ignore[misc]
        mem = await _get_or_make_memory(s, user_id)
        f = dict(mem.facts or {})
        have = set(f.get("vocab") or [])
        fresh = clean - have
        if fresh:
            merged = list(have | clean)[-_MAX_VOCAB:]
            f["vocab"] = merged
            f["vocab_total"] = int(f.get("vocab_total", 0)) + len(fresh)
            today = _now().date().isoformat()
            stats = dict(f.get("daily_stats") or {})
            d = dict(stats.get(today) or {})
            d["new_words"] = int(d.get("new_words", 0)) + len(fresh)
            stats[today] = d
            f["daily_stats"] = stats
            mem.facts = f
            flag_modified(mem, "facts")
            await s.commit()


async def save_letter(user_id: str, text: str) -> None:
    async with _Session() as s:               # type: ignore[misc]
        mem = await _get_or_make_memory(s, user_id)
        f = dict(mem.facts or {})
        f["last_letter"] = {"date": _now().date().isoformat(), "text": text}
        mem.facts = f
        flag_modified(mem, "facts")
        await s.commit()


async def award_badges(user_id: str, ids: list[str]) -> list[str]:
    """Add badge ids to progress if not already present. Returns newly-added ids."""
    if not ids:
        return []
    async with _Session() as s:               # type: ignore[misc]
        prog = await s.get(Progress, user_id)
        if prog is None:
            prog = Progress(user_id=user_id, badges=[], journey={})
            s.add(prog)
        badges = list(prog.badges or [])
        new = [b for b in ids if b not in badges]
        if new:
            prog.badges = badges + new
            flag_modified(prog, "badges")
            await s.commit()
        return new


async def save_future_me(user_id: str, text: str) -> dict:
    async with _Session() as s:               # type: ignore[misc]
        mem = await _get_or_make_memory(s, user_id)
        f = dict(mem.facts or {})
        fm = dict(f.get("future_me") or {})
        if not fm.get("day1_text"):
            fm["day1_text"] = text
        fm["latest_text"] = text
        fm["latest_date"] = _now().date().isoformat()
        f["future_me"] = fm
        mem.facts = f
        flag_modified(mem, "facts")
        await s.commit()
        return f


# ===================== ADMIN (owner dashboard) =====================
async def admin_list_users() -> list[dict]:
    """Full per-user info for the owner dashboard: identity, status/mode, level,
    xp/streak, today's + total activity, and recent per-day usage."""
    if not db_enabled:
        return []
    async with _Session() as s:               # type: ignore[misc]
        rows = (await s.execute(select(User).order_by(User.last_seen.desc()))).scalars().all()
        out = []
        for u in rows:
            prof = await s.get(Profile, u.id)
            prog = await s.get(Progress, u.id)
            mem = await s.get(Memory, u.id)
            f = (mem.facts if mem else {}) or {}
            convos = (await s.execute(
                select(func.count()).select_from(Conversation).where(Conversation.user_id == u.id))).scalar() or 0
            out.append({
                "id": u.id,
                "email": u.email or "",
                "name": u.name or f.get("nickname", "") or "",
                "picture": u.picture or "",
                "status": getattr(u, "status", "active") or "active",
                "mode": getattr(u, "mode", "personal") or "personal",
                "created_at": u.created_at.isoformat() if u.created_at else None,
                "last_seen": u.last_seen.isoformat() if u.last_seen else None,
                "onboarded": bool(prof.onboarded) if prof else False,
                "level": (prof.level if prof else "") or "",
                "goal": (prof.goal if prof else "") or "",
                "xp": (prog.xp if prog else 0) or 0,
                "streak_days": (prog.streak_days if prog else 0) or 0,
                "sessions_today": (prog.sessions_today if prog else 0) or 0,
                "daily_goal": (prog.daily_goal if prog else 0) or 0,
                "total_sessions": int(convos),
                "total_minutes": round(int(f.get("total_seconds", 0)) / 60),
                "words": int((f.get("vocabulary") or {}).get("total", f.get("vocab_total", 0)) or 0),
                "daily_stats": f.get("daily_stats") or {},   # {date: {sessions, seconds, sentences}}
            })
        return out


async def set_user_status(user_id: str, status: str) -> bool:
    if not db_enabled or status not in ("active", "pending", "blocked"):
        return False
    async with _Session() as s:               # type: ignore[misc]
        u = await s.get(User, user_id)
        if not u:
            return False
        u.status = status
        await s.commit()
        return True


async def set_user_mode(user_id: str, mode: str, status: str | None = None) -> bool:
    if not db_enabled or mode not in ("personal", "office"):
        return False
    async with _Session() as s:               # type: ignore[misc]
        u = await s.get(User, user_id)
        if not u:
            return False
        u.mode = mode
        if status:
            u.status = status
        await s.commit()
        return True


async def get_user_flags(user_id: str) -> dict:
    """Cheap status/mode lookup for the access gate."""
    if not db_enabled:
        return {"status": "active", "mode": "personal"}
    async with _Session() as s:               # type: ignore[misc]
        u = await s.get(User, user_id)
        if not u:
            return {"status": "active", "mode": "personal"}
        return {"status": getattr(u, "status", "active") or "active",
                "mode": getattr(u, "mode", "personal") or "personal"}
