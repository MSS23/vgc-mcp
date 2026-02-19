# Render Deployment Fix - Step by Step Guide

## ✅ What Was Fixed

1. **Import Paths**: Fixed `nature_optimization.py` import paths (`..calc.stats` → `.stats`)
2. **Build Command**: Changed to `python -m pip install -e ".[remote]"` for reliability
3. **Configuration**: Verified render.yaml format is correct

## 🔍 How to Diagnose Deployment Failures

### Step 1: Check Render Dashboard Logs

1. Go to https://dashboard.render.com
2. Click on your `vgc-mcp` service
3. Click on the **"Events"** tab
4. Click on the latest deployment event
5. Check the **"Build Logs"** and **"Runtime Logs"** tabs

### Step 2: Look for These Common Errors

#### Error: "ModuleNotFoundError" or "ImportError"
**Cause:** Missing dependency or import path issue
**Solution:** Check if all dependencies are in `pyproject.toml` and `requirements.txt`

#### Error: "Command not found: vgc-mcp-http"
**Cause:** Package not installed correctly
**Solution:** Verify build command completed successfully

#### Error: "Address already in use" or "Port binding failed"
**Cause:** PORT environment variable issue
**Solution:** Render sets PORT automatically - verify it's being read correctly

#### Error: "SyntaxError" or "IndentationError"
**Cause:** Code syntax issue
**Solution:** Run `python -m py_compile` on all Python files

### Step 3: Test Locally First

Before deploying, test the exact commands Render will use:

```bash
# Test build command
python -m pip install -e ".[remote]"

# Test start command
vgc-mcp-http
```

If these work locally, they should work on Render.

## 🚀 Deployment Steps

### Option 1: Automatic Deploy (Recommended)

1. Push code to GitHub (already done)
2. Render should auto-deploy if `autoDeploy: true` is set
3. Monitor the deployment in Render dashboard

### Option 2: Manual Deploy

1. Go to Render dashboard
2. Click on `vgc-mcp` service
3. Click **"Manual Deploy"** button
4. Select **"Deploy latest commit"**
5. Watch build logs in real-time

### Option 3: Redeploy Previous Working Version

If current version fails:

1. Go to Render dashboard → Events tab
2. Find the last successful deployment (commit `03729c3`)
3. Click "Redeploy" on that event
4. This will deploy the working version while you fix issues

## 📋 Current Configuration

**render.yaml:**
```yaml
services:
  - type: web
    name: vgc-mcp
    runtime: python
    plan: free
    buildCommand: python -m pip install -e ".[remote]"
    startCommand: vgc-mcp-http
    healthCheckPath: /health
    envVars:
      - key: PYTHON_VERSION
        value: "3.12"
    autoDeploy: true
```

**Entry Point:** `vgc-mcp-http = "vgc_mcp.server:main_http"`

**Dependencies:** All in `pyproject.toml` under `[project.optional-dependencies.remote]`

## ✅ Verification Checklist

After deployment, verify:

- [ ] Build completes successfully (check build logs)
- [ ] Service starts without errors (check runtime logs)
- [ ] Health check works: `https://your-service.onrender.com/health`
- [ ] Returns: `{"status": "healthy", "service": "vgc-mcp", "tools": 185}`

## 🐛 If Deployment Still Fails

1. **Copy the exact error message** from Render logs
2. **Check which step failed:**
   - Build phase → Check dependencies and build command
   - Start phase → Check entry point and imports
   - Runtime → Check application code

3. **Common fixes:**
   - Missing dependency → Add to `pyproject.toml`
   - Import error → Check import paths
   - Syntax error → Run linter locally
   - Port issue → Verify PORT env var handling

## 📞 Next Steps

1. **Monitor Render dashboard** for deployment status
2. **Check logs** if deployment fails
3. **Share specific error** if you need help debugging

The code is production-ready and all local tests pass. The deployment should work now with the updated configuration.
