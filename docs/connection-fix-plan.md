# Fix Plan: `vgc-mcp.onrender.com` MCP Connection Failures

**Symptom:** claude.ai custom connector reports *"Couldn't connect to the server. Check that the URL points to a valid MCP server"* when pointed at `https://vgc-mcp.onrender.com/sse`.

**Status of diagnosis (2026-07-07):** Root causes identified with live probes. The server code and deploy are FINE — this is a warm-up + endpoint-choice problem. Evidence below.

> ## Execution status (2026-07-11)
> All repo-side fixes are DONE (pending deploy to main):
> - **Fix 3 (done):** `POST /sse` now forwards to the Streamable HTTP handler
>   (Option A, `StreamableHTTPCompat` in `server.py`) — a streamable client
>   pointed at the legacy URL just works. `DELETE /sse` (session teardown)
>   forwards too. Covered by tests in `tests/test_http_transport.py`.
> - **Fix 2 (done):** all docs + `smithery.yaml` now present `/mcp` as the
>   primary URL; `/sse` labeled legacy-only. Root endpoint returns a
>   `connect` hint.
> - **Fix 1 (repo side done):** `keep-alive.yml` rewritten — each run now
>   pings every 4 min for ~24 min (covers GitHub cron drift windows),
>   `concurrency` guard prevents stacking.
>   **USER ACTION STILL REQUIRED:** create a free UptimeRobot (or
>   cron-job.org) monitor on `https://vgc-mcp.onrender.com/health` at a
>   5-minute interval — GitHub cron alone cannot guarantee warmness — or
>   upgrade Render to Starter (`plan: starter` in render.yaml).
> - **Fix 4 (measured, no change needed):** import + full 208-tool
>   registration is ~1.1s; openpyxl/fpdf are already lazy imports. The ~50s
>   cold start is Render free-tier container spin-up, not Python boot.
> - **Live probes (2026-07-11):** `/health` 200 in 0.28s, `/mcp` initialize
>   handshake OK (server v1.28.1), `POST /sse` on the OLD deploy still 405s —
>   redeploy required to pick up Fix 3.

---

## Diagnosis Evidence (verified 2026-07-07, ~20:30 UTC)

All probes run against the live Render deployment:

| Probe | Result | Meaning |
|---|---|---|
| `GET /health` | 200 in 0.15s | Server up (warm at probe time) |
| `GET /` | 200 JSON, reports 208 tools, endpoints `/mcp`, `/sse`, `/messages/` | App booted correctly |
| `GET /sse` | 200 `text/event-stream`, emits `event: endpoint` with session id | Legacy SSE transport works |
| `POST /messages/?session_id=...` with `initialize` | 202 Accepted, initialize result arrives on SSE stream (v1.28.1) | Full legacy handshake works end-to-end |
| `POST /mcp` with `initialize` | 200, valid `InitializeResult` (protocol 2025-03-26) | Streamable HTTP transport works end-to-end |
| `POST /sse` | **405 Method Not Allowed** | Streamable-HTTP clients pointed at `/sse` fail hard |
| GitHub Actions keep-alive run history | Scheduled `*/14 * * * *` but actual runs are **~2 hours apart** (08:49, 11:34, 13:50, 16:13, 18:21, 20:21 UTC) | Keep-alive is NOT keeping the dyno warm |

### Root cause 1 (primary): cold starts — keep-alive cron drift

Render free tier spins the instance down after **15 minutes** idle. Cold start is ~50s, which exceeds the Claude connector's handshake timeout → "Couldn't connect."

The repo's `.github/workflows/keep-alive.yml` pings `/health` every 14 minutes *on paper*, but GitHub Actions delays high-frequency scheduled workflows heavily on free runners — observed real interval is **~2 hours**. So the dyno is asleep most of the day, and any first connection attempt fails.

### Root cause 2 (secondary): wrong endpoint for modern connectors

claude.ai custom connectors speak **Streamable HTTP**: they `POST` the initialize request to the exact URL you give them. `POST https://vgc-mcp.onrender.com/sse` returns **405**. The correct URL for claude.ai is:

```
https://vgc-mcp.onrender.com/mcp
```

`/sse` only works for clients that speak the legacy HTTP+SSE transport (GET-then-POST). Depending on client version, fallback from 405 → SSE may not happen, so `/sse` is fragile even when the dyno is warm.

---

## Fixes (in priority order)

### Fix 1 — Replace GitHub Actions keep-alive with an external uptime pinger (REQUIRED)

GitHub cron cannot be trusted at 14-minute granularity. Move the keep-alive off GitHub:

1. Create a free monitor at **UptimeRobot** (or cron-job.org / Better Stack — anything with a reliable ≤5-minute interval):
   - Type: HTTP(s), URL: `https://vgc-mcp.onrender.com/health`
   - Interval: 5 minutes
   - This requires the user to create an account — flag this step for the user; it cannot be done from the repo.
2. Update `.github/workflows/keep-alive.yml`:
   - Keep it as a **backup** pinger but acknowledge drift in the comments, OR delete it once the external monitor is confirmed running.
   - If kept: the current 750 instance-hours/month math in the comments still holds.
3. **Alternative (best, costs money):** upgrade the Render service to the Starter plan (`plan: starter` in `render.yaml`), which never spins down. If the user approves this, the keep-alive machinery can be deleted entirely.

### Fix 2 — Publish/use the correct connector URL (REQUIRED, zero code)

Update the claude.ai custom connector to point at:

```
https://vgc-mcp.onrender.com/mcp
```

Also update any README / docs in the repo that tell users to connect to `/sse` — search for `onrender.com/sse` and `your-server.com/sse` and make `/mcp` the primary documented URL, with `/sse` labeled "legacy clients only".

### Fix 3 — Make `/sse` resilient for streamable clients (RECOMMENDED hardening)

In `src/vgc_mcp/server.py` (`build_http_app`, around lines 299–370): `POST /sse` currently 405s. Add a `POST /sse` route that either:

- **Option A (preferred):** forwards to the Streamable HTTP handler (treat `POST /sse` exactly like `POST /mcp`), so a streamable client pointed at `/sse` just works; or
- **Option B (minimal):** returns a 4xx JSON body with a clear message: `{"error": "This is the legacy SSE endpoint. Use POST https://<host>/mcp for Streamable HTTP."}` so failures are self-diagnosing.

Add a test in the HTTP app test module (the one using Starlette `TestClient` against `build_http_app`) covering the chosen behavior.

### Fix 4 — Reduce cold-start pain (OPTIONAL)

Even with a pinger, occasional cold starts happen (deploys, Render maintenance):

- Measure boot time: check Render logs for time between process start and "Uvicorn running". If tool registration (208 tools) or heavy imports dominate, lazy-import heavy modules (pandas/openpyxl/reportlab in the export path are common culprits).
- Verify `healthCheckPath: /health` responds before full tool registration completes, or Render's own health check may flap during boot.

---

## Verification Checklist (run after fixes)

1. **Warmness over time** — after the external pinger has run for >1 hour, from any machine:
   ```bash
   curl -s -o /dev/null -w "HTTP %{http_code} time=%{time_total}s\n" https://vgc-mcp.onrender.com/health
   ```
   Expect: `HTTP 200`, `time < 1s` at ANY time of day (test at a few random times). A multi-second response means the dyno was asleep → pinger not working.

2. **Streamable HTTP handshake:**
   ```bash
   curl -s -X POST https://vgc-mcp.onrender.com/mcp \
     -H "Content-Type: application/json" \
     -H "Accept: application/json, text/event-stream" \
     -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"probe","version":"1.0"}}}'
   ```
   Expect: `event: message` with a JSON-RPC `InitializeResult` (serverInfo "VGC Team Builder").

3. **Legacy SSE handshake:**
   ```bash
   curl -s -N --max-time 8 https://vgc-mcp.onrender.com/sse | head -5
   ```
   Expect: `event: endpoint` + `data: /messages/?session_id=...` within ~2s.

4. **POST /sse behavior** (after Fix 3): expect either a valid initialize response (Option A) or the explanatory JSON error (Option B) — not a bare 405.

5. **End-to-end:** re-add the connector in claude.ai using `https://vgc-mcp.onrender.com/mcp`, confirm it lists 208 tools, and call `welcome_new_user` or `get_help` successfully.

6. **Regression:** `python -m pytest tests/ -v` passes; `ruff check src/` clean.

---

## Non-causes (already ruled out — do not chase these)

- ❌ Server crash / bad deploy — server is up, v1.28.1, both transports verified working when warm.
- ❌ Auth middleware blocking the connector — `VGC_MCP_API_KEY` is not set on Render (no 401s observed; middleware only activates when the env var exists).
- ❌ SSE endpoint-event bug — the `endpoint` event is emitted correctly with a session id.
- ❌ Keep-alive workflow disabled — it is `active` and succeeding; the problem is GitHub's scheduling drift, not the workflow itself.
