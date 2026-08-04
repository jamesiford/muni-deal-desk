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
    [string] $Environment = 'demo-vnet',
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
        'AZURE_CONTAINER_REGISTRY_ENDPOINT',
        'AZURE_CORPUS_UPLOADER_IDENTITY_ID',
        'AZURE_CORPUS_UPLOADER_CLIENT_ID',
        'AZURE_CORPUS_UPLOADER_SUBNET',
        'AZURE_EVALUATION_VNET_NAME'
    )
    $missing = $required | Where-Object { -not (Get-Item "env:$_" -ErrorAction SilentlyContinue) }
    if ($missing) {
        throw "Missing environment values: $($missing -join ', ')"
    }

    $suffix = $Environment.ToLowerInvariant() -replace '[^a-z0-9-]', ''
    $timestamp = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
    $containerGroupName = "ci-mdd-upload-$suffix-$timestamp"
    $repository = 'muni-deal-desk/corpus-uploader'
    $tag = "phase3-$timestamp"
    $image = "$($env:AZURE_CONTAINER_REGISTRY_ENDPOINT)/${repository}:$tag"

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

    Write-Host "Uploading public corpus through the private endpoint" -ForegroundColor Cyan
    az container create `
        --name $containerGroupName `
        --resource-group $env:AZURE_RESOURCE_GROUP `
        --location $env:AZURE_LOCATION `
        --image $image `
        --registry-login-server $env:AZURE_CONTAINER_REGISTRY_ENDPOINT `
        --assign-identity $env:AZURE_CORPUS_UPLOADER_IDENTITY_ID `
        --acr-identity $env:AZURE_CORPUS_UPLOADER_IDENTITY_ID `
        --vnet $env:AZURE_EVALUATION_VNET_NAME `
        --subnet $env:AZURE_CORPUS_UPLOADER_SUBNET `
        --os-type Linux `
        --restart-policy Never `
        --no-wait `
        --cpu 1 `
        --memory 1.5 `
        --environment-variables `
            "AZURE_CLIENT_ID=$($env:AZURE_CORPUS_UPLOADER_CLIENT_ID)" `
            "AZURE_STORAGE_BLOB_ENDPOINT=$($env:AZURE_STORAGE_BLOB_ENDPOINT)" `
            "AZURE_STORAGE_CORPUS_CONTAINER=$($env:AZURE_STORAGE_CORPUS_CONTAINER)" `
        --output none
    $state = $null
    $deadline = [DateTimeOffset]::UtcNow.AddMinutes(10)
    while ([DateTimeOffset]::UtcNow -lt $deadline) {
        $state = az container show `
            --name $containerGroupName `
            --resource-group $env:AZURE_RESOURCE_GROUP `
            --query 'containers[0].instanceView.currentState' `
            --output json | ConvertFrom-Json
        if ($state.state -eq 'Terminated') {
            break
        }
        Start-Sleep -Seconds 5
    }
    if ($state.state -ne 'Terminated') {
        throw "Private corpus uploader did not terminate within ten minutes."
    }
    if ($state.exitCode -ne 0) {
        az container logs --name $containerGroupName --resource-group $env:AZURE_RESOURCE_GROUP
        throw "Private corpus upload failed: $($state.detailStatus)"
    }
    $logs = az container logs --name $containerGroupName --resource-group $env:AZURE_RESOURCE_GROUP
    $logs | Write-Host
    $inventoryLine = $logs | Where-Object { $_ -like 'CORPUS_INVENTORY=*' } | Select-Object -Last 1
    if (-not $inventoryLine) {
        throw 'Private uploader did not return a corpus inventory receipt.'
    }
    $inventoryJson = $inventoryLine.Substring('CORPUS_INVENTORY='.Length)
    $inventory = $inventoryJson | ConvertFrom-Json
    $manifest = Get-Content (Join-Path $repoRoot 'src/corpus/out/manifest.json') -Raw | ConvertFrom-Json
    $expected = @{}
    foreach ($document in $manifest.documents | Where-Object sensitivity -eq 'public') {
        $path = "pdf/public/$($document.blob_path)"
        $hash = (Get-FileHash (Join-Path $repoRoot "src/corpus/out/$($document.blob_path)") `
            -Algorithm SHA256).Hash.ToLowerInvariant()
        $expected[$path] = @{
            document_id = $document.document_id
            source_sha256 = $hash
        }
    }
    if ($inventory.document_count -ne $expected.Count) {
        throw "Private corpus inventory contains $($inventory.document_count) PDFs; expected $($expected.Count)."
    }
    foreach ($document in $inventory.documents) {
        $match = $expected[$document.blob_path]
        if (-not $match) {
            throw "Unexpected Blob inventory path: $($document.blob_path)"
        }
        if ($document.document_id -ne $match.document_id -or
            $document.source_sha256 -ne $match.source_sha256) {
            throw "Blob inventory metadata mismatch: $($document.blob_path)"
        }
    }
    $inventoryPath = Join-Path $repoRoot 'src/corpus/out/public-inventory.json'
    $inventoryJson | ConvertFrom-Json | ConvertTo-Json -Depth 10 | Set-Content `
        -Path $inventoryPath `
        -Encoding utf8
    Write-Host "  Inventory receipt: $inventoryPath" -ForegroundColor DarkGray
    Write-Host 'Private public-corpus upload completed.' -ForegroundColor Green
}
finally {
    if (-not $KeepResources -and $containerGroupName) {
        az container delete `
            --name $containerGroupName `
            --resource-group $env:AZURE_RESOURCE_GROUP `
            --yes `
            --output none 2>$null
        if ($env:AZURE_CONTAINER_REGISTRY_NAME -and $repository -and $tag) {
            az acr repository delete `
                --name $env:AZURE_CONTAINER_REGISTRY_NAME `
                --image "${repository}:$tag" `
                --yes 2>$null
        }
    }
    Pop-Location
}
