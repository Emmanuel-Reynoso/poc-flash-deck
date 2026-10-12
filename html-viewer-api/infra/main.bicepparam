using 'main.bicep'

param appName = 'htmlviewer'
param environmentName = 'prod'
param staticWebAppLocation = 'eastus2'
param maxUploadMb = 20
param shareMaxDays = 30

// Read from the environment so secrets never land in the repo.
param entraClientId = readEnvironmentVariable('ENTRA_CLIENT_ID', '')
param entraClientSecret = readEnvironmentVariable('ENTRA_CLIENT_SECRET', '')
