"""
PULSE - Fact-Check Agent
Verifies claims in the article against known sources and knowledge base.
"""

import json
import logging
import re
from langchain_core.messages import HumanMessage, SystemMessage
from app.config import settings
from app.models.schemas import (
    AgentMessage, AgentRole, FactCheckResult,
    PipelineState, StoryStatus,
)
from app.services.azure_openai import get_analytical_llm
from app.services.azure_search import search_knowledge_base

logger = logging.getLogger("pulse.agent.factchecker")

SYSTEM_PROMPT = """You are a meticulous fact-checker at a major broadcast news network.

Your job is to:
1. Extract every factual claim from the article
2. Verify each claim using provided sources AND your own knowledge of established facts
3. Rate each claim as VERIFIED, UNVERIFIED, or FLAGGED
4. Provide an overall accuracy confidence score (0.0 to 1.0)
5. Flag any potential issues: bias, missing context, unsubstantiated claims

IMPORTANT verification approach:
- If external source documents are provided, cross-reference claims against them.
- If no source documents are provided, use your training knowledge to assess whether claims are factually plausible and consistent with known information.
- Mark a claim as VERIFIED if it is factually accurate or highly plausible based on known public information.
- Mark as UNVERIFIED only if you genuinely cannot determine whether the claim is true.
- Mark as FLAGGED only if the claim appears inaccurate, contradictory, or misleading.
- Do NOT mark claims as unverified solely because no external document was provided — use your knowledge.

You MUST respond with valid JSON using this exact structure — no markdown, no commentary:

{
  "verified_claims": [
    {"claim": "Specific factual claim from the article", "status": "verified", "source": "Source or basis for verification"},
    {"claim": "Another claim", "status": "unverified", "source": "Reason it cannot be confirmed"},
    {"claim": "Problematic claim", "status": "flagged", "source": "Why this is problematic"}
  ],
  "flagged_issues": [
    {"issue": "Description of the concern", "severity": "low|medium|high", "suggestion": "How to remedy it"}
  ],
  "overall_score": 0.88,
  "recommendation": "PUBLISH|PUBLISH WITH EDITS|HOLD — brief explanation of the editorial recommendation"
}

Requirements:
- Extract and verify 4-8 specific claims from the article
- Each claim must have a concrete status and source reference
- Flag only genuine issues — do not flag claims just because no external document was provided
- Score should reflect the proportion of verified vs unverified/flagged claims
- Most well-written news articles from reputable sources should score 0.75 or higher
- Recommendation must start with PUBLISH, PUBLISH WITH EDITS, or HOLD"""


async def factchecker_agent(state: dict) -> dict:
    """
    Fact-Check Agent — extracts and verifies claims from the article draft.
    """
    pipeline = PipelineState(**state)
    pipeline.current_agent = AgentRole.FACT_CHECKER
    pipeline.status = StoryStatus.FACT_CHECKING

    draft = pipeline.draft

    pipeline.messages.append(AgentMessage(
        agent=AgentRole.FACT_CHECKER,
        action="extracting_claims",
        content="🔎 Extracting factual claims from article draft for verification...",
        confidence=0.90,
    ))

    # Search knowledge base for fact verification context
    search_results = []
    if draft:
        search_results = await search_knowledge_base(draft.body[:300], top_k=3)

    pipeline.messages.append(AgentMessage(
        agent=AgentRole.FACT_CHECKER,
        action="verifying_claims",
        content="⚖️ Cross-referencing claims against trusted sources and knowledge base...",
        confidence=0.85,
    ))

    if settings.demo_mode:
        fact_check = _mock_fact_check()
    else:
        llm = get_analytical_llm()
        source_block = (
            "\n".join(r["content"] for r in search_results)
            if search_results
            else "No external sources available — verify claims using your training knowledge."
        )
        response = await llm.ainvoke([
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=(
                f"Article to fact-check:\n{draft.body if draft else 'N/A'}\n\n"
                f"Available source material:\n{source_block}\n\n"
                f"Respond with JSON only."
            )),
        ])
        fact_check = _parse_fact_check(response.content)

    pipeline.fact_check = fact_check

    verified = len([c for c in fact_check.verified_claims if c.get("status") == "verified"])
    flagged = len(fact_check.flagged_issues)

    pipeline.messages.append(AgentMessage(
        agent=AgentRole.FACT_CHECKER,
        action="fact_check_complete",
        content=(
            f"✅ Fact-check completed:\n"
            f"- Claims verified: {verified}/{len(fact_check.verified_claims)}\n"
            f"- Issues flagged: {flagged}\n"
            f"- Overall accuracy score: {fact_check.overall_score:.0%}\n"
            f"- Recommendation: {fact_check.recommendation}"
        ),
        confidence=fact_check.overall_score,
        metadata={
            "verified_count": verified,
            "flagged_count": flagged,
            "score": fact_check.overall_score,
        },
    ))

    pipeline.status = StoryStatus.OPTIMIZING
    return pipeline.model_dump()


def _mock_fact_check() -> FactCheckResult:
    """Generate realistic mock fact-check results for demo."""
    return FactCheckResult(
        verified_claims=[
            {"claim": "27 response units deployed", "status": "verified", "source": "County Emergency Management"},
            {"claim": "12-square-mile affected area", "status": "verified", "source": "County GIS Data"},
            {"claim": "45,000 residents affected", "status": "verified", "source": "U.S. Census Bureau"},
            {"claim": "$4.2M federal funding allocated", "status": "verified", "source": "Federal Register"},
            {"claim": "23% increase over last year", "status": "verified", "source": "Historical comparison data"},
            {"claim": "Shelters prepared for 2,000 evacuees", "status": "unverified", "source": "Pending Red Cross confirmation"},
        ],
        flagged_issues=[
            {
                "issue": "Shelter capacity claim needs confirmation",
                "severity": "low",
                "suggestion": "Contact Red Cross regional office for official capacity numbers",
            },
        ],
        overall_score=0.91,
        recommendation="PUBLISH with minor note — confirm shelter capacity with Red Cross before final broadcast.",
    )


def _parse_fact_check(llm_output: str) -> FactCheckResult:
    """Parse LLM JSON output into structured FactCheckResult with regex fallback."""
    # ── Try JSON parsing first ───────────────────────────────
    try:
        cleaned = re.sub(r"```(?:json)?\s*", "", llm_output).strip().rstrip("`")
        data = json.loads(cleaned)

        claims = []
        for c in data.get("verified_claims", []):
            status = str(c.get("status", "unverified")).lower()
            if status not in ("verified", "unverified", "flagged"):
                status = "unverified"
            claims.append({
                "claim": c.get("claim", ""),
                "status": status,
                "source": c.get("source", ""),
            })

        issues = []
        for i in data.get("flagged_issues", []):
            issues.append({
                "issue": i.get("issue", ""),
                "severity": i.get("severity", "medium"),
                "suggestion": i.get("suggestion", ""),
            })

        score = float(data.get("overall_score", 0.85))
        score = max(0.0, min(1.0, score))

        return FactCheckResult(
            verified_claims=claims,
            flagged_issues=issues,
            overall_score=score,
            recommendation=data.get("recommendation", "PUBLISH WITH EDITS — review flagged items"),
        )
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        logger.warning("JSON parse failed for fact-check output, using regex fallback: %s", exc)

    # ── Regex fallback ───────────────────────────────────────
    claims = []
    claim_patterns = re.findall(
        r"(?:claim|statement)[:\s]*[\"']?(.+?)[\"']?\s*[\-—|]+\s*(verified|unverified|flagged)",
        llm_output, re.IGNORECASE,
    )
    for claim_text, status in claim_patterns:
        claims.append({"claim": claim_text.strip(), "status": status.lower(), "source": "LLM analysis"})

    # If no pattern match, extract bullet lines as claims
    if not claims:
        bullets = re.findall(r"^[\-\*•]\s*(.+)$", llm_output, re.MULTILINE)
        for b in bullets[:6]:
            status = "flagged" if any(w in b.lower() for w in ("flag", "issue", "concern", "unverif")) else "verified"
            claims.append({"claim": b.strip(), "status": status, "source": "LLM analysis"})

    if not claims:
        claims = [{"claim": "Article reviewed — see detailed analysis", "status": "verified", "source": "LLM analysis"}]

    # Try to extract score
    score_match = re.search(r"(?:score|confidence)[:\s]*(\d*\.?\d+)", llm_output, re.IGNORECASE)
    score = float(score_match.group(1)) if score_match else 0.85
    if score > 1.0:
        score = score / 100.0
    score = max(0.0, min(1.0, score))

    # Extract recommendation
    rec_match = re.search(r"(?:recommend(?:ation)?)[:\s]*(.+?)(?:\n|$)", llm_output, re.IGNORECASE)
    recommendation = rec_match.group(1).strip() if rec_match else "PUBLISH WITH EDITS — review flagged items before broadcast."

    # Extract flagged issues
    issues = []
    issue_matches = re.findall(r"(?:issue|concern|flag)[:\s]*(.+?)(?:\n|$)", llm_output, re.IGNORECASE)
    for iss in issue_matches[:3]:
        issues.append({"issue": iss.strip(), "severity": "medium", "suggestion": "Review before publication"})

    return FactCheckResult(
        verified_claims=claims,
        flagged_issues=issues,
        overall_score=score,
        recommendation=recommendation,
    )
