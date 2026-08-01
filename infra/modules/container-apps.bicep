targetScope = 'resourceGroup'

@description('Container registry name.')
param registryName string

@description('Container Apps managed environment name.')
param environmentName string

@description('User-assigned managed identity name for container workloads.')
param identityName string

@description('Log Analytics workspace ID for container console and system logs.')
param logAnalyticsId string

@description('Azure region.')
param location string

@description('Tags applied to all resources.')
param tags object

// Workloads authenticate to the registry with a managed identity, so the admin user
// stays disabled and no registry credentials exist to be stored or rotated.
resource registry 'Microsoft.ContainerRegistry/registries@2023-11-01-preview' = {
  name: registryName
  location: location
  tags: tags
  sku: {
    name: 'Basic'
  }
  properties: {
    adminUserEnabled: false
    anonymousPullEnabled: false
    publicNetworkAccess: 'Enabled'
  }
}

// A single user-assigned identity is shared by the MCP server and the orchestrator.
// They are separate workloads but the same trust boundary: both are our code calling
// the same downstream services with the same rights.
resource workloadIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: identityName
  location: location
  tags: tags
}

resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2023-09-01' existing = {
  name: last(split(logAnalyticsId, '/'))
}

resource managedEnvironment 'Microsoft.App/managedEnvironments@2025-01-01' = {
  name: environmentName
  location: location
  tags: tags
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalytics.properties.customerId
        sharedKey: logAnalytics.listKeys().primarySharedKey
      }
    }
    zoneRedundant: false
  }
}

var acrPullRoleId = '7f951dda-4ed3-4680-a7ca-43fe172d538d'

resource acrPull 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: registry
  name: guid(registry.id, workloadIdentity.id, acrPullRoleId)
  properties: {
    principalId: workloadIdentity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', acrPullRoleId)
  }
}

output registryName string = registry.name
output registryLoginServer string = registry.properties.loginServer
output environmentId string = managedEnvironment.id
output environmentName string = managedEnvironment.name
output environmentDefaultDomain string = managedEnvironment.properties.defaultDomain
output workloadIdentityId string = workloadIdentity.id
output workloadIdentityClientId string = workloadIdentity.properties.clientId
output workloadIdentityPrincipalId string = workloadIdentity.properties.principalId
