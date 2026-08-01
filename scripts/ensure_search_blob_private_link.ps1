#Requires -Version 7.0
<#
.SYNOPSIS
    Ensures Azure AI Search can privately read the corpus Blob container.
#>
$ErrorActionPreference = 'Stop'

$required = @(
    'AZURE_RESOURCE_GROUP',
    'AZURE_SEARCH_SERVICE_NAME',
    'AZURE_STORAGE_ACCOUNT_NAME'
)
$missing = $required | Where-Object { -not (Get-Item "env:$_" -ErrorAction SilentlyContinue) }
if ($missing) {
    throw "Missing environment values: $($missing -join ', ')"
}

$linkName = 'spl-muni-deal-corpus-blob'
$storageId = az storage account show `
    --name $env:AZURE_STORAGE_ACCOUNT_NAME `
    --resource-group $env:AZURE_RESOURCE_GROUP `
    --query id `
    --output tsv

az search shared-private-link-resource show `
    --name $linkName `
    --service-name $env:AZURE_SEARCH_SERVICE_NAME `
    --resource-group $env:AZURE_RESOURCE_GROUP `
    --output none 2>$null
if ($LASTEXITCODE -ne 0) {
    az search shared-private-link-resource create `
        --name $linkName `
        --service-name $env:AZURE_SEARCH_SERVICE_NAME `
        --resource-group $env:AZURE_RESOURCE_GROUP `
        --group-id blob `
        --resource-id $storageId `
        --request-message 'Approve private Blob access for Municipal Deal Desk knowledge source' `
        --only-show-errors `
        --output none
    if ($LASTEXITCODE -ne 0) {
        throw 'Could not create the Search shared private link to Blob Storage.'
    }
}

$connections = @(
    az network private-endpoint-connection list `
        --id $storageId `
        --output json | ConvertFrom-Json
)
$pending = @(
    $connections | Where-Object {
        $_.properties.privateLinkServiceConnectionState.status -eq 'Pending'
    }
)
foreach ($connection in $pending) {
    az network private-endpoint-connection approve `
        --id $connection.id `
        --description 'Approved for Azure AI Search Blob knowledge source' `
        --only-show-errors `
        --output none
    if ($LASTEXITCODE -ne 0) {
        throw "Could not approve private endpoint connection $($connection.name)."
    }
}

$link = az search shared-private-link-resource show `
    --name $linkName `
    --service-name $env:AZURE_SEARCH_SERVICE_NAME `
    --resource-group $env:AZURE_RESOURCE_GROUP `
    --output json | ConvertFrom-Json
if ($link.properties.status -ne 'Approved' -or $link.properties.provisioningState -ne 'Succeeded') {
    throw (
        "Search Blob private link is not ready: " +
        "status=$($link.properties.status), state=$($link.properties.provisioningState)"
    )
}
Write-Host '  Search Blob shared private link is approved.' -ForegroundColor Green
