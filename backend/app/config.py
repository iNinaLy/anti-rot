from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    secret_key: str = Field(min_length=32)
    database_url: str = "sqlite:///./data/app.db"
    media_dir: Path = Path("media")
    static_dir: Path = Path("../frontend/dist")
    access_token_minutes: int = Field(default=15, ge=1)
    refresh_token_days: int = Field(default=180, ge=1)
    max_image_bytes: int = Field(default=5 * 1024 * 1024, ge=1)
    max_images_per_card: int = Field(default=10, ge=1)
    max_image_dimension: int = Field(default=1600, ge=1)
    max_csv_bytes: int = Field(default=5 * 1024 * 1024, ge=1)
    login_attempts: int = Field(default=10, ge=1)
    login_window_seconds: int = Field(default=300, ge=1)
    cookie_secure: bool = True
    fsrs_desired_retention: float = Field(default=0.9, ge=0.7, le=0.99)
    push_keys_file: Path = Path("data/push-keys.json")
    push_contact: str = "mailto:admin@example.com"
    reminders_enabled: bool = True
    news_fetch_enabled: bool = True
    ollama_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "qwen3:0.6b"
    backups_enabled: bool = True
    backup_dir: Path = Path("backups")
    backup_time: str = Field(default="03:00", pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")
    backup_keep: int = Field(default=7, ge=1, le=90)


@lru_cache
def get_settings() -> Settings:
    return Settings()
