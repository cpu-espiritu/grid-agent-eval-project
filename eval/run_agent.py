# run the agent on every question in questions.yaml, save the traces, then score them
# the agent sees only the question text, never the gold SQL or expected answers
# each run gets its own folder: eval/runs/<utc timestamp>_<model>/
#   meta.json      git SHA, code/data/question hashes, model settings
#   traces.jsonl   one full agent trace per question
#   summary.json   accuracy, 95% bootstrap CI, per-category scores (from eval.score)
#   failures.csv   wrong answers, with blank failure_tag column to fill in by hand
# run: python -m eval.run_agent [--only E01 D03 ...]

import argparse
import hashlib
import json
from datetime import datetime, timezone

import duckdb

from agent.agent import Agent
from eval import score
from eval.check_gold import QUESTIONS_PATH, load_questions, validate_structure
from eval.run_gold import git_info, sha256_files
from ingest import config

RUNS_DIR = QUESTIONS_PATH.parent / "runs"


def main():
    parser = argparse.ArgumentParser(description="Run the agent on the test set and score it")
    parser.add_argument("--only", nargs="+", metavar="ID", help="run a subset of question ids (for debugging)")
    args = parser.parse_args()

    questions = load_questions()
    validate_structure(questions)
    if args.only:
        questions = [q for q in questions if q["id"] in args.only]

    agent = Agent()
    run_id = f"{datetime.now(timezone.utc):%Y%m%dT%H%MZ}_{agent.settings['model']}"
    run_dir = RUNS_DIR / run_id
    run_dir.mkdir(parents=True)

    raw_files = list(config.RAW_DIR.rglob("*.json"))
    meta = {
        "settings": agent.settings,
        "git": git_info(),
        # hashes pin the exact code, prompt, data and questions even if the tree was dirty
        "agent_code_sha256": sha256_files(list((config.ROOT / "agent").glob("*.py")), config.ROOT),
        "system_prompt_sha256": hashlib.sha256(agent.system_prompt.encode()).hexdigest(),
        "raw_data_sha256": sha256_files(raw_files, config.RAW_DIR),
        "questions_sha256": sha256_files([QUESTIONS_PATH], QUESTIONS_PATH.parent),
        "duckdb_version": duckdb.__version__,
        "subset": args.only,
    }
    (run_dir / "meta.json").write_text(json.dumps(meta, indent=2) + "\n")

    print(f"run {run_id}: {len(questions)} questions, model={agent.settings['model']}")
    with open(run_dir / "traces.jsonl", "w") as f:
        for q in questions:
            trace = agent.ask(q["question"])
            f.write(json.dumps({"id": q["id"], "category": q["category"], **trace}, default=str) + "\n")
            f.flush()  # keep finished questions if the run is interrupted
            print(f"  {q['id']}  {trace['status']:<9}  {json.dumps(trace['answer'], default=str)}")

    print("\nscoring...")
    score.print_report(*score.score_run(run_dir))
    print(f"\nsaved to {run_dir.relative_to(config.ROOT)}")


if __name__ == "__main__":
    main()
