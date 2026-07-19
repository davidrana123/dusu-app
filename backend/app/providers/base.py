"""Provider interface.

The app depends only on this LLMProvider protocol, never on a concrete
vendor. Swapping models (or providers) is a change in providers/__init__.py,
not in callers. STT/TTS are not here — they run in the browser.
"""

from typing import Protocol


class LLMProvider(Protocol):
    async def next_question(self, system: str, transcript: list[dict]) -> str:
        """Persona (system) + conversation so far -> the AI interviewer's
        next spoken line."""
        ...

    async def score(self, system: str, transcript: list[dict]) -> dict:
        """Post-interview: full transcript -> JSON report."""
        ...
