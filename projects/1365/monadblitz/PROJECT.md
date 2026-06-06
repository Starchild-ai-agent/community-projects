# ⚡ MonadBlitz — Demo Day Credit Claim

## What

An event onboarding skill for the MonadBlitz Demo Day. Guides attendees through claiming their free **10 USDC** in Starchild credits using an event password. One code per attendee, non-reissuable.

## Required env

None — no API keys needed. The claim endpoint is public but password-protected.

## How to start

Install the skill in your Starchild agent:

```bash
npx skills@latest add monadblitz --yes
```

Then trigger the workflow by asking your agent:

> "Help me claim my MonadBlitz credits"

The agent will ask for the event password, call the claim endpoint, and walk you through redeeming the code.

## Outputs

- A unique `SC-XXXX-YYYY-ZZZZ` credit code worth 10 USDC
- Instructions to redeem via Wallet → Recharge → Bonus tab

## Troubleshooting

| Issue | Fix |
|---|---|
| `401` from claim endpoint | Wrong event password — double-check with the presenter |
| `410` from claim endpoint | Code pool exhausted — speak to the Starchild team at the event |
| Code doesn't work on redeem | Make sure to paste it in the **Bonus** tab, not the main Recharge input |
| Credits didn't appear | Wait 10–15 seconds, then refresh the Wallet page |
