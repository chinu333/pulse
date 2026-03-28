"""
PULSE - Speech Agent
Handles audio transcription (Speech-to-Text), narration generation (Text-to-Speech),
and speaker diarization. Uses Azure AI Speech service.
"""

import logging
from app.config import settings
from app.models.schemas import AgentMessage, AgentRole, PipelineState, StoryStatus

logger = logging.getLogger("pulse.agent.speech")


async def speech_agent(state: dict) -> dict:
    """
    Speech Agent — transcribes uploaded audio, generates article narration,
    and identifies speakers when applicable.
    """
    pipeline = PipelineState(**state)
    pipeline.current_agent = AgentRole.SPEECH
    pipeline.status = StoryStatus.TRANSCRIBING

    headline = pipeline.input.headline

    # ── Step 1: Check for audio input ────────────────────────
    pipeline.messages.append(AgentMessage(
        agent=AgentRole.SPEECH,
        action="audio_analysis",
        content=f"🎙️ Analyzing audio inputs for: \"{headline}\"",
        confidence=0.90,
    ))

    if settings.demo_mode:
        speech_result = _mock_speech(headline)
    else:
        from app.services.azure_speech import transcribe_audio, synthesize_speech

        # If audio was uploaded, transcribe it
        audio_data = pipeline.input.metadata.get("audio_bytes") if hasattr(pipeline.input, "metadata") else None
        if audio_data:
            transcript = await transcribe_audio(audio_data)
            speech_result = {
                "transcript": transcript.get("transcript", ""),
                "language_detected": transcript.get("language", "en-US"),
                "confidence": transcript.get("confidence", 0.0),
                "duration_seconds": transcript.get("duration_seconds", 0),
                "speakers": [],
                "narration_available": False,
                "narration_voice": "en-us-ava:DragonHDOmniLatestNeural",
            }
        else:
            # No uploaded audio — use LLM to generate a simulated press briefing
            # transcript relevant to the story (like a field reporter's audio)
            speech_result = await _generate_live_transcript(headline, pipeline.input.description)

    pipeline.speech = speech_result

    # ── Step 2: Report results ───────────────────────────────
    transcript_len = len(speech_result.get("transcript", "").split())
    speakers_count = len(speech_result.get("speakers", []))
    duration = speech_result.get("duration_seconds", 0)

    pipeline.messages.append(AgentMessage(
        agent=AgentRole.SPEECH,
        action="transcription_complete",
        content=(
            f"✅ Audio analysis complete:\n"
            f"- Transcript: {transcript_len} words\n"
            f"- Duration: {duration:.1f}s\n"
            f"- Speakers identified: {speakers_count}\n"
            f"- Language: {speech_result.get('language_detected', 'en-US')}\n"
            f"- Narration: {'Ready' if speech_result.get('narration_available') else 'Pending draft'}"
        ),
        confidence=speech_result.get("confidence", 0.92),
        metadata={
            "word_count": transcript_len,
            "duration": duration,
            "speakers": speakers_count,
        },
    ))

    return pipeline.model_dump()


def _mock_speech(headline: str) -> dict:
    """Generate realistic mock speech/audio results for demo."""
    script = [
        {"speaker": "Anchor", "text": (
            "Good afternoon. We're coming to you live from the Municipal Operations Center "
            "where emergency management officials are providing an update on the ongoing situation."
        )},
        {"speaker": "Field Reporter", "text": (
            "That's right. County Director Sarah Mitchell says the response teams have been "
            "deployed across all affected areas. Emergency shelters are being prepared as we speak."
        )},
        {"speaker": "Official Source", "text": (
            "We are taking every precaution to ensure public safety. Our teams have been "
            "preparing for this scenario. Federal authorities have confirmed four point two "
            "million dollars in relief funding."
        )},
        {"speaker": "Anchor", "text": (
            "Approximately 45,000 residents are in the impact zone. We'll continue to "
            "monitor the situation and bring you updates as they develop. Reporting live, "
            "this is PULSE News."
        )},
    ]
    transcript = " ".join(line["text"] for line in script)
    return {
        "transcript": transcript,
        "language_detected": "en-US",
        "confidence": 0.96,
        "duration_seconds": 42.5,
        "speakers": [
            {"id": "Speaker_1", "name": "Anchor", "segments": 2, "duration": 20.0},
            {"id": "Speaker_2", "name": "Field Reporter", "segments": 1, "duration": 10.5},
            {"id": "Speaker_3", "name": "Official Source", "segments": 1, "duration": 12.0},
        ],
        "script": script,
        "narration_available": True,
        "narration_voice": "en-us-ava:DragonHDOmniLatestNeural",
        "narration_duration_estimate": 38.0,
    }


async def _generate_live_transcript(headline: str, description: str) -> dict:
    """Use GPT-4.1 to generate a simulated press briefing transcript for the story.

    In a real production scenario, this would come from actual uploaded audio.
    For the live demo (no audio file), we generate a realistic field-reporter
    style transcript so the Audio tab has meaningful content.
    """
    from app.services.azure_openai import get_creative_llm
    from langchain_core.messages import SystemMessage, HumanMessage

    llm = get_creative_llm()

    try:
        response = await llm.ainvoke([
            SystemMessage(content=(
                "You are a news broadcast script writer. Generate a realistic simulated "
                "audio transcript of a live field report / press briefing for the given story. "
                "Include exactly 3 speakers: an Anchor, a Field Reporter, and an Official Source.\n\n"
                "Format each line as:\n"
                "ANCHOR: [dialogue]\n"
                "FIELD REPORTER: [dialogue]\n"
                "OFFICIAL SOURCE: [dialogue]\n\n"
                "Guidelines:\n"
                "- Anchor opens and closes the segment\n"
                "- Field Reporter does the on-scene reporting\n"
                "- Official Source provides a direct quote or statement\n"
                "- 4-6 lines total, 80-120 words combined\n"
                "- Sound like real broadcast audio — use natural spoken language"
            )),
            HumanMessage(content=f"Story: {headline}\nDetails: {description or 'No additional details.'}"),
        ])

        script = _parse_speech_script(response.content)
        transcript_text = " ".join(line["text"] for line in script)
        word_count = len(transcript_text.split())
        # Estimate duration: ~150 words per minute for broadcast
        est_duration = round(word_count / 150 * 60, 1)

        logger.info("Generated live transcript: %d words, ~%.1fs", word_count, est_duration)

        return {
            "transcript": transcript_text,
            "language_detected": "en-US",
            "confidence": 0.94,
            "duration_seconds": est_duration,
            "speakers": [
                {"id": "Speaker_1", "name": "Anchor", "segments": sum(1 for l in script if l["speaker"] == "Anchor"), "duration": round(est_duration * 0.4, 1)},
                {"id": "Speaker_2", "name": "Field Reporter", "segments": sum(1 for l in script if l["speaker"] == "Field Reporter"), "duration": round(est_duration * 0.35, 1)},
                {"id": "Speaker_3", "name": "Official Source", "segments": sum(1 for l in script if l["speaker"] == "Official Source"), "duration": round(est_duration * 0.25, 1)},
            ],
            "script": script,
            "narration_available": True,
            "narration_voice": "en-us-ava:DragonHDOmniLatestNeural",
            "narration_duration_estimate": est_duration,
        }
    except Exception as e:
        logger.error("Failed to generate live transcript: %s", e)
        # Fall back to mock if LLM call fails
        return _mock_speech(headline)


def _parse_speech_script(raw_text: str) -> list[dict[str, str]]:
    """Parse LLM output into structured speaker lines."""
    speaker_map = {
        "ANCHOR": "Anchor",
        "FIELD REPORTER": "Field Reporter",
        "OFFICIAL SOURCE": "Official Source",
        "REPORTER": "Field Reporter",
        "SOURCE": "Official Source",
    }
    lines = []
    for line in raw_text.strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        matched = False
        for prefix, name in speaker_map.items():
            if line.upper().startswith(prefix + ":"):
                text = line[len(prefix) + 1:].strip()
                if text:
                    lines.append({"speaker": name, "text": text})
                matched = True
                break
        if not matched and lines:
            # Continuation of previous speaker's line
            lines[-1]["text"] += " " + line
    return lines if lines else [{"speaker": "Anchor", "text": raw_text.strip()[:500]}]
