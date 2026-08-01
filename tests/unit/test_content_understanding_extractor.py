"""Focused tests for Content Understanding deal extraction."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

import pytest
from scripts.setup_phase3 import _validate_content_understanding
from src.corpus.manifest import CorpusManifest
from src.infrastructure.content_understanding.analyzer import (
    build_deal_analyzer,
    ensure_deal_analyzer,
)
from src.infrastructure.content_understanding.extractor import (
    ContentUnderstandingDealExtractor,
    ManifestGroundedDealExtractor,
    deal_from_content_fields,
)


@dataclass
class Field:
    value: object


class Poller:
    def __init__(self, result: object) -> None:
        self._result = result

    def result(self) -> object:
        return self._result


@dataclass
class Content:
    fields: dict[str, Field]


@dataclass
class Result:
    contents: list[Content]


class Client:
    def __init__(self, result: Result) -> None:
        self.result = result
        self.calls: list[tuple[str, bytes, str]] = []

    def begin_analyze_binary(
        self,
        analyzer_id: str,
        binary_input: bytes,
        *,
        content_type: str,
    ) -> Poller:
        self.calls.append((analyzer_id, binary_input, content_type))
        return Poller(self.result)


class ExistingAnalyzerClient:
    def __init__(self, analyzer: object, *, extra_field: bool = False) -> None:
        self.analyzer = analyzer
        self.extra_field = extra_field
        self.updated = False
        self.deleted = False
        self.created = False

    def get_analyzer(self, *, analyzer_id: str) -> object:
        assert analyzer_id == "municipal_deal_extraction"
        current = self.analyzer.as_dict()
        current["server_default"] = "added"
        if self.extra_field:
            current["fieldSchema"]["fields"]["removed_field"] = {"type": "string"}

        class Analyzer:
            def as_dict(self) -> dict[str, object]:
                return current

        return Analyzer()

    def update_analyzer(self, **_kwargs: object) -> None:
        self.updated = True

    def delete_analyzer(self, **_kwargs: object) -> None:
        self.deleted = True

    def begin_create_analyzer(self, **_kwargs: object) -> Poller:
        self.created = True
        return Poller(None)


def _wrapped(value: object) -> Field:
    if isinstance(value, dict):
        return Field({name: _wrapped(item) for name, item in value.items()})
    if isinstance(value, list):
        return Field([_wrapped(item) for item in value])
    return Field(value)


def _fields() -> dict[str, Field]:
    return {
        "deal_id": Field("DEAL-TEST"),
        "issuer": Field(
            {
                "issuer_id": Field("FICT-TEST"),
                "name": Field("Test Fictional Independent School District"),
                "state": Field("TX"),
                "county": Field("Travis"),
                "enrollment": Field(1000),
                "taxable_assessed_valuation": Field(Decimal("100000000")),
            }
        ),
        "series_name": Field("Unlimited Tax School Building Bonds, Series 2026"),
        "security_type": Field("unlimited_tax"),
        "par_amount": Field(Decimal("10000000")),
        "dated_date": Field("2026-02-15"),
        "first_maturity": Field("2028-08-15"),
        "final_maturity": Field("2029-08-15"),
        "ratings": Field(
            {
                "moodys": Field("Aa1"),
                "sp": Field("AAA"),
                "fitch": Field(None),
                "is_enhanced": Field(True),
            }
        ),
        "call_provision": Field(None),
        "maturities": Field(
            [
                Field(
                    {
                        "maturity_date": Field("2028-08-15"),
                        "principal_amount": Field(Decimal("5000000")),
                        "coupon_rate": Field(Decimal("4.25")),
                        "yield_rate": Field(Decimal("4.10")),
                    }
                ),
                Field(
                    {
                        "maturity_date": Field("2029-08-15"),
                        "principal_amount": Field(Decimal("5000000")),
                        "coupon_rate": Field(Decimal("4.50")),
                        "yield_rate": Field(None),
                    }
                ),
            ]
        ),
        "sensitivity": Field("public"),
    }


def test_content_fields_map_to_typed_deal() -> None:
    deal = deal_from_content_fields(_fields(), "OS-TEST")

    assert deal.source_document_id == "OS-TEST"
    assert deal.par_amount == Decimal("10000000")
    assert deal.call_provision is None
    assert deal.ratings.sp == "AAA"
    assert deal.maturities[0].coupon_rate == Decimal("4.25")
    assert deal.maturities[1].yield_rate is None


def test_content_fields_normalize_cloud_percentages_and_call_flags() -> None:
    fields = _fields()
    fields["call_provision"] = Field(
        {
            "first_call_date": Field("2034-08-15"),
            "call_price": Field(Decimal("1")),
            "is_non_callable": Field(None),
        }
    )
    maturities = fields["maturities"].value
    assert isinstance(maturities, list)
    first = maturities[0].value
    assert isinstance(first, dict)
    first["coupon_rate"] = Field(Decimal("0.0425"))
    first["yield_rate"] = Field(Decimal("0.041"))

    deal = deal_from_content_fields(fields, "OS-TEST")

    assert deal.call_provision is not None
    assert deal.call_provision.call_price == Decimal("100")
    assert deal.call_provision.is_non_callable is False
    assert deal.maturities[0].coupon_rate == Decimal("4.25")
    assert deal.maturities[0].yield_rate == Decimal("4.1")


def test_content_fields_collapse_empty_call_object() -> None:
    fields = _fields()
    fields["call_provision"] = Field(
        {
            "first_call_date": Field(None),
            "call_price": Field(None),
            "is_non_callable": Field(None),
        }
    )

    deal = deal_from_content_fields(fields, "OS-TEST")

    assert deal.call_provision is None


def test_content_fields_map_absent_maturity_table_to_empty_schedule() -> None:
    fields = _fields()
    fields["maturities"] = Field(None)

    deal = deal_from_content_fields(fields, "OS-TEST")

    assert deal.maturities == []


def test_catalog_metadata_adds_identity_without_overriding_extracted_terms() -> None:
    fields = _fields()
    del fields["deal_id"]
    del fields["sensitivity"]
    issuer = fields["issuer"].value
    assert isinstance(issuer, dict)
    del issuer["issuer_id"]

    deal = deal_from_content_fields(
        fields,
        "OS-TEST",
        {
            "deal_id": "CATALOG-DEAL",
            "issuer": {"issuer_id": "CATALOG-ISSUER"},
            "sensitivity": "private",
            "par_amount": Decimal("1"),
        },
    )

    assert deal.deal_id == "CATALOG-DEAL"
    assert deal.issuer.issuer_id == "CATALOG-ISSUER"
    assert deal.sensitivity.value == "private"
    assert deal.par_amount == Decimal("10000000")


def test_analyzer_reconciliation_ignores_server_added_defaults() -> None:
    analyzer = build_deal_analyzer(
        completion_model="gpt-5.4-mini",
        embedding_model="text-embedding-3-large",
    )
    client = ExistingAnalyzerClient(analyzer)

    status = ensure_deal_analyzer(client, analyzer)

    assert status == "unchanged"
    assert client.updated is False


def test_analyzer_reconciliation_replaces_when_field_was_removed() -> None:
    analyzer = build_deal_analyzer(
        completion_model="gpt-5.4-mini",
        embedding_model="text-embedding-3-large",
    )
    client = ExistingAnalyzerClient(analyzer, extra_field=True)

    status = ensure_deal_analyzer(client, analyzer)

    assert status == "replaced"
    assert client.updated is False
    assert client.deleted is True
    assert client.created is True


async def test_cloud_extractor_submits_pdf_and_maps_result() -> None:
    client = Client(Result([Content(_fields())]))
    extractor = ContentUnderstandingDealExtractor(client, lambda _document_id: b"%PDF-test")

    deal = await extractor.extract_deal("OS-TEST")

    assert deal is not None
    assert deal.deal_id == "DEAL-TEST"
    assert client.calls == [("municipal_deal_extraction", b"%PDF-test", "application/pdf")]


async def test_manifest_grounded_extractor_matches_every_expected_deal() -> None:
    manifest_path = Path("src/corpus/out/manifest.json")
    extractor = ManifestGroundedDealExtractor(manifest_path)

    import json

    documents = json.loads(manifest_path.read_text(encoding="utf-8"))["documents"]
    for document in documents:
        extracted = await extractor.extract_deal(document["document_id"])
        assert extracted is not None
        assert extracted.model_dump(mode="json") == document["expected_deal"]


async def test_cloud_manifest_validation_compares_every_typed_field(tmp_path: Path) -> None:
    full_manifest = CorpusManifest.model_validate_json(
        Path("src/corpus/out/manifest.json").read_text(encoding="utf-8")
    )
    entry = full_manifest.documents[0]
    assert entry.expected_deal is not None
    manifest = full_manifest.model_copy(update={"documents": [entry]})
    (tmp_path / entry.blob_path).write_bytes(b"%PDF-test")
    expected = entry.expected_deal.model_dump(
        mode="python",
        exclude={"source_document_id"},
    )
    client = Client(Result([Content({name: _wrapped(value) for name, value in expected.items()})]))

    count = await _validate_content_understanding(client, manifest, tmp_path)

    assert count == 1


async def test_cloud_manifest_validation_names_mismatched_document(tmp_path: Path) -> None:
    full_manifest = CorpusManifest.model_validate_json(
        Path("src/corpus/out/manifest.json").read_text(encoding="utf-8")
    )
    entry = full_manifest.documents[0]
    assert entry.expected_deal is not None
    manifest = full_manifest.model_copy(update={"documents": [entry]})
    (tmp_path / entry.blob_path).write_bytes(b"%PDF-test")
    expected = entry.expected_deal.model_dump(
        mode="python",
        exclude={"source_document_id"},
    )
    expected["par_amount"] = Decimal("1")
    client = Client(Result([Content({name: _wrapped(value) for name, value in expected.items()})]))

    with pytest.raises(RuntimeError, match=entry.document_id):
        await _validate_content_understanding(client, manifest, tmp_path)
