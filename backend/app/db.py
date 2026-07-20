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

from .config import settings


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


async def save_assessment(user_id: str, data: dict) -> dict:
    """Persist assessment results → mark onboarded. `data` has goal, comfort,
    practice_time, level, scores{}, weak_areas[]."""
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
        await s.commit()
        prog = await s.get(Progress, user_id)
        user = await s.get(User, user_id)
        return _state(user, prof, prog)


async def get_state(user_id: str) -> dict | None:
    async with _Session() as s:               # type: ignore[misc]
        user = await s.get(User, user_id)
        if user is None:
            return None
        prof = await s.get(Profile, user_id) or Profile(user_id=user_id)
        prog = await s.get(Progress, user_id) or Progress(user_id=user_id)
        return _state(user, prof, prog)
