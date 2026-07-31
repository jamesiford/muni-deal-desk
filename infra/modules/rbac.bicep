targetScope = 'resourceGroup'

@description('Foundry project system-assigned managed identity principal ID.')
param projectPrincipalId string

@description('Azure AI Search system-assigned managed identity principal ID.')
param searchPrincipalId string

@description('Object ID of the developer or service principal running the deployment.')
param developerPrincipalId string

@description('Principal type of the developer identity: User or ServicePrincipal.')
@allowed(['User', 'ServicePrincipal'])
param developerPrincipalType string

@description('Foundry account name, used to scope role assignments.')
param accountName string

@description('Azure AI Search service name, used to scope role assignments.')
param searchServiceName string

@description('Storage account name, used to scope role assignments.')
param storageAccountName string

// Built-in data-plane roles. Control-plane roles such as Owner and Contributor are
// deliberately absent: no runtime identity in this solution needs to manage resources.
var roles = {
  searchIndexDataContributor: '8ebe5a00-799e-43f5-93ac-243d3dce84a7'
  searchIndexDataReader: '1407120a-92aa-4202-b7e9-c0e197c71c8f'
  searchServiceContributor: '7ca78c08-252a-4471-8644-bb5ff32d4ba0'
  storageBlobDataContributor: 'ba92f5b4-2d11-453d-a403-e96b0029c9fe'
  storageBlobDataReader: '2a2b9908-6ea1-4ae2-8e65-a410df84e7d1'
  cognitiveServicesUser: 'a97b65f3-24c7-4388-baec-2e87135dc908'
  cognitiveServicesOpenAIUser: '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd'
  azureAIDeveloper: '64702f94-c441-49e6-a78b-ef80e0188fee'
}

resource account 'Microsoft.CognitiveServices/accounts@2025-04-01-preview' existing = {
  name: accountName
}

resource searchService 'Microsoft.Search/searchServices@2024-06-01-preview' existing = {
  name: searchServiceName
}

resource storageAccount 'Microsoft.Storage/storageAccounts@2023-05-01' existing = {
  name: storageAccountName
}

// The Foundry project reads and writes indexes so agents can query the knowledge base.
resource projectSearchContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: searchService
  name: guid(searchService.id, projectPrincipalId, roles.searchIndexDataContributor)
  properties: {
    principalId: projectPrincipalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions',
      roles.searchIndexDataContributor
    )
  }
}

resource projectSearchServiceContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: searchService
  name: guid(searchService.id, projectPrincipalId, roles.searchServiceContributor)
  properties: {
    principalId: projectPrincipalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions',
      roles.searchServiceContributor
    )
  }
}

resource projectStorageReader 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: storageAccount
  name: guid(storageAccount.id, projectPrincipalId, roles.storageBlobDataReader)
  properties: {
    principalId: projectPrincipalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions',
      roles.storageBlobDataReader
    )
  }
}

// Search reads corpus blobs during indexing.
resource searchStorageReader 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: storageAccount
  name: guid(storageAccount.id, searchPrincipalId, roles.storageBlobDataReader)
  properties: {
    principalId: searchPrincipalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions',
      roles.storageBlobDataReader
    )
  }
}

// Search calls the embedding deployment for integrated vectorization.
resource searchOpenAIUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: account
  name: guid(account.id, searchPrincipalId, roles.cognitiveServicesOpenAIUser)
  properties: {
    principalId: searchPrincipalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions',
      roles.cognitiveServicesOpenAIUser
    )
  }
}

// The developer identity runs the postup data-plane scripts: uploading the corpus,
// creating the index and registering agents. Local authentication is disabled on the
// Foundry account, so these data-plane roles are the only access path.
resource developerAIDeveloper 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: account
  name: guid(account.id, developerPrincipalId, roles.azureAIDeveloper)
  properties: {
    principalId: developerPrincipalId
    principalType: developerPrincipalType
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions',
      roles.azureAIDeveloper
    )
  }
}

resource developerCognitiveUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: account
  name: guid(account.id, developerPrincipalId, roles.cognitiveServicesUser)
  properties: {
    principalId: developerPrincipalId
    principalType: developerPrincipalType
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions',
      roles.cognitiveServicesUser
    )
  }
}

resource developerOpenAIUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: account
  name: guid(account.id, developerPrincipalId, roles.cognitiveServicesOpenAIUser)
  properties: {
    principalId: developerPrincipalId
    principalType: developerPrincipalType
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions',
      roles.cognitiveServicesOpenAIUser
    )
  }
}

resource developerSearchContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: searchService
  name: guid(searchService.id, developerPrincipalId, roles.searchIndexDataContributor)
  properties: {
    principalId: developerPrincipalId
    principalType: developerPrincipalType
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions',
      roles.searchIndexDataContributor
    )
  }
}

resource developerSearchServiceContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: searchService
  name: guid(searchService.id, developerPrincipalId, roles.searchServiceContributor)
  properties: {
    principalId: developerPrincipalId
    principalType: developerPrincipalType
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions',
      roles.searchServiceContributor
    )
  }
}

resource developerStorageContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: storageAccount
  name: guid(storageAccount.id, developerPrincipalId, roles.storageBlobDataContributor)
  properties: {
    principalId: developerPrincipalId
    principalType: developerPrincipalType
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions',
      roles.storageBlobDataContributor
    )
  }
}
