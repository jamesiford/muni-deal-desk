"""Document extraction adapters for cloud execution and offline validation."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Mapping
from decimal import Decimal
from pathlib import Path
from typing import Protocol

from src.corpus.manifest import CorpusManifest
from src.domain.entities.deal import Deal

from .analyzer import ANALYZER_ID


class _AnalyzePoller(Protocol):
    def result(self) -> object: ...


class ContentUnderstandingClientProtocol(Protocol):
    """Narrow client surface used by the extraction adapter."""

    def begin_analyze_binary(
        self,
        analyzer_id: str,
        binary_input: bytes,
        *,
        content_type: str,
    ) -> _AnalyzePoller:
        """Begin binary document analysis."""
        ...


def _unwrap(field: object) -> object:
    value = getattr(field, "value", field)
    if isinstance(value, Mapping):
        return {name: _unwrap(item) for name, item in value.items()}
    if isinstance(value, list):
        return [_unwrap(item) for item in value]
    return value


def _percentage(value: object) -> object:
    if value is None or isinstance(value, bool):
        return value
    number = Decimal(str(value))
    return number * Decimal("100") if abs(number) <= Decimal("1") else number


def _normalize_percentages(values: dict[str, object]) -> None:
    call = values.get("call_provision")
    if isinstance(call, Mapping):
        normalized_call = dict(call)
        if all(value is None for value in normalized_call.values()):
            values["call_provision"] = None
        else:
            normalized_call["call_price"] = _percentage(normalized_call.get("call_price"))
            if normalized_call.get("is_non_callable") is None:
                normalized_call["is_non_callable"] = False
            values["call_provision"] = normalized_call

    maturities = values.get("maturities")
    if maturities is None:
        values["maturities"] = []
    elif isinstance(maturities, list):
        normalized_maturities: list[object] = []
        for maturity in maturities:
            if not isinstance(maturity, Mapping):
                normalized_maturities.append(maturity)
                continue
            normalized = dict(maturity)
            normalized["coupon_rate"] = _percentage(normalized.get("coupon_rate"))
            normalized["yield_rate"] = _percentage(normalized.get("yield_rate"))
            normalized_maturities.append(normalized)
        values["maturities"] = normalized_maturities

    ratings = values.get("ratings")
    if isinstance(ratings, Mapping):
        normalized_ratings = dict(ratings)
        enhancement = normalized_ratings.pop("enhancement", None)
        if enhancement is not None:
            normalized_ratings["is_enhanced"] = enhancement == "enhanced"
        values["ratings"] = normalized_ratings


def _apply_catalog_metadata(values: dict[str, object], metadata: Mapping[str, object]) -> None:
    """Add identifiers and classification that belong to the document catalog."""
    values["deal_id"] = metadata["deal_id"]
    values["sensitivity"] = metadata["sensitivity"]
    issuer = dict(values["issuer"]) if isinstance(values.get("issuer"), Mapping) else {}
    metadata_issuer = metadata.get("issuer")
    if isinstance(metadata_issuer, Mapping):
        issuer["issuer_id"] = metadata_issuer["issuer_id"]
    values["issuer"] = issuer


def deal_from_content_fields(
    fields: Mapping[str, object],
    document_id: str,
    catalog_metadata: Mapping[str, object] | None = None,
) -> Deal:
    """Translate Content Understanding field wrappers into the domain entity."""
    values = {name: _unwrap(field) for name, field in fields.items()}
    _normalize_percentages(values)
    if catalog_metadata is not None:
        _apply_catalog_metadata(values, catalog_metadata)
    values["source_document_id"] = document_id
    return Deal.model_validate(values)


class ContentUnderstandingDealExtractor:
    """Extract typed deals from local PDF bytes using a durable cloud analyzer."""

    def __init__(
        self,
        client: ContentUnderstandingClientProtocol,
        document_loader: Callable[[str], bytes],
        catalog_metadata_loader: Callable[[str], Mapping[str, object]] | None = None,
    ) -> None:
        self._client = client
        self._document_loader = document_loader
        self._catalog_metadata_loader = catalog_metadata_loader

    async def extract_deal(self, document_id: str) -> Deal | None:
        """Analyze one PDF and map its first content segment to a deal."""
        pdf = self._document_loader(document_id)
        poller = self._client.begin_analyze_binary(
            ANALYZER_ID,
            pdf,
            content_type="application/pdf",
        )
        result = await asyncio.to_thread(poller.result)
        contents = getattr(result, "contents", None)
        if not contents:
            return None
        fields = getattr(contents[0], "fields", None)
        if not fields:
            return None
        metadata = (
            self._catalog_metadata_loader(document_id)
            if self._catalog_metadata_loader is not None
            else None
        )
        return deal_from_content_fields(fields, document_id, metadata)


class ManifestGroundedDealExtractor:
    """Offline-only extraction oracle backed by synthetic corpus ground truth.

    This adapter validates mapping and downstream behavior without credentials. It is
    not evidence that Content Understanding extracted a document successfully.
    """

    def __init__(self, manifest_path: Path) -> None:
        self._manifest_path = manifest_path

    async def extract_deal(self, document_id: str) -> Deal | None:
        """Return the manifest's expected deal for deterministic offline tests."""
        manifest = CorpusManifest.model_validate_json(
            self._manifest_path.read_text(encoding="utf-8")
        )
        entry = next(
            (document for document in manifest.documents if document.document_id == document_id),
            None,
        )
        if entry is None or entry.expected_deal is None:
            return None
        return entry.expected_deal.model_copy(deep=True)
