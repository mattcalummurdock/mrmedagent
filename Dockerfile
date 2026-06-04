# Sarah voice agent — Cloud Run (Exotel telephony)
FROM python:3.11-slim-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen 2>/dev/null || uv sync

COPY . .
RUN chmod +x docker-entrypoint.sh \
    && test -f scripts/cube_tools.py

ENV PYTHONUNBUFFERED=1
ENV PORT=8080
EXPOSE 8080

ENTRYPOINT ["./docker-entrypoint.sh"]
