@description('Static Web App name.')
param name string

@description('Static Web Apps is only offered in a few regions.')
param location string
param tags object = {}

@description('Client id of the Entra ID app registration used for sign-in.')
param entraClientId string

@secure()
@description('Client secret of that app registration.')
param entraClientSecret string

// Standard is required for custom Entra ID auth (single tenant) and linked backends.
resource site 'Microsoft.Web/staticSites@2024-04-01' = {
  name: name
  location: location
  tags: tags
  sku: {
    name: 'Standard'
    tier: 'Standard'
  }
  properties: {
    stagingEnvironmentPolicy: 'Enabled'
    allowConfigFileUpdates: true
  }
}

// Read by staticwebapp.config.json (clientIdSettingName / clientSecretSettingName).
resource settings 'Microsoft.Web/staticSites/config@2024-04-01' = {
  parent: site
  name: 'appsettings'
  properties: {
    AZURE_CLIENT_ID: entraClientId
    AZURE_CLIENT_SECRET: entraClientSecret
  }
}

output name string = site.name
output id string = site.id
output defaultHostname string = site.properties.defaultHostname
