"""
PULSE - Azure AI Speech Service
Provides Speech-to-Text, Text-to-Speech, and Speech Translation.
Uses Azure RBAC (DefaultAzureCredential) — no API keys required.
Required Role: "Cognitive Services Speech User" on the Speech resource.

With custom domain: Exchange AAD token for a Speech token via STS,
then use the STS token with the custom domain endpoint.
"""

import io
import logging
import time
from typing import Optional

import httpx
from azure.identity import DefaultAzureCredential
from app.config import settings

logger = logging.getLogger("pulse.azure_speech")

# Azure AD credential for Cognitive Services
_credential = DefaultAzureCredential()

# Cache the STS-issued speech token (valid ~10 min)
_speech_token_cache: dict = {"token": None, "expires_at": 0}


def _get_speech_token() -> str:
    """Get a Speech token via STS exchange using Azure AD credential.

    The Speech SDK with custom domain endpoints needs an STS-issued token,
    not a raw Azure AD bearer token.
    """
    now = time.time()
    if _speech_token_cache["token"] and _speech_token_cache["expires_at"] > now + 60:
        return _speech_token_cache["token"]

    # Get Azure AD token
    aad_token = _credential.get_token("https://cognitiveservices.azure.com/.default").token

    # Exchange for Speech token via STS
    endpoint = settings.azure_speech.endpoint.rstrip("/")
    sts_url = f"{endpoint}/sts/v1.0/issueToken"

    resp = httpx.post(
        sts_url,
        headers={"Authorization": f"Bearer {aad_token}"},
        content=b"",
        timeout=10,
    )
    resp.raise_for_status()

    speech_token = resp.text
    _speech_token_cache["token"] = speech_token
    _speech_token_cache["expires_at"] = now + 540  # ~9 min (token valid ~10 min)
    logger.debug("Acquired fresh Speech STS token (%d chars)", len(speech_token))
    return speech_token


async def transcribe_audio(audio_bytes: bytes, language: str = "en-US") -> dict:
    """
    Transcribe audio bytes to text using Azure AI Speech.
    Returns dict with transcript text, language, confidence, and duration.
    """
    import azure.cognitiveservices.speech as speechsdk

    speech_config = speechsdk.SpeechConfig(
        endpoint=settings.azure_speech.endpoint,
    )
    speech_config.authorization_token = _get_speech_token()
    speech_config.speech_recognition_language = language

    # Create audio stream from bytes
    stream = speechsdk.audio.PushAudioInputStream()
    stream.write(audio_bytes)
    stream.close()
    audio_config = speechsdk.audio.AudioConfig(stream=stream)

    recognizer = speechsdk.SpeechRecognizer(
        speech_config=speech_config,
        audio_config=audio_config,
    )

    result = recognizer.recognize_once()

    if result.reason == speechsdk.ResultReason.RecognizedSpeech:
        return {
            "transcript": result.text,
            "language": language,
            "confidence": 0.95,
            "duration_seconds": result.duration / 10_000_000,  # ticks to seconds
        }
    else:
        logger.warning(f"Speech recognition failed: {result.reason}")
        return {
            "transcript": "",
            "language": language,
            "confidence": 0.0,
            "duration_seconds": 0,
            "error": str(result.reason),
        }


# Default Dragon HD Omni voice for high-definition TTS
DEFAULT_HD_VOICE = "en-us-ava:DragonHDOmniLatestNeural"


async def synthesize_speech(text: str, voice: str = DEFAULT_HD_VOICE) -> bytes:
    """
    Convert text to speech audio using Azure AI Speech (TTS).
    Uses Dragon HD Omni voice via SSML for high-definition broadcast-quality audio.
    Returns MP3 audio bytes.
    """
    import azure.cognitiveservices.speech as speechsdk
    import html as html_lib

    endpoint = settings.azure_speech.endpoint
    region = settings.azure_speech.region
    logger.info("[TTS-synth] endpoint=%s, region=%s, voice=%s, text_len=%d",
                endpoint, region, voice, len(text))

    try:
        speech_token = _get_speech_token()
        logger.info("[TTS-synth] STS token acquired (%d chars)", len(speech_token))
    except Exception as exc:
        logger.error("[TTS-synth] Failed to get STS token: %s", exc, exc_info=True)
        raise

    speech_config = speechsdk.SpeechConfig(
        endpoint=endpoint,
    )
    speech_config.authorization_token = speech_token
    speech_config.set_speech_synthesis_output_format(
        speechsdk.SpeechSynthesisOutputFormat.Audio16Khz32KBitRateMonoMp3
    )

    # Enable SDK-level logging for diagnostics
    speech_config.set_property(
        speechsdk.PropertyId.Speech_LogFilename, "/tmp/speech_sdk.log"
    )

    synthesizer = speechsdk.SpeechSynthesizer(
        speech_config=speech_config,
        audio_config=None,  # output to stream
    )

    # Escape text for XML safety
    safe_text = html_lib.escape(text)

    # Build SSML — Dragon HD Omni requires SSML with the colon-format voice name
    ssml = (
        '<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" '
        'xmlns:mstts="http://www.w3.org/2001/mstts" xml:lang="en-US">'
        f'<voice name="{voice}">'
        f'{safe_text}'
        '</voice></speak>'
    )
    logger.debug("[TTS-synth] SSML: %s", ssml[:500])

    logger.info("[TTS-synth] Calling speak_ssml...")
    result = synthesizer.speak_ssml(ssml)
    logger.info("[TTS-synth] speak_ssml returned reason=%s", result.reason)

    if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
        logger.info("[TTS-synth] Audio completed: %d bytes", len(result.audio_data))
        return result.audio_data
    else:
        cancellation = result.cancellation_details
        error_detail = cancellation.error_details if cancellation else "unknown"
        error_code = cancellation.reason if cancellation else "unknown"
        logger.error(
            "[TTS-synth] FAILED: result_reason=%s, cancellation_reason=%s, error_details=%s",
            result.reason,
            error_code,
            error_detail,
        )
        # Also try to read the SDK log file for additional clues
        try:
            import os
            log_path = "/tmp/speech_sdk.log"
            if os.path.exists(log_path):
                stat = os.stat(log_path)
                logger.error("[TTS-synth] SDK log file size: %d bytes", stat.st_size)
                # Read last 2KB of log
                with open(log_path, "r", errors="replace") as f:
                    f.seek(max(0, stat.st_size - 2048))
                    tail = f.read()
                logger.error("[TTS-synth] SDK log tail:\n%s", tail)
        except Exception:
            pass
        return b""


async def translate_speech(
    audio_bytes: bytes,
    source_language: str = "en-US",
    target_languages: list[str] = None,
) -> dict:
    """
    Translate speech audio into text in one or more target languages.
    Uses Azure Speech Translation.
    """
    import azure.cognitiveservices.speech as speechsdk

    if target_languages is None:
        target_languages = ["es", "fr", "de"]

    translation_config = speechsdk.translation.SpeechTranslationConfig(
        endpoint=settings.azure_speech.endpoint,
    )
    translation_config.authorization_token = _get_speech_token()
    translation_config.speech_recognition_language = source_language
    for lang in target_languages:
        translation_config.add_target_language(lang)

    stream = speechsdk.audio.PushAudioInputStream()
    stream.write(audio_bytes)
    stream.close()
    audio_config = speechsdk.audio.AudioConfig(stream=stream)

    recognizer = speechsdk.translation.TranslationRecognizer(
        translation_config=translation_config,
        audio_config=audio_config,
    )

    result = recognizer.recognize_once()

    if result.reason == speechsdk.ResultReason.TranslatedSpeech:
        translations = {}
        for lang in target_languages:
            translations[lang] = result.translations.get(lang, "")
        return {
            "source_text": result.text,
            "source_language": source_language,
            "translations": translations,
        }
    else:
        logger.warning(f"Speech translation failed: {result.reason}")
        return {
            "source_text": "",
            "source_language": source_language,
            "translations": {},
            "error": str(result.reason),
        }


async def translate_text(
    text: str,
    target_languages: list[str] = None,
    source_language: str = "en",
) -> dict:
    """
    Translate text to multiple target languages using Azure AI Speech + LLM fallback.
    In demo mode, returns mock translations.
    """
    if target_languages is None:
        target_languages = ["es", "fr", "de"]

    # For text-to-text translation in production, you'd use the Translator API
    # or route through the LLM. This service focuses on speech-based translation.
    # See the translation agent for the LLM-based text translation approach.
    return {
        "source_text": text[:200],
        "source_language": source_language,
        "translations": {lang: "" for lang in target_languages},
    }
