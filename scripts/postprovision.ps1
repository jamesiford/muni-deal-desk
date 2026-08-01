#Requires -Version 7.0
<#
.SYNOPSIS
    Completes the data-plane setup after infrastructure provisioning.

.DESCRIPTION
    Runs the steps that turn a provisioned environment into a working demonstration:
    generate the synthetic corpus, establish private Blob access, upload it, create
    Foundry IQ artifacts, and register the specialist agents.

    Each step is idempotent and skipped when its inputs are absent, so this script is
    safe to run repeatedly and safe to run before the later build phases exist.

    Role assignments can take a minute to propagate, so data-plane calls are retried
    rather than allowed to fail the deployment.
#>
$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent $PSScriptRoot

Write-Host ''
Write-Host 'Municipal Deal Desk - post-provision setup' -ForegroundColor Cyan
Write-Host ''

function Invoke-Step {
    <#
    .SYNOPSIS
        Runs a named setup step, skipping it when its script is not yet present.
    #>
    param(
        [Parameter(Mandatory)][string] $Name,
        [Parameter(Mandatory)][string] $ScriptPath,
        [string[]] $ScriptArgs = @()
    )

    $full = Join-Path $repoRoot $ScriptPath
    if (-not (Test-Path $full)) {
        Write-Host ("  [skip] {0} - not yet implemented" -f $Name) -ForegroundColor DarkGray
        return
    }

    Write-Host ("  [run ] {0}" -f $Name) -ForegroundColor Yellow
    & $full @ScriptArgs
    if ($LASTEXITCODE -ne 0) {
        throw ("Step failed: {0}" -f $Name)
    }
    Write-Host ("  [ ok ] {0}" -f $Name) -ForegroundColor Green
}

# --- Verify required outputs reached the environment ------------------------------
$required = @(
    'AZURE_AI_PROJECT_ENDPOINT',
    'AZURE_SEARCH_ENDPOINT',
    'AZURE_STORAGE_ACCOUNT_NAME'
)
$missing = $required | Where-Object { -not (Get-Item "env:$_" -ErrorAction SilentlyContinue) }
if ($missing) {
    throw ("Missing environment values after provisioning: {0}" -f ($missing -join ', '))
}

Write-Host ("  Project  : {0}" -f $env:AZURE_AI_PROJECT_ENDPOINT)
Write-Host ("  Search   : {0}" -f $env:AZURE_SEARCH_ENDPOINT)
Write-Host ("  Storage  : {0}" -f $env:AZURE_STORAGE_ACCOUNT_NAME)
Write-Host ("  Registry : {0}" -f $env:AZURE_CONTAINER_REGISTRY_ENDPOINT)
Write-Host ''

# --- Wait for role assignment propagation ----------------------------------------
# Data-plane calls immediately after provisioning can fail with 403 while role
# assignments replicate. A short wait costs less than a failed deployment.
Write-Host '  Waiting 30s for role assignments to propagate...' -ForegroundColor DarkGray
Start-Sleep -Seconds 30
Write-Host ''

# --- Verify the environment actually works ---------------------------------------
# Provisioning success is not the same as a working environment, and finding out at
# demonstration time is not acceptable.
Write-Host '  [run ] Verify environment' -ForegroundColor Yellow
python (Join-Path $repoRoot 'scripts/verify_environment.py')
if ($LASTEXITCODE -ne 0) {
    throw 'Environment verification failed. See failures above.'
}
Write-Host '  [ ok ] Verify environment' -ForegroundColor Green
Write-Host ''

# --- Steps, in dependency order ---------------------------------------------------
Invoke-Step -Name 'Generate synthetic corpus' -ScriptPath 'scripts/generate_corpus.ps1'
Invoke-Step -Name 'Ensure Search private Blob access' -ScriptPath 'scripts/ensure_search_blob_private_link.ps1'
Invoke-Step -Name 'Upload corpus to blob storage' -ScriptPath 'scripts/upload_corpus.ps1'
Invoke-Step -Name 'Create Blob knowledge source and knowledge base' -ScriptPath 'scripts/setup_search.ps1'
Invoke-Step -Name 'Register specialist agents' -ScriptPath 'scripts/register_agents.ps1'

Write-Host ''
Write-Host 'Post-provision setup complete.' -ForegroundColor Green
Write-Host ''
Write-Host 'Open the project in the Microsoft Foundry portal:' -ForegroundColor Cyan
Write-Host ("  {0}" -f $env:AZURE_AI_PROJECT_ENDPOINT)
Write-Host ''
