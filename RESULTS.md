# Results

Every reported number and exactly how it was produced. Newest at the bottom.

How runs are produced:

- `python -m eval.run_agent` runs the agent on all 30 questions in `eval/questions.yaml` and saves `eval/runs/<run_id>/`
  (`meta.json` settings + hashes, `traces.jsonl` every attempt, `summary.json` scores, `failures.csv` for tagging)
- `python -m eval.score eval/runs/<run_id>` rescores a saved run without calling the model
- Correct = matches any listed interpretation within the question's tolerance. M06 is correct only if the agent gives no number
- 95% CI: percentile bootstrap over questions, 10,000 resamples, seed 0. n=30 is small, so intervals are wide

---

## Stage 1: agent evaluation

### Run 1 — superseded, do not report

|                              |                                                                        |
| ---------------------------- | ---------------------------------------------------------------------- |
| Run                          | `20261011T1950Z_gpt-6-luna`                                            |
| Model / prompt / temperature | gpt-6-luna / v1 / model default (1)                                    |
| Git                          | `1175d20`, dirty (eval scripts not yet committed)                      |
| Accuracy                     | 27/30 = 90.0%, 95% CI 76.7% to 100.0%                                  |
| By category                  | easy 5/6, aggregation 5/6, joins 6/6, date handling 5/6, ambiguous 6/6 |
| Mean SQL attempts            | 1.0                                                                    |
| Tokens                       | 37,833 in / 6,708 out                                                  |

Superseded because A06's question text was wrong (DECISIONS.md #9), so this run tested an old version of the test set (`questions_sha256` b6694449…).

Failures:

| Question | What happened                                                                                                                                                      | Tag                  |
| -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------ | -------------------- |
| E05      | Correct SQL (177) but final reply had no `answer` field. Passed when re-run alone (`20261011T1952Z`, diagnostic subset, not counted), so it's run-to-run variation | answer format        |
| A06      | Signed mean (0.978) instead of mean absolute error (9.282). Caused by the faulty question wording                                                                  | n/a (test set fault) |
| D04      | `timezone('Europe/London', period_start_utc)` on the naive UTC column converts the wrong way, 52.37 vs 53.1                                                        | date handling        |

### Official runs

Pending: 3 runs from a clean commit, reported as mean and range with the 95% CI of each.
