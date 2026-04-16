# ============================================================
# config.py — DataPulse AI Configuration
# ============================================================
# Reads secrets from environment variables (.env file)
# NEVER commit real credentials to git!
# ============================================================

import os
from pathlib import Path

# Load .env file if it exists
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent.parent.parent / ".env"
    load_dotenv(env_path)
except ImportError:
    pass

# --- Database ---
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "datapulse_db")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# --- Encryption ---
ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY", "")

# --- JWT ---
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "change-this-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_HOURS = 24
JWT_EXPIRY_HOURS = 24
JWT_ACCESS_TOKEN_EXPIRE_MINUTES = JWT_EXPIRY_HOURS * 60  # 1440 minutes

# --- AI / LLM ---
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = "llama-3.3-70b-versatile"

# --- Ollama (Local LLM) ---
OLLAMA_MODEL = "llama3.2"
OLLAMA_HOST = "http://localhost:11434"

# --- AI Provider Selection ---
AI_PROVIDER = os.getenv("AI_PROVIDER", "groq")  # "groq" or "ollama"

# --- Email (SMTP) ---
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
ALERT_EMAIL = os.getenv("ALERT_EMAIL", "")