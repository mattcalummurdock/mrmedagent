# Sarah voice agent + embedded Cube.js — single Cloud Run container
FROM python:3.11-slim-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    ca-certificates \
    gnupg \
    && mkdir -p /etc/apt/keyrings \
    && curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key \
       | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg \
    && echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_20.x nodistro main" \
       > /etc/apt/sources.list.d/nodesource.list \
    && apt-get update \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv

WORKDIR /app

# Python deps
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen 2>/dev/null || uv sync

# Cube.js deps (package files only — layer cached when lockfile unchanged)
COPY cube/package.json cube/package-lock.json ./cube/
RUN cd cube && npm ci --omit=dev

# Application + embedded Cube schema
COPY . .
RUN cd cube && cp -a schema model \
    && chmod +x docker-entrypoint.sh \
    && test -f scripts/cube_tools.py \
    && test -f cube/cube.js \
    && test -f cube_config.py \
    && test -d cube/model \
    && node --version \
    && test -d cube/node_modules

# Agent listens on PORT (8080 on Cloud Run); Cube always on localhost:4000
ENV PYTHONUNBUFFERED=1
ENV PORT=8080
ENV CUBEJS_SCHEMA_PATH=model
ENV CUBEJS_CACHE_AND_QUEUE_DRIVER=memory
ENV CUBEJS_DEV_MODE=false
ENV CUBEJS_LOG_LEVEL=info
EXPOSE 8080

ENTRYPOINT ["./docker-entrypoint.sh"]
