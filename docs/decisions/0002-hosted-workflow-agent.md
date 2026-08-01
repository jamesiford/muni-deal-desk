# 2. Hosting the orchestrator as an Agent Framework workflow agent

Date: 2026-07-31
Status: Accepted

## Context

The session must show two things that pull in different directions: agents that are
viewable and editable in the Microsoft Foundry portal, and pro-code multi-agent
orchestration that is only honestly shown in source.

Microsoft Agent Framework workflows run anywhere, but a workflow only appears as an
agent in the Foundry portal when it is hosted through the agent server bridge.

## Decision

Two agent kinds.

The Research, Analyst and Compliance specialists are **prompt agents**, registered with
`azure-ai-projects` 2.4.0 using `PromptAgentDefinition` and `create_version`. They are
versioned in the project and therefore individually viewable, editable and testable in
the portal.

The Deal Desk orchestrator is a **Microsoft Agent Framework workflow** converted with
`.as_agent()` and served by `agent_framework_foundry_hosting.InvocationsHostServer`.
`azd` deploys the Python 3.14 source directly to Foundry Hosted Agents, which builds the
runtime image, creates an immutable agent version and dedicated agent identity, and
publishes the Invocations endpoint. The custom MCP server remains in Container Apps.

Internal specialist communication uses checkpointed functional workflow steps carrying
Pydantic contracts from `domain/contracts`. A2A is not used for internal wiring.

The Invocations protocol is chosen over Responses for the orchestrator.

## Prerelease dependency

`agent-framework-foundry-hosting` is pinned at `1.0.0a260604`, an alpha release. The
repository rules require an exact version, a limitation, a fallback and a validation
step for any prerelease dependency.

**Exact version:** `agent-framework-foundry-hosting==1.0.0a260604`, isolated in the
`hosting` optional dependency group so the core dependency set is unaffected by a
change to the hosting path.

**Limitation:** The published Agent Framework sample for hosted agents imports
`azure.ai.agentserver.agentframework`. That distribution is not available on PyPI as of
2026-07-31; `pip index versions azure-ai-agentserver-agentframework` returns no
matching distribution. `agent-framework-foundry-hosting` supersedes it and exposes
`InvocationsHostServer` and `ResponsesHostServer`. Sample code found online will not
run unmodified.

**Fallback:** If the alpha host proves unstable, the same workflow can run in Container
Apps behind its Invocations host. The fallback was exercised during development, then
removed after native direct-code hosting passed. No fallback ACA or image remains.

**Validation:** Foundry Hosted Agent `municipal-deal-desk-orchestrator` version 3 is
active and portal-visible. A typed `DealDeskRequest` paused for a typed supervising-
principal decision and resumed to a valid `DealDeskAnswer`. Application Insights shows
planner, Research, Analyst, synthesis, Compliance, guardrail and approval spans.

## Consequences

The session can open a specialist in the portal, edit its instructions, run it in the
playground, then switch to VS Code and show the workflow that composes all three. That
is the intended "both surfaces" narrative.

Rejecting A2A for internal wiring is a deliberate accuracy choice. Agent Framework's
A2A support is client-side: `A2AAgent` wraps an externally hosted endpoint discovered
through an AgentCard at `/.well-known/agent.json`. Using it between co-located
specialists would add network hops and failure modes to a live demo while
misrepresenting what the protocol is for. A2A may still be demonstrated as an optional
aside by exposing the Compliance specialist as an external endpoint, off the critical
path.

Invocations is chosen over Responses because it supports websocket transport, SSE
keepalive and invocation cancellation, which suit a multi-agent run lasting longer than
a single request-response cycle.
