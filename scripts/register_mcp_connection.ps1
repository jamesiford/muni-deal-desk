#Requires -Version 7.0
[CmdletBinding()]
param(
    [string] $Environment = 'demo-vnet',
    [string] $ConnectionName = 'muni-deal-desk-mcp',
    [string] $Endpoint,
    [string] $ProjectEndpoint
)

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$env:AZURE_DEV_USER_AGENT = 'microsoft_foundry_skill'

Push-Location $repoRoot
try {
    if (-not $Endpoint) {
        $Endpoint = azd env get-value MCP_ENDPOINT --environment $Environment
    }
    if (-not $ProjectEndpoint) {
        $ProjectEndpoint = azd env get-value AZURE_AI_PROJECT_ENDPOINT --environment $Environment
    }
    if (-not $Endpoint) {
        throw 'MCP_ENDPOINT is missing. Deploy the MCP service before registering its connection.'
    }
    if (-not $ProjectEndpoint) {
        throw 'AZURE_AI_PROJECT_ENDPOINT is missing from the selected azd environment.'
    }

    $currentJson = azd ai connection show $ConnectionName `
        --project-endpoint $ProjectEndpoint `
        --output json `
        --no-prompt 2>$null
    $current = if ($LASTEXITCODE -eq 0) { $currentJson | ConvertFrom-Json } else { $null }
    $currentTarget = if ($current.target) { $current.target } else { $current.properties.target }

    if ($currentTarget -eq $Endpoint) {
        Write-Host "Connection $ConnectionName already targets $Endpoint" -ForegroundColor DarkGray
    }
    else {
        azd ai connection create $ConnectionName `
            --project-endpoint $ProjectEndpoint `
            --kind remote-tool `
            --target $Endpoint `
            --auth-type none `
            --force `
            --no-prompt
        if ($LASTEXITCODE -ne 0) {
            throw 'Foundry MCP connection registration failed.'
        }
    }

    $statusEndpoint = $Endpoint -replace '/mcp$', '/status'
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

    python -m scripts.smoke_mcp $Endpoint
    if ($LASTEXITCODE -ne 0) {
        throw 'The connection target did not expose the expected MCP tools.'
    }

    azd ai connection show $ConnectionName `
        --project-endpoint $ProjectEndpoint `
        --output table `
        --no-prompt
}
finally {
    Pop-Location
}