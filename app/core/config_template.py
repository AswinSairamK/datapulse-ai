# Copy this as app/core/config.py and fill in your values

DB_HOST = "localhost"
DB_PORT = "5432"
DB_NAME = "datapulse_db"
DB_USER = "postgres"
DB_PASSWORD = "YOUR_PASSWORD"
DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

GROQ_API_KEY = "YOUR_GROQ_API_KEY"
GROQ_MODEL = "llama-3.3-70b-versatile"

APP_NAME = "DataPulse AI"
APP_VERSION = "1.0.0"