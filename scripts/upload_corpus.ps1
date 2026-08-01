#Requires -Version 7.0
<#
.SYNOPSIS
    Uploads the synthetic corpus with Entra authentication.

.DESCRIPTION
    Uploads every generated PDF and the manifest. Blob metadata carries only indexer
    bootstrap fields; typed deal fields are applied from the manifest after integrated
    vectorization. A SHA-256 metadata value makes repeated runs no-ops when content is
    unchanged. Shared keys and connection strings are never requested.
#>
$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent $PSScriptRoot
$corpusRoot = Join-Path $repoRoot 'src/corpus/out'
$manifestPath = Join-Path $corpusRoot 'manifest.json'

if (-not $env:AZURE_STORAGE_ACCOUNT_NAME) {
    throw 'Missing required environment variable: AZURE_STORAGE_ACCOUNT_NAME'
}
if (-not $env:AZURE_STORAGE_CORPUS_CONTAINER) {
    throw 'Missing required environment variable: AZURE_STORAGE_CORPUS_CONTAINER'
}
if (-not (Test-Path $manifestPath)) {
    throw "Corpus manifest not found: $manifestPath"
}

$publicNetworkAccess = az storage account show `
    --name $env:AZURE_STORAGE_ACCOUNT_NAME `
    --resource-group $env:AZURE_RESOURCE_GROUP `
    --query publicNetworkAccess `
    --output tsv
if ($LASTEXITCODE -ne 0) {
    throw 'Could not inspect the corpus storage network policy.'
}
if ($publicNetworkAccess -eq 'Disabled') {
    Write-Host '  Public Blob access is disabled; using the private uploader.' -ForegroundColor DarkGray
    & (Join-Path $PSScriptRoot 'upload_corpus_private.ps1') `
        -Environment $env:AZURE_ENV_NAME
    exit $LASTEXITCODE
}

$manifest = Get-Content $manifestPath -Raw | ConvertFrom-Json
$entries = @{}
foreach ($document in $manifest.documents) {
    $entries[$document.blob_path] = $document
}

$files = @(Get-ChildItem $corpusRoot -File -Filter '*.pdf') + @(Get-Item $manifestPath)
foreach ($file in $files) {
    $entry = if ($file.Extension -eq '.pdf') { $entries[$file.Name] } else { $null }
    if ($entry -and $entry.sensitivity -ne 'public') {
        Write-Host ("  [skip] {0} - private-side document" -f $file.Name) -ForegroundColor DarkGray
        continue
    }
    $hash = (Get-FileHash $file.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
    $blobName = if ($file.Extension -eq '.pdf') { "pdf/public/$($file.Name)" } else { $file.Name }
    $remoteHash = az storage blob show `
        --account-name $env:AZURE_STORAGE_ACCOUNT_NAME `
        --container-name $env:AZURE_STORAGE_CORPUS_CONTAINER `
        --name $blobName `
        --auth-mode login `
        --query 'metadata.source_sha256' `
        --output tsv 2>$null

    if ($LASTEXITCODE -eq 0 -and $remoteHash -eq $hash) {
        Write-Host ("  unchanged {0}" -f $file.Name) -ForegroundColor DarkGray
        continue
    }

    $metadata = @("source_sha256=$hash")
    $contentType = 'application/json'
    if ($file.Extension -eq '.pdf') {
        if (-not $entry) {
            throw "Manifest has no entry for $($file.Name)"
        }
        $metadata += "document_id=$($entry.document_id)"
        $metadata += "document_title=$($entry.title)"
        $metadata += "sensitivity=$($entry.sensitivity)"
        $contentType = 'application/pdf'
    }

    az storage blob upload `
        --account-name $env:AZURE_STORAGE_ACCOUNT_NAME `
        --container-name $env:AZURE_STORAGE_CORPUS_CONTAINER `
        --name $blobName `
        --file $file.FullName `
        --auth-mode login `
        --overwrite true `
        --content-type $contentType `
        --metadata @metadata `
        --only-show-errors `
        --output none
    if ($LASTEXITCODE -ne 0) {
        throw "Upload failed: $($file.Name)"
    }
    Write-Host ("  uploaded  {0}" -f $blobName) -ForegroundColor Green
}