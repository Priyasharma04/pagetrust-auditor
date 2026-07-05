from __future__ import annotations

from functools import lru_cache
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')

    app_env: str = Field(default='development', alias='APP_ENV')
    backend_cors_origins: str = Field(default='http://localhost:3000', alias='BACKEND_CORS_ORIGINS')
    use_playwright: bool = Field(default=True, alias='USE_PLAYWRIGHT')
    link_check_concurrency: int = Field(default=12, alias='LINK_CHECK_CONCURRENCY')
    link_check_timeout_seconds: float = Field(default=8.0, alias='LINK_CHECK_TIMEOUT_SECONDS')

    storage_backend: str = Field(default='local', alias='STORAGE_BACKEND')
    local_report_dir: str = Field(default='app/storage/local_reports', alias='LOCAL_REPORT_DIR')

    openai_api_key: str | None = Field(default=None, alias='OPENAI_API_KEY')
    openai_model: str = Field(default='gpt-4o-mini', alias='OPENAI_MODEL')

    supabase_url: str | None = Field(default=None, alias='SUPABASE_URL')
    supabase_service_role_key: str | None = Field(default=None, alias='SUPABASE_SERVICE_ROLE_KEY')
    supabase_audit_table: str = Field(default='audits', alias='SUPABASE_AUDIT_TABLE')

    @property
    def cors_origins(self) -> List[str]:
        return [origin.strip() for origin in self.backend_cors_origins.split(',') if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
