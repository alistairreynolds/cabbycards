from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration, sourced from environment / .env (see .env.example).

    Only secrets and per-environment connection values are required (no default).
    Everything else has a safe operational default that can be overridden via env.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- Required: must be set per environment (no safe default) ---
    database_url: str
    jwt_secret: str
    turnstile_secret_key: str

    # --- Safe defaults (override via env as needed) ---
    scryfall_base_url: str = "https://api.scryfall.com"
    scryfall_user_agent: str = "CabbyCards/0.1 (+https://github.com/alistairreynolds/cabbycards)"
    card_cache_ttl_days: int = 14

    turnstile_verify_url: str = "https://challenges.cloudflare.com/turnstile/v0/siteverify"

    email_backend: str = "console"
    email_from: str = "CabbyCards <no-reply@cabbycards.local>"
    frontend_base_url: str = "http://localhost:5173"

    jwt_algorithm: str = "HS256"
    jwt_expiry_minutes: int = 43200


@lru_cache
def get_settings() -> Settings:
    """Cached so the .env file and environment are read once per process.

    See: tests/test_config.py
    """
    return Settings()  # type: ignore[call-arg]
