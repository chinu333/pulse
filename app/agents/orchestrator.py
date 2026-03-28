"""
PULSE - Orchestrator Agent (Editor-in-Chief)
The master agent that coordinates the entire newsroom pipeline.
"""

import logging
from datetime import datetime
from app.models.schemas import (
    AgentMessage, AgentRole, PipelineState, StoryPriority, StoryStatus,
)

logger = logging.getLogger("pulse.agent.orchestrator")


async def orchestrator_agent(state: dict) -> dict:
    """
    Editor-in-Chief Agent — evaluates the incoming story, decides priority,
    and routes it through the pipeline. This is the first and last agent
    that touches every story.
    """
    pipeline = PipelineState(**state)
    pipeline.current_agent = AgentRole.ORCHESTRATOR
    pipeline.status = StoryStatus.INCOMING

    logger.info(f"[Orchestrator] Received story: {pipeline.input.headline}")

    # ── Triage & prioritization ──────────────────────────────
    priority_assessment = _assess_priority(pipeline.input.headline, pipeline.input.description)

    message = AgentMessage(
        agent=AgentRole.ORCHESTRATOR,
        action="story_triage",
        content=(
            f"📋 Story received: \"{pipeline.input.headline}\"\n"
            f"Priority assessed as: {priority_assessment.upper()}\n"
            f"Routing through full editorial pipeline: "
            f"Research → Write → Fact-Check → Optimize → Compliance"
        ),
        confidence=0.95,
        metadata={
            "priority": priority_assessment,
            "pipeline_stages": [
                "research", "write", "fact_check", "optimize", "compliance"
            ],
        },
    )
    pipeline.messages.append(message)
    pipeline.status = StoryStatus.RESEARCHING

    return pipeline.model_dump()


async def orchestrator_finalize(state: dict) -> dict:
    """
    Final orchestrator pass — reviews all agent outputs and makes
    a publish/hold decision.
    """
    pipeline = PipelineState(**state)
    pipeline.current_agent = AgentRole.ORCHESTRATOR

    fact_score = pipeline.fact_check.overall_score if pipeline.fact_check else 0
    compliance_ok = pipeline.compliance.approved if pipeline.compliance else False
    seo_score = pipeline.seo.seo_score if pipeline.seo else 0

    if fact_score >= 0.7 and compliance_ok:
        pipeline.status = StoryStatus.READY_TO_PUBLISH
        decision = "✅ APPROVED for publication"
    else:
        pipeline.status = StoryStatus.COMPLIANCE_REVIEW
        decision = "⚠️ HELD for editorial review"

    message = AgentMessage(
        agent=AgentRole.ORCHESTRATOR,
        action="publish_decision",
        content=(
            f"{decision}\n"
            f"Fact-Check Score: {fact_score:.0%} | "
            f"SEO Score: {seo_score:.0%} | "
            f"Compliance: {'Passed' if compliance_ok else 'Flagged'}\n"
            f"Story pipeline completed in {len(pipeline.messages)} agent actions."
        ),
        confidence=0.97,
        metadata={
            "fact_check_score": fact_score,
            "seo_score": seo_score,
            "compliance_approved": compliance_ok,
            "total_actions": len(pipeline.messages),
        },
    )
    pipeline.messages.append(message)
    pipeline.completed_at = datetime.utcnow()

    return pipeline.model_dump()


def _assess_priority(headline: str, description: str) -> str:
    """Simple keyword-based priority assessment for demo."""
    text = f"{headline} {description}".lower()
    breaking_keywords = ["breaking", "urgent", "emergency", "shooting", "earthquake", "hurricane", "explosion", "crash"]
    high_keywords = ["election", "death", "scandal", "arrest", "fire", "storm", "recall"]

    if any(kw in text for kw in breaking_keywords):
        return StoryPriority.BREAKING
    elif any(kw in text for kw in high_keywords):
        return StoryPriority.HIGH
    else:
        return StoryPriority.MEDIUM
