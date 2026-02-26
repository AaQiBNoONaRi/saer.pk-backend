"""
Application settings and configuration
"""
import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    # Application
    APP_NAME = "Saerpk 2.0"
    VERSION = "2.0.0"
    DEBUG = os.getenv("DEBUG", "True") == "True"
    
    # Security
    SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
    ALGORITHM = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours
    
    # CORS
    ALLOWED_ORIGINS = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
    ]
    
    # Employee ID Prefixes
    ORG_EMPLOYEE_PREFIX = "ORGEP"
    BRANCH_EMPLOYEE_PREFIX = "BREMP"
    AGENCY_EMPLOYEE_PREFIX = "AGCEMP"
    
    # Pagination
    DEFAULT_PAGE_SIZE = 20
    MAX_PAGE_SIZE = 100

    # File Uploads
    UPLOAD_DIR = os.path.join(os.getcwd(), "uploads")

    # AIQS Flight API
    AIQS_AUTH_URL = os.getenv("AIQS_AUTH_URL", "https://pp-auth-api.aiqs.link/auth/cognito")
    AIQS_REST_URL = os.getenv("AIQS_REST_URL", "https://pp-api.aiqs.link")
    AIQS_WSS_URL  = os.getenv("AIQS_WSS_URL",  "wss://pp-api.aiqs.link")
    AIQS_CLIENT_ID = os.getenv("AIQS_CLIENT_ID", "6tvsrg4go69ktu9f4369tvmvi8")
    AIQS_USERNAME  = os.getenv("AIQS_USERNAME",  "preprod@gmail.com")
    AIQS_PASSWORD  = os.getenv("AIQS_PASSWORD",  "Preprod#1@2025")

settings = Settings()
