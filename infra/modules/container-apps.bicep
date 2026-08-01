targetScope = 'resourceGroup'

@description('Container registry name.')
param registryName string

@description('Container Apps managed environment name.')
param environmentName string

@description('User-assigned managed identity name for container workloads.')
param identityName string

@description('MCP server Container App name.')
param mcpAppName string

@description('True when the MCP Container App already exists.')
param mcpResourceExists bool

@description('Log Analytics workspace ID for container console and system logs.')
param logAnalyticsId string

param accountEndpoint string
param projectEndpoint string
param extractionDeployment string
param reasoningDeployment string
param routerDeployment string
param embeddingDeployment string
param searchEndpoint string
param searchConnectionName string
param storageAccountName string
param storageBlobEndpoint string
param corpusContainerName string
param applicationInsightsConnectionString string

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

// The custom MCP server uses a dedicated user-assigned identity. Foundry Hosted Agents
// receive a separate per-agent identity from the platform.
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

resource existingMcpApp 'Microsoft.App/containerApps@2025-01-01' existing = if (mcpResourceExists) {
  name: mcpAppName
}

var bootstrapImage = 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest'
var mcpHostName = '${mcpAppName}.${managedEnvironment.properties.defaultDomain}'

resource mcpApp 'Microsoft.App/containerApps@2025-01-01' = if (!mcpResourceExists) {
  name: mcpAppName
  location: location
  tags: union(tags, {
    'azd-service-name': 'mcp'
  })
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${workloadIdentity.id}': {}
    }
  }
  properties: {
    environmentId: managedEnvironment.id
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: {
        external: true
        allowInsecure: false
        targetPort: 8000
        transport: 'auto'
      }
      registries: [
        {
          server: registry.properties.loginServer
          identity: workloadIdentity.id
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'mcp'
          image: bootstrapImage
          env: [
            { name: 'AZURE_CLIENT_ID', value: workloadIdentity.properties.clientId }
            { name: 'AZURE_AI_ACCOUNT_ENDPOINT', value: accountEndpoint }
            { name: 'AZURE_AI_PROJECT_ENDPOINT', value: projectEndpoint }
            { name: 'AZURE_AI_EXTRACTION_DEPLOYMENT', value: extractionDeployment }
            { name: 'AZURE_AI_REASONING_DEPLOYMENT', value: reasoningDeployment }
            { name: 'AZURE_AI_ROUTER_DEPLOYMENT', value: routerDeployment }
            { name: 'AZURE_AI_EMBEDDING_DEPLOYMENT', value: embeddingDeployment }
            { name: 'AZURE_SEARCH_ENDPOINT', value: searchEndpoint }
            { name: 'AZURE_SEARCH_CONNECTION_NAME', value: searchConnectionName }
            { name: 'AZURE_STORAGE_ACCOUNT_NAME', value: storageAccountName }
            { name: 'AZURE_STORAGE_BLOB_ENDPOINT', value: storageBlobEndpoint }
            { name: 'AZURE_STORAGE_CORPUS_CONTAINER', value: corpusContainerName }
            { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', value: applicationInsightsConnectionString }
            { name: 'MCP_ADAPTER_FACTORY', value: 'src.infrastructure.mcp.factory:create_manifest_adapters' }
            { name: 'MCP_ALLOWED_HOSTS', value: mcpHostName }
            { name: 'PORT', value: '8000' }
          ]
          resources: {
            cpu: json('0.5')
            memory: '1Gi'
          }
          probes: [
            {
              type: 'Liveness'
              httpGet: {
                path: '/status'
                port: 8000
                scheme: 'HTTP'
              }
              initialDelaySeconds: 10
              periodSeconds: 30
              timeoutSeconds: 5
              failureThreshold: 3
            }
            {
              type: 'Readiness'
              httpGet: {
                path: '/status'
                port: 8000
                scheme: 'HTTP'
              }
              initialDelaySeconds: 5
              periodSeconds: 10
              timeoutSeconds: 5
              failureThreshold: 3
            }
          ]
        }
      ]
      scale: {
        minReplicas: 1
        maxReplicas: 2
      }
    }
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
output mcpAppName string = mcpAppName
output mcpUri string = 'https://${mcpResourceExists ? existingMcpApp!.properties.configuration.ingress.fqdn : mcpApp!.properties.configuration.ingress.fqdn}'
