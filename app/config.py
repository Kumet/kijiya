from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    anthropic_api_key: str = ""
    model: str = "claude-sonnet-5"
    max_tokens: int = 8000
    fetch_timeout: float = 15.0
    max_download_bytes: int = 3_000_000
    max_source_chars: int = 24_000
    doc_ttl_seconds: int = 1800
    max_docs: int = 200
    allow_private_hosts: bool = False
    rate_limit_per_hour: int = 30


settings = Settings()
