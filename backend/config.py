"""Environment configuration shared by the API and workflow."""
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


@dataclass
class Settings:
    database_url: str = "sqlite:///./data/support.db"
    checkpoint_url: str = ""
    checkpoint_file: str = "./data/checkpoints.sqlite"
    api_key: str = "local-demo-key-change-before-hosting"
    environment: str = "development"
    ai_mode: str = "rules"
    gemini_key: str = ""
    gemini_model: str = ""
    seed_demo: bool = True

    @classmethod
    def from_env(cls):
        return cls(
            database_url=os.getenv("DATABASE_URL", cls.database_url),
            checkpoint_url=os.getenv("CHECKPOINT_DATABASE_URL", ""),
            checkpoint_file=os.getenv("CHECKPOINT_FILE", cls.checkpoint_file),
            api_key=os.getenv("BACKEND_API_KEY", cls.api_key),
            environment=os.getenv("APP_ENV", "development"),
            ai_mode=os.getenv("AI_MODE", "rules"),
            gemini_key=os.getenv("GEMINI_API_KEY", ""),
            gemini_model=os.getenv("GEMINI_MODEL", ""),
            seed_demo=os.getenv("SEED_DEMO", "true").lower() == "true",
        )

    def validate(self):
        if self.ai_mode not in {"rules", "gemini"}:
            raise ValueError("AI_MODE must be rules or gemini")
        if self.ai_mode == "gemini" and not (self.gemini_key and self.gemini_model):
            raise ValueError("Gemini mode requires GEMINI_API_KEY and GEMINI_MODEL")
        if self.environment == "production":
            if len(self.api_key) < 32 or self.api_key == Settings.api_key:
                raise ValueError("Set a unique BACKEND_API_KEY of at least 32 characters")
            if not self.database_url.startswith(("postgres://", "postgresql://", "postgresql+psycopg://")):
                raise ValueError("Production requires persistent PostgreSQL DATABASE_URL")
            if self.checkpoint_url and not self.checkpoint_url.startswith(("postgres://", "postgresql://", "postgresql+psycopg://")):
                raise ValueError("Production checkpoints must use PostgreSQL")
        Path(self.checkpoint_file).parent.mkdir(parents=True, exist_ok=True)
        if self.database_url.startswith("sqlite:///./"):
            Path(self.database_url.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)


def sqlalchemy_url(url: str) -> str:
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg://", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


def psycopg_url(url: str) -> str:
    return url.replace("postgresql+psycopg://", "postgresql://", 1).replace("postgres://", "postgresql://", 1)
