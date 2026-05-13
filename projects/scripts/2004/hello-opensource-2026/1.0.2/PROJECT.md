# hello-opensource-2026

End-to-end smoke test for the public Code Projects API after PR #2 merge.

## What

Tiny test script that verifies the full open-source publish flow:

- publish_project() writes into community-projects repo
- GET /api/code-projects/explore returns the entry without auth
- GET /api/code-projects/list returns it without auth
- GET /api/code-projects/{user_id}/{slug} returns it without auth
- Auto-link reverse-lookup behaves as expected when no matching live preview exists
- fork_project() round-trips the source back to the workspace

## Required env

None.

## How to start

```
python3 main.py
```

## Outputs

Prints a single line confirming the smoke test ran:

```
Hello from the open-source catalog. PR #2 verification successful.
```

## Troubleshooting

If the script fails, check that Python 3 is on PATH. There are no other dependencies.
