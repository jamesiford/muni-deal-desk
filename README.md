# Municipal Deal Desk

A Microsoft Foundry demonstration solution: a new-issue **Deal Desk** agent for a
public finance broker-dealer desk.

The solution exists to make Foundry platform capabilities visible and explainable in a
customer technical session. Every capability has a corresponding artifact that can be
opened in the Microsoft Foundry portal and equivalent source that can be opened in
VS Code.

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

| Capability | Where it appears |
| --- | --- |
| Agents | Three prompt-agent specialists plus a hosted workflow orchestrator |
| Foundry IQ | One knowledge base over the corpus, with entitlement-filtered retrieval |
| MCP | Custom server exposing the debt service calculator and deal lookup |
| Tools | Calculator and lookup tools, reachable by agents |
| Model choice | Extraction, reasoning and router deployments compared on cost and latency |
| Guardrails | Deterministic conduct policies, plus content safety |
| Evaluations | Graded golden set gating promotion in CI |
| Tracing | Decomposition, retrieval, tool selection and model calls per interaction |
| Observability | Cost attribution and continuous evaluation in the control plane |
| Governance | Distinct agent identities, sensitivity labelling, entitlement-aware retrieval |

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

Retrieval is filtered using group claims passed at query time. That is ACL-aware
retrieval, and it is not the same as end-to-end on-behalf-of enforcement. The
distinction is documented in `docs/guardrails.md` and must be stated accurately when
the solution is presented.

The conduct policies are modelled on MSRB Rule G-17, MSRB Rule G-42 and FINRA
Regulatory Notice 24-09. They do not certify compliance with any of them.

## Getting started

```powershell
python -m pip install -e ".[dev]"
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
