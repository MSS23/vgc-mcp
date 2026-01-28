# Deployment Guide

Comprehensive guide for deploying the VGC MCP Server on various platforms.

## Table of Contents

- [Deployment Options Overview](#deployment-options-overview)
- [Local Deployment (stdio)](#local-deployment-stdio)
- [Docker Deployment](#docker-deployment)
- [Fly.io Deployment](#flyio-deployment)
- [Render Deployment](#render-deployment)
- [Self-Hosted HTTP Server](#self-hosted-http-server)
- [Health Checks & Monitoring](#health-checks--monitoring)
- [Scaling Considerations](#scaling-considerations)

---

## Deployment Options Overview

| Option | Use Case | Difficulty | Cost |
|--------|----------|------------|------|
| **Local (stdio)** | End users, development | Easy | Free |
| **Docker** | Containerized deployment | Medium | Hosting costs |
| **Fly.io** | Production, auto-scaling | Medium | ~$5-20/month |
| **Render** | Quick deployment, simple setup | Easy | Free tier available |
| **Self-hosted** | Full control, on-premises | Hard | Infrastructure costs |

### When to Use Each Option

- **Local**: Best for individual users, fastest performance, works on free Claude Desktop
- **Docker**: Best for reproducible deployments, multi-environment consistency
- **Fly.io**: Best for production, auto-scaling, global distribution
- **Render**: Best for quick prototyping, free tier for testing
- **Self-hosted**: Best for organizations with existing infrastructure, compliance requirements

---

## Local Deployment (stdio)

**For end users** - See [LOCAL_SETUP.md](LOCAL_SETUP.md) for detailed instructions.

**Quick Setup:**

```bash
# Install
pip install -e .

# Add to Claude Desktop config
# Windows: %APPDATA%\Claude\claude_desktop_config.json
# Mac: ~/Library/Application Support/Claude/claude_desktop_config.json
{
  "mcpServers": {
    "vgc": {
      "command": "python",
      "args": ["-m", "vgc_mcp"]
    }
  }
}

# Restart Claude Desktop
```

**Advantages:**
- ✅ Free (works on free Claude Desktop)
- ✅ Fast (no network latency)
- ✅ Private (data stays local)

**Disadvantages:**
- ❌ Requires Python installation
- ❌ Manual updates

---

## Docker Deployment

### Prerequisites

- Docker installed: https://docs.docker.com/get-docker/
- Docker Compose (included with Docker Desktop)

### Using the Provided Dockerfile

**Build the image:**

```bash
docker build -t vgc-mcp .
```

**Run the container:**

```bash
docker run -p 8000:8000 vgc-mcp
```

**With environment variables:**

```bash
docker run -p 8000:8000 \
  -e PORT=8000 \
  -e LOG_LEVEL=info \
  vgc-mcp
```

### Using Docker Compose

**docker-compose.yml:**

```yaml
version: '3.8'

services:
  vgc-mcp:
    build: .
    ports:
      - "8000:8000"
    environment:
      - PORT=8000
      - LOG_LEVEL=info
    volumes:
      - cache-data:/app/data/cache
    restart: unless-stopped

volumes:
  cache-data:
```

**Start the service:**

```bash
docker-compose up -d
```

**View logs:**

```bash
docker-compose logs -f vgc-mcp
```

**Stop the service:**

```bash
docker-compose down
```

### Cache Persistence

**Important**: Mount a volume for cache persistence to avoid re-fetching API data:

```bash
docker run -p 8000:8000 \
  -v vgc-cache:/app/data/cache \
  vgc-mcp
```

Without volume mounts, cache is lost when container restarts.

### Multi-Stage Build (Production)

**Optimized Dockerfile:**

```dockerfile
# Build stage
FROM python:3.11-slim as builder

WORKDIR /app
COPY pyproject.toml .
RUN pip install --no-cache-dir build && \
    python -m build

# Runtime stage
FROM python:3.11-slim

WORKDIR /app
COPY --from=builder /app/dist/*.whl .
RUN pip install --no-cache-dir *.whl[remote]

CMD ["python", "-m", "vgc_mcp_http"]
```

**Build:**

```bash
docker build -t vgc-mcp:prod -f Dockerfile.prod .
```

---

## Fly.io Deployment

### Prerequisites

- Fly.io account: https://fly.io/app/sign-up
- Fly CLI installed: https://fly.io/docs/hands-on/install-flyctl/

### Setup

1. **Login to Fly.io:**

   ```bash
   flyctl auth login
   ```

2. **Create app (if not using provided fly.toml):**

   ```bash
   flyctl launch
   ```

   Or use the provided `fly.toml`:

   ```toml
   # fly.toml
   app = "vgc-mcp"
   primary_region = "sjc"

   [build]
     dockerfile = "Dockerfile"

   [http_service]
     internal_port = 8000
     force_https = true
     auto_stop_machines = true
     auto_start_machines = true
     min_machines_running = 0

   [[vm]]
     cpu_kind = "shared"
     cpus = 1
     memory_mb = 1024
   ```

3. **Deploy:**

   ```bash
   flyctl deploy
   ```

4. **Get your app URL:**

   ```bash
   flyctl info
   ```

   Your MCP endpoint will be: `https://YOUR_APP.fly.dev/sse`

### Configure Claude Desktop

```json
{
  "mcpServers": {
    "vgc": {
      "url": "https://YOUR_APP.fly.dev/sse"
    }
  }
}
```

### Scaling

**Scale up:**

```bash
flyctl scale count 2  # Run 2 instances
flyctl scale vm shared-cpu-2x  # Upgrade to 2 CPU cores
flyctl scale memory 2048  # Increase to 2GB RAM
```

**Auto-scaling** is configured in fly.toml:

```toml
[http_service]
  auto_stop_machines = true  # Stop when idle
  auto_start_machines = true  # Start on request
  min_machines_running = 0  # Cost optimization
```

### Monitoring

**View logs:**

```bash
flyctl logs
```

**Check status:**

```bash
flyctl status
```

**View metrics:**

```bash
flyctl dashboard
```

### Custom Domain

```bash
flyctl certs add yourdomain.com
flyctl certs show yourdomain.com
```

Add DNS records as instructed, then:

```json
{
  "mcpServers": {
    "vgc": {
      "url": "https://yourdomain.com/sse"
    }
  }
}
```

---

## Render Deployment

### Prerequisites

- Render account: https://render.com/
- GitHub repository (for auto-deploy)

### One-Click Deploy

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy)

### Manual Setup

1. **Create new Web Service** on Render dashboard

2. **Configure service:**
   - Name: `vgc-mcp`
   - Environment: `Python 3`
   - Build Command: `pip install -e ".[remote]"`
   - Start Command: `python -m vgc_mcp_http`

3. **Set environment variables:**
   - `PORT`: `8000`
   - `LOG_LEVEL`: `info`

4. **Deploy**

### Using render.yaml

**render.yaml:**

```yaml
services:
  - type: web
    name: vgc-mcp
    env: python
    plan: free
    buildCommand: "pip install -e '.[remote]'"
    startCommand: "python -m vgc_mcp_http"
    envVars:
      - key: PORT
        value: 8000
      - key: LOG_LEVEL
        value: info
```

Push to GitHub, then connect repository in Render dashboard.

### Auto-Deploy from GitHub

1. Connect GitHub repository
2. Select branch (main)
3. Enable auto-deploy
4. Push to GitHub → Automatic deployment

### Get Your URL

After deployment, Render provides URL: `https://vgc-mcp.onrender.com`

MCP endpoint: `https://vgc-mcp.onrender.com/sse`

### Free Tier Limitations

- Server spins down after 15 minutes of inactivity
- First request after spin-down takes ~30 seconds (cold start)
- Upgrade to paid plan for always-on service

---

## Self-Hosted HTTP Server

### Prerequisites

- Linux server (Ubuntu 22.04+ recommended)
- Python 3.11+
- Nginx (for reverse proxy)
- Certbot (for SSL certificates)

### Installation

1. **Install dependencies:**

   ```bash
   sudo apt update
   sudo apt install python3.11 python3.11-venv nginx certbot python3-certbot-nginx
   ```

2. **Clone repository:**

   ```bash
   cd /opt
   sudo git clone https://github.com/MSS23/vgc-mcp.git
   cd vgc-mcp
   ```

3. **Create virtual environment:**

   ```bash
   sudo python3.11 -m venv venv
   sudo venv/bin/pip install -e ".[remote]"
   ```

4. **Create systemd service:**

   **/etc/systemd/system/vgc-mcp.service:**

   ```ini
   [Unit]
   Description=VGC MCP Server
   After=network.target

   [Service]
   Type=simple
   User=www-data
   WorkingDirectory=/opt/vgc-mcp
   Environment="PATH=/opt/vgc-mcp/venv/bin"
   ExecStart=/opt/vgc-mcp/venv/bin/python -m vgc_mcp_http
   Restart=always
   RestartSec=10

   [Install]
   WantedBy=multi-user.target
   ```

5. **Start service:**

   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable vgc-mcp
   sudo systemctl start vgc-mcp
   ```

6. **Check status:**

   ```bash
   sudo systemctl status vgc-mcp
   ```

### Nginx Reverse Proxy

**/etc/nginx/sites-available/vgc-mcp:**

```nginx
server {
    listen 80;
    server_name vgc.yourdomain.com;

    location / {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # SSE-specific headers
        proxy_buffering off;
        proxy_cache off;
        proxy_set_header Connection '';
        chunked_transfer_encoding off;
    }
}
```

**Enable site:**

```bash
sudo ln -s /etc/nginx/sites-available/vgc-mcp /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### SSL/TLS with Let's Encrypt

```bash
sudo certbot --nginx -d vgc.yourdomain.com
```

Certbot will automatically:
- Obtain SSL certificate
- Update Nginx config
- Set up auto-renewal

**Test renewal:**

```bash
sudo certbot renew --dry-run
```

### Performance Tuning

**Run multiple workers (Gunicorn):**

```bash
pip install gunicorn
gunicorn -w 4 -k uvicorn.workers.UvicornWorker vgc_mcp_http:app
```

**Update systemd service:**

```ini
ExecStart=/opt/vgc-mcp/venv/bin/gunicorn -w 4 -k uvicorn.workers.UvicornWorker vgc_mcp_http:app --bind 0.0.0.0:8000
```

**Nginx worker processes:**

```nginx
# /etc/nginx/nginx.conf
worker_processes auto;
worker_connections 1024;
```

---

## Health Checks & Monitoring

### Health Endpoint

All HTTP deployments expose a health check endpoint:

```bash
curl https://your-server.com/health
```

**Response:**

```json
{
  "status": "ok",
  "version": "0.1.0",
  "uptime": 3600,
  "cache_size": 1024
}
```

### Uptime Monitoring

**UptimeRobot (free):**

1. Go to https://uptimerobot.com/
2. Add new monitor:
   - Type: HTTP(S)
   - URL: `https://your-server.com/health`
   - Interval: 5 minutes
3. Configure alerts (email, Slack, etc.)

**Healthchecks.io:**

```bash
# Add to cron or systemd timer
curl https://hc-ping.com/YOUR-UUID-HERE
```

### Logging

**Fly.io:**

```bash
flyctl logs --tail
```

**Render:**

View logs in Render dashboard

**Self-hosted (systemd):**

```bash
sudo journalctl -u vgc-mcp -f
```

**Self-hosted (file):**

```python
# Update logging config
import logging

logging.basicConfig(
    filename='/var/log/vgc-mcp.log',
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
```

### Error Alerting

**Sentry (error tracking):**

```bash
pip install sentry-sdk
```

```python
# server.py
import sentry_sdk

sentry_sdk.init(
    dsn="YOUR_SENTRY_DSN",
    traces_sample_rate=0.1
)
```

---

## Scaling Considerations

### Cache Persistence

**Problem**: Each instance has its own cache, leading to redundant API calls.

**Solution**: Use shared cache (Redis):

```bash
pip install redis
```

```python
# api/cache.py
import redis

cache = redis.Redis(host='localhost', port=6379, db=0)

def cached_get(key, fetch_func, ttl=604800):
    value = cache.get(key)
    if value:
        return json.loads(value)

    value = fetch_func()
    cache.setex(key, ttl, json.dumps(value))
    return value
```

### Load Balancing

**Nginx load balancing:**

```nginx
upstream vgc_mcp {
    server 127.0.0.1:8000;
    server 127.0.0.1:8001;
    server 127.0.0.1:8002;
}

server {
    location / {
        proxy_pass http://vgc_mcp;
    }
}
```

### Rate Limiting

**Protect APIs from abuse:**

```python
from fastapi import Request
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@app.route("/sse")
@limiter.limit("100/minute")
async def sse_endpoint(request: Request):
    # ...
```

### Database for State

**For persistent team storage across instances:**

```bash
pip install sqlalchemy asyncpg
```

```python
# Use PostgreSQL for team_manager instead of in-memory
from sqlalchemy.ext.asyncio import create_async_engine

engine = create_async_engine("postgresql+asyncpg://user:pass@localhost/vgc")
```

---

## Summary

| Deployment | Setup Time | Best For | Cost |
|------------|------------|----------|------|
| **Local** | 5 min | Individual use, development | Free |
| **Docker** | 10 min | Reproducible deploys | Hosting |
| **Fly.io** | 15 min | Production, auto-scale | $5-20/mo |
| **Render** | 10 min | Quick prototyping | Free tier |
| **Self-hosted** | 30-60 min | Full control, compliance | Infrastructure |

**Recommended**:
- **End users**: Local deployment (free, fast)
- **Small teams**: Render (easy, free tier)
- **Production**: Fly.io (reliable, scalable)
- **Enterprise**: Self-hosted (full control)

---

**Questions?** See [FAQ.md](FAQ.md) or open an issue on GitHub!
