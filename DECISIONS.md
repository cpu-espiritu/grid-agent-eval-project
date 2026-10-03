# Decisions

Running log of design choices, with newest at the bottom.

---

## 1

/generation mix → `generationmix` long for stability (API adds category e.g fuel) + natural GROUP BY/ranking
Rejected wide because of awkward cross-fuel queries for LLM e.g LLM has to infer column names

## 2

Timezones stored in UTC → agent will convert to either GMT or BST depending on date

## 3

Fixed the date range (2025-01-01 to 2025-12-31 UTC) whilst building, saved raw JSON for reproducability
