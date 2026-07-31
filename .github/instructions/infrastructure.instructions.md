---
applyTo: "src/infrastructure/**,src/hosts/**"
---

# Infrastructure and hosts

Adapters implementing application ports, and the composition roots that wire them.

## Infrastructure

Every class here implements a Protocol from `src/application/ports`. It may import
Azure SDKs; it is the only layer that may.

Adapters translate. Business rules do not belong here — if an adapter starts deciding
what is comparable or what is compliant, that logic belongs in a handler or a policy.

`calculators.py` is the deliberate exception: it implements a port and has no external
dependency. It lives here because it satisfies a port, and it is directly unit-tested.

## Hosts

Composition roots only. A host constructs adapters, registers handlers on the mediator,
and starts a server. A host containing an `if` statement about municipal finance is a
host containing business logic that belongs in the application layer.

Both hosts must register handlers against the **same** instances where behaviour must
be identical. Divergence between the MCP tool result and the workflow result is the
failure mode this architecture exists to prevent.

## Identity and secrets

- `DefaultAzureCredential` and managed identity. No keys, no connection strings with
  embedded credentials.
- Read configuration from environment through `pydantic-settings`, and fail fast at
  startup with a message naming the missing variable.
- Never log prompts, retrieved passages, tokens or group claims at `INFO`. Sensitive
  telemetry is opt-in and off by default.

## Registration scripts

Any script registering an agent, connection, index or knowledge base must be idempotent:
read current state, compare against desired, update only on difference. Re-running must
not create a duplicate version. Duplicate agent versions are visible in the portal and
will be seen during the walkthrough.

## Prerelease dependencies

`agent-framework-foundry-hosting` is alpha (`1.0.0a260604`). It is confined to
`hosts/orchestrator` so the fallback in ADR-0002 does not touch the workflow, the
handlers or the contracts. Keep it that way: do not import it elsewhere.
