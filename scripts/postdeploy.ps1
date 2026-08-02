#Requires -Version 7.0
<#
.SYNOPSIS
    Validates deployed MCP and specialist agents after both services are live.
#>
$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot

Push-Location $repoRoot
try {
    $endpoint = azd env get-value MCP_ENDPOINT --environment $env:AZURE_ENV_NAME
    $statusEndpoint = $endpoint -replace '/mcp$', '/status'
    $status = $null
    $deadline = [DateTimeOffset]::UtcNow.AddMinutes(5)
    while ([DateTimeOffset]::UtcNow -lt $deadline) {
        try {
            $status = Invoke-RestMethod -Uri $statusEndpoint -TimeoutSec 10
            if ($status -eq 'ready') {
                break
            }
        }
        catch {
            Write-Verbose "MCP revision is not ready yet: $($_.Exception.Message)"
        }
        Start-Sleep -Seconds 5
    }
    if ($status -ne 'ready') {
        throw "MCP endpoint did not become ready within five minutes: $statusEndpoint"
    }

    python -m scripts.smoke_mcp $endpoint
    if ($LASTEXITCODE -ne 0) {
        throw 'The deployed MCP endpoint did not expose the expected tools.'
    }

    & (Join-Path $PSScriptRoot 'register_agents.ps1')
    if ($LASTEXITCODE -ne 0) {
        throw 'Post-deploy specialist smoke validation failed.'
    }
}
finally {
    Pop-Location
}
