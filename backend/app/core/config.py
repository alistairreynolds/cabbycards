from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str

    scryfall_base_url: str = "https://api.scryfall.com"
    scryfall_user_agent: str = "CabbyCards/0.1"
    card_cache_ttl_days: int = 14

    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expiry_minutes: int = 43200


@lru_cache
def get_settings() -> Settings:
    """Cached so the .env file and environment are read once per process.

    See: tests/test_config.py
    """
    return Settings()  # type: ignore[call-arg]
