from datetime import datetime, timezone
from pathlib import Path

API_BASE = "https://api.carbonintensity.org.uk"
ENDPOINTS = ["intensity", "generation"]  
TIMEOUT = (5, 30)
MAX_RETRIES = 3
CHUNK_DAYS = 30

# date range fixed for now (will be updated to latest data in future)
START = datetime(2025, 1, 1, tzinfo=timezone.utc)
END = datetime(2026, 1, 1, tzinfo=timezone.utc)

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
DB_PATH = DATA_DIR / "grid.duckdb"