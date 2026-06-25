"""Local Mr. Med agent test — Pipecat built-in WebRTC UI only (no Daily).

Same inbound prompt and tools as production. Open /client after starting:

    uv run test.py
"""

from __future__ import annotations

import asyncio
import inspect
import os
import sys
import threading
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
from loguru import logger

load_dotenv(override=True)

from inbound_system_prompt import SYSTEM_PROMPT as INBOUND_SYSTEM_PROMPT
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.audio.vad.vad_analyzer import VADParams
from pipecat.frames.frames import LLMRunFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import LLMContextAggregatorPair
from pipecat.runner.types import RunnerArguments
from pipecat.runner.utils import create_transport
from pipecat.services.google.gemini_live.llm_vertex import GeminiLiveVertexLLMService
from pipecat.transports.base_transport import BaseTransport, TransportParams
from postProcessor import process_call_end
from tools import TOOLS_SCHEMA, register_tools
from vertex_config import log_vertex_llm_config
from vertex_credentials import load_vertex_credentials

logger.remove(0)
logger.add(sys.stderr, level="DEBUG")

IST = timezone(timedelta(hours=5, minutes=30))
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 7860
ICE_SERVERS = (
    "stun:stun.l.google.com:19302",
    "stun:stun1.l.google.com:19302",
)

transport_params = {
    "webrtc": lambda: TransportParams(
        audio_in_enabled=True,
        audio_out_enabled=True,
        vad_analyzer=SileroVADAnalyzer(
            params=VADParams(stop_secs=0.2, min_volume=0.6, start_secs=0.1),
        ),
    ),
}


def _vertex_model_path(project_id: str, location: str) -> str:
    """Full Vertex publisher path — same as server.py."""
    model_id = os.getenv(
        "VERTEX_MODEL", "gemini-live-2.5-flash-preview-native-audio-09-2025"
    ).strip()
    if model_id.startswith("projects/"):
        return model_id
    model_id = model_id.split("/")[-1]
    return (
        f"projects/{project_id}/locations/{location}/"
        f"publishers/google/models/{model_id}"
    )


def _datetime_context() -> str:
    now = datetime.now(IST)
    tomorrow = now + timedelta(days=1)
    return f"""

## CURRENT DATE AND TIME INFORMATION

- **Current Date**: {now.strftime("%B %d, %Y")} ({now.strftime("%A")})
- **Current Date (YYYY-MM-DD)**: {now.strftime("%Y-%m-%d")}
- **Current Time**: {now.strftime("%H:%M")} (Asia/Kolkata (IST))
- **Tomorrow**: {tomorrow.strftime("%B %d, %Y")} ({tomorrow.strftime("%A")}), {tomorrow.strftime("%Y-%m-%d")}

"""


def build_system_instruction() -> str:
    return INBOUND_SYSTEM_PROMPT + _datetime_context()


def build_greeting_developer_message() -> str:
    return (
        'Say exactly: "Hi, this is Sarah from Mr. Med — may I know your name please?" '
        "Talk in an Indian accent but don't be slow — conversational tone. "
        "One sentence only — do not ask how you can help or mention any medicine."
    )


def _apply_webrtc_runner_patches() -> None:
    """STUN for browser + server; keep esp32 SDP munging off unless --esp32 is passed."""
    import pipecat.runner.run as runner_run
    from pipecat.transports.smallwebrtc.connection import IceServer

    source = inspect.getsource(runner_run._setup_webrtc_routes)
    source = source.replace(
        'if request_data.get("enableDefaultIceServers"):',
        "if True:  # always expose STUN to the prebuilt WebRTC client",
    )
    source = source.replace(
        "SmallWebRTCRequestHandler(\n        esp32_mode=args.esp32, host=args.host\n    )",
        "SmallWebRTCRequestHandler(\n"
        "        ice_servers=_SERVER_ICE_SERVERS,\n"
        "        esp32_mode=args.esp32,\n"
        "        host=args.host,\n"
        "    )",
    )

    namespace = dict(vars(runner_run))
    namespace["_SERVER_ICE_SERVERS"] = [IceServer(urls=url) for url in ICE_SERVERS]
    namespace["IceServer"] = IceServer
    exec(compile(source, "<webrtc_setup>", "exec"), namespace)
    runner_run._setup_webrtc_routes = namespace["_setup_webrtc_routes"]
    logger.info("WebRTC runner patched (STUN enabled, esp32 munging only with --esp32)")


def _should_postprocess(messages: list) -> bool:
    """Skip DB writes when WebRTC never connected and Sarah never spoke."""
    if not messages:
        return False
    roles = [str(m.get("role", "")).lower() for m in messages]
    if "assistant" not in roles and roles.count("user") <= 1:
        return False
    return True


def _log_postprocess_task(task: asyncio.Task) -> None:
    try:
        task.result()
    except asyncio.CancelledError:
        logger.warning("Post-processing task was cancelled")
    except Exception as exc:
        logger.error(f"Post-processing failed: {exc}")


async def run_bot(transport: BaseTransport, runner_args: RunnerArguments) -> None:
    credentials_json, credentials_project_id = load_vertex_credentials()
    project_id = os.getenv("GOOGLE_CLOUD_PROJECT_ID") or credentials_project_id
    location = os.getenv("GOOGLE_CLOUD_LOCATION") or "us-central1"
    model_path = _vertex_model_path(project_id, location)
    voice_id = (
        os.getenv("VERTEX_VOICE", "").strip()
        or os.getenv("GEMINI_VOICE_NAME", "").strip()
        or "Aoede"
    )

    logger.info(f"Initializing Vertex Live LLM (project={project_id})")
    logger.info(f"Using model: {model_path}")
    log_vertex_llm_config(logger, project_id=project_id)

    llm = GeminiLiveVertexLLMService(
        credentials=credentials_json,
        project_id=project_id,
        location=location,
        model=model_path,
        system_instruction=build_system_instruction(),
        voice_id=voice_id,
        tools=TOOLS_SCHEMA,
    )
    register_tools(llm)

    context = LLMContext(
        [{"role": "user", "content": build_greeting_developer_message()}]
    )
    context_aggregator = LLMContextAggregatorPair(context)

    pipeline = Pipeline(
        [
            transport.input(),
            context_aggregator.user(),
            llm,
            transport.output(),
            context_aggregator.assistant(),
        ]
    )

    task = PipelineTask(
        pipeline,
        params=PipelineParams(
            audio_in_sample_rate=16000,
            audio_out_sample_rate=16000,
            enable_metrics=True,
            enable_usage_metrics=True,
        ),
        idle_timeout_secs=runner_args.pipeline_idle_timeout_secs,
    )

    @transport.event_handler("on_client_connected")
    async def on_client_connected(transport, client):
        logger.info("Client connected — inbound greeting")
        await task.queue_frames([LLMRunFrame()])

    @transport.event_handler("on_client_disconnected")
    async def on_client_disconnected(transport, client):
        messages = context.get_messages()
        if _should_postprocess(messages):
            logger.info("Client disconnected — scheduling post-processing")
            pp_task = asyncio.create_task(
                process_call_end(messages, caller_phone=None, call_sid=None)
            )
            pp_task.add_done_callback(_log_postprocess_task)
        else:
            logger.info("Client disconnected before a conversation — skipping post-processing")
        await task.cancel()

    runner = PipelineRunner(handle_sigint=runner_args.handle_sigint)
    await runner.run(task)


async def bot(runner_args: RunnerArguments) -> None:
    transport = await create_transport(runner_args, transport_params)
    await run_bot(transport, runner_args)


def _default_port() -> int:
    port_env = os.getenv("PORT", "").strip()
    if port_env.isdigit():
        return int(port_env)
    return DEFAULT_PORT


def _ensure_cli_defaults() -> None:
    if "-t" not in sys.argv and "--transport" not in sys.argv:
        sys.argv.extend(["--transport", "webrtc"])
    if "--host" not in sys.argv:
        sys.argv.extend(["--host", DEFAULT_HOST])
    if "--port" not in sys.argv:
        sys.argv.extend(["--port", str(_default_port())])
    # Do not force --esp32: SDP munging breaks browser WebRTC on localhost/Windows.


def _start_cube() -> None:
    from cube_service import start_embedded_cube

    start_embedded_cube()


def _start_semantic_prewarm() -> None:
    def _thread() -> None:
        try:
            from tools._medicine_search import prewarm_semantic_search

            if prewarm_semantic_search():
                logger.info("Embedding model prewarm finished (semantic medicine lookup)")
            else:
                logger.info("Embedding model prewarm skipped (semantic search disabled or unavailable)")
        except Exception as exc:
            logger.warning(f"Embedding model prewarm failed: {exc}")

    threading.Thread(
        target=_thread,
        daemon=True,
        name="semantic-prewarm",
    ).start()


if __name__ == "__main__":
    from pipecat.runner.run import main

    _ensure_cli_defaults()
    _apply_webrtc_runner_patches()

    try:
        _start_cube()
    except Exception as exc:
        logger.error(f"Embedded Cube startup failed: {exc}")
        raise

    _start_semantic_prewarm()

    try:
        _, startup_project_id = load_vertex_credentials()
    except ValueError as exc:
        startup_project_id = None
        logger.warning(f"Vertex credentials unavailable at startup: {exc}")

    logger.info("=== Vertex Live configuration (test.py) ===")
    log_vertex_llm_config(logger, project_id=startup_project_id)

    host = DEFAULT_HOST
    if "--host" in sys.argv:
        idx = sys.argv.index("--host")
        if idx + 1 < len(sys.argv):
            host = sys.argv[idx + 1]

    port = _default_port()
    if "--port" in sys.argv:
        idx = sys.argv.index("--port")
        if idx + 1 < len(sys.argv):
            try:
                port = int(sys.argv[idx + 1])
            except ValueError:
                pass

    print()
    print("Mr. Med agent test (Pipecat WebRTC UI)")
    print(f"   Open: http://{host}:{port}/client")
    print("   Click Connect, allow microphone, then speak.")
    print("   If ICE times out on Windows, run this script in WSL/Linux instead.")
    print()

    main()
