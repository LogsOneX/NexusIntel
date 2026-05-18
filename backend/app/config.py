from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "NexusIntel"
    database_url: str = "postgresql+psycopg2://nexus:nexus@postgres:5432/nexusintel"
    redis_url: str = "redis://redis:6379/0"
    cors_origins: str = "*"
    request_timeout: float = 12.0
    standard_concurrency: int = 12
    aggressive_concurrency: int = 32

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def cors_origin_list(self) -> list[str]:
        if self.cors_origins.strip() == "*":
            return ["*"]
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
