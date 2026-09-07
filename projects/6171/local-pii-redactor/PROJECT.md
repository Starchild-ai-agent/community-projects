# Local PII Redactor

## What
Deterministically detects and replaces common PII patterns locally.

## Required env
None.

## How to start
`printf 'email jane@example.com' | python3 scripts/redact.py`

## Outputs
JSON containing redacted_text, per-pattern counts, and total.

## Troubleshooting
Input must be UTF-8 text on stdin. Pattern matching is heuristic.
