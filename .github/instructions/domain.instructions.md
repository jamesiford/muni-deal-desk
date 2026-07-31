---
applyTo: "src/domain/**"
---

# Domain layer

The innermost ring. Entities, agent contracts and conduct policies.

## Hard constraints

- **No imports from `src.application`, `src.infrastructure` or `src.hosts`.**
- **No Azure SDK imports.** Not `azure-ai-projects`, not `azure-search-documents`, not
  `azure-identity`. If a type here needs an Azure concept, the concept belongs in a port.
- **No I/O.** No network, no filesystem, no environment variables, no clock reads that
  are not passed in.
- Permitted third-party imports: `pydantic` only.

These constraints are what allow `pytest tests/unit` to pass with no Azure credentials.
That property is asserted by the test suite and is load-bearing for the demonstration —
breaking it is not a stylistic regression.

## Contracts

Types in `contracts/` are used as `response_format` on agents, so they are a public
protocol between components. Changing a field name is a breaking change that also
invalidates recorded evaluation cases. Add fields rather than rename them.

Give every field a `description` where the meaning is not obvious from the name; those
descriptions reach the model as schema and materially affect output quality.

## Policies

Conduct policies must be deterministic and total: the same input always produces the
same finding, and every input produces a finding rather than an exception.

Policies model regulatory obligations. They do not certify compliance. Wording in
`detail` must describe what was found and why it matters operationally, and must not
read as legal advice.

Every policy needs unit tests covering the pass path and each distinct fail path.
