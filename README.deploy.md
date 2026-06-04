# Deploy Sarah agent to Cloud Run

Cube is already at:

`https://mrmedcube-432303484897.asia-south1.run.app`

This agent runs **Exotel telephony** (`-t exotel`), not the browser WebRTC `/client` UI.

## Architecture

```
Exotel  --wss-->  Cloud Run (mrmed-agent)  --HTTP-->  Cloud Run (mrmedcube)
                         |
                         +--> Railway Postgres
```

## Build image (from `AICaller/`)

```powershell
cd c:\Users\MSI\Desktop\mrmed\AICaller
docker build -f agent/Dockerfile -t mrmed-agent .
```

## Cloud Run settings

| Setting | Value |
|---------|--------|
| Port | `8080` |
| Request timeout | `3600` seconds (long calls) |
| Memory | `2 GiB` minimum (audio + Gemini) |
| CPU | `1`–`2` |
| Min instances | `1` if you need low cold-start on inbound calls |

## Required environment variables

Copy from `.env.cloudrun.example`. Critical ones:

| Variable | Notes |
|----------|--------|
| `AGENT_PUBLIC_URL` | `https://<agent-service>.run.app` — Exotel uses `wss://<host>/ws` |
| `CUBE_BASE` | `https://mrmedcube-432303484897.asia-south1.run.app/cubejs-api/v1` |
| `CUBEJS_API_SECRET` | Must match Cube service |
| `DATABASE_URL` | Railway **public** URL + `?sslmode=require` |
| `GEMINI_API_KEY` | |
| `GROQ_API_KEY` | Post-call processing |
| `EXOTEL_*` | Telephony credentials |

Do **not** set `NGROK_AUTH_TOKEN` on Cloud Run.

## Exotel

After deploy, set Voicebot applet WebSocket URL to:

```text
wss://<your-agent-host>/ws
```

Same host as `AGENT_PUBLIC_URL` without `https://`.

## GitHub Actions

Use the same pattern as `mrmedcube`:

1. Repo with `agent/` app or monorepo path `AICaller/agent`
2. Build context: **`AICaller`** (parent folder) so `DB/scripts/cube_tools.py` is copied
3. `docker build -f agent/Dockerfile .`
4. `gcloud run deploy` with all secrets above

## Local test against cloud Cube

```powershell
cd AICaller\agent
# .env: CUBE_BASE=https://mrmedcube-432303484897.asia-south1.run.app/cubejs-api/v1
uv run server.py -t exotel
```

## Browser demo

`/client` WebRTC is for local dev only. Production voice is **phone via Exotel**.
