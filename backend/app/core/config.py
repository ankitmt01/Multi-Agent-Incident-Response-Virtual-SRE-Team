# app/core/config.py
from __future__ import annotations
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # ---- app meta ----
    app_env: str = "dev"       # dev|staging|prod
    log_level: str = "INFO"

    # ---- API & RAG knobs ----
    openai_api_key: Optional[str] = None
    vector_db_dir: str = "./kb/index"
    chroma_collection: str = "kb_docs"
    prometheus_url: str = "http://localhost:9090"
    vite_api_url: str = "/api"

    # ---- Knowledge base / RAG (NEW defaults so pipeline never crashes) ----
    kb_min_docs: int = 1                  # pipeline checks this at startup
    kb_watch_dir: str = "./kb/dropbox"    # optional; only used if you implement watch
    rag_top_k: int = 8
    rag_fetch_k: int = 24
    rag_min_score: float = 0.0            # set higher if you want a threshold later

    # ---- policy / approvals ----
    high_risk_actions_csv: str = ""                    # e.g. "delete_db,drop_table"
    needs_approval_actions_csv: str = ""               # e.g. "restart_service"
    nonprod_envs_csv: str = "dev,staging"
    allow_manual_approval: bool = True

    # ---- database (async for app; sync for Alembic) ----
    database_url: str = "sqlite+aiosqlite:///./data/app.db"
    alembic_database_url: Optional[str] = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",        # ignore unknown keys in .env
        case_sensitive=False,  # DATABASE_URL or database_url both fine
    )

    @property
    def alembic_url(self) -> str:
        if self.alembic_database_url:
            return self.alembic_database_url
        return (
            self.database_url
            .replace("postgresql+asyncpg", "postgresql+psycopg")
            .replace("sqlite+aiosqlite", "sqlite")
        )

# Singleton accessor
_settings: Optional[Settings] = None
def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
