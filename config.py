import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Application Settings (non-sensitive)
    DB_PATH = os.getenv("DB_PATH", "db/cve.db")
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    LOG_DIR = os.getenv("LOG_DIR", "logs")
    
    # API Endpoints (non-sensitive)
    NVD_API_URL = os.getenv("NVD_API_URL", "https://services.nvd.nist.gov/rest/json/cves/2.0")
    NVD_UPDATE_INTERVAL = int(os.getenv("NVD_UPDATE_INTERVAL", "3600"))  # 1 час
    OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
    EPSS_API_URL = os.getenv("EPSS_API_URL", "https://api.first.org/data/v1/epss")
    
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
    def get_admin_ids(cls):
        """Get admin user IDs from environment (optional)"""
        admin_ids_str = os.getenv("ADMIN_IDS", "")
        if not admin_ids_str:
            return []
        try:
            return [int(x.strip()) for x in admin_ids_str.split(",") if x.strip()]
        except ValueError:
            return []
    
    @classmethod
    def validate(cls):
        """Validate required configuration"""
        try:
            cls.get_telegram_token()
            return True
        except ValueError as e:
            raise e
