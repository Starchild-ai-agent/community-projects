# PROJECT.md Template

Required file. Forked users (and their agents) read this to understand what the project does and how to run it. Strict 4-section structure.

```markdown
# {Project Name}

## What

One sentence describing what this does. Don't oversell. State the actual behavior.

## Required env

- `VAR_NAME`: where to get it (URL or "from your account at X"), why it's needed
- `ANOTHER_VAR`: same format

If `env_optional` exists in project.yaml, list those here too with "(optional)" suffix and the default fallback behavior.

## How to start

For task: "Auto-registered as paused. Activate via `scheduled_task(action='activate', job_id=...)`."
For preview: "Auto-served. Open the preview link the agent gave you."
For service: "Run `bash python src/server.py background=true`."
For script: "Run `bash python src/main.py`."

If there are extra setup steps (DB migration, model download, etc.), put them here.

## Outputs / Behavior

What does success look like? What gets pushed where? What files get created? What's the cadence?

## Troubleshooting

Top 3 things that go wrong. Not exhaustive — just the common ones.

- "X happens" → check Y
- "Z error" → likely cause and fix
```

## Strictness

The validator checks for exactly these section headers. Extra sections (e.g. `## License`, `## Credits`) are allowed below them. The 4 required ones cannot be renamed or omitted.
