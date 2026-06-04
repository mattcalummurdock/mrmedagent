#
# Local Vertex AI voice demo — Pipecat WebRTC UI only.
# Auth: VERTEX_CREDENTIALS or GOOGLE_VERTEX_CREDENTIALS (inline JSON or path to .json).
#

from __future__ import annotations

import inspect
import os
import sys

from dotenv import load_dotenv
from loguru import logger

load_dotenv(override=True)

from pipecat.frames.frames import LLMRunFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import LLMContextAggregatorPair
from pipecat.runner.types import RunnerArguments
from pipecat.runner.utils import create_transport
from pipecat.services.google.gemini_live.vertex.llm import GeminiLiveVertexLLMService
from pipecat.transports.base_transport import BaseTransport, TransportParams

logger.remove(0)
logger.add(sys.stderr, level="INFO")

SYSTEM_PROMPT = (
    "Talk in English in an INDIAN accent AT ALL COSTS."
)

from vertex_config import log_vertex_llm_config, vertex_location, vertex_model, vertex_voice

VERTEX_LOCATION = vertex_location()
VERTEX_MODEL = vertex_model()
VERTEX_VOICE = vertex_voice()

LOCAL_HOST = "127.0.0.1"
DEFAULT_PORT = 7860
STUN_SERVER = "stun:stun.l.google.com:19302"

# WebRTC only — no Daily / telephony transports.
transport_params = {
    "webrtc": lambda: TransportParams(
        audio_in_enabled=True,
        audio_out_enabled=True,
    ),
}


from vertex_credentials import load_vertex_credentials


def _apply_webrtc_runner_patches() -> None:
    """Reliable local WebRTC on Windows (same approach as server.py)."""
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
        "        esp32_mode=True,\n"
        "        host=args.host,\n"
        "    )",
    )

    namespace = dict(vars(runner_run))
    namespace["_SERVER_ICE_SERVERS"] = [IceServer(urls=STUN_SERVER)]
    namespace["IceServer"] = IceServer
    exec(compile(source, "<webrtc_setup>", "exec"), namespace)
    runner_run._setup_webrtc_routes = namespace["_setup_webrtc_routes"]
    logger.info("WebRTC runner patched for local client")


async def run_bot(transport: BaseTransport, runner_args: RunnerArguments) -> None:
    credentials_json, project_id = load_vertex_credentials()

    log_vertex_llm_config(logger, project_id=project_id)

    llm = GeminiLiveVertexLLMService(
        credentials=credentials_json,
        project_id=project_id,
        location=VERTEX_LOCATION,
        settings=GeminiLiveVertexLLMService.Settings(
            model=VERTEX_MODEL,
            voice=VERTEX_VOICE,
            system_instruction=SYSTEM_PROMPT,
        ),
    )

    context = LLMContext()
    user_aggregator, assistant_aggregator = LLMContextAggregatorPair(context)

    pipeline = Pipeline(
        [
            transport.input(),
            user_aggregator,
            llm,
            transport.output(),
            assistant_aggregator,
        ]
    )

    task = PipelineTask(
        pipeline,
        params=PipelineParams(
            audio_in_sample_rate=16000,
            audio_out_sample_rate=24000,
            enable_metrics=True,
            enable_usage_metrics=True,
        ),
        idle_timeout_secs=runner_args.pipeline_idle_timeout_secs,
    )

    @transport.event_handler("on_client_connected")
    async def on_client_connected(transport, client):
        logger.info("Client connected — starting conversation")
        context.add_message(
            {"role": "developer", "content": "Say hello briefly and wait for the user."}
        )
        await task.queue_frames([LLMRunFrame()])

    @transport.event_handler("on_client_disconnected")
    async def on_client_disconnected(transport, client):
        logger.info("Client disconnected")
        await task.cancel()

    runner = PipelineRunner(handle_sigint=runner_args.handle_sigint)
    await runner.run(task)


async def bot(runner_args: RunnerArguments) -> None:
    """Pipecat runner entry point."""
    transport = await create_transport(runner_args, transport_params)
    await run_bot(transport, runner_args)


if __name__ == "__main__":
    from pipecat.runner.run import main

    _apply_webrtc_runner_patches()

    if "-t" not in sys.argv and "--transport" not in sys.argv:
        sys.argv.extend(["-t", "webrtc"])
    if "--host" not in sys.argv:
        sys.argv.extend(["--host", LOCAL_HOST])
    if "--esp32" not in sys.argv:
        sys.argv.append("--esp32")

    print()
    print("Vertex AI voice demo — open the Pipecat WebRTC client:")
    print(f"   http://{LOCAL_HOST}:{DEFAULT_PORT}/client")
    print()
    print(f"  Region: {VERTEX_LOCATION}  |  Model: {VERTEX_MODEL}")
    print()

    main()
