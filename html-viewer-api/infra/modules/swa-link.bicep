@description('Links the Function App as the /api backend of the Static Web App.')
param staticWebAppName string
param functionAppId string
param functionAppLocation string

resource site 'Microsoft.Web/staticSites@2024-04-01' existing = {
  name: staticWebAppName
}

// Linking also locks the Function App down so only the Static Web App can call
// it. That is what makes trusting the x-ms-client-principal header safe.
resource backend 'Microsoft.Web/staticSites/linkedBackends@2024-04-01' = {
  parent: site
  name: 'api'
  properties: {
    backendResourceId: functionAppId
    region: functionAppLocation
  }
}
