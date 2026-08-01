#Requires -Version 7.0
<#
.SYNOPSIS
    Seeds the private corpus container from a transient Azure Container Instance.

.DESCRIPTION
    Builds an image containing only public PDFs, creates a short-lived VNet/private
    endpoint and uploader identity, uploads through the storage private endpoint, and
    removes the transient resources. The Search shared private link is separate and
    remains available for knowledge-source ingestion.
#>
[CmdletBinding()]
param(
    [string] $Environment = 'demo',
    [switch] $KeepResources
)

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$env:AZURE_DEV_USER_AGENT = 'microsoft_foundry_skill'

Push-Location $repoRoot
try {
    azd env get-values --environment $Environment | ForEach-Object {
        if ($_ -match '^([^=]+)="(.*)"$') {
            Set-Item -Path "Env:$($matches[1])" -Value $matches[2]
        }
    }

    $required = @(
        'AZURE_LOCATION',
        'AZURE_SUBSCRIPTION_ID',
        'AZURE_RESOURCE_GROUP',
        'AZURE_STORAGE_ACCOUNT_NAME',
        'AZURE_STORAGE_BLOB_ENDPOINT',
        'AZURE_STORAGE_CORPUS_CONTAINER',
        'AZURE_CONTAINER_REGISTRY_NAME',
        'AZURE_CONTAINER_REGISTRY_ENDPOINT'
    )
    $missing = $required | Where-Object { -not (Get-Item "env:$_" -ErrorAction SilentlyContinue) }
    if ($missing) {
        throw "Missing environment values: $($missing -join ', ')"
    }

    $suffix = $Environment.ToLowerInvariant() -replace '[^a-z0-9-]', ''
    $uploadResourceGroup = "rg-mdd-corpus-upload-$suffix"
    $identityName = "id-mdd-corpus-upload-$suffix"
    $vnetName = "vnet-mdd-corpus-upload-$suffix"
    $aciSubnetName = 'snet-aci'
    $privateEndpointSubnetName = 'snet-private-endpoints'
    $privateEndpointName = "pe-mdd-corpus-$suffix"
    $containerGroupName = "ci-mdd-corpus-upload-$suffix"
    $repository = 'muni-deal-desk/corpus-uploader'
    $tag = "phase3-$([DateTimeOffset]::UtcNow.ToUnixTimeSeconds())"
    $image = "$($env:AZURE_CONTAINER_REGISTRY_ENDPOINT)/${repository}:$tag"

    if ((az group exists --name $uploadResourceGroup) -eq 'true') {
        az group delete --name $uploadResourceGroup --yes --no-wait
        az group wait --name $uploadResourceGroup --deleted
    }

    Write-Host "Building public-corpus uploader image $image" -ForegroundColor Cyan
    az acr build `
        --registry $env:AZURE_CONTAINER_REGISTRY_NAME `
        --image "${repository}:$tag" `
        --file scripts/private_blob_uploader/Dockerfile `
        --no-logs `
        .
    if ($LASTEXITCODE -ne 0) {
        throw 'Could not queue or complete the uploader image build.'
    }
    $tagExists = az acr repository show-tags `
        --name $env:AZURE_CONTAINER_REGISTRY_NAME `
        --repository $repository `
        --query "contains(@, '$tag')" `
        --output tsv
    if ($tagExists -ne 'true') {
        throw 'Uploader image was not pushed to Azure Container Registry.'
    }

    Write-Host "Creating transient private upload network" -ForegroundColor Cyan
    az group create --name $uploadResourceGroup --location $env:AZURE_LOCATION --output none
    $identity = az identity create `
        --name $identityName `
        --resource-group $uploadResourceGroup `
        --location $env:AZURE_LOCATION `
        --output json | ConvertFrom-Json
    $storageId = az storage account show `
        --name $env:AZURE_STORAGE_ACCOUNT_NAME `
        --resource-group $env:AZURE_RESOURCE_GROUP `
        --query id --output tsv
    $registryId = az acr show `
        --name $env:AZURE_CONTAINER_REGISTRY_NAME `
        --resource-group $env:AZURE_RESOURCE_GROUP `
        --query id --output tsv

    az role assignment create `
        --assignee-object-id $identity.principalId `
        --assignee-principal-type ServicePrincipal `
        --role 'Storage Blob Data Contributor' `
        --scope $storageId `
        --output none
    az role assignment create `
        --assignee-object-id $identity.principalId `
        --assignee-principal-type ServicePrincipal `
        --role AcrPull `
        --scope $registryId `
        --output none

    az network vnet create `
        --name $vnetName `
        --resource-group $uploadResourceGroup `
        --location $env:AZURE_LOCATION `
        --address-prefixes 10.77.0.0/16 `
        --subnet-name $aciSubnetName `
        --subnet-prefixes 10.77.1.0/24 `
        --output none
    az network vnet subnet update `
        --name $aciSubnetName `
        --vnet-name $vnetName `
        --resource-group $uploadResourceGroup `
        --delegations Microsoft.ContainerInstance/containerGroups `
        --output none
    az network vnet subnet create `
        --name $privateEndpointSubnetName `
        --vnet-name $vnetName `
        --resource-group $uploadResourceGroup `
        --address-prefixes 10.77.2.0/24 `
        --private-endpoint-network-policies Disabled `
        --output none
    az network private-dns zone create `
        --resource-group $uploadResourceGroup `
        --name privatelink.blob.core.windows.net `
        --output none
    az network private-dns link vnet create `
        --resource-group $uploadResourceGroup `
        --zone-name privatelink.blob.core.windows.net `
        --name link-corpus-upload `
        --virtual-network $vnetName `
        --registration-enabled false `
        --output none
    $subnetId = az network vnet subnet show `
        --name $privateEndpointSubnetName `
        --vnet-name $vnetName `
        --resource-group $uploadResourceGroup `
        --query id `
        --output tsv
    $privateEndpointId = (
        "/subscriptions/$($env:AZURE_SUBSCRIPTION_ID)/resourceGroups/" +
        "$uploadResourceGroup/providers/Microsoft.Network/privateEndpoints/" +
        $privateEndpointName
    )
    $privateEndpointUri = (
        "https://management.azure.com$privateEndpointId" +
        '?api-version=2024-05-01'
    )
    $privateEndpointBody = @{
        location = $env:AZURE_LOCATION
        properties = @{
            subnet = @{ id = $subnetId }
            privateLinkServiceConnections = @(
                @{
                    name = 'corpus-upload'
                    properties = @{
                        privateLinkServiceId = $storageId
                        groupIds = @('blob')
                        requestMessage = 'Private corpus upload'
                    }
                }
            )
        }
    } | ConvertTo-Json -Depth 10
    $managementToken = az account get-access-token `
        --resource https://management.azure.com/ `
        --query accessToken `
        --output tsv
    Invoke-RestMethod `
        -Method Put `
        -Uri $privateEndpointUri `
        -Headers @{ Authorization = "Bearer $managementToken" } `
        -ContentType 'application/json' `
        -Body $privateEndpointBody | Out-Null
    az network private-endpoint wait `
        --name $privateEndpointName `
        --resource-group $uploadResourceGroup `
        --created `
        --interval 10 `
        --timeout 600
    if ($LASTEXITCODE -ne 0) {
        throw 'Storage private endpoint did not reach Succeeded.'
    }
    az network private-endpoint dns-zone-group create `
        --endpoint-name $privateEndpointName `
        --resource-group $uploadResourceGroup `
        --name blob-zone-group `
        --zone-name blob `
        --private-dns-zone privatelink.blob.core.windows.net `
        --output none

    Write-Host "Uploading public corpus through the private endpoint" -ForegroundColor Cyan
    az container create `
        --name $containerGroupName `
        --resource-group $uploadResourceGroup `
        --location $env:AZURE_LOCATION `
        --image $image `
        --registry-login-server $env:AZURE_CONTAINER_REGISTRY_ENDPOINT `
        --assign-identity $identity.id `
        --acr-identity $identity.id `
        --vnet $vnetName `
        --subnet $aciSubnetName `
        --os-type Linux `
        --restart-policy Never `
        --cpu 1 `
        --memory 1.5 `
        --environment-variables `
            "AZURE_CLIENT_ID=$($identity.clientId)" `
            "AZURE_STORAGE_BLOB_ENDPOINT=$($env:AZURE_STORAGE_BLOB_ENDPOINT)" `
            "AZURE_STORAGE_CORPUS_CONTAINER=$($env:AZURE_STORAGE_CORPUS_CONTAINER)" `
        --output none
    az container attach --name $containerGroupName --resource-group $uploadResourceGroup
    $state = az container show `
        --name $containerGroupName `
        --resource-group $uploadResourceGroup `
        --query 'containers[0].instanceView.currentState' `
        --output json | ConvertFrom-Json
    if ($state.exitCode -ne 0) {
        az container logs --name $containerGroupName --resource-group $uploadResourceGroup
        throw "Private corpus upload failed: $($state.detailStatus)"
    }
    az container logs --name $containerGroupName --resource-group $uploadResourceGroup
    Write-Host 'Private public-corpus upload completed.' -ForegroundColor Green
}
finally {
    if (-not $KeepResources -and $uploadResourceGroup) {
        $identityId = az identity show `
            --name $identityName `
            --resource-group $uploadResourceGroup `
            --query principalId --output tsv 2>$null
        if ($identityId) {
            az role assignment delete --assignee $identityId --scope $storageId 2>$null
            az role assignment delete --assignee $identityId --scope $registryId 2>$null
        }
        az group delete --name $uploadResourceGroup --yes --no-wait 2>$null
        if ($env:AZURE_CONTAINER_REGISTRY_NAME -and $repository -and $tag) {
            az acr repository delete `
                --name $env:AZURE_CONTAINER_REGISTRY_NAME `
                --image "${repository}:$tag" `
                --yes 2>$null
        }
    }
    Pop-Location
}
