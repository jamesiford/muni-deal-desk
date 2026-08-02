targetScope = 'resourceGroup'

@description('Foundry account system-assigned managed identity principal ID.')
param accountPrincipalId string

@description('Foundry project system-assigned managed identity principal ID.')
param projectPrincipalId string

@description('Azure AI Search system-assigned managed identity principal ID.')
param searchPrincipalId string

@description('User-assigned managed identity used by the MCP server and orchestrator.')
param workloadPrincipalId string

@description('Object ID of the developer or service principal running the deployment.')
param developerPrincipalId string

@description('Principal type of the developer identity: User or ServicePrincipal.')
@allowed(['User', 'ServicePrincipal'])
param developerPrincipalType string

@description('Foundry account name, used to scope role assignments.')
param accountName string

@description('Foundry project name, used to scope developer data-plane access.')
param projectName string

@description('Azure AI Search service name, used to scope role assignments.')
param searchServiceName string

@description('Storage account name, used to scope role assignments.')
param storageAccountName string

@description('Application Insights name, used to scope telemetry ingestion.')
param applicationInsightsName string

// Built-in data-plane roles. Control-plane roles such as Owner and Contributor are
// deliberately absent: no runtime identity in this solution needs to manage resources.
var roles = {
  searchIndexDataContributor: '8ebe5a00-799e-43f5-93ac-243d3dce84a7'
  searchServiceContributor: '7ca78c08-252a-4471-8644-bb5ff32d4ba0'
  storageBlobDataContributor: 'ba92f5b4-2d11-453d-a403-e96b0029c9fe'
  storageBlobDataOwner: 'b7e6dc6d-f1e8-4753-8033-0f276bb0955b'
  storageBlobDataReader: '2a2b9908-6ea1-4ae2-8e65-a410df84e7d1'
  cognitiveServicesUser: 'a97b65f3-24c7-4388-baec-2e87135dc908'
  cognitiveServicesOpenAIUser: '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd'
  foundryUser: '53ca6127-db72-4b80-b1b0-d745d6d5456d'
  monitoringMetricsPublisher: '3913510d-42f4-4e42-8a64-420c390055eb'
}

resource account 'Microsoft.CognitiveServices/accounts@2025-04-01-preview' existing = {
  name: accountName
}

resource project 'Microsoft.CognitiveServices/accounts/projects@2025-04-01-preview' existing = {
  parent: account
  name: projectName
}

// Evaluation and hosted-agent workloads execute as the project identity and need the
// current Foundry data-plane role on their parent account.
resource projectFoundryUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: account
  name: guid(account.id, projectPrincipalId, roles.foundryUser)
  properties: {
    principalId: projectPrincipalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions',
      roles.foundryUser
    )
  }
}

resource searchService 'Microsoft.Search/searchServices@2024-06-01-preview' existing = {
  name: searchServiceName
}

resource storageAccount 'Microsoft.Storage/storageAccounts@2023-05-01' existing = {
  name: storageAccountName
}

resource applicationInsights 'Microsoft.Insights/components@2020-02-02' existing = {
  name: applicationInsightsName
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

// Foundry evaluations stage datasets and result artifacts through the connected
// storage account, so the project identity needs write access as well as read access.
resource projectStorageOwner 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: storageAccount
  name: guid(storageAccount.id, projectPrincipalId, roles.storageBlobDataOwner)
  properties: {
    principalId: projectPrincipalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions',
      roles.storageBlobDataOwner
    )
  }
}

// The evaluation service resolves uploaded datasets through the account-level
// Asset Store, which authenticates with the parent Foundry account identity.
resource accountStorageOwner 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: storageAccount
  name: guid(storageAccount.id, accountPrincipalId, roles.storageBlobDataOwner)
  properties: {
    principalId: accountPrincipalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions',
      roles.storageBlobDataOwner
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

// Blob knowledge-source ingestion and knowledge-base query planning use the broader
// Cognitive Services data-plane role documented for Foundry IQ model access.
resource searchCognitiveServicesUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: account
  name: guid(account.id, searchPrincipalId, roles.cognitiveServicesUser)
  properties: {
    principalId: searchPrincipalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions',
      roles.cognitiveServicesUser
    )
  }
}

resource workloadTelemetryPublisher 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: applicationInsights
  name: guid(applicationInsights.id, workloadPrincipalId, roles.monitoringMetricsPublisher)
  properties: {
    principalId: workloadPrincipalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions',
      roles.monitoringMetricsPublisher
    )
  }
}

// The developer identity runs the postup data-plane scripts: uploading the corpus,
// creating the index and registering agents. Local authentication is disabled on the
// Foundry account, so these data-plane roles are the only access path.
resource developerFoundryUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: project
  name: guid(project.id, developerPrincipalId, roles.foundryUser)
  properties: {
    principalId: developerPrincipalId
    principalType: developerPrincipalType
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions',
      roles.foundryUser
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
