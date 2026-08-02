#Requires -Version 7.0
<#
.SYNOPSIS
    Verifies that Foundry evaluations can process rows through private storage.
#>
$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot

Push-Location $repoRoot
try {
    python -m scripts.verify_foundry_evaluation
    if ($LASTEXITCODE -ne 0) {
        throw "Foundry evaluation storage verification failed with exit code $LASTEXITCODE."
    }
}
finally {
    Pop-Location
}
