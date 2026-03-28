"""
PULSE - Research Agent
Gathers background information, sources, and context for a story.
Uses Azure AI Search (RAG) and LLM for synthesis.
"""

import json
import logging
import re
from langchain_core.messages import HumanMessage, SystemMessage
from app.config import settings
from app.models.schemas import (
    AgentMessage, AgentRole, PipelineState,
    ResearchResult, StoryStatus,
)
from app.services.azure_openai import get_llm
from app.services.azure_search import search_knowledge_base

logger = logging.getLogger("pulse.agent.researcher")

SYSTEM_PROMPT = """You are a senior investigative research analyst at a major broadcast news network.
Your job is to gather comprehensive background information for a news story.

Given a story headline and description, produce a structured research brief.
You MUST respond with valid JSON using this exact structure — no markdown, no commentary:

{
  "key_facts": [
    "Fact 1 — a specific verified data point or finding",
    "Fact 2 — another specific detail with numbers when possible"
  ],
  "background_context": "2-3 paragraph narrative providing historical context, recent developments, and why this story matters now.",
  "sources": [
    {"name": "Source Name", "type": "official|government|wire_service|academic|industry", "reliability": "high|medium|low"},
    {"name": "Another Source", "type": "government", "reliability": "high"}
  ],
  "related_stories": [
    "Month Year: Brief description of a related prior story",
    "Month Year: Another related development"
  ],
  "data_points": [
    {"metric": "What is measured", "value": "The number or value", "source": "Where it comes from"},
    {"metric": "Another metric", "value": "Its value", "source": "Its source"}
  ]
}

Requirements:
- Provide 5-8 key facts with specific numbers and details
- Include 3-5 credible sources with type and reliability rating
- Write substantive background context (not just one sentence)
- List 3-4 related stories with approximate dates
- Include 3-5 quantitative data points with metrics, values, and sources
- Be thorough, accurate, and cite your reasoning
- Flag any claims that need verification by adding "[NEEDS VERIFICATION]" suffix"""


async def researcher_agent(state: dict) -> dict:
    """
    Research Agent — retrieves relevant knowledge from the vector store
    and synthesizes a research brief using the LLM.
    """
    pipeline = PipelineState(**state)
    pipeline.current_agent = AgentRole.RESEARCHER
    pipeline.status = StoryStatus.RESEARCHING

    headline = pipeline.input.headline
    description = pipeline.input.description

    # ── Step 1: Vector search for relevant context ───────────
    pipeline.messages.append(AgentMessage(
        agent=AgentRole.RESEARCHER,
        action="knowledge_search",
        content=f"🔍 Searching knowledge base for context on: \"{headline}\"",
        confidence=0.90,
    ))

    search_results = await search_knowledge_base(f"{headline} {description}", top_k=5)
    context_snippets = "\n\n".join(
        f"[Source: {r['metadata'].get('source', 'unknown')}] {r['content']}"
        for r in search_results
    )

    # ── Step 2: LLM synthesis ────────────────────────────────
    pipeline.messages.append(AgentMessage(
        agent=AgentRole.RESEARCHER,
        action="synthesizing_research",
        content="📚 Analyzing sources and compiling research brief...",
        confidence=0.85,
    ))

    if settings.demo_mode:
        research = _mock_research(headline)
    else:
        llm = get_llm()
        context_block = (
            f"Knowledge Base Context:\n{context_snippets}\n\n"
            if context_snippets.strip()
            else "Note: No documents were found in the knowledge base for this topic. Use your training knowledge to produce a thorough research brief.\n\n"
        )
        response = await llm.ainvoke([
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=(
                f"Story Headline: {headline}\n"
                f"Description: {description}\n\n"
                f"{context_block}"
                f"Produce a comprehensive research brief as JSON."
            )),
        ])
        research = _parse_research(response.content)

    pipeline.research = research
    pipeline.messages.append(AgentMessage(
        agent=AgentRole.RESEARCHER,
        action="research_complete",
        content=(
            f"✅ Research brief compiled:\n"
            f"- {len(research.key_facts)} key facts identified\n"
            f"- {len(research.sources)} sources referenced\n"
            f"- {len(research.data_points)} data points gathered\n"
            f"- {len(research.related_stories)} related stories found"
        ),
        confidence=0.92,
        metadata={"sources_count": len(research.sources), "facts_count": len(research.key_facts)},
    ))

    pipeline.status = StoryStatus.WRITING
    return pipeline.model_dump()


def _mock_research(headline: str) -> ResearchResult:
    """Generate realistic mock research results for demo."""
    return ResearchResult(
        key_facts=[
            "The story involves a significant development affecting the local community",
            "Multiple government agencies have confirmed the initial reports",
            "This represents a 23% increase compared to the same period last year",
            "Local officials held an emergency briefing at 2:00 PM EST",
            "Community organizations have mobilized response teams",
            "Federal funding of $4.2M has been allocated for relief efforts",
            "Similar incidents were reported in three neighboring counties",
        ],
        sources=[
            {"name": "County Emergency Management Office", "type": "official", "reliability": "high"},
            {"name": "National Weather Service Bulletin", "type": "government", "reliability": "high"},
            {"name": "Associated Press Wire Report", "type": "wire_service", "reliability": "high"},
            {"name": "Local Police Department Press Release", "type": "official", "reliability": "high"},
            {"name": "University Research Center Analysis", "type": "academic", "reliability": "medium"},
        ],
        background_context=(
            "This story builds on a series of developments over the past 18 months. "
            "The region has seen increased activity in this area, with experts attributing "
            "the trend to a combination of policy changes and environmental factors. "
            "Previous coverage by our station in March and August provides useful context."
        ),
        related_stories=[
            "March 2026: Initial warnings issued by federal agency",
            "August 2025: Community forum drew 500+ residents",
            "January 2026: State legislature proposed new regulations",
            "November 2025: Similar incident in neighboring market",
        ],
        data_points=[
            {"metric": "Affected area", "value": "12 square miles", "source": "County GIS"},
            {"metric": "Population impact", "value": "~45,000 residents", "source": "Census Bureau"},
            {"metric": "Response teams deployed", "value": "27 units", "source": "Emergency Mgmt"},
            {"metric": "Estimated cost", "value": "$4.2 million", "source": "Federal allocation"},
        ],
    )


def _parse_research(llm_output: str) -> ResearchResult:
    """Parse LLM JSON output into structured ResearchResult with regex fallback."""
    # ── Try JSON parsing first ───────────────────────────────
    try:
        # Strip markdown fences if present
        cleaned = re.sub(r"```(?:json)?\s*", "", llm_output).strip().rstrip("`")
        data = json.loads(cleaned)
        return ResearchResult(
            key_facts=data.get("key_facts", [])[:8],
            background_context=data.get("background_context", ""),
            sources=[
                {"name": s.get("name", "Unknown"), "type": s.get("type", "unknown"), "reliability": s.get("reliability", "medium")}
                for s in data.get("sources", [])
            ],
            related_stories=data.get("related_stories", [])[:6],
            data_points=[
                {"metric": d.get("metric", ""), "value": d.get("value", ""), "source": d.get("source", "")}
                for d in data.get("data_points", [])
            ],
        )
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        logger.warning("JSON parse failed for research output, using regex fallback: %s", exc)

    # ── Regex fallback ───────────────────────────────────────
    # Extract bullet points as key facts
    facts = re.findall(r"^[\-\*•]\s*(.+)$", llm_output, re.MULTILINE)
    if not facts:
        facts = [line.strip() for line in llm_output.split("\n") if line.strip() and len(line.strip()) > 20][:8]

    # Try to find a background/context paragraph (longest paragraph)
    paragraphs = [p.strip() for p in llm_output.split("\n\n") if len(p.strip()) > 80]
    background = max(paragraphs, key=len) if paragraphs else llm_output[:500]

    # Extract anything that looks like a source reference
    source_matches = re.findall(r"(?:Source|According to|per)\s*:?\s*([A-Z][^,\n]{5,60})", llm_output, re.IGNORECASE)
    sources = [{"name": s.strip(), "type": "referenced", "reliability": "medium"} for s in source_matches[:5]]
    if not sources:
        sources = [{"name": "LLM-synthesized research", "type": "ai", "reliability": "medium"}]

    # Extract numbered items or date-prefixed items as related stories
    related = re.findall(r"(?:(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}[:\-]\s*.+|(?:\d{1,2}[./]\d{4})[:\-]\s*.+)", llm_output, re.IGNORECASE)
    if not related:
        related = re.findall(r"^\d+[.)]\s*(.+)$", llm_output, re.MULTILINE)[:4]

    # Extract data points from number-containing lines
    data_lines = re.findall(r"^.*\b(\d[\d,.]+\s*(?:%|percent|million|billion|thousand|units|residents|miles|acres))\b.*$", llm_output, re.MULTILINE | re.IGNORECASE)
    data_points = [{"metric": "Statistic", "value": d.strip(), "source": "Research analysis"} for d in data_lines[:5]]

    return ResearchResult(
        key_facts=facts[:8],
        background_context=background,
        sources=sources,
        related_stories=related[:4],
        data_points=data_points,
    )
