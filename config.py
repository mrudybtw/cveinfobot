import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Application Settings (non-sensitive)
    DB_PATH = os.getenv("DB_PATH", "db/cve.db")
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    LOG_DIR = os.getenv("LOG_DIR", "logs")
    LOG_MAX_SIZE = int(os.getenv("LOG_MAX_SIZE", "10485760"))  # 10MB
    LOG_BACKUP_COUNT = int(os.getenv("LOG_BACKUP_COUNT", "5"))
    TIMEZONE = os.getenv("TIMEZONE", "UTC+3")
    
    # API Endpoints (non-sensitive)
    NVD_API_URL = os.getenv("NVD_API_URL", "https://services.nvd.nist.gov/rest/json/cves/2.0")
    NVD_UPDATE_INTERVAL = int(os.getenv("NVD_UPDATE_INTERVAL", "3600"))
    OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
    
    # Sensitive data (from .env only)
    @classmethod
    def get_telegram_token(cls):
        """Get Telegram token from environment"""
        token = os.getenv("TELEGRAM_TOKEN")
        if not token:
            raise ValueError("TELEGRAM_TOKEN is required in .env file")
        return token
    
    @classmethod
    def get_nvd_api_key(cls):
        """Get NVD API key from environment (optional)"""
        return os.getenv("NVD_API_KEY", "")
    
    @classmethod
    def validate(cls):
        """Validate required configuration"""
        try:
            cls.get_telegram_token()
            return True
        except ValueError as e:
            raise e
