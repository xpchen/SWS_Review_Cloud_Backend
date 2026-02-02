from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Database
    DATABASE_URL: str
    DB_SCHEMA: str = "sws"

    # API
    BASE_URL: str = "http://localhost:8000"

    # Redis & Celery
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"

    # Storage: local | minio
    STORAGE_TYPE: str = "local"
    # Local: directory for files (relative or absolute)
    LOCAL_STORAGE_DIR: str = "storage_data"
    # MinIO
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_BUCKET: str = "sws"
    MINIO_SECURE: bool = False

    # JWT
    JWT_SECRET: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_EXPIRE_MINUTES: int = 30
    JWT_REFRESH_EXPIRE_DAYS: int = 7

    # Qwen / DashScope (AI review)
    QWEN_API_KEY: str = ""
    QWEN_MODEL: str = "qwen-plus"
    
    # Review
    AUTO_TRIGGER_REVIEW: bool = True  # 版本处理完成后是否自动触发规则审查

settings = Settings()
