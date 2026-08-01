#Requires -Version 7.0
[CmdletBinding()]
param(
    [string] $ImageName = 'muni-deal-desk-mcp:local'
)

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot

docker build `
    --file (Join-Path $repoRoot 'src/hosts/mcp_server/Dockerfile') `
    --tag $ImageName `
    $repoRoot

if ($LASTEXITCODE -ne 0) {
    throw 'MCP container build failed.'
}

Write-Host "Built $ImageName" -ForegroundColor Green