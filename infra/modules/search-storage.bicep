targetScope = 'resourceGroup'

@description('Azure AI Search service name.')
param searchServiceName string

@description('Storage account name for the synthetic corpus.')
param storageAccountName string

@description('Blob container holding corpus documents.')
param corpusContainerName string

@description('Azure region.')
param location string

@description('Tags applied to all resources.')
param tags object

// Standard tier is required for semantic ranking, which the agentic retrieval path in
// the knowledge base depends on.
resource searchService 'Microsoft.Search/searchServices@2024-06-01-preview' = {
  name: searchServiceName
  location: location
  tags: tags
  identity: {
    type: 'SystemAssigned'
  }
  sku: {
    name: 'standard'
  }
  properties: {
    authOptions: {
      aadOrApiKey: {
        aadAuthFailureMode: 'http401WithBearerChallenge'
      }
    }
    disableLocalAuth: false
    hostingMode: 'default'
    partitionCount: 1
    replicaCount: 1
    publicNetworkAccess: 'enabled'
    semanticSearch: 'standard'
  }
}

resource storageAccount 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: storageAccountName
  location: location
  kind: 'StorageV2'
  sku: {
    name: 'Standard_LRS'
  }
  tags: tags
  properties: {
    allowBlobPublicAccess: false
    // Entra authentication only. No account keys exist to be leaked or rotated.
    allowSharedKeyAccess: false
    minimumTlsVersion: 'TLS1_2'
    publicNetworkAccess: 'Enabled'
    supportsHttpsTrafficOnly: true
  }
}

resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2023-05-01' = {
  parent: storageAccount
  name: 'default'
}

resource corpusContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  parent: blobService
  name: corpusContainerName
  properties: {
    publicAccess: 'None'
  }
}

output searchServiceId string = searchService.id
output searchServiceName string = searchService.name
output searchServiceEndpoint string = 'https://${searchService.name}.search.windows.net'
output searchPrincipalId string = searchService.identity.principalId
output storageAccountId string = storageAccount.id
output storageAccountName string = storageAccount.name
output storageBlobEndpoint string = storageAccount.properties.primaryEndpoints.blob
output corpusContainerName string = corpusContainer.name
