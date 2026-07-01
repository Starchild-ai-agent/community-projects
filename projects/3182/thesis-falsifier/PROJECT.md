# Thesis Falsifier

## What

A Starchild skill that takes any investment thesis ("I should buy X because Y") and systematically tries to **destroy it before you act**.

Most investment theses are unfalsifiable narratives. "AI will drive growth" can never be wrong because it's vague. This skill's job: make the thesis falsifiable, then try to kill it.

**A thesis that survives an honest assassination attempt is worth acting on. One that doesn't survive was confirmation bias dressed up as analysis.**

### Six-step workflow

1. **证伪化改写** — break the thesis into 3 testable claims: Claim A (is Y actually true?), Claim B (is Y already priced in?), Claim C (will Y persist long enough to matter?). Identify the load-bearing claim.
2. **最弱环节** — of A/B/C, find the most uncertain AND most checkable. That's the attack surface. A thesis is only as strong as its weakest load-bearing claim.
3. **主动猎杀** — run `web_search` with adversarial queries (`"[X] bear case"`, `"[Y] wrong"`, `"[X] overvalued"`). Report findings honestly. Finding nothing negative is itself a warning.
4. **钢铁人对方** — write the strongest 3-sentence bear case. NOT a strawman — the version a smart bear would sign their name to. If it doesn't scare you a little, rebuild it.
5. **代价量化** — max realistic downside, can you survive being wrong at current sizing, define the invalidation signal upfront.
6. **证伪后信念** — re-rate confidence 1-10 after all the above. Dropped ≥3 points → confirmation bias, don't act. Dropped 1-2 → real risks found, proceed with eyes open. Held or rose → robust thesis worth real size.

### Asset-agnostic

Works on stocks, crypto, macro bets, career decisions — anything with an "I should do X because Y" structure. Adapt vocabulary per asset class (crypto has no earnings → Claim A becomes on-chain metrics / adoption / tokenomics).

## Required env

None. The skill is pure markdown — no API keys, no external services beyond the agent's built-in `web_search` tool.

## How to start

This is a Starchild skill, not a standalone app. Two ways to use it:

### Option A — install via Starchild skill registry (recommended)

```
npx skills add @3182/thesis-falsifier@1.0.0
```

Then in any Starchild agent session, the skill is auto-loaded and the agent will follow the workflow when you present a thesis.

### Option B — manual install

Copy `skills/thesis-falsifier/SKILL.md` into your agent's `skills/thesis-falsifier/` directory. Refresh the skill cache. The workflow runs inside any agent that supports `web_search`.

### Running a falsification session

Just tell your agent something like:

> "I'm thinking of buying X because Y. Run the thesis falsifier on it."

The agent will execute the six-step workflow and output a structured 证伪报告.

## Outputs

A structured report in this format:

```
## 证伪报告: [thesis in one line]

### 证伪化改写
- Claim A (事实): [claim] | 置信度: __/10
- Claim B (未定价): [claim] | 置信度: __/10
- Claim C (持续性): [claim] | 置信度: __/10
- 承重墙: Claim [A/B/C]

### 最弱环节
[which claim to attack + why]

### 猎杀发现
- [counter-evidence 1, with source]
- [counter-evidence 2, with source]
- [counter-evidence 3, or "未找到显著反证"]

### 钢铁人对方
[strongest bear case in 3 sentences]

### 代价量化
- 最大现实下行: [price/level + reasoning]
- 当前仓位是否可承受: [yes/no]
- 无效化信号: [what proves thesis wrong]

### 证伪后信念
初始信念: __/10 → 证伪后: __/10
结论: [act with size / act normal / act small / don't act / rework]

### 一句话
[the honest bottom line]
```

## Troubleshooting

| Symptom | Fix |
|---|---|
| Agent doesn't run the workflow | Make sure the skill is installed and the cache is refreshed. Verify `skills/thesis-falsifier/SKILL.md` exists. |
| Step 3 (猎杀) feels weak | The agent may not be running adversarial web searches. Explicitly prompt: "run web_search with bear-case queries before concluding." |
| Bear case is too easy to knock down | That's a strawman, not a steel-man. Prompt the agent: "rebuild the bear case so it's uncomfortable — the version a smart short seller would sign." |
| Output is vague | The input thesis was probably vague. First force specification: good for WHAT, over WHAT horizon, vs WHAT alternative? Vague theses can't be falsified — that's the point. |

## License

MIT — fork it, adapt it, republish your own version. The methodology is meant to be used.
