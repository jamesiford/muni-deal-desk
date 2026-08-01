#Requires -Version 7.0
[CmdletBinding()]
param(
    [string] $Environment = 'demo'
)

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$env:AZURE_DEV_USER_AGENT = 'microsoft_foundry_skill'

Push-Location $repoRoot
try {
    azd deploy mcp --environment $Environment --no-prompt
    if ($LASTEXITCODE -ne 0) {
        throw 'MCP service deployment failed.'
    }

    $endpoint = azd env get-value MCP_ENDPOINT --environment $Environment
    if ($LASTEXITCODE -ne 0 -or -not $endpoint) {
        throw 'Deployment succeeded but MCP_ENDPOINT was not found in the azd environment.'
    }

    python -m scripts.smoke_mcp $endpoint
    if ($LASTEXITCODE -ne 0) {
        throw 'The deployed MCP endpoint did not pass its protocol smoke test.'
    }
}
finally {
    Pop-Location
}