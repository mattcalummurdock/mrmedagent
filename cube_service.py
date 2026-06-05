"""Embedded Cube.js server — always runs locally alongside the agent."""

from __future__ import annotations

import atexit
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

import requests
from loguru import logger

from cube_config import CUBE_BASE, CUBE_PORT

_CUBE_DIR = Path(__file__).resolve().parent / "cube"
_CUBE_PROCESS: subprocess.Popen | None = None


def _node_command() -> list[str]:
    npm = shutil.which("npm.cmd") or shutil.which("npm")
    if npm:
        return [npm, "start"]
    node = shutil.which("node")
    if node:
        return [node, "scripts/start-cube.js"]
    raise RuntimeError("Node.js/npm not found — install Node 20+ for embedded Cube")


def _ensure_cube_deps() -> None:
    node_modules = _CUBE_DIR / "node_modules"
    if node_modules.is_dir():
        return
    npm = shutil.which("npm.cmd") or shutil.which("npm")
    if not npm:
        raise RuntimeError(
            f"Cube dependencies missing ({node_modules}). Run: cd cube && npm ci"
        )
    logger.info("Installing embedded Cube dependencies (first run)...")
    subprocess.run(
        [npm, "ci", "--omit=dev"],
        cwd=_CUBE_DIR,
        check=True,
    )


def _wait_for_cube(timeout: float | None = None) -> bool:
    url = f"{CUBE_BASE}/meta"
    deadline = time.time() + float(timeout or os.getenv("CUBE_STARTUP_TIMEOUT", "120"))
    while time.time() < deadline:
        if _CUBE_PROCESS and _CUBE_PROCESS.poll() is not None:
            logger.error(f"Embedded Cube exited early (code={_CUBE_PROCESS.returncode})")
            return False
        try:
            resp = requests.get(url, timeout=2)
            if resp.status_code == 200:
                return True
        except requests.RequestException:
            pass
        time.sleep(0.5)
    return False


def _shutdown_cube() -> None:
    global _CUBE_PROCESS
    proc = _CUBE_PROCESS
    if proc is None or proc.poll() is not None:
        return
    logger.info("Stopping embedded Cube server...")
    try:
        if sys.platform == "win32":
            proc.terminate()
        else:
            proc.send_signal(signal.SIGTERM)
        proc.wait(timeout=10)
    except Exception:
        proc.kill()
    _CUBE_PROCESS = None


def start_embedded_cube() -> None:
    """Start Cube.js on localhost — required for every agent run."""
    global _CUBE_PROCESS

    if not _CUBE_DIR.is_dir():
        raise RuntimeError(f"Embedded cube directory missing: {_CUBE_DIR}")

    if _CUBE_PROCESS and _CUBE_PROCESS.poll() is None:
        return

    _ensure_cube_deps()

    env = os.environ.copy()
    env["PORT"] = str(CUBE_PORT)
    env.setdefault("CUBEJS_SCHEMA_PATH", "model")
    env.setdefault("CUBEJS_CACHE_AND_QUEUE_DRIVER", "memory")
    env.setdefault("CUBEJS_LOG_LEVEL", "info")

    cmd = _node_command()
    logger.info(f"Starting embedded Cube on {CUBE_BASE} ({' '.join(cmd)})")

    _CUBE_PROCESS = subprocess.Popen(
        cmd,
        cwd=_CUBE_DIR,
        env=env,
        stdout=sys.stdout,
        stderr=sys.stderr,
    )
    atexit.register(_shutdown_cube)

    if not _wait_for_cube():
        _shutdown_cube()
        raise RuntimeError(
            f"Embedded Cube did not become ready at {CUBE_BASE}. "
            "Check CUBEJS_DB_* env vars and cube/ logs."
        )

    logger.info(f"Embedded Cube ready at {CUBE_BASE}")
