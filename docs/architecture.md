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
| Azure AI Search (Standard, semantic ranking) | Index behind the Foundry IQ knowledge base |
| Storage account | Synthetic corpus documents |
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

## Identity and access

Public network access with Microsoft Entra authentication. `disableLocalAuth` is set on
the Foundry account, so no API keys exist. Storage has `allowSharedKeyAccess` disabled
for the same reason.

Access is controlled by role assignment at the narrowest practical scope. No runtime
identity holds `Owner` or `Contributor`.

| Principal | Roles |
| --- | --- |
| Foundry project identity | Search Index Data Contributor, Search Service Contributor, Storage Blob Data Reader |
| Search identity | Storage Blob Data Reader, Cognitive Services OpenAI User |
| Developer identity | Azure AI Developer, Cognitive Services User and OpenAI User, Search data and service contributor, Storage Blob Data Contributor |

This posture suits a demonstration presented from a laptop. It is not a production
landing zone pattern and must not be presented as one. See
`docs/decisions/0003-public-network-access-for-demo.md`.

## Validated

- All four model deployments report `Succeeded`
- Chat completions return from `gpt-5.4-mini` and `gpt-5.5` using Entra auth with no keys
- Azure AI Search data plane is reachable with Entra auth
- `az bicep build --file infra/main.bicep` compiles with no errors
- `azd provision` is idempotent across repeated runs
