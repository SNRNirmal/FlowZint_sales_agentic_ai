"""Structured output schemas for LLM-driven agent nodes.

These replace the current pattern in agents/delay_intelligence.py and
agents/document_generation.py, where LLM responses are manually
json.loads()'d with a bare except fallback. Each of these is bound to
its LLM call via LangChain's `with_structured_output()`, so validation
happens at the model layer instead of ad hoc in agent code.
"""

from pydantic import BaseModel, Field


class DelayPrediction(BaseModel):
    """Structured output of the Delay Intelligence node."""

    delay_probability: float = Field(ge=0.0, le=1.0)
    expected_delay_days: float = Field(ge=0.0)
    root_cause: str
    confidence: float = Field(ge=0.0, le=1.0)
    metadata: dict = Field(default_factory=dict)


class DraftedArtifact(BaseModel):
    """Structured output of the Document Generator node."""

    content: str
    format_used: str
    approver_id: str
    metadata: dict = Field(default_factory=dict)


class DraftedNudge(BaseModel):
    """Structured output of the Communication Planner node."""

    message: str
    urgency: str = Field(pattern="^(low|normal|high)$")
    approver_id: str
    metadata: dict = Field(default_factory=dict)


class TwinConfidenceAssessment(BaseModel):
    """Computed (not LLM-generated) alongside a BehavioralTwinSnapshot,
    to decide whether the Human Review low-confidence branch should
    fire. Kept as its own schema so the confidence-computation logic
    is independently testable and swappable."""

    approver_id: str
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str
