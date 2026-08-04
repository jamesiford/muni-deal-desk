# Municipal Deal Desk

A Microsoft Foundry demonstration solution: a new-issue **Deal Desk** agent for a
public finance broker-dealer desk.

The application is branded **Zava Securities**, a fictional broker-dealer created for
this synthetic demonstration. The brand, issuers, documents, figures and internal
pricing records do not represent a real firm or real municipal securities activity.
Its visual system follows the fictional logo: deep teal and aqua for identity,
interaction and workflow progress; cool gray for operational surfaces; and red/amber
reserved for danger and warning states.

The solution exists to make Foundry platform capabilities visible and explainable in a
customer technical session. Infrastructure, synthetic corpus, Foundry IQ, MCP, prompt
agents, hosted orchestration, evaluations and the banker-facing front door are complete.

## The scenario

A banker preparing a competitive response asks one deliberately messy question:

> Gulf Lantern Fictional ISD is issuing about $85 million of unlimited tax school
> building bonds this fall. Pull the most comparable Texas ISD issues from the last
> 18 months, compare debt service and call features, flag evidence gaps, and draft the
> market summary section for our RFP response.

Answering it requires decomposition, retrieval across several source types, a tool call,
a model switch, a compliance check and a human gate.

## Capability map

| Capability | Status | Where it appears |
| --- | --- | --- |
| Foundry IQ | Complete | Blob-backed public PDF source with model-planned, extractive retrieval |
| Content Understanding | Complete | Portal-visible typed municipal document analyzer, validated 14/14 |
| MCP and tools | Complete | ACA-hosted debt service, comparables and deal lookup tools |
| Model choice | Deployed | Extraction, reasoning, router and embedding deployments |
| Governance | Implemented for current paths | Source separation, sensitivity labels and withheld counts |
| Guardrails | Complete | Model review plus deterministic blocking and typed human approval |
| Agents | Complete | Three prompt specialists and native Foundry Hosted orchestrator v4 |
| Evaluations | Complete | 25-case local/portal gate and two-model comparison |
| Tracing and observability | Complete for demo | Workflow spans, branch-aware SSE status streaming and portal evaluation runs |
| Copilot Studio / Teams | Blocked externally | Supported Foundry connector found; tenant DLP blocks connection creation |
| BYO memory / Cosmos DB | Not implemented | Platform-managed state only; documented production option |
| Fine-tuning | Not used | Evaluation-first baseline retained for a future candidate |

The promoted front door and orchestrator add active spinners, fine-grained multi-agent/
tool/knowledge status messages, parallel-branch status arbitration, and GitHub-Flavored
Markdown table rendering. Hosted orchestrator v4 passed the complete local gate and a
native cloud invocation with 21 status events, approval checkpoint and approved final.

## Demo narrative

The presenter runbook explains the fictional Zava Securities Deal Desk, the relevant
broker-dealer audiences, personas, prompt terminology, call provisions, private
precedent value, every deployed Azure service, all four document types, and the complete
Foundry Home/Discover/Build/Operate walkthrough. See
[docs/demo-runbook.md](docs/demo-runbook.md).

Supporting detail:

- [Architecture and trust boundaries](docs/architecture.md)
- [Guardrail scope and regulatory framing](docs/guardrails.md)
- [Hybrid evaluation networking](docs/hybrid-evaluation-networking-plan.md)
- [Build and validation history](docs/roadmap.md)
- [Terms of Use](docs/terms-of-use.md)
- [Privacy Statement](docs/privacy.md)

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

Provision and deploy the complete hybrid demo environment with one command:

```powershell
azd up --environment demo-vnet
```

The Foundry portal remains public and Entra-protected for the walkthrough. Foundry
outbound evaluation traffic is VNet-injected into private Blob storage; Search uses a
shared private link, and corpus upload runs in a persistent private uploader subnet.

The frontend is intentionally **not deployed to Azure**. Azure hosts the MCP Container
App and Foundry Hosted orchestrator; the presenter runs the React/FastAPI front door
locally against that hosted Invocations endpoint.

Run the complete demo from a fresh shell after `azd up`:

```powershell
azd env select demo-vnet
npm install --prefix frontend
npm run build --prefix frontend
azd env get-values --environment demo-vnet | ForEach-Object {
  if ($_ -match '^([^=]+)="(.*)"$') { Set-Item "Env:$($matches[1])" $matches[2] }
}
python -m src.hosts.front_door
```

Open `http://127.0.0.1:8080`. The local FastAPI process serves `frontend/dist` and
bridges browser SSE requests to the deployed hosted-agent endpoint. Stop it with
`Ctrl+C` after the walkthrough.

## Validation

| Check | Command |
| --- | --- |
| Lint | `python -m ruff check .` |
| Format | `python -m ruff format --check .` |
| Unit tests | `python -m pytest tests/unit` |
| Infrastructure | `az bicep build --file infra/main.bicep` |
| Local evaluation gate | `python -m evals.runner --local-only --environment demo-vnet` |
| Cloud two-model gate | `python -m evals.runner --environment demo-vnet` |
| Phase 3 cloud artifacts | `python -m scripts.setup_phase3 --validate-content-understanding` |
| Deployed MCP | `python -m scripts.smoke_mcp $(azd env get-value MCP_ENDPOINT)` |
