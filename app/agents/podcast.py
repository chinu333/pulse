"""
PULSE - Podcast Agent
Generates a two-host conversational podcast episode from a news article.
Creates a script with segments, then optionally synthesizes audio via Azure AI Speech.
"""

import logging
from langchain_core.messages import HumanMessage, SystemMessage
from app.config import settings
from app.models.schemas import AgentMessage, AgentRole, PipelineState, StoryStatus
from app.services.azure_openai import get_creative_llm

logger = logging.getLogger("pulse.agent.podcast")

SYSTEM_PROMPT = """You are a podcast script writer for a daily news podcast called "PULSE Daily."
The podcast features two hosts — Alex (lead anchor, authoritative tone) and Morgan (conversational, asks follow-up questions).

Write an engaging, natural-sounding conversational script between the two hosts covering the news story provided.

Format each line as:
ALEX: [dialogue]
MORGAN: [dialogue]

Guidelines:
- Open with a brief teaser hook
- Alex presents the core facts; Morgan asks the "so-what" questions
- Include one moment of genuine reaction or surprise
- Reference specific data points and quotes from the article
- Close with a "what to watch for" segment
- Keep total script to 3-4 minutes of spoken dialogue (~500-650 words)
- Sound natural — use contractions, brief pauses (...), and conversational transitions"""


async def podcast_agent(state: dict) -> dict:
    """
    Podcast Agent — transforms the article into a two-host conversational
    podcast script with segments and timing estimates.
    """
    pipeline = PipelineState(**state)
    pipeline.current_agent = AgentRole.PODCAST
    pipeline.status = StoryStatus.GENERATING_PODCAST

    headline = pipeline.input.headline
    draft = pipeline.draft

    # ── Step 1: Generate script ──────────────────────────────
    pipeline.messages.append(AgentMessage(
        agent=AgentRole.PODCAST,
        action="generating_podcast",
        content=f"🎙️ Generating podcast episode for: \"{headline}\"",
        confidence=0.90,
    ))

    if settings.demo_mode:
        podcast_result = _mock_podcast(headline, draft)
    else:
        podcast_result = await _generate_live_podcast(headline, draft)

    pipeline.podcast = podcast_result

    # ── Step 2: Report results ───────────────────────────────
    num_lines = len(podcast_result.get("script", []))
    num_segments = len(podcast_result.get("segments", []))
    est_min = podcast_result.get("estimated_duration_minutes", 0)

    pipeline.messages.append(AgentMessage(
        agent=AgentRole.PODCAST,
        action="podcast_complete",
        content=(
            f"✅ Podcast episode generated:\n"
            f"- Title: \"{podcast_result.get('episode_title', '')}\"\n"
            f"- Script lines: {num_lines}\n"
            f"- Segments: {num_segments}\n"
            f"- Estimated duration: {est_min:.1f} min\n"
            f"- Hosts: {podcast_result.get('host_a', 'Alex')} & {podcast_result.get('host_b', 'Morgan')}"
        ),
        confidence=0.92,
        metadata={
            "script_lines": num_lines,
            "segments": num_segments,
            "duration_minutes": est_min,
        },
    ))

    return pipeline.model_dump()


async def _generate_live_podcast(headline: str, draft) -> dict:
    """Generate podcast script using LLM."""
    llm = get_creative_llm()
    article_text = draft.body if draft else headline

    response = await llm.ainvoke([
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=(
            f"Create a podcast episode script for PULSE Daily covering this story:\n\n"
            f"Headline: {headline}\n\n"
            f"Article:\n{article_text}"
        )),
    ])

    script_lines = _parse_script(response.content)
    word_count = sum(len(line.get("text", "").split()) for line in script_lines)

    return {
        "episode_title": f"PULSE Daily: {headline[:60]}",
        "episode_summary": f"Alex and Morgan break down the latest on: {headline}",
        "script": script_lines,
        "host_a": "Alex",
        "host_b": "Morgan",
        "estimated_duration_minutes": round(word_count / 150, 1),
        "segments": [
            {"name": "Cold Open", "duration": "0:30"},
            {"name": "Main Story", "duration": f"{max(1, round(word_count / 150) - 1)}:00"},
            {"name": "What to Watch", "duration": "0:30"},
        ],
        "audio_ready": False,
    }


def _parse_script(raw_text: str) -> list[dict[str, str]]:
    """Parse LLM script output into structured lines."""
    lines = []
    for line in raw_text.strip().split("\n"):
        line = line.strip()
        if line.startswith("ALEX:"):
            lines.append({"speaker": "Alex", "text": line[5:].strip()})
        elif line.startswith("MORGAN:"):
            lines.append({"speaker": "Morgan", "text": line[7:].strip()})
    return lines if lines else [{"speaker": "Alex", "text": raw_text[:500]}]


def _mock_podcast(headline: str, draft) -> dict:
    """Generate realistic mock podcast results for demo."""
    return {
        "episode_title": f"PULSE Daily: {headline[:60]}",
        "episode_summary": (
            "Alex and Morgan break down a developing story that has multiple agencies "
            "scrambling to coordinate response efforts across three counties."
        ),
        "script": [
            {
                "speaker": "Alex",
                "text": (
                    "Welcome back to PULSE Daily. I'm Alex, and today we have a story that's moving fast. "
                    "Morgan, what are we looking at?"
                ),
            },
            {
                "speaker": "Morgan",
                "text": (
                    "Alex, this one is significant. We're tracking a major developing situation "
                    "that's affecting thousands of residents across a multi-county area. Emergency "
                    "management teams have stood up a unified command center."
                ),
            },
            {
                "speaker": "Alex",
                "text": (
                    "Let's get into the numbers. Twenty-seven response units deployed across a "
                    "twelve-square-mile area. The impact zone — and this is the number that jumped "
                    "out to me — approximately forty-five thousand residents."
                ),
            },
            {
                "speaker": "Morgan",
                "text": (
                    "Forty-five thousand. That is... that's a whole small city worth of people. "
                    "What's the official response looking like?"
                ),
            },
            {
                "speaker": "Alex",
                "text": (
                    "So County Emergency Management Director Sarah Mitchell held a press briefing "
                    "and here's the key quote: 'We are taking every precaution to ensure public "
                    "safety. Our teams have been preparing for this scenario.' She sounded "
                    "confident, but you could tell this is all-hands-on-deck."
                ),
            },
            {
                "speaker": "Morgan",
                "text": (
                    "And there's federal money coming in too, right? I saw $4.2 million in relief "
                    "funding. That's actually a 23 percent increase over last year's allocations "
                    "for similar events."
                ),
            },
            {
                "speaker": "Alex",
                "text": (
                    "Right, and community shelters are prepped for up to two thousand displaced "
                    "residents if evacuation orders go out. Volunteer networks are already activated."
                ),
            },
            {
                "speaker": "Morgan",
                "text": (
                    "What should people be watching for? What's the next big moment in this story?"
                ),
            },
            {
                "speaker": "Alex",
                "text": (
                    "Two things: there's an official briefing at 6 PM EST tonight, and state "
                    "legislators have a committee hearing next week on whether current frameworks "
                    "are sufficient. This could have policy implications well beyond this one event."
                ),
            },
            {
                "speaker": "Morgan",
                "text": (
                    "Big story. We'll keep tracking it. That's your PULSE Daily update — stay safe "
                    "out there, everyone."
                ),
            },
        ],
        "host_a": "Alex",
        "host_b": "Morgan",
        "estimated_duration_minutes": 3.5,
        "segments": [
            {"name": "Cold Open", "start": "0:00", "duration": "0:25"},
            {"name": "The Facts", "start": "0:25", "duration": "1:15"},
            {"name": "Official Response", "start": "1:40", "duration": "0:50"},
            {"name": "Federal & Community", "start": "2:30", "duration": "0:35"},
            {"name": "What to Watch", "start": "3:05", "duration": "0:25"},
        ],
        "audio_ready": True,
    }
