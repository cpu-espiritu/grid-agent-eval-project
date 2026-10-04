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
