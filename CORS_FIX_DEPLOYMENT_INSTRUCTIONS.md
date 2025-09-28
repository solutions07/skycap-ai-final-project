# SkyCap AI Service Redeployment Instructions
## CORS Policy Fix Deployment

**Issue:** Live frontend at https://solutions07.github.io cannot connect due to CORS policy blocking the origin.

**Fix Applied:** Updated app.py CORS configuration to:
```python
CORS(app, resources={r"/ask": {"origins": "https://solutions07.github.io"}})
```

## Deployment Commands for Google Cloud Shell

Since local DNS resolution is failing, execute these commands in **Google Cloud Shell**:

### Step 1: Access the Updated Code
```bash
# Ensure you have the updated code with the CORS fix
# The CORS configuration has been updated to allow https://solutions07.github.io
```

### Step 2: Deploy the Service
```bash
gcloud run deploy skycap-ai-service \
  --source . \
  --platform managed \
  --region europe-west1 \
  --allow-unauthenticated \
  --memory 4Gi \
  --cpu 2 \
  --timeout 3600s \
  --cpu-boost
```

### Step 3: Verify Deployment
The deployment should complete successfully and provide the service URL:
```
https://skycap-ai-service-472059152731.europe-west1.run.app
```

### Expected Result
- ✅ Service deployed with new CORS policy
- ✅ Frontend at https://solutions07.github.io can now connect
- ✅ CORS errors resolved

## Changes Made
1. **Removed** complex allowed_origins array configuration
2. **Implemented** specific origin allowance: `"https://solutions07.github.io"`
3. **Simplified** CORS configuration for production stability

## Validation
After deployment, test the frontend connectivity:
1. Visit https://solutions07.github.io
2. Submit a query to verify CORS policy is working
3. Confirm no CORS errors in browser console

---
**Status:** Ready for deployment via Google Cloud Shell
**Priority:** URGENT - Frontend currently blocked by CORS policy