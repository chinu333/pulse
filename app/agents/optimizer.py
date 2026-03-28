"""
PULSE - SEO / Headline Optimizer Agent
Optimizes headlines, meta descriptions, and social media copy.
"""

import logging
from langchain_core.messages import HumanMessage, SystemMessage
from app.config import settings
from app.models.schemas import (
    AgentMessage, AgentRole, PipelineState,
    SEOResult, StoryStatus,
)
from app.services.azure_openai import get_llm

logger = logging.getLogger("pulse.agent.optimizer")

SYSTEM_PROMPT = """You are a digital content optimization specialist at a major news network.

Your job is to optimize a news article for digital distribution. Return your response as valid JSON with exactly this structure (no markdown, no code fences):

{
  "optimized_headline": "SEO headline, 55-70 chars, include location + topic",
  "meta_description": "Compelling meta description, 150-160 characters",
  "keywords": ["keyword1", "keyword2", "keyword3", "keyword4", "keyword5", "keyword6"],
  "social_copy": {
    "twitter": "Punchy tweet under 280 chars with relevant hashtags",
    "facebook": "Conversational post encouraging sharing, slightly longer",
    "instagram": "Visual language with hashtags"
  },
  "seo_score": 0.85
}

Rules:
- optimized_headline: 55-70 characters, include location and topic
- meta_description: 150-160 characters, compelling
- keywords: 5-8 relevant SEO keywords as an array of strings
- social_copy: platform-specific copy for twitter, facebook, and instagram
- seo_score: float from 0.0 to 1.0 rating the content's SEO potential

Return ONLY the JSON object, nothing else."""


async def optimizer_agent(state: dict) -> dict:
    """
    SEO/Headline Optimizer Agent — polishes content for digital distribution.
    """
    pipeline = PipelineState(**state)
    pipeline.current_agent = AgentRole.OPTIMIZER
    pipeline.status = StoryStatus.OPTIMIZING

    draft = pipeline.draft

    pipeline.messages.append(AgentMessage(
        agent=AgentRole.OPTIMIZER,
        action="analyzing_content",
        content="📊 Analyzing article for SEO optimization and social media distribution...",
        confidence=0.88,
    ))

    if settings.demo_mode:
        seo = _mock_seo(draft.headline if draft else "")
    else:
        llm = get_llm()
        response = await llm.ainvoke([
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=(
                f"Original headline: {draft.headline if draft else 'N/A'}\n"
                f"Article summary: {draft.summary if draft else 'N/A'}\n"
                f"Target audience: {pipeline.input.target_audience}\n\n"
                f"Optimize this content for digital distribution."
            )),
        ])
        seo = _parse_seo(response.content)

    pipeline.seo = seo

    pipeline.messages.append(AgentMessage(
        agent=AgentRole.OPTIMIZER,
        action="optimization_complete",
        content=(
            f"✅ Content optimized for digital distribution:\n"
            f"- SEO Headline: \"{seo.optimized_headline}\"\n"
            f"- Keywords: {', '.join(seo.keywords[:5])}\n"
            f"- SEO Score: {seo.seo_score:.0%}\n"
            f"- Social copy generated for {len(seo.social_copy)} platforms"
        ),
        confidence=0.92,
        metadata={"seo_score": seo.seo_score, "keywords": seo.keywords},
    ))

    pipeline.status = StoryStatus.COMPLIANCE_REVIEW
    return pipeline.model_dump()


def _mock_seo(headline: str) -> SEOResult:
    """Generate realistic mock SEO results for demo."""
    return SEOResult(
        optimized_headline=f"Local Emergency Response: {headline[:40]}",
        meta_description=(
            "Multiple agencies deploy 27 units across 12-mile zone as 45,000 residents "
            "prepare for impact. Federal aid of $4.2M confirmed. Latest updates here."
        ),
        keywords=[
            "emergency response", "local news", "community impact",
            "federal funding", "evacuation", "public safety",
            "breaking news", "weather emergency",
        ],
        social_copy={
            "twitter": (
                "🚨 DEVELOPING: 27 response units deployed across 12-sq-mi area. "
                "45K residents affected. $4.2M federal aid allocated. "
                "Follow for live updates. #BreakingNews #LocalNews"
            ),
            "facebook": (
                "DEVELOPING STORY: Emergency response teams are on the ground as a significant "
                "situation unfolds in our community. 45,000 residents may be affected. "
                "We're monitoring this closely — stay with us for the latest updates. "
                "Share to keep your neighbors informed. ⬇️"
            ),
            "instagram": (
                "🚨 BREAKING: Major emergency response underway in our community. "
                "27 units deployed. 45K residents impacted. Federal aid confirmed. "
                "Swipe for details ➡️\n\n"
                "#BreakingNews #LocalNews #CommunityFirst #EmergencyResponse "
                "#StaySafe #NewsAlert #ScrippsNews"
            ),
        },
        seo_score=0.87,
    )


def _parse_seo(llm_output: str) -> SEOResult:
    """Parse JSON LLM output into structured SEOResult."""
    import json
    import re

    text = llm_output.strip()

    # Strip markdown code fences if the LLM wrapped it
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    text = text.strip()

    try:
        data = json.loads(text)
        return SEOResult(
            optimized_headline=data.get("optimized_headline", "")[:70],
            meta_description=data.get("meta_description", "")[:160],
            keywords=data.get("keywords", []),
            social_copy=data.get("social_copy", {}),
            seo_score=float(data.get("seo_score", 0.80)),
        )
    except (json.JSONDecodeError, ValueError) as e:
        logger.warning("Failed to parse SEO JSON, attempting regex extraction: %s", e)

    # Fallback: regex extraction from free-text LLM output
    headline = ""
    meta = ""
    keywords = []
    social = {}
    score = 0.80

    # Try to find headline
    m = re.search(r"headline[:\s]*[\"']?([^\"'\n]{20,70})", text, re.IGNORECASE)
    if m:
        headline = m.group(1).strip().rstrip(".,")

    # Try to find meta description
    m = re.search(r"meta\s*description[:\s]*[\"']?([^\"'\n]{50,200})", text, re.IGNORECASE)
    if m:
        meta = m.group(1).strip()[:160]

    # Try to find keywords
    kw_match = re.search(r"keywords?[:\s]*\[([^\]]+)\]", text, re.IGNORECASE)
    if kw_match:
        keywords = [k.strip().strip("\"' ") for k in kw_match.group(1).split(",") if k.strip()]
    else:
        kw_match = re.findall(r"[-•]\s*(.+?)(?:\n|$)", text)
        if kw_match:
            keywords = [k.strip() for k in kw_match[:8]]

    # Try to find social copy sections
    for platform in ("twitter", "facebook", "instagram"):
        m = re.search(rf"{platform}[:\s]*[\"']?(.{{20,400}}?)(?:[\"']?\s*(?:facebook|instagram|seo_score|\Z))",
                       text, re.IGNORECASE | re.DOTALL)
        if m:
            social[platform] = m.group(1).strip().rstrip(",\"'")

    # Try to find score
    m = re.search(r"seo_score[:\s]*([0-9.]+)", text, re.IGNORECASE)
    if m:
        try:
            score = min(1.0, max(0.0, float(m.group(1))))
        except ValueError:
            pass

    return SEOResult(
        optimized_headline=headline or text[:70],
        meta_description=meta or text[:160],
        keywords=keywords,
        social_copy=social,
        seo_score=score,
    )
