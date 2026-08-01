#Requires -Version 7.0
<#
.SYNOPSIS
    Reconciles Content Understanding, Search and Foundry IQ Phase 3 artifacts.
#>
$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent $PSScriptRoot
$required = @(
    'AZURE_AI_ACCOUNT_ENDPOINT',
    'AZURE_AI_ACCOUNT_NAME',
    'AZURE_AI_EMBEDDING_DEPLOYMENT',
    'AZURE_AI_EXTRACTION_DEPLOYMENT',
    'AZURE_SEARCH_ENDPOINT',
    'AZURE_STORAGE_ACCOUNT_NAME',
    'AZURE_STORAGE_CORPUS_CONTAINER',
    'AZURE_SUBSCRIPTION_ID',
    'AZURE_RESOURCE_GROUP'
)
$missing = $required | Where-Object { -not (Get-Item "env:$_" -ErrorAction SilentlyContinue) }
if ($missing) {
    throw ("Missing environment values: {0}" -f ($missing -join ', '))
}

Push-Location $repoRoot
try {
    & (Get-Command python).Source -m scripts.setup_phase3
}
finally {
    Pop-Location
}
if ($LASTEXITCODE -ne 0) {
    throw 'Phase 3 setup failed. See the first error above.'
}