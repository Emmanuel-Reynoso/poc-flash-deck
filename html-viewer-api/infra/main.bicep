targetScope = 'resourceGroup'

@minLength(3)
@maxLength(10)
@description('Short app name, letters and digits. Used in resource names.')
param appName string = 'htmlviewer'

@allowed(['dev', 'test', 'prod'])
param environmentName string = 'prod'

@description('Region for storage, Function App and monitoring.')
param location string = resourceGroup().location

@allowed(['centralus', 'eastus2', 'westus2', 'westeurope', 'eastasia'])
@description('Static Web Apps is available in a few regions only. Content is served from the global edge anyway.')
param staticWebAppLocation string = 'eastus2'

@description('Client id of the Entra ID app registration used for sign-in.')
param entraClientId string

@secure()
@description('Client secret of the Entra ID app registration.')
param entraClientSecret string

@description('Maximum size of an uploaded HTML file, in MB.')
param maxUploadMb int = 20

@description('Maximum lifetime of a public share link, in days.')
param shareMaxDays int = 30

@allowed(['Standard_LRS', 'Standard_ZRS', 'Standard_GRS', 'Standard_RAGRS'])
param dataStorageSku string = 'Standard_LRS'

@description('Extra origins allowed to upload to Blob Storage, e.g. a custom domain: ["https://html.contoso.com"].')
param extraAllowedOrigins array = []

param tags object = {}

var suffix = take(uniqueString(resourceGroup().id, appName, environmentName), 8)
var baseName = '${appName}-${environmentName}-${suffix}'
var compactApp = toLower(replace(appName, '-', ''))
var allTags = union({ app: appName, environment: environmentName }, tags)

// Built-in role ids
var storageBlobDataContributor = 'ba92f5b4-2d11-453d-a403-e96b0029c9fe'
var storageBlobDelegator = 'db58b8e5-c6ad-4a2a-8342-4190687cbf4a'
var storageTableDataContributor = '0a9a7e1f-b9d0-4cc4-a60d-0319b160aaa3'

module monitoring 'modules/monitoring.bicep' = {
  name: 'monitoring'
  params: {
    name: baseName
    location: location
    tags: allTags
  }
}

module web 'modules/static-web-app.bicep' = {
  name: 'web'
  params: {
    name: 'swa-${baseName}'
    location: staticWebAppLocation
    tags: allTags
    entraClientId: entraClientId
    entraClientSecret: entraClientSecret
  }
}

module data 'modules/storage-data.bicep' = {
  name: 'data'
  params: {
    name: 'st${compactApp}${suffix}d'
    location: location
    tags: allTags
    skuName: dataStorageSku
    allowedOrigins: concat(['https://${web.outputs.defaultHostname}'], extraAllowedOrigins)
  }
}

module api 'modules/function-app.bicep' = {
  name: 'api'
  params: {
    name: 'func-${baseName}'
    location: location
    tags: allTags
    hostStorageName: 'st${compactApp}${suffix}f'
    appInsightsConnectionString: monitoring.outputs.appInsightsConnectionString
    appSettings: {
      STORAGE_ACCOUNT_NAME: data.outputs.name
      HTML_CONTAINER: 'html'
      MAX_UPLOAD_MB: string(maxUploadMb)
      SHARE_MAX_DAYS: string(shareMaxDays)
    }
  }
}

// The API signs user delegation SAS and reads/writes blobs and tables with its
// Managed Identity.
module dataRoles 'modules/storage-roles.bicep' = {
  name: 'data-roles'
  params: {
    storageAccountName: data.outputs.name
    principalId: api.outputs.principalId
    roleDefinitionIds: [storageBlobDataContributor, storageBlobDelegator, storageTableDataContributor]
  }
}

module link 'modules/swa-link.bicep' = {
  name: 'swa-link'
  params: {
    staticWebAppName: web.outputs.name
    functionAppId: api.outputs.id
    functionAppLocation: location
  }
}

output webUrl string = 'https://${web.outputs.defaultHostname}'
output staticWebAppName string = web.outputs.name
output functionAppName string = api.outputs.name
output dataStorageAccountName string = data.outputs.name
output entraRedirectUri string = 'https://${web.outputs.defaultHostname}/.auth/login/aad/callback'
