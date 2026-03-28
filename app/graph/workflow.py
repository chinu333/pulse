"""
PULSE - LangGraph Workflow Definition
Defines the multi-agent orchestration graph for the newsroom pipeline.

Pipeline Flow:
  ┌─────────────┐
  │ Orchestrator │  (Triage & Route)
  └──────┬──────┘
         │
  ┌──────▼──────┐
  │🛡️ Security  │  (Inbound Scan — PII, Injection, Content Safety)
  └──────┬──────┘
         │
  ┌──────▼──────┐
  │  Researcher  │  (RAG + Knowledge Base)
  └──────┬──────┘
         │
    ┌────┴────┐
    │         │
  ┌─▼──┐  ┌──▼──┐
  │Spch│  │Video│  (Parallel: Audio + Video Analysis)
  └─┬──┘  └──┬──┘
    └────┬────┘
         │
  ┌──────▼──────┐
  │   Writer     │  (Draft Article)
  └──────┬──────┘
         │
  ┌──────▼──────┐
  │ Fact-Checker │  (Verify Claims)
  └──────┬──────┘
         │
  ┌──────▼──────┐
  │ Compliance   │  (Legal Review)
  └──────┬──────┘
         │
     ┌───┴───┐
     │ Gate   │  (Approved?)
     └───┬───┘
    Yes  │  No → skip to Final
         │
  ┌──────▼──────┐
  │  Optimizer   │  (SEO + Social — only if approved)
  └──────┬──────┘
         │
  ┌──────▼──────┐
  │  Podcast     │  (Generate Podcast Script — only if approved)
  └──────┬──────┘
         │
  ┌──────▼──────┐
  │ Translation  │  (Multi-language — only if approved)
  └──────┬──────┘
         │
  ┌──────▼──────┐
  │🛡️ Security  │  (Outbound Scan — PII Leakage, Content Review)
  └──────┬──────┘
         │
  ┌──────▼──────┐
  │ Orchestrator │  (Final Decision)
  └─────────────┘
"""

import logging
from typing import Any, TypedDict
from langgraph.graph import StateGraph, END

from app.agents.orchestrator import orchestrator_agent, orchestrator_finalize
from app.agents.researcher import researcher_agent
from app.agents.speech import speech_agent
from app.agents.video import video_agent
from app.agents.writer import writer_agent
# from app.agents.image_generator import image_generator_agent  # Disabled per CIO feedback — not using gpt-image-1
from app.agents.podcast import podcast_agent
from app.agents.translation import translation_agent
from app.agents.factchecker import factchecker_agent
from app.agents.optimizer import optimizer_agent
from app.agents.compliance import compliance_agent
from app.agents.security import security_inbound_agent, security_outbound_agent

logger = logging.getLogger("pulse.graph")


class WorkflowState(TypedDict, total=False):
    """The state that flows through the LangGraph workflow."""
    story_id: str
    input: dict[str, Any]
    status: str
    messages: list[dict[str, Any]]
    research: dict[str, Any] | None
    speech: dict[str, Any] | None
    video: dict[str, Any] | None
    draft: dict[str, Any] | None
    image: dict[str, Any] | None
    podcast: dict[str, Any] | None
    translation: dict[str, Any] | None
    fact_check: dict[str, Any] | None
    seo: dict[str, Any] | None
    compliance: dict[str, Any] | None
    security: dict[str, Any] | None
    created_at: str
    completed_at: str | None
    current_agent: str | None
    iteration_count: int
    error: str | None


def _security_outbound_gate(state: dict) -> str:
    """Route based on outbound security scan: passed -> compliance, failed -> final."""
    security = state.get("security")
    if security:
        passed = getattr(security, 'outbound_scan_passed', True) if hasattr(security, 'outbound_scan_passed') else security.get('outbound_scan_passed', True)
        if not passed:
            return "failed"
    return "passed"


def _compliance_gate(state: dict) -> str:
    """Route based on compliance approval: approved → optimizer, rejected → final."""
    compliance = state.get("compliance")
    if compliance and compliance.get("approved", False):
        return "approved"
    return "rejected"


def build_newsroom_graph() -> StateGraph:
    """
    Builds and compiles the LangGraph workflow for the newsroom pipeline.
    Returns a compiled graph ready for invocation.
    """
    workflow = StateGraph(WorkflowState)

    # ── Add nodes ────────────────────────────────────────────
    workflow.add_node("orchestrator_triage", orchestrator_agent)
    workflow.add_node("security_inbound", security_inbound_agent)
    workflow.add_node("research_agent", researcher_agent)
    workflow.add_node("speech_agent", speech_agent)
    workflow.add_node("video_agent", video_agent)
    workflow.add_node("writer_agent", writer_agent)
    workflow.add_node("podcast_agent", podcast_agent)
    workflow.add_node("translation_agent", translation_agent)
    workflow.add_node("factcheck_agent", factchecker_agent)
    workflow.add_node("optimizer_agent", optimizer_agent)
    workflow.add_node("compliance_agent", compliance_agent)
    workflow.add_node("security_outbound", security_outbound_agent)
    workflow.add_node("orchestrator_final", orchestrator_finalize)

    # ── Define edges ─────────────────────────────────────────
    # Pipeline: triage → security_inbound → research → speech → video → writer
    #   → factcheck → security_outbound [GATE: if fails → final]
    #   → compliance [GATE: if rejected → final, else → optimizer → podcast → translator → final]
    workflow.set_entry_point("orchestrator_triage")
    workflow.add_edge("orchestrator_triage", "security_inbound")
    workflow.add_edge("security_inbound", "research_agent")
    workflow.add_edge("research_agent", "speech_agent")
    workflow.add_edge("speech_agent", "video_agent")
    workflow.add_edge("video_agent", "writer_agent")
    workflow.add_edge("writer_agent", "factcheck_agent")
    workflow.add_edge("factcheck_agent", "security_outbound")
    # Security outbound gate: only proceed to compliance if security passes
    workflow.add_conditional_edges(
        "security_outbound",
        _security_outbound_gate,
        {
            "passed": "compliance_agent",
            "failed": "orchestrator_final",
        },
    )
    # Compliance gate: only run optimizer + podcast + translator if compliance approves
    workflow.add_conditional_edges(
        "compliance_agent",
        _compliance_gate,
        {
            "approved": "optimizer_agent",
            "rejected": "orchestrator_final",
        },
    )
    workflow.add_edge("optimizer_agent", "podcast_agent")
    workflow.add_edge("podcast_agent", "translation_agent")
    workflow.add_edge("translation_agent", "orchestrator_final")
    workflow.add_edge("orchestrator_final", END)

    # ── Compile ──────────────────────────────────────────────
    compiled = workflow.compile()
    logger.info("Newsroom pipeline graph compiled successfully (11 agents, security-wrapped, compliance-gated)")
    return compiled


# Singleton compiled graph
newsroom_graph = None


def get_newsroom_graph():
    """Get or create the compiled newsroom graph."""
    global newsroom_graph
    if newsroom_graph is None:
        newsroom_graph = build_newsroom_graph()
    return newsroom_graph
