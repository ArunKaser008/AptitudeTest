from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "MentorMuni Aptitude API"
    api_prefix: str = "/api/v1"
    database_url: str = "postgresql+psycopg://aptitude:aptitude@localhost:5432/aptitude"
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    environment: str = "development"
    candidate_session_ttl_hours: int = 24
    llm_api_key: str | None = None
    llm_base_url: str = "https://api.openai.com/v1/chat/completions"
    llm_model: str = "gpt-4o-mini"
    llm_timeout_seconds: int = 30
    ai_generation_max_retries: int = 3
    seed_default_assessments: bool = False

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @model_validator(mode="after")
    def validate_runtime_settings(self) -> "Settings":
        if not 1 <= self.candidate_session_ttl_hours <= 168:
            raise ValueError("CANDIDATE_SESSION_TTL_HOURS must be between 1 and 168.")
        if not 1 <= self.llm_timeout_seconds <= 120:
            raise ValueError("LLM_TIMEOUT_SECONDS must be between 1 and 120.")
        if not 1 <= self.ai_generation_max_retries <= 5:
            raise ValueError("AI_GENERATION_MAX_RETRIES must be between 1 and 5.")
        if self.environment.lower() in {"production", "prod"}:
            if "localhost" in self.database_url or "127.0.0.1" in self.database_url:
                raise ValueError("Production DATABASE_URL must not point to localhost.")
            if not self.cors_origins or "*" in self.cors_origins:
                raise ValueError("Production CORS_ORIGINS must contain explicit trusted origins.")
            if "aptitude:aptitude@" in self.database_url:
                raise ValueError("The development database credentials are not allowed in production.")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
