import atexit
import asyncio
import html
import inspect
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

from vertex_config import vertex_location, vertex_model, vertex_voice
from vertex_credentials import load_vertex_credentials

from pipecat.audio.filters.rnnoise_filter import RNNoiseFilter
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.audio.vad.vad_analyzer import VADParams
from pipecat.frames.frames import LLMRunFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import LLMContextAggregatorPair
from pipecat.runner.types import (
    RunnerArguments,
    SmallWebRTCRunnerArguments,
    WebSocketRunnerArguments,
)
from pipecat.runner.utils import (
    _create_telephony_transport,
    _get_transport_params,
    create_transport,
    parse_telephony_websocket,
)
from pipecat.services.google.gemini_live.vertex.llm import GeminiLiveVertexLLMService
from pipecat.transports.base_transport import BaseTransport, TransportParams
from pipecat.transports.websocket.fastapi import FastAPIWebsocketParams

logger.remove(0)
logger.add(sys.stderr, level="DEBUG")

DEFAULT_PORT = 7860
IST = timezone(timedelta(hours=5, minutes=30))
STUN_SERVER = "stun:stun.l.google.com:19302"
LOCAL_HOST = "127.0.0.1"

_ngrok_tunnel = None

transport_params = {
    "webrtc": lambda: TransportParams(
        audio_in_filter=RNNoiseFilter(),
        audio_in_enabled=True,
        audio_out_enabled=True,
    ),
    "exotel": lambda: FastAPIWebsocketParams(
        audio_in_filter=RNNoiseFilter(),
        audio_in_enabled=True,
        audio_out_enabled=True,
        add_wav_header=False,
        vad_analyzer=SileroVADAnalyzer(
            params=VADParams(start_secs=0.2, stop_secs=0.2),
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


def _apply_webrtc_runner_patches():
    """Patch Pipecat runner for reliable local WebRTC on Windows."""
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
    logger.info(
        f"WebRTC runner patched: browser STUN, server SDP munged to {LOCAL_HOST}"
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
            "Speak English with a THICK unmistakable Indian accent — stern tone, "
            "never American/British/neutral foreign accent. "
            "One sentence only — do not introduce yourself "
            "or mention Mr. Med or any medicine yet. Wait for their answer."
        )
    return (
        'Say exactly: "Hi, this is Sarah from Mr. Med — may I know your name please?" '
        "Speak English with a THICK unmistakable Indian accent — stern tone, "
        "never American/British/neutral foreign accent. "
        "One sentence only — do not ask how you can help or mention any medicine."
    )


def _audio_sample_rates(runner_args: RunnerArguments) -> tuple[int, int]:
    if isinstance(runner_args, WebSocketRunnerArguments):
        return 16000, 8000
    return 16000, 24000


async def _create_bot_transport(runner_args: RunnerArguments):
    """Create transport; for telephony, parse Exotel/Twilio handshake once for call metadata."""
    if isinstance(runner_args, WebSocketRunnerArguments):
        transport_type, call_data = await parse_telephony_websocket(
            runner_args.websocket
        )
        params = _get_transport_params(transport_type, transport_params)
        transport = await _create_telephony_transport(
            runner_args.websocket, params, transport_type, call_data
        )
        return transport, call_data
    transport = await create_transport(runner_args, transport_params)
    return transport, None


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

    credentials_json, project_id = load_vertex_credentials()
    location = vertex_location()
    model = vertex_model()
    voice = vertex_voice()
    temperature = float(os.getenv("LLM_TEMPERATURE", "0.2"))
    audio_in_rate, audio_out_rate = _audio_sample_rates(runner_args)

    logger.info(
        f"Vertex Live: project={project_id} location={location} model={model} voice={voice}"
    )

    llm = GeminiLiveVertexLLMService(
        credentials=credentials_json,
        project_id=project_id,
        location=location,
        settings=GeminiLiveVertexLLMService.Settings(
            model=model,
            voice=voice,
            temperature=temperature,
            system_instruction=build_system_instruction(session),
        ),
        tools=TOOLS_SCHEMA,
    )
    register_tools(llm)

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
            audio_in_sample_rate=audio_in_rate,
            audio_out_sample_rate=audio_out_rate,
            enable_metrics=True,
            enable_usage_metrics=True,
        ),
        idle_timeout_secs=runner_args.pipeline_idle_timeout_secs,
    )

    @transport.event_handler("on_client_connected")
    async def on_client_connected(transport, client):
        logger.info(f"Client connected — {mode} greeting")
        context.add_message(
            {
                "role": "developer",
                "content": build_greeting_developer_message(session),
            }
        )
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
    transport = None
    call_data = None
    try:
        transport, call_data = await _create_bot_transport(runner_args)

        if isinstance(runner_args, SmallWebRTCRunnerArguments):
            logger.info("Engaging WebRTC peer connection early")
            await runner_args.webrtc_connection.connect()

        await run_bot(transport, runner_args, call_data=call_data)
    except Exception as e:
        logger.error(f"Call session failed: {e}", exc_info=True)
        raise
    finally:
        if transport is not None:
            try:
                await transport.cleanup()
            except Exception as cleanup_err:
                logger.warning(f"Transport cleanup error: {cleanup_err}")


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


if __name__ == "__main__":
    from pipecat.runner.run import app, main

    _register_dialout_route(app)

    exotel_mode = _is_exotel_mode()

    if exotel_mode:
        if "--host" not in sys.argv:
            sys.argv.extend(["--host", "0.0.0.0"])
        _prepare_exotel_proxy()
    else:
        _apply_webrtc_runner_patches()
        if "--host" not in sys.argv:
            sys.argv.extend(["--host", LOCAL_HOST])
        if "--esp32" not in sys.argv:
            sys.argv.append("--esp32")

        print()
        print("IMPORTANT: Open this exact URL (not localhost):")
        print(f"   http://{LOCAL_HOST}:7860/client")
        print()

    main()


def _shutdown_all() -> None:
    shutdown_postprocessor()
    try:
        asyncio.run(ExotelService.shutdown())
    except Exception as e:
        logger.debug(f"Exotel shutdown skipped or failed: {e}")


atexit.register(_shutdown_all)
