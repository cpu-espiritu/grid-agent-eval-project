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

### Official runs (v1)

Three back-to-back runs of `python -m eval.run_agent`, all from commit `6163d6f`, identical code
(`agent_code_sha256` 3b00b93c…), prompt v1, questions `43fffb53…` (after the A06 fix), gpt-6-luna, temperature = model default (1).

| Run                         | Accuracy          | 95% CI              | Failed   |
| --------------------------- | ----------------- | ------------------- | -------- |
| `20261011T2003Z_gpt-6-luna` | 29/30 = 96.7%     | 90.0% to 100%       | J03      |
| `20261011T2005Z_gpt-6-luna` | 30/30 = 100%      | 100% to 100%        | none     |
| `20261011T2007Z_gpt-6-luna` | 28/30 = 93.3%     | 83.3% to 100%       | D03, D05 |
| **Mean of 3**               | **87/90 = 96.7%** | range 93.3% to 100% |          |

By category, summed over 3 runs: easy 18/18, aggregation 18/18, joins 17/18, date handling 16/18, ambiguous 18/18.
27 of 30 questions were correct in all three runs. Mean SQL attempts per question ≈ 1.0, so retries were almost never needed.
Tokens over 3 runs: 111,749 in / 20,324 out.

n=30 is small: the interval on a single run is wide, and a 100% run has a degenerate 100–100% interval, which
says nothing about questions outside the test set. The spread across runs (93.3–100%) comes from the model's
sampling (temperature 1), separate from the uncertainty of having only 30 questions.

Note: runs 2005Z and 2007Z record `"dirty": true`. That was a bug in the dirty check (it counted the earlier runs'
untracked output folders), not a code change: commit and code hash match run 2003Z. Fixed afterwards by
excluding `eval/runs/` from the check.

Failures:

| Run   | Question | What happened                                                                                                                                                                                                                | Tag             |
| ----- | -------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------- |
| 2003Z | J03      | First query was correct (both tied half-hours, 72.0 and 72.1), then the model sent another query to get the timestamps instead of answering. The v1 loop allows no queries after a successful one, so no answer was recorded | no final answer |
| 2007Z | D03      | `timezone('Europe/London', period_start_utc)` on the naive UTC column converts the wrong way: 50 periods instead of 46                                                                                                       | date handling   |
| 2007Z | D05      | First query gave the correct value (144.798), then the model sent a corrected query (its date bounds were off by an hour) instead of answering. Same loop limit as J03                                                       | no final answer |

Patterns:

- **no final answer** (2 here, probably 3 counting E05 in run 1): the model wants a follow-up query after a successful one. This is a limit of the v1 loop design, not wrong SQL. It's not one of the five planned tags.
- **date handling** (1 here, plus D04 in run 1): the same wrong-way `timezone()` call on a naive UTC column both times.
