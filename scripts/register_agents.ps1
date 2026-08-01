#Requires -Version 7.0
<#
.SYNOPSIS
    Registers and smoke-tests the three Foundry prompt specialists.
#>
$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot

Push-Location $repoRoot
try {
    $output = python -m scripts.register_agents
    if ($LASTEXITCODE -ne 0) {
        throw 'Prompt-agent registration or smoke validation failed.'
    }
    $output | Write-Host
    $marker = $output | Where-Object { $_ -like 'AZD_AGENT_VERSIONS=*' } | Select-Object -Last 1
    if (-not $marker) {
        throw 'Prompt-agent registration did not report promoted versions.'
    }
    $versions = ($marker -replace '^AZD_AGENT_VERSIONS=', '') | ConvertFrom-Json
    azd env set RESEARCH_AGENT_VERSION $versions.'municipal-deal-research' | Out-Null
    azd env set ANALYST_AGENT_VERSION $versions.'municipal-deal-analyst' | Out-Null
    azd env set COMPLIANCE_AGENT_VERSION $versions.'municipal-deal-compliance' | Out-Null
}
finally {
    Pop-Location
}
