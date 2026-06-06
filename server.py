import atexit
import asyncio
import html
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlparse

from dotenv import load_dotenv
from fastapi import Request
from fastapi.responses import JSONResponse
from loguru import logger
from inbound_system_prompt import SYSTEM_PROMPT as INBOUND_SYSTEM_PROMPT
from outbound_system_prompt import (
    SYSTEM_PROMPT as OUTBOUND_SYSTEM_PROMPT,
    build_outbound_context,
)
from exotel_service import ExotelService
from postProcessor import normalize_phone_number, process_call_end, shutdown_postprocessor
from tools import TOOLS_SCHEMA, register_tools

load_dotenv(override=True)

from vertex_config import log_vertex_llm_config
from vertex_credentials import load_vertex_credentials

from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.audio.vad.vad_analyzer import VADParams
from pipecat.frames.frames import LLMRunFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import LLMContextAggregatorPair
from pipecat.runner.types import RunnerArguments, SmallWebRTCRunnerArguments
from pipecat.runner.utils import create_transport, parse_telephony_websocket
from pipecat.serializers.exotel import ExotelFrameSerializer
from pipecat.services.google.gemini_live.llm_vertex import GeminiLiveVertexLLMService
from pipecat.transports.base_transport import BaseTransport, TransportParams
from pipecat.transports.websocket.fastapi import (
    FastAPIWebsocketParams,
    FastAPIWebsocketTransport,
)

logger.remove(0)
logger.add(sys.stderr, level="DEBUG")


DEFAULT_PORT = 7860
IST = timezone(timedelta(hours=5, minutes=30))
_ngrok_tunnel = None

# Match qua/agent/qua.py transport params exactly.
transport_params = {
    "daily": lambda: TransportParams(
        audio_in_enabled=True,
        audio_out_enabled=True,
        vad_analyzer=SileroVADAnalyzer(
            params=VADParams(stop_secs=0.3, min_volume=0.6),
        ),
    ),
    "twilio": lambda: FastAPIWebsocketParams(
        audio_in_enabled=True,
        audio_out_enabled=True,
        add_wav_header=False,
        vad_analyzer=SileroVADAnalyzer(
            params=VADParams(stop_secs=0.3, min_volume=0.6),
        ),
    ),
    "exotel": lambda: FastAPIWebsocketParams(
        audio_in_enabled=True,
        audio_out_enabled=True,
        add_wav_header=False,
        vad_analyzer=SileroVADAnalyzer(
            params=VADParams(stop_secs=0.1, min_volume=0.3, start_secs=0.1),
        ),
    ),
    "webrtc": lambda: TransportParams(
        audio_in_enabled=True,
        audio_out_enabled=True,
        vad_analyzer=SileroVADAnalyzer(
            params=VADParams(stop_secs=0.2, min_volume=0.6, start_secs=0.1),
        ),
    ),
}


@dataclass
class CallSession:
    is_outbound: bool
    customer_phone: str | None
    call_sid: str | None
    outbound_context: dict[str, Any] | None


def _is_exotel_mode() -> bool:
    return "-t" in sys.argv and "exotel" in sys.argv or (
        "--transport" in sys.argv
        and "exotel"
        in sys.argv[
            sys.argv.index("--transport") + 1
            if sys.argv.index("--transport") + 1 < len(sys.argv)
            else -1
        ]
    )


def _argv_has_flag(flag: str) -> bool:
    return flag in sys.argv


def _get_cli_port() -> int:
    if "--port" in sys.argv:
        idx = sys.argv.index("--port")
        if idx + 1 < len(sys.argv):
            try:
                return int(sys.argv[idx + 1])
            except ValueError:
                pass
    port_env = os.getenv("PORT", "").strip()
    if port_env.isdigit():
        return int(port_env)
    return DEFAULT_PORT


def _phone_digits(value: str) -> str:
    return "".join(c for c in str(value or "") if c.isdigit())


def _parse_custom_parameters(raw: Any) -> dict[str, Any]:
    """Parse Exotel CustomField from telephony handshake custom_parameters."""
    if not raw:
        return {}
    try:
        if isinstance(raw, dict):
            custom_str = next(iter(raw.keys()), "")
        else:
            custom_str = str(raw)
        custom_str = html.unescape(custom_str)
        parsed = json.loads(custom_str)
        if isinstance(parsed, dict):
            return parsed
    except (json.JSONDecodeError, TypeError, StopIteration) as e:
        logger.warning(f"Could not parse Exotel custom_parameters: {e}")
    return {}


def parse_call_session(call_data: dict | None) -> CallSession:
    """Derive call direction, customer phone, and outbound context from Exotel handshake."""
    if not call_data:
        return CallSession(
            is_outbound=False,
            customer_phone=None,
            call_sid=None,
            outbound_context=None,
        )

    from_number = str(call_data.get("from") or "")
    to_number = str(call_data.get("to") or "")
    custom = _parse_custom_parameters(call_data.get("custom_parameters"))

    exotel_phone = os.getenv("EXOTEL_PHONE_NUMBER", "").strip()
    exotel_digits = _phone_digits(exotel_phone)
    from_digits = _phone_digits(from_number)
    to_digits = _phone_digits(to_number)

    is_outbound = custom.get("call_type") == "outbound"
    if exotel_digits and from_digits:
        if from_digits == exotel_digits or (
            len(from_digits) >= 10
            and exotel_digits.endswith(from_digits[-10:])
        ):
            is_outbound = True

    if is_outbound:
        raw_phone = to_number or custom.get("phone", "")
        logger.info(f"OUTBOUND call — customer phone from 'to': {raw_phone}")
    else:
        raw_phone = from_number
        logger.info(f"INBOUND call — customer phone from 'from': {raw_phone}")

    normalized = normalize_phone_number(str(raw_phone))
    customer_phone = normalized if len(normalized) == 10 else None

    sid = call_data.get("call_id") or call_data.get("call_sid")
    outbound_context = custom if is_outbound and custom else None

    return CallSession(
        is_outbound=is_outbound,
        customer_phone=customer_phone,
        call_sid=str(sid) if sid else None,
        outbound_context=outbound_context,
    )


def start_ngrok_tunnel(port: int) -> str:
    """Start ngrok HTTP tunnel and return the public hostname (no scheme)."""
    global _ngrok_tunnel
    from pyngrok import ngrok

    token = os.getenv("NGROK_AUTH_TOKEN", "").strip()
    if token:
        ngrok.set_auth_token(token)
        logger.info("Using NGROK_AUTH_TOKEN from environment")
    else:
        logger.warning(
            "NGROK_AUTH_TOKEN not set — using free ngrok (URLs change each restart)"
        )

    _ngrok_tunnel = ngrok.connect(port, "http")
    public_url = _ngrok_tunnel.public_url
    hostname = urlparse(public_url).netloc
    atexit.register(cleanup_ngrok)
    return hostname


def cleanup_ngrok():
    global _ngrok_tunnel
    if not _ngrok_tunnel:
        return
    try:
        from pyngrok import ngrok

        ngrok.disconnect(_ngrok_tunnel.public_url)
        ngrok.kill()
        logger.info("ngrok tunnel closed")
    except Exception as e:
        logger.error(f"Error closing ngrok tunnel: {e}")
    finally:
        _ngrok_tunnel = None


def _prepare_exotel_proxy():
    """Inject -x proxy hostname for Pipecat runner (ngrok locally, public URL on Cloud Run)."""
    if _argv_has_flag("-x") or _argv_has_flag("--proxy"):
        return

    port = _get_cli_port()

    public_base = os.getenv("AGENT_PUBLIC_URL", "").strip()
    if public_base or os.getenv("K_SERVICE"):
        if not public_base:
            logger.warning(
                "K_SERVICE set but AGENT_PUBLIC_URL missing — set AGENT_PUBLIC_URL "
                "(e.g. https://your-service.run.app) for Exotel wss://.../ws"
            )
            return
        hostname = urlparse(public_base).netloc
        if not hostname:
            logger.warning(f"Invalid AGENT_PUBLIC_URL: {public_base}")
            return
        sys.argv.extend(["-x", hostname])
        print()
        print("Exotel WebSocket URL (App Bazaar Voicebot applet):")
        print(f"  wss://{hostname}/ws")
        print()
        return

    hostname = start_ngrok_tunnel(port)
    sys.argv.extend(["-x", hostname])

    print()
    print("Exotel WebSocket URL (paste into App Bazaar Voicebot applet):")
    print(f"  wss://{hostname}/ws")
    print()
    print(f"Local server: http://0.0.0.0:{port}")
    print("Outbound: uv run python dialout.py --phone <number> --name \"Name\"")
    print("Ensure Postgres + Cube.js are reachable for medicine tool lookups.")
    print()


def _vertex_model_path(project_id: str, location: str) -> str:
    """Full Vertex publisher path — same shape as qua/agent/qua.py."""
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


def get_current_datetime_info() -> dict:
    now = datetime.now(IST)
    tomorrow = now + timedelta(days=1)
    return {
        "current_date": now.strftime("%Y-%m-%d"),
        "current_time": now.strftime("%H:%M"),
        "day_of_week": now.strftime("%A"),
        "readable_date": now.strftime("%B %d, %Y"),
        "tomorrow_date": tomorrow.strftime("%Y-%m-%d"),
        "tomorrow_readable": tomorrow.strftime("%B %d, %Y"),
        "tomorrow_day": tomorrow.strftime("%A"),
        "timezone": "Asia/Kolkata (IST)",
    }


def _datetime_context() -> str:
    dt = get_current_datetime_info()
    return f"""

## CURRENT DATE AND TIME INFORMATION

- **Current Date**: {dt['readable_date']} ({dt['day_of_week']})
- **Current Date (YYYY-MM-DD)**: {dt['current_date']}
- **Current Time**: {dt['current_time']} ({dt['timezone']})
- **Tomorrow**: {dt['tomorrow_readable']} ({dt['tomorrow_day']}), {dt['tomorrow_date']}

"""


def build_system_instruction(session: CallSession) -> str:
    base = _datetime_context()
    if session.is_outbound and session.outbound_context:
        ctx = session.outbound_context
        outbound_ctx = build_outbound_context(
            name=str(ctx.get("name") or "there"),
            product=str(ctx.get("product") or "Oxiage LG Tablet"),
            last_purchase_quantity=int(ctx.get("last_purchase_quantity") or 10),
            last_purchase_when=str(ctx.get("last_purchase_when") or "1 week ago"),
        )
        return OUTBOUND_SYSTEM_PROMPT + outbound_ctx + base
    if session.is_outbound:
        return OUTBOUND_SYSTEM_PROMPT + build_outbound_context() + base
    return INBOUND_SYSTEM_PROMPT + base


def build_greeting_developer_message(session: CallSession) -> str:
    if session.is_outbound:
        name = "there"
        if session.outbound_context:
            name = str(session.outbound_context.get("name") or "there")
        return (
            f'Say exactly: "Hello, am I speaking with {name}?" '
            "Talk in an Indian accent but don't be slow — conversational tone. "
            "One sentence only — do not introduce yourself "
            "or mention Mr. Med or any medicine yet. Wait for their answer."
        )
    return (
        'Say exactly: "Hi, this is Sarah from Mr. Med — may I know your name please?" '
        "Talk in an Indian accent but don't be slow — conversational tone. "
        "One sentence only — do not ask how you can help or mention any medicine."
    )


def _log_postprocess_task(task: asyncio.Task) -> None:
    try:
        task.result()
    except asyncio.CancelledError:
        logger.warning("Post-processing task was cancelled")
    except Exception as e:
        logger.error(f"Post-processing failed: {e}")


async def run_bot(
    transport: BaseTransport,
    runner_args: RunnerArguments,
    *,
    call_data: dict | None = None,
):
    session = parse_call_session(call_data)
    if isinstance(runner_args, SmallWebRTCRunnerArguments):
        session = CallSession(
            is_outbound=False,
            customer_phone=None,
            call_sid=None,
            outbound_context=None,
        )

    mode = "outbound" if session.is_outbound else "inbound"
    logger.info(
        f"Starting {mode} call session "
        f"(phone={session.customer_phone}, sid={session.call_sid})"
    )

    credentials_json, credentials_project_id = load_vertex_credentials()
    # Same env vars as qua/agent/qua.py
    project_id = os.getenv("GOOGLE_CLOUD_PROJECT_ID") or credentials_project_id
    location = os.getenv("GOOGLE_CLOUD_LOCATION") or "us-central1"
    model_path = _vertex_model_path(project_id, location)
    voice_id = (
        os.getenv("VERTEX_VOICE", "").strip()
        or os.getenv("GEMINI_VOICE_NAME", "").strip()
        or "Aoede"
    )

    logger.info(f"Initializing Vertex Live LLM for {mode} call (project={project_id})")
    logger.info(f"Using model: {model_path}")
    log_vertex_llm_config(logger, project_id=project_id)

    llm = GeminiLiveVertexLLMService(
        credentials=credentials_json,
        project_id=project_id,
        location=location,
        model=model_path,
        system_instruction=build_system_instruction(session),
        voice_id=voice_id,
        tools=TOOLS_SCHEMA,
    )
    register_tools(llm)

    context = LLMContext(
        [
            {
                "role": "user",
                "content": build_greeting_developer_message(session),
            }
        ]
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
        logger.info(f"Client connected — {mode} greeting")
        await task.queue_frames([LLMRunFrame()])

    @transport.event_handler("on_client_disconnected")
    async def on_client_disconnected(transport, client):
        logger.info(f"Client disconnected ({mode}) — scheduling post-processing")
        messages = context.get_messages()
        pp_task = asyncio.create_task(
            process_call_end(
                messages,
                caller_phone=session.customer_phone,
                call_sid=str(session.call_sid) if session.call_sid else None,
            )
        )
        pp_task.add_done_callback(_log_postprocess_task)
        await task.cancel()

    runner = PipelineRunner(handle_sigint=runner_args.handle_sigint)
    await runner.run(task)


async def bot(runner_args: RunnerArguments):
    """Match qua/agent/qua.py transport selection and pipeline entry."""
    if hasattr(runner_args, "websocket") and runner_args.websocket:
        transport_type, call_data = await parse_telephony_websocket(
            runner_args.websocket
        )
        logger.info(f"Auto-detected transport: {transport_type}")

        serializer = ExotelFrameSerializer(
            stream_sid=call_data.get("stream_id", ""),
            call_sid=call_data.get("call_id", ""),
        )

        transport = FastAPIWebsocketTransport(
            websocket=runner_args.websocket,
            params=FastAPIWebsocketParams(
                audio_in_enabled=True,
                audio_out_enabled=True,
                add_wav_header=False,
                vad_analyzer=SileroVADAnalyzer(
                    params=VADParams(
                        stop_secs=0.1,
                        min_volume=0.3,
                        start_secs=0.1,
                    )
                ),
                serializer=serializer,
            ),
        )
    else:
        transport = await create_transport(runner_args, transport_params)
        call_data = None

    await run_bot(transport, runner_args, call_data=call_data)


def _register_dialout_route(app) -> None:
    @app.post("/dialout")
    async def initiate_outbound_call(request: Request):
        """Initiate outbound call via Exotel Connect API."""
        logger.info("Received outbound dial-out request")
        try:
            data = await request.json()
        except Exception:
            return JSONResponse(
                status_code=400,
                content={"error": "Invalid JSON body"},
            )

        settings = data.get("dialout_settings") or {}
        phone_number = str(settings.get("phone_number") or "").strip()
        if not phone_number:
            return JSONResponse(
                status_code=400,
                content={"error": "Missing dialout_settings.phone_number"},
            )

        custom_field = settings.get("custom_field")
        if isinstance(custom_field, dict):
            custom_field.setdefault("call_type", "outbound")
        elif custom_field is None:
            custom_field = {"call_type": "outbound"}

        try:
            exotel = await ExotelService.get_instance()
            result = await exotel.call(
                to_number=phone_number,
                custom_field=custom_field,
            )
        except ValueError as e:
            return JSONResponse(status_code=400, content={"error": str(e)})
        except Exception as e:
            logger.error(f"Exotel dial-out failed: {e}")
            return JSONResponse(
                status_code=500,
                content={"error": f"Failed to initiate call: {e}"},
            )

        return JSONResponse(
            {
                "call_sid": result.get("call_sid", "unknown"),
                "status": result.get("status", "call_initiated"),
                "phone_number": phone_number,
            }
        )


def _patch_runner_with_dialout_route() -> None:
    """Pipecat 0.0.92 builds the FastAPI app inside main(); hook dialout there."""
    import pipecat.runner.run as runner_run

    original_create = runner_run._create_server_app

    def create_server_app_with_dialout(**kwargs):
        app = original_create(**kwargs)
        _register_dialout_route(app)
        return app

    runner_run._create_server_app = create_server_app_with_dialout


if __name__ == "__main__":
    from pipecat.runner.run import main

    _patch_runner_with_dialout_route()

    try:
        from cube_service import start_embedded_cube

        start_embedded_cube()
    except Exception as exc:
        logger.error(f"Embedded Cube startup failed: {exc}")
        raise

    import threading

    def _semantic_prewarm_thread() -> None:
        try:
            from tools._medicine_search import prewarm_semantic_search

            if prewarm_semantic_search():
                logger.info("Embedding model prewarm finished (semantic medicine lookup)")
            else:
                logger.info("Embedding model prewarm skipped (semantic search disabled or unavailable)")
        except Exception as exc:
            logger.warning(f"Embedding model prewarm failed: {exc}")

    threading.Thread(
        target=_semantic_prewarm_thread,
        daemon=True,
        name="semantic-prewarm",
    ).start()

    try:
        _, startup_project_id = load_vertex_credentials()
    except ValueError as exc:
        startup_project_id = None
        logger.warning(f"Vertex credentials unavailable at startup: {exc}")
    logger.info("=== Vertex Live configuration (server startup) ===")
    log_vertex_llm_config(logger, project_id=startup_project_id)

    exotel_mode = _is_exotel_mode()

    if exotel_mode:
        if "--host" not in sys.argv:
            sys.argv.extend(["--host", "0.0.0.0"])
        _prepare_exotel_proxy()
    else:
        print()
        print("WebRTC client:")
        print(f"   http://127.0.0.1:{_get_cli_port()}/client")
        print()

    main()


def _shutdown_all() -> None:
    shutdown_postprocessor()
    try:
        asyncio.run(ExotelService.shutdown())
    except Exception as e:
        logger.debug(f"Exotel shutdown skipped or failed: {e}")


atexit.register(_shutdown_all)
