"""
PULSE - Compliance Agent
Reviews content for legal, regulatory, and editorial policy compliance.
"""

import logging
from langchain_core.messages import HumanMessage, SystemMessage
from app.config import settings
from app.models.schemas import (
    AgentMessage, AgentRole, ComplianceResult,
    PipelineState, StoryStatus,
)
from app.services.azure_openai import get_analytical_llm
from app.services.azure_search import search_knowledge_base

logger = logging.getLogger("pulse.agent.compliance")

SYSTEM_PROMPT = """You are a broadcast compliance and standards officer at a major television network.

Review the submitted news article for:
1. FCC broadcast regulations compliance
2. Defamation / libel risk assessment
3. Privacy concerns (minors, victims, HIPAA)
4. Editorial policy adherence (fairness, balance, attribution)
5. Advertising / sponsorship identification issues
6. Sensitive content warnings needed

Return your assessment as valid JSON with exactly this structure (no markdown, no code fences):

{
  "approved": true,
  "verdict": "APPROVE or HOLD",
  "legal_flags": ["flag description 1"],
  "issues": [
    {"type": "CRITICAL or WARNING or ADVISORY", "description": "issue description"}
  ],
  "suggestions": ["suggestion 1", "suggestion 2"],
  "editorial_notes": ["note 1", "note 2"]
}

Rules:
- approved: true if the article can be published, false if it must be held
- legal_flags: array of strings for legal concerns (empty array if none)
- issues: array of objects with type (CRITICAL/WARNING/ADVISORY) and description. Omit trivial items.
- suggestions: actionable improvement suggestions (2-4 items)
- editorial_notes: positive observations about the article's quality (2-4 items)

Return ONLY the JSON object, nothing else."""


async def compliance_agent(state: dict) -> dict:
    """
    Compliance Agent — reviews article for legal and editorial policy compliance.
    """
    pipeline = PipelineState(**state)
    pipeline.current_agent = AgentRole.COMPLIANCE
    pipeline.status = StoryStatus.COMPLIANCE_REVIEW

    draft = pipeline.draft

    pipeline.messages.append(AgentMessage(
        agent=AgentRole.COMPLIANCE,
        action="compliance_review",
        content="⚖️ Running legal, regulatory, and editorial compliance review...",
        confidence=0.90,
    ))

    # Search compliance knowledge base
    compliance_context = await search_knowledge_base("FCC broadcast compliance editorial policy", top_k=3)

    if settings.demo_mode:
        compliance = _mock_compliance()
    else:
        llm = get_analytical_llm()
        context_text = "\n".join(r["content"] for r in compliance_context)
        response = await llm.ainvoke([
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=(
                f"Article for review:\nHeadline: {draft.headline if draft else 'N/A'}\n"
                f"Body: {draft.body if draft else 'N/A'}\n\n"
                f"Compliance Guidelines:\n{context_text}\n\n"
                f"Provide compliance assessment."
            )),
        ])
        compliance = _parse_compliance(response.content)

    pipeline.compliance = compliance

    status_emoji = "✅" if compliance.approved else "⚠️"
    pipeline.messages.append(AgentMessage(
        agent=AgentRole.COMPLIANCE,
        action="compliance_complete",
        content=(
            f"{status_emoji} Compliance review completed:\n"
            f"- Status: {'APPROVED' if compliance.approved else 'HOLDS REQUIRED'}\n"
            f"- Legal flags: {len(compliance.legal_flags)}\n"
            f"- Issues found: {len(compliance.issues)}\n"
            f"- Suggestions: {len(compliance.suggestions)}\n"
            f"- Editorial notes: {len(compliance.editorial_notes)}"
        ),
        confidence=0.94,
        metadata={
            "approved": compliance.approved,
            "issues_count": len(compliance.issues),
            "legal_flags_count": len(compliance.legal_flags),
        },
    ))

    return pipeline.model_dump()


def _mock_compliance() -> ComplianceResult:
    """Generate realistic mock compliance results for demo."""
    return ComplianceResult(
        approved=True,
        issues=[
            {
                "type": "ADVISORY",
                "description": "Consider adding 'alleged' qualifier before unconfirmed shelter capacity",
                "section": "paragraph_5",
            },
        ],
        suggestions=[
            "Add disclaimer about ongoing nature of the situation",
            "Include contact information for local emergency services",
            "Consider adding accessibility information for affected residents",
        ],
        legal_flags=[],
        editorial_notes=[
            "Article maintains appropriate objectivity and balance",
            "Source attribution is present for all major claims",
            "No identification of minors or protected individuals detected",
            "Content is appropriate for all broadcast dayparts",
        ],
    )


def _parse_compliance(llm_output: str) -> ComplianceResult:
    """Parse JSON LLM output into structured ComplianceResult."""
    import json
    import re

    text = llm_output.strip()

    # Strip markdown code fences if the LLM wrapped it
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    text = text.strip()

    try:
        data = json.loads(text)

        # Normalize issues — ensure each is a dict with type + description
        raw_issues = data.get("issues", [])
        issues = []
        for item in raw_issues:
            if isinstance(item, dict):
                issues.append({
                    "type": item.get("type", "WARNING"),
                    "description": item.get("description", ""),
                })
            elif isinstance(item, str):
                issues.append({"type": "WARNING", "description": item})

        return ComplianceResult(
            approved=data.get("approved", True),
            legal_flags=data.get("legal_flags", []),
            issues=issues,
            suggestions=data.get("suggestions", []),
            editorial_notes=data.get("editorial_notes", []),
        )
    except (json.JSONDecodeError, ValueError) as e:
        logger.warning("Failed to parse compliance JSON, using fallback: %s", e)

    # Fallback: determine verdict from text and return full text as a suggestion
    lower = text.lower()
    approved = "approve" in lower and "hold" not in lower.split("approve")[0][-30:]

    return ComplianceResult(
        approved=approved,
        legal_flags=[],
        issues=[],
        suggestions=[text[:500]] if text else [],
        editorial_notes=[],
    )
