# mrmedagent

Sarah — MrMed voice agent (Gemini Live + Exotel + embedded Cube.js medicine tools).

## Architecture

```
Exotel  --wss-->  Agent (Python + Cube.js on localhost:4000)  -->  Postgres
```

Cube **always** runs locally inside the agent process tree (`cube_service.py` → `cube/` on port 4000). Tool calls hit `http://127.0.0.1:4000/cubejs-api/v1/load` — there is no external Cube service.

`CUBEJS_API_SECRET` must match the embedded Cube server. The client signs a short-lived JWT for `/load` when `CUBEJS_DEV_MODE=false`.

## Local dev (Exotel + ngrok)

```bash
cp .env.example .env
# fill Vertex, Exotel, CUBEJS_DB_*, CUBEJS_API_SECRET
cd cube && npm ci && cd ..
uv sync
uv run server.py -t exotel
```

## Local dev (browser WebRTC)

```bash
uv run server.py
# http://127.0.0.1:7860/client
```

## Docker / Cloud Run

```bash
docker build -t mrmed-agent .
docker run -p 8080:8080 --env-file .env -e PORT=8080 mrmed-agent
```

Single container: Node 20 + Cube schema + Python agent. No separate mrmedcube deploy.

| Setting | Value |
|---------|--------|
| Agent port | `8080` (Cloud Run `PORT`) |
| Cube port | `4000` (localhost only, inside container) |
| Memory | `2 GiB`+ |
| Timeout | `3600`s |

Env: see `.env.cloudrun.example`. Set `AGENT_PUBLIC_URL` for Exotel `wss://<host>/ws`.

## GitHub Actions

Workflow: `.github/workflows/google-cloudrun-docker.yml`

## Layout

| Path | Role |
|------|------|
| `server.py` | Pipecat + FastAPI runner |
| `cube_config.py` | Hardcoded localhost Cube URL |
| `cube_service.py` | Starts embedded Cube.js subprocess |
| `cube/` | Cube.js server (schema, `cube.js`, npm deps) |
| `tools/` | Gemini function tools (medicine lookup) |
| `scripts/cube_tools.py` | Cube.js HTTP client (localhost only) |
| `postProcessor.py` | Post-call Groq + Postgres CRM |
