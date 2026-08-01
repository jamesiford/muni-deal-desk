---
applyTo: "infra/**"
---

# Infrastructure as code

Bicep, orchestrated by Azure Developer CLI. Target region `westus3`.

## Rules

- Compile after every edit: `az bicep build --file infra/main.bicep`. Do not hand a
  change over without compiling.
- Modules must be idempotent and safe to redeploy.
- No secrets in parameter files. No `@secure()` values with defaults.
- Every resource gets `azd-env-name` tags so `azd down` cleans up completely. A demo
  subscription accumulating orphaned Foundry projects is a real cost.

## Identity

Keep these principals distinct, and grant each only what it needs:

| Principal | Needs |
| --- | --- |
| Deployment identity | Resource creation only |
| Foundry project identity | Its own dependencies and connections |
| MCP runtime identity | Search read, model inference, telemetry publishing, ACR pull |
| Search identity | Storage read, embedding and query-planning model access |

Do not grant `Owner` or `Contributor` to any runtime identity. Prefer built-in
data-plane roles over control-plane roles.

## Model deployments

Four, deliberately: `gpt-5.4-mini` for extraction, `gpt-5.5` for synthesis,
`model-router`, and `text-embedding-3-large` for embeddings.

The count matters for the demonstration. A single deployment renders the cost
attribution panel as a flat line, which removes the reason to open it.

Verify SKU availability in `westus3` before adding a deployment:

```
az cognitiveservices model list -l westus3 --query "[?kind=='AIServices']" -o table
```

## Naming

Use `infra/abbreviations.json` conventions and a resource token derived from the
environment name, so repeated deployments into one subscription do not collide.
