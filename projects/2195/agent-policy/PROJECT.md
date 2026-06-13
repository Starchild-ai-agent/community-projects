# agent-policy

A signing policy engine for AI-driven DeFi bots. Built from operating a live
NATGAS market-maker on Orderly Network — the enforcement layer that sits
between an agent's decisions and actual key usage.

## What

Every action an agent proposes goes through `PolicyEngine.evaluate()` before
any signing call. Returns one of three verdicts:

- **ALLOW** — execute immediately, no human needed
- **ESCALATE** — push to Telegram with ✅/❌ buttons, block until answered or timeout
- **BLOCK** — raise `PolicyViolation`, action never reaches the exchange

Policy is declared in a YAML file — not in code. Swap the YAML, change the
behavior. No redeploy required.

**Circuit breakers** trip automatically on:
- Daily realized loss exceeding a threshold
- Equity drawdown from 24h high
- N consecutive losing trades
- Margin ratio approaching liquidation

State persists across restarts via a local JSON file.

## Required env

None for the core engine.

For `TelegramNotifier` (ESCALATE approval loop):
- `POLICY_TG_BOT_TOKEN` — BotFather token
- `POLICY_TG_CHAT_ID` — your Telegram user or chat ID

## How to start

```bash
pip install pyyaml requests
```

Drop into any bot that uses `OrderlyClient`:

```python
from src.policy import PolicyEngine
from src.notifier import TelegramNotifier
from src.policy_client import PolicyClient

engine   = PolicyEngine.from_yaml("src/policy_natgas.yaml")
notifier = TelegramNotifier()          # reads env vars
client   = PolicyClient(raw_client, engine, notifier=notifier)

# use client exactly as before — policy enforced transparently
client.place_order({"symbol": "PERP_NATGAS_USDC", "side": "BUY",
                    "order_type": "LIMIT", "price": 3.15, "quantity": 640})
```

Dry-run mode (no exchange calls, logs decisions only):

```python
client = PolicyClient(raw_client, engine, notifier=notifier, dry_run=True)
```

## Outputs

- `policy_state.json` — circuit breaker state (auto-created, survives restarts)

## Troubleshooting

- **`PolicyViolation` on every order** — check `circuit_breakers` in your YAML;
  a tripped breaker blocks all new orders. Reset by fixing the underlying
  condition and deleting/editing `policy_state.json`.
- **ESCALATE never resolves** — verify `POLICY_TG_BOT_TOKEN` and
  `POLICY_TG_CHAT_ID` are set; check that the bot has been started with
  `/start` in your chat. Default timeout is 5 minutes → DENY.
- **Unknown action → ESCALATE** — this is the fail-safe default. Add the
  action to `autonomous` in your YAML if it should be unblocked.
