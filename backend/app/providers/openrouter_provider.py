"""OpenRouter implementation of the LLM provider.

OpenRouter is OpenAI-compatible, so we drive it with the OpenAI SDK pointed at
OpenRouter's base URL. Free models are shared and frequently rate-limited
(HTTP 429), so every call walks the configured model list until one answers.

Speech-to-text and text-to-speech are NOT here — the browser handles them via
the Web Speech API, so the model only ever sees and emits text.
"""

import json
import re

from openai import AsyncOpenAI, APIStatusError

from ..config import settings

_client = AsyncOpenAI(
    api_key=settings.openrouter_api_key,
    base_url=settings.openrouter_base_url,
    # Optional OpenRouter attribution headers.
    default_headers={
        "HTTP-Referer": "http://localhost:8000",
        "X-Title": "AI Interview Coach",
    },
)


async def _complete(messages: list[dict], max_tokens: int) -> str:
    """Try each free model in turn; skip past rate-limited / unavailable ones."""
    last_err = None
    for model in settings.model_list:
        try:
            resp = await _client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=0.7,
                # Free tier is mostly reasoning models; suppress their
                # chain-of-thought so it doesn't leak into the spoken answer.
                extra_body={"reasoning": {"exclude": True, "effort": "low"}},
            )
            text = (resp.choices[0].message.content or "").strip()
            if text:
                return text
        except APIStatusError as e:
            # 429 (rate limit) / 404 (model gone) -> fall through to next model.
            last_err = e
            continue
    raise RuntimeError(f"all models unavailable: {last_err}")


def _extract_json(text: str) -> dict:
    """Free models don't reliably honor JSON mode — pull the first {...} block."""
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
        return await _complete(messages, max_tokens=180)

    async def score(self, system: str, transcript: list[dict]) -> dict:
        convo = "\n".join(f"{m['role']}: {m['content']}" for m in transcript)
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": convo + "\n\nReturn ONLY the JSON object."},
        ]
        text = await _complete(messages, max_tokens=1200)
        return _extract_json(text)
