from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"

    gaze_low_sec: float = 2.0
    gaze_medium_sec: float = 5.0
    face_not_detected_sec: float = 5.0
    connection_timeout_sec: float = 30.0

    risk_low_min_score: float = 0.75
    risk_medium_min_score: float = 0.50

    session_ttl_sec: int = 3600

    max_zip_files: int = 200
    max_zip_uncompressed_bytes: int = 52_428_800
    max_snippet_chars: int = 8000

    cors_origins: str = "*"

    host: str = "0.0.0.0"
    port: int = 8000

    @property
    def cors_origin_list(self) -> list[str]:
        if self.cors_origins.strip() == "*":
            return ["*"]
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
