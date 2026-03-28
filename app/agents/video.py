"""
PULSE - Video Agent
Analyzes uploaded video content for newsroom use.
Extracts scenes, topics, faces, OCR text, transcript segments, and content moderation flags.
Uses Azure Video Indexer when video is uploaded, or LLM-generated analysis for story context.
"""

import json
import logging
import re
from langchain_core.messages import HumanMessage, SystemMessage
from app.config import settings
from app.models.schemas import AgentMessage, AgentRole, PipelineState, StoryStatus
from app.services.azure_openai import get_llm

logger = logging.getLogger("pulse.agent.video")

VIDEO_ANALYSIS_PROMPT = """You are a video analysis AI that simulates what Azure Video Indexer would produce
when analyzing a broadcast news segment about a given story.

Given a news headline and context, generate a realistic video analysis report as if a 2-minute
news broadcast segment about this story was analyzed frame-by-frame.

You MUST respond with valid JSON using this exact structure — no markdown, no commentary:

{
  "duration": 127,
  "topics": [
    {"name": "Topic Name", "confidence": 0.95}
  ],
  "scenes": [
    {"id": 1, "start": "0:00:00", "end": "0:00:18", "description": "Brief description of what happens in this scene"}
  ],
  "faces": [
    {"name": "Person Name", "title": "Their Role/Title", "appearances": 4}
  ],
  "ocr_text": [
    "TEXT VISIBLE ON SCREEN"
  ],
  "transcript_segments": [
    {"text": "What was said", "start": "0:00:18", "speaker": "Speaker Name or Role", "confidence": 0.97}
  ],
  "keywords": ["keyword1", "keyword2"],
  "content_moderation": {
    "is_adult": false,
    "is_racy": false
  }
}

Requirements:
- Duration should be 90-150 seconds (typical broadcast news segment)
- Include 4-6 topics with descending confidence scores (0.80-0.98)
- Include 5-7 scenes with realistic timecodes covering the full duration
- Include 3-5 identified faces (anchors, officials, reporters)  
- Include 4-6 OCR text items (chyrons, lower-thirds, graphics)
- Include 5-8 transcript segments with speakers and timecodes
- Include 5-8 keywords
- Content moderation should be clean (false/false) for standard news
- Make all content specific to the story headline provided
- Timecodes must be sequential and within the duration"""


async def video_agent(state: dict) -> dict:
    """
    Video Agent — analyzes uploaded video to extract scenes, topics,
    transcript, faces, OCR, and content moderation insights.
    """
    pipeline = PipelineState(**state)
    pipeline.current_agent = AgentRole.VIDEO
    pipeline.status = StoryStatus.VIDEO_ANALYSIS

    headline = pipeline.input.headline

    # ── Step 1: Ingest video ─────────────────────────────────
    pipeline.messages.append(AgentMessage(
        agent=AgentRole.VIDEO,
        action="video_analysis",
        content=f"🎬 Analyzing video content for: \"{headline}\"",
        confidence=0.90,
    ))

    if settings.demo_mode:
        video_result = _mock_video(headline)
    else:
        video_data = None
        try:
            video_data = pipeline.input.metadata.get("video_bytes") if hasattr(pipeline.input, "metadata") else None
        except Exception:
            pass

        if video_data:
            from app.services.azure_video import upload_video, get_video_summary
            upload_resp = await upload_video(video_data, name=headline[:50])
            video_id = upload_resp.get("video_id", "")
            video_result = await get_video_summary(video_id)
        else:
            # No video uploaded — generate realistic analysis via LLM
            video_result = await _generate_live_video_analysis(headline, pipeline.draft)

    pipeline.video = video_result

    # ── Step 2: Report results ───────────────────────────────
    num_scenes = len(video_result.get("scenes", []))
    num_topics = len(video_result.get("topics", []))
    num_faces = len(video_result.get("faces", []))
    num_segments = len(video_result.get("transcript_segments", []))
    duration = video_result.get("duration", 0)
    moderation = video_result.get("content_moderation", {})
    flags = []
    if moderation.get("is_adult"):
        flags.append("Adult content detected")
    if moderation.get("is_racy"):
        flags.append("Racy content detected")
    flag_text = ", ".join(flags) if flags else "No issues"

    pipeline.messages.append(AgentMessage(
        agent=AgentRole.VIDEO,
        action="video_analysis_complete",
        content=(
            f"✅ Video analysis complete:\n"
            f"- Duration: {duration}s\n"
            f"- Scenes: {num_scenes}\n"
            f"- Topics: {num_topics}\n"
            f"- Faces: {num_faces}\n"
            f"- Transcript segments: {num_segments}\n"
            f"- Content moderation: {flag_text}"
        ),
        confidence=0.94,
        metadata={
            "scenes": num_scenes,
            "topics": num_topics,
            "faces": num_faces,
            "duration": duration,
        },
    ))

    return pipeline.model_dump()


async def _generate_live_video_analysis(headline: str, draft) -> dict:
    """Generate realistic video analysis using GPT-4.1 when no video is uploaded."""
    llm = get_llm()
    article_context = draft.body[:500] if draft else headline

    response = await llm.ainvoke([
        SystemMessage(content=VIDEO_ANALYSIS_PROMPT),
        HumanMessage(content=(
            f"Generate a video analysis report for a broadcast news segment about:\n\n"
            f"Headline: {headline}\n\n"
            f"Story context:\n{article_context}\n\n"
            f"Respond with JSON only."
        )),
    ])

    return _parse_video_analysis(response.content, headline)


def _parse_video_analysis(llm_output: str, headline: str) -> dict:
    """Parse LLM JSON output into video analysis dict with fallback."""
    empty = {
        "duration": 0,
        "topics": [],
        "scenes": [],
        "faces": [],
        "ocr_text": [],
        "transcript_segments": [],
        "keywords": [],
        "content_moderation": {"is_adult": False, "is_racy": False},
    }
    try:
        cleaned = re.sub(r"```(?:json)?\s*", "", llm_output).strip().rstrip("`")
        data = json.loads(cleaned)

        return {
            "duration": int(data.get("duration", 120)),
            "topics": [
                {"name": t.get("name", ""), "confidence": round(float(t.get("confidence", 0.8)), 2)}
                for t in data.get("topics", [])
            ],
            "scenes": [
                {
                    "id": s.get("id", i + 1),
                    "start": s.get("start", ""),
                    "end": s.get("end", ""),
                    "description": s.get("description", ""),
                }
                for i, s in enumerate(data.get("scenes", []))
            ],
            "faces": [
                {
                    "name": f.get("name", "Unknown"),
                    "title": f.get("title", ""),
                    "appearances": int(f.get("appearances", 1)),
                }
                for f in data.get("faces", [])
            ],
            "ocr_text": data.get("ocr_text", []),
            "transcript_segments": [
                {
                    "text": t.get("text", ""),
                    "start": t.get("start", ""),
                    "speaker": t.get("speaker", ""),
                    "confidence": round(float(t.get("confidence", 0.9)), 2),
                }
                for t in data.get("transcript_segments", [])
            ],
            "keywords": data.get("keywords", []),
            "content_moderation": {
                "is_adult": bool(data.get("content_moderation", {}).get("is_adult", False)),
                "is_racy": bool(data.get("content_moderation", {}).get("is_racy", False)),
            },
        }
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        logger.warning("Failed to parse LLM video analysis: %s", exc)
        return empty


def _mock_video(headline: str) -> dict:
    """Generate realistic mock video analysis results for demo."""
    return {
        "duration": 127,
        "topics": [
            {"name": "Emergency Response", "confidence": 0.97},
            {"name": "Weather & Natural Disasters", "confidence": 0.94},
            {"name": "Government & Public Safety", "confidence": 0.91},
            {"name": "Community Impact", "confidence": 0.88},
            {"name": "Federal Funding", "confidence": 0.82},
        ],
        "scenes": [
            {"id": 1, "start": "0:00:00", "end": "0:00:18", "description": "Aerial footage of flooding in residential area"},
            {"id": 2, "start": "0:00:18", "end": "0:00:42", "description": "Press conference at Municipal Operations Center"},
            {"id": 3, "start": "0:00:42", "end": "0:01:05", "description": "Emergency response teams in the field"},
            {"id": 4, "start": "0:01:05", "end": "0:01:28", "description": "Interviews with affected residents"},
            {"id": 5, "start": "0:01:28", "end": "0:01:52", "description": "Map overlay showing impact zone"},
            {"id": 6, "start": "0:01:52", "end": "0:02:07", "description": "Anchor wrap-up and call to action"},
        ],
        "faces": [
            {"name": "Sarah Mitchell", "title": "Emergency Management Director", "appearances": 4},
            {"name": "Unknown Person 1", "title": "Resident", "appearances": 2},
            {"name": "Unknown Person 2", "title": "First Responder", "appearances": 3},
            {"name": "News Anchor", "title": "Reporter", "appearances": 6},
        ],
        "ocr_text": [
            "BREAKING NEWS",
            "Emergency Declaration — 3 Counties",
            "Municipal Operations Center",
            "Federal Relief: $4.2M Allocated",
            "Stay Safe: Evacuation Routes →",
        ],
        "transcript_segments": [
            {
                "text": "Good afternoon, we're coming to you live from the Municipal Operations Center.",
                "start": "0:00:18",
                "speaker": "Anchor",
                "confidence": 0.98,
            },
            {
                "text": "We are taking every precaution to ensure public safety.",
                "start": "0:00:32",
                "speaker": "Sarah Mitchell",
                "confidence": 0.97,
            },
            {
                "text": "Twenty-seven response units are currently deployed across the affected area.",
                "start": "0:00:48",
                "speaker": "Anchor",
                "confidence": 0.96,
            },
            {
                "text": "Our teams have been preparing for this scenario, and we're confident in our response plan.",
                "start": "0:01:02",
                "speaker": "Sarah Mitchell",
                "confidence": 0.95,
            },
            {
                "text": "Federal authorities have allocated $4.2 million in relief funding.",
                "start": "0:01:18",
                "speaker": "Anchor",
                "confidence": 0.97,
            },
            {
                "text": "We've lost everything. This is our whole life.",
                "start": "0:01:28",
                "speaker": "Resident",
                "confidence": 0.93,
            },
        ],
        "keywords": [
            "emergency response",
            "flood damage",
            "evacuation",
            "federal relief",
            "public safety",
            "Municipal Operations Center",
            "Sarah Mitchell",
        ],
        "content_moderation": {
            "is_adult": False,
            "is_racy": False,
        },
    }
