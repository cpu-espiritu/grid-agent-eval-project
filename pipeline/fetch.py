"""Download raw JSON from the Carbon Intensity API into data/raw/<endpoint>/.

Run with: python -m pipeline.fetch [--force]
"""

import argparse
import json
import time
from datetime import timedelta

import requests

from pipeline import config

API_TIME_FORMAT = "%Y-%m-%dT%H:%MZ"


def date_chunks(start, end, days=config.CHUNK_DAYS):
    """Split [start, end) into consecutive (from, to) windows of at most `days` days."""
    chunks = []
    current = start
    while current < end:
        nxt = min(current + timedelta(days=days), end)
        chunks.append((current, nxt))
        current = nxt
    return chunks


def get_json(url):
    """GET a URL and return parsed JSON, retrying with exponential backoff on failure."""
    for attempt in range(config.MAX_RETRIES + 1):
        try:
            r = requests.get(url, headers=config.HEADERS, timeout=config.TIMEOUT)
            r.raise_for_status()
            return r.json()
        except (requests.exceptions.RequestException, ValueError) as e:
            if attempt == config.MAX_RETRIES:
                raise
            wait = config.BACKOFF_SECONDS * 2**attempt
            print(f"  {type(e).__name__}: {e} -> retrying in {wait}s")
            time.sleep(wait)


def raw_path(endpoint, start, end):
    name = f"{start:%Y%m%dT%H%M}_{end:%Y%m%dT%H%M}.json"
    return config.RAW_DIR / endpoint / name


def fetch_endpoint(endpoint, start=config.START, end=config.END, force=False):
    """Save one raw JSON file per chunk. Existing files are skipped unless force=True."""
    out_dir = config.RAW_DIR / endpoint
    out_dir.mkdir(parents=True, exist_ok=True)

    for chunk_start, chunk_end in date_chunks(start, end):
        path = raw_path(endpoint, chunk_start, chunk_end)
        if path.exists() and not force:
            print(f"skip  {endpoint} {path.name}")
            continue

        url = (
            f"{config.BASE_URL}/{endpoint}/"
            f"{chunk_start.strftime(API_TIME_FORMAT)}/{chunk_end.strftime(API_TIME_FORMAT)}"
        )
        data = get_json(url)
        if not data.get("data"):
            raise ValueError(f"No 'data' in response from {url}")

        # Write to a temp file first so an interrupted run never leaves a half-written file
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data))
        tmp.replace(path)
        print(f"saved {endpoint} {path.name} ({len(data['data'])} records)")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true", help="re-download files that already exist")
    args = parser.parse_args()

    for endpoint in config.ENDPOINTS:
        fetch_endpoint(endpoint, force=args.force)


if __name__ == "__main__":
    main()
