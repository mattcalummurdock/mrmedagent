# mrmedagent

Sarah — MrMed voice agent (Gemini Live + Exotel + medicine tools via Cube.js).

## Production architecture

```
Exotel  --wss-->  Cloud Run (this repo)  --HTTP-->  Cloud Run (mrmedcube)
                        |
                        +--> Railway Postgres
```

Cube API: `https://mrmedcube-432303484897.asia-south1.run.app/cubejs-api/v1`

## Local dev (Exotel + ngrok)

```bash
cp .env.example .env
# fill keys; CUBE_BASE can point at local or cloud Cube
uv sync
uv run server.py -t exotel
```

## Local dev (browser WebRTC)

```bash
uv run server.py
# http://127.0.0.1:7860/client
```

## Docker

```bash
docker build -t mrmed-agent .
docker run -p 8080:8080 --env-file .env -e PORT=8080 mrmed-agent
```

## Cloud Run

- **Port:** `8080`
- **Timeout:** `3600`s
- **Memory:** `2 GiB`+
- **Entry:** Exotel mode (`docker-entrypoint.sh`)
- **Env:** see `.env.example` — set `AGENT_PUBLIC_URL` to the service URL (for `wss://.../ws` in Exotel)

Exotel Voicebot WebSocket URL:

```text
wss://<AGENT_PUBLIC_URL host>/ws
```

## GitHub Actions

Workflow: `.github/workflows/deploy-cloudrun.yml` (fill repository secrets).

## Layout

| Path | Role |
|------|------|
| `server.py` | Pipecat + FastAPI runner |
| `tools/` | Gemini function tools (medicine lookup) |
| `scripts/cube_tools.py` | Cube.js HTTP client |
| `postProcessor.py` | Post-call Groq + Postgres CRM |
