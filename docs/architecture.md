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
| VNet, Blob private endpoint and private DNS | Private outbound path for evaluations and corpus upload |
| Content Understanding analyzer | Portal-visible typed extraction of municipal document fields |
| Foundry Hosted Agent | Builds and hosts the Agent Framework orchestrator from Python source |
| Azure Container Apps and ACR | Hosts and packages only the streamable HTTP MCP server |
| User-assigned managed identity | MCP telemetry publishing and ACR pull |
| Corpus uploader identity | Uploads exactly the public corpus subset without storage keys |
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
                    -> Foundry IQ knowledge base -> Research agent connection
                    -> knowledge_base_retrieve -> cited extractive data

Generated manifest -> ManifestDealRepository -> Deal Desk MCP typed tools
                   -> typed deals and private-record filtering

Research combines both results into ResearchFindings; neither path duplicates the other.
```

The public Blob source contains 11 official statements, continuing disclosures and event
notices. It excludes the three private pricing memos. The knowledge base uses
`gpt-5.4-mini` for low-effort query planning, returns `extractiveData`, and leaves
synthesis to the specialist agents.

The Research agent has two separately visible connections: `municipal-deal-foundry-iq`
for public narrative retrieval and `muni-deal-desk-mcp` for typed candidate selection.
The manifest repository applies caller group claims to private pricing records and
reports an explicit withheld count. The custom MCP server does not query the knowledge
base.

Content Understanding is a parallel, portal-visible extraction artifact. Its
`municipal_deal_extraction` analyzer was validated against all 14 manifest records, but
the live answer path does not consume those extraction results: public narrative comes
from Foundry IQ and typed candidate records come from the packaged manifest repository.

## Where numbers come from

Debt service figures are computed arithmetically by `DebtServiceCalculator`, never by a
language model. A model may describe a schedule; it does not produce the schedule. This
boundary is the reason the calculator lives behind a port and carries direct unit tests.

## Thread and memory storage

Thread state and agent memory are **Microsoft-managed** in this deployment, held within
the project's regional boundary. The solution does not implement bring-your-own memory,
cross-session personalization or a Cosmos DB memory store.

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
`disableLocalAuth` is set on the Foundry account, so no API keys exist. The Foundry
account is created with outbound VNet injection so managed evaluations can reach private
Blob while the portal and hosted endpoint remain browser-accessible. Storage has both
shared-key and public-network access disabled. Azure AI Search reaches Blob through an
approved Search-managed shared private link. Corpus seeding runs as a short-lived ACI in
a persistent delegated uploader subnet and leaves an Azure-derived inventory receipt.

Access is controlled by role assignment at the narrowest practical scope. No runtime
identity holds `Owner` or `Contributor`.

| Principal | Roles |
| --- | --- |
| Foundry project identity | Foundry User, Search Index Data Contributor, Search Service Contributor, Storage Blob Data Owner |
| Foundry account identity | Storage Blob Data Owner for evaluation Asset Store operations |
| Search identity | Storage Blob Data Reader, Cognitive Services OpenAI User, Cognitive Services User |
| MCP workload identity | Monitoring Metrics Publisher, AcrPull |
| Hosted orchestrator identity | Platform-managed per-agent identity; project model and agent access |
| Developer identity | Foundry User, Cognitive Services User and OpenAI User, Search data and service contributor, Storage Blob Data Contributor |

This posture suits a demonstration presented from a laptop. It is not a production
landing zone pattern and must not be presented as one. See
`docs/decisions/0003-public-network-access-for-demo.md`.

## Validated

- All four model deployments report `Succeeded`
- Chat completions return from `gpt-5.4-mini` and `gpt-5.5` using Entra auth with no keys
- Azure AI Search data plane is reachable with Entra auth
- Blob knowledge source processed 11 public PDFs with zero failures
- Knowledge base returns 11 citations with extractive output
- Content Understanding extraction matches the manifest for all 14 generated PDFs
- Research v1 calls both `find_comparable_deals` and `knowledge_base_retrieve`
- MCP endpoint lists and calls its three typed tools over streamable HTTP
- Hosted orchestrator v4 is active with Invocations 2.0.0 and a dedicated agent identity
- Native v4 SSE emits stage-owned orchestration, agent, MCP, Foundry IQ, calculator,
  synthesis, control and approval statuses without exposing chain-of-thought
- Final mini and reasoning portal evaluations each passed 25/25 rows with zero errors
- Deal-team and public-side runs return 14 and 11 sources respectively, with an explicit
    three-record withheld disclosure for the public-side caller
- `az bicep build --file infra/main.bicep` compiles with no errors
- A complete `azd up --environment demo-vnet` succeeds end to end
