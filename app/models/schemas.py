"""
PULSE - Pydantic Models / Schemas
Defines data structures used across the application.
"""

from __future__ import annotations
from datetime import datetime
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field
import uuid


# ── Enums ────────────────────────────────────────────────────

class StoryPriority(str, Enum):
    BREAKING = "breaking"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class StoryStatus(str, Enum):
    INCOMING = "incoming"
    SECURITY_SCAN = "security_scan"
    RESEARCHING = "researching"
    TRANSCRIBING = "transcribing"
    VIDEO_ANALYSIS = "video_analysis"
    WRITING = "writing"
    GENERATING_IMAGE = "generating_image"
    GENERATING_PODCAST = "generating_podcast"
    TRANSLATING = "translating"
    FACT_CHECKING = "fact_checking"
    OPTIMIZING = "optimizing"
    COMPLIANCE_REVIEW = "compliance_review"
    READY_TO_PUBLISH = "ready_to_publish"
    PUBLISHED = "published"
    ENDED_BY_USER = "ended_by_user"


class AgentRole(str, Enum):
    ORCHESTRATOR = "orchestrator"
    SECURITY = "security"
    RESEARCHER = "researcher"
    SPEECH = "speech"
    VIDEO = "video"
    WRITER = "writer"
    IMAGE_GENERATOR = "image_generator"
    PODCAST = "podcast"
    TRANSLATOR = "translator"
    FACT_CHECKER = "fact_checker"
    OPTIMIZER = "optimizer"
    COMPLIANCE = "compliance"


# ── Request/Response Models ──────────────────────────────────

class StoryInput(BaseModel):
    """Incoming story request from the user/editor."""
    headline: str = Field(..., description="Story headline or topic")
    description: str = Field(default="", description="Brief description or lead")
    priority: StoryPriority = Field(default=StoryPriority.MEDIUM)
    sources: list[str] = Field(default_factory=list, description="Initial source URLs or references")
    target_audience: str = Field(default="general", description="Target audience segment")


class AgentMessage(BaseModel):
    """A message produced by an agent during processing."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    agent: AgentRole
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    action: str = Field(..., description="What the agent is doing")
    content: str = Field(..., description="Output or status message")
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ResearchResult(BaseModel):
    """Output from the Research Agent."""
    key_facts: list[str] = Field(default_factory=list)
    sources: list[dict[str, str]] = Field(default_factory=list)
    background_context: str = ""
    related_stories: list[str] = Field(default_factory=list)
    data_points: list[dict[str, Any]] = Field(default_factory=list)


class ArticleDraft(BaseModel):
    """Output from the Writer Agent."""
    headline: str = ""
    subheadline: str = ""
    body: str = ""
    summary: str = ""
    word_count: int = 0
    tone: str = "neutral"
    quotes: list[str] = Field(default_factory=list)


class FactCheckResult(BaseModel):
    """Output from the Fact-Check Agent."""
    verified_claims: list[dict[str, Any]] = Field(default_factory=list)
    flagged_issues: list[dict[str, Any]] = Field(default_factory=list)
    overall_score: float = Field(default=0.0, ge=0.0, le=1.0)
    recommendation: str = ""


class SEOResult(BaseModel):
    """Output from the SEO/Headline Optimizer Agent."""
    optimized_headline: str = ""
    meta_description: str = ""
    keywords: list[str] = Field(default_factory=list)
    social_copy: dict[str, str] = Field(default_factory=dict)
    seo_score: float = Field(default=0.0, ge=0.0, le=1.0)


class ComplianceResult(BaseModel):
    """Output from the Compliance Agent."""
    approved: bool = False
    issues: list[dict[str, str]] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)
    legal_flags: list[str] = Field(default_factory=list)
    editorial_notes: list[str] = Field(default_factory=list)


class SpeechResult(BaseModel):
    """Output from the Speech Agent."""
    transcript: str = ""
    language_detected: str = "en-US"
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    duration_seconds: float = 0.0
    speakers: list[dict[str, Any]] = Field(default_factory=list)
    narration_available: bool = False
    narration_voice: str = "en-us-ava:DragonHDOmniLatestNeural"
    narration_duration_estimate: float = 0.0


class TranslationResult(BaseModel):
    """Output from the Translation Agent."""
    source_language: str = "en"
    source_language_name: str = "English"
    target_languages: list[str] = Field(default_factory=list)
    translations: dict[str, dict[str, Any]] = Field(default_factory=dict)
    auto_detected: bool = False
    quality_scores: dict[str, float] = Field(default_factory=dict)


class VideoResult(BaseModel):
    """Output from the Video Agent."""
    duration: float = 0.0
    topics: list[dict[str, Any]] = Field(default_factory=list)
    scenes: list[dict[str, Any]] = Field(default_factory=list)
    faces: list[dict[str, Any]] = Field(default_factory=list)
    ocr_text: list[str] = Field(default_factory=list)
    transcript_segments: list[dict[str, Any]] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    content_moderation: dict[str, bool] = Field(default_factory=dict)


class ImageResult(BaseModel):
    """Output from the Image Generator Agent."""
    hero_image_url: str = ""
    thumbnail_url: str = ""
    alt_text: str = ""
    prompt_used: str = ""
    style: str = "photojournalistic"
    dimensions: str = "1024x1024"
    additional_images: list[dict[str, str]] = Field(default_factory=list)


class PodcastResult(BaseModel):
    """Output from the Podcast Agent."""
    episode_title: str = ""
    episode_summary: str = ""
    script: list[dict[str, str]] = Field(default_factory=list)
    host_a: str = "Alex"
    host_b: str = "Morgan"
    estimated_duration_minutes: float = 0.0
    segments: list[dict[str, Any]] = Field(default_factory=list)
    audio_ready: bool = False


class SecurityResult(BaseModel):
    """Output from the Security Guard Agent."""
    scan_passed: bool = True
    scan_type: str = "inbound"  # inbound | outbound
    risk_score: float = Field(default=0.0, ge=0.0, le=1.0)
    threats_found: list[dict[str, Any]] = Field(default_factory=list)
    pii_detected: list[dict[str, Any]] = Field(default_factory=list)
    injection_detected: bool = False
    data_classification: str = "PUBLIC"  # PUBLIC | INTERNAL | CONFIDENTIAL
    scan_summary: str = ""
    # Outbound scan fields (populated by second pass)
    outbound_scan_passed: Optional[bool] = None
    outbound_risk_score: Optional[float] = None
    outbound_threats: list[dict[str, Any]] = Field(default_factory=list)
    outbound_pii: list[dict[str, Any]] = Field(default_factory=list)


# ── Workflow State ───────────────────────────────────────────

class PipelineState(BaseModel):
    """Full state of the story pipeline, passed through LangGraph."""
    story_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:12])
    input: StoryInput
    status: StoryStatus = StoryStatus.INCOMING
    messages: list[AgentMessage] = Field(default_factory=list)
    research: Optional[ResearchResult] = None
    speech: Optional[dict] = None
    video: Optional[dict] = None
    draft: Optional[ArticleDraft] = None
    image: Optional[dict] = None
    podcast: Optional[dict] = None
    translation: Optional[dict] = None
    fact_check: Optional[FactCheckResult] = None
    seo: Optional[SEOResult] = None
    compliance: Optional[ComplianceResult] = None
    security: Optional[SecurityResult] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    current_agent: Optional[AgentRole] = None
    iteration_count: int = 0
    error: Optional[str] = None


# ── API Response Models ──────────────────────────────────────

class StoryResponse(BaseModel):
    """API response after submitting a story."""
    story_id: str
    status: StoryStatus
    message: str


class PipelineStatusResponse(BaseModel):
    """API response for pipeline status queries."""
    story_id: str
    status: StoryStatus
    current_agent: Optional[AgentRole]
    messages: list[AgentMessage]
    progress_pct: float = 0.0
    draft: Optional[ArticleDraft] = None
    seo: Optional[SEOResult] = None
    fact_check: Optional[FactCheckResult] = None
    compliance: Optional[ComplianceResult] = None
    speech: Optional[dict] = None
    video: Optional[dict] = None
    translation: Optional[dict] = None
    image: Optional[dict] = None
    podcast: Optional[dict] = None
    security: Optional[dict] = None
