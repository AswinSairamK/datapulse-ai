from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.core.database import engine, Base
from app.core.rate_limiter import limiter
from app.api.endpoints import router
from app.services.scheduler import start_scheduler, stop_scheduler
from app.api.auth_endpoints import router as auth_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Runs on startup and shutdown."""
    Base.metadata.create_all(bind=engine)
    start_scheduler(interval_minutes=60)
    yield
    stop_scheduler()


app = FastAPI(
    title="DataPulse AI",
    description="Intelligent Data Quality Monitoring & AI-Powered Analytics",
    version="1.0.0",
    lifespan=lifespan
)

# Register the rate limiter with the app
# This makes limiter available as app.state.limiter
app.state.limiter = limiter

# Custom handler for when rate limit is exceeded
# Returns a clean JSON error instead of HTML
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.include_router(auth_router, prefix="/api")
app.include_router(router, prefix="/api")


@app.get("/")
def root():
    return {
        "app": "DataPulse AI",
        "status": "running",
        "docs": "Visit /docs for API documentation"
    }