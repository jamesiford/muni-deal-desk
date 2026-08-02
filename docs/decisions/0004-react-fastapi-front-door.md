# 4. React and FastAPI front door with SSE streaming

Date: 2026-07-31
Status: Accepted

## Context

The session walkthrough has three parts: the banker-facing application, the Azure portal
showing what was deployed, and the Foundry portal explored left to right. The third part
carries the bulk of the time.

Part one needs a front door. The Foundry playground would cost nothing to build, but then
part one and part three are the same screen, which collapses the narrative. The reveal
only lands if the audience first sees something that looks like an application and is then
shown the platform underneath it.

## Decision

A React and Vite frontend in plain JSX, served by an async FastAPI backend that streams
over Server-Sent Events.

Streaming is the load-bearing requirement rather than a polish item. A multi-agent run
takes long enough that a spinner reads as a hang. Streaming lets the audience watch the
planner decompose the question, the specialists report, and the compliance gate apply —
which is the same story the trace view tells later in the Foundry portal, seen once from
the outside and once from the inside.

The frontend carries an explicit identity switcher between a public-side analyst and a
deal-team member. This is what makes the entitlement contrast visible: the same question,
asked twice, returning different evidence and an explicit disclosure that results were
withheld.

## Consequences

The frontend is a presentation surface only. It holds no business logic: it posts a
question and an identity, and renders streamed events. Every rule lives behind the
mediator, so nothing shown in the browser is implemented twice.

The SSE event contract is deliberately narrow, so the backend can evolve without breaking
the UI:

| Event | Payload |
| --- | --- |
| `stage` | Named workflow stage, for the progress display |
| `status` | Operational message plus optional owning `stage` for handoffs and boundaries |
| `token` | Incremental text for the draft |
| `citation` | A source reference as it is resolved |
| `policy` | A conduct policy finding |
| `final` | The complete `DealDeskAnswer` |
| `error` | A message safe to display |

`status` messages describe observable work such as candidate selection, specialist
handoffs, deterministic calculation, synthesis, control review and approval wait. They
do not expose model chain-of-thought or hidden reasoning tokens. Stage-owned messages
are displayed only while that branch is active. When Research and calculation run in
parallel, completion of the faster calculator branch therefore cannot overwrite the
still-active Research status.

Cost: roughly five to six hours, and a container to deploy. Accepted because part one of
the walkthrough has no substitute, and because a visibly working application is what makes
an architect audience take the platform discussion seriously.

Falls back to the Foundry playground if the schedule collapses. The roadmap lists the
frontend above Copilot Studio in the cut order, because the Copilot Studio surface is
promised on a slide while the frontend is not.
