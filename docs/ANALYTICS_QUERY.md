# Analytics Query (FUNCTION_CALL fallback) — Design & Usage

This document describes how the bot answers user questions that require reading data from the database using a safe, flexible FUNCTION_CALL fallback based on a JSON specification (spec). It also explains the interaction with the existing catalog of first‑class functions, safety measures, and operational details on Windows and Linux.

## Overview

- Primary path: the model (e.g., Gemini Flash) chooses one of our existing, explicit functions (max/min/statistics/lists). These are cheap, predictable, and fast.
- Fallback path: when a user asks for a report not covered by the explicit set, the model returns:
  - `FUNCTION_CALL: analytics_query(spec_json)`
  - `spec_json` is a strictly validated JSON describing WHAT to fetch (not SQL). We compile and run it safely via ORM.
- Both paths always run under user scoping (only the current user’s data) and read‑only access.

## End‑to‑End Flow

1) User sends a question in chat.
2) AI Instruction (prompt) asks the model to choose:
   - One of the known functions, or
   - `analytics_query(spec_json)` when the known functions do not match.
3) The bot receives a FUNCTION_CALL and normalizes it:
   - Invalid or deprecated calls are remapped to supported ones.
   - `analytics_query` specs are validated against a whitelist schema.
4) The request is executed server‑side:
   - We force‑apply `user_id` filter.
   - We translate `spec -> ORM QuerySet` or parameterized SQL (no string concatenation).
   - We run in read‑only mode with limits and timeouts.
5) Results are formatted to human‑readable text and sent to the user.

## When Fallback Is Used

Fallback is used only if:
- The model cannot confidently map the request to an existing function, or
- The request is too custom to be mapped (e.g., multi‑criteria ad‑hoc queries).

The set of first‑class functions remains and is preferred. Fallback exists to cover the long‑tail of questions.

## Spec Schema (High‑Level)

`analytics_query(spec_json)` uses a constrained JSON specification. Only whitelisted fields, operators, and aggregates are accepted. Any extra or unknown keys are rejected.

Top‑level fields:

- `entity`: one of `expenses | incomes | operations`.
- `filters` (object):
  - `date`: either
    - `{ "between": ["YYYY-MM-DD", "YYYY-MM-DD"] }` or
    - `{ "period": "today|yesterday|week|month|year" }`
  - `category`: one of
    - `{ "equals": "🛒 Продукты" }`
    - `{ "contains": "продукты" }`
    - `{ "id": 123 }`
  - `amount`: `{ "gte": number, "lte": number }` (any subset allowed)
  - `text`: `{ "contains": "строка" }` — matches descriptions (and safe fields only)
- `group_by`: `none | date | category | weekday`
- `aggregate`: array of allowed aggregates: any subset of `["sum","count","avg","max","min"]`
- `sort`: array of objects with whitelisted keys, e.g.:
  - `[{ "by": "sum|avg|max|min|amount|date|count", "dir": "asc|desc" }]`
- `limit`: integer (e.g., `<= 100`)
- `projection` (optional): array of allowed fields for list mode

Notes:
- We will always inject `user_id` on the server side — the model must not supply user scopes.
- Unknown keys, unknown values, or disallowed combinations cause validation errors and the request is refused with a helpful message.

## Examples

1) Smallest expense this month (list of 1):

```
{
  "entity": "expenses",
  "filters": { "date": { "period": "month" } },
  "sort": [{ "by": "amount", "dir": "asc" }],
  "limit": 1
}
```

2) “How much did I spend in August on groceries?” — grouped by category:

```
{
  "entity": "expenses",
  "filters": {
    "date": { "between": ["2025-08-01", "2025-08-31"] },
    "category": { "contains": "продукты" }
  },
  "group_by": "category",
  "aggregate": ["sum", "count"],
  "limit": 50
}
```

3) “Show incomes by day for last week”:

```
{
  "entity": "incomes",
  "filters": { "date": { "period": "week" } },
  "group_by": "date",
  "aggregate": ["sum", "count"],
  "sort": [{ "by": "date", "dir": "asc" }],
  "limit": 100
}
```

## Normalization Rules

- Deprecated or unintended functions are remapped to supported ones.
- If the model returned a date range in an older function form, we convert it to the spec or to an existing function with explicit `start_date`/`end_date`.
- Periods like “August 2025” must anchor to exact dates (e.g., `2025-08-01 .. 2025-08-31`), not “last 31 days”.

## Execution Details

- Validation: a strict schema (e.g., Pydantic) enforces allowed fields and values.
- User scoping: we forcibly add `profile=user_id` filter on the server regardless of the spec.
- ORM compilation: we translate `spec -> Django QuerySet` (or parameterized SQL) using whitelists and bind parameters.
- Read‑only: use a read‑only DB role; optionally enable Postgres Row‑Level Security (RLS) for additional isolation.
- Limits & timeouts: apply `LIMIT`, windowing of dates (e.g., ≤ 1 year), and DB statement timeouts.
- Sorting & pagination: only on whitelisted keys; cap `limit` (e.g., ≤ 100).

## Security Against SQL Injection

- The model never sends SQL or executable code — only a JSON spec.
- We never interpolate strings into SQL; we use ORM or parameterized queries exclusively.
- Strict whitelists for entities, fields, filters, aggregates, and sort keys.
- Forced `user_id` scoping server‑side.
- Read‑only DB user and (optional) RLS ensure no writes and no cross‑user reads.
- Request limits, statement timeouts, and audit logging.

## Error Handling

- Invalid spec → friendly error with a minimal hint (without exposing internal schema details).
- Unsupported combination → suggest a closest supported form or a simpler report.
- Empty results → concise “no data” text with the selected period and filters.

## Logging & Metrics

- Log: user_id, sanitized spec, query shape (aggregates/group_by/sort), runtime, rows returned.
- Metrics: success rate, latency p50/p95, fallback hit rate vs. first‑class functions.

## Windows vs. Linux

- Linux/Mac: native async path parses and executes FUNCTION_CALL directly.
- Windows: adaptive path previously returned raw FUNCTION_CALL as text; now it parses and executes it identically and returns formatted results.

## Interaction With First‑Class Functions

- We keep the existing functions (max/min/statistics/lists) and prefer them when possible.
- The fallback `analytics_query(spec_json)` is used for non‑standard or long‑tail requests.
- Normalization remaps legacy/incorrect function names to either the closest first‑class function or `analytics_query` with an equivalent spec.

## Formatting Responses

- Results from both paths are passed to a unified formatter that returns readable text (localized, with totals, lists, and highlights where appropriate).
- For grouped results (e.g., by `category`), we can optionally emphasize the category referenced in the user’s phrasing.

## Versioning & Governance

- The `spec` is versioned (e.g., add `"version": 1`) so we can extend it safely.
- Any schema extension must preserve backwards compatibility or include migration logic in the normalizer.
- All changes go through code review and include validation tests.

---

If you need examples tailored to a specific phrasing (e.g., “покажи топ‑3 категорий за прошлый квартал”), add them to the prompt’s examples and the test suite to raise coverage for the fallback.

