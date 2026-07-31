---
mode: agent
description: Add a use case as a full vertical slice through the layers
---

Add a new use case to the Deal Desk solution: `${input:useCase}`

Work through the layers in dependency order, inside out. Do not skip a layer because it
seems trivial for this case.

1. **Domain.** If the use case introduces a concept, add or extend an entity in
   `src/domain/entities`. If it produces agent-visible output, add a contract in
   `src/domain/contracts`. Pydantic only; no Azure imports.

2. **Port.** If the use case needs something from outside, add or extend a Protocol in
   `src/application/ports/__init__.py`. Reuse an existing port before adding one.

3. **Message.** Add a frozen `slots=True` dataclass to
   `src/application/messages/__init__.py`. Include a `Caller` if the use case reaches
   data.

4. **Handler.** Add to `src/application/handlers/`. Constructor takes port Protocols.
   Single `async def handle`. No Azure imports, no imports from `infrastructure`.

5. **Adapter.** Implement the port in `src/infrastructure/`, if a new one was added.

6. **Registration.** Register the handler in every host that needs it. Both hosts must
   share the same handler instance where behaviour must be identical.

7. **Tests.** Unit tests in `tests/unit/` covering the success path and each failure
   path. They must pass with no Azure credentials.

Then run the full gate:

```powershell
python -m ruff check . ; python -m ruff format --check . ; python -m pytest tests/unit -q
```

Report what you changed per layer, and state explicitly whether entitlement filtering
applies to this use case and how it is enforced.
