"""Flatten raw JSON from data/raw/ and load it into DuckDB.

Tables (all timestamps UTC, see DECISIONS.md #2):
  intensity       one row per half hour: from_utc, to_utc, forecast, actual, index
  generation_mix  long format, one row per half hour per fuel: from_utc, to_utc, fuel, perc
                  (see DECISIONS.md #1)

Run with: python -m pipeline.load
"""

import json

import duckdb
import pandas as pd

from pipeline import config


def read_records(endpoint):
    """Return the 'data' records from every raw file for an endpoint."""
    files = sorted((config.RAW_DIR / endpoint).glob("*.json"))
    if not files:
        raise FileNotFoundError(f"No raw files in {config.RAW_DIR / endpoint}, run pipeline.fetch first")

    records = []
    for f in files:
        records.extend(json.loads(f.read_text())["data"])
    return records


def tidy_periods(df, start=config.START, end=config.END):
    """Parse from/to as UTC, keep only periods inside [start, end)."""
    df = df.rename(columns={"from": "from_utc", "to": "to_utc"})
    df["from_utc"] = pd.to_datetime(df["from_utc"], utc=True)
    df["to_utc"] = pd.to_datetime(df["to_utc"], utc=True)
    df = df[(df["from_utc"] >= start) & (df["to_utc"] <= end)]
    return df


def build_intensity(records):
    df = pd.json_normalize(records)
    df = df.rename(
        columns={
            "intensity.forecast": "forecast",
            "intensity.actual": "actual",
            "intensity.index": "index",
        }
    )
    df = tidy_periods(df[["from", "to", "forecast", "actual", "index"]])
    df = df.drop_duplicates(subset="from_utc", keep="last")
    df["forecast"] = df["forecast"].astype("Int64")
    df["actual"] = df["actual"].astype("Int64")  # actual can be null
    return df.sort_values("from_utc").reset_index(drop=True)


def build_generation_mix(records):
    df = pd.json_normalize(records, record_path="generationmix", meta=["from", "to"])
    df = tidy_periods(df[["from", "to", "fuel", "perc"]])
    df = df.drop_duplicates(subset=["from_utc", "fuel"], keep="last")
    df["perc"] = df["perc"].astype(float)
    return df.sort_values(["from_utc", "fuel"]).reset_index(drop=True)


def load(db_path=config.DB_PATH):
    intensity = build_intensity(read_records("intensity"))
    generation_mix = build_generation_mix(read_records("generation"))

    con = duckdb.connect(str(db_path))
    try:
        con.execute("SET TimeZone = 'UTC'")
        con.register("intensity_df", intensity)
        con.register("generation_mix_df", generation_mix)

        con.execute(
            """
            CREATE OR REPLACE TABLE intensity (
                from_utc TIMESTAMPTZ PRIMARY KEY,
                to_utc   TIMESTAMPTZ NOT NULL,
                forecast INTEGER,
                actual   INTEGER,
                "index"  VARCHAR
            )
            """
        )
        con.execute("INSERT INTO intensity SELECT from_utc, to_utc, forecast, actual, \"index\" FROM intensity_df")

        con.execute(
            """
            CREATE OR REPLACE TABLE generation_mix (
                from_utc TIMESTAMPTZ NOT NULL,
                to_utc   TIMESTAMPTZ NOT NULL,
                fuel     VARCHAR NOT NULL,
                perc     DOUBLE,
                PRIMARY KEY (from_utc, fuel)
            )
            """
        )
        con.execute("INSERT INTO generation_mix SELECT from_utc, to_utc, fuel, perc FROM generation_mix_df")
    finally:
        con.close()

    print(f"loaded {len(intensity)} rows into intensity")
    print(f"loaded {len(generation_mix)} rows into generation_mix")
    print(f"database: {db_path}")


if __name__ == "__main__":
    load()
