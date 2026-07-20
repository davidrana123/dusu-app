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

from sqlalchemy import String, Integer, Boolean, DateTime, Date, ForeignKey, select
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
# Levels that gate level-up behind a passing Level Test (see submit_level_test).
# Levels not listed here still auto-advance on lesson completion, as before.
LEVELS_WITH_TEST = {1, 2}


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


async def init_db() -> None:
    if not db_enabled:
        return
    async with _engine.begin() as conn:      # type: ignore[union-attr]
        await conn.run_sync(Base.metadata.create_all)


def _state(user: User, prof: Profile, prog: Progress) -> dict:
    """Everything the client needs about a returning user."""
    return {
        "user": {"id": user.id, "email": user.email, "name": user.name, "picture": user.picture},
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

        await s.commit()
        return _state(user, prof, prog)


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
        if leveled_up and "level_up" not in badges:
            badges.append("level_up"); new_badges.append("level_up")

        prog.journey = j
        prog.badges = badges
        flag_modified(prog, "journey")
        flag_modified(prog, "badges")
        await s.commit()

        user = await s.get(User, user_id)
        prof = await s.get(Profile, user_id) or Profile(user_id=user_id)
        return {"progress": _state(user, prof, prog)["progress"],
                "leveled_up": leveled_up, "new_badges": new_badges, "passed": passed}


async def get_state(user_id: str) -> dict | None:
    async with _Session() as s:               # type: ignore[misc]
        user = await s.get(User, user_id)
        if user is None:
            return None
        prof = await s.get(Profile, user_id) or Profile(user_id=user_id)
        prog = await s.get(Progress, user_id) or Progress(user_id=user_id)
        return _state(user, prof, prog)
