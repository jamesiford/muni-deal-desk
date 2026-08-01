# 5. Blob-backed Foundry IQ knowledge source

Date: 2026-07-31
Status: Accepted

## Context

The demonstration must expose a durable, inspectable Foundry IQ knowledge source and
knowledge base in the portal. A manually populated Search index satisfies retrieval but
hides the source-document ingestion story and leaves multiple similar artifacts that are
hard to explain on a projector.

The corpus also contains three private pricing memos. Putting them into the same
public-document source without validated document-level permission enforcement would
make the demonstration's entitlement claim indefensible.

The tenant enforces private Blob Storage. Azure AI Search therefore needs a shared
private link, and local upload cannot reach the container directly.

## Decision

Use `azure-search-documents==11.7.0b2` with Search data-plane API
`2026-05-01-preview` to register:

- `municipal-deal-pdf-blob-source`, an `AzureBlobKnowledgeSource` over
  `corpus/pdf/public`
- the source-generated data source, skillset, index and indexer
- `municipal-deal-knowledge-base`, configured with `gpt-5.4-mini`, low retrieval
  reasoning, `extractiveData`, and explicit municipal-document retrieval instructions

Answer instructions remain blank because specialist agents own synthesis. The knowledge
base supplies query planning, retrieval and citations.

Only 11 public PDFs enter the Blob source. The three private pricing memos remain in the
packaged manifest. `ManifestDealRepository` applies caller group claims to those typed
records and reports the number withheld.

Search reaches Blob through an approved shared private link. The generated indexer is
preserved and patched only to set `parameters.configuration.executionEnvironment` to
`private`, as required for reliable shared-private-link execution. Corpus upload uses a
short-lived ACI identity, VNet and private endpoint; those resources and the uploader
image are deleted after use.

## Preview limitation

`2026-05-01-preview` has no production SLA and its SDK models do not fully round-trip the
auto-generated indexer. Generated Search artifacts have fixed names and templates and
must not be manually redesigned. The private execution setting is applied by a
preserve-and-PUT REST update because the preview SDK omits server-owned fields during
serialization.

The Blob knowledge source is public-document-only. It does not demonstrate end-to-end
per-user permission enforcement. Private manifest filtering is application-level, not
on-behalf-of authorization.

## Fallback

If the preview Blob knowledge source becomes unavailable, retain the manifest repository
for typed MCP tools and create one manually managed Search index over the same 11 public
PDFs using stable indexer APIs. Register that index as a `SearchIndexKnowledgeSource`
with minimal extractive retrieval. This loses the portal-visible Blob-source ingestion
story but preserves public cited retrieval without exposing private records.

## Validation

The accepted deployment was validated by:

- `python -m scripts.setup_phase3 --validate-content-understanding`
- 14 of 14 Content Understanding results matching the corpus manifest
- Blob ingestion processing 11 documents with zero failures
- generated data source, skillset, index and indexer present under the source name
- knowledge base returning 11 cited references
- a second setup run reporting source, generated indexer and knowledge base unchanged
- live MCP `find_comparables` returning five deals, 11 citations and three withheld
  private source records
- removal of the superseded manual index and index-backed knowledge source
