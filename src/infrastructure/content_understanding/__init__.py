"""Azure Content Understanding infrastructure adapters."""

from __future__ import annotations

from .analyzer import (
    ANALYZER_ID,
    build_deal_analyzer,
    ensure_deal_analyzer,
    ensure_model_defaults,
)
from .extractor import (
    ContentUnderstandingDealExtractor,
    ManifestGroundedDealExtractor,
    deal_from_content_fields,
)

__all__ = [
    "ANALYZER_ID",
    "ContentUnderstandingDealExtractor",
    "ManifestGroundedDealExtractor",
    "build_deal_analyzer",
    "deal_from_content_fields",
    "ensure_deal_analyzer",
    "ensure_model_defaults",
]
"""Content Understanding adapters: structured field extraction from source documents."""
