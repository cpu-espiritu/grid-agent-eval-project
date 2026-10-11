# run every gold_sql in questions.yaml against the frozen data and save the outputs
# rebuilds the database from the committed raw JSON first, so same raw files -> same outputs
# output is deterministic (no timestamps): rerunning on unchanged data gives a byte-identical file
# run: python -m eval.run_gold

import hashlib
import json
import subprocess
import sys
from datetime import date, datetime
from decimal import Decimal

import duckdb

from eval.check_gold import QUESTIONS_PATH, load_questions, same, validate_structure
from ingest import config
from ingest import load as ingest_load

OUTPUT_PATH = QUESTIONS_PATH.parent / "gold_outputs.json"


def sha256_files(paths, root):
    # hash relative path + contents of each file, in sorted order
    h = hashlib.sha256()
    for p in sorted(paths):
        h.update(str(p.relative_to(root)).encode())
        h.update(p.read_bytes())
    return h.hexdigest()


def git_info():
    def git(*args):
        return subprocess.run(["git", *args], cwd=config.ROOT, capture_output=True, text=True).stdout.strip()
    return {"sha": git("rev-parse", "HEAD"), "dirty": bool(git("status", "--porcelain"))}


def to_json(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, (float, Decimal)):
        # parallel aggregation sums in a varying order, so the last few float digits change run to run
        # 9 dp is far below every tolerance in questions.yaml
        return round(float(value), 9)
    return value


def run_query(con, sql, answer_type):
    # full result table plus the single value used for comparison (same rules as check_gold)
    cur = con.execute(sql)
    columns = [d[0] for d in cur.description]
    rows = [[to_json(v) for v in r] for r in cur.fetchall()]
    if answer_type == "list":
        value = [r[0] for r in rows]
    elif len(rows) == 1:
        value = rows[0][0]
    else:
        raise ValueError(f"expected 1 row, got {len(rows)}")
    return columns, rows, value


def main():
    questions = load_questions()
    validate_structure(questions)

    # rebuild from raw JSON 
    print("rebuilding database from raw JSON...")
    ingest_load.main()

    raw_files = list(config.RAW_DIR.rglob("*.json"))
    meta = {
        "git": git_info(),
        "duckdb_version": duckdb.__version__,
        "raw_data_sha256": sha256_files(raw_files, config.RAW_DIR),
        "raw_file_count": len(raw_files),
        "questions_sha256": sha256_files([QUESTIONS_PATH], QUESTIONS_PATH.parent),
        "date_range_utc": [config.START.isoformat(), config.END.isoformat()],
    }

    results, mismatches = [], 0
    with duckdb.connect(str(config.DB_PATH), read_only=True) as con:
        for q in questions:
            entry = {"id": q["id"], "category": q["category"], "answer_type": q["answer_type"], "answers": []}
            for ans in q["answers"]:
                out = {"interpretation": ans.get("interpretation"), "gold_sql": ans["gold_sql"],
                       "expected": ans["expected"]}
                if ans["gold_sql"] is None:
                    out["status"] = "unanswerable"
                else:
                    try:
                        columns, rows, value = run_query(con, ans["gold_sql"], q["answer_type"])
                        ok = same(value, ans["expected"], q["answer_type"])
                        out.update(columns=columns, rows=rows, value=value, status="match" if ok else "MISMATCH")
                    except Exception as e:
                        out.update(error=f"{type(e).__name__}: {e}", status="ERROR")
                if out["status"] in ("MISMATCH", "ERROR"):
                    mismatches += 1
                print(f"  {out['status']:<12} {q['id']}  {out.get('value', out.get('error', ''))}")
                entry["answers"].append(out)
            results.append(entry)

    OUTPUT_PATH.write_text(json.dumps({"meta": meta, "results": results}, indent=2) + "\n")
    print(f"\n{len(questions)} questions, {mismatches} mismatches/errors")
    print(f"wrote {OUTPUT_PATH.relative_to(config.ROOT)}")
    if meta["git"]["dirty"]:
        print("note: working tree has uncommitted changes, commit before treating these outputs as final")
    sys.exit(1 if mismatches else 0)


if __name__ == "__main__":
    main()
