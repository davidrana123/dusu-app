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
    xp: Mapped[int] = mapped_column(Integer, default=0)
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
    async with _engine.begin() as conn:      # type: ignore[union-attr]
        await conn.run_sync(Base.metadata.create_all)


def _state(user: User, prof: Profile, prog: Progress, mem: "Memory | None" = None) -> dict:
    """Everything the client needs about a returning user (incl. emotional memory)."""
    return {
        "user": {"id": user.id, "email": user.email, "name": user.name, "picture": user.picture,
                 "created_at": user.created_at.isoformat() if user.created_at else None},
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


async def _get_or_make_memory(s, user_id: str) -> "Memory":
    mem = await s.get(Memory, user_id)
    if mem is None:
        mem = Memory(user_id=user_id, facts={})
        s.add(mem)
    return mem


async def get_memory(user_id: str) -> dict:
    async with _Session() as s:               # type: ignore[misc]
        mem = await s.get(Memory, user_id)
        return dict(mem.facts) if mem and mem.facts else {}


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


async def add_conversation(user_id: str, mode: str, summary: str) -> None:
    if not (summary or "").strip():
        return
    async with _Session() as s:               # type: ignore[misc]
        s.add(Conversation(user_id=user_id, mode=mode, summary=summary.strip()))
        await s.commit()


async def save_checkin(user_id: str, mood: str) -> dict:
    async with _Session() as s:               # type: ignore[misc]
        mem = await _get_or_make_memory(s, user_id)
        f = dict(mem.facts or {})
        today = _now().date().isoformat()
        checkins = [c for c in (f.get("checkins") or []) if c.get("date") != today]
        checkins.append({"date": today, "mood": mood})
        f["checkins"] = checkins[-_MAX_CHECKINS:]
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
