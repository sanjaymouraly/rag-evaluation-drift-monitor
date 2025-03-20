"""Application settings.

All settings can be overridden with ``RQM_``-prefixed environment variables or
a local ``.env`` file. Secrets are never echoed by the API (see ``security.py``).
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="RQM_", env_file=".env", extra="ignore")

    # --- core ---
    app_name: str = "RAG Quality Monitor"
    environment: str = "development"
    database_url: str = "sqlite:///./rag_monitor.db"

    # --- http security ---
    # When set, every request except /health, /ready and / requires X-API-Key.
    api_key: str = ""
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    max_upload_bytes: int = 10 * 1024 * 1024
    rate_limit_per_minute: int = 600
    trusted_hosts: str = ""

    # --- execution ---
    max_workers: int = 4
    job_retries: int = 2
    run_timeout_s: float = 3600.0
    scheduler_enabled: bool = False
    scheduler_tick_s: int = 60

    # --- cost control ---
    default_budget_usd: float = 1.0
    hard_cost_limit_usd: float = 25.0
    # Guard rail for a single evaluation run; 0 disables the per-run cap.
    max_run_cost_usd: float = 5.0

    # --- alerting ---
    alert_webhook_url: str = ""
    alert_webhook_timeout_s: float = 5.0

    # --- observability ---
    log_level: str = "INFO"
    log_json: bool = False

    # --- demo ---
    demo_mode: bool = False

    @field_validator("cors_origins", "trusted_hosts", mode="before")
    @classmethod
    def _blank_to_empty(cls, v: object) -> object:
        return "" if v is None else v

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def trusted_host_list(self) -> list[str]:
        return [h.strip() for h in self.trusted_hosts.split(",") if h.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
