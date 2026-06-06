# MONSKILLS EZ-Path v0.1.1 — Launch Execution Guide

**Complete checklist to go live with HTTP API + full marketing launch.**

---

## 🎯 Phase 1: Vercel Deployment (15 minutes)

### Step 1: Install Vercel CLI

```bash
npm i -g vercel
```

### Step 2: Build locally first

```bash
cd /tmp/monskills-ezpath
npm run build
```

Expected output:
```
✅ src/index.ts
✅ src/api-server.ts
✅ src/agents/...
✅ dist/ created
```

### Step 3: Deploy to Vercel

```bash
vercel --prod --name monskills-ezpath
```

Follow the prompts:
```
? Set up and deploy "./monskills-ezpath"? [Y/n] y
? Which scope do you want to deploy to? [select your account]
? Link to existing project? [y/N] n
? What's your project's name? monskills-ezpath
? In which directory is your code? [.] .
? Want to modify these settings? [y/N] n
```

### Step 4: Get your API URL

Vercel will output:

```
✅ Production: https://monskills-ezpath.vercel.app
```

**Save this URL** — you'll use it everywhere.

### Step 5: Test the live API

```bash
curl https://monskills-ezpath.vercel.app/v1/health
```

Expected response:
```json
{
  "status": "healthy",
  "venues": {
    "healthy": ["0x", "Aerodrome", "Uniswap V3", ...],
    "degraded": []
  },
  "timestamp": "2026-06-06T16:00:00Z"
}
```

✅ **API is live!**

---

## 🎯 Phase 2: Update All Materials (10 minutes)

### Update URLs in Files

Replace these placeholders:
- `https://api.monskills-ezpath.dev` → `https://monskills-ezpath.vercel.app`
- `api.monskills-ezpath.dev` → `monskills-ezpath.vercel.app`

**Files to update:**

```bash
# Update agent.json
sed -i 's|https://api\.monskills-ezpath\.dev|https://monskills-ezpath.vercel.app|g' .well-known/agent.json

# Update agent.json (alternate endpoint references)
sed -i 's|api\.monskills-ezpath\.dev|monskills-ezpath.vercel.app|g' .well-known/agent.json AGENT_CALLS.md ERROR_CODES.md

# Update README
sed -i 's|api\.monskills-ezpath\.dev|monskills-ezpath.vercel.app|g' README.md
```

Or manually update in these files:
- `.well-known/agent.json` (endpoints section)
- `AGENT_CALLS.md` (all curl examples)
- `ERROR_CODES.md` (references)
- `README.md` (API section)

### Commit changes

```bash
git add -A
git commit -m "Deploy: API live on Vercel at https://monskills-ezpath.vercel.app

- Vercel deployment successful
- All endpoints tested and responding
- Updated agent.json with production API URL
- Ready for full launch"

git push origin main
```

---

## 🎯 Phase 3: Twitter Launch Burst (15 minutes)

### Tweet 1: API Live Announcement

```
🎉 MONSKILLS EZ-Path HTTP API is LIVE

Agents can now call real DEX quotes in 30 seconds. No npm install. No setup.

POST https://monskills-ezpath.vercel.app/v1/quote

Example:
```bash
curl -X POST https://monskills-ezpath.vercel.app/v1/quote \
  -H "Content-Type: application/json" \
  -d '{
    "chain": "monad",
    "sellToken": "0x4200000000000000000000000000000000000006",
    "buyToken": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
    "sellAmount": "1000000000000000000"
  }'
```

10-venue race. 177ms execution. Live on Monad & Base.

npm: https://www.npmjs.com/package/@infiniteezverse/monskills-ezpath
GitHub: https://github.com/infiniteezverse/monskills-ezpath
API: https://monskills-ezpath.vercel.app

/1
```

**Wait 30 minutes**

### Tweet 2: Three Adoption Paths

```
MONSKILLS EZ-Path: Pick your path 🚀

🌐 HTTP API
30-second integration. No setup.
POST https://monskills-ezpath.vercel.app/v1/quote

📦 npm Package
Full TypeScript integration + type safety
npm install @infiniteezverse/monskills-ezpath

🔍 Auto-Discovery
Agents find you via .well-known/agent.json
OpenAPI schema included

All three go live today.

Docs: https://github.com/infiniteezverse/monskills-ezpath/blob/main/AGENT_CALLS.md

/2
```

**Wait 30 minutes**

### Tweet 3: Error Codes + Retry Logic

```
Building for production? We handle the hard parts.

Machine-friendly error codes:
✅ UNSUPPORTED_PAIR
✅ INSUFFICIENT_LIQUIDITY
✅ QUOTE_TIMEOUT
✅ RATE_LIMITED
✅ UPSTREAM_ERROR

Auto-retry with exponential backoff included.
Rate limits: 120 req/min (configurable).

Error handling guide: https://github.com/infiniteezverse/monskills-ezpath/blob/main/ERROR_CODES.md

/3
```

**Wait 30 minutes**

### Tweet 4: CTA + Links

```
MONSKILLS EZ-Path v0.1.1 is production-ready.

Try it now:

API endpoint:
https://monskills-ezpath.vercel.app

Integration examples (3 languages):
https://github.com/infiniteezverse/monskills-ezpath/blob/main/AGENT_CALLS.md

Error codes + retry patterns:
https://github.com/infiniteezverse/monskills-ezpath/blob/main/ERROR_CODES.md

Deploy guide (Vercel, Railway, Cloud Run, Docker):
https://github.com/infiniteezverse/monskills-ezpath/blob/main/API_DEPLOYMENT.md

npm: https://www.npmjs.com/package/@infiniteezverse/monskills-ezpath
GitHub: https://github.com/infiniteezverse/monskills-ezpath

Ship your agent today.

/4
```

---

## 🎯 Phase 4: Discord Posts (5 minutes)

### Monad Discord

```
🎉 MONSKILLS EZ-Path HTTP API is LIVE

Call real 10-venue DEX routing in 30 seconds:

```bash
curl -X POST https://monskills-ezpath.vercel.app/v1/quote \
  -H "Content-Type: application/json" \
  -d '{
    "chain": "monad",
    "sellToken": "0x4200000000000000000000000000000000000006",
    "buyToken": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
    "sellAmount": "1000000000000000000"
  }'
```

**Three integration paths:**
1️⃣ HTTP API (30-second setup)
2️⃣ npm package (full TypeScript support)
3️⃣ Auto-discovery (.well-known/agent.json)

**Docs & Examples:**
- API Integration: https://github.com/infiniteezverse/monskills-ezpath/blob/main/AGENT_CALLS.md
- Error Handling: https://github.com/infiniteezverse/monskills-ezpath/blob/main/ERROR_CODES.md
- Deployment: https://github.com/infiniteezverse/monskills-ezpath/blob/main/API_DEPLOYMENT.md

**Links:**
- npm: https://www.npmjs.com/package/@infiniteezverse/monskills-ezpath
- GitHub: https://github.com/infiniteezverse/monskills-ezpath
- Live API: https://monskills-ezpath.vercel.app

v0.1.1 | Production-ready for agents
```

### infiniteezverse Discord

```
🚀 MONSKILLS EZ-Path v0.1.1 — API Live on Vercel

Complete agent-facing HTTP API deployed and tested:

✅ Live API: https://monskills-ezpath.vercel.app
✅ Health check: https://monskills-ezpath.vercel.app/v1/health
✅ 177ms execution (proven on Monad testnet)
✅ Rate limiting: 120 req/min
✅ 3 integration paths live

**What ships today:**
- HTTP API (5 endpoints)
- npm package (TypeScript)
- Auto-discovery (agent registries)
- Complete documentation
- Error codes + retry logic
- 5+ deployment options

**Get started in 30 seconds:**
```bash
curl -X POST https://monskills-ezpath.vercel.app/v1/quote \
  -H "Content-Type: application/json" \
  -d '{"chain":"monad","sellToken":"0x4200000000000000000000000000000000000006","buyToken":"0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913","sellAmount":"1000000000000000000"}'
```

**Links:**
- npm: https://www.npmjs.com/package/@infiniteezverse/monskills-ezpath
- GitHub: https://github.com/infiniteezverse/monskills-ezpath
- API: https://monskills-ezpath.vercel.app
- Docs: https://github.com/infiniteezverse/monskills-ezpath#readme

This is it. We're live.
```

---

## 🎯 Phase 5: Registry Submissions (10 minutes)

### MONSKILLS Marketplace

Submit at: https://skills.devnads.com

**Title:** MONSKILLS EZ-Path — 10-Venue DEX Router

**Short Description:**
Agent-ready DEX routing API + npm package. 177ms execution. Live on Monad & Base.

**Description:**
```
MONSKILLS EZ-Path gives agents instant access to multi-venue DEX routing.

HTTP API: Zero setup, 30-second integration
npm Package: Full TypeScript support
Auto-Discovery: Agent registries can find you automatically

Three venues to query:
- 0x, Aerodrome, Uniswap V3
- Curve, Balancer, Uniswap V2
- ParaSwap, 1Inch, CoW, Synthetix

Live API: https://monskills-ezpath.vercel.app
npm: npm install @infiniteezverse/monskills-ezpath
GitHub: https://github.com/infiniteezverse/monskills-ezpath

Docs: https://github.com/infiniteezverse/monskills-ezpath
Error Codes: https://github.com/infiniteezverse/monskills-ezpath/blob/main/ERROR_CODES.md
Examples: https://github.com/infiniteezverse/monskills-ezpath/blob/main/AGENT_CALLS.md

Production-ready. MIT licensed.
```

### AgentX Registry

Submit at: https://agentic.market (or relevant agent registry)

Same content as MONSKILLS + add:

```
API Endpoint: https://monskills-ezpath.vercel.app
OpenAPI Schema: https://github.com/infiniteezverse/monskills-ezpath/blob/main/.well-known/openapi.yaml
Agent Manifest: https://monskills-ezpath.vercel.app/.well-known/agent.json
```

---

## ✅ Complete Launch Checklist

```
DEPLOYMENT:
☐ Build locally: npm run build
☐ Deploy to Vercel: vercel --prod
☐ Get live API URL
☐ Test health endpoint
☐ Verify all 5 endpoints responding

UPDATES:
☐ Update .well-known/agent.json with live API URL
☐ Update AGENT_CALLS.md with live API URL
☐ Update ERROR_CODES.md with live API URL
☐ Commit and push to GitHub

TWITTER (15+ min spacing):
☐ Tweet 1: API Live Announcement + curl example
☐ Tweet 2: Three Adoption Paths
☐ Tweet 3: Error Codes + Retry Logic
☐ Tweet 4: CTA + All Links

DISCORD:
☐ Monad Discord post
☐ infiniteezverse Discord post

REGISTRY SUBMISSIONS:
☐ MONSKILLS Marketplace
☐ AgentX Registry
☐ Any other agent marketplaces

MONITORING:
☐ Watch GitHub stars
☐ Monitor API health
☐ Track npm installs
☐ Respond to issues
```

---

## 📊 Expected Impact

**After Vercel deployment:**
- ✅ Zero-friction agent adoption
- ✅ 30-second time-to-integration
- ✅ 10-100x faster than npm-only

**After social posts:**
- 📈 5-10K impressions per tweet
- 📈 100-200 link clicks
- 📈 50-100 npm installs (day 1)
- 📈 10-20 GitHub stars
- 📈 3-5 early integrations

**After registry submissions:**
- 🤖 Agents auto-discover via registries
- 🤖 Higher visibility in agent marketplaces
- 🤖 More organic integrations

---

## 🚀 Your Command Now

**You are 15 minutes from live.**

```bash
# 1. Build
npm run build

# 2. Deploy
vercel --prod --name monskills-ezpath

# 3. Test
curl https://monskills-ezpath.vercel.app/v1/health

# 4. Update & commit
git add -A && git commit -m "API LIVE on Vercel" && git push origin main

# 5. Post Twitter thread (4 tweets, 30 min apart)
# 6. Post Discord (Monad + infiniteezverse)
# 7. Submit to registries
```

---

**Ready to deploy?** 🚀
