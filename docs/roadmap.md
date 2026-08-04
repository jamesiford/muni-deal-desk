# Build roadmap

Target: reusable Microsoft Foundry technical demonstration.

This document is the contract between work surfaces. It is written so that the build can
be picked up in VS Code, in a chat assistant, or by another engineer, without re-deriving
context. Each phase states its exit criteria; a phase is not done until they are met and
validated.

## Current position

| Phase | Status | Result |
| --- | --- | --- |
| 1-6 | Complete | Infrastructure, corpus, IQ, MCP, prompt agents and hosted workflow |
| 7 and 7A | Complete | Private-storage evaluation path and final 25-case two-model runs |
| 8 | Complete | Local fictional Zava Securities React/FastAPI presentation front door |
| 9 | **Blocked** | Direct connector discovered; tenant DLP/admin dependency prevents connection creation |
| 10 | Complete | Presenter runbook and end-to-end rehearsal |
| 11 | Pending | Record and store the fallback walkthrough |

The core Foundry demonstration is complete and can run end to end now. Phase 9 reached
the supported Copilot Studio connector but is blocked by tenant governance outside this
repository. Phase 11 is the next actionable session-readiness task because its Phase 10
dependency is already complete.

The frontend is not an Azure service in this topology. `azd up` deploys MCP to Container
Apps and the orchestrator to Foundry Hosted Agents; the presenter builds React and runs
the FastAPI bridge locally against the deployed Invocations endpoint.

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

Bicep deployed into `westus3` in a non-production Azure subscription.

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

**Final validation (1 August 2026):** `azd up --environment demo-vnet` completed end to
end in 7m36s, including private corpus upload, IQ reconciliation, evaluation-storage
smoke, MCP deployment, hosted orchestrator v3 and specialist contract smokes.

`scripts/verify_environment.py` now runs as part of the post-provision hook on every
`azd up`, because provisioning success is not the same as a working environment. It
confirms chat completions return from both the extraction and reasoning tiers under
Entra authentication, the Search data plane is reachable, and a span is accepted by
Application Insights. All four checks pass.

Role assignments confirmed at resource scope. The workload identity holds only
`Search Index Data Reader`, `Cognitive Services OpenAI User`,
`Monitoring Metrics Publisher` and `AcrPull`. No runtime identity holds `Owner` or
`Contributor`.

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

**Status:** complete
**Depends on:** 1, 2

Content Understanding analyzer extracting typed fields: par amount, security type,
dated date, maturities, coupons, call provisions, ratings. A Blob knowledge source over
the public synthetic PDFs automatically generates the Azure AI Search data source,
skillset, index and indexer shown in the portal. A model-backed Foundry IQ knowledge
base orchestrates retrieval over that source. Private pricing memos remain outside the
public knowledge source and are governed through the typed manifest repository.

**Exit criteria — all met**

- [x] Extracted fields match the corpus manifest for every document
- [x] The public knowledge source contains no private documents, and typed retrieval
   returns more source records with the private deal-team claim than without it
- [x] The knowledge base is visible in the Foundry portal and returns cited results
- [x] The withheld-result count is returned to the caller, not silently dropped

**Validation (31 July 2026):** the durable Content Understanding analyzer extracted all
14 documents and every typed `Deal` matched the manifest. The Blob knowledge source
`municipal-deal-pdf-blob-source` ingested all 11 public PDFs through an approved Search
shared private link and generated exactly one source-specific data source, skillset,
index and indexer. The three private pricing memos never enter that source.

The knowledge base `municipal-deal-knowledge-base` uses `gpt-5.4-mini`, low retrieval
reasoning, extractive data output, and municipal-document routing instructions. The chat
model performs query planning; specialist agents own synthesis, so answer instructions
are intentionally blank. The knowledge base returned 11 cited references. The deployed
MCP runtime uses the manifest for typed, ACL-aware comparables and reports three private
source records withheld from public callers. The superseded `municipal-deal-chunks`
index and index-backed knowledge source were deleted; only the Blob-generated index and
Blob knowledge source remain.

**Audit (31 July 2026):** a full Content Understanding validation again matched 14 of
14 documents. Blob ingestion reports 11 processed and zero failed. The source, generated
indexer and knowledge base are unchanged on a repeat run, and retrieval returns 11 cited
references. Live Search inventory contains only the Blob source and its generated data
source, skillset, index and indexer.

## Phase 4 — MCP server

**Status:** complete
**Depends on:** 1
**Parallel with:** 3

MCP server exposing `compute_debt_service`, `find_comparable_deals` and `get_deal`, as thin
adapters over the existing application handlers. Containerised to Container Apps.
Registered as a Foundry project connection.

**Exit criteria — all met**

- [x] Tools callable over streamable HTTP
- [x] Tool list visible in the Foundry portal connection
- [x] `compute_debt_service` output matches `DebtServiceCalculator` unit test values
- [x] Server authenticates with managed identity, no keys

**Final validation (1 August 2026):** `ca-mcp-brl2ihmwze6og` is healthy and serves all
three structured tools over streamable HTTP. `DEAL-001` debt service matched the
deterministic calculator at $30,000,000 principal and $7,672,500 interest.

The idempotent Foundry project connection `muni-deal-desk-mcp` is registered as a
`RemoteTool`. Application Insights contains spans for all three MCP tools. The workload
identity holds only `AcrPull` and telemetry publishing; it has no `Owner` or
`Contributor` assignment.

**Audit (31 July 2026):** `/status` returns `ready`; the endpoint lists all three tools;
`DEAL-001` still matches the deterministic calculator; and `find_comparable_deals`
returns typed deals and withheld private record counts without querying documents. The
Foundry `RemoteTool` connection targets the live endpoint. Application Insights contains
recent spans for all three tools. Runtime roles are exactly `AcrPull` and
`Monitoring Metrics Publisher`.

## Phase 5 — Prompt agents

**Status:** complete
**Depends on:** 3

Three specialists registered with `PromptAgentDefinition` and `create_version`:
Research, Analyst, Compliance. Each bound to a structured response format from
`domain/contracts`, and to the model tier appropriate to its job — extraction on
`gpt-5.4-mini`, synthesis on `gpt-5.5`.

Registration must be idempotent: compare desired against current and update rather than
duplicate versions.

**Exit criteria — all met**

- [x] All three visible in the portal with instructions, model and tools
- [x] Each runs standalone in the portal playground
- [x] Each returns valid instances of its contract
- [x] Re-running registration produces no duplicate versions

**Final validation (1 August 2026):** Research v1, Analyst v1 and Compliance v1 return
provider-enforced Pydantic contracts. Research has separate portal-visible connections
to Foundry IQ and the Deal Desk MCP; its trace completed both
`knowledge_base_retrieve` and `find_comparable_deals`. Analyst and Compliance remained
unchanged, and a reconciliation run created no duplicate versions.

## Phase 6 — Orchestrator

**Status:** complete
**Depends on:** 4, 5

Agent Framework workflow: planner decomposes, Research and Analyst run, Compliance
gates, human approval before any client-facing draft is returned. Hosted through
`InvocationsHostServer`.

`agent-framework-foundry-hosting` is alpha and pinned. The Python source is deployed
directly to Foundry Hosted Agents; Foundry owns containerization, immutable versions,
the dedicated agent identity and the native Invocations endpoint. ADR-0002 records the
removed ACA fallback.

**Exit criteria — all met**

- [x] End-to-end run against the demo question returns a `DealDeskAnswer`
- [x] Trace shows decomposition, retrieval, tool call and model calls
- [x] A guardrail-violating draft is blocked, not annotated
- [x] `requires_human_review` is true on every client-facing draft

**Validation (31 July 2026):** Hosted Agent
`municipal-deal-desk-orchestrator` v3 is active and portal-visible with Invocations
2.0.0, Python 3.14 direct-code hosting and a dedicated agent identity. A typed request
paused at `supervising-principal-approval`, resumed on an explicit typed approval, and
returned four sections, four comparables and deterministic total debt service of
$107,673,750.00 with non-blocking compliance and `requires_human_review=true`.
Application Insights contains successful planner, Research, Analyst, synthesis,
Compliance, deterministic guardrail and approval spans. The replaced orchestrator ACA,
image repository, superseded hosted versions and validation sessions were deleted.

## Phase 7 — Evaluations

**Status:** complete
**Depends on:** 5
**Blocked by:** 7A

Roughly 25 graded questions covering comparables selection, figure accuracy, citation
presence, gap disclosure, entitlement behaviour and guardrail triggers. Graded on
groundedness, retrieval relevance and citation accuracy. CI gate in
`.github/workflows/eval-gate.yml`.

Run the suite against two model tiers so the cost-quality tradeoff is shown with real
numbers rather than asserted.

**Exit criteria**

- [x] Evaluation run visible in the Foundry portal
- [x] Thresholds fail the build when deliberately degraded
- [x] Two-model comparison produces a defensible cost and quality delta

**Validation (1 August 2026):** the committed 25-case local gate passes 100%. Final
portal evaluation `eval_b23afc8b99554c30a7c8af566abb375d` completed both file-backed
runs with 25 passed, zero failed and zero errored rows:

- mini: `evalrun_8229604602a64e8b894f8f13d06c1bf8`
- reasoning: `evalrun_8d1753f9149246d399e97392cf3b010d`

The deterministic Python criterion owns promotion. The fixed `gpt-5.5` score-model
criterion remains visible as an advisory quality/cost comparison metric; it does not
override exact contract, figure, citation, gap, entitlement or guardrail evaluators.

## Phase 7A — Hybrid evaluation networking and corpus evidence

**Status:** complete
**Depends on:** 1, 3
**Blocks:** Phase 7 portal completion

Recreate the Foundry account in a parallel azd environment with outbound VNet injection
configured at account creation. Keep Foundry inbound access public and Entra-protected
for the customer walkthrough, while evaluations reach policy-compliant private Blob
storage through a private endpoint and private DNS.

Direct Storage Explorer access from the presenter laptop is intentionally outside the
critical path because it requires P2S VPN, ExpressRoute or a jump host. Instead, `azd up`
will produce a public-only local corpus view and an Azure-side inventory receipt with
blob paths and hashes. See `docs/hybrid-evaluation-networking-plan.md`.

**Exit criteria**

- [x] Parallel `azd up` creates the injected Foundry account, Blob private endpoint and
   DNS without changing the working demo environment
- [x] Foundry portal and hosted-agent endpoint remain reachable from the presenter laptop
   without VPN
- [x] A file-backed portal evaluation processes rows rather than failing at
   `temporaryDataReference`
- [x] The full 25-case model comparison completes in Foundry
- [x] Azure-side inventory matches exactly the 11 public manifest documents
- [x] No private `pm-*` document appears in Blob, Foundry IQ or the demo-safe folder
- [x] Cutover and old-account removal occur only after rehearsal passes

**Validation (1 August 2026):** parallel environment `demo-vnet` created Foundry account
`aif-brl2ihmwze6og` with public inbound access and creation-time VNet injection. Blob
remains private behind `pe-stbrl2ihmwze6og-blob`; the Foundry evaluation smoke processed
two file-backed rows and removed its temporary artifacts. `azd up` creates a persistent
private uploader subnet and identity, uploads exactly 11 public PDFs, and writes
`src/corpus/out/public-inventory.json` from the Azure-side Blob listing.

## Phase 8 — Front door application

**Status:** complete
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

**Validation (1 August 2026):** the desktop app against the hosted orchestrator emitted
its first stage at 8 seconds, streamed 14 evidence sources and six citations by 36
seconds, reached approval at 146 seconds, and rendered `Approved` after resume. The
public persona returned 11 sources, explicit withholding disclosure and no `PM-*`
records; the deal-team persona returned 14. A fiduciary/investor-recommendation request
returned a blocked final with no approval bar. Light/dark themes, Zava Securities branding and
the 40px prompt action pass desktop browser checks without horizontal overflow.

**Palette validation (1 August 2026):** both themes now derive from the Zava logo's deep
teal, aqua and cool-gray visual system. Red and amber remain semantic danger/warning
colors rather than brand accents. Primary-button contrast is 5.62:1 in light mode and
8.93:1 in dark mode; desktop and 390px mobile browser checks show no horizontal overflow.

**Approved promotion candidate (1 August 2026):** the local front door now renders
GitHub-Flavored Markdown tables, spins the Run control and each active workflow stage,
and shows fine-grained orchestration, specialist, MCP, Foundry IQ, calculator, synthesis,
control and approval statuses. Statuses carry their owning stage, so completion of the
parallel calculator branch cannot overwrite a still-active Research status. The exact
race was reproduced and passed in browser automation at desktop and mobile widths; all
95 tests, Ruff and the production frontend build pass.

**Promotion validation (1 August 2026):** hosted orchestrator v4 is active with Python
3.14 and Invocations 2.0.0. A native cloud run emitted 21 granular statuses across all
five owned stages, showed the calculator completing while Research remained active,
paused for supervising-principal approval, resumed from checkpoint and returned an
approved three-section answer. Superseded v3 was removed after validation.

## Phase 9 — Copilot Studio surface

**Status:** blocked by Power Platform DLP and environment administration
**Depends on:** 6
**External owner:** Power Platform administrator

Publish the orchestrator and call it from Copilot Studio into Teams. Requested
specifically by the account team, and slide 14 of the deck promises it.

**Exit criteria**

- [ ] Agent reachable from Copilot Studio
- [ ] Approval checkpoint and citations survive the connected-agent handoff
- [ ] A question asked in Teams returns a cited answer

**Attempted validation (1 August 2026):** a Zava Municipal Deal Desk wrapper was created
in Copilot Studio environment `745d0669-8702-e0c2-a33d-b5f249478a0e`. The Azure AI
Foundry Agent Service connector was available, Microsoft Entra ID User Login was
selected, and the validated Foundry project endpoint was entered. Connection creation
was blocked at design time by DLP policy `Personal Developer - (default)`. The maker
cannot change that policy or create an alternate sandbox environment.

This is an external governance dependency, not a Foundry endpoint failure. No connection
was created, no Copilot Studio invocation reached orchestrator v4, and nothing was
published to Teams. A2A, MCP, HTTP or custom-connector workarounds are intentionally not
used because they remain policy-governed and would not prove the requested direct
Foundry connected-agent path.

**Resume criteria:** an administrator must provide a dedicated sandbox or scoped policy
that permits Azure AI Foundry Agent Service and the Teams/Microsoft 365 channel in
compatible data groups. After propagation, repeat connection, approval/citation testing,
personal Teams installation and only then broader sharing. Because v4 exposes only a
custom Invocations 2.0 contract, acceptance must also prove typed request mapping,
client-managed session continuity, long-running execution, approval resume, citation
preservation and guardrail behavior through the Copilot Studio/Teams bridge.

**Separate path discovered:** Foundry exposes a direct **Publish to Teams and Microsoft
365** wizard. The subscription's `Microsoft.BotService` provider was registered during
the proof. Current Hosted Agents guidance specifies Responses + Activity for direct
Teams/Microsoft 365 publication; orchestrator v4 declares Invocations only. No Azure Bot
resource or Teams application was created, and this path is not counted toward Phase 9
completion. Adding Responses/Activity would be a new protocol adapter, not a deployment
setting change.

## Phase 10 — Runbook and rehearsal

**Status:** complete
**Depends on:** 6, 7, 8

`docs/demo-runbook.md` covering the three-part walkthrough: front door application,
Azure portal resource discovery, then the Foundry portal explored left to right with
the bulk of the time.

**Exit criteria**

- [x] Full run performed start to finish against the deployed environment
- [x] Every portal artifact referenced actually loads
- [x] Timing fits the slot with margin

**Validation (1 August 2026):** the presenter runbook now covers the business/domain
primer, persona experiment, Azure resource inventory, exact corpus, Foundry
Home/Discover/Build/Operate navigation, agents, models, Content Understanding, MCP,
Foundry IQ, `DefaultV2`, memory boundaries, data, final evaluations, fine-tuning status,
tracing and production caveats. The live application sequence was rehearsed against the
accepted `demo-vnet` deployment.

## Phase 11 — Fallback recording

**Status:** pending
**Depends on:** 10

Screen recording of the full walkthrough. The deck's speaker notes already call for
this. A live Foundry demo on a Monday morning without a fallback is an avoidable risk.

**Exit criteria**

- Recording covers all three parts
- Stored somewhere reachable without VPN

## What to cut, in order

1. **Copilot Studio surface (Phase 9).** Blocked by tenant DLP. Mitigate by showing the
   policy enforcement as a two-minute governance coda, then return to hosted v4.
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
- Never claim on-behalf-of enforcement; public documents are source-isolated and private
   manifest records are filtered in application code using group claims
- No figure reaching a client document originates from a language model
- Do not describe a component as working before its validation passes
