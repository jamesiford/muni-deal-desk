#Requires -Version 7.0
<#
.SYNOPSIS
    Generates the synthetic Municipal Deal Desk PDF corpus and manifest.
#>
$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent $PSScriptRoot
Push-Location $repoRoot
try {
    python -m src.corpus.generate @args
    if ($LASTEXITCODE -ne 0) {
        throw "Corpus generation failed with exit code $LASTEXITCODE."
    }
}
finally {
    Pop-Location
}