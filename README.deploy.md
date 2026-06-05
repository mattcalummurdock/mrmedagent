# Deploy Sarah agent to Cloud Run

Single service: Python agent + embedded Cube.js (localhost:4000 inside the container).

## Architecture

```
Exotel  --wss-->  Cloud Run (mrmed-agent + embedded Cube)  -->  Railway Postgres
```

No separate mrmedcube Cloud Run service is required.

## Build image

```powershell
cd c:\Users\MSI\Desktop\mrmed\Agent\mrmedagent
docker build -t mrmed-agent .
```

## Cloud Run settings

| Setting | Value |
|---------|--------|
| Port | `8080` |
| Request timeout | `3600` seconds (long calls) |
| Memory | `2 GiB` minimum (Python + Node + Cube + audio) |
| CPU | `1`–`2` |
| Min instances | `1` if you need low cold-start on inbound calls |

## Required environment variables

Copy from `.env.cloudrun.example`. Critical ones:

| Variable | Notes |
|----------|--------|
| `AGENT_PUBLIC_URL` | `https://<agent-service>.run.app` — Exotel uses `wss://<host>/ws` |
| `CUBEJS_API_SECRET` | JWT secret for embedded Cube `/load` |
| `CUBEJS_DB_*` | Railway Postgres (same DB as `DATABASE_URL`) |
| `CUBEJS_DEV_MODE` | `false` in production |
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

Workflow: `.github/workflows/google-cloudrun-docker.yml`

Build context is the `mrmedagent` repo root (Dockerfile includes `cube/` and Node deps).

## Browser demo

`/client` WebRTC is for local dev only. Production voice is **phone via Exotel**.
