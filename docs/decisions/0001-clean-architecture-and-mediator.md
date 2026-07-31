# 1. Clean Architecture with a hand-rolled mediator

Date: 2026-07-31
Status: Accepted

## Context

This solution is a demonstration asset for a customer technical session. Two audiences
read it: the presenter narrating it on screen, and the customer engineers who may be
pointed at the repository afterwards. It also has to expose the same use cases through
two different hosts — an MCP server and an Agent Framework workflow orchestrator.

## Decision

Four layers with inward-pointing dependencies: `domain`, `application`,
`infrastructure`, `hosts`. Outbound dependencies are expressed as Protocol interfaces
in `application/ports`. Use cases are dispatched through a mediator implemented in
`application/mediator.py`.

The mediator is hand-rolled at roughly sixty lines rather than taken from a library.

## Consequences

The MCP server and the orchestrator resolve the same handler instances, so the debt
service calculation and the conduct policies exist once and are reachable from both
surfaces. This is the DRY property that matters here, because a demo that computed a
figure two different ways would eventually show two different numbers on stage.

`domain` and `application` import no Azure SDK, so unit tests run without credentials.
This is enforced by the tests themselves: `pytest tests/unit` passes on a machine with
no Azure login.

A hand-rolled mediator can be read aloud during a walkthrough. A library dependency
would have to be explained instead of shown, and the session's purpose is to make
mechanics visible.

The cost is a small amount of dispatch machinery that a reader must understand before
following a request through the system. Mitigated by keeping it in one file with no
generic indirection beyond a type-keyed dictionary.
