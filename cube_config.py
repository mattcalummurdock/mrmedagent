"""Local embedded Cube — always localhost, never an external service."""

CUBE_HOST = "127.0.0.1"
CUBE_PORT = 4000
CUBE_BASE = f"http://{CUBE_HOST}:{CUBE_PORT}/cubejs-api/v1"
