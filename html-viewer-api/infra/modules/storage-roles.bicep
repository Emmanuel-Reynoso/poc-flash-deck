@description('Grants a principal data-plane roles on a storage account.')
param storageAccountName string
param principalId string
param roleDefinitionIds array

resource account 'Microsoft.Storage/storageAccounts@2023-05-01' existing = {
  name: storageAccountName
}

resource assignments 'Microsoft.Authorization/roleAssignments@2022-04-01' = [
  for roleId in roleDefinitionIds: {
    name: guid(account.id, principalId, roleId)
    scope: account
    properties: {
      principalId: principalId
      principalType: 'ServicePrincipal'
      roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleId)
    }
  }
]
