"""Per-session state + turn logic, shared by both modes.

Modes:
  - "interview"     : DuSu plays HR interviewer; self-ends and produces a report.
  - "conversation"  : DuSu is a friendly partner; never ends, no report.

v0 keeps the full transcript in memory (one session per WebSocket). Plan
section P calls for summarizing context once conversations get long — do that
here later; the interface stays the same.
"""

from ..providers import llm
from .prompts import interviewer_system, conversation_system, SCORER_SYSTEM

END_MARKER = "INTERVIEW_COMPLETE:"
MODES = ("interview", "conversation")


class Session:
    def __init__(self, mode: str, name: str, role: str):
        self.mode = mode if mode in MODES else "interview"
        self.name = name or "there"
        self.role = role or "general"
        if self.mode == "interview":
            self.system = interviewer_system(self.name, self.role)
        else:
            self.system = conversation_system(self.name)
        self.transcript: list[dict] = []  # {role: "user"|"assistant", content}
        self.done = False

    def add_user(self, text: str) -> None:
        self.transcript.append({"role": "user", "content": text})

    async def next_ai_turn(self) -> str:
        """Return DuSu's next spoken line. In interview mode, detects the
        self-end marker and strips it; conversation mode never ends."""
        raw = await llm.next_question(self.system, self.transcript)
        spoken = raw
        if self.mode == "interview" and END_MARKER in raw:
            self.done = True
            spoken = raw.split(END_MARKER, 1)[1].strip() or "Thanks, that's the end of our interview."
        self.transcript.append({"role": "assistant", "content": spoken})
        return spoken

    async def build_report(self) -> dict:
        """Only interview mode is scored. Conversation returns nothing."""
        if self.mode != "interview":
            return {}
        return await llm.score(SCORER_SYSTEM, self.transcript)
