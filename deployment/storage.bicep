@description('The base name for the Storage Account. Must be 3-15 chars, lowercase letters/numbers. A unique string will be appended.')
@minLength(3)
@maxLength(15)
param storageAccountNameBase string

@description('The location for the Storage Account.')
param location string = resourceGroup().location

@description('The name for the approvals table.')
param approvalsTableName string = 'approvals'

var uniqueSuffix = uniqueString(resourceGroup().id)
var combinedName = '${storageAccountNameBase}${uniqueSuffix}'
var storageAccountName = substring(toLower(replace(combinedName, '-', '')), 0, min(length(combinedName), 24))

resource storageAccount 'Microsoft.Storage/storageAccounts@2023-01-01' = {
  name: storageAccountName
  location: location
  sku: {
    name: 'Standard_LRS'
  }
  kind: 'StorageV2'
  properties: {
    allowBlobPublicAccess: false
    networkAcls: {
      bypass: 'AzureServices'
      virtualNetworkRules: []
      ipRules: []
      defaultAction: 'Allow'
    }
    minimumTlsVersion: 'TLS1_2'
    supportsHttpsTrafficOnly: true
  }
}

resource tableService 'Microsoft.Storage/storageAccounts/tableServices@2023-01-01' = {
  parent: storageAccount
  name: 'default' 
}

resource approvalsTable 'Microsoft.Storage/storageAccounts/tableServices/tables@2023-01-01' = {
  parent: tableService
  name: approvalsTableName
}

output storageAccountName string = storageAccount.name
output approvalsTableName string = approvalsTable.name
output storageConnectionString string = 'DefaultEndpointsProtocol=https;AccountName=${storageAccount.name};AccountKey=${listKeys(storageAccount.id, storageAccount.apiVersion).keys[0].value};EndpointSuffix=${environment().suffixes.storage}'

