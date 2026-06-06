# MonadBlitz — Demo Day Credit Claim Skill

## What

A Starchild skill for the MonadBlitz Demo Day. When installed, it walks the attendee through:

1. Entering the event password announced by the presenter
2. Calling the live claim endpoint to receive a unique 10 USDC top-up code
3. Redeeming the code via Wallet → Recharge → Bonus tab
4. Confirming the credits were added to their account

Each code is single-use and permanently reserved the moment it's issued — no code is ever given to two people.

## Required env

None — the claim endpoint is public (password-gated).

## How to start

Install the skill in any Starchild agent, then let the agent guide the attendee through the workflow automatically.

## Outputs

A unique `SC-XXXX-XXXX-XXXX` top-up code worth 10 USDC, redeemable in the Starchild wallet.

## Troubleshooting

- **Wrong password (401):** Ask the Starchild team at the event for the correct password.
- **Pool empty (410):** All codes have been claimed — speak to the Starchild team directly.
- **Credits not showing:** Go to Wallet → Recharge → Bonus tab and paste the code there.
