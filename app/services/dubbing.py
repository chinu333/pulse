"""
PULSE - News Dubbing Service
Generates a 60-second multi-voice, multi-language dubbed news script
using Azure AI Speech TTS with different voices for each speaker + language.
"""

import io
import logging
import asyncio
from dataclasses import dataclass

from app.config import settings

logger = logging.getLogger("pulse.dubbing")

# ── Voice map: role → {language: voice_name} ─────────────────
VOICE_MAP = {
    "anchor_female": {
        "en": "en-US-SaraNeural",
        "es": "es-MX-DaliaNeural",
        "fr": "fr-FR-DeniseNeural",
    },
    "reporter_male": {
        "en": "en-US-AndrewNeural",
        "es": "es-MX-JorgeNeural",
        "fr": "fr-FR-HenriNeural",
    },
    "correspondent_female": {
        "en": "en-US-JennyNeural",
        "es": "es-MX-BeatrizNeural",
        "fr": "fr-FR-EloiseNeural",
    },
}

# ── Speaking styles per role ─────────────────────────────────
STYLE_MAP = {
    "anchor_female": "newscast-formal",
    "reporter_male": "newscast-casual",
    "correspondent_female": "newscast-formal",
}

# ── 60-Second Mock Script (time-sliced segments) ─────────────
MOCK_SCRIPT = {
    "title": "Hurricane Milton — Live Coverage",
    "duration": "60 seconds",
    "segments": [
        {
            "id": 1,
            "timecode": "0:00 – 0:10",
            "role": "anchor_female",
            "label": "Anchor",
            "en": "Good evening. Breaking news tonight — Hurricane Milton has made landfall along Florida's Gulf Coast as a powerful Category 3 storm, bringing catastrophic winds and life-threatening storm surge to the Tampa Bay area.",
            "es": "Buenas noches. Noticias de última hora esta noche: el huracán Milton ha tocado tierra en la costa del Golfo de Florida como una poderosa tormenta de categoría 3, trayendo vientos catastróficos y marejada ciclónica potencialmente mortal al área de la bahía de Tampa.",
            "fr": "Bonsoir. Nouvelles de dernière heure ce soir — l'ouragan Milton a touché terre sur la côte du golfe de Floride en tant que puissante tempête de catégorie 3, apportant des vents catastrophiques et une onde de tempête mortelle dans la région de la baie de Tampa.",
        },
        {
            "id": 2,
            "timecode": "0:10 – 0:24",
            "role": "reporter_male",
            "label": "Field Reporter",
            "en": "I'm standing in downtown Sarasota where conditions have deteriorated rapidly over the past two hours. Power is out across most of the county. Emergency crews are positioned but cannot respond until winds drop below 45 miles per hour. Residents who did not evacuate are being told to shelter in interior rooms immediately.",
            "es": "Me encuentro en el centro de Sarasota donde las condiciones se han deteriorado rápidamente en las últimas dos horas. La electricidad se ha cortado en la mayor parte del condado. Los equipos de emergencia están posicionados pero no pueden responder hasta que los vientos bajen de 72 kilómetros por hora. A los residentes que no evacuaron se les pide que se refugien en habitaciones interiores de inmediato.",
            "fr": "Je suis dans le centre-ville de Sarasota où les conditions se sont détériorées rapidement au cours des deux dernières heures. L'électricité est coupée dans la majeure partie du comté. Les équipes d'urgence sont en place mais ne peuvent pas intervenir tant que les vents ne descendent pas en dessous de 72 kilomètres par heure. Les résidents qui n'ont pas évacué sont invités à se réfugier dans des pièces intérieures immédiatement.",
        },
        {
            "id": 3,
            "timecode": "0:24 – 0:36",
            "role": "correspondent_female",
            "label": "Correspondent",
            "en": "We're at Tampa General Hospital which has activated its flood barrier system. Hundreds of patients have been moved to upper floors as a precaution. Hospital officials tell us they have 72 hours of backup power and enough medical supplies to operate independently. The National Guard has stationed vehicles here for emergency evacuations if needed.",
            "es": "Estamos en el Hospital General de Tampa que ha activado su sistema de barrera contra inundaciones. Cientos de pacientes han sido trasladados a pisos superiores como precaución. Los funcionarios del hospital nos dicen que tienen 72 horas de energía de respaldo y suficientes suministros médicos para operar de forma independiente. La Guardia Nacional ha estacionado vehículos aquí para evacuaciones de emergencia si es necesario.",
            "fr": "Nous sommes à l'hôpital général de Tampa qui a activé son système de barrière anti-inondation. Des centaines de patients ont été transférés aux étages supérieurs par précaution. Les responsables de l'hôpital nous disent qu'ils disposent de 72 heures d'alimentation de secours et de suffisamment de fournitures médicales pour fonctionner de manière autonome. La Garde nationale a stationné des véhicules ici pour des évacuations d'urgence si nécessaire.",
        },
        {
            "id": 4,
            "timecode": "0:36 – 0:48",
            "role": "reporter_male",
            "label": "Field Reporter",
            "en": "Back here in Sarasota, we've been monitoring local shelters — they are at or near capacity across Sarasota and Manatee counties. The Red Cross has brought in additional cots and supplies. First responders tell me their number one concern right now is flooding from the storm surge, which could push water several miles inland.",
            "es": "Aquí en Sarasota, hemos estado monitoreando los refugios locales: están al límite o cerca de su capacidad en los condados de Sarasota y Manatee. La Cruz Roja ha traído catres y suministros adicionales. Los socorristas me dicen que su principal preocupación en este momento son las inundaciones por la marejada ciclónica, que podría empujar el agua varios kilómetros tierra adentro.",
            "fr": "Ici à Sarasota, nous surveillons les refuges locaux — ils sont pleins ou presque dans les comtés de Sarasota et Manatee. La Croix-Rouge a apporté des lits de camp et des fournitures supplémentaires. Les premiers intervenants me disent que leur principale préoccupation est l'inondation due à l'onde de tempête, qui pourrait pousser l'eau sur plusieurs kilomètres à l'intérieur des terres.",
        },
        {
            "id": 5,
            "timecode": "0:48 – 1:00",
            "role": "anchor_female",
            "label": "Anchor",
            "en": "Thank you both for those reports. The National Hurricane Center reports maximum sustained winds of 120 miles per hour. We will continue to bring you live coverage throughout the night. If you are in the evacuation zone, do not attempt to leave now — stay sheltered in place. This is a PULSE News special report.",
            "es": "Gracias a ambos por esos reportes. El Centro Nacional de Huracanes reporta vientos máximos sostenidos de 193 kilómetros por hora. Continuaremos brindándoles cobertura en vivo durante toda la noche. Si se encuentra en la zona de evacuación, no intente salir ahora — permanezca resguardado en su lugar. Este es un reporte especial de PULSE Noticias.",
            "fr": "Merci à vous deux pour ces reportages. Le Centre national des ouragans signale des vents soutenus maximaux de 193 kilomètres par heure. Nous continuerons à vous apporter une couverture en direct tout au long de la nuit. Si vous êtes dans la zone d'évacuation, ne tentez pas de partir maintenant — restez à l'abri sur place. C'est un reportage spécial de PULSE Nouvelles.",
        },
    ],
}

LANGUAGE_LABELS = {
    "en": "🇺🇸 English",
    "es": "🇪🇸 Spanish",
    "fr": "🇫🇷 French",
}


def get_dubbing_script():
    """Return the mock dubbing script with metadata."""
    return MOCK_SCRIPT


def build_segment_ssml(segment: dict, language: str) -> str:
    """Build SSML for a single segment in the given language."""
    role = segment["role"]
    voice = VOICE_MAP.get(role, {}).get(language, "en-US-AriaNeural")
    style = STYLE_MAP.get(role, "newscast-formal")
    text = segment.get(language, segment.get("en", ""))

    # Escape XML special chars
    text = (text.replace("&", "&amp;").replace("<", "&lt;")
               .replace(">", "&gt;").replace('"', "&quot;").replace("'", "&apos;"))

    lang_tag = {"en": "en-US", "es": "es-MX", "fr": "fr-FR"}.get(language, "en-US")

    ssml = (
        f'<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" '
        f'xmlns:mstts="http://www.w3.org/2001/mstts" xml:lang="{lang_tag}">'
        f'<voice name="{voice}">'
        f'<mstts:express-as style="{style}">'
        f'<prosody rate="-3%">{text}</prosody>'
        f'</mstts:express-as>'
        f'</voice></speak>'
    )
    return ssml


async def synthesize_segment(segment: dict, language: str) -> bytes:
    """
    Synthesize a single script segment to MP3 audio using Azure AI Speech.
    Returns MP3 bytes. In demo mode returns empty bytes.
    """
    if settings.demo_mode:
        return b""

    import azure.cognitiveservices.speech as speechsdk
    from azure.identity import DefaultAzureCredential, get_bearer_token_provider

    _credential = DefaultAzureCredential()
    _token_provider = get_bearer_token_provider(
        _credential, "https://cognitiveservices.azure.com/.default"
    )

    speech_config = speechsdk.SpeechConfig(
        endpoint=settings.azure_speech.endpoint,
        auth_token=_token_provider(),
    )
    speech_config.set_speech_synthesis_output_format(
        speechsdk.SpeechSynthesisOutputFormat.Audio16Khz32KBitRateMonoMp3
    )

    synthesizer = speechsdk.SpeechSynthesizer(
        speech_config=speech_config,
        audio_config=None,
    )

    ssml = build_segment_ssml(segment, language)
    result = synthesizer.speak_ssml(ssml)

    if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
        logger.info(f"Synthesized segment {segment['id']} ({language}) — {len(result.audio_data)} bytes")
        return result.audio_data
    else:
        logger.error(f"Synthesis failed for segment {segment['id']} ({language}): {result.reason}")
        return b""


async def synthesize_full_dub(language: str) -> bytes:
    """
    Synthesize all segments for a language into a single MP3 stream.
    Concatenates all segment audio in order.
    """
    if settings.demo_mode:
        return b""

    all_audio = b""
    for seg in MOCK_SCRIPT["segments"]:
        audio = await synthesize_segment(seg, language)
        all_audio += audio

    return all_audio
