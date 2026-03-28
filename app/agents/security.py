"""
PULSE - Security Guard Agent
Scans content at pipeline entry (inbound) and exit (outbound) for:
  - Prompt injection / jailbreak attempts
  - PII leakage (SSN, credit cards, emails, phone numbers)
  - Harmful / toxic content
  - Data classification (PUBLIC / INTERNAL / CONFIDENTIAL)

Uses Azure AI Content Safety API in live mode; rule-based scanning in demo mode.
"""

import logging
from datetime import datetime
from app.config import settings
from app.models.schemas import (
    AgentMessage, AgentRole, PipelineState,
    SecurityResult, StoryStatus,
)
from app.services.content_safety import scan_content
from app.services.audit_trail import record_audit_event

logger = logging.getLogger("pulse.agent.security")


async def security_inbound_agent(state: dict) -> dict:
    """
    Security Guard (Inbound) — scans the incoming story input for threats
    before it enters the pipeline. Runs immediately after orchestrator triage.
    """
    pipeline = PipelineState(**state)
    pipeline.current_agent = AgentRole.SECURITY
    pipeline.status = StoryStatus.SECURITY_SCAN

    headline = pipeline.input.headline
    description = pipeline.input.description
    combined_input = f"{headline}\n{description}"

    pipeline.messages.append(AgentMessage(
        agent=AgentRole.SECURITY,
        action="inbound_scan_start",
        content="🛡️ Security Guard: Scanning inbound content for threats, PII, and injection attempts…",
        confidence=0.95,
    ))

    # Scan the input text
    scan_result = await scan_content(combined_input, content_type="input")

    # Build SecurityResult
    threats = scan_result.get("threats", [])
    pii_items = scan_result.get("pii_detected", [])
    is_safe = scan_result.get("safe", True)
    risk_score = scan_result.get("risk_score", 0.0)

    # Classify data sensitivity
    classification = _classify_content(combined_input, threats)

    security = SecurityResult(
        scan_passed=is_safe,
        scan_type="inbound",
        risk_score=risk_score,
        threats_found=threats,
        pii_detected=pii_items,
        injection_detected=scan_result.get("injection_detected", False),
        data_classification=classification,
        scan_summary=_build_summary(is_safe, threats, pii_items, classification),
    )
    pipeline.security = security

    # Record audit trail event
    await record_audit_event(
        story_id=pipeline.story_id,
        agent=AgentRole.SECURITY,
        action="inbound_scan",
        decision="PASS" if is_safe else "FLAG",
        confidence=1.0 - risk_score,
        details={
            "threats_count": len(threats),
            "pii_count": len(pii_items),
            "injection": scan_result.get("injection_detected", False),
            "classification": classification,
            "risk_score": risk_score,
        },
    )

    # Build status message
    if is_safe:
        status_msg = (
            f"✅ Inbound security scan PASSED\n"
            f"- Risk score: {risk_score:.0%}\n"
            f"- Data classification: {classification}\n"
            f"- Threats detected: 0\n"
            f"- PII found: {len(pii_items)} item{'s' if len(pii_items) != 1 else ''}\n"
            f"- Content cleared for pipeline processing"
        )
    else:
        threat_types = set(t["category"] for t in threats)
        status_msg = (
            f"⚠️ Inbound security scan FLAGGED\n"
            f"- Risk score: {risk_score:.0%}\n"
            f"- Data classification: {classification}\n"
            f"- Threats detected: {len(threats)} ({', '.join(threat_types)})\n"
            f"- PII found: {len(pii_items)} item{'s' if len(pii_items) != 1 else ''}\n"
            f"- Content flagged for review — pipeline continues with monitoring"
        )

    pipeline.messages.append(AgentMessage(
        agent=AgentRole.SECURITY,
        action="inbound_scan_complete",
        content=status_msg,
        confidence=1.0 - risk_score,
        metadata={
            "scan_passed": is_safe,
            "risk_score": risk_score,
            "threats_count": len(threats),
            "pii_count": len(pii_items),
            "data_classification": classification,
        },
    ))

    return pipeline.model_dump()


async def security_outbound_agent(state: dict) -> dict:
    """
    Security Guard (Outbound) — scans all generated content before publication.
    Runs as the second-to-last step, right before orchestrator final.
    """
    pipeline = PipelineState(**state)
    pipeline.current_agent = AgentRole.SECURITY
    pipeline.status = StoryStatus.SECURITY_SCAN

    pipeline.messages.append(AgentMessage(
        agent=AgentRole.SECURITY,
        action="outbound_scan_start",
        content="🛡️ Security Guard: Scanning all generated content before publication…",
        confidence=0.95,
    ))

    # Collect all generated content for scanning
    content_blocks = []
    if pipeline.draft:
        content_blocks.append(("Article Draft", f"{pipeline.draft.headline}\n{pipeline.draft.body}"))
    if pipeline.podcast:
        podcast = pipeline.podcast
        if isinstance(podcast, dict):
            script_lines = podcast.get("script", [])
            script_text = " ".join(s.get("text", s.get("line", "")) for s in script_lines if isinstance(s, dict))
            content_blocks.append(("Podcast Script", script_text))
    if pipeline.seo:
        seo_text = f"{pipeline.seo.optimized_headline}\n{pipeline.seo.meta_description}"
        content_blocks.append(("SEO Output", seo_text))
    if pipeline.translation:
        trans = pipeline.translation
        if isinstance(trans, dict):
            for lang, data in trans.get("translations", {}).items():
                if isinstance(data, dict):
                    content_blocks.append((f"Translation ({lang})", data.get("body", "")))

    # Scan each block
    all_threats = []
    all_pii = []
    worst_risk = 0.0
    all_safe = True

    for label, text in content_blocks:
        if not text or not text.strip():
            continue
        result = await scan_content(text, content_type="output")
        if result["threats"]:
            for t in result["threats"]:
                t["source"] = label
            all_threats.extend(result["threats"])
        if result["pii_detected"]:
            for p in result["pii_detected"]:
                p["source"] = label
            all_pii.extend(result["pii_detected"])
        if result["risk_score"] > worst_risk:
            worst_risk = result["risk_score"]
        if not result["safe"]:
            all_safe = False

    # Update security result (merge with inbound)
    existing_security = pipeline.security
    outbound_security = SecurityResult(
        scan_passed=all_safe,
        scan_type="outbound",
        risk_score=worst_risk,
        threats_found=all_threats,
        pii_detected=all_pii,
        injection_detected=False,
        data_classification=existing_security.data_classification if existing_security else "PUBLIC",
        scan_summary=_build_summary(all_safe, all_threats, all_pii,
                                     existing_security.data_classification if existing_security else "PUBLIC"),
    )

    # Keep both inbound and outbound results
    if existing_security:
        existing_security.outbound_scan_passed = all_safe
        existing_security.outbound_risk_score = worst_risk
        existing_security.outbound_threats = all_threats
        existing_security.outbound_pii = all_pii
        pipeline.security = existing_security
    else:
        pipeline.security = outbound_security

    # Record audit trail
    await record_audit_event(
        story_id=pipeline.story_id,
        agent=AgentRole.SECURITY,
        action="outbound_scan",
        decision="PASS" if all_safe else "FLAG",
        confidence=1.0 - worst_risk,
        details={
            "blocks_scanned": len(content_blocks),
            "threats_count": len(all_threats),
            "pii_count": len(all_pii),
            "risk_score": worst_risk,
        },
    )

    blocks_label = ", ".join(label for label, _ in content_blocks) if content_blocks else "none"

    if all_safe:
        status_msg = (
            f"✅ Outbound security scan PASSED\n"
            f"- Content scanned: {len(content_blocks)} block(s) ({blocks_label})\n"
            f"- Risk score: {worst_risk:.0%}\n"
            f"- No threats or PII leakage detected\n"
            f"- Content cleared for publication"
        )
    else:
        threat_types = set(t["category"] for t in all_threats)
        status_msg = (
            f"⚠️ Outbound security scan FLAGGED\n"
            f"- Content scanned: {len(content_blocks)} block(s)\n"
            f"- Risk score: {worst_risk:.0%}\n"
            f"- Threats: {len(all_threats)} ({', '.join(threat_types)})\n"
            f"- PII exposure: {len(all_pii)} item{'s' if len(all_pii) != 1 else ''}\n"
            f"- ⚠️ Review required before publication"
        )

    pipeline.messages.append(AgentMessage(
        agent=AgentRole.SECURITY,
        action="outbound_scan_complete",
        content=status_msg,
        confidence=1.0 - worst_risk,
        metadata={
            "scan_passed": all_safe,
            "risk_score": worst_risk,
            "blocks_scanned": len(content_blocks),
            "threats_count": len(all_threats),
            "pii_count": len(all_pii),
        },
    ))

    return pipeline.model_dump()


def _classify_content(text: str, threats: list) -> str:
    """Classify content sensitivity: PUBLIC, INTERNAL, or CONFIDENTIAL."""
    text_lower = text.lower()

    # CONFIDENTIAL indicators
    confidential_keywords = [
        "confidential", "classified", "off the record", "anonymous source",
        "unnamed source", "whistleblower", "sealed", "grand jury",
        "not for publication", "embargoed",
    ]
    if any(kw in text_lower for kw in confidential_keywords):
        return "CONFIDENTIAL"

    # Check for PII threats → CONFIDENTIAL
    if any(t["category"] == "PII_Exposure" and t["severity"] in ("high", "critical") for t in threats):
        return "CONFIDENTIAL"

    # INTERNAL indicators
    internal_keywords = [
        "internal", "draft", "pre-release", "embargo",
        "not yet announced", "pending approval", "internal memo",
    ]
    if any(kw in text_lower for kw in internal_keywords):
        return "INTERNAL"

    return "PUBLIC"


def _build_summary(is_safe: bool, threats: list, pii_items: list, classification: str) -> str:
    """Build a human-readable scan summary."""
    if is_safe and not threats and not pii_items:
        return f"Content is clean. Classification: {classification}. No threats or PII detected."
    parts = []
    if threats:
        cats = set(t["category"] for t in threats)
        parts.append(f"{len(threats)} threat(s) ({', '.join(cats)})")
    if pii_items:
        types = [p["label"] for p in pii_items]
        parts.append(f"PII: {', '.join(types)}")
    parts.append(f"Classification: {classification}")
    return "; ".join(parts)
