"""Application configuration from environment variables.

All config comes from env vars with sensible defaults for local development.
No secrets are ever hardcoded.
"""

import os


# --- Server ---
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))

# --- CORS ---
# In production, set this to your frontend domain(s), comma-separated.
# e.g. ALLOWED_ORIGINS=https://ff-projections.vercel.app
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",")

# --- Rate limiting ---
RATE_LIMIT_PER_MINUTE = int(os.getenv("RATE_LIMIT_PER_MINUTE", "60"))

# --- Data ---
# Path to the export directory containing projections and models
EXPORT_DIR = os.getenv("EXPORT_DIR", "export")

# --- League defaults ---
DEFAULT_LEAGUE_SIZE = 12
DEFAULT_ROSTER = {
    "QB": 1,
    "RB": 2,
    "WR": 2,
    "TE": 1,
    "FLEX": 1,  # RB/WR/TE
}
