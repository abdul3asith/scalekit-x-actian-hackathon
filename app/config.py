"""Typed application settings, loaded from environment / .env."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Backend
    public_base_url: str = "http://localhost:8000"
    backend_api_key: str = "dev-change-me"
    session_secret: str = "dev-session-secret-change-me"

    # PostgreSQL
    database_url: str = "postgresql://postgres:postgres@localhost:5432/scheduler"

    # Nebius (OpenAI-compatible)
    nebius_api_key: str = ""
    nebius_base_url: str = "https://api.studio.nebius.com/v1/"
    nebius_chat_model: str = "Qwen/Qwen3-235B-A22B-Instruct-2507"
    nebius_embed_model: str = "Qwen/Qwen3-Embedding-8B"
    embed_dim: int = 4096

    # Scalekit
    scalekit_environment_url: str = ""
    scalekit_client_id: str = ""
    scalekit_client_secret: str = ""
    scalekit_redirect_uri: str = "http://localhost:8000/auth/callback"

    # Actian VectorAI
    actian_enabled: bool = False
    actian_host: str = "localhost"
    actian_port: int = 6574

    # VAPI
    vapi_api_key: str = ""
    vapi_base_url: str = "https://api.vapi.ai"
    vapi_phone_number_id: str = ""
    vapi_inbound_assistant_id: str = ""
    vapi_outbound_assistant_id: str = ""

    @property
    def outbound_calling_ready(self) -> bool:
        return bool(
            self.vapi_api_key
            and self.vapi_phone_number_id
            and self.vapi_outbound_assistant_id
        )

    @property
    def scalekit_configured(self) -> bool:
        return bool(
            self.scalekit_environment_url
            and self.scalekit_client_id
            and self.scalekit_client_secret
        )

    @property
    def nebius_configured(self) -> bool:
        return bool(self.nebius_api_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
