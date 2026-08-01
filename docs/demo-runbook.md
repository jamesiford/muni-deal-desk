# Demo runbook

customer organization, Microsoft Foundry session. Monday 3 August 2026, 08:00 PDT.

Three parts. The application first so the audience sees a working thing, the Azure
portal briefly so they know what was deployed, then the Foundry portal for the bulk of
the time.

> **Target-state runbook.** Infrastructure, corpus, Foundry IQ and MCP steps are
> validated. Application, specialist-agent, orchestrator and evaluation steps remain
> roadmap work. Do not use this runbook for rehearsal until their phase exit criteria
> pass.

**Portal navigation verified 31 July 2026** against the deployed project. The new
Foundry experience uses a top navigation of **Home, Discover, Build, Operate, Docs**,
which is itself a left-to-right walk. Everything below follows that order.

Project: `muni-deal-desk` on account `aif-wdrdcs6ulivnk`, resource group
`rg-muni-deal-desk-demo`, region `westus3`.

`westus3` is confirmed supported by the new Foundry experience — the project appears in
the project picker and loads.

---

## Before you start

- [ ] Open three browser tabs: the front-door app, the Azure portal on the resource
      group, and the Foundry portal on the project
- [ ] Sign in to the Foundry portal ahead of time and dismiss the "Welcome to the new
      Microsoft Foundry" dialog; it appears on first load and will interrupt you
- [ ] Toggle **New Foundry** on. The classic experience has different navigation and
      the walkthrough below will not match
- [ ] Run one warm-up question so the first live query is not a cold start
- [ ] Have the fallback recording open in a fourth tab
- [ ] Close anything unrelated; the audience will read your tab titles

---

## Part 1 — The application

**Purpose:** establish that something real works, before any platform discussion.

Open the front door. Do not explain the architecture yet.

Paste the question:

> Baytown ISD is issuing about $85 million of unlimited tax school building bonds this
> fall. Pull the three most comparable Texas ISD issues from the last 18 months, compare
> their debt service structure and call features to what we're proposing, flag anything
> in their continuing disclosure that would affect pricing, and draft the market summary
> section for our RFP response.

While it streams, narrate only what is visible:

- Stages appear as the workflow decomposes the question
- Citations resolve against specific documents
- The draft assembles with figures carrying source markers

**Then the three moments that matter.**

**Moment one — the gap.** The answer reports that one comparable has no stated call
provisions. Say: *"It could have guessed a redemption date. It reported the absence
instead. That is a design decision, and I will show you where it is enforced."*

**Moment two — the entitlement contrast.** Switch identity from deal-team member to
public-side analyst. Ask the same question. Fewer comparables return, the internal
pricing memos are gone, and the answer discloses that results were withheld.

Say: *"Same question and same agent. Public citations come from the public knowledge
source; private pricing records are a separate governed source. The application filters
those records for this caller and tells you the answer is partial rather than quietly
answering with less."*

**Moment three — the refusal.** Ask:

> Which of these bonds should I recommend to a client?

It refuses. Say: *"That is not a content filter declining a rude question. That is a
firm conduct rule, and it is enforced in code that does not depend on the model
cooperating."*

Do not explain how any of it works yet. That is the next hour.

---

## Part 2 — What was deployed

**Purpose:** short. Establish the footprint, then move on.

Azure portal, resource group `rg-muni-deal-desk-demo`. Focus on these resources:

| Resource | Role |
| --- | --- |
| `aif-wdrdcs6ulivnk` | Foundry account and project |
| `srch-wdrdcs6ulivnk` | Azure AI Search behind the knowledge base |
| `stwdrdcs6ulivnk` | Corpus documents |
| `ca-mcp-wdrdcs6ulivnk` / `cae-` / `cr-` | MCP app, Container Apps environment and registry |
| `id-wdrdcs6ulivnk` | MCP workload identity; hosted orchestrator has a dedicated Foundry identity |
| `appi-` / `log-` | Application Insights and Log Analytics |

Two points worth making here and nowhere else:

- The whole environment is one `azd up`. Infrastructure, role assignments, private
      corpus upload, Blob knowledge source, knowledge base and MCP registration.
- There are no keys. Local authentication is disabled on the Foundry account and shared
  key access is disabled on storage. Everything runs on Entra identity and role
  assignment.

If asked about private networking: interactive surfaces are public with Entra auth so the
demo works from a laptop. Blob Storage is private; Search uses a shared private link and
the corpus uploader uses a transient private endpoint. A production topology would
isolate the remaining surfaces as well. **Do not imply this hybrid deployment is a
production pattern.**

Move on within five minutes.

---

## Part 3 — The Foundry portal, left to right

**Purpose:** the substance. Walk the top navigation in order.

### Home

Land here. Three things are visible without clicking anything:

- **Project endpoint** — what the application actually calls
- **API key: "API key authentication is disabled for this project."** Point at it. For a
  bank, that sentence is worth more than a slide about security
- **Model selection** and recent work

### Discover

The model catalogue. Keep it brief — the point is breadth and that model choice is not
an architectural commitment.

Say: *"Eleven thousand models, one API. We chose three for this workload. Swapping them
is a configuration change, not a rewrite."*

### Build

The left navigation under Build is grouped **Create** and **Optimize**, and it maps
almost exactly onto what was built. Walk it top to bottom.

**Agents.** The three specialists — Research, Analyst, Compliance — each a registered
prompt agent with its own version. Open one. Show the instructions, the bound model, the
structured output schema.

Say: *"These are editable here. Your team does not need my laptop to change how the
Analyst reasons."*

Then the orchestrator: a hosted Agent Framework workflow. This is the moment to contrast
the two build surfaces — declarative agents you edit in a browser, and pro-code
orchestration you edit in VS Code. Have VS Code ready to switch to.

**Models.** Four deployments: `gpt-5.4-mini` for extraction, `gpt-5.5` for synthesis,
`model-router`, `text-embedding-3-large` for embeddings.

Say: *"Extraction runs on the cheap model. Synthesis runs on the expensive one. That is
a per-task decision, and the cost difference is visible in Operate."*

**Services** and **Tools.** The MCP server connection. Show the tool list — the debt
service calculator and deal lookup.

Say: *"This is our own code, exposed over MCP. The agent chose to call it. Critically,
the debt service numbers are computed arithmetically, not generated. A model describes
the schedule; it does not produce it. That is the difference between a demo and
something you could put in front of a client."*

Then open the separate `municipal-deal-foundry-iq` connection on Research. Show that
`knowledge_base_retrieve` belongs to Foundry IQ, while `find_comparable_deals` belongs
to our custom MCP. The protocol is shared; the capabilities and ownership are distinct.

**Knowledge.** Open `municipal-deal-pdf-blob-source`. Show `kind: azureBlob`, the public
`pdf/public` folder, and the generated data source, skillset, index and indexer. Then open
`municipal-deal-knowledge-base`: `gpt-5.4-mini`, low reasoning, extractive data, and the
retrieval instructions. Point out that answer instructions are blank because specialists
own synthesis.

Be precise here: *"The knowledge source contains public documents only. Private pricing
records are kept in a separate typed repository and filtered in application code using
caller group claims. The agent uses its own managed identity, so this is not
on-behalf-of enforcement. OBO is a different, stronger design."*

That precision will earn more credibility than the feature does.

**Guardrails.** Content safety and jailbreak defence at the platform layer.

Then make the two-layer point: *"This is one layer. The conduct rules you saw refuse a
recommendation are a second, independent layer in our domain code. A prompt change
cannot disable them, and they are deterministic — same input, same finding, every
time."*

**Memory.** Thread and memory state. Worth thirty seconds.

*"Managed by Microsoft inside the project's regional boundary here. If you need it in
your own subscription, Standard Agent Setup points threads and memory at a Cosmos DB
account you own, under your keys and your retention policy. Deployment-time choice; the
agent code is unchanged."*

**Data.** Corpus documents. Reiterate that everything is synthetic — fictional issuers,
nothing retrieved from any disclosure system.

**Evaluations.** Under Optimize. The graded golden set: groundedness, retrieval
relevance, citation accuracy. Show a run.

Say: *"This gates promotion in CI. An agent version that scores below threshold does not
ship. This is the answer to 'how do you know it still works after you change the
prompt.'"*

If the two-model comparison survived the build, show it here: same suite, two model
tiers, real cost and quality numbers.

**Fine-tune.** Mention and move on. Not used, and saying so is more honest than
implying it.

### Operate

The control plane. Left navigation: **Overview, Assets, Compliance, Quota, Admin**.

**Overview.** Active alerts, estimated cost, agent success rate, token usage, and
success-rate trends.

Say: *"One agent is a project. Sixty agents is an estate. This is the screen that
matters when you get to sixty — and note the cost is attributed, so a business unit can
be charged for what it used."*

**Assets.** Inventory of every agent. The governance answer to "what do we actually
have running."

**Compliance.** Where the compliance posture surfaces. Connect to Purview and Entra
Agent ID if the conversation goes that way.

**Quota.** Capacity and throughput. Mention PTU for predictable latency if a
capacity-planning question comes up.

**Admin.** Project access and configuration.

### Tracing

Open a trace from the run in Part 1. This is the closing move, and arguably the single
most persuasive screen in the session.

Walk the tree: decomposition, each retrieval, the tool call, each model call with its
token count.

Say: *"Every step. What it asked, what came back, which tool it chose, what it cost. We
added no instrumentation to get this. When your risk function asks why the agent said
something in March, this is the answer."*

---

## If something breaks

| Failure | Response |
| --- | --- |
| App will not stream | Switch to the Foundry playground and run the same question |
| Portal slow or erroring | Fallback recording, tab four |
| Agent returns an error | Do not debug live. Move to Part 3; the artifacts still tell the story |
| Question about a cut feature | Say it was out of scope for the session and offer it as a follow-up |

Never debug in front of the customer. The recording exists for this.

---

## Closing

Return to the invite's third item: next steps, owners, follow-ups.

- Which of the candidate use cases is real for customer
- The architecture and security session with Emory Long
- Scoping the first increment

Do not leave without a named owner against at least the first two.
