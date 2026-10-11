# Decisions

Running log of design choices, with newest at the bottom.

---

## 1

/generation mix -> `generationmix` long for stability (API adds category e.g fuel) + natural GROUP BY/ranking
Rejected wide because of awkward cross-fuel queries for LLM e.g LLM has to infer column names

## 2

Timezones stored in UTC -> agent will convert to either GMT or BST depending on date

## 3

Fixed the date range (2025-01-01 to 2025-12-31 UTC) whilst building, saved raw JSON for reproducability

## 4

Database is rebuilt from the raw JSON each load, same files -> same database, stage 2 is when we add new data

## 5

Column names have their units, prevents agent from guessing units/timezone incorrectly + API names 'from' and 'to' that would break the SQL queries

## 6

Timestamps with no timezone automatically get UTC, DuckDB would default to laptop timezone causing errors to the agents response

## 7

Seperate raw JSON (source of truth), the build (loader) and ground truth (saved gold SQL results), so accuracy is only dependent on model changes

## 8

Model selected is gpt-6-luna

## 9

A06 reworded (2026-10-11) -> edited before the first commit, new wording ("average difference") changed the meaning to a signed mean but gold answer stayed as mean absolute error. Restored intended meaning: "On average, how far was the forecast carbon intensity from the actual in 2025, in either direction?", gold SQL and expected (9.282) unchanged
Found after first eval run (20261011T1950Z), that run is superseded but kept in eval/runs/ (no deleting runs)
Rejected keeping the wording and accepting the signed answer (0.978), that was the agent's answer so it would move the test towards the model
