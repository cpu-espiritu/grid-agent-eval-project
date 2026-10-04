"""Shared settings for the fetch and load steps."""

from datetime import datetime, timezone
from pathlib import Path

# Carbon Intensity API (National Grid ESO), no auth needed
BASE_URL = "https://api.carbonintensity.org.uk"
ENDPOINTS = ["intensity", "generation"]

# Fixed build window, UTC, end exclusive (see DECISIONS.md #2, #3)
START = datetime(2025, 1, 1, tzinfo=timezone.utc)
END = datetime(2026, 1, 1, tzinfo=timezone.utc)

# The API caps how much a single from/to request can cover, so the range is split into chunks
CHUNK_DAYS = 14

# Requests
TIMEOUT = (5, 30)  # (connect, read) seconds
MAX_RETRIES = 4
BACKOFF_SECONDS = 2  # doubles on each retry
HEADERS = {"Accept": "application/json"}

# Paths
ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"
DB_PATH = ROOT / "grid.duckdb"
