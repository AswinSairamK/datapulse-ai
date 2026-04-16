# ============================================================
# rate_limiter.py — Rate limiting configuration
# ============================================================
# Uses slowapi (FastAPI wrapper around the limits library).
# 
# How it works:
# - Identifies each client by their IP address
# - Counts requests per endpoint per time window
# - Returns 429 Too Many Requests when limit is exceeded
# - Limits are per-endpoint, so chat and rules have different limits
# ============================================================

from slowapi import Limiter
from slowapi.util import get_remote_address


# Create the limiter instance
# get_remote_address extracts the client IP from the request
# This is the function that identifies "who" is making requests
limiter = Limiter(key_func=get_remote_address)