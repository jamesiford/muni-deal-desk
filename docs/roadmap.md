# Build roadmap

Target: **Monday 3 August 2026, 08:00 PDT** — customer organization Foundry session.

This document is the contract between work surfaces. It is written so that the build can
be picked up in VS Code, in a chat assistant, or by another engineer, without re-deriving
context. Each phase states its exit criteria; a phase is not done until they are met and
validated.

## Time budget

Roughly 17 hours of build against a weekend. The critical path is:

```
infra -> knowledge base -> prompt agents -> orchestrator -> runbook -> rehearsal
```

Corpus generation and the MCP server run parallel to that path. If the schedule slips,
cut from the list in "What to cut, in order" rather than compressing rehearsal.

## Phase 1 — Infrastructure

**Status:** complete
**Blocks:** everything

Bicep deployed into `westus3`, subscription `non-production Azure subscription`
(`subscription-id-redacted`).

`eastus2` was the original target and failed with `InsufficientResourcesAvailable` on
Azure AI Search. `westus3` carries all four model versions at identical SKUs, so the
move required no template change beyond the location.

Deployed resources: Foundry account and project, four model deployments
(`gpt-5.4-mini`, `gpt-5.5`, `model-router`, `text-embedding-3-large`), Azure AI Search
with semantic ranking, storage for the corpus, a Container Apps environment and
container registry for the MCP server and orchestrator, a user-assigned workload
identity, and Log Analytics with Application Insights.

Content Understanding is reached through the same `AIServices` account rather than as a
separate resource.

Four model deployments is deliberate: a single deployment makes the cost attribution
panel a flat line, which defeats the point of showing it.

**Exit criteria — all met**

- [x] `az bicep build --file infra/main.bicep` compiles with no errors
- [x] `azd up` completes
- [x] Foundry project opens in the portal and lists all four deployments
- [x] Application Insights receives a test trace
- [x] No runtime identity holds `Owner` or `Contributor`

**Validation (31 July 2026):** `azd up` completed end to end in 2m35s, deploying the
Container Apps environment `cae-wdrdcs6ulivnk`, registry `crwdrdcs6ulivnk` and workload
identity alongside the earlier resources.

`scripts/verify_environment.py` now runs as part of the post-provision hook on every
`azd up`, because provisioning success is not the same as a working environment. It
confirms chat completions return from both the extraction and reasoning tiers under
Entra authentication, the Search data plane is reachable, and a span is accepted by
Application Insights. All four checks pass.

Role assignments confirmed at resource scope. The workload identity holds only
`Search Index Data Reader`, `Cognitive Services OpenAI User`, `Storage Blob Data Reader`
and `AcrPull`. No runtime identity holds `Owner` or `Contributor`.

## Phase 2 — Synthetic corpus

**Status:** complete
**Parallel with:** Phase 1

Generate roughly 12 documents as PDFs: official statements, continuing disclosure annual
reports, and material event notices for fictional Texas school districts. Plus a small
set of private-side precedent pricing records.

Synthetic only. Nothing is retrieved from MSRB EMMA; its Terms of Use prohibit automated
access, database creation from its content, and OCR of imaged documents.

Planted defects, because a guardrail that fires only sometimes is not demonstrable:

| Defect | Purpose |
| --- | --- |
| One issue with no stated call provisions | Forces an evidence gap into the answer |
| One continuing disclosure filed late | Gives the compliance path something real to flag |
| Two documents disagreeing on an enrollment figure | Exercises groundedness scoring |
| Three deals visible only to private-side claims | Drives the entitlement contrast |

**Exit criteria**

- Documents render as readable PDFs
- Each carries a sensitivity classification
- A manifest maps document id to expected extracted fields, for eval grading
- Every planted defect is recorded in the manifest with the behaviour it should trigger

**Validation (31 July 2026):** generated 14 readable PDFs matching the requested document
mix, with extraction ground truth, sensitivity labels, ACL claims and all planted defects in
the manifest. PDF render/text checks, Ruff and all 28 unit tests pass.

## Phase 3 — Extraction and knowledge base

**Depends on:** 1, 2

Content Understanding analyzer extracting typed fields: par amount, security type,
dated date, maturities, coupons, call provisions, ratings. Azure AI Search index with
integrated vectorization for narrative chunks, plus filterable typed fields and an ACL
field carrying group claims. Foundry IQ knowledge base over the index.

**Exit criteria**

- Extracted fields match the corpus manifest for every document
- A query filtered by public-side claims returns strictly fewer results than the same
  query with private-side claims
- The knowledge base is visible in the Foundry portal and returns cited results
- The withheld-result count is returned to the caller, not silently dropped

## Phase 4 — MCP server

**Depends on:** 1
**Parallel with:** 3

MCP server exposing `compute_debt_service`, `find_comparables` and `get_deal`, as thin
adapters over the existing application handlers. Containerised to Container Apps.
Registered as a Foundry project connection.

**Exit criteria**

- Tools callable over streamable HTTP
- Tool list visible in the Foundry portal connection
- `compute_debt_service` output matches `DebtServiceCalculator` unit test values
- Server authenticates with managed identity, no keys

## Phase 5 — Prompt agents

**Depends on:** 3

Three specialists registered with `PromptAgentDefinition` and `create_version`:
Research, Analyst, Compliance. Each bound to a structured response format from
`domain/contracts`, and to the model tier appropriate to its job — extraction on
`gpt-5.4-mini`, synthesis on `gpt-5.5`.

Registration must be idempotent: compare desired against current and update rather than
duplicate versions.

**Exit criteria**

- All three visible in the portal with instructions, model and tools
- Each runs standalone in the portal playground
- Each returns valid instances of its contract
- Re-running registration produces no duplicate versions

## Phase 6 — Orchestrator

**Depends on:** 4, 5

Agent Framework workflow: planner decomposes, Research and Analyst run, Compliance
gates, human approval before any client-facing draft is returned. Hosted through
`InvocationsHostServer`.

`agent-framework-foundry-hosting` is alpha. If it proves unstable, fall back to a
container agent per ADR-0002 — the workflow and handlers are unchanged because hosting
is confined to `hosts/orchestrator`.

**Exit criteria**

- End-to-end run against the demo question returns a `DealDeskAnswer`
- Trace shows decomposition, retrieval, tool call and model calls
- A guardrail-violating draft is blocked, not annotated
- `requires_human_review` is true on every client-facing draft

## Phase 7 — Evaluations

**Depends on:** 5

Roughly 25 graded questions covering comparables selection, figure accuracy, citation
presence, gap disclosure, entitlement behaviour and guardrail triggers. Graded on
groundedness, retrieval relevance and citation accuracy. CI gate in
`.github/workflows/eval-gate.yml`.

Run the suite against two model tiers so the cost-quality tradeoff is shown with real
numbers rather than asserted.

**Exit criteria**

- Evaluation run visible in the Foundry portal
- Thresholds fail the build when deliberately degraded
- Two-model comparison produces a defensible cost and quality delta

## Phase 8 — Front door application

**Depends on:** 6

React and Vite in plain JSX, served by an async FastAPI backend streaming over SSE.
Part one of the walkthrough: the banker-facing experience, before anything is revealed
about the platform underneath.

Carries an identity switcher between a public-side analyst and a deal-team member, so
the same question asked twice returns different evidence with an explicit disclosure
that results were withheld.

Presentation only. No business logic: it posts a question and an identity, and renders
streamed events. See ADR-0004 for the event contract.

**Exit criteria**

- Question submitted, stages stream, draft renders with citations
- Identity switch visibly changes the evidence and discloses the withheld count
- A guardrail violation surfaces as a blocked draft, not a silent edit
- Runs locally against the deployed backend without a container build

## Phase 9 — Copilot Studio surface

**Depends on:** 6
**First candidate for cutting**

Publish the orchestrator and call it from Copilot Studio into Teams. Requested
specifically by the account team, and slide 14 of the deck promises it.

**Exit criteria**

- Agent reachable from Copilot Studio
- A question asked in Teams returns a cited answer

## Phase 10 — Runbook and rehearsal

**Depends on:** 6, 7, 8

`docs/demo-runbook.md` covering the three-part walkthrough: front door application,
Azure portal resource discovery, then the Foundry portal explored left to right with
the bulk of the time.

**Exit criteria**

- Full run performed start to finish against the deployed environment
- Every portal artifact referenced actually loads
- Timing fits the slot with margin

## Phase 11 — Fallback recording

**Depends on:** 10

Screen recording of the full walkthrough. The deck's speaker notes already call for
this. A live Foundry demo on a Monday morning without a fallback is an avoidable risk.

**Exit criteria**

- Recording covers all three parts
- Stored somewhere reachable without VPN

## What to cut, in order

1. **Copilot Studio surface (Phase 9).** Costs a slide promise. Mitigate by showing the
   published agent endpoint instead.
2. **The optional A2A aside.** Never on the critical path.
3. **Two-model evaluation comparison.** Keep single-model evals; assert the tradeoff
   from the model catalogue instead of measuring it.
4. **Front door application (Phase 8).** Falls back to the Foundry playground. Costs the
   three-part structure, which is why it is cut after Copilot Studio rather than before.
5. **Content Understanding (Phase 3).** Fall back to Search-only. Costs the structured
   comparables table and weakens the calculator's inputs. Last resort.

Do not cut: the guardrail refusal, the entitlement contrast, or the trace view. Those
three are the moments that distinguish this from a generic chatbot demo.

## Standing rules

Full detail in `.github/copilot-instructions.md`. The ones most often violated under
time pressure:

- Synthetic data only; never automate access to EMMA
- Never claim on-behalf-of enforcement; this is ACL-aware retrieval with query-time
  group claims
- No figure reaching a client document originates from a language model
- Do not describe a component as working before its validation passes
