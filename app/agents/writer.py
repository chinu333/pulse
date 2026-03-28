"""
PULSE - Writer Agent
Drafts broadcast-quality news articles from research briefs.
"""

import json
import logging
import re
from langchain_core.messages import HumanMessage, SystemMessage
from app.config import settings
from app.models.schemas import (
    AgentMessage, AgentRole, ArticleDraft,
    PipelineState, StoryStatus,
)
from app.services.azure_openai import get_creative_llm

logger = logging.getLogger("pulse.agent.writer")

SYSTEM_PROMPT = """You are an award-winning broadcast news writer at a major television network.
Your writing style is clear, concise, and compelling — designed for both digital and on-air delivery.

You MUST respond with valid JSON using this exact structure — no markdown, no commentary:

{
  "headline": "A compelling, broadcast-ready headline (55-70 chars)",
  "subheadline": "A secondary line that adds context or urgency",
  "body": "The full article body with paragraph breaks (use \\n\\n between paragraphs). 300-500 words. Include at least one direct quote.",
  "summary": "A 1-2 sentence summary suitable for a news ticker or push notification.",
  "tone": "urgent-but-measured|investigative|breaking|human-interest|analytical",
  "quotes": [
    "\\\"Exact quote from the article.\\\" — Speaker Name, Title"
  ]
}

Writing guidelines:
- Lead with the most newsworthy element
- Use active voice and present tense
- Keep sentences under 25 words for broadcast readability
- Include at least one direct quote from sources
- Write a compelling subheadline that adds context beyond the headline
- Structure: Lead → Context → Details → Impact → What's Next
- Target 300-500 words for the article body
- Maintain journalistic objectivity
- The body field must contain the full article text with \\n\\n paragraph separators"""


async def writer_agent(state: dict) -> dict:
    """
    Writer Agent — takes research brief and produces a polished article draft.
    """
    pipeline = PipelineState(**state)
    pipeline.current_agent = AgentRole.WRITER
    pipeline.status = StoryStatus.WRITING

    research = pipeline.research
    headline = pipeline.input.headline

    pipeline.messages.append(AgentMessage(
        agent=AgentRole.WRITER,
        action="drafting_article",
        content=f"✍️ Crafting article draft based on {len(research.key_facts) if research else 0} research facts...",
        confidence=0.88,
    ))

    if settings.demo_mode:
        draft = _mock_draft(headline)
    else:
        llm = get_creative_llm()
        research_brief = _format_research_brief(research)
        response = await llm.ainvoke([
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=(
                f"Story Headline: {headline}\n"
                f"Target Audience: {pipeline.input.target_audience}\n\n"
                f"Research Brief:\n{research_brief}\n\n"
                f"Write a broadcast-quality news article. Respond with JSON only."
            )),
        ])
        draft = _parse_draft(response.content, headline)

    pipeline.draft = draft
    pipeline.messages.append(AgentMessage(
        agent=AgentRole.WRITER,
        action="draft_complete",
        content=(
            f"✅ Article draft completed:\n"
            f"- Headline: \"{draft.headline}\"\n"
            f"- Word count: {draft.word_count}\n"
            f"- Tone: {draft.tone}\n"
            f"- Quotes included: {len(draft.quotes)}"
        ),
        confidence=0.90,
        metadata={"word_count": draft.word_count, "tone": draft.tone},
    ))

    pipeline.status = StoryStatus.FACT_CHECKING
    return pipeline.model_dump()


def _mock_draft(headline: str) -> ArticleDraft:
    """Generate a realistic mock article draft for demo."""
    return ArticleDraft(
        headline=headline,
        subheadline="Multiple agencies respond as community braces for impact; officials urge preparedness",
        body=(
            "Local authorities are mobilizing resources today in response to what officials "
            "describe as a significant and developing situation affecting thousands of residents "
            "across the region.\n\n"
            "Emergency management teams from three counties have established a unified command "
            "center at the Municipal Operations Center. Twenty-seven response units are currently "
            "deployed across a 12-square-mile area, according to county officials.\n\n"
            "\"We are taking every precaution to ensure public safety,\" said County Emergency "
            "Management Director Sarah Mitchell during an afternoon press briefing. \"Our teams "
            "have been preparing for this scenario, and we are confident in our response plan.\"\n\n"
            "The impact zone encompasses approximately 45,000 residents, based on Census Bureau "
            "data. Federal authorities have allocated $4.2 million in relief funding, a figure "
            "that represents a 23% increase over similar allocations from last year.\n\n"
            "Community organizations have activated their volunteer networks, with local shelters "
            "reporting they are prepared to accommodate up to 2,000 displaced residents if necessary.\n\n"
            "State legislators have renewed calls for updated regulations, pointing to this incident "
            "as evidence that current frameworks are insufficient. A legislative committee hearing "
            "is scheduled for next week.\n\n"
            "Residents in affected areas are urged to monitor official channels for updates and "
            "follow evacuation orders if issued. The next official briefing is scheduled for "
            "6:00 PM EST."
        ),
        summary=(
            "Local authorities mobilize 27 response units across 12-square-mile area affecting "
            "45,000 residents. Federal funding of $4.2M allocated. Community shelters prepared "
            "for up to 2,000 evacuees."
        ),
        word_count=247,
        tone="urgent-but-measured",
        quotes=[
            "\"We are taking every precaution to ensure public safety.\" — County Emergency Management Director Sarah Mitchell",
        ],
    )


def _format_research_brief(research) -> str:
    """Format research result into a readable brief for the LLM."""
    if not research:
        return "No research data available."
    parts = [
        "KEY FACTS:",
        *[f"- {f}" for f in (research.key_facts or [])],
        "\nBACKGROUND:",
        research.background_context or "N/A",
        "\nSOURCES:",
        *[f"- {s.get('name', 'Unknown')} ({s.get('type', '')})" for s in (research.sources or [])],
    ]
    return "\n".join(parts)


def _parse_draft(llm_output: str, headline: str) -> ArticleDraft:
    """Parse LLM JSON output into structured ArticleDraft with regex fallback."""
    # ── Try JSON parsing first ───────────────────────────────
    try:
        cleaned = re.sub(r"```(?:json)?\s*", "", llm_output).strip().rstrip("`")
        data = json.loads(cleaned)

        body = data.get("body", "")
        words = body.split()
        quotes = data.get("quotes", [])
        if isinstance(quotes, str):
            quotes = [quotes]

        tone = data.get("tone", "neutral")
        valid_tones = {"urgent-but-measured", "investigative", "breaking", "human-interest", "analytical", "neutral"}
        if tone not in valid_tones:
            tone = "neutral"

        return ArticleDraft(
            headline=data.get("headline", headline),
            subheadline=data.get("subheadline", ""),
            body=body,
            summary=data.get("summary", body[:200]),
            word_count=len(words),
            tone=tone,
            quotes=quotes,
        )
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        logger.warning("JSON parse failed for writer output, using regex fallback: %s", exc)

    # ── Regex fallback ───────────────────────────────────────
    text = llm_output.strip()

    # Extract headline if present at top
    extracted_headline = headline
    hl_match = re.search(r"^(?:#+\s*|Headline[:\s]*)?(.{20,80})\n", text)
    if hl_match:
        extracted_headline = hl_match.group(1).strip().strip('"')

    # Extract subheadline
    subheadline = ""
    sub_match = re.search(r"(?:subheadline|subtitle|sub-head)[:\s]*(.+?)(?:\n|$)", text, re.IGNORECASE)
    if sub_match:
        subheadline = sub_match.group(1).strip().strip('"')

    # Extract quotes (text between quotation marks followed by attribution)
    quotes = re.findall(r'("[^"]{15,200}")\s*(?:—|--|–|-)\s*([A-Z][^"\n]{3,60})', text)
    quote_list = [f'{q[0]} — {q[1].strip()}' for q in quotes]

    # Extract tone
    tone = "neutral"
    tone_match = re.search(r"(?:tone)[:\s]*([\w-]+)", text, re.IGNORECASE)
    if tone_match:
        tone = tone_match.group(1).lower()

    # Clean body — remove any leading headline/metadata lines
    body = text
    # Remove lines that look like metadata
    body = re.sub(r"^(?:headline|subheadline|subtitle|tone|summary|quotes?)[:\s]*.+?\n", "", body, flags=re.IGNORECASE | re.MULTILINE)

    words = body.split()

    # Extract summary
    summary = ""
    sum_match = re.search(r"(?:summary|tldr|tl;dr)[:\s]*(.+?)(?:\n\n|$)", text, re.IGNORECASE | re.DOTALL)
    if sum_match:
        summary = sum_match.group(1).strip()[:300]
    else:
        summary = body[:200]

    return ArticleDraft(
        headline=extracted_headline,
        subheadline=subheadline,
        body=body,
        summary=summary,
        word_count=len(words),
        tone=tone,
        quotes=quote_list,
    )
