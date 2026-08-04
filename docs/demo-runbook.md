# Municipal Deal Desk demo runbook

Reusable presenter guide for a Microsoft Foundry technical session.

This is the presenter narrative, not just a click path. It explains the municipal
business problem first, shows the application second, and then reveals how Azure and
Microsoft Foundry implement it.

**Deployed project**

| Item | Value |
| --- | --- |
| Azure environment | `demo-vnet` |
| Resource group | `rg-muni-deal-desk-demo-vnet` |
| Region | `westus3` |
| Foundry account | `aif-brl2ihmwze6og` |
| Foundry project | `muni-deal-desk` |
| Hosted orchestrator | `municipal-deal-desk-orchestrator`, version 4 |
| Final evaluation | `eval_b23afc8b99554c30a7c8af566abb375d` |

> **Accuracy boundary.** All issuers, documents, figures and deal-team records are
> synthetic. Zava Securities is a fictional broker-dealer brand used only for this
> demonstration and is not associated with any real company or customer. Nothing was
> retrieved from MSRB EMMA. The persona switch demonstrates physical source separation
> plus application-level group filtering, not end-to-end on-behalf-of authorization. The
> conduct controls are modelled on regulatory obligations; they do not certify
> compliance or provide legal advice.

## Session shape

| Time | Part | Outcome |
| --- | --- | --- |
| 0-8 min | Business and domain primer | The audience understands the job and prompt |
| 8-20 min | Application | Evidence, persona contrast, controls and approval |
| 20-28 min | Azure portal and corpus | Deployed footprint and source material |
| 28-55 min | Foundry portal | Platform artifacts behind the application |
| 55-60 min | Operate, trace and close | Governance, evidence and next steps |

The application comes first so the platform discussion is attached to a working
experience. Spend most of the session in Foundry **Build**.

## Before the session

- [ ] Open the front door, Azure resource group and Foundry project in separate tabs
- [ ] Turn on **New Foundry**; this follows **Home, Discover, Build, Operate, Docs**
- [ ] Dismiss the first-run Foundry welcome dialog
- [ ] Open `src/corpus/out/public` and `src/corpus/out/public-inventory.json` in VS Code
- [ ] Open `src/hosts/orchestrator/workflow.py` and
      `src/domain/policies/conduct_policies.py` in VS Code
- [ ] Warm the application with one complete run
- [ ] Keep the fallback recording open but out of sight
- [ ] Confirm the app starts in the **Deal-team member** persona

The values below are prepared for a future direct Foundry publication attempt. Do not
use this as part of the core walkthrough or imply publication completed. The repository
must be publicly reachable, or these URLs must move to another public host, before they
can be used in a Teams application listing.

| Field | Value |
| --- | --- |
| Publish version | `1.0.0` |
| Developer | `Zava Securities Demo Team` |
| Developer website | `https://github.com/jamesiford/muni-deal-desk` |
| Terms of use | `https://github.com/jamesiford/muni-deal-desk/blob/main/docs/terms-of-use.md` |
| Privacy statement | `https://github.com/jamesiford/muni-deal-desk/blob/main/docs/privacy.md` |

The legal pages explicitly identify Zava, the issuers, documents and pricing records as
fictional and prohibit entering real confidential or material nonpublic information.

Launch the local front door from a fresh PowerShell session:

```powershell
azd env select demo-vnet
npm ci --prefix frontend
npm run build --prefix frontend
azd env get-values --environment demo-vnet | ForEach-Object {
  if ($_ -match '^([^=]+)="(.*)"$') { Set-Item "Env:$($matches[1])" $matches[2] }
}
python -m src.hosts.front_door
```

Open `http://127.0.0.1:8080`. Keep that shell running throughout the walkthrough.

## Part 1 - Business and application

### What is this application?

The Zava Securities Municipal Deal Desk is a new-issue intelligence assistant for a
fictional public finance broker-dealer desk. It helps a banker prepare an issuer-facing
response by finding comparable municipal bond issues, comparing structures, identifying
disclosure facts that could affect pricing, and drafting a cited market summary for review.

It does not decide whether an investor should buy a bond, provide legal advice, replace
a banker, or approve client communication. It accelerates evidence assembly and first
drafting while preserving source attribution, information barriers, deterministic
calculations, conduct checks and supervising-principal approval.

### What is a municipal Deal Desk?

A municipal new issue is debt sold by a state or local government entity such as a
school district. Before an issue is priced, public finance bankers, underwriters,
traders, analysts and supervisors need a common view of:

- the proposed issuer and security pledge
- recently priced comparable issues
- maturity and debt-service structure
- ratings, credit enhancement and call features
- continuing-disclosure and material-event developments
- internal pricing experience that a public-side user may not be permitted to see

The Deal Desk is the coordination function around that work. The hard part is not
writing a paragraph. It is joining evidence from several document types, applying
permission boundaries, calculating figures consistently, surfacing missing or
conflicting facts, and producing something a supervisor can review.

### Who would care?

Zava Securities is the fictional firm represented in the application. It is not
associated with any real company or customer, and no real organization supplied the
synthetic internal pricing records.

The direct business fit is a public finance broker-dealer and its control and technology
functions.

| Broker-dealer audience | Why this matters |
| --- | --- |
| Public Finance bankers | Faster comparable research and RFP market-summary drafting |
| Municipal underwriting and syndicate | Consistent structure, call and precedent comparison before pricing |
| Fixed Income Capital Markets, trading and sales | Organized public evidence and internal precedent context |
| Municipal credit or research professionals | Cited disclosure changes, conflicts and stale information |
| Supervising principals, Compliance, Legal and Risk | Reviewable controls, source lineage, approval and traces |
| Technology, Data and AI platform teams | Governed agents, knowledge, tools, evaluation and operations |

Enterprise technology, cyber, risk, records-management and model-governance leaders
would care about operating this pattern consistently across business units. The
platform pattern can transfer to other regulated, document-heavy processes even though
they are not the primary users of this municipal workflow.

### The two Zava demo personas

These are fixed presentation personas mapped to explicit application claims. They are
not a claim that the end user's Entra token reaches every source.

| Persona | Claims | Evidence available |
| --- | --- | --- |
| Deal-team member | Subject-deal plus private-side deal-team access | 11 public documents and 3 internal pricing memos |
| Public-side analyst | Subject-deal access only | 11 public documents; 3 private records withheld and disclosed |

Public-side and private-side separation matters at a broker-dealer because a person may
be restricted from material or deal-confidential information. A useful assistant must
not simply return fewer facts silently. It must apply the boundary and tell the caller
when the answer is partial.

### Why this prompt is significant

Use the prompt already loaded in the app:

> Gulf Lantern Fictional ISD is issuing about $85 million of unlimited tax school
> building bonds this fall. Pull the most comparable Texas ISD issues from the last
> 18 months, compare debt service and call features, flag evidence gaps, and draft the
> market summary section for our RFP response.

This is intentionally one compound banker request, not a chatbot trivia question.

| Prompt term | Meaning and why it changes the work |
| --- | --- |
| Gulf Lantern Fictional ISD | The proposed subject issuer; fictional by design |
| About $85 million | Par amount used to select similarly sized precedents |
| Unlimited tax | An unlimited ad valorem tax pledge; compare like security structures |
| School building bonds | Capital-purpose debt with a maturity and debt-service profile |
| This fall | Pricing context is time-sensitive |
| Texas ISD | Narrows issuer type, state framework and likely PSF-enhanced peers |
| Last 18 months | Prevents stale market precedents from dominating the set |
| Most comparable | Requires deterministic filtering plus qualitative assessment |
| Debt service | Principal and interest burden by period; calculated, not generated |
| Call features | Optional redemption rights that affect value and pricing |
| Evidence gaps | Missing, conflicting, late or stale facts must be disclosed, not guessed |
| RFP response | Issuer-facing business communication that requires supervision |

The prompt forces the system to decompose a task, use public narrative retrieval and
typed private records, call deterministic tools, coordinate specialists, draft with
citations, apply conduct controls, and stop for a human decision. That is why it is a
useful Foundry demonstration.

### What is a call provision?

A call provision gives the issuer the right, but not the obligation, to redeem bonds
before their stated maturity under specified terms. The important fields are the first
call date, call price and whether a bond is non-callable.

Call protection changes economic value. If rates fall, an issuer may refinance callable
bonds; the investor receives principal back and must reinvest at lower rates. Two bonds
with similar issuer, rating and maturity are not clean pricing comparables if one is
callable earlier or at a different price. This is why the absence of a stated call
provision is a material evidence gap. The correct answer is "not stated," not an
industry-standard date invented by the model.

### What do the private citations add?

`PM-001`, `PM-002` and `PM-003` are synthetic internal pricing memos for Blue Mesa,
Lone Heron and Red Bluff. They carry comparable maturity scales and yields plus the
deal team's working view of the issue, call structure and enrollment trend.

Their value is the firm's own precedent context: information available to an authorized
deal team but not part of the public disclosure corpus. Public official statements can
show what was offered; an internal memo can preserve how the desk framed that precedent
for pricing. The demo keeps those records out of Foundry IQ entirely and exposes them
only through the typed repository behind MCP. Do not say the private memos came from
Blob or Foundry IQ.

### Live application sequence

#### 1. Deal-team run

Start as **Deal-team member** and run the loaded prompt. While it streams, point to:

- six named workflow stages rather than a generic spinner
- active stage and Run-button spinners throughout the long-running workflow
- one branch-aware status line naming orchestrator handoffs, specialists, MCP tools,
  Foundry IQ public-document retrieval, calculation, synthesis and controls
- 14 evidence sources, including the three `PM-*` private records
- citations arriving before the final answer
- computed debt service and structural comparisons
- explicit evidence gaps rather than inferred facts
- the supervising-principal approval gate

Say: *"The user sees progress because this is a multi-minute workflow, not one model
completion. Research and calculation fan out in parallel, and the status line follows
whichever branches remain active before the workflow joins for analysis and drafting."*

Approve the clean draft. The final state should read **Approved**.

#### 2. Same prompt, public-side persona

Start a new run, switch to **Public-side analyst**, and submit the exact same prompt.
Point out:

- 11 sources rather than 14
- no `PM-*` source or citation
- the explicit disclosure that three records were withheld
- a partial answer that still requires review

Say: *"The business question did not change; the caller's entitlement did. Asking the
same prompt is the controlled experiment. It proves that evidence selection is a
separate concern from prompt wording."*

Then be precise: *"Public documents are physically isolated in Foundry IQ. Private
records are filtered in application code using caller group claims. This is not an
on-behalf-of implementation."*

#### 3. Missing evidence

Open the Copper Star comparable and its missing call provision. Say: *"A fluent model
could fill this with a customary redemption date. This system reports the absence, and
the evaluation suite has a critical case that fails if it invents one."*

The corpus also contains three other deliberate quality traps:

- North Lantern enrollment is `12,840` in `OS-006` and `13,215` in `CD-001`
- Juniper Bend's annual disclosure was due 28 February 2026 and filed 17 April 2026
- Silver Cactus uses financial statements only through 31 August 2023 in a July 2026
  official statement

#### 4. Conduct-control refusal

Ask:

> Which of these bonds should I recommend to a client?

The workflow should block before approval and should not expose a pre-review draft.

Say: *"This is not a generic content filter objecting to the topic. The request is
outside this issuer-facing underwriting workflow, and a deterministic firm conduct rule
blocks it even if a model would otherwise answer."*

### What the front door is built from

The branded interface is React 19 and Vite in plain JSX. A small FastAPI bridge maps the
selected presentation persona to typed claims and streams the hosted agent's Invocations
events over SSE. It contains no pricing, entitlement or compliance logic. Those rules
live behind the application mediator and are shared by the hosted workflow and MCP.

The visual system follows the fictional Zava logo: deep teal and aqua identify primary
actions, focus and live workflow progress; cool grays organize the operational surface;
red and amber are reserved for blocked/error and warning states. Both light and dark
themes retain accessible primary-action contrast.

## Part 2 - Azure resource group and corpus

Open Azure portal resource group `rg-muni-deal-desk-demo-vnet`. The point is not to
inspect every property; it is to establish that the application is a composed, governed
workload rather than one opaque endpoint.

### Deployed services

| Azure resource | What it does here | Why it is needed |
| --- | --- | --- |
| Foundry account `aif-brl2ihmwze6og` | AI Services account, project parent, models, Content Understanding and outbound injection | Governed control plane for models and AI services |
| Foundry project `muni-deal-desk` | Owns agents, connections, files, evaluations and traces | Durable application-team and portal boundary |
| Four model deployments | Extraction, reasoning, routing and embeddings | Match model cost/capability to each task |
| AI Search `srch-brl2ihmwze6og` | Blob ingestion pipeline and Foundry IQ retrieval | Hybrid/vector retrieval, index lifecycle and citations |
| Storage `stbrl2ihmwze6og` | Holds 11 public PDFs and project evaluation data | Durable private source with shared keys disabled |
| VNet `vnet-brl2ihmwze6og` | Foundry injection, private endpoint and uploader subnets | Private path from managed workloads to Blob |
| Blob private endpoint and private DNS | Resolves and routes Blob privately | Tenant policy prohibits usable public Blob access |
| Container App `ca-mcp-brl2ihmwze6og` | Hosts the streamable HTTP MCP server | Reusable typed business tools for agents |
| Container Apps environment `cae-*` | Managed runtime and ingress for MCP | TLS, revisions, scaling and logs |
| Container Registry `crbrl2ihmwze6og` | Stores MCP and temporary uploader images | Reproducible private container deployment |
| MCP managed identity `id-*` | Authenticates MCP without secrets | Least-privilege Azure access and telemetry |
| Corpus-uploader identity `id-corpus-uploader-*` | Authenticates the short-lived private uploader | Uploads without storage keys |
| Application Insights `appi-*` | Receives agent, workflow, MCP and model spans | Trace and token evidence |
| Log Analytics `log-*` | Workspace for telemetry and Container Apps logs | Queryable operational retention |

The native hosted orchestrator is a Foundry project artifact with a dedicated platform
identity. It is intentionally not a second Container App. The short-lived ACI corpus
uploader is deleted after each successful upload; it should not remain in the group.

### Identity and network story

Two statements are enough:

1. *"There are no application keys. Foundry local auth and Storage shared-key access are
   disabled; workloads use Entra identities and scoped role assignments."*
2. *"The Foundry portal and hosted agent are public and Entra-protected for this laptop
   demo. Foundry outbound evaluation traffic is VNet-injected, Blob is private, Search
   uses an approved shared private link, and corpus upload runs inside the VNet."*

This hybrid shape preserves a browser-accessible demonstration while satisfying private
Blob policy. It is not a production landing zone. Production design would also assess
private inbound access, OBO identity, enterprise networking, threat modelling, records
retention and operational separation.

### One-command lifecycle

The complete environment is reconciled by:

```powershell
azd up --environment demo-vnet
```

That command provisions Bicep, applies RBAC, verifies both chat model tiers, generates
the corpus, uploads exactly 11 public PDFs through the private endpoint, reconciles
Foundry IQ and Content Understanding, registers specialists, runs a private-storage
  evaluation smoke, deploys MCP and the next immutable hosted orchestrator version, then runs contract
smokes.

### The document corpus

The generator creates 14 one-page synthetic PDFs and a machine-readable manifest. Only
11 public PDFs are uploaded to the Foundry IQ Blob prefix.

| Document type | Count | What it tells the desk |
| --- | ---: | --- |
| Official statement (`OS`) | 8 public | Offering terms, issuer facts, pledge, ratings, maturity scale, yields, calls and financial period |
| Annual continuing disclosure (`CD`) | 2 public | Post-issuance operating/debt updates and filing timeliness |
| Material event notice (`ME`) | 1 public | A significant post-issuance event; here, an underlying rating change |
| Internal pricing memo (`PM`) | 3 private | Deal-team precedent scale, yields and working pricing context |

**Official statements.** These are the primary offering documents for eight fictional
Texas ISD issues from $30 million to $150 million. Three are deliberately notable:

- `OS-003`, Copper Star: no call provision is stated
- `OS-006`, North Lantern: enrollment conflicts with `CD-001`
- `OS-008`, Silver Cactus: financial statements are stale

**Continuing disclosures.** `CD-001` creates the North Lantern enrollment conflict.
`CD-002` was filed late, which may affect the desk's view of disclosure discipline and
requires review.

**Material event notice.** `ME-001` reports Cedar Prairie's fictional underlying
Moody's change from Aa1 to Aa2 while its enhanced S&P rating remains AAA. It shows why a
desk cannot rely only on the original offering document.

**Internal pricing memos.** `PM-001`, `PM-002` and `PM-003` cover Blue Mesa, Lone Heron
and Red Bluff. They are private typed fixtures, never uploaded under `pdf/public`, and
exist to make the persona contrast inspectable and testable.

### How to show private Blob safely

Do not open Storage Browser or Storage Explorer. Those tools read Blob from the
presenter's laptop and require VPN or a jump host when public access is disabled.

Show these together instead:

1. `src/corpus/out/public`, containing exactly 11 demo-safe PDFs
2. `src/corpus/out/public-inventory.json`, emitted by the uploader inside Azure
3. Foundry IQ's 11-document source count and returned citations

The inventory records Blob path, document ID, byte length and source SHA-256 for exact
manifest parity. The full local output also contains the three `PM-*` private fixtures;
do not describe the entire folder as the Blob container.

## Part 3 - Microsoft Foundry portal

Follow the top navigation left to right: **Home, Discover, Build, Operate**. The reason
Foundry fits should emerge from the artifacts: the portal and source code expose the
same agents, models, tools, knowledge, controls, evaluations and traces to different
roles.

### Home

**Show** the `Municipal Deal Desk` project card, endpoint and authentication status.

**Say:** *"This project is the durable boundary for the application. The endpoint is
what our code calls. API key authentication is disabled, so access is through Entra and
managed identity."*

Use Home to orient, not to explain the solution.

### Discover

**Show** the model catalogue and open one deployed model family.

**Say:** *"Model choice is a workload decision, not an application rewrite. We use a
smaller model for high-volume extraction and compliance tasks, a reasoning model for
analysis and synthesis, an embedding model for retrieval, and a router to demonstrate
policy-based selection."*

Do not quote a catalogue model count; it changes.

### Build - Agents

Open **Build > Agents**. Four durable agents should be visible.

| Agent | Kind | Model | Responsibility |
| --- | --- | --- | --- |
| `municipal-deal-research` v1 | Prompt agent | `gpt-5.4-mini` | Candidate lookup plus cited public retrieval; reports gaps |
| `municipal-deal-analyst` v1 | Prompt agent | `gpt-5.5` | Uses deal/debt-service tools and explains structures |
| `municipal-deal-compliance` v1 | Prompt agent | `gpt-5.4-mini` | Structured model review for conduct and human review |
| `municipal-deal-desk-orchestrator` v4 | Hosted workflow | Mixed | Plans, invokes, streams branch-aware status, controls and pauses for approval |

Open Research. Show its instructions, tools and structured `ResearchFindings` format.
Point out its two connections: custom MCP for candidates and Foundry IQ for public
passages.

Open Analyst. Show that figures require `get_deal` and `compute_debt_service` before
discussion. The model interprets a schedule; it is not the source of the arithmetic.

Open Compliance. Show the typed `ComplianceReview`, then state that model review is not
the final control.

Open the orchestrator and contrast the authoring surfaces:

- prompt specialists use `PromptAgentDefinition` and are inspectable, versioned and
  testable in the portal
- the orchestrator is a checkpointed Agent Framework workflow authored in Python and
  deployed as source to Foundry Hosted Agents

Switch briefly to `src/hosts/orchestrator/workflow.py`. Point to typed messages, parallel
research/debt-service work, deterministic review and the approval checkpoint. Internal
specialist wiring uses the workflow, not A2A.

**Why this matters:** Foundry supports prompt iteration and pro-code workflow control
without forcing every component into one authoring model.

### Build - Models

Open **Models** or **Deployed models**.

| Deployment | Purpose in this solution |
| --- | --- |
| `gpt-5.4-mini` | Research extraction, Compliance review and IQ query planning |
| `gpt-5.5` | Analyst reasoning, synthesis and advisory score-model evaluation |
| `model-router` | Inspectable optional runtime-selection capability; the live workflow pins task models |
| `text-embedding-3-large` | Integrated vectorization for the knowledge base |

Say: *"We allocate model capability by task. Evaluations make the cost-quality tradeoff
measurable instead of assumed."*

### Build - Services and Content Understanding

Open **Services > Content Understanding** and analyzer
`municipal_deal_extraction`.

It uses the prebuilt document analyzer with layout, OCR, confidence and source
estimation. Its typed schema extracts issuer, security type, par, dates, ratings, call
provision, and each maturity's principal, coupon and yield.

The analyzer was validated against the manifest for all 14 PDFs. Be precise about its
role: it is a durable demonstration of structured extraction. The live Research path
uses Foundry IQ for public narrative evidence and the packaged manifest repository for
typed candidate records. Do not imply the live answer is populated from Content
Understanding output.

This shows two complementary document jobs:

- Content Understanding turns a document into a typed business record
- Foundry IQ retrieves cited passages to ground an answer

### Build - Tools and MCP

Open **Tools** and connection `muni-deal-desk-mcp`. Show three streamable HTTP tools:

| Tool | Purpose |
| --- | --- |
| `find_comparable_deals` | Filters state, security, size, age and claims; returns withheld count |
| `get_deal` | Returns one entitled deal without revealing whether an absent record was barred |
| `compute_debt_service` | Computes principal, interest and total debt service arithmetically |

Say: *"MCP is the contract between an agent and reusable business capabilities. Foundry
can discover the tool, while calculation and entitlement logic remain normal tested
application code."*

The server runs in Container Apps with its own managed identity. MCP and the hosted
orchestrator use the same hand-rolled mediator, so rules and calculations are not
duplicated.

Open connection `municipal-deal-foundry-iq`. Both speak MCP, but ownership differs:

- `knowledge_base_retrieve` is a Foundry IQ capability over public documents
- the three Deal Desk tools are custom application capabilities

### Build - Knowledge and Foundry IQ

Open Blob knowledge source `municipal-deal-pdf-blob-source` and show:

- kind `azureBlob`
- container path `corpus/pdf/public`
- 11 processed public documents
- source-generated Search data source, skillset, index and indexer

Open `municipal-deal-knowledge-base` and show:

- `gpt-5.4-mini` query planning with low reasoning effort
- `extractiveData` output
- municipal-document retrieval instructions
- blank answer instructions because specialists own synthesis

Say: *"Foundry IQ owns retrieval planning and cited extractive evidence. Research owns
the answer. We deliberately did not create a second hand-managed index."*

Repeat the boundary once: IQ is public-only. Private pricing memos remain in the typed
repository and are filtered by the application. The hosted agent uses managed identity,
not the end user's delegated identity.

### Build - Guardrails

Open **Guardrails** and platform guardrail `DefaultV2`.

`DefaultV2` is the platform baseline for content-safety categories and jailbreak
defence. It was not customized for municipal underwriting here. It is valuable, but it
does not know that an underwriter must not imply municipal-advisor or fiduciary standing.

Then show `src/domain/policies/conduct_policies.py` and the second layer:

| Deterministic policy | What it blocks |
| --- | --- |
| `msrb-g17-fiduciary-implication` | Advisor, municipal-advisor or fiduciary claims |
| `retail-recommendation-out-of-scope` | Investor-directed buy or suitability recommendations |
| `uncited-figure` | Money or rate statements without a citation marker |

These policies run against the request and generated draft. A blocked request never
exposes a draft or reaches approval. Every allowed client-facing answer still sets
`requires_human_review=true`.

Say: *"Platform safety and firm conduct are independent controls. A prompt edit can
change agent behavior; it cannot edit these domain policies."*

### Build - Memory

Open **Memory** and state the status plainly.

This demo does **not** implement bring-your-own memory or a Cosmos DB memory store.
Workflow checkpoints and hosted-agent session state support the in-flight approval,
while persistent thread/memory storage uses the platform-managed project configuration.

For a production regulated workload, Standard Agent Setup can place thread and memory
data in customer-owned Cosmos DB with customer-defined networking, keys, retention and
lifecycle controls. That choice belongs with records-management and privacy design. It
was omitted to keep a fixed-date demo focused and reliable.

Do not claim custom long-term user memory, cross-session personalization, BYO Cosmos or
a firm retention policy.

### Build - Data

Open **Data**. The retained final evaluation inputs are:

- `muni-deal-desk-phase-7-final-mini.jsonl`
- `muni-deal-desk-phase-7-final-reasoning.jsonl`

These are durable, file-backed 25-row datasets used by the final portal runs. The public
PDF corpus is not duplicated here; it belongs under Knowledge as a private Blob-backed
source. Evaluation data and retrieval knowledge have distinct purposes and lifecycles.

### Build - Evaluations

Open `muni-deal-desk-phase-7-final`, ID
`eval_b23afc8b99554c30a7c8af566abb375d`.

The suite contains exactly 25 human-reviewable cases:

| Category | Cases | What can fail |
| --- | ---: | --- |
| Comparable selection | 6 | Wrong, duplicate or misordered deal IDs |
| Debt-service figures | 4 | Principal, interest or total differs by any amount |
| Citation integrity | 4 | Missing/wrong source or private leakage |
| Gap disclosure | 4 | Missing call, conflict, late filing or stale data hidden |
| Entitlement contrasts | 3 | Wrong withheld count, partiality or private visibility |
| Guardrails | 4 | Required block/review behavior not enforced |

Show both final runs:

| Configuration | Run ID | Result |
| --- | --- | --- |
| Mini | `evalrun_8229604602a64e8b894f8f13d06c1bf8` | 25 passed, 0 failed, 0 errored |
| Reasoning | `evalrun_8d1753f9149246d399e97392cf3b010d` | 25 passed, 0 failed, 0 errored |

Open a row and show two graders:

- `deterministic_gate` is Python over typed expected results and owns promotion
- `expected_behavior_quality` uses fixed `gpt-5.5` as an advisory score-model criterion

Say: *"A model does not grade exact arithmetic, permissions or required source IDs.
Those are deterministic. A score model adds qualitative evidence but cannot override a
failed critical contract check."*

The local gate evaluated genuine collected outputs and passed 100% for both model
configurations. The file-backed portal runs prove managed evaluation can read through
the private Blob path and produce durable results. CI blocks promotion when deterministic
thresholds fail.

### Build - Fine-tuning

Open **Fine-tuning** only long enough to locate it. No model was fine-tuned here.

Say: *"We started with retrieval, tools, structured contracts, prompt agents and
evaluation. Fine-tuning is appropriate when repeated evaluation reveals a stable
behavior gap that examples can teach and retrieval or instructions cannot solve. It is
not the first answer to missing knowledge, current data or deterministic math."*

The 25-case suite would be the baseline a future fine-tuned candidate must beat without
regressing critical controls.

### Operate

Move to **Operate**. Portal labels may evolve, but cover these responsibilities:

| Surface | What to say |
| --- | --- |
| Overview | Success, latency, token and cost trends turn one run into an operated workload |
| Assets | Inventory answers which agents and versions exist; only orchestrator v4 remains active |
| Compliance | Connect posture to enterprise governance; do not claim Purview or Agent ID integration |
| Quota | Capacity and throughput are dependencies; PTU is a future option, not used here |
| Admin | Project access, connections and configuration are governed apart from prompts |

The shift from Build to Operate is the platform argument: a prototype answers one
question; an enterprise platform inventories, measures and governs an agent estate.

### Tracing and observability

End on a trace from the application run. Walk the span tree:

- planning
- Research and Analyst specialist calls
- Foundry IQ and MCP calls
- synthesis model call and token usage
- model Compliance review
- deterministic guardrail review
- approval checkpoint and resume

Say: *"This is the same workflow we watched from the user's side, now visible from the
operator's side. We can see what was called, what evidence returned, which model ran,
where time was spent and why the workflow stopped."*

Application Insights and Log Analytics receive OpenTelemetry data. Tracing supports
debugging and governance evidence; it is not by itself a complete books-and-records
program. Retention, redaction, access and supervision remain production decisions.

## Optional coda - Copilot Studio governance

**Timebox:** two minutes. Show this only after the complete working application and
Foundry walkthrough. It is a governance proof, not a fourth working application.

Open the draft **Zava Municipal Deal Desk** agent in Copilot Studio. Navigate to the
Azure AI Foundry Agent Service connection dialog and show:

| Field | Validated value |
| --- | --- |
| Authentication | Microsoft Entra ID User Login |
| Foundry project | `https://aif-brl2ihmwze6og.services.ai.azure.com/api/projects/muni-deal-desk` |
| Intended agent | `municipal-deal-desk-orchestrator:4` |

Point to the banner:

> Connection creation/edit of Azure AI Foundry Agent Service has been blocked by Data
> Loss Prevention (DLP) policy `Personal Developer - (default)`.

Say: *"This is design-time governance working before data can cross a platform
boundary. Copilot Studio discovered the supported Foundry connector and accepted the
project endpoint, but this personal developer environment is not authorized to create
that connection. We did not weaken the policy or route around it."*

Then state the unvalidated continuation, using conditional language:

1. A Power Platform administrator provides a dedicated sandbox or scoped policy where
   Azure AI Foundry Agent Service and the Teams/Microsoft 365 channel are allowed in
   compatible data groups.
2. The maker creates the Entra-authenticated Foundry connection, selects orchestrator
   v4, and verifies citations, the approval pause and final response in test chat.
3. Only after that test passes does the maker publish the Copilot Studio wrapper and add
   the Teams and Microsoft 365 channel.

Be explicit about what this proves and what it does not:

- **Proved:** the intended connector exists; the correct endpoint is known; tenant DLP
  blocks connection creation in this environment.
- **Not proved:** Copilot Studio invoked v4, citations survived the connected-agent
  handoff, the approval checkpoint rendered, or Teams returned an answer.
- **Not acceptable as a bypass:** A2A, MCP, HTTP and custom connectors are also governed
  by Power Platform policy and would change the architecture without satisfying the
  blocked direct-connector acceptance criterion.

### Protocol caveats if asked

Orchestrator v4 declares only **Invocations 2.0**. That choice is deliberate for this
application: Invocations accepts the typed `start` and `approve` payloads, preserves a
client-managed session ID across the human-review pause, and carries custom raw SSE
events for stages, statuses, evidence, citations and policy findings.

Microsoft's current Hosted Agents guidance recommends **Responses + Activity** for
agents published to Teams or Microsoft 365. Responses supplies platform-managed
conversation history and lifecycle events; Activity is the channel bridge. V4 does not
declare either protocol. The Copilot Studio Foundry connector is preview and its
documentation does not state that it adapts a custom Invocations contract. DLP blocked
the connection before we could test that compatibility.

If the policy blocker is removed, do not treat successful connection creation as Phase
9 completion. Run these acceptance checks:

| Risk | Required proof |
| --- | --- |
| Input mapping | Copilot Studio sends a request v4 can validate as `DealDeskRequest`, including the intended persona/claims behavior |
| Long-running execution | A representative two-to-three-minute run completes without a connector or channel timeout |
| Streaming | Determine whether custom status/stage events are preserved, collapsed to a generic wait state, or discarded |
| Human approval | The typed `approval_required` event renders an actionable prompt and the decision resumes the same Foundry session |
| Session continuity | Teams conversation turns map consistently to the client-managed Invocations session ID |
| Output fidelity | Structured sections, GFM tables, evidence gaps and permission disclosures survive any parent-agent re-synthesis |
| Citations | Citation identity and excerpts survive the connected-agent handoff and Teams rendering |
| Identity | Verify the actual caller identity path; Microsoft Entra login does not by itself prove end-to-end OBO or group-claim enforcement |
| Guardrails | A prohibited recommendation remains blocked before any draft reaches the channel |

The most likely failure modes are a rejected custom payload, loss of custom SSE events,
an approval pause with no channel UI, a timeout, or the parent agent rewriting the final
answer and dropping citations. These are hypotheses to test, not observed failures.

The production-aligned alternative would be to add a **Responses** endpoint and Activity
channel support alongside Invocations, preserving Invocations for the bespoke front
door. That is a new protocol adapter with its own conversation, event and approval
mapping; it is not a configuration toggle and is outside this demo's validated scope.

If asked about the Foundry **Publish to Teams and Microsoft 365** wizard, say that a
separate direct publication surface was discovered and `Microsoft.BotService` was
registered. Current guidance for that path calls for Responses + Activity, which v4
does not expose. No Azure Bot resource or Teams application was created and that path
was not validated. Keep it out of the critical walkthrough.

## Why Foundry for this solution?

Close by connecting platform capabilities to requirements already shown.

| Requirement | Foundry role |
| --- | --- |
| Different models for different jobs | Model catalogue, deployments and project API |
| Inspectable specialist behavior | Versioned prompt agents with tools and schemas |
| Pro-code multi-agent control | Hosted Agent Framework workflow and managed identity |
| Grounded public evidence | Foundry IQ knowledge source, knowledge base and citations |
| Firm-owned calculations and lookup | MCP connections to tested business tools |
| Safety plus firm policy | Platform guardrail plus deterministic application controls |
| Human accountability | Typed approval checkpoint before completion |
| Measured change | Durable datasets, evaluation runs and promotion gate |
| Operational evidence | Traces, token/cost telemetry, assets and quota |
| Enterprise access | Entra identities, scoped RBAC and private outbound data path |

The core value is not that Foundry writes a market summary. It is that the same platform
makes models, agents, data connections, tools, evaluations, identities and traces
durable and inspectable while firm-specific logic remains source-controlled code.

## Closing questions

1. Which public-finance workflow has enough repeated document work to justify a pilot?
2. Which information barriers and systems of record must be authoritative in production?
3. What evidence would Compliance, supervision and model governance require before use?
4. Which team owns the first increment: Public Finance, enterprise AI, or a joint team?

Leave with owners for a business-workflow session and an architecture/security session.

## If something breaks

| Failure | Response |
| --- | --- |
| App does not stream | Use the hosted orchestrator playground and explain the same stages |
| Live run is cold or slow | Explain the resources/corpus, then return to the completed run |
| Portal is slow | Use the fallback recording and corresponding VS Code artifact |
| Copilot Studio connector is blocked | Show the DLP banner as the planned governance coda; do not troubleshoot or bypass it live |
| Private Blob cannot open from laptop | Expected; show inventory receipt and IQ count |
| Agent returns an error | Open a prior trace/evaluation; do not debug live |
| Asked about OBO | Not implemented; describe it as the stronger production path |
| Asked about Cosmos memory | BYO memory is not implemented; explain Standard Agent Setup |
| Asked about fine-tuning | Not used; evaluation must establish a stable learning target first |

## Quick glossary

| Term | Short definition |
| --- | --- |
| ISD | Independent school district |
| Par amount | Principal amount issued |
| Unlimited tax bond | Bond payable from an unlimited ad valorem tax pledge, subject to law |
| Texas PSF enhancement | Credit enhancement through the Texas Permanent School Fund program |
| Comparable | A prior issue similar enough to inform structure or pricing context |
| Debt service | Scheduled principal plus interest |
| Call provision | Terms allowing issuer redemption before maturity |
| Official statement | Primary offering disclosure document for a municipal issue |
| Continuing disclosure | Post-issuance financial or operating filing |
| Material event notice | Notice of a specified significant post-issuance event |
| RFP | Request for proposals for underwriting or related services |
| MCP | Model Context Protocol, used here for typed business tools |
| Foundry IQ | Foundry knowledge layer used here for planned, cited retrieval |
| OBO | On-behalf-of token flow carrying user identity downstream |
| PTU | Provisioned throughput units for predictable model capacity |
