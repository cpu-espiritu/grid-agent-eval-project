# score a saved agent run against the expected answers in questions.yaml
# separate from running the agent so scoring can be re-run on saved traces without calling the model again
# run: python -m eval.score eval/runs/<run_id>

import csv
import json
import random
import sys
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path

from eval.check_gold import load_questions

BOOTSTRAP_SAMPLES = 10_000
BOOTSTRAP_SEED = 0  # fixed so the same run always gives the same interval


# ---------------------------------------------------------------- answer matching

def to_number(value):
    if isinstance(value, bool) or value is None:
        raise ValueError("not a number")
    if isinstance(value, (int, float)):
        return float(value)
    return float(str(value).replace(",", "").replace("%", "").strip())


def to_date(value):
    return date.fromisoformat(str(value).strip()[:10])


def to_datetime(value):
    return datetime.fromisoformat(str(value).strip()).replace(second=0, microsecond=0)


def matches(answer, expected, answer_type, tolerance):
    # True if the agent's answer equals one expected value; parse failures count as wrong
    try:
        if answer_type == "number":
            return abs(to_number(answer) - float(expected)) <= tolerance
        if answer_type == "integer":
            return to_number(answer) == float(expected)
        if answer_type == "text":
            return str(answer).strip().lower() == str(expected).strip().lower()
        if answer_type == "date":
            return to_date(answer) == to_date(expected)
        if answer_type == "datetime":
            return to_datetime(answer) == to_datetime(expected)
        if answer_type == "list":
            return isinstance(answer, list) and [str(a).strip().lower() for a in answer] == \
                [str(e).strip().lower() for e in expected]
    except (ValueError, TypeError):
        return False
    raise ValueError(f"unknown answer_type {answer_type}")


def score_answer(answer, q):
    # returns (correct, index of the matched interpretation or None)
    if q["answer_type"] == "unanswerable":
        return answer is None, 0 if answer is None else None
    if answer is None:
        return False, None
    for i, ans in enumerate(q["answers"]):
        if matches(answer, ans["expected"], q["answer_type"], q.get("tolerance", 0)):
            return True, i
    return False, None


# ---------------------------------------------------------------- summary

def bootstrap_ci(correct, samples=BOOTSTRAP_SAMPLES, seed=BOOTSTRAP_SEED):
    # 95% percentile interval for accuracy, resampling questions with replacement
    rng = random.Random(seed)
    n = len(correct)
    accs = sorted(sum(rng.choices(correct, k=n)) / n for _ in range(samples))
    return accs[int(0.025 * samples)], accs[int(0.975 * samples) - 1]


def summarise(scored):
    correct = [s["correct"] for s in scored]
    lo, hi = bootstrap_ci(correct)
    by_cat = defaultdict(list)
    for s in scored:
        by_cat[s["category"]].append(s["correct"])
    return {
        "n_questions": len(scored),
        "n_correct": sum(correct),
        "accuracy": round(sum(correct) / len(correct), 4),
        "ci95": [round(lo, 4), round(hi, 4)],
        "ci_method": f"percentile bootstrap over questions, {BOOTSTRAP_SAMPLES} resamples, seed {BOOTSTRAP_SEED}",
        "by_category": {c: f"{sum(v)}/{len(v)}" for c, v in by_cat.items()},
        "status_counts": dict(sorted(
            {st: sum(1 for s in scored if s["status"] == st) for st in {s["status"] for s in scored}}.items())),
        "mean_attempts": round(sum(s["n_attempts"] for s in scored) / len(scored), 2),
        "tokens": {"input": sum(s["usage"]["input_tokens"] for s in scored),
                   "output": sum(s["usage"]["output_tokens"] for s in scored)},
    }


def write_failures(scored, questions, path):
    # one row per wrong answer; failure_tag and notes are filled in by hand
    # tags: wrong table | wrong filter | invented column | date handling | misread question
    qs = {q["id"]: q for q in questions}
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "category", "question", "expected", "got", "explanation",
                    "status", "n_attempts", "final_sql", "last_error", "failure_tag", "notes"])
        for s in scored:
            if s["correct"]:
                continue
            q = qs[s["id"]]
            expected = " | ".join(json.dumps(a["expected"]) for a in q["answers"])
            last_error = next((a["error"] for a in reversed(s["attempts"]) if a["error"]), s["error"])
            w.writerow([s["id"], s["category"], q["question"], expected, json.dumps(s["answer"]),
                        s["explanation"], s["status"], s["n_attempts"], s["final_sql"], last_error, "", ""])


def score_run(run_dir):
    run_dir = Path(run_dir)
    questions = {q["id"]: q for q in load_questions()}
    traces = [json.loads(line) for line in (run_dir / "traces.jsonl").read_text().splitlines()]

    scored = []
    for t in traces:
        correct, matched = score_answer(t["answer"], questions[t["id"]])
        scored.append({**t, "correct": correct, "matched_interpretation": matched})

    meta = json.loads((run_dir / "meta.json").read_text())
    summary = {"run_id": run_dir.name, **meta, "results": summarise(scored),
               "per_question": {s["id"]: {"correct": s["correct"], "answer": s["answer"],
                                          "matched_interpretation": s["matched_interpretation"]}
                                for s in scored}}
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2, default=str) + "\n")
    write_failures(scored, list(questions.values()), run_dir / "failures.csv")
    return summary, scored


def print_report(summary, scored):
    r = summary["results"]
    for s in scored:
        mark = "ok  " if s["correct"] else "FAIL"
        print(f"  {mark}  {s['id']}  got={json.dumps(s['answer'], default=str)}"
              + ("" if s["correct"] else f"  ({s['status']}, {s['n_attempts']} attempts)"))
    print(f"\nmodel={summary['settings']['model']}  prompt={summary['settings']['prompt_version']}  "
          f"temperature={summary['settings']['temperature']}")
    print(f"accuracy: {r['n_correct']}/{r['n_questions']} = {r['accuracy']:.1%}  "
          f"(95% CI {r['ci95'][0]:.1%} to {r['ci95'][1]:.1%}, n={r['n_questions']} is small)")
    print("by category:", r["by_category"])
    print("statuses:", r["status_counts"], f" mean attempts: {r['mean_attempts']}  tokens: {r['tokens']}")


def main():
    if len(sys.argv) != 2:
        sys.exit("usage: python -m eval.score eval/runs/<run_id>")
    print_report(*score_run(sys.argv[1]))


if __name__ == "__main__":
    main()
