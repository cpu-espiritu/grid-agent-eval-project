# build the schema description given to the model, read from the live database
# generated rather than hand-written so it can't drift from what ingest.load builds

# low-cardinality text columns whose distinct values are listed for the model
CATEGORICAL = {("generation_mix", "fuel"), ("carbon_intensity", "intensity_index")}


def describe_schema(con):
    tables = [r[0] for r in con.execute(
        "SELECT table_name FROM information_schema.tables WHERE table_schema = 'main' ORDER BY 1").fetchall()]

    lines = []
    for table in tables:
        n = con.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
        lines.append(f"TABLE {table}  ({n} rows)")
        cols = con.execute(
            "SELECT column_name, data_type FROM information_schema.columns "
            "WHERE table_name = ? ORDER BY ordinal_position", [table]).fetchall()
        for name, dtype in cols:
            line = f"  {name} {dtype}"
            if (table, name) in CATEGORICAL:
                values = [r[0] for r in con.execute(
                    f"SELECT DISTINCT {name} FROM {table} WHERE {name} IS NOT NULL ORDER BY 1").fetchall()]
                line += f"  -- values: {', '.join(values)}"
            lines.append(line)

        lo, hi = con.execute(f"SELECT min(period_start_utc), max(period_start_utc) FROM {table}").fetchone()
        lines.append(f"  -- period_start_utc ranges from {lo} to {hi}\n")
    return "\n".join(lines)
