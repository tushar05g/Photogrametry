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
    
    # CORS Configuration (⭐ Security: Restrict to known origins)
    CORS_ORIGINS: list = [
        "http://localhost",
        "http://localhost:3000",
        "http://localhost:8000",
        "http://localhost:8080",
        "http://127.0.0.1",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:8000",
    ]
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Add environment-based origins if provided
        if env_origins := os.getenv("CORS_ORIGINS"):
            self.CORS_ORIGINS.extend([o.strip() for o in env_origins.split(",")])
    
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
    STORAGE_BASE_DIR: str = os.getenv("STORAGE_BASE_DIR", "morphic-scan-data")
    _OUTPUT_DIR: str = os.getenv("OUTPUT_DIR", "output")
    
    # Derived paths as Path objects (Only used for LocalStorage)
    @property
    def UPLOAD_DIR(self) -> Path:
        p = Path(self.STORAGE_BASE_DIR) / "uploads"
        p.mkdir(parents=True, exist_ok=True)
        return p
        
    @property
    def OUTPUT_DIR(self) -> Path:
        p = Path(self._OUTPUT_DIR)
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
    
    # Cloudinary Integration (🏁 v7.1.0: Added for image hosting)
    CLOUDINARY_CLOUD_NAME: str = os.getenv("CLOUDINARY_CLOUD_NAME", "")
    CLOUDINARY_API_KEY: str = os.getenv("CLOUDINARY_API_KEY", "")
    CLOUDINARY_API_SECRET: str = os.getenv("CLOUDINARY_API_SECRET", "")
    
    # Modal
    MODAL_WORKSPACE: str = os.getenv("MODAL_WORKSPACE", "morphic")
    MODAL_APP_NAME: str = "photogrammetry-worker"
    MODAL_FUNCTION_NAME: str = "run_colmap_job"
    
    # Feature Flags
    ENABLE_DENSE: bool = os.getenv("ENABLE_DENSE", "True").lower() == "true"
    ENABLE_SPLAT: bool = os.getenv("ENABLE_SPLAT", "False").lower() == "true"
    
    # Resource Governance
    MAX_UPLOAD_SIZE: int = 500 * 1024 * 1024  # 🏁 v10.0.0: Increased to 500MB for video support
    MAX_IMAGES_PER_JOB: int = 1000  # Increased for video frames
    MIN_IMAGES_PER_JOB: int = 3
    FRAME_EXTRACTION_FPS: int = 10  # Increased (v10.3.3) for better overlap in short videos
    MAX_GPU_MINUTES: int = 30
    MAX_STORAGE_GB: float = 1.0
    
    # Strategy Governance (🏁 v10.4.2)
    WORKER_STRATEGY: str = os.getenv("WORKER_STRATEGY", "push") # 'push' (Modal) or 'pull' (Kaggle)
    WORKER_TOKEN: str = os.getenv("WORKER_TOKEN", "test-token-123")
    
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
print(f"🛠️  Strategy: {settings.WORKER_STRATEGY}")
