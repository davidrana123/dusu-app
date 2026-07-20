"""LLM provider chain (all OpenAI-compatible: Gemini, OpenRouter, Groq, …).

Every provider exposes the OpenAI Chat Completions shape, so one OpenAI client
per provider (different base_url + key) drives them all. On any failure — quota
(429/402), model gone (404), bad request — we fall through to the next model,
then the next provider. Configure the chain in config.Settings.providers().

Speech is browser-side; the model only ever sees and emits text.
"""

import json
import re
import time

from openai import AsyncOpenAI

from ..config import settings

_clients: dict[str, AsyncOpenAI] = {}
_cooldown: dict[str, float] = {}   # provider name -> skip-until timestamp


def _client(p: dict) -> AsyncOpenAI:
    if p["name"] not in _clients:
        _clients[p["name"]] = AsyncOpenAI(
            api_key=p["key"],
            base_url=p["base_url"],
            default_headers=p.get("headers") or {},
        )
    return _clients[p["name"]]


def _mark_cooldown(name: str, err: str) -> None:
    """A rate-limited/exhausted provider is skipped for a while so we don't
    waste a failing round-trip on it every single turn."""
    low = err.lower()
    daily = any(k in low for k in ("day", "quota", "free_tier", "free-models"))
    _cooldown[name] = time.time() + (1800 if daily else 90)


async def _complete(messages: list[dict], max_tokens: int) -> str:
    """Walk the provider chain → each provider's models → until one answers.
    Skips providers on cooldown; if every provider is cooling down, tries them
    anyway rather than failing."""
    last_err = None
    for ignore_cd in (False, True):
        now = time.time()
        attempted = False
        for p in settings.providers():
            if not ignore_cd and _cooldown.get(p["name"], 0) > now:
                continue
            attempted = True
            client = _client(p)
            for model in p["models"]:
                try:
                    resp = await client.chat.completions.create(
                        model=model,
                        messages=messages,
                        max_tokens=max_tokens,
                        temperature=0.7,
                        extra_body=p.get("extra") or {},
                    )
                    text = (resp.choices[0].message.content or "").strip()
                    if text:
                        return text
                except Exception as e:
                    last_err = e
                    s = str(e)
                    if any(k in s.lower() for k in ("429", "rate", "quota", "exceed", "exhaust")):
                        _mark_cooldown(p["name"], s)  # whole provider limited
                        break                          # skip its other models
                    continue                           # other error → next model
        if attempted:
            break   # we tried the available providers; don't loop into ignore-pass
    raise RuntimeError(f"all providers/models unavailable: {last_err}")


def _extract_json(text: str) -> dict:
    """Models don't always return clean JSON — pull the first {...} block."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                pass
    return {"error": "scoring_parse_failed", "raw": text[:500]}


class OpenRouterLLM:
    async def next_question(self, system: str, transcript: list[dict]) -> str:
        messages = [{"role": "system", "content": system}, *transcript]
        # Some providers (Gemini) reject a system-only request — DuSu speaks first
        # with an empty transcript, so seed a user turn to kick it off.
        if not any(m["role"] == "user" for m in transcript):
            messages.append({"role": "user",
                             "content": "Let's begin. Greet me and ask your first question."})
        return await _complete(messages, max_tokens=250)

    async def translate(self, system: str, text: str) -> str:
        messages = [{"role": "system", "content": system},
                    {"role": "user", "content": text}]
        return await _complete(messages, max_tokens=120)

    async def generate(self, system: str, prompt: str, max_tokens: int = 500) -> str:
        """Free-form prose (weekly letters, session summaries). Returns raw text."""
        messages = [{"role": "system", "content": system},
                    {"role": "user", "content": prompt}]
        return await _complete(messages, max_tokens=max_tokens)

    async def assess(self, system: str, payload: str) -> dict:
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": payload + "\n\nReturn ONLY the JSON object."},
        ]
        return _extract_json(await _complete(messages, max_tokens=700))

    async def score(self, system: str, transcript: list[dict]) -> dict:
        convo = "\n".join(f"{m['role']}: {m['content']}" for m in transcript)
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": convo + "\n\nReturn ONLY the JSON object."},
        ]
        return _extract_json(await _complete(messages, max_tokens=1200))
