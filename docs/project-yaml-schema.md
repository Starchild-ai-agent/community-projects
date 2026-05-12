# project.yaml Schema

Required file in every project root. Describes the project to the gateway and the fork-side installer.

## Required fields

```yaml
name: btc-funding-monitor          # slug (lowercase, hyphen-separated)
version: 1.2.0                     # semver, must increment on republish
type: task                         # task | preview | service | script
description: "Monitor BTC funding rate, alert on extremes"
author: "user-2004"                # publisher's user_id (auto-filled)
license: MIT                       # SPDX identifier
entry: src/run.py                  # main file path, relative to project root
```

## Type-specific fields

`type: task`

```yaml
schedule: "*/15 * * * *"           # cron expression (UTC)
```

`type: preview` or `type: service`

```yaml
port: 5173                         # port the service listens on
```

## Runtime

```yaml
runtime:
  python: ">=3.10"                 # or node, bash, etc.
  setup: setup.sh                  # optional, runs once on install (user confirms)
```

## Environment variables

```yaml
env_required:
  - COINGLASS_API_KEY              # missing → fork blocks until provided
env_optional:
  - SLACK_WEBHOOK_URL              # missing → warn but proceed
```

Each name must match a key in `.env.example`.

## sc-proxy usage (transparency)

```yaml
sc_proxy:
  apis: [coinglass, coingecko]     # paid APIs the project will hit
  estimated_credits_per_run: 2     # rough cost estimate per invocation
```

## Discovery

```yaml
tags: [crypto, monitoring, defi]   # for search and filtering
```

## Full example

```yaml
name: btc-funding-monitor
version: 1.2.0
type: task
description: "Alert when BTC funding rate goes below -0.05% on any major exchange"
author: "user-2004"
license: MIT
entry: src/run.py

schedule: "*/15 * * * *"

runtime:
  python: ">=3.10"

env_required:
  - COINGLASS_API_KEY
env_optional:
  - TG_CHAT_ID

sc_proxy:
  apis: [coinglass]
  estimated_credits_per_run: 2

tags: [crypto, funding, monitoring]
```

## Validation

Gateway rejects on publish if:

- `name` doesn't match folder slug
- `version` <= already-published latest version
- `type` not in allowed set
- `entry` path doesn't exist in tarball
- env names in `env_required` not present in `.env.example`
- license is empty
- `setup.sh` is referenced but not present
