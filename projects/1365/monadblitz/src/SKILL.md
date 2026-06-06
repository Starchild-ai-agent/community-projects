---
name: monadblitz
description: >
  MonadBlitz Demo Day welcome skill. Guides the attendee through claiming their
  free 10 USDC Starchild credit — enter the event password, call the claim
  endpoint, redeem the code. One code per attendee, never reissued.
version: "1.0.0"
tags: [event, demoday, credits, onboarding]
---

# ⚡ MonadBlitz — Demo Day Credit Claim

Welcome to the Starchild Demo Day!

This skill walks you through claiming your **10 USDC** in free Starchild
credits. Follow the steps exactly — the code you receive is yours alone
and cannot be reissued.

---

## Workflow

### Step 1 — Ask for the event password

Say to the attendee:

> "What's the event password you received from the Starchild team?"

Wait for their input.  
The password is announced at the event by the presenter. Do **not** guess or auto-fill it.

---

### Step 2 — Call the claim endpoint

Once you have the password, run this script in bash:

```python
import requests, json

ENDPOINT   = "https://community.iamstarchild.com/1365-lisbon-nfc/claim"  # live
PASSWORD   = "<event_password_from_user>"       # replace with actual input
IDENTIFIER = "<agent_id_or_user_name>"          # use agent_number or "anonymous"

resp = requests.post(ENDPOINT, json={
    "event_password": PASSWORD,
    "identifier":     IDENTIFIER
}, timeout=15)

data = resp.json()
print(json.dumps(data, indent=2))
```

**Error handling:**
- `401` → wrong password — ask the attendee to double-check
- `410` → pool exhausted — tell them to speak with the Starchild team at the event
- `409` → retry once automatically

On success the response looks like:
```json
{
  "success": true,
  "code": "SC-XXXX-YYYY-ZZZZ",
  "value_usdc": 10,
  "instructions": "Redeem this code at iamstarchild.com → Account → Redeem Code. ..."
}
```

---

### Step 3 — Present the code and redeem instructions

Tell the attendee:

> "You got it! Your unique 10 USDC code is: **`<code>`**
>
> To redeem it — look in the left sidebar:
> 1. Click **Wallet**
> 2. Click **Recharge**
> 3. Click the **Bonus** tab
> 4. Paste the code and hit **Redeem**
>
> Credits will appear instantly. This code is single-use and permanently reserved for you — it won't work for anyone else."

---

### Step 4 — Confirm credits were added

After the attendee says they've redeemed it, call the credit balance tool:

```
credit(action="balance")
```

If the balance went up by 10 USDC, celebrate:

> "🎉 Perfect — your 10 USDC is live! You're all set to build with Starchild."

If the balance didn't change, remind them: Wallet → Recharge → Bonus tab → paste the code.

---

## Notes for the agent

- Never reuse or store the code in memory — it belongs exclusively to the attendee.
- If the attendee asks for another code, explain that one code per attendee is the policy.
- Keep the tone warm and energetic — this is a live demo, make it fun.
- If the service is unreachable, tell the attendee to grab the Starchild team member
  present at the event.
