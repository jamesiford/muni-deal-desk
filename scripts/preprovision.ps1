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
$repoRoot = Split-Path -Parent $PSScriptRoot

Write-Host ''
Write-Host 'Municipal Deal Desk - pre-provision checks' -ForegroundColor Cyan
Write-Host ''

# --- Azure CLI login and subscription context ------------------------------------
$account = az account show 2>$null | ConvertFrom-Json
if (-not $account) {
    throw 'Not signed in to Azure CLI. Run: az login'
}
if ($env:AZURE_SUBSCRIPTION_ID) {
    az account set --subscription $env:AZURE_SUBSCRIPTION_ID
    if ($LASTEXITCODE -ne 0) {
        throw "Could not select the azd subscription: $($env:AZURE_SUBSCRIPTION_ID)"
    }
    $account = az account show 2>$null | ConvertFrom-Json
    if ($account.id -ne $env:AZURE_SUBSCRIPTION_ID) {
        throw "Azure CLI subscription does not match the azd environment: $($account.id)"
    }
}
Write-Host ("  Subscription : {0}" -f $account.name)
Write-Host ("  Identity     : {0}" -f $account.user.name)

# --- Resource providers ----------------------------------------------------------
$requiredProviders = @(
    'Microsoft.App',
    'Microsoft.CognitiveServices',
    'Microsoft.ContainerInstance',
    'Microsoft.ContainerRegistry',
    'Microsoft.Insights',
    'Microsoft.ManagedIdentity',
    'Microsoft.Network',
    'Microsoft.OperationalInsights',
    'Microsoft.Search',
    'Microsoft.Storage'
)
$unregistered = $requiredProviders | Where-Object {
    $state = az provider show --namespace $_ --query registrationState -o tsv 2>$null
    $state -ne 'Registered'
}
if ($unregistered) {
    throw ("Required Azure resource providers are not registered: {0}. Register them before running azd up." -f ($unregistered -join ', '))
}

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

    $template = az bicep build `
        --file (Join-Path $repoRoot 'infra/main.bicep') `
        --stdout 2>$null | ConvertFrom-Json
    if (-not $template) {
        throw 'Could not compile infra/main.bicep to inspect model requirements.'
    }
    $required = @($template.parameters.modelDeployments.defaultValue)
    $available = az cognitiveservices model list --location $location `
        --query "[?kind=='AIServices'].model" -o json 2>$null | ConvertFrom-Json

    if ($available) {
        $missing = $required | Where-Object {
            $requirement = $_
            -not ($available | Where-Object {
                $_.name -eq $requirement.modelName -and
                $_.version -eq $requirement.version -and
                $_.skus.name -contains $requirement.skuName
            })
        }
        if ($missing) {
            $labels = $missing | ForEach-Object {
                "$($_.modelName) $($_.version) ($($_.skuName))"
            }
            throw ("Model versions or SKUs unavailable in {0}: {1}. Choose another region or edit modelDeployments in infra/main.bicep." -f $location, ($labels -join ', '))
        }
        Write-Host '  All configured model versions and SKUs are available.' -ForegroundColor Green
    }
    else {
        Write-Warning '  Could not query model availability. Continuing.'
    }
}

Write-Host ''
Write-Host 'Pre-provision checks passed.' -ForegroundColor Green
Write-Host ''
