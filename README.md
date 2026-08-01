# Municipal Deal Desk

A Microsoft Foundry demonstration solution: a new-issue **Deal Desk** agent for a
public finance broker-dealer desk.

The solution exists to make Foundry platform capabilities visible and explainable in a
customer technical session. Phases 1-4 are complete: infrastructure, synthetic corpus,
Foundry IQ and MCP. Agents, orchestration and evaluations remain roadmap work and must
not be presented as working until their validation passes.

## The scenario

A banker preparing a competitive response asks one deliberately messy question:

> Baytown ISD is issuing about $85 million of unlimited tax school building bonds this
> fall. Pull the three most comparable Texas ISD issues from the last 18 months, compare
> their debt service structure and call features to what we're proposing, flag anything
> in their continuing disclosure that would affect pricing, and draft the market summary
> section for our RFP response.

Answering it requires decomposition, retrieval across several source types, a tool call,
a model switch, a compliance check and a human gate.

## Capability map

| Capability | Status | Where it appears |
| --- | --- | --- |
| Foundry IQ | Complete | Blob-backed public PDF source with model-planned, extractive retrieval |
| MCP and tools | Complete | ACA-hosted debt service, comparables and deal lookup tools |
| Model choice | Deployed | Extraction, reasoning, router and embedding deployments |
| Governance | Implemented for current paths | Source separation, sensitivity labels and withheld counts |
| Guardrails | Complete | Model review plus deterministic blocking and typed human approval |
| Agents | Complete | Three prompt specialists and native Foundry Hosted orchestrator v3 |
| Evaluations | Planned | Phase 7 golden-set promotion gate |
| Tracing and observability | Workflow spans validated | Continuous evaluation remains Phase 7 |

## Architecture

Clean Architecture with inward-pointing dependencies.

```
src/
  domain/          entities, agent contracts, conduct policies   (no dependencies)
  application/     ports, messages, handlers, mediator           (domain only)
  infrastructure/  Azure adapters implementing the ports
  hosts/           composition roots: orchestrator and MCP server
```

The MCP server and the orchestrator dispatch through the same mediator and resolve the
same handler instances, so a calculation or a policy is implemented exactly once.

The Research agent combines two deliberate, separately visible connections:

- `municipal-deal-pdf-blob-source` contains only public PDFs. Foundry IQ generates its
  own Search data source, skillset, index and indexer, and the knowledge base returns
  cited extractive data through `knowledge_base_retrieve`.
- `ManifestDealRepository` reads typed corpus ground truth packaged with the runtime.
  The custom MCP exposes typed lookup/calculation tools, filters private pricing records
  using caller group claims, and reports the number withheld.

Keeping private records out of the public knowledge source makes the demo boundary easy
to inspect. It is still application-level authorization, not on-behalf-of enforcement.

See `docs/decisions/` for the reasoning behind the layering and the agent topology.

## Data

The corpus is **synthetic**. It imitates the structure of public finance documents and
contains no collected content.

The MSRB Website Terms of Use, updated 2 January 2026, expressly prohibit automated
access to EMMA, creation of a database from its content, and OCR of imaged documents.
Nothing in this repository retrieves from EMMA.

The corpus deliberately contains contradictions, gaps and stale disclosures so that
groundedness scoring and guardrails fire deterministically on every run.

## What this solution does not claim

Public narrative retrieval is isolated to public PDFs. Private structured records are
filtered by the application using group claims passed with each message. That is not the
same as end-to-end on-behalf-of enforcement. The distinction is documented in
`docs/guardrails.md` and must be stated accurately when the solution is presented.

The conduct policies are modelled on MSRB Rule G-17, MSRB Rule G-42 and FINRA
Regulatory Notice 24-09. They do not certify compliance with any of them.

## Getting started

```powershell
python -m pip install -e ".[dev]"
./scripts/generate_corpus.ps1
python -m pytest tests/unit      # passes without Azure credentials
python -m ruff check .
```

## Validation

| Check | Command |
| --- | --- |
| Lint | `python -m ruff check .` |
| Format | `python -m ruff format --check .` |
| Unit tests | `python -m pytest tests/unit` |
| Infrastructure | `az bicep build --file infra/main.bicep` |
| Phase 3 cloud artifacts | `python -m scripts.setup_phase3 --validate-content-understanding` |
| Deployed MCP | `python -m scripts.smoke_mcp $(azd env get-value MCP_ENDPOINT)` |
