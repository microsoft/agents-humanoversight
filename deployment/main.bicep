@description('The base name for resources. A unique string will be appended.')
param baseName string = 'ho${uniqueString(resourceGroup().id)}'

@description('The location for all resources.')
param location string = resourceGroup().location

var storageAccountNameBase = toLower(replace(baseName, '-', ''))

var logicAppName = '${baseName}-logicapp'
var approvalsTableName = 'approvals'

module storage 'storage.bicep' = {
  name: 'storageDeploy'
  params: {
    storageAccountNameBase: storageAccountNameBase
    location: location
    approvalsTableName: approvalsTableName
  }
}

module logicApp 'logicapp.bicep' = {
  name: 'logicAppDeploy'
  params: {
    logicAppName: logicAppName
    location: location
    approvalsTableName: storage.outputs.approvalsTableName
    storageConnectionString: storage.outputs.storageConnectionString
  }
}

output logicAppUrl string = logicApp.outputs.logicAppUrl
output storageAccountName string = storage.outputs.storageAccountName
output approvalsTableName string = storage.outputs.approvalsTableName
output storageConnectionString string = storage.outputs.storageConnectionString
