targetScope = 'resourceGroup'

@description('Foundry account name.')
param accountName string

@description('Foundry project name.')
param projectName string

@description('Deployed MCP streamable HTTP endpoint.')
param mcpEndpoint string

@description('Foundry IQ knowledge-base MCP endpoint.')
param knowledgeBaseEndpoint string

resource account 'Microsoft.CognitiveServices/accounts@2025-04-01-preview' existing = {
  name: accountName
}

resource project 'Microsoft.CognitiveServices/accounts/projects@2025-04-01-preview' existing = {
  parent: account
  name: projectName
}

resource mcpConnection 'Microsoft.CognitiveServices/accounts/projects/connections@2025-04-01-preview' = {
  parent: project
  name: 'muni-deal-desk-mcp'
  properties: {
    authType: 'None'
    category: 'RemoteTool'
    isSharedToAll: false
    metadata: {}
    target: mcpEndpoint
  }
}

resource knowledgeBaseConnection 'Microsoft.CognitiveServices/accounts/projects/connections@2025-04-01-preview' = {
  parent: project
  name: 'municipal-deal-foundry-iq'
  properties: {
    audience: 'https://search.azure.com/'
    #disable-next-line BCP036
    authType: 'ProjectManagedIdentity'
    category: 'RemoteTool'
    isSharedToAll: false
    metadata: {
      ApiType: 'Azure'
    }
    target: knowledgeBaseEndpoint
  }
}

output knowledgeBaseConnectionName string = knowledgeBaseConnection.name
output mcpConnectionName string = mcpConnection.name
