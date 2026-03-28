"""
PULSE - Azure AI Avatar Service
Provides speech token, ICE credentials, and avatar connection management.
Uses Azure RBAC (DefaultAzureCredential) — no API keys required.
Required Role: "Cognitive Services Speech User" on the Speech resource.

Architecture follows the server-side avatar pattern:
  - Server manages SpeechSynthesizer + avatar WebRTC signaling
  - Client only manages RTCPeerConnection + video rendering
"""

import json
import logging
import threading
import time
from typing import Optional

import azure.cognitiveservices.speech as speechsdk
import requests
from azure.identity import DefaultAzureCredential

from app.config import settings

logger = logging.getLogger("pulse.azure_avatar")

# ── Global token state (refreshed in background threads) ─────
_speech_token: Optional[str] = None
_ice_token: Optional[str] = None
_avatar_speech_token: Optional[str] = None  # separate token for avatar resource
_avatar_ice_token: Optional[str] = None    # separate ICE token for avatar resource
_credential = DefaultAzureCredential()

# ── Per-client avatar sessions ───────────────────────────────
avatar_sessions: dict[str, dict] = {}  # client_id → session state


def _has_avatar_resource() -> bool:
    """Return True if a separate avatar speech resource is configured."""
    cfg = settings.azure_avatar_speech
    return bool(cfg.endpoint and cfg.region)


# ── Token refresh ────────────────────────────────────────────

def _refresh_speech_token() -> None:
    """Refresh the speech token every 9 minutes (tokens expire in 10 min).

    Uses STS token exchange when a custom domain endpoint is configured,
    otherwise falls back to the aad# format for regional endpoints.
    """
    global _speech_token
    region = settings.azure_speech.region
    endpoint = settings.azure_speech.endpoint
    resource_url = settings.azure_speech.resource_url

    while True:
        try:
            token = _credential.get_token("https://cognitiveservices.azure.com/.default")

            if endpoint:
                # Custom domain → exchange AAD token for STS speech token
                sts_url = f"{endpoint.rstrip('/')}/sts/v1.0/issueToken"
                resp = requests.post(sts_url, headers={
                    "Authorization": f"Bearer {token.token}",
                    "Content-Length": "0",
                })
                resp.raise_for_status()
                _speech_token = resp.text
                logger.info("Speech token refreshed via STS (endpoint=%s)", endpoint)
            elif resource_url:
                # Regional + RBAC: aad#{resourceUrl}#{rawToken}
                _speech_token = f"aad#{resource_url}#{token.token}"
                logger.info("Speech token refreshed (region=%s)", region)
            else:
                _speech_token = token.token
                logger.info("Speech token refreshed (region=%s)", region)
        except Exception as e:
            logger.error("Failed to refresh speech token: %s", e)
        time.sleep(60 * 9)


def _get_sts_token(endpoint_override: str = "") -> str:
    """Exchange an AAD token for an STS speech token via the custom domain."""
    endpoint = (endpoint_override or settings.azure_speech.endpoint).rstrip("/")
    aad_token = _credential.get_token("https://cognitiveservices.azure.com/.default")
    sts_url = f"{endpoint}/sts/v1.0/issueToken"
    resp = requests.post(sts_url, headers={
        "Authorization": f"Bearer {aad_token.token}",
        "Content-Length": "0",
    })
    resp.raise_for_status()
    return resp.text


def _refresh_ice_token() -> None:
    """Refresh the ICE/TURN relay token every 24 hours."""
    global _ice_token
    region = settings.azure_speech.region
    endpoint = settings.azure_speech.endpoint  # custom domain, e.g. https://xyz.cognitiveservices.azure.com/

    while True:
        try:
            # Wait for speech token to be available first
            while not _speech_token:
                time.sleep(0.5)

            # Use custom domain endpoint for the relay URL
            if endpoint:
                base = endpoint.rstrip("/")
                url = f"{base}/tts/cognitiveservices/avatar/relay/token/v1"
            else:
                url = f"https://{region}.tts.speech.microsoft.com/cognitiveservices/avatar/relay/token/v1"

            # The relay endpoint requires an STS token (exchange AAD → STS first)
            sts_token = _get_sts_token()

            resp = requests.get(url, headers={"Authorization": f"Bearer {sts_token}"})
            if resp.status_code == 200:
                _ice_token = resp.text
                logger.info("ICE relay token refreshed")
            else:
                logger.error("ICE token request failed: %s %s", resp.status_code, resp.text[:200])
        except Exception as e:
            logger.error("Failed to refresh ICE token: %s", e)
        time.sleep(60 * 60 * 24)


def _refresh_avatar_speech_token() -> None:
    """Refresh the speech token for the dedicated Avatar speech resource."""
    global _avatar_speech_token
    if not _has_avatar_resource():
        return
    avatar_cfg = settings.azure_avatar_speech
    while True:
        try:
            token = _credential.get_token("https://cognitiveservices.azure.com/.default")
            sts_url = f"{avatar_cfg.endpoint.rstrip('/')}/sts/v1.0/issueToken"
            resp = requests.post(sts_url, headers={
                "Authorization": f"Bearer {token.token}",
                "Content-Length": "0",
            })
            resp.raise_for_status()
            _avatar_speech_token = resp.text
            logger.info("Avatar speech token refreshed via STS (endpoint=%s)", avatar_cfg.endpoint)
        except Exception as e:
            logger.error("Failed to refresh avatar speech token: %s", e)
        time.sleep(60 * 9)


def _refresh_avatar_ice_token() -> None:
    """Refresh the ICE/TURN relay token for the dedicated Avatar speech resource."""
    global _avatar_ice_token
    if not _has_avatar_resource():
        return
    avatar_cfg = settings.azure_avatar_speech
    while True:
        try:
            while not _avatar_speech_token:
                time.sleep(0.5)
            base = avatar_cfg.endpoint.rstrip("/")
            url = f"{base}/tts/cognitiveservices/avatar/relay/token/v1"
            sts_token = _get_sts_token(avatar_cfg.endpoint)
            resp = requests.get(url, headers={"Authorization": f"Bearer {sts_token}"})
            if resp.status_code == 200:
                _avatar_ice_token = resp.text
                logger.info("Avatar ICE relay token refreshed")
            else:
                logger.error("Avatar ICE token request failed: %s %s", resp.status_code, resp.text[:200])
        except Exception as e:
            logger.error("Failed to refresh avatar ICE token: %s", e)
        time.sleep(60 * 60 * 24)


def start_token_refresh_threads() -> None:
    """Start background threads for token refresh. Call once at app startup."""
    t1 = threading.Thread(target=_refresh_speech_token, daemon=True)
    t1.start()
    t2 = threading.Thread(target=_refresh_ice_token, daemon=True)
    t2.start()
    if _has_avatar_resource():
        t3 = threading.Thread(target=_refresh_avatar_speech_token, daemon=True)
        t3.start()
        t4 = threading.Thread(target=_refresh_avatar_ice_token, daemon=True)
        t4.start()
        logger.info("Token refresh threads started (main + avatar)")
    else:
        logger.info("Token refresh threads started (avatar uses main speech resource)")


# ── Public API functions ─────────────────────────────────────

def get_speech_token_value() -> dict:
    """Return the current speech token and region for the frontend."""
    return {
        "token": _speech_token or "",
        "region": settings.azure_speech.region,
    }


def get_ice_token() -> dict:
    """Return the current ICE token (JSON) for WebRTC relay."""
    if _ice_token:
        return json.loads(_ice_token)
    return {"Urls": [], "Username": "", "Password": ""}


def get_avatar_config() -> dict:
    """Return the full avatar configuration for the frontend."""
    cfg = settings.azure_avatar
    return {
        "sttLocales": cfg.stt_locales,
        "ttsVoice": cfg.tts_voice,
        "customVoiceEndpointId": cfg.custom_voice_endpoint_id,
        "personalVoiceSpeakerProfileId": cfg.personal_voice_speaker_profile_id,
        "continuousConversation": cfg.continuous_conversation,
        "avatarCharacter": cfg.avatar_character,
        "avatarStyle": cfg.avatar_style,
        "customAvatar": cfg.custom_avatar,
        "autoReconnect": cfg.auto_reconnect,
        "useLocalVideoForIdle": cfg.use_local_video_for_idle,
        "transparentBackground": cfg.transparent_background,
        "enableOyd": cfg.enable_oyd,
        "speechRegion": settings.azure_avatar_speech.region if _has_avatar_resource() else settings.azure_speech.region,
    }


def connect_avatar(client_id: str, local_sdp: str, avatar_character: str,
                    avatar_style: str, custom_avatar: bool,
                    transparent_background: bool,
                    tts_voice: Optional[str] = None,
                    custom_voice_endpoint_id: Optional[str] = None) -> str:
    """
    Connect to the TTS Avatar service on the server side.

    1. Creates a SpeechSynthesizer with the avatar WebRTC config
    2. Sends an empty speak request to establish the connection
    3. Returns the remote SDP for the client's RTCPeerConnection
    """
    # Disconnect existing session if any
    disconnect_avatar(client_id)

    # Use dedicated avatar speech resource if configured, else fall back to main
    if _has_avatar_resource():
        region = settings.azure_avatar_speech.region
        auth_token = _avatar_speech_token
        ice_src = _avatar_ice_token
    else:
        region = settings.azure_speech.region
        auth_token = _speech_token
        ice_src = _ice_token

    cfg = settings.azure_avatar

    # Wait for the appropriate speech token
    while not auth_token:
        time.sleep(0.2)
        auth_token = _avatar_speech_token if _has_avatar_resource() else _speech_token

    # Build speech config with avatar WebSocket endpoint
    # Avatar WebSocket is only available on the regional endpoint, not custom domains.
    # Auth still uses the STS token (exchanged from AAD via the custom domain).
    ws_endpoint = f"wss://{region}.tts.speech.microsoft.com/cognitiveservices/websocket/v1?enableTalkingAvatar=true"

    speech_config = speechsdk.SpeechConfig(endpoint=ws_endpoint)
    speech_config.authorization_token = auth_token

    if custom_voice_endpoint_id:
        speech_config.endpoint_id = custom_voice_endpoint_id

    # Create speech synthesizer
    speech_synthesizer = speechsdk.SpeechSynthesizer(
        speech_config=speech_config, audio_config=None
    )

    # Parse ICE token (use avatar-specific if available)
    ice_raw = ice_src if _has_avatar_resource() else _ice_token
    ice_token_obj = json.loads(ice_raw) if ice_raw else {"Urls": [], "Username": "", "Password": ""}

    # Build avatar config for WebRTC signaling
    # Use dark background that matches the UI theme (green chromakey is unreliable in canvas)
    bg_color = "#252a3aFF" if transparent_background else "#FFFFFFFF"
    avatar_config = {
        "synthesis": {
            "video": {
                "protocol": {
                    "name": "WebRTC",
                    "webrtcConfig": {
                        "clientDescription": local_sdp,
                        "iceServers": [{
                            "urls": [ice_token_obj["Urls"][0]] if ice_token_obj.get("Urls") else [],
                            "username": ice_token_obj.get("Username", ""),
                            "credential": ice_token_obj.get("Password", ""),
                        }],
                    },
                },
                "format": {
                    "crop": {
                        "topLeft": {"x": 0, "y": 0},
                        "bottomRight": {"x": 1920, "y": 1080},
                    },
                    "bitrate": 2000000,
                },
                "talkingAvatar": {
                    "customized": custom_avatar,
                    "character": avatar_character,
                    "style": avatar_style,
                    "background": {
                        "color": bg_color,
                        "image": {"url": ""},
                    },
                },
            }
        }
    }

    # Set the avatar config on the connection
    connection = speechsdk.Connection.from_speech_synthesizer(speech_synthesizer)
    connection.set_message_property("speech.config", "context", json.dumps(avatar_config))

    # Store session state
    avatar_sessions[client_id] = {
        "speech_synthesizer": speech_synthesizer,
        "connection": connection,
        "connected": True,
        "tts_voice": tts_voice or cfg.tts_voice,
    }

    # Send empty speak to establish the WebRTC connection
    result = speech_synthesizer.speak_text_async("").get()
    logger.info("Avatar connect result ID: %s, reason: %s", result.result_id, result.reason)

    if result.reason == speechsdk.ResultReason.Canceled:
        details = result.cancellation_details
        logger.error("Avatar connection canceled: %s — %s", details.reason, details.error_details)
        raise Exception(f"Avatar connection failed: {details.error_details}")

    # Extract the remote SDP from the turn start message
    turn_start_msg = speech_synthesizer.properties.get_property_by_name(
        "SpeechSDKInternal-ExtraTurnStartMessage"
    )
    remote_sdp = json.loads(turn_start_msg)["webrtc"]["connectionString"]

    logger.info("Avatar connected for client %s", client_id)
    return remote_sdp


def speak_ssml(client_id: str, ssml: str) -> str:
    """Speak SSML through the connected avatar. Returns result ID."""
    session = avatar_sessions.get(client_id)
    if not session or not session.get("speech_synthesizer"):
        raise Exception("Avatar not connected")

    synthesizer = session["speech_synthesizer"]
    result = synthesizer.speak_ssml_async(ssml).get()

    if result.reason == speechsdk.ResultReason.Canceled:
        details = result.cancellation_details
        logger.error("Speak failed: %s — %s", details.reason, details.error_details)
        raise Exception(f"Speak failed: {details.error_details}")

    logger.info("Avatar speak result: %s", result.result_id)
    return result.result_id


def stop_speaking(client_id: str) -> None:
    """Stop the avatar from speaking."""
    session = avatar_sessions.get(client_id)
    if not session:
        return
    connection = session.get("connection")
    if connection:
        connection.send_message_async("synthesis.control", '{"action":"stop"}').get()
        logger.info("Avatar stopped speaking for client %s", client_id)


def disconnect_avatar(client_id: str) -> None:
    """Disconnect and clean up the avatar session."""
    session = avatar_sessions.pop(client_id, None)
    if not session:
        return
    connection = session.get("connection")
    synthesizer = session.get("speech_synthesizer")
    if connection:
        try:
            connection.close()
        except Exception:
            pass
    if synthesizer:
        try:
            del synthesizer
        except Exception:
            pass
    logger.info("Avatar disconnected for client %s", client_id)
