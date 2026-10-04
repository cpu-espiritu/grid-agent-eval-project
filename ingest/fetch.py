# download raw JSON from API in date chunks
# chunks saved to data/raw/<endpoint>/<start>_<end>.json
# chunks already on disk are skipped
# delete a file/folder to re-fetch
# run: python -m ingest.fetch

import json
import time
from datetime import timedelta

import requests

from ingest import config

FMT = "%Y-%m-%dT%H:%MZ"

def date_chunks(start, end, days):
    # yield (chunk_start, chunk_end) pairs covering [start, end).
    cur = start
    while cur < end:
        nxt = min(cur + timedelta(days=days), end)
        yield cur, nxt
        cur = nxt


def get_json(url):
    # GET with retry and exponential backoff, raises after MAX_RETRIES
    for attempt in range(1, config.MAX_RETRIES + 1):
        try:
            r = requests.get(url, headers={"Accept": "application/json"}, timeout=config.TIMEOUT)
            r.raise_for_status()
            payload = r.json()
            if "error" in payload:
                raise ValueError(f"API error: {payload['error']}")
            return payload
        except (requests.RequestException, ValueError) as e:
            if attempt == config.MAX_RETRIES:
                raise
            wait = 2 ** attempt
            print(f"    attempt {attempt} failed ({type(e).__name__}: {e}); retrying in {wait}s")
            time.sleep(wait)


def fetch_endpoint(endpoint):
    out_dir = config.RAW_DIR / endpoint
    out_dir.mkdir(parents=True, exist_ok=True)

    for s, e in date_chunks(config.START, config.END, config.CHUNK_DAYS):
        path = out_dir / f"{s:%Y%m%d}_{e:%Y%m%d}.json"
        if path.exists():
            print(f"  skip  {path.name} (already fetched)")
            continue

        url = f"{config.API_BASE}/{endpoint}/{s:{FMT}}/{e:{FMT}}"
        payload = get_json(url)
        path.write_text(json.dumps(payload))
        print(f"  saved {path.name} ({len(payload['data'])} records)")
        time.sleep(0.5)


def main():
    for endpoint in config.ENDPOINTS:
        print(f"Fetching /{endpoint} {config.START:%Y-%m-%d} -> {config.END:%Y-%m-%d}")
        fetch_endpoint(endpoint)


if __name__ == "__main__":
    main()
