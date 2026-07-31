targetScope = 'subscription'

metadata description = '''
Municipal Deal Desk: a Microsoft Foundry demonstration environment.

Deploys with public network access and Entra authentication. This is a demonstration
asset, not a production landing zone pattern. See docs/decisions/0003.
'''

@minLength(1)
@maxLength(64)
@description('Environment name. Used to derive resource names and azd tagging.')
param environmentName string

@minLength(1)
@description('Azure region. Must support all four model deployments.')
param location string

@description('Object ID of the developer or service principal running the deployment.')
param principalId string

@description('Principal type of the deploying identity.')
@allowed(['User', 'ServicePrincipal'])
param principalType string = 'User'

@description('''
Model deployments.

Four deployments are deliberate. The session demonstrates cost attribution across a
model portfolio, which is not visible with a single deployment.
''')
param modelDeployments array = [
  {
    // Bulk document extraction. The cheap tier in the cost comparison.
    name: 'gpt-5.4-mini'
    modelName: 'gpt-5.4-mini'
    version: '2026-03-17'
    format: 'OpenAI'
    skuName: 'GlobalStandard'
    capacity: 100
  }
  {
    // Comparables synthesis and drafting. The reasoning tier.
    name: 'gpt-5.5'
    modelName: 'gpt-5.5'
    version: '2026-04-24'
    format: 'OpenAI'
    skuName: 'GlobalStandard'
    capacity: 100
  }
  {
    // Per-request model selection. Demonstrates model choice as a runtime decision.
    name: 'model-router'
    modelName: 'model-router'
    version: '2025-11-18'
    format: 'OpenAI'
    skuName: 'GlobalStandard'
    capacity: 100
  }
  {
    // Knowledge base embeddings for integrated vectorization.
    name: 'text-embedding-3-large'
    modelName: 'text-embedding-3-large'
    version: '1'
    format: 'OpenAI'
    skuName: 'Standard'
    capacity: 50
  }
]

var abbrs = loadJsonContent('abbreviations.json')
var resourceToken = toLower(uniqueString(subscription().id, environmentName, location))
var tags = {
  'azd-env-name': environmentName
  solution: 'muni-deal-desk'
  purpose: 'demonstration'
}

resource resourceGroup 'Microsoft.Resources/resourceGroups@2021-04-01' = {
  name: '${abbrs.resourcesResourceGroups}muni-deal-desk-${environmentName}'
  location: location
  tags: tags
}

module monitoring 'modules/monitoring.bicep' = {
  scope: resourceGroup
  name: 'monitoring'
  params: {
    location: location
    logAnalyticsName: '${abbrs.operationalInsightsWorkspaces}${resourceToken}'
    applicationInsightsName: '${abbrs.insightsComponents}${resourceToken}'
    tags: tags
  }
}

module searchStorage 'modules/search-storage.bicep' = {
  scope: resourceGroup
  name: 'search-storage'
  params: {
    location: location
    searchServiceName: '${abbrs.searchSearchServices}${resourceToken}'
    storageAccountName: '${abbrs.storageStorageAccounts}${resourceToken}'
    corpusContainerName: 'corpus'
    tags: tags
  }
}

module foundry 'modules/foundry.bicep' = {
  scope: resourceGroup
  name: 'foundry'
  params: {
    location: location
    accountName: '${abbrs.cognitiveServicesAccounts}${resourceToken}'
    projectName: 'muni-deal-desk'
    projectDisplayName: 'Municipal Deal Desk'
    projectDescription: 'New-issue intelligence for a public finance desk. Synthetic data.'
    modelDeployments: modelDeployments
    searchServiceId: searchStorage.outputs.searchServiceId
    searchServiceEndpoint: searchStorage.outputs.searchServiceEndpoint
    searchServiceName: searchStorage.outputs.searchServiceName
    storageAccountId: searchStorage.outputs.storageAccountId
    storageBlobEndpoint: searchStorage.outputs.storageBlobEndpoint
    storageAccountName: searchStorage.outputs.storageAccountName
    applicationInsightsId: monitoring.outputs.applicationInsightsId
    applicationInsightsConnectionString: monitoring.outputs.applicationInsightsConnectionString
    tags: tags
  }
}

module rbac 'modules/rbac.bicep' = {
  scope: resourceGroup
  name: 'rbac'
  params: {
    projectPrincipalId: foundry.outputs.projectPrincipalId
    searchPrincipalId: searchStorage.outputs.searchPrincipalId
    developerPrincipalId: principalId
    developerPrincipalType: principalType
    accountName: foundry.outputs.accountName
    searchServiceName: searchStorage.outputs.searchServiceName
    storageAccountName: searchStorage.outputs.storageAccountName
  }
}

// Consumed by the postup hooks that upload the corpus, build the index and register
// agents, and written into the azd environment for local development.
output AZURE_LOCATION string = location
output AZURE_RESOURCE_GROUP string = resourceGroup.name
output AZURE_AI_ACCOUNT_NAME string = foundry.outputs.accountName
output AZURE_AI_ACCOUNT_ENDPOINT string = foundry.outputs.accountEndpoint
output AZURE_AI_PROJECT_NAME string = foundry.outputs.projectName
output AZURE_AI_PROJECT_ENDPOINT string = foundry.outputs.projectEndpoint
output AZURE_AI_EXTRACTION_DEPLOYMENT string = modelDeployments[0].name
output AZURE_AI_REASONING_DEPLOYMENT string = modelDeployments[1].name
output AZURE_AI_ROUTER_DEPLOYMENT string = modelDeployments[2].name
output AZURE_AI_EMBEDDING_DEPLOYMENT string = modelDeployments[3].name
output AZURE_SEARCH_ENDPOINT string = searchStorage.outputs.searchServiceEndpoint
output AZURE_SEARCH_SERVICE_NAME string = searchStorage.outputs.searchServiceName
output AZURE_SEARCH_CONNECTION_NAME string = foundry.outputs.searchConnectionName
output AZURE_STORAGE_ACCOUNT_NAME string = searchStorage.outputs.storageAccountName
output AZURE_STORAGE_BLOB_ENDPOINT string = searchStorage.outputs.storageBlobEndpoint
output AZURE_STORAGE_CORPUS_CONTAINER string = searchStorage.outputs.corpusContainerName
output APPLICATIONINSIGHTS_CONNECTION_STRING string = monitoring.outputs.applicationInsightsConnectionString
