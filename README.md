# Starchild Community Projects

Fork-and-run code projects shared by the Starchild community.

Each project here is **runnable code** — task scripts, dashboards, services, or one-off scripts. Fork one to install it directly into your Starchild workspace and start using it.

## Project Types

| Type | What it is | How it runs |
|------|-----------|-------------|
| `task` | Scheduled / cron job | Auto-registered as a paused job; you activate it |
| `preview` | Web dashboard or app | Auto-served under `/preview/{id}/` |
| `service` | Long-running background process | Started via `bash background=true` |
| `script` | One-shot script | Single command |

## Repository Layout

```
projects/
├── tasks/{user_id}/{slug}/{version}/
├── previews/{user_id}/{slug}/{version}/
├── services/{user_id}/{slug}/{version}/
└── scripts/{user_id}/{slug}/{version}/
index.json   # global searchable catalog (auto-maintained by gateway)
templates/   # blank scaffolds for each type
docs/        # project.yaml schema + PROJECT.md template
```

Every published project version has the same files inside its `{version}/` folder:

```
project.yaml      # metadata (type, version, env_required, sc_proxy usage)
PROJECT.md        # what / required env / how to start / outputs / troubleshooting
.env.example      # all environment variables (filled with placeholder values)
.gitignore        # secrets blacklist
src/              # code
```

## Forking a Project

In a Starchild chat:

```
fork community-projects/<user>/<slug>
```

The agent will:

1. Pull the latest version (or pin to `@1.2.0` if requested)
2. Show you what env vars are needed
3. Collect them via secure input (one popup, all at once)
4. Install per-type:
   - `task` → register as paused, you confirm to activate
   - `preview` → serve and give you the URL
   - `service` → confirm and start in background
   - `script` → show you the run command

## Publishing Your Own

In a Starchild chat:

```
publish my project at output/projects/<slug>
```

The agent will:

1. Validate `project.yaml` and `PROJECT.md`
2. Scan for accidental secrets in `src/`
3. Bump version (you choose patch / minor / major)
4. Push to this repo via the gateway

See `docs/project-yaml-schema.md` and `docs/PROJECT-md-template.md` for what these files look like.

## Index

`index.json` is the global catalog, auto-maintained by `sc-community-gateway` whenever a project is published or unpublished. Format:

```json
[
  {
    "type": "task",
    "user_id": "2004",
    "slug": "btc-funding-monitor",
    "latest_version": "1.2.0",
    "description": "Monitor BTC funding rate, alert on extremes",
    "tags": ["crypto", "monitoring"],
    "author": "leon",
    "updated_at": "2026-05-12T10:30:00Z"
  }
]
```

Search is exposed at `https://sc-community-gateway.fly.dev/api/code-projects/list`.

## Safety

- All publishes go through gateway-side secret scanning
- `.env`, `*.key`, `*.pem`, `secrets/` are hard-blocked
- Fork never auto-runs `setup.sh` — you confirm first
- License must be specified per-project (defaults MIT)

## Differences from Skills

Skills (separate ecosystem at [skills.sh](https://skills.sh) and `Starchild-ai-agent/official-skills`) are **workflow instructions** — markdown documents that teach the agent how to use tools.

Projects (this repo) are **runnable code** — fork, configure env, start, get output.

You probably want a skill if you're documenting a workflow. You probably want a project if you've built something you want others to deploy.
