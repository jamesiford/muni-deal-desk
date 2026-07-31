#Requires -Version 7.0
<#
.SYNOPSIS
    Pre-provision checks for the Municipal Deal Desk demonstration environment.

.DESCRIPTION
    Fails fast on the conditions that otherwise surface as confusing mid-deployment
    errors: wrong subscription, missing model availability in the target region, and
    an unresolved deploying identity.

    Every check here exists because its absence produced a real failure during build.
#>
$ErrorActionPreference = 'Stop'

Write-Host ''
Write-Host 'Municipal Deal Desk - pre-provision checks' -ForegroundColor Cyan
Write-Host ''

# --- Azure CLI login -------------------------------------------------------------
$account = az account show 2>$null | ConvertFrom-Json
if (-not $account) {
    throw 'Not signed in to Azure CLI. Run: az login'
}
Write-Host ("  Subscription : {0}" -f $account.name)
Write-Host ("  Identity     : {0}" -f $account.user.name)

# --- Deploying identity ----------------------------------------------------------
# Role assignments need an object ID. azd supplies AZURE_PRINCIPAL_ID for user logins
# but not always for service principals, so resolve and set it explicitly.
if (-not $env:AZURE_PRINCIPAL_ID) {
    $principalId = az ad signed-in-user show --query id -o tsv 2>$null
    if (-not $principalId) {
        throw 'Could not resolve the signed-in identity. Set AZURE_PRINCIPAL_ID manually.'
    }
    azd env set AZURE_PRINCIPAL_ID $principalId | Out-Null
    Write-Host ("  Principal ID : {0}" -f $principalId)
}

$principalType = if ($account.user.type -eq 'servicePrincipal') { 'ServicePrincipal' } else { 'User' }
azd env set AZURE_PRINCIPAL_TYPE $principalType | Out-Null

# --- Model availability ----------------------------------------------------------
# A model missing from the target region fails partway through provisioning, after
# the account exists. Checking first turns that into a clear message in seconds.
$location = $env:AZURE_LOCATION
if ($location) {
    Write-Host ''
    Write-Host ("  Checking model availability in {0}..." -f $location)

    $required = @('gpt-5.4-mini', 'gpt-5.5', 'model-router', 'text-embedding-3-large')
    $available = az cognitiveservices model list --location $location `
        --query "[?kind=='AIServices'].model.name" -o tsv 2>$null

    if ($available) {
        $missing = $required | Where-Object { $available -notcontains $_ }
        if ($missing) {
            throw ("Models unavailable in {0}: {1}. Choose another region or edit modelDeployments in infra/main.bicep." -f $location, ($missing -join ', '))
        }
        Write-Host '  All four model deployments are available.' -ForegroundColor Green
    }
    else {
        Write-Warning '  Could not query model availability. Continuing.'
    }
}

Write-Host ''
Write-Host 'Pre-provision checks passed.' -ForegroundColor Green
Write-Host ''
