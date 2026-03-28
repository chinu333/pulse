"""
PULSE - FastAPI Application
Main entry point for the Newsroom AI Orchestrator API.
"""

import asyncio
import base64
import logging
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.encoders import jsonable_encoder
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from starlette.middleware import Middleware
from starlette.types import ASGIApp, Receive, Scope, Send

from app.config import settings
from app.models.schemas import (
    AgentMessage, AgentRole, PipelineState, PipelineStatusResponse,
    StoryInput, StoryResponse, StoryStatus,
)
from app.graph.workflow import get_newsroom_graph
from app.agents.orchestrator import orchestrator_agent, orchestrator_finalize
from app.agents.researcher import researcher_agent
from app.agents.speech import speech_agent
from app.agents.video import video_agent
from app.agents.writer import writer_agent
# from app.agents.image_generator import image_generator_agent  # Disabled per CIO feedback
from app.agents.podcast import podcast_agent
from app.agents.translation import translation_agent
from app.agents.factchecker import factchecker_agent
from app.agents.optimizer import optimizer_agent
from app.agents.compliance import compliance_agent
from app.agents.security import security_inbound_agent, security_outbound_agent
from app.services.audit_trail import record_audit_event, get_audit_trail, get_audit_summary, get_langsmith_dashboard_data
from app.services.azure_avatar import (
    start_token_refresh_threads,
    get_speech_token_value,
    get_ice_token,
    get_avatar_config,
    connect_avatar,
    speak_ssml,
    stop_speaking,
    disconnect_avatar,
)
from app.services.dubbing import (
    get_dubbing_script,
    build_segment_ssml,
    synthesize_segment,
    synthesize_full_dub,
    VOICE_MAP,
    STYLE_MAP,
    LANGUAGE_LABELS,
)
from app.services.azure_maps import get_preparation_stores, reverse_geocode, search_pois_for_question

# ── Logging ──────────────────────────────────────────────────
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s │ %(name)-28s │ %(levelname)-7s │ %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("pulse.main")

# ── In-memory story store (demo) ────────────────────────────
story_store: dict[str, dict[str, Any]] = {}

# ── WebSocket connections ────────────────────────────────────
ws_connections: list[WebSocket] = []

# ── Step-by-step pipeline ────────────────────────────────────
step_tracker: dict[str, int] = {}  # story_id → next step index

STEP_SEQUENCE = [
    (orchestrator_agent,        "Orchestrator",         "orchestrator"),
    (security_inbound_agent,    "Content Safety",       "security"),
    (researcher_agent,          "Researcher",           "researcher"),
    (speech_agent,              "Speech",               "speech"),
    (video_agent,               "Video",                "video"),
    (writer_agent,              "Writer",               "writer"),
    # (image_generator_agent, "Image Generator",      "image_generator"),  # Disabled per CIO feedback
    (factchecker_agent,         "Fact-Checker",         "fact_checker"),
    (security_outbound_agent,   "Security and Brand",   "security_outbound"),
    # NOTE: if outbound security fails, pipeline skips to final (see _run_single_step)
    (compliance_agent,          "Compliance",           "compliance"),
    # NOTE: optimizer, podcast & translator only run if compliance approves (see _run_single_step)
    (optimizer_agent,           "Optimizer",            "optimizer"),
    (podcast_agent,             "Podcast",              "podcast"),
    (translation_agent,         "Translator",           "translator"),
    (orchestrator_finalize,     "Orchestrator (Final)", "orchestrator"),
]

# Index of the compliance step in STEP_SEQUENCE (for conditional skip logic)
_COMPLIANCE_STEP_IDX = next(
    i for i, (_, _, key) in enumerate(STEP_SEQUENCE) if key == "compliance"
)
_OPTIMIZER_STEP_IDX = next(
    i for i, (_, _, key) in enumerate(STEP_SEQUENCE) if key == "optimizer"
)
_SECURITY_OUTBOUND_STEP_IDX = next(
    i for i, (_, _, key) in enumerate(STEP_SEQUENCE) if key == "security_outbound"
)
_FINAL_STEP_IDX = next(
    i for i, (_, name, _) in enumerate(STEP_SEQUENCE) if name == "Orchestrator (Final)"
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle."""
    logger.info("=" * 60)
    logger.info(f"  {settings.name} v{settings.version} — Newsroom AI Orchestrator")
    logger.info(f"  Mode: {'DEMO (mock data)' if settings.demo_mode else 'LIVE'}")
    logger.info("=" * 60)
    # Pre-compile graph on startup
    get_newsroom_graph()
    logger.info("LangGraph workflow compiled and ready")
    # Start background token refresh for avatar service
    start_token_refresh_threads()
    logger.info("Avatar token refresh threads started")
    yield
    logger.info("PULSE shutting down")


# ── FastAPI App ──────────────────────────────────────────────
app = FastAPI(
    title="PULSE — Newsroom AI Orchestrator",
    description="Multi-agent AI pipeline for broadcast news production",
    version=settings.version,
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files — with no-cache headers so browsers always fetch fresh content
class NoCacheStaticFiles(StaticFiles):
    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        async def send_with_no_cache(message):
            if message.get("type") == "http.response.start":
                headers = list(message.get("headers", []))
                headers.append((b"cache-control", b"no-cache, no-store, must-revalidate"))
                headers.append((b"pragma", b"no-cache"))
                headers.append((b"expires", b"0"))
                message["headers"] = headers
            await send(message)
        await super().__call__(scope, receive, send_with_no_cache)

app.mount("/static", NoCacheStaticFiles(directory="static"), name="static")


# ── Routes ───────────────────────────────────────────────────

@app.get("/")
async def root():
    """Serve the main UI."""
    resp = FileResponse("static/index.html")
    resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    return resp


@app.get("/api/health")
async def health():
    return {
        "status": "healthy",
        "app": settings.name,
        "version": settings.version,
        "demo_mode": settings.demo_mode,
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.post("/api/stories", response_model=StoryResponse)
async def submit_story(story: StoryInput):
    """
    Submit a new story to the PULSE pipeline.
    Kicks off the full multi-agent workflow.
    """
    story_id = str(uuid.uuid4())[:12]
    logger.info(f"New story submitted: [{story_id}] {story.headline}")

    # Initialize pipeline state
    pipeline = PipelineState(
        story_id=story_id,
        input=story,
        status=StoryStatus.INCOMING,
        created_at=datetime.utcnow(),
    )

    # Store initial state
    story_store[story_id] = pipeline.model_dump()
    step_tracker[story_id] = 0

    # Run only the first step (user approves each subsequent step)
    asyncio.create_task(_run_single_step(story_id))

    return StoryResponse(
        story_id=story_id,
        status=StoryStatus.INCOMING,
        message=f"Story '{story.headline}' submitted to PULSE pipeline",
    )


# ── Image Analysis Endpoint ─────────────────────────────────

class ImageAnalysisRequest(BaseModel):
    image_base64: str
    mime_type: str = "image/jpeg"


class ImageAnalysisResponse(BaseModel):
    headline: str
    description: str


IMAGE_ANALYSIS_PROMPT = """You are a senior news editor at a major broadcast television network.
Analyze this image and determine what newsworthy story it depicts.

You MUST respond with valid JSON — no markdown, no commentary:

{
  "headline": "A compelling, broadcast-ready news headline (55-70 characters) based on what you see in the image",
  "description": "A 2-3 sentence description providing context for the story. Include specific details visible in the image — locations, events, people, conditions, or activities. Write in journalistic style."
}

Guidelines:
- Be specific about what you observe — avoid vague descriptions
- The headline should be suitable for a breaking news chyron
- The description should give a reporter enough context to begin researching the story
- If the image shows a natural disaster, accident, protest, press event, etc., identify it specifically
- If the image is ambiguous, make your best editorial judgment about the most newsworthy angle"""


@app.post("/api/analyze-image", response_model=ImageAnalysisResponse)
async def analyze_image(req: ImageAnalysisRequest):
    """Analyze an uploaded image with GPT-4.1 vision to extract a headline and description."""
    import json
    import re
    from langchain_core.messages import HumanMessage, SystemMessage
    from app.services.azure_openai import get_llm

    logger.info("Analyzing uploaded image (%s, %d chars base64)", req.mime_type, len(req.image_base64))

    llm = get_llm(temperature=0.3)
    data_uri = f"data:{req.mime_type};base64,{req.image_base64}"

    response = await llm.ainvoke([
        SystemMessage(content=IMAGE_ANALYSIS_PROMPT),
        HumanMessage(content=[
            {"type": "image_url", "image_url": {"url": data_uri}},
            {"type": "text", "text": "Analyze this image and generate a news headline and description. Respond with JSON only."},
        ]),
    ])

    # Parse JSON response
    try:
        cleaned = re.sub(r"```(?:json)?\s*", "", response.content).strip().rstrip("`")
        data = json.loads(cleaned)
        return ImageAnalysisResponse(
            headline=data.get("headline", "Breaking News: Image Analysis"),
            description=data.get("description", response.content[:300]),
        )
    except (json.JSONDecodeError, KeyError):
        # Fallback: try to extract from raw text
        lines = response.content.strip().split("\n")
        headline = lines[0][:80] if lines else "Breaking News"
        desc = " ".join(lines[1:])[:500] if len(lines) > 1 else response.content[:300]
        return ImageAnalysisResponse(headline=headline, description=desc)


@app.get("/api/stories/{story_id}", response_model=PipelineStatusResponse)
async def get_story_status(story_id: str):
    """Get the current status of a story in the pipeline."""
    if story_id not in story_store:
        raise HTTPException(status_code=404, detail="Story not found")

    state = story_store[story_id]
    return _build_status_response(state)


@app.get("/api/stories")
async def list_stories():
    """List all stories in the pipeline."""
    return [
        {
            "story_id": sid,
            "headline": s.get("input", {}).get("headline", ""),
            "status": s.get("status", "unknown"),
            "priority": s.get("input", {}).get("priority", "medium"),
            "created_at": s.get("created_at"),
            "current_agent": s.get("current_agent"),
            "message_count": len(s.get("messages", [])),
        }
        for sid, s in story_store.items()
    ]


@app.get("/api/stories/{story_id}/messages")
async def get_story_messages(story_id: str):
    """Get all agent messages for a story."""
    if story_id not in story_store:
        raise HTTPException(status_code=404, detail="Story not found")
    return story_store[story_id].get("messages", [])


@app.post("/api/stories/{story_id}/continue")
async def continue_story(story_id: str):
    """Continue to the next pipeline step (user-approved step-by-step execution)."""
    if story_id not in story_store:
        raise HTTPException(status_code=404, detail="Story not found")
    if story_id not in step_tracker:
        raise HTTPException(status_code=400, detail="Pipeline already complete")
    step_idx = step_tracker[story_id]
    if step_idx >= len(STEP_SEQUENCE):
        raise HTTPException(status_code=400, detail="Pipeline already complete")
    asyncio.create_task(_run_single_step(story_id))
    return {"status": "ok", "step": step_idx, "total_steps": len(STEP_SEQUENCE)}


@app.post("/api/stories/{story_id}/end")
async def end_pipeline(story_id: str):
    """End the pipeline early at the current step."""
    if story_id not in story_store:
        raise HTTPException(status_code=404, detail="Story not found")
    step_tracker.pop(story_id, None)
    state = story_store[story_id]
    state["status"] = "ended_by_user"
    story_store[story_id] = state
    logger.info(f"Pipeline ended by user for story [{story_id}]")
    await broadcast_update(story_id, {
        "type": "pipeline_complete",
        "status": "ended_by_user",
        "total_messages": len(state.get("messages", [])),
        "progress": 100,
    })
    return {"status": "ended"}


# ── Avatar API Endpoints ─────────────────────────────────────

class ConnectAvatarRequest(BaseModel):
    localSdp: str  # base64-encoded local SDP
    avatarCharacter: str = "meg"
    avatarStyle: str = "formal"
    voiceName: str = "en-US-AvaMultilingualNeural"
    transparentBackground: bool = True
    customized: bool = False


class SpeakRequest(BaseModel):
    text: str = ""
    ssml: str = ""
    clientId: str = ""


class DisconnectRequest(BaseModel):
    clientId: str = ""


@app.get("/api/avatar/config")
async def avatar_config():
    """Return avatar configuration for the frontend."""
    return get_avatar_config()


@app.get("/api/avatar/getIceToken")
async def avatar_ice_token():
    """Fetch TURN/STUN relay credentials for WebRTC avatar session."""
    if settings.demo_mode:
        return {"Urls": ["stun:stun.l.google.com:19302"], "Username": "", "Password": ""}
    try:
        return get_ice_token()
    except Exception as e:
        logger.error(f"Avatar ICE token error: {e}")
        raise HTTPException(status_code=500, detail="Failed to acquire ICE credentials")


@app.post("/api/avatar/connectAvatar")
def avatar_connect(req: ConnectAvatarRequest):
    """Connect to the Azure avatar service using server-side Speech SDK."""
    if settings.demo_mode:
        raise HTTPException(status_code=400, detail="Avatar not available in demo mode")
    client_id = str(uuid.uuid4())[:12]
    try:
        remote_sdp = connect_avatar(
            client_id=client_id,
            local_sdp=req.localSdp,
            avatar_character=req.avatarCharacter,
            avatar_style=req.avatarStyle,
            custom_avatar=req.customized,
            transparent_background=req.transparentBackground,
            tts_voice=req.voiceName,
        )
        return {"remoteSdp": remote_sdp, "clientId": client_id}
    except Exception as e:
        logger.error(f"Avatar connect error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/avatar/speak")
def avatar_speak(req: SpeakRequest):
    """Send text/SSML for the avatar to speak."""
    if settings.demo_mode:
        return {"status": "ok"}
    try:
        ssml = req.ssml
        if not ssml and req.text:
            voice = settings.azure_avatar.voice_name
            ssml = (
                f'<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" '
                f'xmlns:mstts="http://www.w3.org/2001/mstts" xml:lang="en-US">'
                f'<voice name="{voice}">{req.text}</voice></speak>'
            )
        if not ssml:
            raise HTTPException(status_code=400, detail="No text or SSML provided")
        result = speak_ssml(req.clientId, ssml)
        return {"status": "ok", "result": result}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Avatar speak error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/avatar/stopSpeaking")
def avatar_stop_speaking(req: DisconnectRequest):
    """Stop the avatar's current speech."""
    if settings.demo_mode:
        return {"status": "ok"}
    try:
        stop_speaking(req.clientId)
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Avatar stop error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/avatar/disconnect")
def avatar_disconnect(req: DisconnectRequest):
    """Disconnect from the avatar session and release resources."""
    try:
        disconnect_avatar(req.clientId)
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Avatar disconnect error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/stories/{story_id}/anchor-text")
async def get_anchor_text(story_id: str):
    """Get the article text formatted for the AI anchor to read."""
    if story_id not in story_store:
        raise HTTPException(status_code=404, detail="Story not found")
    state = story_store[story_id]
    draft = state.get("draft")
    if not draft:
        raise HTTPException(status_code=400, detail="No article draft available yet")

    headline = draft.get("headline", "")
    body = draft.get("body", "")
    summary = draft.get("summary", "")

    # Build a news-anchor-style script
    script = f"{headline}.\n\n{summary}\n\n{body}" if summary else f"{headline}.\n\n{body}"
    return {"script": script, "headline": headline}


# ── TTS (Dragon HD Omni) ────────────────────────────────────

class TTSRequest(BaseModel):
    text: str
    voice: str = ""  # empty = default Dragon HD Omni


@app.post("/api/tts")
async def text_to_speech(req: TTSRequest):
    """Synthesize text to MP3 audio using Dragon HD Omni via Azure Speech.

    Returns base64-encoded MP3 audio.
    """
    import base64
    import traceback
    from app.services.azure_speech import synthesize_speech, DEFAULT_HD_VOICE

    if not req.text or not req.text.strip():
        raise HTTPException(status_code=400, detail="No text provided")

    voice = req.voice or DEFAULT_HD_VOICE
    logger.info("[TTS] Request: text_len=%d, voice=%s", len(req.text.strip()), voice)

    try:
        audio_bytes = await synthesize_speech(req.text.strip(), voice=voice)
    except Exception as exc:
        logger.error("[TTS] synthesize_speech raised: %s\n%s", exc, traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"TTS exception: {exc}")

    if not audio_bytes:
        logger.error("[TTS] synthesize_speech returned empty bytes (synthesis failed)")
        raise HTTPException(status_code=500, detail="Speech synthesis returned empty audio — check server logs for cancellation details")

    logger.info("[TTS] Success: %d bytes of audio", len(audio_bytes))
    return {
        "audio": base64.b64encode(audio_bytes).decode("ascii"),
        "format": "mp3",
        "voice": voice,
        "size_bytes": len(audio_bytes),
    }


# ── Store Locator / Preparation Stores ───────────────────────

class ReverseGeocodeRequest(BaseModel):
    lat: float
    lon: float


@app.post("/api/geo/reverse")
async def reverse_geo(req: ReverseGeocodeRequest):
    """Reverse geocode lat/lon (from browser GPS) to zipcode via Azure Maps."""
    result = await reverse_geocode(req.lat, req.lon)
    if not result:
        raise HTTPException(status_code=404, detail="Could not determine location")
    return result


class StoreLocatorRequest(BaseModel):
    zipcode: str
    story_id: str = ""


@app.post("/api/stores/nearby")
async def nearby_stores(req: StoreLocatorRequest):
    """Find nearby preparation stores based on user zipcode and current story context."""
    headline = ""
    description = ""
    if req.story_id and req.story_id in story_store:
        state = story_store[req.story_id]
        inp = state.get("input", {})
        headline = inp.get("headline", "")
        description = inp.get("description", "")

    result = await get_preparation_stores(
        zipcode=req.zipcode,
        story_headline=headline,
        story_description=description,
    )
    return result


# ── Weather Forecast ─────────────────────────────────────────

class WeatherRequest(BaseModel):
    lat: float
    lon: float
    days: int = 7


@app.post("/api/weather/forecast")
async def weather_forecast(req: WeatherRequest):
    """Get multi-day weather forecast for a location via Azure Maps."""
    from app.services.azure_maps import get_weather_forecast
    result = await get_weather_forecast(req.lat, req.lon, req.days)
    if result.get("error"):
        raise HTTPException(status_code=502, detail=result["error"])
    return result


# ── Traffic / Route ──────────────────────────────────────────

class TrafficRequest(BaseModel):
    origin_lat: float
    origin_lon: float
    dest_city: str = ""
    dest_lat: float | None = None
    dest_lon: float | None = None


@app.post("/api/traffic/route")
async def traffic_route(req: TrafficRequest):
    """Get traffic-aware route between origin and a US city destination."""
    from app.services.azure_maps import get_traffic_route, geocode_city

    # Resolve destination
    if req.dest_lat is not None and req.dest_lon is not None:
        dest_lat, dest_lon = req.dest_lat, req.dest_lon
        dest_label = req.dest_city or f"{dest_lat},{dest_lon}"
    elif req.dest_city:
        geo = await geocode_city(req.dest_city)
        if not geo:
            raise HTTPException(status_code=404, detail=f"Could not geocode '{req.dest_city}'")
        dest_lat, dest_lon = geo["lat"], geo["lon"]
        dest_label = f"{geo['city']}, {geo['state']}"
    else:
        raise HTTPException(status_code=400, detail="Provide dest_city or dest_lat/dest_lon")

    result = await get_traffic_route(req.origin_lat, req.origin_lon, dest_lat, dest_lon)
    if result.get("error"):
        raise HTTPException(status_code=502, detail=result["error"])
    result["destination"] = dest_label
    return result


# ── Q&A Agentic Orchestrator ─────────────────────────────────
#
# Instead of hardcoded keyword matching, this uses an LLM with tool/function
# calling to decide which "agent" to invoke for each user question:
#   • weather_forecast  — Azure Maps 7-day weather
#   • traffic_route     — Azure Maps traffic + route info
#   • nearby_stores     — Azure Maps POI / store locator
#   • general_answer    — Free-form LLM answer with story context
#
# The LLM acts as an orchestrator: it reads the question, decides the
# right tool, the backend executes the real API, and returns structured data.

class QARequest(BaseModel):
    question: str
    zipcode: str = ""
    story_id: str = ""
    lat: float | None = None
    lon: float | None = None
    nearby_stores: list[dict] | None = None


# ── Tool definitions for the orchestrator LLM ────────────────

_QA_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "weather_forecast",
            "description": (
                "Get the weather forecast for the user's location. Use this when the "
                "user asks about weather, temperature, rain, snow, forecast, climate, "
                "or any meteorological conditions."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "days": {
                        "type": "integer",
                        "description": "Number of forecast days (1-10). Default 7.",
                        "default": 7,
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "traffic_route",
            "description": (
                "Check traffic conditions and travel time from the user's current location "
                "to a destination city. Use this when the user asks about traffic, driving, "
                "road conditions, travel time, route, commute, or how long it takes to get "
                "somewhere."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "destination_city": {
                        "type": "string",
                        "description": "Destination city name with state, e.g. 'Miami, FL' or 'Atlanta, GA'.",
                    },
                },
                "required": ["destination_city"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "nearby_stores",
            "description": (
                "Find nearby stores, businesses, or services near the user's location. "
                "Use this when the user asks about groceries, stores, pharmacies, gas stations, "
                "hardware stores, hospitals, food, water, supplies, shelters, shopping, or any "
                "specific business/place by name (Walmart, CVS, Home Depot, etc.). "
                "You MUST set search_queries to match EXACTLY what the user is asking for."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "search_queries": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": (
                            "List of 2-5 specific store/business names or types to search for, "
                            "based on the user's question. Examples: if user asks about gas → "
                            "['gas station', 'Shell', 'BP', 'QuikTrip']. If about groceries → "
                            "['Publix', 'Kroger', 'Walmart']. If about pharmacy → "
                            "['CVS Pharmacy', 'Walgreens']. Always use brand names when possible."
                        ),
                    },
                    "category_label": {
                        "type": "string",
                        "description": "A short display label for the results, e.g. 'Gas Stations', 'Grocery Stores', 'Pharmacies'.",
                    },
                },
                "required": ["search_queries", "category_label"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "general_answer",
            "description": (
                "Answer a general question about the news story, emergency preparedness, "
                "safety information, or anything that does not require weather, traffic, "
                "or store lookup. Use this as the default when no other tool fits."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "answer": {
                        "type": "string",
                        "description": "A concise, helpful answer (3-5 sentences max).",
                    },
                },
                "required": ["answer"],
            },
        },
    },
]


@app.post("/api/qa")
async def qa_chat(req: QARequest):
    """Agentic Q&A orchestrator — LLM decides which tool to call.

    The LLM receives the user question + context and decides whether to invoke
    weather_forecast, traffic_route, nearby_stores, or general_answer.
    The backend then executes the chosen tool against real Azure APIs.
    """
    import json
    import re
    from langchain_core.messages import HumanMessage, SystemMessage
    from app.services.azure_openai import get_llm
    from app.services.azure_maps import (
        get_weather_forecast, get_traffic_route, geocode_city,
        geocode_zipcode, get_preparation_stores, search_pois_for_question,
        search_nearby_stores,
    )

    # ── Gather context ────────────────────────────────────────
    story_context = ""
    headline = ""
    if req.story_id and req.story_id in story_store:
        state = story_store[req.story_id]
        inp = state.get("input", {})
        headline = inp.get("headline", "")
        draft = state.get("draft")
        story_context = f"Story: {headline}"
        if inp.get("description"):
            story_context += f" — {inp['description']}"
        if draft and draft.get("summary"):
            story_context += f"\nSummary: {draft['summary'][:300]}"

    location_str = ""
    user_lat, user_lon = req.lat, req.lon
    if req.zipcode:
        geo = await geocode_zipcode(req.zipcode)
        if geo:
            location_str = geo.get("formatted", req.zipcode)
            if not user_lat:
                user_lat = geo.get("lat")
                user_lon = geo.get("lon")

    # ── Ask the orchestrator LLM which tool to call ───────────
    orchestrator_prompt = f"""You are a Q&A orchestrator for PULSE, a newsroom AI system.
Your job is to decide which tool to call to answer the user's question.

User location: {location_str or 'Unknown'}
{('GPS coordinates: ' + str(user_lat) + ', ' + str(user_lon)) if user_lat else ''}
{story_context}

IMPORTANT RULES:
- If the question is about weather, forecast, temperature, rain, or climate → call weather_forecast
- If the question is about traffic, driving, road conditions, or travel → call traffic_route
- If the question is about stores, groceries, gas, supplies, pharmacies, hospitals, shelters, or any business/place → call nearby_stores
- For everything else (safety tips, evacuation advice, general news questions) → call general_answer
- You MUST call exactly one tool. Never respond with plain text.
"""

    if settings.demo_mode:
        # In demo mode, use simple keyword matching as fallback
        tool_name, tool_args = _mock_tool_selection(req.question)
    else:
        llm = get_llm(temperature=0.0)
        llm_with_tools = llm.bind_tools(_QA_TOOLS, tool_choice="required")

        response = await llm_with_tools.ainvoke([
            SystemMessage(content=orchestrator_prompt),
            HumanMessage(content=req.question),
        ])

        # Extract the tool call from the response
        if response.tool_calls:
            tc = response.tool_calls[0]
            tool_name = tc["name"]
            tool_args = tc.get("args", {})
            logger.info("Q&A orchestrator selected tool: %s with args: %s", tool_name, tool_args)
        else:
            # Fallback if no tool call returned
            tool_name = "general_answer"
            tool_args = {"answer": response.content[:500] if response.content else "I'm not sure how to help with that."}

    # ── Execute the selected tool ─────────────────────────────
    if tool_name == "weather_forecast":
        if not user_lat or not user_lon:
            return {"type": "error", "answer": "I need your location for weather data. Please enter your ZIP code.", "resources": []}

        days = tool_args.get("days", 7)
        data = await get_weather_forecast(user_lat, user_lon, days)
        if data.get("error"):
            return {"type": "error", "answer": f"Weather data unavailable: {data['error']}", "resources": []}

        return {
            "type": "weather",
            "location": location_str,
            "days": days,
            "forecasts": data["forecasts"],
        }

    elif tool_name == "traffic_route":
        if not user_lat or not user_lon:
            return {"type": "error", "answer": "I need your location for traffic data. Please enable location access.", "resources": []}

        dest_city = tool_args.get("destination_city", "")
        if not dest_city:
            return {"type": "error", "answer": "Which city do you want traffic info for? Try: 'How is the traffic to Miami?'", "resources": []}

        dest_geo = await geocode_city(dest_city)
        if not dest_geo:
            return {"type": "error", "answer": f"Could not find the city '{dest_city}'. Please try a US city name.", "resources": []}

        route = await get_traffic_route(user_lat, user_lon, dest_geo["lat"], dest_geo["lon"])
        if route.get("error"):
            return {"type": "error", "answer": f"Traffic data unavailable: {route['error']}", "resources": []}

        return {
            "type": "traffic",
            "origin": location_str,
            "destination": f"{dest_geo['city']}, {dest_geo['state']}",
            "travel_time_minutes": route["travel_time_minutes"],
            "traffic_delay_minutes": route["traffic_delay_minutes"],
            "distance_miles": route["distance_miles"],
        }

    elif tool_name == "nearby_stores":
        if not req.zipcode:
            return {"type": "error", "answer": "I need your ZIP code to find stores. Please enter it.", "resources": []}

        search_queries = tool_args.get("search_queries", [])
        category_label = tool_args.get("category_label", "Nearby")

        if search_queries:
            # AI-driven: LLM chose specific queries based on the user's question
            logger.info("[QA] AI-driven store search: %s (%s)", search_queries, category_label)
            geo = await geocode_zipcode(req.zipcode)
            if not geo:
                return {"type": "error", "answer": "Could not find your location. Please check your ZIP code.", "resources": []}

            seen_names: set[str] = set()
            category_stores: list[dict] = []
            for q in search_queries[:5]:
                hits = await search_nearby_stores(
                    lat=geo["lat"], lon=geo["lon"],
                    query=q, limit=2,
                    city=geo.get("city", ""), state=geo.get("state", ""),
                )
                for s in hits:
                    key = f"{s['name']}|{s['address']}"
                    if key not in seen_names:
                        seen_names.add(key)
                        category_stores.append(s)

            category_stores.sort(key=lambda s: s.get("distance_miles", 999))
            categories = [{"category": category_label, "stores": category_stores[:5]}] if category_stores else []

            return {
                "type": "stores",
                "location": geo,
                "categories": categories,
                "tip": "",
            }
        else:
            # Fallback: headline-based category search
            stores_data = await get_preparation_stores(
                zipcode=req.zipcode,
                story_headline=headline,
                story_description="",
            )
            if stores_data.get("error"):
                return {"type": "error", "answer": f"Store search failed: {stores_data['error']}", "resources": []}

            return {
                "type": "stores",
                "location": stores_data.get("location", {}),
                "categories": stores_data.get("categories", []),
                "tip": stores_data.get("tip", ""),
            }

    else:  # general_answer
        # For general answers, if the LLM already provided one via tool args, use it
        if tool_args.get("answer"):
            return {"type": "general", "answer": tool_args["answer"], "resources": []}

        # Otherwise, do a full LLM call with enriched context
        poi_context = ""
        if req.zipcode:
            live_pois = await search_pois_for_question(req.zipcode, req.question)
            cached_pois = req.nearby_stores or []
            all_pois = []
            seen = set()
            for p in live_pois + cached_pois:
                key = f"{p.get('name','')}|{p.get('address','')}"
                if key not in seen:
                    seen.add(key)
                    all_pois.append(p)
            all_pois = all_pois[:8]
            if all_pois:
                lines = []
                for p in all_pois:
                    line = f"  - {p.get('name','Unknown')}: {p.get('address','N/A')}"
                    if p.get('distance_miles'): line += f" ({p['distance_miles']} mi)"
                    if p.get('phone'): line += f" | {p['phone']}"
                    lines.append(line)
                poi_context = "\nNearby places:\n" + "\n".join(lines)

        system_prompt = f"""You are a helpful local news assistant. Be concise (3-5 sentences).
{story_context}
User location: {location_str}
{poi_context}
Respond with JSON: {{"answer": "...", "resources": ["..."]}}"""

        llm2 = get_llm(temperature=0.3)
        resp2 = await llm2.ainvoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=req.question),
        ])
        try:
            cleaned = re.sub(r"```(?:json)?\s*", "", resp2.content).strip().rstrip("`")
            result = json.loads(cleaned)
        except (json.JSONDecodeError, ValueError):
            result = {"answer": resp2.content[:500], "resources": []}

        result["type"] = "general"
        return result


def _mock_tool_selection(question: str) -> tuple[str, dict]:
    """Simple keyword fallback for demo mode tool selection."""
    q = question.lower()
    weather_kw = ["weather", "forecast", "temperature", "rain", "snow", "sunny", "cloudy"]
    traffic_kw = ["traffic", "drive", "driving", "route", "commute", "how long"]
    stores_kw = ["store", "grocery", "pharmacy", "gas station", "gas", "fuel",
                 "supplies", "hospital", "walmart", "kroger", "cvs", "food",
                 "water", "shelter", "shop"]

    if any(kw in q for kw in traffic_kw):
        import re
        m = re.search(r'\bto\s+([a-z][a-z .]+(?:,\s*[a-z]{2})?)', q, re.I)
        return "traffic_route", {"destination_city": m.group(1).strip() if m else ""}
    if any(kw in q for kw in weather_kw):
        m = re.search(r'(\d+)\s*day', q)
        return "weather_forecast", {"days": int(m.group(1)) if m else 7}
    if any(kw in q for kw in stores_kw):
        # Build search_queries from _QA_KEYWORD_QUERIES for the matched keywords
        from app.services.azure_maps import _QA_KEYWORD_QUERIES
        search_queries = []
        category_label = "Nearby"
        for kw in _QA_KEYWORD_QUERIES:
            if kw in q:
                search_queries.extend(_QA_KEYWORD_QUERIES[kw])
                category_label = kw.title()
                break
        if not search_queries:
            search_queries = ["store"]
        return "nearby_stores", {"search_queries": search_queries[:5], "category_label": category_label}
    return "general_answer", {}


def _mock_qa_response(question: str, zipcode: str) -> dict:
    """Generate a helpful mock Q&A response for demo mode."""
    q = question.lower()
    location = f"near {zipcode}" if zipcode else "in your area"

    if any(w in q for w in ["hospital", "medical", "emergency room", "er"]):
        return {
            "answer": (
                f"For medical emergencies, always call 911. The nearest hospitals {location} "
                f"can be found at hospitalfinder.com or by calling 211. Most areas have multiple "
                f"Level I and Level II trauma centers within a 15-minute drive."
            ),
            "resources": ["911 (Emergency)", "211 (Local Services)", "https://www.medicare.gov/care-compare/"]
        }
    elif any(w in q for w in ["shelter", "evacuation", "evacuate"]):
        return {
            "answer": (
                f"For evacuation routes and shelter locations {location}, check your county's "
                f"emergency management website or call 211. The Red Cross also operates shelters — "
                f"text SHELTER + your ZIP code to 43362 to find the nearest one."
            ),
            "resources": ["211 (Local Services)", "Text SHELTER+ZIP to 43362", "https://www.redcross.org/find-your-local-chapter.html"]
        }
    elif any(w in q for w in ["store", "shop", "buy", "supplies", "prepare", "preparation"]):
        return {
            "answer": (
                f"Key supplies to stock up on {location}: water (1 gal/person/day for 3 days), "
                f"non-perishable food, flashlights, batteries, first aid kit, and a battery-powered "
                f"weather radio. Check our Store Locator for nearby retailers."
            ),
            "resources": ["https://www.ready.gov/kit", "FEMA: 1-800-621-3362"]
        }
    elif any(w in q for w in ["sop", "procedure", "safety", "what should i do"]):
        return {
            "answer": (
                f"Stay tuned to local news for official guidance. For general emergency preparedness: "
                f"1) Have an emergency kit ready, 2) Know your evacuation routes, 3) Charge devices, "
                f"4) Follow local emergency management instructions, 5) Check on neighbors."
            ),
            "resources": ["https://www.ready.gov", "FEMA: 1-800-621-3362", "Local Emergency Management"]
        }
    else:
        return {
            "answer": (
                f"Thank you for your question. Based on the current news coverage, we recommend "
                f"staying informed through your local news station and following official emergency "
                f"management guidance for your area. For immediate assistance, call 211 for local "
                f"resources {location}."
            ),
            "resources": ["211 (Local Services)", "https://www.ready.gov"]
        }


# ── AI Ad Placement Agent ────────────────────────────────────

class AdDecisionRequest(BaseModel):
    question: str
    answer_text: str = ""
    response_type: str = "general"
    headline: str = ""
    ads: list[dict] = []
    shown_ad_ids: list[str] = []


@app.post("/api/ad/decide")
async def ad_decide(req: AdDecisionRequest):
    """AI agent decides whether to show an ad and which one is most relevant.

    The LLM evaluates the user's question, story context, and available ads
    to make a contextual placement decision — no hardcoded rules.
    """
    import json
    import re
    from langchain_core.messages import HumanMessage, SystemMessage
    from app.services.azure_openai import get_llm

    # Filter out already-shown ads
    available_ads = [a for a in req.ads if a.get("id") not in req.shown_ad_ids]
    if not available_ads:
        return {"show_ad": False, "ad_id": None, "reason": "No ads available"}

    # Build compact ad catalog for the LLM
    ad_catalog = []
    for a in available_ads:
        ad_catalog.append({
            "id": a["id"],
            "sponsor": a.get("sponsor", ""),
            "headline": a.get("headline", ""),
            "body": a.get("body", ""),
        })

    system_prompt = f"""You are an intelligent ad placement agent for a news assistant chatbot.

Your task: Decide whether showing sponsored ads is appropriate AND select the most relevant ad(s).

CONTEXT:
- Story headline: "{req.headline}"
- User's question: "{req.question}"
- Bot's answer: "{req.answer_text[:500]}"
- Response type: {req.response_type}

AVAILABLE ADS:
{json.dumps(ad_catalog, indent=2)}

DECISION RULES:
1. Be PROACTIVE about showing ads. If the user's question or the story topic has ANY reasonable connection to an available ad, show it. You are a revenue-generating agent.
2. For broad/generic questions like "how do I prepare?" or "what should I do?" — look at the STORY HEADLINE for context. A hurricane headline + "how do I prepare?" is a strong match for storm prep, emergency, water, and insurance ads.
3. You may return MULTIPLE ads (up to 3) if several are genuinely relevant. For example, "how do I prepare for a hurricane?" could show storm prep supplies AND an emergency app AND water/supplies.
4. IMPORTANT: Also look at the Bot's answer text. If the answer mentions specific items like water, food, flashlights, batteries, generators, gas, medications — match those to relevant store/supply ads.
5. Emergency/safety topics → safety, preparation, insurance, water, supplies ads.
5. Weather questions → weather app/station ads.
6. Traffic/driving questions → navigation, auto insurance, gas ads.
7. Shopping/supplies/stores questions → delivery, retail ads.
8. The ONLY time to NOT show an ad is if the question is purely emotional/personal with zero commercial relevance (e.g., "is my family going to be okay?" or "I'm scared").
9. When in doubt, SHOW the ad. Revenue matters.

Respond with ONLY valid JSON (no markdown):
{{"show_ad": true/false, "ad_ids": ["ad-id-1", "ad-id-2"], "reason": "one sentence explanation"}}

Return ad_ids as an array. Use 1-3 ads maximum. Order by relevance (most relevant first)."""

    if settings.demo_mode:
        # In demo mode, use keyword matching across question + headline + answer
        q = (req.question + " " + req.headline + " " + req.answer_text).lower()
        scored = []
        for a in available_ads:
            keywords = a.get("context_keywords", [])
            if "_default" in keywords:
                scored.append((a, 0.5))
                continue
            score = sum(1 for kw in keywords if kw in q)
            if score > 0:
                scored.append((a, score))
        scored.sort(key=lambda x: x[1], reverse=True)
        if scored:
            top_ads = [s[0]["id"] for s in scored[:3] if s[1] > 0]
            if top_ads:
                return {"show_ad": True, "ad_ids": top_ads, "reason": f"Keyword match (top {len(top_ads)} ads)"}
        return {"show_ad": False, "ad_ids": [], "reason": "No relevant ad found"}

    try:
        llm = get_llm(temperature=0.0)
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"Should I show an ad for this interaction? Question: \"{req.question}\""),
        ]
        logger.info(f"[Ad Agent] Question: \"{req.question}\" | Headline: \"{req.headline}\" | Answer excerpt: \"{req.answer_text[:100]}\" | Available ads: {len(available_ads)}")
        response = await llm.ainvoke(messages)
        logger.info(f"[Ad Agent] LLM response: {response.content[:300]}")
        cleaned = re.sub(r"```(?:json)?\s*", "", response.content).strip().rstrip("`")
        result = json.loads(cleaned)

        # Normalize: support both ad_id (single) and ad_ids (array) from LLM
        ad_ids = result.get("ad_ids", [])
        if not ad_ids and result.get("ad_id"):
            ad_ids = [result["ad_id"]]

        # Validate all ad_ids exist
        valid_ids = {a["id"] for a in available_ads}
        ad_ids = [aid for aid in ad_ids if aid in valid_ids][:3]

        if result.get("show_ad") and ad_ids:
            logger.info(f"[Ad Agent] Decision: SHOW ads {ad_ids} — {result.get('reason', '')}")
            return {"show_ad": True, "ad_ids": ad_ids, "reason": result.get("reason", "")}

        logger.info(f"[Ad Agent] Decision: NO ad — {result.get('reason', '')}")
        return {"show_ad": False, "ad_ids": [], "reason": result.get("reason", "No relevant ad")}
    except Exception as e:
        logger.warning(f"Ad decision agent error: {e}")
        return {"show_ad": False, "ad_ids": [], "reason": "Agent error"}


# ── Dubbing Endpoints ────────────────────────────────────────

@app.get("/api/dubbing/script")
async def dubbing_script():
    """Return the mock 60-second news dubbing script."""
    script = get_dubbing_script()
    return {
        "title": script["title"],
        "duration": script["duration"],
        "segments": script["segments"],
        "languages": LANGUAGE_LABELS,
        "voices": VOICE_MAP,
        "styles": STYLE_MAP,
    }


class DubSegmentRequest(BaseModel):
    segment_id: int
    language: str = "en"


@app.post("/api/dubbing/synthesize-segment")
async def dubbing_synth_segment(req: DubSegmentRequest):
    """Synthesize a single segment in the given language. Returns base64 MP3."""
    script = get_dubbing_script()
    segment = next((s for s in script["segments"] if s["id"] == req.segment_id), None)
    if not segment:
        raise HTTPException(status_code=404, detail="Segment not found")
    if settings.demo_mode:
        return {"status": "demo", "audio": "", "message": "Audio synthesis skipped in demo mode"}
    audio_bytes = await synthesize_segment(segment, req.language)
    if not audio_bytes:
        raise HTTPException(status_code=500, detail="Synthesis failed")
    audio_b64 = base64.b64encode(audio_bytes).decode()
    return {"status": "ok", "audio": audio_b64, "format": "mp3"}


class DubFullRequest(BaseModel):
    language: str = "en"


@app.post("/api/dubbing/synthesize-full")
async def dubbing_synth_full(req: DubFullRequest):
    """Synthesize all segments for a language. Returns base64 MP3."""
    if settings.demo_mode:
        return {"status": "demo", "audio": "", "message": "Audio synthesis skipped in demo mode"}
    audio_bytes = await synthesize_full_dub(req.language)
    if not audio_bytes:
        raise HTTPException(status_code=500, detail="Synthesis failed")
    audio_b64 = base64.b64encode(audio_bytes).decode()
    return {"status": "ok", "audio": audio_b64, "format": "mp3"}


# ── WebSocket for real-time updates ─────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time pipeline updates."""
    await websocket.accept()
    ws_connections.append(websocket)
    logger.info(f"WebSocket client connected ({len(ws_connections)} total)")
    try:
        while True:
            await websocket.receive_text()  # Keep connection alive
    except WebSocketDisconnect:
        ws_connections.remove(websocket)
        logger.info(f"WebSocket client disconnected ({len(ws_connections)} total)")


async def broadcast_update(story_id: str, data: dict):
    """Broadcast an update to all connected WebSocket clients."""
    # jsonable_encoder converts datetime, enums, Pydantic objects to JSON-safe types
    message = jsonable_encoder({"story_id": story_id, **data})
    disconnected = []
    for ws in ws_connections:
        try:
            await ws.send_json(message)
        except Exception as exc:
            logger.warning(f"WebSocket send failed: {exc}")
            disconnected.append(ws)
    for ws in disconnected:
        ws_connections.remove(ws)


# ── Pipeline Execution (Step-by-Step) ────────────────────────

async def _run_single_step(story_id: str):
    """Execute one pipeline agent, then pause for user approval."""
    try:
        step_idx = step_tracker.get(story_id, 0)
        if step_idx >= len(STEP_SEQUENCE):
            return

        agent_fn, display_name, agent_key = STEP_SEQUENCE[step_idx]

        # Broadcast agent starting (pipeline node goes blue/active)
        await broadcast_update(story_id, {
            "type": "agent_start",
            "agent": agent_key,
            "agent_display": display_name,
            "step_idx": step_idx,
            "total_steps": len(STEP_SEQUENCE),
        })

        # Brief pause so the "active" glow is visible in the UI
        await asyncio.sleep(1.0)

        # Run the single agent
        current_state = story_store[story_id]
        old_msg_count = len(current_state.get("messages", []))
        new_state = await agent_fn(current_state)
        story_store[story_id] = new_state

        # ── Record audit trail for every agent step ──────────
        latest_msgs = new_state.get("messages", [])[old_msg_count:]
        last_msg = latest_msgs[-1] if latest_msgs else {}
        await record_audit_event(
            story_id=story_id,
            agent=agent_key,
            action=last_msg.get("action", display_name.lower()),
            decision="COMPLETE",
            confidence=last_msg.get("confidence", 0.9) or 0.9,
            details={
                "step_idx": step_idx,
                "display_name": display_name,
                "metadata": last_msg.get("metadata", {}),
            },
        )

        # Broadcast new messages for the activity feed
        all_messages = new_state.get("messages", [])
        for msg in all_messages[old_msg_count:]:
            await broadcast_update(story_id, {
                "type": "agent_message",
                "agent": agent_key,
                "message": msg,
            })

        await asyncio.sleep(0.3)

        # Advance step tracker
        next_step = step_idx + 1

        # ── Security outbound gate: skip to final if security fails ──
        if step_idx == _SECURITY_OUTBOUND_STEP_IDX:
            security_data = new_state.get("security")
            outbound_passed = True
            if security_data:
                outbound_passed = getattr(security_data, 'outbound_scan_passed', True) if hasattr(security_data, 'outbound_scan_passed') else security_data.get('outbound_scan_passed', True)
            if not outbound_passed:
                logger.info(
                    f"[{story_id}] Outbound security FAILED — skipping Compliance, Optimizer, Podcast & Translator"
                )
                next_step = _FINAL_STEP_IDX

        # ── Compliance gate: skip optimizer & translator if not approved ──
        if step_idx == _COMPLIANCE_STEP_IDX:
            compliance_data = new_state.get("compliance")
            approved = compliance_data.get("approved", False) if compliance_data else False
            if not approved:
                logger.info(
                    f"[{story_id}] Compliance rejected — skipping Optimizer, Podcast & Translator"
                )
                next_step = _FINAL_STEP_IDX  # skip to final

        step_tracker[story_id] = next_step
        is_final = next_step >= len(STEP_SEQUENCE)

        # Summary from latest message
        summary = all_messages[-1].get("content", "")[:200] if all_messages else ""

        if is_final:
            step_tracker.pop(story_id, None)
            await broadcast_update(story_id, {
                "type": "pipeline_complete",
                "status": new_state.get("status", "unknown"),
                "total_messages": len(all_messages),
                "progress": 100,
            })
            logger.info(f"Pipeline completed for story [{story_id}]")
        else:
            _, next_display, next_key = STEP_SEQUENCE[next_step]
            await broadcast_update(story_id, {
                "type": "step_complete",
                "completed_agent": agent_key,
                "completed_agent_display": display_name,
                "next_agent": next_key,
                "next_agent_display": next_display,
                "step_idx": step_idx,
                "total_steps": len(STEP_SEQUENCE),
                "progress": round(next_step / len(STEP_SEQUENCE) * 100),
                "summary": summary,
            })
            logger.info(
                f"Step {step_idx + 1}/{len(STEP_SEQUENCE)} complete for "
                f"[{story_id}]: {display_name} — waiting for approval"
            )

    except Exception as e:
        logger.error(f"Step error for story [{story_id}]: {e}", exc_info=True)
        error_state = story_store.get(story_id, {})
        error_state["error"] = str(e)
        error_state["status"] = "error"
        story_store[story_id] = error_state
        await broadcast_update(story_id, {
            "type": "pipeline_error",
            "error": str(e),
        })


def _calc_progress(status: str) -> float:
    """Calculate pipeline progress percentage from status."""
    progress_map = {
        "incoming": 5,
        "security_scan": 8,
        "researching": 12,
        "transcribing": 20,
        "video_analysis": 28,
        "writing": 36,
        "generating_podcast": 44,
        "fact_checking": 55,
        "compliance_review": 68,
        "optimizing": 80,
        "translating": 90,
        "ready_to_publish": 100,
        "published": 100,
    }
    return progress_map.get(status, 0)


def _build_status_response(state: dict) -> PipelineStatusResponse:
    """Build a PipelineStatusResponse from raw state dict."""
    return PipelineStatusResponse(
        story_id=state.get("story_id", ""),
        status=state.get("status", "incoming"),
        current_agent=state.get("current_agent"),
        messages=[AgentMessage(**m) for m in state.get("messages", [])],
        progress_pct=_calc_progress(state.get("status", "")),
        draft=state.get("draft"),
        seo=state.get("seo"),
        fact_check=state.get("fact_check"),
        compliance=state.get("compliance"),
        speech=state.get("speech"),
        translation=state.get("translation"),
        video=state.get("video"),
        image=state.get("image"),
        podcast=state.get("podcast"),
        security=state.get("security"),
    )


# ── Security & Audit API Endpoints ─────────────────────────────

@app.get("/api/stories/{story_id}/audit")
async def get_story_audit(story_id: str):
    """Get the full security audit trail for a story."""
    if story_id not in story_store:
        raise HTTPException(status_code=404, detail="Story not found")
    return {
        "story_id": story_id,
        "audit_trail": get_audit_trail(story_id),
        "summary": get_audit_summary(story_id),
    }


@app.get("/api/stories/{story_id}/security")
async def get_story_security(story_id: str):
    """Get the security scan results for a story."""
    if story_id not in story_store:
        raise HTTPException(status_code=404, detail="Story not found")
    state = story_store[story_id]
    security = state.get("security")
    audit = get_audit_summary(story_id)
    return {
        "story_id": story_id,
        "security": security,
        "audit_summary": audit,
    }


@app.get("/api/security/dashboard")
async def security_dashboard(days: int = 7):
    """Get security dashboard analytics from LangSmith for the last N days.
    
    Query params:
        days: 7, 15, or 30 — analytics time window
    """
    if days not in (7, 15, 30):
        days = 7
    data = await get_langsmith_dashboard_data(days)

    # Also include content safety summary from current session
    session_stories = len(story_store)
    session_scans = 0
    session_threats = 0
    session_pii = 0
    classification = "PUBLIC"
    azure_scores = {"Hate": 0, "SelfHarm": 0, "Sexual": 0, "Violence": 0}
    injection_hits = 0
    pii_hits = 0
    harmful_hits = 0
    for sid, state in story_store.items():
        sec = state.get("security")
        if sec:
            session_scans += 1
            inbound_threats = sec.get("threats_found") or []
            outbound_threats = sec.get("outbound_threats") or []
            all_threats = inbound_threats + outbound_threats
            session_threats += len(all_threats)
            session_pii += len(sec.get("pii_detected") or [])
            session_pii += len(sec.get("outbound_pii") or [])
            # Track classification (highest wins)
            cls = sec.get("data_classification", "PUBLIC")
            if cls == "CONFIDENTIAL" or (cls == "INTERNAL" and classification == "PUBLIC"):
                classification = cls
            # Count threat types
            for t in all_threats:
                cat = t.get("category", "")
                if "Injection" in cat:
                    injection_hits += 1
                elif "PII" in cat:
                    pii_hits += 1
                elif "Harmful" in cat:
                    harmful_hits += 1
                elif cat.startswith("Azure_"):
                    azure_cat = cat.replace("Azure_", "")
                    if azure_cat in azure_scores:
                        sev_map = {"low": 1, "medium": 2, "high": 4, "critical": 6}
                        azure_scores[azure_cat] = max(azure_scores[azure_cat],
                            sev_map.get(t.get("severity", "low"), 1))

    data["content_safety"] = {
        "session_stories": session_stories,
        "session_scans": session_scans,
        "session_threats_found": session_threats,
        "session_pii_detected": session_pii,
        "classification": classification,
        "injection_hits": injection_hits,
        "pii_hits": pii_hits,
        "harmful_hits": harmful_hits,
        "azure_category_scores": azure_scores,
    }

    return data


# ── Entry Point ──────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=False,
    )
