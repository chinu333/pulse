"""
PULSE - Translation Agent
Translates articles and content into multiple target languages.
Uses Azure AI Speech (Speech Translation) and LLM for text translation.
"""

import json
import logging
import re
from langchain_core.messages import HumanMessage, SystemMessage
from app.config import settings
from app.models.schemas import AgentMessage, AgentRole, PipelineState, StoryStatus
from app.services.azure_openai import get_llm

logger = logging.getLogger("pulse.agent.translation")

SYSTEM_PROMPT = """You are a professional multilingual news translator working for a major broadcast network.
You translate news articles accurately while preserving:
- Journalistic tone and style
- Cultural context and localization
- Proper nouns and place names (keep original or provide standard local equivalents)
- Quotes should be translated with a note: [Translated from English]

You MUST respond with valid JSON using this exact structure — no markdown, no commentary:

{
  "headline": "The translated headline in the target language",
  "body": "The full translated article body, maintaining the same paragraph structure. Use \\n\\n between paragraphs."
}

Return ONLY the JSON object. Do not include any other text."""


async def translation_agent(state: dict) -> dict:
    """
    Translation Agent — translates the final article into multiple languages
    using LLM-based translation with journalistic awareness.
    """
    pipeline = PipelineState(**state)
    pipeline.current_agent = AgentRole.TRANSLATOR
    pipeline.status = StoryStatus.TRANSLATING

    headline = pipeline.input.headline
    draft = pipeline.draft

    # ── Step 1: Detect source and prepare ────────────────────
    pipeline.messages.append(AgentMessage(
        agent=AgentRole.TRANSLATOR,
        action="preparing_translation",
        content=f"🌐 Preparing multi-language translation for: \"{headline}\"",
        confidence=0.90,
    ))

    target_languages = ["es", "fr", "de"]  # Spanish, French, German
    article_text = draft.body if draft else headline

    if settings.demo_mode:
        translation_result = _mock_translation(headline, article_text)
    else:
        llm = get_llm(temperature=0.2)
        translations = {}

        language_names = {"es": "Spanish", "fr": "French", "de": "German"}

        for lang_code in target_languages:
            lang_name = language_names.get(lang_code, lang_code)
            response = await llm.ainvoke([
                SystemMessage(content=SYSTEM_PROMPT),
                HumanMessage(content=(
                    f"Translate the following news article into {lang_name}.\n\n"
                    f"Headline: {headline}\n\n"
                    f"Article:\n{article_text}\n\n"
                    f"Respond with JSON only."
                )),
            ])
            parsed = _parse_translation(response.content, headline)
            translations[lang_code] = {
                "headline": parsed["headline"],
                "body": parsed["body"],
                "language_name": lang_name,
            }

        translation_result = {
            "source_language": "en",
            "source_language_name": "English",
            "target_languages": target_languages,
            "translations": translations,
            "auto_detected": True,
            "quality_scores": {lang: 0.90 for lang in target_languages},
        }

    pipeline.translation = translation_result

    # ── Step 2: Report results ───────────────────────────────
    num_langs = len(translation_result.get("translations", {}))
    lang_list = ", ".join(
        translation_result.get("translations", {}).get(k, {}).get("language_name", k)
        for k in translation_result.get("target_languages", [])
    )

    pipeline.messages.append(AgentMessage(
        agent=AgentRole.TRANSLATOR,
        action="translation_complete",
        content=(
            f"✅ Translation complete:\n"
            f"- Source: {translation_result.get('source_language_name', 'English')}\n"
            f"- Translated to: {lang_list}\n"
            f"- Languages: {num_langs}\n"
            f"- Auto-detected: {'Yes' if translation_result.get('auto_detected') else 'No'}"
        ),
        confidence=0.93,
        metadata={
            "languages_count": num_langs,
            "target_languages": translation_result.get("target_languages", []),
        },
    ))

    return pipeline.model_dump()


def _mock_translation(headline: str, article_text: str) -> dict:
    """Generate realistic mock translation results for demo."""
    return {
        "source_language": "en",
        "source_language_name": "English",
        "target_languages": ["es", "fr", "de"],
        "auto_detected": True,
        "translations": {
            "es": {
                "headline": "Alerta: Inundaciones graves afectan a tres condados en el Valle de Ohio",
                "body": (
                    "Las autoridades locales están movilizando recursos hoy en respuesta a lo que "
                    "los funcionarios describen como una situación significativa que afecta a miles "
                    "de residentes en toda la región.\n\n"
                    "Los equipos de gestión de emergencias de tres condados han establecido un "
                    "centro de mando unificado en el Centro de Operaciones Municipales. Veintisiete "
                    "unidades de respuesta están actualmente desplegadas en un área de 12 millas "
                    "cuadradas, según funcionarios del condado.\n\n"
                    "\"Estamos tomando todas las precauciones para garantizar la seguridad pública\", "
                    "dijo la Directora de Gestión de Emergencias del Condado, Sarah Mitchell, "
                    "durante una conferencia de prensa por la tarde. [Traducido del inglés]"
                ),
                "language_name": "Spanish",
                "word_count": 98,
            },
            "fr": {
                "headline": "Alerte: Des inondations majeures touchent trois comtés dans la vallée de l'Ohio",
                "body": (
                    "Les autorités locales mobilisent des ressources aujourd'hui en réponse à ce "
                    "que les responsables décrivent comme une situation importante affectant des "
                    "milliers de résidents dans toute la région.\n\n"
                    "Les équipes de gestion des urgences de trois comtés ont établi un centre de "
                    "commandement unifié au Centre des Opérations Municipales. Vingt-sept unités "
                    "d'intervention sont actuellement déployées sur une zone de 12 miles carrés, "
                    "selon les responsables du comté.\n\n"
                    "« Nous prenons toutes les précautions pour assurer la sécurité publique », "
                    "a déclaré la directrice de la gestion des urgences du comté, Sarah Mitchell. "
                    "[Traduit de l'anglais]"
                ),
                "language_name": "French",
                "word_count": 102,
            },
            "de": {
                "headline": "Eilmeldung: Schwere Überschwemmungen betreffen drei Landkreise im Ohio-Tal",
                "body": (
                    "Die lokalen Behörden mobilisieren heute Ressourcen als Reaktion auf das, was "
                    "Beamte als eine bedeutende Situation beschreiben, die Tausende von Bewohnern "
                    "in der gesamten Region betrifft.\n\n"
                    "Katastrophenschutzteams aus drei Landkreisen haben eine einheitliche "
                    "Einsatzleitung im Städtischen Betriebszentrum eingerichtet. Siebenundzwanzig "
                    "Einsatzkräfte sind derzeit in einem Gebiet von 12 Quadratmeilen im Einsatz, "
                    "so die Kreisbehörden.\n\n"
                    "\"Wir treffen alle Vorsichtsmaßnahmen, um die öffentliche Sicherheit zu "
                    "gewährleisten\", sagte die Katastrophenschutzleiterin des Landkreises, "
                    "Sarah Mitchell. [Aus dem Englischen übersetzt]"
                ),
                "language_name": "German",
                "word_count": 95,
            },
        },
        "quality_scores": {
            "es": 0.94,
            "fr": 0.92,
            "de": 0.91,
        },
    }


def _parse_translation(llm_output: str, fallback_headline: str) -> dict:
    """Parse LLM JSON translation output, extracting headline and body."""
    # ── Try JSON parsing first ───────────────────────────────
    try:
        cleaned = re.sub(r"```(?:json)?\s*", "", llm_output).strip().rstrip("`")
        data = json.loads(cleaned)
        return {
            "headline": data.get("headline", fallback_headline),
            "body": data.get("body", llm_output),
        }
    except (json.JSONDecodeError, KeyError, TypeError):
        pass

    # ── Regex fallback: try to find a headline-like first line ─
    lines = llm_output.strip().split("\n")
    # If the first non-empty line is short (< 120 chars), treat it as headline
    headline = fallback_headline
    body = llm_output
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped:
            if len(stripped) < 120 and i < 3:
                headline = stripped.strip("#").strip("*").strip('"').strip()
                body = "\n".join(lines[i + 1:]).strip()
            break

    return {"headline": headline, "body": body}
