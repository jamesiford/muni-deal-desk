targetScope = 'resourceGroup'

@description('Microsoft Foundry account name.')
param accountName string

@description('Microsoft Foundry project name.')
param projectName string

@description('Display name for the project.')
param projectDisplayName string

@description('Description for the project.')
param projectDescription string

@description('Azure region.')
param location string

@description('Model deployments to create.')
param modelDeployments array

@description('Azure AI Search resource ID for the project connection.')
param searchServiceId string

@description('Azure AI Search endpoint for the project connection.')
param searchServiceEndpoint string

@description('Azure AI Search service name, used as the connection name.')
param searchServiceName string

@description('Storage account resource ID for the project connection.')
param storageAccountId string

@description('Storage blob endpoint for the project connection.')
param storageBlobEndpoint string

@description('Storage account name, used as the connection name.')
param storageAccountName string

@description('Application Insights resource ID for tracing.')
param applicationInsightsId string

@description('Application Insights connection string.')
@secure()
param applicationInsightsConnectionString string

@description('Tags applied to all resources.')
param tags object

#disable-next-line BCP036
resource account 'Microsoft.CognitiveServices/accounts@2025-04-01-preview' = {
  name: accountName
  location: location
  kind: 'AIServices'
  identity: {
    type: 'SystemAssigned'
  }
  sku: {
    name: 'S0'
  }
  tags: tags
  properties: {
    allowProjectManagement: true
    customSubDomainName: accountName
    // Entra authentication only. Combined with public network access this keeps
    // access identity-controlled rather than key-controlled. See ADR-0003.
    disableLocalAuth: true
    publicNetworkAccess: 'Enabled'
  }
}

// Deployed serially. Concurrent deployment writes against one account conflict, which
// surfaces as an intermittent provisioning failure rather than a clear error.
@batchSize(1)
#disable-next-line BCP081
resource deployments 'Microsoft.CognitiveServices/accounts/deployments@2025-04-01-preview' = [
  for deployment in modelDeployments: {
    parent: account
    name: deployment.name
    sku: {
      name: deployment.skuName
      capacity: deployment.capacity
    }
    properties: {
      model: {
        format: deployment.format
        name: deployment.modelName
        version: deployment.version
      }
    }
  }
]

resource appInsightsConnection 'Microsoft.CognitiveServices/accounts/connections@2025-04-01-preview' = {
  parent: account
  name: 'appinsights'
  properties: {
    authType: 'ApiKey'
    category: 'AppInsights'
    credentials: {
      key: applicationInsightsConnectionString
    }
    isSharedToAll: true
    metadata: {
      ApiType: 'Azure'
      ResourceId: applicationInsightsId
    }
    target: applicationInsightsId
  }
}

resource project 'Microsoft.CognitiveServices/accounts/projects@2025-04-01-preview' = {
  parent: account
  name: projectName
  location: location
  tags: tags
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    description: projectDescription
    displayName: projectDisplayName
  }
  // Project creation and model deployment are both write operations against the same
  // account. Without an explicit dependency Bicep runs them concurrently and the
  // project fails with RequestConflict, because the account is still settling.
  dependsOn: [
    deployments
  ]

  resource searchConnection 'connections@2025-04-01-preview' = {
    name: searchServiceName
    properties: {
      authType: 'AAD'
      category: 'CognitiveSearch'
      metadata: {
        ApiType: 'Azure'
        ResourceId: searchServiceId
        location: location
      }
      target: searchServiceEndpoint
    }
  }

  resource storageConnection 'connections@2025-04-01-preview' = {
    name: storageAccountName
    properties: {
      authType: 'AAD'
      category: 'AzureStorageAccount'
      metadata: {
        ApiType: 'Azure'
        ResourceId: storageAccountId
        location: location
      }
      target: storageBlobEndpoint
    }
  }
}

output accountId string = account.id
output accountName string = account.name
output accountEndpoint string = account.properties.endpoint
output projectName string = project.name
output projectPrincipalId string = project.identity.principalId
output projectEndpoint string = 'https://${account.name}.services.ai.azure.com/api/projects/${project.name}'
output searchConnectionName string = project::searchConnection.name
output storageConnectionName string = project::storageConnection.name
