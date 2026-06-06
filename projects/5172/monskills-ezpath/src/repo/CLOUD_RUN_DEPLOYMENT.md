# Cloud Run Deployment — Full API Release

**Deploy MONSKILLS EZ-Path API to Google Cloud Run (5 minutes).**

---

## Prerequisites

### 1. Google Cloud Account

- Create free account: https://console.cloud.google.com
- Enable billing (free tier covers this deployment)

### 2. gcloud CLI

```bash
# Check if installed
gcloud --version

# If not, install:
# macOS: brew install google-cloud-sdk
# Or: https://cloud.google.com/sdk/docs/install
```

### 3. Authenticate gcloud

```bash
gcloud auth login
gcloud auth application-default login
```

This opens your browser to authenticate.

---

## Step-by-Step Deployment

### Step 1: Set Project ID

```bash
# List your projects
gcloud projects list

# Set your project (replace PROJECT_ID)
gcloud config set project PROJECT_ID

# Or create new project
gcloud projects create monskills-ezpath --name "MONSKILLS EZ-Path"
gcloud config set project monskills-ezpath
```

### Step 2: Enable Cloud Run API

```bash
gcloud services enable run.googleapis.com
gcloud services enable compute.googleapis.com
```

### Step 3: Build and Deploy

```bash
cd /tmp/monskills-ezpath

# Deploy directly from source
gcloud run deploy monskills-ezpath \
  --source . \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --memory 512Mi \
  --cpu 1 \
  --timeout 3600 \
  --max-instances 100 \
  --set-env-vars PORT=3000,RATE_LIMIT_PER_MINUTE=120
```

**This will:**
1. Build Docker image
2. Push to Google Container Registry
3. Deploy to Cloud Run
4. Give you a live URL

---

## Expected Output

```
Service [monskills-ezpath] revision [monskills-ezpath-00001-xyz] has been deployed and is serving 100% of traffic.

Service URL: https://monskills-ezpath-xyz.run.app
```

**Save that URL** — that's your live API.

---

## Step 4: Test Live Endpoints

```bash
# Replace with your actual Cloud Run URL
export API_URL="https://monskills-ezpath-xyz.run.app"

# Health check
curl $API_URL/v1/health

# Chains
curl $API_URL/v1/chains

# Venues
curl $API_URL/v1/venues

# Single quote
curl -X POST $API_URL/v1/quote \
  -H "Content-Type: application/json" \
  -d '{
    "chain": "monad",
    "sellToken": "0x4200000000000000000000000000000000000006",
    "buyToken": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
    "sellAmount": "1000000000000000000"
  }'
```

**If all return JSON → API is live ✅**

---

## Optional: Custom Domain

To use your own domain (e.g., `api.monskills-ezpath.dev`):

```bash
gcloud run services update-traffic monskills-ezpath \
  --update-routes monskills-ezpath=100

# Map custom domain
gcloud run domain-mappings create \
  --service=monskills-ezpath \
  --domain=api.monskills-ezpath.dev
```

Then update DNS CNAME to point to Cloud Run.

---

## Monitoring & Logs

### View logs

```bash
gcloud run services logs read monskills-ezpath --limit 100
```

### View metrics

```bash
# In Google Cloud Console:
# Cloud Run → monskills-ezpath → Metrics
# Shows:
# - Requests per second
# - Error rate
# - Latency (p50, p95, p99)
# - CPU/Memory usage
```

### Real-time logs

```bash
gcloud run services logs read monskills-ezpath --follow
```

---

## Scaling & Performance

### Auto-scaling

Cloud Run automatically scales. Configure limits:

```bash
gcloud run services update monskills-ezpath \
  --min-instances 0 \
  --max-instances 100
```

### Concurrency per instance

```bash
gcloud run services update monskills-ezpath \
  --concurrency 80
```

### Memory/CPU

Default (512MB, 1 CPU) is fine. Adjust if needed:

```bash
gcloud run services update monskills-ezpath \
  --memory 1Gi \
  --cpu 2
```

---

## Cost Estimates

**Free tier covers:**
- 180,000 vCPU-seconds/month
- 360,000 GB-seconds/month
- 2 million requests/month

**For MONSKILLS EZ-Path (100 req/min = 144K/month):**
- Total cost: ~$0-5/month
- Likely free tier

---

## Troubleshooting

### Deployment fails

```bash
# Check build logs
gcloud builds log [BUILD_ID] --stream

# View recent builds
gcloud builds list
```

### Service not responding

```bash
# Check service status
gcloud run services describe monskills-ezpath

# Check logs for errors
gcloud run services logs read monskills-ezpath --limit 50
```

### High latency

```bash
# View metrics in Cloud Console
# If cold start issue: increase min-instances
gcloud run services update monskills-ezpath --min-instances 1
```

---

## Update Deployment (For Later)

When you update code:

```bash
# Commit changes
git add -A
git commit -m "Update API"
git push origin main

# Redeploy
gcloud run deploy monskills-ezpath \
  --source . \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated
```

---

## Full Cloud Run URL Format

```
https://SERVICE_NAME-HASH.run.app
├─ SERVICE_NAME: monskills-ezpath
├─ HASH: auto-generated (unique per region/project)
└─ region: us-central1 (changeable)
```

Example:
```
https://monskills-ezpath-7xk2vqr5cq-uc.a.run.app
```

---

## Next Steps After Deployment

1. ✅ Note your Cloud Run URL
2. ✅ Test all 5 endpoints
3. ✅ Update all docs with live URL
4. ✅ Post Twitter/Discord
5. ✅ Submit to registries

---

**Estimated time: 5-10 minutes from `gcloud run deploy` to live API**

Ready to deploy? Run the deployment command above and send me the Cloud Run URL when you get it. 🚀
