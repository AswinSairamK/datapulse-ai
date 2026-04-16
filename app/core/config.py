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

def clean_env(name, default=""):
    """Get env var and strip surrounding quotes if present."""
    value = os.getenv(name, default)
    if value and len(value) >= 2:
        if (value[0] == '"' and value[-1] == '"') or (value[0] == "'" and value[-1] == "'"):
            value = value[1:-1]
    return value



# --- Database ---
DATABASE_URL = clean_env("DATABASE_URL", "")
if not DATABASE_URL:
    DB_HOST = clean_env("DB_HOST", "localhost")
    DB_PORT = clean_env("DB_PORT", "5432")
    DB_NAME = clean_env("DB_NAME", "datapulse_db")
    DB_USER = clean_env("DB_USER", "postgres")
    DB_PASSWORD = clean_env("DB_PASSWORD", "admin123")
    DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# --- Encryption ---
ENCRYPTION_KEY = clean_env("ENCRYPTION_KEY", "")

# --- JWT ---
JWT_SECRET_KEY = clean_env("JWT_SECRET_KEY", "change-this-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_HOURS = 24
JWT_ACCESS_TOKEN_EXPIRE_MINUTES = JWT_EXPIRY_HOURS * 60

# --- AI / LLM ---
GROQ_API_KEY = clean_env("GROQ_API_KEY", "")
# Temporary debug
if GROQ_API_KEY:
    print(f"🔑 GROQ key loaded: {GROQ_API_KEY[:8]}...{GROQ_API_KEY[-4:]} (length: {len(GROQ_API_KEY)})")
else:
    print("🔑 GROQ key: NOT SET")
    
GROQ_MODEL = "llama-3.3-70b-versatile"

# --- Ollama (Local LLM) ---
OLLAMA_MODEL = "llama3.2"
OLLAMA_HOST = "http://localhost:11434"

AI_PROVIDER = clean_env("AI_PROVIDER", "groq")

# --- Email (SMTP) ---
SMTP_HOST = clean_env("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(clean_env("SMTP_PORT", "587"))
SMTP_USER = clean_env("SMTP_USER", "")
SMTP_PASSWORD = clean_env("SMTP_PASSWORD", "")
ALERT_EMAIL = clean_env("ALERT_EMAIL", "")