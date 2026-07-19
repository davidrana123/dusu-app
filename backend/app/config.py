from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Loaded once from .env.

    Multiple free LLM providers can be configured. They're tried in order (the
    chain): when one runs out of free quota (429/402/etc.), the next takes over.
    To add a provider: add its `*_api_key` field here, put the key in .env, and
    add an entry to `providers()`.
    """

    # --- LLM provider keys (any/all; empty ones are skipped) ---
    gemini_api_key: str = ""
    groq_api_key: str = ""
    openrouter_api_key: str = ""
    github_token: str = ""

    # --- Google Sign-In ---
    google_client_id: str = ""
    session_secret: str = "dev-change-me"

    # --- Usage limits (protect the shared free quota) ---
    max_sessions_per_day: int = 20      # per user; resets daily
    conversation_max_turns: int = 40    # free chat gently wraps up
    interview_max_turns: int = 15       # hard cap (interview self-ends ~8)

    host: str = "0.0.0.0"
    port: int = 8000

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    def providers(self) -> list[dict]:
        """Active providers in fallback order. Each: name, base_url, key,
        models (tried in order), headers, extra (per-provider request body)."""
        chain: list[dict] = []
        if self.gemini_api_key:
            chain.append({
                "name": "gemini",
                "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
                "key": self.gemini_api_key,
                "models": ["gemini-flash-latest", "gemini-flash-lite-latest"],
                "headers": {},
                "extra": {"reasoning_effort": "none"},  # no thinking → no truncation
            })
        if self.groq_api_key:
            chain.append({
                "name": "groq",
                "base_url": "https://api.groq.com/openai/v1",
                "key": self.groq_api_key,
                "models": ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"],
                "headers": {},
                "extra": {},
            })
        if self.openrouter_api_key:
            chain.append({
                "name": "openrouter",
                "base_url": "https://openrouter.ai/api/v1",
                "key": self.openrouter_api_key,
                "models": [
                    "openai/gpt-oss-20b:free",
                    "meta-llama/llama-3.3-70b-instruct:free",
                    "nvidia/nemotron-3-super-120b-a12b:free",
                ],
                "headers": {"HTTP-Referer": "https://dusu-app-1.onrender.com", "X-Title": "DuSu"},
                "extra": {"reasoning": {"exclude": True, "effort": "low"}},
            })
        if self.github_token:
            chain.append({
                "name": "github",
                "base_url": "https://models.github.ai/inference",
                "key": self.github_token,
                "models": ["openai/gpt-4o-mini", "meta/Llama-3.3-70B-Instruct"],
                "headers": {},
                "extra": {},
            })
        return chain


settings = Settings()
