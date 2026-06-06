# Deployment & Release Checklist

Complete guide for publishing @infiniteezverse/monskills-ezpath to all distribution channels.

---

## Pre-Deployment Verification

### 1. Code Quality
```bash
cd /tmp/monskills-ezpath

# Clean build
rm -rf dist node_modules
npm install
npm run build

# Verify no errors
echo $?  # Should be 0
```

### 2. Tests
```bash
npm test

# Expected output:
# Test Suites: 1 passed
# Tests: 18 passed
```

### 3. Type Checking
```bash
npx tsc --noEmit

# Should complete with no errors
```

### 4. Package Contents
```bash
# Verify all required files are included
npm pack --dry-run

# Should include:
# - dist/index.js (compiled)
# - dist/index.d.ts (declarations)
# - dist/agents/
# - dist/payments/
# - dist/config/
# - dist/types/
# - README.md
# - LICENSE
# - package.json
```

---

## Step 1: NPM Publishing

### Prerequisites
```bash
# Verify npm login
npm whoami

# If not logged in:
npm login --scope=@infiniteezverse
# Enter username, password, email (2FA if enabled)
```

### Publish to NPM
```bash
# Update version if needed
npm version patch  # 0.1.0 → 0.1.1
# or
npm version minor  # 0.1.0 → 0.2.0
# or manually edit package.json

# Build before publish
npm run build

# Publish
npm publish --access=public

# Verify published
npm view @infiniteezverse/monskills-ezpath

# Should show:
# @infiniteezverse/monskills-ezpath@0.1.0
# published 1 second ago
```

### Test Installation
```bash
# Fresh test in temporary directory
cd /tmp/test-monskills
npm install @infiniteezverse/monskills-ezpath

# Verify it installed
ls node_modules/@infiniteezverse/monskills-ezpath

# Test import
node -e "const pkg = require('@infiniteezverse/monskills-ezpath'); console.log(pkg.skill.name)"
# Should print: ez-path
```

---

## Step 2: MONSKILLS Marketplace Submission

### Create MONSKILLS Manifest
File: `.monskills/manifest.json`

```json
{
  "name": "ez-path",
  "displayName": "EZ-Path DEX Router",
  "version": "0.1.0",
  "description": "Agent skill for querying the best DEX routes across 10 venues simultaneously",
  "author": "infiniteezverse",
  "license": "MIT",
  "repository": "https://github.com/infiniteezverse/monskills-ezpath",
  "homepage": "https://ezpath.myezverse.xyz",
  "keywords": ["dex", "routing", "monad", "base", "trading", "agent-skill"],
  "handlers": {
    "getQuote": "Get a DEX price quote",
    "getPrice": "Quick price lookup",
    "batchQuotes": "Multiple quotes in parallel"
  },
  "supportedChains": ["base", "monad"],
  "installCommand": "npx skills add @infiniteezverse/monskills-ezpath",
  "documentation": "https://github.com/infiniteezverse/monskills-ezpath#readme",
  "marketplaceCategory": "dex-routing"
}
```

### Submit to MONSKILLS
1. Go to https://skills.monad.xyz/ (or MONSKILLS registry)
2. Click "Submit Skill"
3. Fill form:
   - Name: EZ-Path DEX Router
   - Package: @infiniteezverse/monskills-ezpath
   - Category: DEX Routing
   - Description: Races 10 DEX venues for best price
4. Upload manifest
5. Submit for review

### Verification
```bash
# Once approved, verify discoverability
npx skills search ez-path
# Should show skill in results

npx skills info @infiniteezverse/monskills-ezpath
# Should display skill metadata
```

---

## Step 3: GitHub Release

### Create Release Notes
```bash
cd /tmp/monskills-ezpath

# Create release file
cat > RELEASE_NOTES.md << 'EOF'
# Release 0.1.0 - EZ-Path MONSKILLS Plugin

## What's New

- Complete MONSKILLS skill for DEX routing
- Real-time bankroll management for agents
- Arena tournament framework with strategy engine
- X402 EIP-3009 payment settlement
- Monad-optimized for 10,000 TPS

## Features

- `getPrice()` - Quick price lookup
- `getQuote()` - Full quote with venues
- `batchQuotes()` - Parallel multi-pair quoting
- `Agent` - Tournament competition framework
- `QuoteExecutor` - X402 payment handling

## Documentation

- [README](README.md) - Quick start
- [MANIFEST](MANIFEST.md) - Agent discovery
- [MONAD](MONAD.md) - Monad optimization
- [ARENA](ARENA.md) - Agent framework
- [X402](X402_IMPLEMENTATION.md) - Payment implementation

## Installation

```bash
npm install @infiniteezverse/monskills-ezpath
```

## Supported Chains

- ✅ Base (live)
- ✅ Monad (live, optimized)
- 🚧 Arbitrum, Optimism, Polygon (coming soon)

## Tests

- 18 unit tests (all passing)
- Full type safety (TypeScript)
- Zero external dependencies (except axios)

## What's Next

- Multi-chain support
- Agent performance dashboard
- Liquidity aggregation
- MEV protection

---

**Thank you for using EZ-Path! Report issues on GitHub.**
EOF

git add RELEASE_NOTES.md
git commit -m "Add release notes for v0.1.0"
git push origin main
```

### Create GitHub Release
```bash
# Create git tag
git tag -a v0.1.0 -m "EZ-Path MONSKILLS v0.1.0 - Complete plugin"
git push origin v0.1.0

# Create release on GitHub
gh release create v0.1.0 \
  --title "EZ-Path MONSKILLS v0.1.0" \
  --notes-file RELEASE_NOTES.md \
  --draft  # Review before publishing
```

### Verify Release
- Go to https://github.com/infiniteezverse/monskills-ezpath/releases
- Verify v0.1.0 appears
- Verify assets are uploaded (optional .tgz)

---

## Step 4: Ecosystem Announcements

### Twitter/X Announcement
```
🚀 EZ-Path MONSKILLS is LIVE!

The complete DEX routing framework for Monad agents:
✅ 10-venue meta-router
✅ Real-time bankroll management
✅ Arena tournament framework
✅ X402 settlement execution

Install: npm install @infiniteezverse/monskills-ezpath
GitHub: https://github.com/infiniteezverse/monskills-ezpath

Let's build agents! 🤖💰

#Monad #Agents #DeFi
```

### Discord Announcements

**Monad Discord:**
```
🚀 NEW: EZ-Path MONSKILLS Plugin

The complete agent toolkit for DEX routing on Monad is now available!

📦 Install: npm install @infiniteezverse/monskills-ezpath
📖 Docs: https://github.com/infiniteezverse/monskills-ezpath
🎯 Examples: portfolio-valuation.ts, arena-agent-template.ts, x402-payment.ts

Features:
- Get prices from 10 DEX venues
- Real-time bankroll management
- Arena tournament support
- X402 payment settlement

Questions? Check our docs or open an issue on GitHub!
```

**infiniteezverse Discord (if exists):**
```
🎉 Launch: EZ-Path MONSKILLS v0.1.0

We're excited to announce the public launch of our complete DEX routing plugin!

Now available:
- NPM: @infiniteezverse/monskills-ezpath
- MONSKILLS marketplace
- GitHub open source
- Starchild community

Feedback welcome! Join us in building the agent ecosystem.
```

### Blog Post (optional)
```markdown
# Announcing EZ-Path MONSKILLS: DEX Routing for Monad Agents

## Why This Matters

Agents on Monad need real-time DEX pricing. EZ-Path MONSKILLS provides:

1. **10-Venue Meta-Router** - Simultaneous pricing from 0x, Uniswap, Curve, Aerodrome, etc.
2. **Real-Time Valuation** - Bankroll management at sub-2-second latency
3. **Tournament Competition** - Arena-ready with dynamic strategy adjustment
4. **Settlement Execution** - X402 EIP-3009 payments for quote settlement

## Installation

```bash
npm install @infiniteezverse/monskills-ezpath
```

## Quick Example

```typescript
const price = await getPrice('monad', USDC, WETH, '1000000');
console.log(`Price: ${price.price}`);
```

## What's Next

We're planning multi-chain support, agent performance dashboards, and liquidity aggregation. Join us!

---

[Full documentation] | [GitHub] | [npm]
```

---

## Step 5: Monitoring & Support

### Setup Monitoring
```bash
# Monitor npm downloads (daily)
npm stats @infiniteezverse/monskills-ezpath

# Check GitHub stars
curl https://api.github.com/repos/infiniteezverse/monskills-ezpath | jq '.stargazers_count'

# Monitor issues
gh issue list --repo infiniteezverse/monskills-ezpath
```

### Support Channels
- [ ] GitHub Issues enabled
- [ ] Discussions enabled
- [ ] Contributing guidelines added
- [ ] Code of conduct in place
- [ ] Security policy documented

### First Week Checklist
- [ ] Monitor error reports
- [ ] Respond to GitHub issues within 24h
- [ ] Publish week 1 metrics blog post
- [ ] Gather early adopter feedback
- [ ] Fix any critical bugs immediately

---

## Post-Deployment

### Week 1
- Monitor npm install rate
- Check for issues/bugs
- Engage with early adopters
- Publish metrics

### Week 2
- Publish case studies
- Release bug fixes if needed
- Plan Phase 2 features
- Gather feedback

### Month 1
- Release v0.1.1 or v0.2.0
- Publish performance report
- Start multi-chain development
- Plan agent leaderboard

---

## Rollback Plan (if needed)

### Unpublish from NPM
```bash
npm unpublish @infiniteezverse/monskills-ezpath --force
```

### Retract Release
```bash
gh release delete v0.1.0
git tag -d v0.1.0
git push origin --delete v0.1.0
```

### Notify Community
Post on Discord, Twitter, and GitHub explaining issue and timeline.

---

## Success Metrics

**First 48 Hours:**
- [ ] 100+ npm installs
- [ ] 10+ GitHub stars
- [ ] 5+ bug reports (expected)
- [ ] 0 critical issues

**First Week:**
- [ ] 500+ npm installs
- [ ] 50+ GitHub stars
- [ ] 20+ agents integrated
- [ ] <1% error rate

**First Month:**
- [ ] 2,000+ npm installs
- [ ] 200+ GitHub stars
- [ ] 100+ agents using skill
- [ ] <0.1% error rate

---

## Launch Commands

```bash
# Final build and test
npm run build && npm test

# Check package
npm pack --dry-run

# Publish to npm
npm publish --access=public

# Create GitHub release
git tag v0.1.0
git push origin v0.1.0
gh release create v0.1.0

# Announce
# - Twitter
# - Discord
# - Blog (optional)
```

---

**Ready to launch? Follow this checklist step by step. Questions? Check GitHub discussions.**

Good luck! 🚀
