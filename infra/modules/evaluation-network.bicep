targetScope = 'resourceGroup'

@description('Azure region shared by Foundry and its injected virtual network.')
param location string

@description('Virtual network name.')
param vnetName string

@description('Private storage account used by Foundry evaluations and the public corpus.')
param storageAccountName string

@description('Tags applied to network resources.')
param tags object

resource vnet 'Microsoft.Network/virtualNetworks@2024-05-01' = {
  name: vnetName
  location: location
  tags: tags
  properties: {
    addressSpace: {
      addressPrefixes: [
        '172.20.0.0/16'
      ]
    }
  }
}

resource agentSubnet 'Microsoft.Network/virtualNetworks/subnets@2024-05-01' = {
  parent: vnet
  name: 'snet-foundry-agent'
  properties: {
    addressPrefix: '172.20.0.0/24'
    delegations: [
      {
        name: 'foundry-agent-injection'
        properties: {
          serviceName: 'Microsoft.App/environments'
        }
      }
    ]
  }
}

resource privateEndpointSubnet 'Microsoft.Network/virtualNetworks/subnets@2024-05-01' = {
  parent: vnet
  name: 'snet-private-endpoints'
  properties: {
    addressPrefix: '172.20.1.0/24'
    privateEndpointNetworkPolicies: 'Disabled'
  }
}

resource uploaderSubnet 'Microsoft.Network/virtualNetworks/subnets@2024-05-01' = {
  parent: vnet
  name: 'snet-corpus-uploader'
  properties: {
    addressPrefix: '172.20.2.0/24'
    delegations: [
      {
        name: 'container-instances'
        properties: {
          serviceName: 'Microsoft.ContainerInstance/containerGroups'
        }
      }
    ]
  }
}

resource uploaderIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: 'id-corpus-uploader-${uniqueString(resourceGroup().id)}'
  location: location
  tags: tags
}

resource storageAccount 'Microsoft.Storage/storageAccounts@2023-05-01' existing = {
  name: storageAccountName
}

var storageBlobDataContributor = 'ba92f5b4-2d11-453d-a403-e96b0029c9fe'

resource uploaderStorageContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: storageAccount
  name: guid(storageAccount.id, uploaderIdentity.id, storageBlobDataContributor)
  properties: {
    principalId: uploaderIdentity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions',
      storageBlobDataContributor
    )
  }
}

resource storagePrivateEndpoint 'Microsoft.Network/privateEndpoints@2024-05-01' = {
  name: 'pe-${storageAccountName}-blob'
  location: location
  tags: tags
  properties: {
    subnet: {
      id: privateEndpointSubnet.id
    }
    privateLinkServiceConnections: [
      {
        name: 'blob'
        properties: {
          privateLinkServiceId: storageAccount.id
          groupIds: [
            'blob'
          ]
        }
      }
    ]
  }
}

resource blobPrivateDnsZone 'Microsoft.Network/privateDnsZones@2024-06-01' = {
  name: 'privatelink.blob.${environment().suffixes.storage}'
  location: 'global'
  tags: tags
}

resource blobPrivateDnsLink 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2024-06-01' = {
  parent: blobPrivateDnsZone
  name: '${vnetName}-link'
  location: 'global'
  properties: {
    registrationEnabled: false
    virtualNetwork: {
      id: vnet.id
    }
  }
}

resource storagePrivateDnsZoneGroup 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2024-05-01' = {
  parent: storagePrivateEndpoint
  name: 'blob'
  properties: {
    privateDnsZoneConfigs: [
      {
        name: 'blob'
        properties: {
          privateDnsZoneId: blobPrivateDnsZone.id
        }
      }
    ]
  }
}

output agentSubnetId string = agentSubnet.id
output privateEndpointId string = storagePrivateEndpoint.id
output uploaderIdentityClientId string = uploaderIdentity.properties.clientId
output uploaderIdentityId string = uploaderIdentity.id
output uploaderIdentityPrincipalId string = uploaderIdentity.properties.principalId
output uploaderSubnetName string = uploaderSubnet.name
output vnetId string = vnet.id
output vnetName string = vnet.name
