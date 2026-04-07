import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseSettings):
    PROJECT_NAME: str = "Photogrammetry Pipeline"
    API_V1_STR: str = "/api/v1"
    
    # Base URL for static file serving
    BASE_URL: str = os.getenv("BASE_URL", "http://localhost:8000")
    
    # Persistence & Orchestration
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./photogrammetry.db")
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    CELERY_BROKER_URL: str = os.getenv("CELERY_BROKER_URL", REDIS_URL)
    
    @property
    def CELERY_RESULT_BACKEND(self) -> str:
        # v4.0.0: Robust Result Backend resolution for SQL providers
        url = os.getenv("CELERY_RESULT_BACKEND")
        if url:
            return url
            
        db_url = os.getenv("DATABASE_URL", "sqlite:///./photogrammetry.db")
        if "sqlite" in db_url and not db_url.startswith("db+"):
            return db_url.replace("sqlite://", "db+sqlite://")
        if ("postgresql" in db_url or "postgres" in db_url) and not db_url.startswith("db+"):
            return "db+" + db_url
        return db_url
    
    # Storage (🏁 v5.1.4: Keeping STORAGE_BASE_DIR as str for Modal Volume compatibility)
    STORAGE_TYPE: str = os.getenv("STORAGE_TYPE", "local")
    STORAGE_BASE_DIR: str = os.getenv("STORAGE_BASE_DIR", "storage")
    
    # Derived paths as Path objects (Only used for LocalStorage)
    @property
    def UPLOAD_DIR(self) -> Path:
        p = Path(self.STORAGE_BASE_DIR) / "uploads"
        p.mkdir(parents=True, exist_ok=True)
        return p
        
    @property
    def OUTPUT_DIR(self) -> Path:
        p = Path(self.STORAGE_BASE_DIR) / "outputs"
        p.mkdir(parents=True, exist_ok=True)
        return p
    
    # S3 / Cloudflare R2
    S3_ENDPOINT: str = os.getenv("S3_ENDPOINT", "")
    S3_ACCESS_KEY: str = os.getenv("S3_ACCESS_KEY", "")
    S3_SECRET_KEY: str = os.getenv("S3_SECRET_KEY", "")
    S3_BUCKET: str = os.getenv("S3_BUCKET", "photogrammetry-data")
    S3_REGION: str = os.getenv("S3_REGION", "auto")
    S3_PUBLIC_URL_BASE: str = os.getenv("S3_PUBLIC_URL_BASE", "")
    
    # Ngrok Integration (🏁 v6.2.0: Added for public accessibility)
    NGROK_AUTHTOKEN: str = os.getenv("NGROK_AUTHTOKEN", "")
    BACKEND_URL: str = os.getenv("BACKEND_URL", "http://localhost:8000")
    
    # Modal
    MODAL_WORKSPACE: str = os.getenv("MODAL_WORKSPACE", "morphic")
    MODAL_APP_NAME: str = "photogrammetry-worker"
    MODAL_FUNCTION_NAME: str = "run_colmap_job"
    
    # Feature Flags
    ENABLE_DENSE: bool = os.getenv("ENABLE_DENSE", "True").lower() == "true"
    ENABLE_SPLAT: bool = os.getenv("ENABLE_SPLAT", "False").lower() == "true"
    
    # Resource Governance
    MAX_UPLOAD_SIZE: int = 100 * 1024 * 1024
    MAX_IMAGES_PER_JOB: int = 100
    MIN_IMAGES_PER_JOB: int = 3
    MAX_GPU_MINUTES: int = 30
    MAX_STORAGE_GB: float = 1.0
    
    # Observability
    OTEL_EXPORTER_OTLP_ENDPOINT: str = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "")
    LOG_LEVEL: str = "INFO"
    
    # Job Control
    MAX_RETRIES: int = 3
    RETRY_BACKOFF_SECONDS: int = 60
    
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        case_sensitive=True
    )

settings = Settings()
