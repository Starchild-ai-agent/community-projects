---
name: thesis-falsifier
version: 1.0.0
description: 逆向证伪器 — take any investment thesis ("I should buy X because Y") and systematically try to destroy it before you act. Converts narrative conviction into falsifiable claims, hunts for counter-evidence via web search, steel-mans the bear case, and quantifies survival if wrong. Use BEFORE acting on any thesis you feel strongly about. Works on stocks, crypto, macro bets, any decision with a thesis.
author: agentway
tags: [investing, decision-making, critical-thinking, risk-management, thesis, falsification, stocks, crypto]
---

# Thesis Falsifier

## When to use
- You have a thesis you're about to act on (buy / sell / hold / size up)
- You feel conviction — that's the signal to run this, NOT skip it
- Works on any asset: stocks, crypto, macro bets, career decisions, anything with a "because"

## The problem it solves
Most investment theses are unfalsifiable narratives. "AI will drive growth" can never be wrong because it's vague. The skill's job: make the thesis falsifiable, then try to kill it.

**A thesis that survives an honest assassination attempt is worth acting on. One that doesn't survive was confirmation bias dressed up as analysis.**

## Workflow

### Step 1 — 证伪化改写 (Make it falsifiable)
Take the user's thesis and break it into 3 testable claims:
- **Claim A (事实)**: Is Y actually true? (verifiable now — earnings, data, shipping product)
- **Claim B (未定价)**: Is Y already priced in? (has the stock already moved on this?)
- **Claim C (持续性)**: Will Y persist long enough to matter for the position's horizon?

Label which claim is **load-bearing** — the one where if it's wrong, the whole thesis collapses. Most theses have one. Find it.

### Step 2 — 最弱环节 (Weakest link)
Of A/B/C, which is most uncertain AND most checkable? That's the attack surface. Don't attack the strong claims — attack the weak one. A thesis is only as strong as its weakest load-bearing claim.

### Step 3 — 主动猎杀 (Active counter-evidence hunt)
Run `web_search` with adversarial queries. This step is mandatory — without it the skill is just journaling.
- `"[X] bear case"` / `"[X] short thesis"` / `"[X] overvalued"`
- `"[Y thesis] wrong"` / `"[Y] disappointing"` / `"[Y] delayed"`
- Negative earnings surprises, regulatory risk, competitive threats
- Smart investors who publicly disagree

Report what you find honestly. **If you find nothing negative, that's itself a warning** — either you didn't look hard enough, or the crowd hasn't noticed yet (which could be opportunity OR delusion — you don't know which without more work).

### Step 4 — 钢铁人对方 (Steel-man the bear)
Write the strongest 3-sentence version of the opposite thesis. NOT a strawman — the version a smart bear would sign their name to. If your bear case is easy to knock down, you built a strawman. Rebuild it until it scares you a little.

### Step 5 — 代价量化 (Survival check)
If the thesis is wrong:
- What's the max realistic downside? (entry vs invalidation level — a price or event)
- Does current position sizing let you survive being wrong?
- **"Can I be wrong and still be in the game?"** If no → your size is wrong, not your thesis. Fix size first.
- Define the invalidation signal upfront: what price/event proves the thesis wrong and forces exit?

### Step 6 — 证伪后信念 (Post-falsification confidence)
Re-rate confidence 1-10 AFTER all the above. Compare to the user's initial conviction.
- **Dropped ≥3 points** → thesis was built on confirmation bias. Don't act, or size small and keep hunting.
- **Dropped 1-2** → thesis is decent but you found real risks. Proceed with eyes open, size normal.
- **Held or rose** → thesis is robust. This is the rare thesis worth backing with real size.

## Output format

```
## 证伪报告: [thesis in one line]

### 证伪化改写
- Claim A (事实): [claim] | 置信度: __/10
- Claim B (未定价): [claim] | 置信度: __/10
- Claim C (持续性): [claim] | 置信度: __/10
- 承重墙: Claim [A/B/C]

### 最弱环节
[which claim to attack + why it's the weak one]

### 猎杀发现
- [counter-evidence 1, with source]
- [counter-evidence 2, with source]
- [counter-evidence 3, or "未找到显著反证 — 注意: 可能是机会也可能是自欺"]

### 钢铁人对方
[strongest bear case in 3 sentences — the version that scares you]

### 代价量化
- 最大现实下行: [price/level + reasoning]
- 当前仓位是否可承受: [yes/no + reasoning]
- 无效化信号: [what price/event proves thesis wrong]

### 证伪后信念
初始信念: __/10 → 证伪后: __/10
变化: [rose / held / dropped N]
结论: [act with size / act normal / act small / don't act / rework thesis]

### 一句话
[the honest bottom line — would you tell your best friend to make this bet?]
```

## Rules
- **Never skip Step 3.** The web_search is the whole point. Without it you're just talking to yourself.
- **No strawmen in Step 4.** A bear case you can easily knock down is worthless. Build the bear case that makes you uncomfortable. If you're not slightly uncomfortable, rebuild it.
- **The goal is NOT to kill the thesis.** The goal is to know whether it survives. A killed thesis is a SUCCESS (saved you money). A surviving thesis is a SUCCESS (now you can act with real conviction, not narrative conviction). Both outcomes win.
- **Tone: honest friend, not devil's advocate.** Devil's advocates are performative and annoying. Be the friend who actually doesn't want you to lose money — direct, specific, no posturing.
- **Vague thesis handling**: If user gives a vague thesis ("X is good", "should I buy X"), first force specification: good for WHAT, over WHAT horizon, vs WHAT alternative? Vague theses can't be falsified — that's the point. Make them concrete before running the workflow.
- **Asset-agnostic**: works on stocks, crypto, macro, career, any "I should do X because Y". Adapt the vocabulary (crypto has no earnings → Claim A becomes on-chain metrics / adoption / tokenomics).

## Example queries to run in Step 3
- `"[ticker] bear case 2026"`
- `"[ticker] short thesis"`
- `"[ticker] overvalued"`
- `"[thesis keyword] wrong" / "disappointing" / "delayed" / "hype"`
- `"[ticker] risks" / "regulatory" / "competition"`
- `"[sector] bubble" / "[sector] peak"`
