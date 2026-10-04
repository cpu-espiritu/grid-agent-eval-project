# build DuckDB tables from the raw JSON in data/raw/
# full rebuild every run (keeps database schema dependent only on raw files)
# run: python -m ingest.load

import json

import duckdb
import pandas as pd

from ingest import config

def read_raw(endpoint):
    # concatenate 'data' arrays from every raw chunk for an endpoint
    files = sorted((config.RAW_DIR / endpoint).glob("*.json"))
    if not files:
        raise FileNotFoundError(f"No raw files for /{endpoint}. Run: python -m ingest.fetch")
    records = []
    for f in files:
        records.extend(json.loads(f.read_text())["data"])
    return records


def clean_periods(df):
    # parse timestamps, cut to [START, END) and drop chunk-boundary duplicates
    # half-hour ending at the requested start, adjacent chunks overlap by one period
    df["period_start_utc"] = pd.to_datetime(df["from"], utc=True)
    df["period_end_utc"] = pd.to_datetime(df["to"], utc=True)
    df = df[(df["period_start_utc"] >= config.START) & (df["period_start_utc"] < config.END)]
    for col in ["period_start_utc", "period_end_utc"]:
        df[col] = df[col].dt.tz_localize(None)  # store as naive UTC
    return df


def build_intensity():
    df = pd.json_normalize(read_raw("intensity"))
    df = clean_periods(df).drop_duplicates("period_start_utc")
    return df.rename(columns={
        "intensity.forecast": "forecast_gco2_per_kwh",
        "intensity.actual": "actual_gco2_per_kwh",
        "intensity.index": "intensity_index",
    })[["period_start_utc", "period_end_utc",
        "forecast_gco2_per_kwh", "actual_gco2_per_kwh", "intensity_index"]]


def build_generation():
    df = pd.json_normalize(read_raw("generation"), record_path="generationmix", meta=["from", "to"])
    df = clean_periods(df).drop_duplicates(["period_start_utc", "fuel"])
    return df.rename(columns={"perc": "percentage"})[
        ["period_start_utc", "period_end_utc", "fuel", "percentage"]]


def write_tables(con, intensity, generation):
    con.execute("DROP TABLE IF EXISTS carbon_intensity")
    con.execute("""
        CREATE TABLE carbon_intensity (
            period_start_utc      TIMESTAMP PRIMARY KEY,
            period_end_utc        TIMESTAMP NOT NULL,
            forecast_gco2_per_kwh INTEGER,
            actual_gco2_per_kwh   INTEGER,
            intensity_index       VARCHAR
        )""")
    con.execute("INSERT INTO carbon_intensity SELECT * FROM intensity")

    con.execute("DROP TABLE IF EXISTS generation_mix")
    con.execute("""
        CREATE TABLE generation_mix (
            period_start_utc TIMESTAMP NOT NULL,
            period_end_utc   TIMESTAMP NOT NULL,
            fuel             VARCHAR NOT NULL,
            percentage       DOUBLE,
            PRIMARY KEY (period_start_utc, fuel)
        )""")
    con.execute("INSERT INTO generation_mix SELECT * FROM generation")


def report(con):
    """Print sanity checks. Expected: 48 periods per UTC day."""
    expected = int((config.END - config.START).total_seconds() // 1800)
    print(f"\nExpected half-hours in range: {expected}")
    for table in ["carbon_intensity", "generation_mix"]:
        rows, periods, lo, hi = con.execute(f"""
            SELECT count(*), count(DISTINCT period_start_utc),
                   min(period_start_utc), max(period_start_utc)
            FROM {table}""").fetchone()
        print(f"{table:17s} rows={rows:>7}  periods={periods:>6}  "
              f"missing={expected - periods:>4}  range={lo} -> {hi}")

    nulls = con.execute(
        "SELECT count(*) FROM carbon_intensity WHERE actual_gco2_per_kwh IS NULL").fetchone()[0]
    print(f"carbon_intensity  null actuals={nulls}")

    bad_sums = con.execute("""
        SELECT count(*) FROM (
            SELECT period_start_utc, sum(percentage) AS total
            FROM generation_mix GROUP BY 1
        ) WHERE abs(total - 100) > 1""").fetchone()[0]
    print(f"generation_mix    periods where fuels don't sum to 100 (+/-1): {bad_sums}")
    print("fuels:", [r[0] for r in con.execute(
        "SELECT DISTINCT fuel FROM generation_mix ORDER BY 1").fetchall()])


def main():
    intensity = build_intensity()
    generation = build_generation()
    config.DATA_DIR.mkdir(exist_ok=True)
    with duckdb.connect(str(config.DB_PATH)) as con:
        write_tables(con, intensity, generation)
        report(con)
    print(f"\nWrote {config.DB_PATH}")


if __name__ == "__main__":
    main()
