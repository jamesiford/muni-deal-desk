#Requires -Version 7.0
[CmdletBinding()]
param(
    [string] $Environment = 'demo-vnet',
    [string] $ConnectionName = 'municipal-deal-foundry-iq',
    [string] $KnowledgeBaseName = 'municipal-deal-knowledge-base',
    [string] $SearchEndpoint,
    [string] $ProjectEndpoint
)

$ErrorActionPreference = 'Stop'
$env:AZURE_DEV_USER_AGENT = 'microsoft_foundry_skill'

if (-not $SearchEndpoint) {
    $SearchEndpoint = azd env get-value AZURE_SEARCH_ENDPOINT --environment $Environment
}
if (-not $ProjectEndpoint) {
    $ProjectEndpoint = azd env get-value AZURE_AI_PROJECT_ENDPOINT --environment $Environment
}
if (-not $SearchEndpoint -or -not $ProjectEndpoint) {
    throw 'Search and Foundry project endpoints are required for the knowledge-base connection.'
}

$target = (
    $SearchEndpoint.TrimEnd('/') +
    "/knowledgebases/$KnowledgeBaseName/mcp?api-version=2026-05-01-preview"
)
$currentJson = azd ai connection show $ConnectionName `
    --project-endpoint $ProjectEndpoint `
    --output json `
    --no-prompt 2>$null
$current = if ($LASTEXITCODE -eq 0) { $currentJson | ConvertFrom-Json } else { $null }
$currentTarget = if ($current.target) { $current.target } else { $current.properties.target }
$currentAuth = if ($current.authType) { $current.authType } else { $current.properties.authType }

if ($currentTarget -eq $target -and $currentAuth -eq 'ProjectManagedIdentity') {
    Write-Host "Connection $ConnectionName already targets $target" -ForegroundColor DarkGray
}
else {
    azd ai connection create $ConnectionName `
        --project-endpoint $ProjectEndpoint `
        --kind remote-tool `
        --target $target `
        --auth-type project-managed-identity `
        --audience 'https://search.azure.com/' `
        --metadata 'ApiType=Azure' `
        --force `
        --no-prompt
    if ($LASTEXITCODE -ne 0) {
        throw 'Foundry IQ project connection registration failed.'
    }
}

azd ai connection show $ConnectionName `
    --project-endpoint $ProjectEndpoint `
    --output table `
    --no-prompt