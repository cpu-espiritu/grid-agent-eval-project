# verify every gold_sql in questions.yaml still reproduces its stored expected answer
# catches drift if the database is rebuilt from different raw data
# never rewrites expected answers, a failure here means investigate, not overwrite
# run: python -m eval.check_gold

import sys
from collections import Counter
from pathlib import Path

import duckdb
import yaml

from ingest import config

QUESTIONS_PATH = Path(__file__).resolve().parent / "questions.yaml"
CATEGORIES = {"easy", "aggregation", "joins", "date_handling", "ambiguous"}


def load_questions():
    return yaml.safe_load(QUESTIONS_PATH.read_text())["questions"]


def run_gold(con, sql, answer_type):
    rows = con.execute(sql).fetchall()
    if answer_type == "list":
        return [r[0] for r in rows]
    if len(rows) != 1:
        raise ValueError(f"expected 1 row, got {len(rows)}")
    return rows[0][0]


def same(actual, expected, answer_type):
    # gold check is stricter than scoring: expected numbers are stored to 3 dp
    if answer_type == "number":
        return abs(float(actual) - float(expected)) < 0.0006
    return str(actual) == str(expected) if answer_type != "list" else list(actual) == list(expected)


def validate_structure(questions):
    ids = [q["id"] for q in questions]
    dupes = [i for i, n in Counter(ids).items() if n > 1]
    assert not dupes, f"duplicate ids: {dupes}"
    for q in questions:
        assert q["category"] in CATEGORIES, f"{q['id']}: unknown category {q['category']}"
        assert q["answers"], f"{q['id']}: no answers"
        if q["answer_type"] == "number":
            assert "tolerance" in q, f"{q['id']}: number answer needs a tolerance"
    print("questions per category:", dict(Counter(q["category"] for q in questions)))


def main():
    questions = load_questions()
    validate_structure(questions)

    failures = 0
    with duckdb.connect(str(config.DB_PATH), read_only=True) as con:
        for q in questions:
            if q["answer_type"] == "unanswerable":
                print(f"  ok    {q['id']}  (unanswerable, no gold SQL)")
                continue
            for i, ans in enumerate(q["answers"]):
                label = f"{q['id']}.{i}" if len(q["answers"]) > 1 else q["id"]
                try:
                    actual = run_gold(con, ans["gold_sql"], q["answer_type"])
                    ok = same(actual, ans["expected"], q["answer_type"])
                except Exception as e:
                    actual, ok = f"ERROR {type(e).__name__}: {e}", False
                if ok:
                    print(f"  ok    {label}")
                else:
                    failures += 1
                    print(f"  FAIL  {label}  expected={ans['expected']!r}  got={actual!r}")

    print(f"\n{len(questions)} questions, {failures} gold failures")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
