from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Loaded once from .env. OpenRouter (OpenAI-compatible) is the only
    provider; speech I/O is handled in the browser, so there are no STT/TTS
    keys here."""

    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"

    # Comma-separated free models, tried in order (free tiers get rate-limited).
    llm_models: str = (
        "openai/gpt-oss-20b:free,"
        "nvidia/nemotron-3-super-120b-a12b:free,"
        "meta-llama/llama-3.3-70b-instruct:free"
    )

    # --- Google Sign-In ---
    # OAuth 2.0 Web client ID from console.cloud.google.com. When set, login is
    # required; when empty, auth is skipped (dev fallback) so the app still runs.
    google_client_id: str = ""
    # Secret used to sign our own session tokens. Change in production.
    session_secret: str = "dev-change-me"

    host: str = "0.0.0.0"
    port: int = 8000

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def model_list(self) -> list[str]:
        return [m.strip() for m in self.llm_models.split(",") if m.strip()]


settings = Settings()
