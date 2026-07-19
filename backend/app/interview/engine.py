"""Per-session state + turn logic, shared by both modes.

Modes:
  - "interview"     : DuSu plays HR interviewer; self-ends and produces a report.
  - "conversation"  : DuSu is a friendly partner; never ends, no report.

v0 keeps the full transcript in memory (one session per WebSocket). Plan
section P calls for summarizing context once conversations get long — do that
here later; the interface stays the same.
"""

from ..providers import llm
from ..config import settings
from .prompts import interviewer_system, conversation_system, SCORER_SYSTEM, TRANSLATE_SYSTEM

END_MARKER = "INTERVIEW_COMPLETE:"
MODES = ("interview", "conversation", "learning")


class Session:
    def __init__(self, mode: str, name: str, role: str):
        self.mode = mode if mode in MODES else "interview"
        self.name = name or "there"
        self.role = role or "general"
        if self.mode == "interview":
            self.system = interviewer_system(self.name, self.role)
        elif self.mode == "conversation":
            self.system = conversation_system(self.name)
        else:  # learning: server only translates, no chat persona
            self.system = ""
        self.transcript: list[dict] = []  # {role: "user"|"assistant", content}
        self.done = False
        self.capped = False   # conversation hit its turn cap
        self.turns = 0        # user turns so far

    def add_user(self, text: str) -> None:
        self.transcript.append({"role": "user", "content": text})
        self.turns += 1

    async def next_ai_turn(self) -> str:
        """Return DuSu's next spoken line. Enforces turn caps per mode."""
        raw = await llm.next_question(self.system, self.transcript)
        spoken = raw
        if self.mode == "interview":
            if END_MARKER in raw:
                self.done = True
                spoken = raw.split(END_MARKER, 1)[1].strip() or "Thanks, that's the end of our interview."
            elif self.turns >= settings.interview_max_turns:
                self.done = True
                spoken = f"Thanks {self.name} — that's all the questions I have for now. Let me put together your report."
        elif self.mode == "conversation" and self.turns >= settings.conversation_max_turns:
            self.capped = True
            spoken = "This has been such a great long chat — let's pause here for now. Start a fresh conversation whenever you'd like!"
        self.transcript.append({"role": "assistant", "content": spoken})
        return spoken

    async def translate(self, text: str) -> str:
        """Learning mode: Hindi/Hinglish -> natural spoken English."""
        return await llm.translate(TRANSLATE_SYSTEM, text)

    async def build_report(self) -> dict:
        """Only interview mode is scored. Conversation returns nothing."""
        if self.mode != "interview":
            return {}
        return await llm.score(SCORER_SYSTEM, self.transcript)
