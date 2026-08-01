# Architecture

## Deployed environment

Provisioned by `azd up` into `westus3`, subscription `non-production Azure subscription`.

| Component | Purpose |
| --- | --- |
| Foundry account and project | Hosts agents, connections and evaluation runs |
| `gpt-5.4-mini` | Bulk document extraction — the low-cost tier |
| `gpt-5.5` | Comparables synthesis and drafting — the reasoning tier |
| `model-router` | Per-request model selection |
| `text-embedding-3-large` | Knowledge base embeddings |
| Azure AI Search (Standard) | Blob knowledge source, generated ingestion pipeline and knowledge base |
| Storage account | Public synthetic PDFs; public network access disabled |
| Azure Container Apps and ACR | Hosts and packages the streamable HTTP MCP server |
| User-assigned managed identity | Runtime Search/model access, telemetry and ACR pull |
| Application Insights and Log Analytics | Traces, token usage and evaluation telemetry |

Region note: the first deployment attempt targeted `eastus2` and failed with
`InsufficientResourcesAvailable` on Azure AI Search. `westus3` carries all four model
versions at the same SKUs, so the move required no template change.

## Application layers

```
hosts  ->  infrastructure  ->  application  ->  domain
```

`domain` and `application` import no Azure SDK, so unit tests run without credentials.
The MCP server and the workflow orchestrator dispatch through the same mediator and
resolve the same handler instances, so a calculation or a conduct policy is implemented
once and behaves identically on both surfaces.

## Retrieval paths

```text
Public PDFs in Blob -> Blob knowledge source -> generated Search pipeline
                    -> model-backed knowledge base -> cited extractive data

Generated manifest -> ManifestDealRepository -> typed deals and private-record filtering

Both paths -> application handler -> MCP tool / orchestrator
```

The public Blob source contains 11 official statements, continuing disclosures and event
notices. It excludes the three private pricing memos. The knowledge base uses
`gpt-5.4-mini` for low-effort query planning, returns `extractiveData`, and leaves
synthesis to the specialist agents.

The manifest repository supplies typed fields for deterministic comparables and applies
caller group claims to private pricing records. A public caller receives the same public
knowledge-base citations but fewer typed source records, plus an explicit withheld count.

## Where numbers come from

Debt service figures are computed arithmetically by `DebtServiceCalculator`, never by a
language model. A model may describe a schedule; it does not produce the schedule. This
boundary is the reason the calculator lives behind a port and carries direct unit tests.

## Thread and memory storage

Thread state and agent memory are **Microsoft-managed** in this deployment, held within
the project's regional boundary.

Foundry also supports bringing your own storage: with Standard Agent Setup, threads and
memory are written to a Cosmos DB account in your own subscription, under your own keys
and retention policy. That is a deployment-time choice — agent code is unchanged.

Microsoft-managed storage was chosen here deliberately. Standard Agent Setup adds a
capability host and several networked dependencies, which lengthens provisioning and
adds failure modes that a fixed-date demonstration cannot absorb. For a regulated
customer evaluating production topology, bring-your-own Cosmos is the relevant option
and belongs in a scoping conversation rather than in this environment.

## Identity, network and access

Interactive demo surfaces use public endpoints with Microsoft Entra authentication.
`disableLocalAuth` is set on the Foundry account, so no API keys exist. Storage has both
shared-key and public-network access disabled. Azure AI Search reaches Blob through an
approved Search-managed shared private link. Corpus seeding uses a transient VNet/private
endpoint uploader that is deleted after upload.

Access is controlled by role assignment at the narrowest practical scope. No runtime
identity holds `Owner` or `Contributor`.

| Principal | Roles |
| --- | --- |
| Foundry project identity | Search Index Data Contributor, Search Service Contributor, Storage Blob Data Reader |
| Search identity | Storage Blob Data Reader, Cognitive Services OpenAI User, Cognitive Services User |
| MCP/orchestrator workload identity | Search Index Data Reader, Cognitive Services OpenAI User, Monitoring Metrics Publisher, AcrPull |
| Developer identity | Azure AI Developer, Cognitive Services User and OpenAI User, Search data and service contributor, Storage Blob Data Contributor |

This posture suits a demonstration presented from a laptop. It is not a production
landing zone pattern and must not be presented as one. See
`docs/decisions/0003-public-network-access-for-demo.md`.

## Validated

- All four model deployments report `Succeeded`
- Chat completions return from `gpt-5.4-mini` and `gpt-5.5` using Entra auth with no keys
- Azure AI Search data plane is reachable with Entra auth
- Blob knowledge source processed 11 public PDFs with zero failures
- Knowledge base returns 11 citations with extractive output
- MCP endpoint lists and calls all three tools over streamable HTTP
- `az bicep build --file infra/main.bicep` compiles with no errors
- `azd provision` is idempotent across repeated runs
