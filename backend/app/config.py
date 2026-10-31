import os
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Environment
    FASTAPI_ENV: str = "development"
    SECRET_KEY: str = "compliance-sentinel-dev-secret-key-change-in-production-32chars"
    DEBUG: bool = True

    # Database (YugabyteDB YSQL)
    YUGABYTEDB_HOST: str = "localhost"
    YUGABYTEDB_PORT: int = 5433
    DATABASE_NAME: str = "compliance_sentinel"
    DATABASE_USER: str = "yugabyte"
    DATABASE_PASSWORD: str = ""
    DATABASE_URL: Optional[str] = None

    # Connection Pool Settings
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_TIMEOUT: int = 30
    DB_POOL_RECYCLE: int = 1800

    # Authentication & JWT
    JWT_SECRET_KEY: str = "compliance-sentinel-jwt-secret-key-32-characters-minimum-for-security-entropy-token"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    COOKIE_SECURE: bool = False
    COOKIE_SAMESITE: str = "lax"
    COOKIE_NAME: str = "compliance_sentinel_refresh"

    # LLM & Workflow Services
    GEMINI_API_KEY: Optional[str] = None
    GEMINI_MODEL: str = "gemini-2.5-flash"
    GEMINI_TEMPERATURE: float = 0.1
    GEMINI_MAX_OUTPUT_TOKENS: int = 4096
    GEMINI_TIMEOUT_SECONDS: int = 60
    N8N_WEBHOOK_URL: Optional[str] = None
    N8N_ENCRYPTION_KEY: Optional[str] = None

    # Storage & Uploads
    STORAGE_TYPE: str = "local"
    STORAGE_LOCAL_PATH: str = "/data/storage" if os.path.exists("/data/storage") else "/tmp/compliance_sentinel/storage"
    MAX_UPLOAD_SIZE_BYTES: int = 26214400  # 25 MB

    # Frontend CORS
    FRONTEND_URL: str = "http://localhost:3000"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    def get_database_url(self) -> str:
        if self.DATABASE_URL:
            # Normalize to psycopg 3 driver if standard postgresql:// is provided
            if self.DATABASE_URL.startswith("postgresql://") and not self.DATABASE_URL.startswith("postgresql+psycopg://"):
                return self.DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)
            return self.DATABASE_URL

        auth = f"{self.DATABASE_USER}"
        if self.DATABASE_PASSWORD:
            auth += f":{self.DATABASE_PASSWORD}"

        return f"postgresql+psycopg://{auth}@{self.YUGABYTEDB_HOST}:{self.YUGABYTEDB_PORT}/{self.DATABASE_NAME}"


settings = Settings()
