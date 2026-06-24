# mrmedagent

Sarah — MrMed voice agent (Gemini Live + Daily.co browser voice + embedded Cube.js medicine tools).

## Architecture

```
frontend/  --POST {AGENT_SERVER_URL}/start-->  Agent (Cloud Run)  --Daily WebRTC-->  Browser
                                                      |
                                                      +--> Cube.js (localhost:4000) --> Postgres
```

- **Agent** (`server.py`) — API only: `POST /start` creates a Daily room and runs Sarah.
- **Frontend** (`frontend/`) — separate deployable UI. Set `AGENT_SERVER_URL` to the agent's public URL.

## Frontend (voice UI)

```bash
cd frontend
cp config.example.js config.js
# Set agentServerUrl in config.js to your Cloud Run agent URL

python3 -m http.server 3000
# Open http://localhost:3000
```

**Cloud Run frontend:** set env `AGENT_SERVER_URL=https://your-agent.run.app` — see `frontend/README.md`.

## Agent local dev (WSL on Windows)

`daily-python` does not run on native Windows. Use WSL:

```bash
wsl bash scripts/wsl-setup.sh
wsl bash scripts/wsl-start.sh
```

Required in `.env`: `DAILY_API_KEY`, `GOOGLE_VERTEX_CREDENTIALS`, `GOOGLE_CLOUD_PROJECT_ID`, Cube/DB vars.

## Docker / Cloud Run (agent)

```bash
docker build -t mrmed-agent .
docker run -p 8080:8080 --env-file .env -e PORT=8080 mrmed-agent
```

| Setting | Value |
|---------|--------|
| Agent port | `8080` |
| Cube port | `4000` (localhost inside container) |
| Memory | `2 GiB`+ |

Env: `.env.cloudrun.example` — include `DAILY_API_KEY`.

## Layout

| Path | Role |
|------|------|
| `server.py` | Agent API (`POST /start`, `/health`) |
| `daily_utils.py` | Daily room creation |
| `frontend/` | **Voice UI** (deploy separately) |
| `cube/`, `tools/`, `postProcessor.py` | Agent internals (unchanged) |
