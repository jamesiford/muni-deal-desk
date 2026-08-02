"""Citation and evidence types.

Every factual claim an agent surfaces must be traceable to a source document. These
types make that traceability structural rather than a matter of prompt discipline.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from src.domain.entities.deal import Sensitivity


class Citation(BaseModel):
    """A reference to the specific passage that supports a claim."""

    document_id: str
    document_title: str
    page: int | None = None
    excerpt: str = Field(description="Verbatim supporting text. Never paraphrased.")
    sensitivity: Sensitivity = Sensitivity.PUBLIC


class EvidenceGap(BaseModel):
    """A question the corpus could not answer.

    Recorded explicitly so the orchestrator can report an absence rather than allow a
    model to fill the gap. Planted gaps in the synthetic corpus make this path fire
    on every demo run.
    """

    question: str
    reason: str


class EvidenceSource(BaseModel):
    """A source record considered during deterministic comparable selection."""

    document_id: str
    document_title: str
    deal_id: str
    source_type: str
    sensitivity: Sensitivity
