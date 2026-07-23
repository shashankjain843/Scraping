import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file from backend directory or project root
BASE_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = Path(__file__).resolve().parent
load_dotenv(BACKEND_DIR / ".env")
load_dotenv(BASE_DIR / ".env")


class Settings:
    PROJECT_NAME: str = "Fresher Job Application Assistance Platform"
    VERSION: str = "1.0.0"
    BASE_DIR: Path = BASE_DIR

    
    # Secret Key for JWT
    SECRET_KEY: str = os.getenv("SECRET_KEY", "super-secret-key-change-in-production-123456789")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7 # 7 days
    
    # Adzuna API
    ADZUNA_APP_ID: str = os.getenv("ADZUNA_APP_ID", "")
    ADZUNA_APP_KEY: str = os.getenv("ADZUNA_APP_KEY", "")
    ADZUNA_BASE_URL: str = "https://api.adzuna.com/v1/api/jobs/in/search"
    
    # Rate Limits for Adzuna API
    ADZUNA_CALLS_PER_MINUTE_LIMIT: int = 25
    ADZUNA_CALLS_PER_DAY_LIMIT: int = 250
    
    # Gemini AI API Key
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    
    # Default SMTP Credentials
    SMTP_SERVER: str = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_EMAIL: str = os.getenv("SMTP_EMAIL", "")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
    
    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'app.db'}")
    
    # Resume uploads directory
    UPLOADS_DIR: Path = BASE_DIR / "uploads"
    
settings = Settings()
settings.UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
