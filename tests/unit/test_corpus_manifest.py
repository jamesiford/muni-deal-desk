"""Synthetic corpus manifest contract tests."""

from __future__ import annotations

from src.corpus.generate import DEAL_TEAM_GROUP, SUBJECT_ACCESS_GROUP, generate_corpus
from src.corpus.manifest import CorpusManifest, DefectKind
from src.domain.entities.deal import Sensitivity


def test_generated_manifest_round_trips(tmp_path):
    manifest = generate_corpus(tmp_path)
    serialized = manifest.model_dump_json()

    assert CorpusManifest.model_validate_json(serialized) == manifest
    assert (
        CorpusManifest.model_validate_json((tmp_path / "manifest.json").read_text(encoding="utf-8"))
        == manifest
    )
    assert len(manifest.documents) == 14
    assert {path.name for path in (tmp_path / "public").glob("*.pdf")} == {
        document.blob_path for document in manifest.public_documents()
    }
    assert all(document.expected_deal is not None for document in manifest.documents)
    assert manifest.subject_deal is not None
    assert manifest.subject_deal.deal_id == "DEAL-SUBJECT-001"
    assert manifest.subject_deal.par_amount == 85_000_000
    assert manifest.subject_allowed_group_claims == [SUBJECT_ACCESS_GROUP, DEAL_TEAM_GROUP]


def test_every_defect_kind_is_present(tmp_path):
    manifest = generate_corpus(tmp_path)
    defect_kinds = {defect.kind for document in manifest.documents for defect in document.defects}

    assert defect_kinds == set(DefectKind)


def test_group_claims_match_document_sensitivity(tmp_path):
    manifest = generate_corpus(tmp_path)
    private_documents = [
        document for document in manifest.documents if document.sensitivity is Sensitivity.PRIVATE
    ]
    public_documents = manifest.public_documents()

    assert len(private_documents) == 3
    assert all(document.allowed_group_claims == [DEAL_TEAM_GROUP] for document in private_documents)
    assert all(not document.allowed_group_claims for document in public_documents)
