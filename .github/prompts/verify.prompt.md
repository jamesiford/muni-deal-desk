---
mode: agent
description: Run the full validation gate and report honestly
---

Run every validation gate for this repository and report the results.

```powershell
python -m ruff check .
python -m ruff format --check .
python -m pytest tests/unit -q
az bicep build --file infra/main.bicep
```

Then check the architectural constraints that linting cannot catch:

- No file under `src/domain/` imports from `src.application`, `src.infrastructure`,
  `src.hosts`, or any `azure` package.
- No file under `src/application/` imports from `src.infrastructure`, `src.hosts`, or
  any `azure` package.
- No host under `src/hosts/` contains business logic — only wiring.
- `agent-framework-foundry-hosting` is imported only under `src/hosts/orchestrator/`.

Finally scan for credentials before any push:

```powershell
Get-ChildItem -Recurse -File -Include *.py,*.toml,*.md,*.json,*.yml,*.yaml |
  Where-Object { $_.FullName -notmatch '\\\.git\\' } |
  Select-String -Pattern "(?i)(api[_-]?key\s*=|password\s*=|AccountKey=|sk-[A-Za-z0-9]{20,})"
```

Report failures plainly. Do not describe a component as working if its validation did
not run or did not pass — that rule exists because this solution is presented to a
regulated customer and an overstated claim is worse than a missing feature.
