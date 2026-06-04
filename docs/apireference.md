llm
Google Gemini Live API service implementation.

This module provides real-time conversational AI capabilities using Google’s Gemini Live API, supporting both text and audio modalities with voice transcription, streaming responses, and tool usage.

pipecat.services.google.gemini_live.llm.language_to_gemini_language(language: Language)→ str[source]
Maps a Language enum value to a Gemini Live supported language code.

Source: https://ai.google.dev/api/generate-content#MediaResolution

Parameters
:
language – The language enum value to convert.

Returns
:
The Gemini language code string. If language is not in the verified mapping, falls back to the full language code string and logs a warning (via resolve_language(..., use_base_code=False)).

classpipecat.services.google.gemini_live.llm.GeminiModalities(*values)[source]
Bases: StrEnum

Supported modalities for Gemini Live.

Parameters
:
TEXT – Text responses.

AUDIO – Audio responses.

TEXT= 'TEXT'
AUDIO= 'AUDIO'
classpipecat.services.google.gemini_live.llm.GeminiMediaResolution(*values)[source]
Bases: StrEnum

Media resolution options for Gemini Live.

Parameters
:
UNSPECIFIED – Use default resolution setting.

LOW – Low resolution with 64 tokens.

MEDIUM – Medium resolution with 256 tokens.

HIGH – High resolution with zoomed reframing and 256 tokens.

UNSPECIFIED= 'MEDIA_RESOLUTION_UNSPECIFIED'
LOW= 'MEDIA_RESOLUTION_LOW'
MEDIUM= 'MEDIA_RESOLUTION_MEDIUM'
HIGH= 'MEDIA_RESOLUTION_HIGH'
classpipecat.services.google.gemini_live.llm.GeminiVADParams(*, disabled: bool | None = None, start_sensitivity: StartSensitivity | None = None, end_sensitivity: EndSensitivity | None = None, prefix_padding_ms: int | None = None, silence_duration_ms: int | None = None)[source]
Bases: BaseModel

Voice Activity Detection parameters for Gemini Live.

Parameters
:
disabled – Whether to disable VAD. Defaults to None (server-side VAD is enabled).

start_sensitivity – Sensitivity for speech start detection. Defaults to None.

end_sensitivity – Sensitivity for speech end detection. Defaults to None.

prefix_padding_ms – Prefix padding in milliseconds. Defaults to None.

silence_duration_ms – Silence duration threshold in milliseconds. Defaults to None.

disabled: bool | None
start_sensitivity: StartSensitivity | None
end_sensitivity: EndSensitivity | None
prefix_padding_ms: int | None
silence_duration_ms: int | None
classpipecat.services.google.gemini_live.llm.ContextWindowCompressionParams(*, enabled: bool = False, trigger_tokens: int | None = None)[source]
Bases: BaseModel

Parameters for context window compression in Gemini Live.

Parameters
:
enabled – Whether compression is enabled. Defaults to False.

trigger_tokens – Token count to trigger compression. None uses 80% of context window.

enabled: bool
trigger_tokens: int | None
classpipecat.services.google.gemini_live.llm.InputParams(*, frequency_penalty: Annotated[float | None, ~annotated_types.Ge(ge=0.0), ~annotated_types.Le(le=2.0)] = None, max_tokens: Annotated[int | None, ~annotated_types.Ge(ge=1)] = 4096, presence_penalty: Annotated[float | None, ~annotated_types.Ge(ge=0.0), ~annotated_types.Le(le=2.0)] = None, temperature: Annotated[float | None, ~annotated_types.Ge(ge=0.0), ~annotated_types.Le(le=2.0)] = None, top_k: Annotated[int | None, ~annotated_types.Ge(ge=0)] = None, top_p: Annotated[float | None, ~annotated_types.Ge(ge=0.0), ~annotated_types.Le(le=1.0)] = None, modalities: GeminiModalities | None = GeminiModalities.AUDIO, language: Language | None = Language.EN_US, media_resolution: GeminiMediaResolution | None = GeminiMediaResolution.UNSPECIFIED, vad: GeminiVADParams | None = None, context_window_compression: ContextWindowCompressionParams | None = None, thinking: ThinkingConfig | None = None, enable_affective_dialog: bool | None = None, proactivity: ProactivityConfig | None = None, extra: dict[str, ~typing.Any] | None=<factory>)[source]
Bases: BaseModel

Input parameters for Gemini Live generation.

Deprecated since version 0.0.105: Use GeminiLiveLLMService.Settings instead.

Parameters
:
frequency_penalty – Frequency penalty for generation (0.0-2.0). Defaults to None.

max_tokens – Maximum tokens to generate. Must be >= 1. Defaults to 4096.

presence_penalty – Presence penalty for generation (0.0-2.0). Defaults to None.

temperature – Sampling temperature (0.0-2.0). Defaults to None.

top_k – Top-k sampling parameter. Must be >= 0. Defaults to None.

top_p – Top-p sampling parameter (0.0-1.0). Defaults to None.

modalities – Response modalities. Defaults to AUDIO.

language – Language for generation. Defaults to EN_US.

media_resolution – Media resolution setting. Defaults to UNSPECIFIED.

vad – Voice activity detection parameters. Defaults to None.

context_window_compression – Context compression settings. Defaults to None.

thinking – Thinking settings. Defaults to None. Note that these settings may require specifying a model that supports them, e.g. “gemini-2.5-flash-native-audio-preview-12-2025”.

enable_affective_dialog – Enable affective dialog, which allows Gemini to adapt to expression and tone. Defaults to None. Note that these settings may require specifying a model that supports them, e.g. “gemini-2.5-flash-native-audio-preview-12-2025”. Also note that this setting may require specifying an API version that supports it, e.g. HttpOptions(api_version=”v1alpha”).

proactivity – Proactivity settings, which allows Gemini to proactively decide how to behave, such as whether to avoid responding to content that is not relevant. Defaults to None. Note that these settings may require specifying a model that supports them, e.g. “gemini-2.5-flash-native-audio-preview-12-2025”. Also note that this setting may require specifying an API version that supports it, e.g. HttpOptions(api_version=”v1alpha”).

extra – Additional parameters. Defaults to empty dict.

frequency_penalty: float | None
max_tokens: int | None
presence_penalty: float | None
temperature: float | None
top_k: int | None
top_p: float | None
modalities: GeminiModalities | None
language: Language | None
media_resolution: GeminiMediaResolution | None
vad: GeminiVADParams | None
context_window_compression: ContextWindowCompressionParams | None
thinking: ThinkingConfig | None
enable_affective_dialog: bool | None
proactivity: ProactivityConfig | None
extra: dict[str, Any] | None
classpipecat.services.google.gemini_live.llm.GeminiLiveLLMSettings(model: str | None | _NotGiven = <factory>, extra: dict[str, Any]=<factory>, system_instruction: str | None | _NotGiven = <factory>, temperature: float | None | _NotGiven = <factory>, max_tokens: int | None | _NotGiven = <factory>, top_p: float | None | _NotGiven = <factory>, top_k: int | None | _NotGiven = <factory>, frequency_penalty: float | None | _NotGiven = <factory>, presence_penalty: float | None | _NotGiven = <factory>, seed: int | None | _NotGiven = <factory>, filter_incomplete_user_turns: bool | None | _NotGiven = <factory>, user_turn_completion_config: UserTurnCompletionConfig | None | _NotGiven = <factory>, voice: str | _NotGiven = <factory>, modalities: GeminiModalities | _NotGiven = <factory>, language: Language | str | _NotGiven = <factory>, media_resolution: GeminiMediaResolution | _NotGiven = <factory>, vad: GeminiVADParams | None | _NotGiven = <factory>, context_window_compression: ContextWindowCompressionParams | dict | _NotGiven = <factory>, thinking: ThinkingConfig | dict | _NotGiven = <factory>, enable_affective_dialog: bool | _NotGiven = <factory>, proactivity: ProactivityConfig | dict | _NotGiven = <factory>)[source]
Bases: LLMSettings

Settings for GeminiLiveLLMService.

Parameters
:
voice – TTS voice identifier (e.g. "Charon").

modalities – Response modalities.

language – Language for generation.

media_resolution – Media resolution setting.

vad – Voice activity detection parameters.

context_window_compression – Context window compression configuration.

thinking – Thinking configuration.

enable_affective_dialog – Whether to enable affective dialog.

proactivity – Proactivity configuration.

voice: str | _NotGiven
modalities: GeminiModalities | _NotGiven
language: Language | str | _NotGiven
media_resolution: GeminiMediaResolution | _NotGiven
vad: GeminiVADParams | None | _NotGiven
context_window_compression: ContextWindowCompressionParams | dict | _NotGiven
thinking: ThinkingConfig | dict | _NotGiven
enable_affective_dialog: bool | _NotGiven
proactivity: ProactivityConfig | dict | _NotGiven
classpipecat.services.google.gemini_live.llm.GeminiLiveLLMService(*, api_key: str, model: str | None = None, voice_id: str = 'Charon', start_audio_paused: bool = False, start_video_paused: bool = False, system_instruction: str | None = None, tools: list[dict] | ToolsSchema | None = None, params: InputParams | None = None, settings: GeminiLiveLLMSettings | None = None, inference_on_context_initialization: bool = True, file_api_base_url: str = 'https://generativelanguage.googleapis.com/v1beta/files', http_options: HttpOptions | None = None, **kwargs)[source]
Bases: LLMService[GeminiLLMAdapter]

Provides access to Google’s Gemini Live API.

This service enables real-time conversations with Gemini, supporting both text and audio modalities. It handles voice transcription, streaming audio responses, and tool usage.

Settings
alias of GeminiLiveLLMSettings

adapter_class
alias of GeminiLLMAdapter

__init__(*, api_key: str, model: str | None = None, voice_id: str = 'Charon', start_audio_paused: bool = False, start_video_paused: bool = False, system_instruction: str | None = None, tools: list[dict] | ToolsSchema | None = None, params: InputParams | None = None, settings: GeminiLiveLLMSettings | None = None, inference_on_context_initialization: bool = True, file_api_base_url: str = 'https://generativelanguage.googleapis.com/v1beta/files', http_options: HttpOptions | None = None, **kwargs)[source]
Initialize the Gemini Live LLM service.

Parameters
:
api_key – Google AI API key for authentication.

model –

Model identifier to use.

Deprecated since version 0.0.105: Use settings=GeminiLiveLLMService.Settings(model=...) instead.

voice_id –

TTS voice identifier. Defaults to “Charon”.

Deprecated since version 0.0.105: Use settings=GeminiLiveLLMService.Settings(voice=...) instead.

start_audio_paused – Whether to start with audio input paused. Defaults to False.

start_video_paused – Whether to start with video input paused. Defaults to False.

system_instruction – System prompt for the model. Defaults to None.

tools – Tools/functions available to the model. Defaults to None.

params –

Configuration parameters for the model.

Deprecated since version 0.0.105: Use settings=GeminiLiveLLMService.Settings(...) instead.

settings – Gemini Live LLM settings. If provided together with deprecated top-level parameters, the settings values take precedence.

inference_on_context_initialization – Whether to generate a response when context is first set. Defaults to True.

file_api_base_url – Base URL for the Gemini File API. Defaults to the official endpoint.

http_options – HTTP options for the client.

**kwargs – Additional arguments passed to parent LLMService.

create_client()[source]
Create the Gemini API client instance. Subclasses can override this.

propertyfile_api: GeminiFileAPI
Get the Gemini File API client instance. Subclasses can override this.

Returns
:
The Gemini File API client.

can_generate_metrics()→ bool[source]
Check if the service can generate usage metrics.

Returns
:
True as Gemini Live supports token usage metrics.

set_audio_input_paused(paused: bool)[source]
Set the audio input pause state.

Parameters
:
paused – Whether to pause audio input.

set_video_input_paused(paused: bool)[source]
Set the video input pause state.

Parameters
:
paused – Whether to pause video input.

set_model_modalities(modalities: GeminiModalities)[source]
Set the model response modalities.

Parameters
:
modalities – The modalities to use for responses.

set_language(language: Language)[source]
Set the language for generation.

Parameters
:
language – The language to use for generation.

asyncstart(frame: StartFrame)[source]
Start the service and establish connection.

Parameters
:
frame – The start frame.

asyncstop(frame: EndFrame)[source]
Stop the service and close connections.

Parameters
:
frame – The end frame.

asynccancel(frame: CancelFrame)[source]
Cancel the service and close connections.

Parameters
:
frame – The cancel frame.

asyncprocess_frame(frame: Frame, direction: FrameDirection)[source]
Process incoming frames for the Gemini Live service.

Parameters
:
frame – The frame to process.

direction – The frame processing direction.

asyncpush_frame(frame: Frame, direction: FrameDirection = FrameDirection.DOWNSTREAM)
Pushes a frame.

Parameters
:
frame – The frame to push.

direction – The direction of frame pushing.

asyncstop_ttfb_metrics(*, end_time: float | None = None)
Stop time-to-first-byte metrics collection and push results.

Parameters
:
end_time – Optional timestamp to use as the end time. If None, uses the current time.