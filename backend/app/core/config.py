from __future__ import annotations
from pydantic import BaseModel
from dotenv import load_dotenv
from functools import lru_cache
from pathlib import Path
import os

load_dotenv()

class Settings(BaseModel):
    app_env: str = os.getenv("APP_ENV", "dev")
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    openai_api_key: str | None = os.getenv("OPENAI_API_KEY")

    # Resolve VECTOR_DB_DIR relative to the package root (backend/app/)
    _pkg_root = Path(__file__).resolve().parents[1]  # .../backend/app
    _default_vec = (_pkg_root / "kb" / "index").as_posix()
    _env_vec = os.getenv("VECTOR_DB_DIR", "").strip()

    if _env_vec:
        vector_db_dir: str = (_env_vec if os.path.isabs(_env_vec)
                              else (_pkg_root / _env_vec).as_posix())
    else:
        vector_db_dir: str = _default_vec

    # Optional adapters
    prometheus_url: str | None = os.getenv("PROMETHEUS_URL")
    git_token: str | None = os.getenv("GIT_TOKEN")
    k8s_context: str | None = os.getenv("K8S_CONTEXT")

    # KB sanity minimum
    kb_min_docs: int = int(os.getenv("KB_MIN_DOCS", "5"))

@lru_cache
def get_settings() -> Settings:
    return Settings()
