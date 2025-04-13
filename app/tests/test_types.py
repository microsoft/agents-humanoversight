# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for license information.

import unittest
from human_oversight.types import ApprovalPayload, ApprovalResponse, LogEvent, Parameters

class TestTypes(unittest.TestCase):
    """Test the type definitions."""

    def test_approval_payload_structure(self):
        """Test the structure of ApprovalPayload."""
        payload: ApprovalPayload = {
            "agentName": "TestAgent",
            "actionDescription": "Test Action",
            "parameters": {"key": "value"},
            "approverEmails": ["approver@example.com"],
            "correlationId": "test-id",
            "timestamp": "2025-04-13T12:00:00.000000Z"
        }
        self.assertIn("agentName", payload)
        self.assertIn("actionDescription", payload)
        self.assertIn("parameters", payload)

    def test_approval_response_structure(self):
        """Test the structure of ApprovalResponse."""
        response: ApprovalResponse = {
            "status": "Approved",
            "approver": "approver@example.com"
        }
        self.assertIn("status", response)
        self.assertIn("approver", response)

    def test_log_event_structure(self):
        """Test the structure of LogEvent."""
        log_event: LogEvent = {
            "PartitionKey": "TestAgent",
            "RowKey": "test-id",
            "Status": "Initiated",
            "Timestamp": "2025-04-13T12:00:00.000000Z",
            "ActionDescription": "Test Action",
            "Parameters": {"key": "value"}
        }
        self.assertIn("PartitionKey", log_event)
        self.assertIn("RowKey", log_event)
        self.assertIn("Status", log_event)

if __name__ == '__main__':
    unittest.main()
