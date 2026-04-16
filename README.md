# 🔍 DataPulse AI

AI-powered data quality monitoring platform. Connect your PostgreSQL database, chat with your data in plain English, get automated quality monitoring, and receive AI-generated rule suggestions.

## Features

- **AI Chat with Your Database** — Ask questions in plain English, get SQL queries, data, and auto-generated visualizations powered by Groq (Llama 3.3 70B) or local Ollama
- **Data Quality Monitoring** — 5 check types (null, range, duplicate, freshness, custom SQL) with 0-100 health scores
- **AI-Suggested Rules** — AI profiles your tables and recommends quality rules automatically
- **Multi-Database Support** — PostgreSQL, MySQL, and Snowflake from one dashboard
- **Automated Scheduling** — Background checks run hourly via APScheduler with email alerts
- **Data Masking** — Built-in PII masking for emails, phones, SSNs, credit cards
- **Enterprise Security** — JWT authentication, Fernet encryption, SQL injection prevention, rate limiting, complete audit logging
- **Multi-Tenant** — Full user isolation with separate data sources and rules per user
- **Local or Cloud AI** — Choose between Groq cloud (fast) or Ollama local (private)


### 💬 AI Chat Module
Ask questions in plain English — AI converts to SQL, runs it, and explains results.

### 📊 Health Monitor
Automated data quality checks with health scoring (0-100) per table:
- **Null checks** — detect missing values
- **Range checks** — find out-of-bound values
- **Duplicate checks** — identify unexpected duplicates
- **Freshness checks** — alert on stale data
- **Custom SQL** — user-defined validation queries

### 🤖 AI Rule Suggestions
AI profiles your table (schema, distributions, patterns) and auto-suggests monitoring rules with explanations.

### ⏰ Background Scheduler
Automated checks run every hour. Historical results build trends over time.

## Tech Stack

- **Backend:** FastAPI + SQLAlchemy + Pydantic
- **Frontend:** Streamlit + Plotly
- **Database:** PostgreSQL (app), PostgreSQL/MySQL/Snowflake (monitored)
- **AI:** Groq API (Llama 3.3 70B) or Ollama (local)
- **Security:** JWT, bcrypt, Fernet, slowapi
- **Scheduling:** APScheduler
- **Email:** SMTP (Gmail)

### Prerequisites

- Python 3.12+
- PostgreSQL 14+
- Optional: Ollama for local LLM


### Installation

\`\`\`bash
# Clone the repo
git clone https://github.com/AswinSairamK/datapulse-ai.git
cd datapulse-ai

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env with your credentials

# Run the FastAPI backend
uvicorn app.main:app --reload

# In a new terminal, run the Streamlit dashboard
streamlit run dashboard/app.py
\`\`\`

### Environment Variables

Create a \`.env\` file in the project root:

\`\`\`
GROQ_API_KEY=your_groq_api_key
ENCRYPTION_KEY=your_fernet_key
JWT_SECRET_KEY=your_jwt_secret
DB_PASSWORD=your_postgres_password
SMTP_USER=your_email@gmail.com
SMTP_PASSWORD=your_app_password
\`\`\`

Generate a Fernet key:
\`\`\`python
from cryptography.fernet import Fernet
print(Fernet.generate_key().decode())
\`\`\`

## Architecture

- FastAPI backend exposes REST endpoints protected by JWT auth
- Streamlit dashboard provides a user-friendly interface
- SQLAlchemy ORM with multi-user data isolation
- Background scheduler runs DQ checks hourly
- AI layer abstracts Groq/Ollama for provider-agnostic integration

## Screenshots

_Add screenshots of your dashboard here_

## Setup

1. Install dependencies: `pip install fastapi uvicorn sqlalchemy psycopg2-binary pydantic groq apscheduler streamlit plotly requests`
2. Create database: `psql -U postgres -c "CREATE DATABASE datapulse_db;"`
3. Copy `config_template.py` to `app/core/config.py` and add your credentials
4. Start the API: `uvicorn app.main:app --reload`
5. Start the dashboard: `streamlit run dashboard/app.py`

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /api/data-sources | Connect a database |
| GET | /api/data-sources | List connections |
| POST | /api/data-sources/test | Test connection |
| GET | /api/data-sources/{id}/tables | List tables |
| GET | /api/data-sources/{id}/tables/{name}/columns | List columns |
| POST | /api/rules | Add monitoring rule |
| GET | /api/rules/{id} | List rules |
| DELETE | /api/rules/{id} | Delete rule |
| POST | /api/chat | Chat with data (AI) |
| POST | /api/checks/run/{id} | Run DQ checks |
| GET | /api/checks/results/{id} | Get check history |
| GET | /api/suggest/{id}/{table} | AI suggest rules |
| POST | /api/suggest/accept | Accept suggestion |

## Author

**Aswin Sairam Kannan**  
Data Engineer | Chennai, India  
Email: sairam111297@gmail.com  
GitHub: [@AswinSairamK](https://github.com/AswinSairamK)

## License

MIT License — feel free to use, modify, and learn from this project.
"@ | Out-File -FilePath README.md -Encoding UTF8