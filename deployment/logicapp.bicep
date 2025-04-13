@description('The name for the Logic App.')
param logicAppName string

@description('The location for the Logic App.')
param location string = resourceGroup().location

@description('The name of the table within the Storage Account used for logging.')
param approvalsTableName string

@description('The connection string for the Storage Account.')
@secure()
param storageConnectionString string

resource office365Connection 'Microsoft.Web/connections@2016-06-01' = {
  name: 'office365'
  location: location
  properties: {
    displayName: 'Office365-Connection'
    customParameterValues: {}
    api: {
      id: subscriptionResourceId('Microsoft.Web/locations/managedApis', location, 'office365')
    }
  }
}

var storageDetails = split(replace(replace(storageConnectionString, 'DefaultEndpointsProtocol=https;', ''), 'EndpointSuffix=${environment().suffixes.storage}', ''), ';')
var accountNamePart = first(filter(storageDetails, item => startsWith(item, 'AccountName=')))
var accountKeyPart = first(filter(storageDetails, item => startsWith(item, 'AccountKey=')))
var storageAccountName = length(accountNamePart) > 0 ? substring(accountNamePart, length('AccountName='), length(accountNamePart) - length('AccountName=')) : ''
var storageAccountKey = length(accountKeyPart) > 0 ? substring(accountKeyPart, length('AccountKey='), length(accountKeyPart) - length('AccountKey=')) : ''

// API Connection for Azure Table Storage
resource azureTablesConnection 'Microsoft.Web/connections@2016-06-01' = {
  name: 'azuretables'
  location: location
  properties: {
    displayName: 'AzureTables-Connection'
    parameterValues: {
      storageaccount: storageAccountName
      sharedkey: storageAccountKey
    }
    customParameterValues: {}
    api: {
      id: subscriptionResourceId('Microsoft.Web/locations/managedApis', location, 'azuretables')
    }
  }
}


resource logicApp 'Microsoft.Logic/workflows@2019-05-01' = {
  name: logicAppName
  location: location
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    state: 'Enabled'
    definition: {
      '$schema': 'https://schema.management.azure.com/providers/Microsoft.Logic/schemas/2016-06-01/workflowdefinition.json#'
      contentVersion: '1.0.0.0'
      parameters: {
        '$connections': {
          defaultValue: {}
          type: 'Object'
        }
        storageConnectionString: {
          defaultValue: storageConnectionString
          type: 'SecureString'
        }
        approvalsTableName: {
          defaultValue: approvalsTableName
          type: 'String'
        }
      }
      triggers: {
        manual: {
          type: 'Request'
          kind: 'Http'
          inputs: {
            method: 'POST'
            schema: {
              type: 'object'
              properties: {
                agentName: { type: 'string', description: 'Name of the agent requesting approval.' }
                actionDescription: { type: 'string', description: 'Description of the action requiring approval.' }
                parameters: { type: 'object', description: 'Parameters passed to the function/action.' }
                approverEmails: { type: 'array', items: { type: 'string', format: 'email' }, description: 'List of email addresses to request approval from.' }
                correlationId: { type: 'string', description: 'A unique identifier for this approval request.' }
              }
              required: [
                'agentName'
                'actionDescription'
                'parameters'
                'approverEmails'
                'correlationId'
              ]
            }
          }
        }
      }
      actions: {
        Initialize_Variables: {
          runAfter: {}
          type: 'InitializeVariable'
          inputs: {
            variables: [
              {
                name: 'logEntry'
                type: 'object'
                value: {
                  PartitionKey: '@{triggerBody()?[\'agentName\']}'
                  RowKey: '@{triggerBody()?[\'correlationId\']}'
                  AgentName: '@{triggerBody()?[\'agentName\']}'
                  ActionDescription: '@{triggerBody()?[\'actionDescription\']}'
                  Parameters: '@{string(triggerBody()?[\'parameters\'])}'
                  ApproverEmails: '@{string(triggerBody()?[\'approverEmails\'])}'
                  RequestTimestamp: '@{utcNow()}'
                  Status: 'Pending'
                  Approver: null
                  ResponseTimestamp: null
                }
              }, {
                name: 'finalStatus'
                type: 'string'
                value: 'Pending'
              }, {
                name: 'finalApprover'
                type: 'string'
                value: ''
              }
            ]
          }
        }
        Send_approval_email: {
          runAfter: {
            Initialize_Variables: ['Succeeded']
          }
          type: 'ApiConnectionWebhook'
          inputs: {
            host: {
              connection: {
                name: '@parameters(\'$connections\')[\'office365\'][\'connectionId\']'
              }
            }
            body: {
              NotificationUrl: '@{listCallbackUrl()}'
              Message: {
                To: '@join(triggerBody()?[\'approverEmails\'], \';\')'
                Subject: 'Approval Request: @{triggerBody()?[\'agentName\']} - @{triggerBody()?[\'actionDescription\']}'
                Body: 'Agent: @{triggerBody()?[\'agentName\']}\r\nAction: @{triggerBody()?[\'actionDescription\']}\r\n\r\nDetails/Parameters:\r\n@{json(string(triggerBody()?[\'parameters\']))}\r\n\r\nPlease approve or reject this request.'
                Importance: 'Normal'
                Options: 'Approve,Reject'
              }
            }
            path: '/approvalmail/$subscriptions'
          }
        }
        Condition_Check_Approval_Status: {
          runAfter: {
            Send_approval_email: ['Succeeded', 'Failed', 'Skipped', 'TimedOut']
          }
          type: 'If'
          expression: '@or(equals(outputs(\'Send_approval_email\')?[\'body/SelectedOption\'], \'Approve\'), equals(outputs(\'Send_approval_email\')?[\'body/Response\'], \'Approve\'))' // Check both modern and older response formats
          actions: {
            Set_Status_Approved: {
              runAfter: {}
              type: 'SetVariable'
              inputs: {
                name: 'finalStatus'
                value: 'Approved'
              }
            }
            Set_Approver_Approved: {
              runAfter: {
                Set_Status_Approved: ['Succeeded']
              }
              type: 'SetVariable'
              inputs: {
                name: 'finalApprover'
                value: '@{outputs(\'Send_approval_email\')?[\'body/responder\']?[\'email\']}'
              }
            }
          }
          else: {
            actions: {
              Set_Status_Rejected_Timeout: {
                runAfter: {}
                type: 'SetVariable'
                inputs: {
                  name: 'finalStatus'
                  value: '@if(or(equals(outputs(\'Send_approval_email\')?[\'body/SelectedOption\'], \'Reject\'), equals(outputs(\'Send_approval_email\')?[\'body/Response\'], \'Reject\')), \'Rejected\', \'Timeout\')'
                }
              }
              Condition_If_Rejected: {
                runAfter: {
                  Set_Status_Rejected_Timeout: ['Succeeded']
                }
                type: 'If'
                expression: '@or(equals(outputs(\'Send_approval_email\')?[\'body/SelectedOption\'], \'Reject\'), equals(outputs(\'Send_approval_email\')?[\'body/Response\'], \'Reject\'))'
                actions: {
                  Set_Approver_Rejected: {
                    runAfter: {}
                    type: 'SetVariable'
                    inputs: {
                      name: 'finalApprover'
                      value: '@{outputs(\'Send_approval_email\')?[\'body/responder\']?[\'email\']}'
                    }
                  }
                }
              }
            }
          }
        }
        
        // Create the final log entry for storage
        Create_Final_Log_Entry: {
          runAfter: {
            Condition_Check_Approval_Status: ['Succeeded']
          }
          type: 'Compose'
          inputs: {
            PartitionKey: '@{variables(\'logEntry\')?[\'PartitionKey\']}'
            RowKey: '@{variables(\'logEntry\')?[\'RowKey\']}'
            AgentName: '@{variables(\'logEntry\')?[\'AgentName\']}'
            ActionDescription: '@{variables(\'logEntry\')?[\'ActionDescription\']}'
            Parameters: '@{variables(\'logEntry\')?[\'Parameters\']}'
            ApproverEmails: '@{variables(\'logEntry\')?[\'ApproverEmails\']}'
            RequestTimestamp: '@{variables(\'logEntry\')?[\'RequestTimestamp\']}'
            Status: '@{variables(\'finalStatus\')}'
            Approver: '@{variables(\'finalApprover\')}'
            ResponseTimestamp: '@{utcNow()}'
          }
        }
        
        Log_to_Table_Storage: {
          runAfter: {
            Create_Final_Log_Entry: ['Succeeded']
          }
          type: 'ApiConnection'
          inputs: {
            host: {
              connection: {
                name: '@parameters(\'$connections\')[\'azuretables\'][\'connectionId\']'
              }
            }
            method: 'post'
            body: '@outputs(\'Create_Final_Log_Entry\')'
            path: '/Tables/@{encodeURIComponent(parameters(\'approvalsTableName\'))}/entities'
          }
        }
        
        Response: {
          runAfter: {
            Log_to_Table_Storage: ['Succeeded', 'Failed'] 
          }
          type: 'Response'
          kind: 'Http'
          inputs: {
            statusCode: 200
            body: {
              correlationId: '@{triggerBody()?[\'correlationId\']}'
              status: '@{variables(\'finalStatus\')}'
              approver: '@{variables(\'finalApprover\')}'
            }
            headers: {
              'Content-Type': 'application/json'
            }
          }
        }
      }
      outputs: {}
    }
    parameters: {
      '$connections': {
        value: {
          office365: {
            connectionId: office365Connection.id
            connectionName: 'office365'
            id: subscriptionResourceId('Microsoft.Web/locations/managedApis', location, 'office365')
          }
          azuretables: {
             connectionId: azureTablesConnection.id
             connectionName: 'azuretables'
             id: subscriptionResourceId('Microsoft.Web/locations/managedApis', location, 'azuretables')
          }
        }
      }
    }
  }
}

output logicAppUrl string = listCallbackUrl(logicApp.id, logicApp.apiVersion).value
output logicAppManagedIdentityPrincipalId string = logicApp.identity.principalId
