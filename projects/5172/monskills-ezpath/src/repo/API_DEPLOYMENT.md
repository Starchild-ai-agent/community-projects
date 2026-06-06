# API Server Deployment Guide

**Host the agent-facing HTTP API for MONSKILLS EZ-Path.**

---

## 🚀 Quick Start (Local Development)

### 1. Install dependencies

```bash
npm install express express-rate-limit @types/express ts-node
```

### 2. Start development server

```bash
npm run api:dev
```

Expected output:

```
╔════════════════════════════════════════╗
║  MONSKILLS EZ-Path API Server v0.1.1  ║
╚════════════════════════════════════════╝

🚀 Server running on http://localhost:3000
📍 Endpoints:
   POST   /v1/quote              Get DEX quote
   POST   /v1/quote/batch        Batch quotes
   GET    /v1/health             Health check
   GET    /v1/chains             Supported chains
   GET    /v1/venues             Supported venues

📚 Docs: https://github.com/infiniteezverse/monskills-ezpath
💬 Issues: https://github.com/infiniteezverse/monskills-ezpath/issues
```

### 3. Test the API

```bash
curl http://localhost:3000/v1/health
```

---

## 📦 Build for Production

```bash
npm run build
npm run api:start
```

---

## ☁️ Deploy to Vercel

### Option 1: Vercel CLI

```bash
# Install Vercel CLI
npm i -g vercel

# Deploy
vercel --name monskills-ezpath
```

### Option 2: GitHub + Vercel (Recommended)

1. **Create `vercel.json`:**

```json
{
  "version": 2,
  "builds": [
    {
      "src": "dist/api-server.js",
      "use": "@vercel/node"
    }
  ],
  "routes": [
    {
      "src": "/(.*)",
      "dest": "dist/api-server.js"
    }
  ],
  "env": {
    "RATE_LIMIT_PER_MINUTE": "120"
  }
}
```

2. **Push to GitHub:**

```bash
git add vercel.json
git commit -m "Add Vercel deployment config"
git push origin main
```

3. **Connect GitHub to Vercel:**
   - Go to vercel.com
   - Click "New Project"
   - Import repository: `infiniteezverse/monskills-ezpath`
   - Deploy

**Result:** `https://monskills-ezpath.vercel.app`

---

## 🚂 Deploy to Railway

### 1. Create `railway.json`

```json
{
  "$schema": "https://railway.app/railway.schema.json",
  "build": {
    "builder": "nixpacks"
  },
  "deploy": {
    "startCommand": "npm run api:start",
    "restartPolicyMaxRetries": 5
  }
}
```

### 2. Install Railway CLI

```bash
npm i -g @railway/cli
```

### 3. Deploy

```bash
railway login
railway init
railway up
```

**Result:** `https://<project>.railway.app`

---

## 🐳 Deploy to Cloud Run (Google Cloud)

### 1. Create Dockerfile

```dockerfile
FROM node:18-alpine

WORKDIR /app

COPY package*.json ./
RUN npm ci --only=production && npm run build

COPY dist ./dist

EXPOSE 3000
ENV PORT=3000

CMD ["npm", "run", "api:start"]
```

### 2. Deploy

```bash
# Build and push to Cloud Run
gcloud run deploy monskills-ezpath \
  --source . \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated
```

**Result:** `https://monskills-ezpath-<hash>.run.app`

---

## 🎯 Deploy with Docker Compose (Self-Hosted)

### 1. Create `docker-compose.yml`

```yaml
version: '3.8'

services:
  api:
    build: .
    ports:
      - "3000:3000"
    environment:
      - PORT=3000
      - RATE_LIMIT_PER_MINUTE=120
      - LOG_LEVEL=info
    restart: always
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:3000/v1/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - ./certbot/conf:/etc/letsencrypt:ro
    depends_on:
      - api
    restart: always
```

### 2. Run

```bash
docker-compose up -d
```

---

## 🔐 Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `PORT` | 3000 | Server port |
| `RATE_LIMIT_PER_MINUTE` | 120 | Requests per minute per IP |
| `LOG_LEVEL` | info | Logging level |
| `NODE_ENV` | production | Environment (production or development) |

### Example `.env` file

```bash
PORT=3000
RATE_LIMIT_PER_MINUTE=120
LOG_LEVEL=info
NODE_ENV=production
```

---

## 📊 Monitoring & Logging

### Health Check Endpoint

```bash
curl https://api.monskills-ezpath.dev/v1/health
```

**Expected response:**

```json
{
  "status": "healthy",
  "uptime_ms": 3600000,
  "venues": {
    "healthy": [
      "0x",
      "Aerodrome",
      ...
    ],
    "degraded": []
  },
  "timestamp": "2026-06-06T16:00:00Z"
}
```

### Structured Logging

All requests log with format:

```
[2026-06-06T15:02:39Z] POST /v1/quote 200 177ms
[2026-06-06T15:02:40Z] POST /v1/quote/batch 200 245ms
[2026-06-06T15:02:41Z] GET /v1/health 200 12ms
```

**For production logging, integrate with:**
- **Vercel:** Built-in logs
- **Railway:** Built-in logs
- **Cloud Run:** Cloud Logging
- **Self-hosted:** Send to ELK, Datadog, or similar

---

## 🛡️ Security Checklist

- ✅ Rate limiting enabled (120 req/min by default)
- ✅ Input validation on all endpoints
- ✅ Error messages don't expose internal details
- ✅ HTTPS enforced in production
- ✅ CORS disabled by default (agents call direct)
- ✅ No authentication required (stateless, rate-limited by IP)

### Add CORS if needed

```typescript
import cors from 'cors';

app.use(
  cors({
    origin: ['https://example.com'], // Whitelist specific origins
  })
);
```

---

## 🧪 Load Testing

### Test with Apache Bench

```bash
# 100 requests, 10 concurrent
ab -n 100 -c 10 -p request.json -T application/json http://localhost:3000/v1/quote
```

### Test with wrk

```bash
# 100 connections, 4 threads, 30 seconds
wrk -t4 -c100 -d30s http://localhost:3000/v1/health
```

---

## 📈 Scaling

### Horizontal Scaling (Multiple Instances)

**Vercel:** Automatic  
**Railway:** Automatic  
**Cloud Run:** Automatic  
**Self-hosted:** Use load balancer (nginx, HAProxy)

### Rate Limiting at Scale

For multiple instances, use Redis for shared rate limit state:

```typescript
import RedisStore from 'rate-limit-redis';
import redis from 'redis';

const redisClient = redis.createClient();

const limiter = rateLimit({
  store: new RedisStore({
    client: redisClient,
    prefix: 'monskills-ezpath',
  }),
  windowMs: 60 * 1000,
  max: 120,
});
```

---

## 🚨 Troubleshooting

### Server won't start

```bash
# Check if port is in use
lsof -i :3000

# Kill process on port 3000
kill -9 $(lsof -t -i :3000)

# Start with different port
PORT=3001 npm run api:start
```

### Rate limiting not working

Check `X-RateLimit-*` headers:

```bash
curl -i http://localhost:3000/v1/health
```

Expected headers:

```
X-RateLimit-Limit: 120
X-RateLimit-Remaining: 119
X-RateLimit-Reset: 1717680879
```

### High latency

Check `/v1/health` endpoint for degraded venues:

```bash
curl http://localhost:3000/v1/health | jq .venues
```

---

## 📞 Support

**Having deployment issues?**

- 📖 Docs: https://github.com/infiniteezverse/monskills-ezpath
- 🐛 Issues: https://github.com/infiniteezverse/monskills-ezpath/issues
- 💬 Discord: https://discord.gg/infiniteezverse

---

## Quick Deployment Links

| Platform | Command | Result |
|----------|---------|--------|
| **Local** | `npm run api:dev` | http://localhost:3000 |
| **Vercel** | `vercel` | https://monskills-ezpath.vercel.app |
| **Railway** | `railway up` | https://monskills-ezpath.railway.app |
| **Cloud Run** | `gcloud run deploy` | https://monskills-ezpath.run.app |
| **Docker** | `docker-compose up` | http://localhost (with nginx) |

---

**v0.1.1 | Production-ready API server for autonomous agents**
