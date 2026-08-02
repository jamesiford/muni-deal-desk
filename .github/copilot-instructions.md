# GitHub Copilot Repository Instructions

## Purpose

Build a Microsoft Foundry L200 demonstration solution for a customer technical session:
a municipal new-issue **Deal Desk** agent for a public finance broker-dealer desk.

The solution exists to make Foundry platform capabilities *visible and explainable*.
Every capability below must have a corresponding artifact a presenter can open and
narrate in the Microsoft Foundry portal, and equivalent source a presenter can open in
VS Code:

Agents, MCP, Foundry IQ, Evaluations, Observability, Tracing, Model choice, Tools,
Governance, Guardrails.

## Current validated state

Phases 1-8, 7A and 10 are complete in azd environment `demo-vnet`, resource group
`rg-muni-deal-desk-demo-vnet`, region `westus3`. The retired `demo` environment and
resource group were removed.

- Prompt specialists: Research v1, Analyst v1, Compliance v1.
- Hosted orchestrator: `municipal-deal-desk-orchestrator` v4, Invocations 2.0.0.
- Foundry IQ: 11 public PDFs; three private `PM-*` records remain manifest-only.
- Final evaluation: both mini and reasoning configurations passed 25/25 portal rows,
  with zero failed and zero errored rows.
- Front door: React/Vite output served by local FastAPI. It is not an Azure service.
  `azure.yaml` deploys only MCP and the hosted orchestrator.
- Presentation brand: Zava Securities is fictional. customer is the customer audience,
  not the owner or source of any synthetic issuer, document or private pricing record.
- Zava palette: deep teal `#15353b`, aqua `#35a49a` and cool gray `#52666a` define the
  brand. Use teal/aqua for primary interaction and progress; reserve red/amber for
  semantic danger and warning states. Preserve light/dark contrast and mobile fit.
- Promoted experience: branch-aware granular SSE statuses, active spinners and GFM
  table rendering pass all local checks and a native v4 cloud invocation. Superseded v3
  was removed after v4 passed approval-resume validation.
- Phase 9 status: the Copilot Studio Azure AI Foundry Agent Service connector was found
  and configured with the correct project endpoint, but DLP policy
  `Personal Developer - (default)` blocks connection creation. The user cannot change
  policy or create another environment. Do not claim Teams/Copilot Studio integration
  works and do not build an A2A/MCP/HTTP bypass unless the user explicitly reopens the
  architecture. Phase 11 fallback recording is the next actionable phase.

Do not recreate retired resources, superseded agent versions, failed evaluation
definitions or temporary evaluation agents. Preserve the final evaluation and its two
file-backed datasets unless the user explicitly requests a new promoted run.

## Presentation constraint (drives design)

This is a demo asset. Two rules follow from that and outrank convenience:

1. **Portal-visible artifacts.** Prefer implementations that register a durable,
   inspectable artifact in the Foundry portal (agent versions, knowledge bases,
   evaluation runs, traces, connections, analyzers) over implementations that only
   exist at runtime or only in code.
2. **Readable on a projector.** Code shown on stage must be short, well named, and
   commented with intent rather than mechanics. Prefer a hand-rolled 60-line mediator
   that can be read aloud over a dependency that cannot.

Neither rule permits inventing capabilities or overstating what a component proves.

## Architecture

Clean Architecture with strict inward-pointing dependencies. SOLID throughout. DRY:
a rule or calculation is defined once and reached from every surface that needs it.

```
src/
  domain/          no dependencies on other layers or on Azure SDKs
  application/     depends on domain only; defines ports and message handlers
  infrastructure/  implements application ports; owns all Azure SDK usage
  hosts/           composition roots only; wiring, no business logic
```

Dependency rule: `hosts -> infrastructure -> application -> domain`. Never the reverse.
`domain` and `application` must remain importable without Azure credentials so unit
tests run offline.

### Mediator

Application use cases are dispatched through a small hand-rolled mediator
(`application/mediator.py`). Handlers register by message type. This keeps hosts
decoupled from handlers and lets the MCP server and the orchestrator invoke the same
handler without duplication.

Do not add a third-party mediator dependency.

### Ports

All outbound dependencies are expressed as Protocol interfaces in
`application/ports/`. Infrastructure adapters implement them. Handlers depend on the
Protocol, never on a concrete adapter, and never import from `infrastructure`.

## Agent topology

Two agent kinds, deliberately, so the session can show both build surfaces:

- **Prompt agents** (`azure-ai-projects`, `PromptAgentDefinition` + `create_version`):
  the Research, Analyst and Compliance specialists. Registered as versioned agents so
  they are individually viewable, editable and testable in the Foundry portal.
- **Hosted workflow agent** (Microsoft Agent Framework): the Deal Desk orchestrator.
  A MAF workflow converted with `.as_agent()` and hosted via
  `agent_framework_foundry_hosting.InvocationsHostServer`. Deploy Python source directly
  with `host: azure.ai.agent`; do not add a second orchestrator Container App.

Use the **Invocations** protocol for the orchestrator (websocket, SSE keepalive and
cancellation support suit a multi-minute multi-agent run).

Agent-to-agent communication uses checkpointed MAF functional workflow steps carrying
typed Pydantic messages. Do not use A2A for internal specialist wiring: MAF's A2A
support is client-side, intended for consuming externally hosted agents. A2A may be
used only for an optional, non-critical-path demonstration of protocol interop.

## Structured I/O

Every specialist-to-orchestrator handoff uses a Pydantic model from
`domain/contracts/` as `response_format`. Untyped free-text handoffs are not
acceptable. The same contract objects are asserted against by the evaluation suite.

## Data rules

- **Synthetic data only.** The corpus is generated, not collected.
- **Never scrape, crawl, bulk-download, OCR or otherwise automate access to MSRB EMMA.**
  The MSRB Website Terms of Use (updated 2 January 2026) expressly prohibit automated
  access, database creation from its content, and OCR of imaged documents. Corpus
  documents imitate the *structure* of public finance documents; they contain no
  content retrieved from EMMA.
- Do not use real issuer names in a way that implies real financial data. Synthetic
  issuers must be clearly fictional.
- The corpus deliberately contains planted contradictions, gaps and stale disclosures so
  groundedness scoring and guardrails fire deterministically on every run.
- The Foundry IQ Blob knowledge source contains public PDFs only. Private pricing memos
  must never be uploaded under its `pdf/public` prefix.

## Retrieval topology

- Foundry IQ uses one `AzureBlobKnowledgeSource` over public synthetic PDFs. Azure AI
  Search owns the generated data source, skillset, index and indexer; do not edit or
  create competing manual versions of those generated artifacts.
- The knowledge base uses `gpt-5.4-mini` for low-effort query planning and returns
  `extractiveData`. Retrieval instructions are populated; answer instructions are blank
  because specialist agents, not the knowledge base, own synthesis.
- The Research agent connects directly to the Foundry IQ knowledge base through the
  `municipal-deal-foundry-iq` connection and `knowledge_base_retrieve`. The separate
  Deal Desk MCP supplies typed candidates and calculations; it must not proxy IQ.
- Typed deal lookup and private-side comparables use the packaged corpus manifest through
  `ManifestDealRepository`. It applies caller group claims in application code and
  returns the number of private source records withheld.
- Do not add a second hand-managed Search index for the same corpus. One portal-visible
  Blob-generated index is deliberate and keeps the demonstration unambiguous.

## Security rules

- Never commit secrets, tokens, certificates, API keys, or credential-bearing
  connection strings. No generated local environment files.
- Use managed identity and Microsoft Entra authentication wherever supported.
- Keep deployment, Foundry project, Search, MCP workload and hosted-agent identities
  distinct. Foundry creates a dedicated identity for the hosted orchestrator; the MCP
  server retains its own user-assigned identity.
- Grant runtime identities only what they need, at the narrowest practical scope.
- Do not grant runtime identities `Owner` or `Contributor`.
- End users receive `Foundry Agent Consumer` at individual-agent scope where possible.
  Do not grant end users `Foundry User`, `Contributor` or `Owner`.

## Accuracy rules

These exist because the audience is a regulated financial institution and the presenter
must not overstate the platform.

- **Do not claim per-user permission enforcement that is not implemented.** Public
  narrative retrieval is physically separated into a public-only Blob knowledge source.
  Private pricing records are filtered by `ManifestDealRepository` using caller group
  claims in application code. Neither path is end-to-end on-behalf-of enforcement.
  Documentation and narration must state the difference. See `docs/guardrails.md`.
- Do not describe a component as working until its validation exists and passes.
- Preview and prerelease dependencies are permitted only with the exact version,
  the limitation, a fallback, and a validation step documented in
  `docs/decisions/`. `agent-framework-foundry-hosting` is prerelease and requires this.
- Regulatory references (MSRB Rule G-17, MSRB Rule G-42, FINRA Regulatory Notice 24-09)
  must be described accurately and must not be paraphrased into legal advice. Guardrails
  are *modelled on* these obligations; the code does not certify compliance.

## Engineering rules

- Python 3.14. Azure Developer CLI and Bicep for infrastructure.
- `from __future__ import annotations` in every module. Full type hints.
- Format and lint with `ruff`. Line length 100.
- Registration scripts must be idempotent: compare desired against current and update
  rather than duplicate.
- Keep Bicep modules syntactically valid and idempotent; compile after every edit.
- Use `TODO` comments only for tenant-specific values, prerelease APIs, or steps
  requiring manual validation.
- Comment intent, not mechanics. Explain *why* a decision was made where it is not
  obvious. Do not narrate what the next line plainly does.

## Validation expectations

- `ruff check` and `ruff format --check` pass.
- `pytest tests/unit` passes without Azure credentials.
- `az bicep build --file infra/main.bicep` compiles with no errors.
- Scan for accidentally committed credentials before any push.
- The evaluation gate in `.github/workflows/eval-gate.yml` must pass before an agent
  version is promoted.
- The canonical full local gate is:
  `pytest tests/unit tests/integration`, `ruff check .`, `ruff format --check .`,
  `python -m evals.runner --local-only --environment demo-vnet`,
  `npm run build --prefix frontend`, and `az bicep build --file infra/main.bicep`.
- Run the presentation front door locally after building `frontend/dist`; do not add an
  Azure frontend host unless a future roadmap decision explicitly changes the topology.
