# Render Deployment Checklist

## ✅ Pre-Deployment Verification

### 1. Code Quality
- [x] All imports work correctly
- [x] No syntax errors
- [x] All modules compile successfully
- [x] Server initializes with 185 tools
- [x] Entry point `main_http` is callable

### 2. Configuration Files

#### render.yaml
```yaml
services:
  - type: web
    name: vgc-mcp
    runtime: python
    plan: free
    buildCommand: pip install -e ".[remote]"
    startCommand: vgc-mcp-http
    healthCheckPath: /health
    envVars:
      - key: PYTHON_VERSION
        value: "3.12"
    autoDeploy: true
```

**Status:** ✅ Correct format

#### pyproject.toml
- Entry point: `vgc-mcp-http = "vgc_mcp.server:main_http"` ✅
- Dependencies: All present ✅
- Remote extras: `uvicorn`, `starlette` ✅

### 3. Critical Files
- [x] `src/vgc_mcp/server.py` - Has `main_http()` function
- [x] `src/vgc_mcp_core/calc/nature_optimization.py` - Imports fixed
- [x] Health check route `/health` exists

## 🔍 Common Render Deployment Issues

### Issue 1: Build Command Fails
**Symptom:** Build fails during `pip install`
**Solution:** 
- Verify `pyproject.toml` is valid
- Check if `[remote]` extras are correctly defined
- Ensure all dependencies are available on PyPI

### Issue 2: Start Command Fails Immediately
**Symptom:** Service starts then immediately crashes
**Possible Causes:**
1. Missing environment variable (PORT)
2. Import error at module level
3. Syntax error in code
4. Missing dependency

**Debug Steps:**
1. Check Render build logs for import errors
2. Verify PORT environment variable is set
3. Check if uvicorn/starlette are installed

### Issue 3: Health Check Fails
**Symptom:** Service starts but health check returns 404
**Solution:**
- Verify `healthCheckPath: /health` matches route
- Check that route is registered in Starlette app

## 🚀 Deployment Steps

### Step 1: Verify Local Build
```bash
# Test the build command locally
pip install -e ".[remote]"

# Test the start command
vgc-mcp-http
```

### Step 2: Check Render Dashboard
1. Go to Render dashboard
2. Select `vgc-mcp` service
3. Check "Events" tab for deployment status
4. Check "Logs" tab for error messages

### Step 3: Manual Deploy (if auto-deploy fails)
1. Click "Manual Deploy" button
2. Select "Deploy latest commit"
3. Watch build logs in real-time

### Step 4: Verify Deployment
1. Check health endpoint: `https://your-service.onrender.com/health`
2. Should return: `{"status": "healthy", "service": "vgc-mcp", "tools": 185}`

## 🐛 Troubleshooting

### If Build Fails:
1. Check build logs for specific error
2. Verify Python version (should be 3.12)
3. Check if all dependencies install correctly

### If Start Fails:
1. Check start logs for import errors
2. Verify PORT environment variable
3. Check if uvicorn can start the app

### If Health Check Fails:
1. Verify route is registered: `Route("/health", endpoint=health_check)`
2. Check if app is actually running
3. Verify CORS middleware isn't blocking requests

## 📝 Current Status

**Last Test:** All local tests pass ✅
**Code Status:** Production ready ✅
**Configuration:** Correct ✅

**Next Action:** Monitor Render deployment logs for specific error message
