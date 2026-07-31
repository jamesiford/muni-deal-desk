---
applyTo: "src/application/**"
---

# Application layer

Use cases. Ports, messages, handlers and the mediator.

## Hard constraints

- **No imports from `src.infrastructure` or `src.hosts`.** Depend on the Protocol in
  `ports/`, never on a concrete adapter.
- **No Azure SDK imports.**
- Permitted third-party imports: `pydantic` only.

## Handlers

One handler per message, exposing a single `async def handle(self, message) -> Result`.
Dependencies arrive through the constructor as port Protocols.

A handler is reachable from more than one host — typically both the MCP server and the
workflow orchestrator. Never duplicate a rule or calculation into a host; if a host
needs behaviour, it sends a message.

## Entitlements

Every message that reaches data carries a `Caller`. Do not read identity from ambient
state, module-level context or environment variables. Passing it explicitly is what
makes the permission boundary visible at each call site.

When results are withheld by an entitlement filter, return the withheld count alongside
the results. Never silently drop them: an answer that is partial must be able to say so.

Do not distinguish "not found" from "not permitted" in an error surfaced to a caller.
Confirming that a barred record exists is itself a disclosure across the information
barrier.

## Messages

Frozen dataclasses with `slots=True`. A handler must not mutate its input, because the
same message is replayed during evaluation runs.
