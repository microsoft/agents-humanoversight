# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for license information.

"""
Tests for gate functionality.
"""

import unittest
from unittest.mock import patch
import logging

from human_oversight import approval_gate
from human_oversight.constants import DEFAULT_REFUSAL_VALUE


# Configure logging for tests
logging.basicConfig(level=logging.INFO)


class TestApprovalGateFunctionality(unittest.TestCase):
    """
    Test the approval_gate decorator behavior under different conditions.
    
    These tests focus on the gate behavior rather than the internal 
    implementation details.
    """

    def setUp(self):
        """Set up test fixtures."""
        self.agent_name = "SecurityAgent"
        self.action_desc = "Format Hard Drive"
        self.approver_emails = ["security@example.com", "admin@example.com"]

        # Counter for function calls
        self.call_count = 0

        # Simple function to be decorated
        def critical_operation(resource_id, confirm=False):
            self.call_count += 1
            return f"Performed critical operation on {resource_id} (confirm={confirm})"

        self.critical_operation = critical_operation

    @patch('human_oversight.decorator.HO_LOGIC_APP_URL', 'https://test-gate.example.com')
    @patch('human_oversight.decorator.request_approval')
    def test_approved_operation_executes(self, mock_request):
        """Test that operations are executed when approved."""
        # Mock approved response
        mock_request.return_value = (
            True,
            {"status": "Approved", "approver": "security@example.com"},
            {"Status": "Approved"}
        )

        # Create decorated function
        secured_operation = approval_gate(
            agent_name=self.agent_name,
            action_description=self.action_desc,
            approver_emails=self.approver_emails
        )(self.critical_operation)

        # Call with test parameters
        result = secured_operation("server-001", confirm=True)

        # Verify function was executed
        self.assertEqual(self.call_count, 1)
        self.assertIn("Performed critical operation", result)
        self.assertIn("server-001", result)

    @patch('human_oversight.decorator.HO_LOGIC_APP_URL', 'https://test-gate.example.com')
    @patch('human_oversight.decorator.request_approval')
    def test_rejected_operation_blocked(self, mock_request):
        """Test that operations are blocked when rejected."""
        # Mock rejected response
        mock_request.return_value = (
            True,
            {"status": "Rejected", "approver": "admin@example.com"},
            {"Status": "Rejected"}
        )

        # Custom refusal message
        refusal_msg = "Security policy violation: operation rejected"

        # Create decorated function
        secured_operation = approval_gate(
            agent_name=self.agent_name,
            action_description=self.action_desc,
            approver_emails=self.approver_emails,
            refusal_return_value=refusal_msg
        )(self.critical_operation)

        # Call with test parameters
        result = secured_operation("database-prod", confirm=True)

        # Verify function was NOT executed
        self.assertEqual(self.call_count, 0)
        self.assertEqual(result, refusal_msg)

    @patch('human_oversight.decorator.HO_LOGIC_APP_URL', 'https://test-gate.example.com')
    @patch('human_oversight.decorator.request_approval')
    def test_default_refusal_value(self, mock_request):
        """Test the default refusal value is returned when not overridden."""
        # Mock rejected response
        mock_request.return_value = (
            True,
            {"status": "Rejected", "approver": "admin@example.com"},
            {"Status": "Rejected"}
        )

        # Create decorated function with default refusal value
        secured_operation = approval_gate(
            agent_name=self.agent_name,
            action_description=self.action_desc,
            approver_emails=self.approver_emails
        )(self.critical_operation)

        # Call with test parameters
        result = secured_operation("database-prod", confirm=True)

        # Verify default refusal value is returned
        self.assertEqual(self.call_count, 0)
        self.assertEqual(result, DEFAULT_REFUSAL_VALUE)

    @patch('human_oversight.decorator.HO_LOGIC_APP_URL', 'https://test-gate.example.com')
    @patch('human_oversight.decorator.request_approval')
    def test_complex_function_signature(self, mock_request):
        """Test that approval gate works with complex function signatures."""
        # Mock approved response
        mock_request.return_value = (
            True,
            {"status": "Approved", "approver": "security@example.com"},
            {"Status": "Approved"}
        )

        # Function with complex signature
        def complex_function(a, b, *args, c=None, **kwargs):  #pylint: disable=invalid-name
            self.call_count += 1
            return {
                "a": a,
                "b": b,
                "args": args,
                "c": c,
                "kwargs": kwargs
            }

        # Create decorated function
        secured_complex = approval_gate(
            agent_name=self.agent_name,
            action_description=self.action_desc,
            approver_emails=self.approver_emails
        )(complex_function)

        # Call with variety of parameters
        result = secured_complex(
            1, "text", "extra1", "extra2",
            c="override",
            option1=True,
            option2="value"
        )

        # Verify function was executed with all parameters
        self.assertEqual(self.call_count, 1)
        self.assertEqual(result["a"], 1)
        self.assertEqual(result["b"], "text")
        self.assertEqual(result["args"], ("extra1", "extra2"))
        self.assertEqual(result["c"], "override")
        self.assertEqual(result["kwargs"]["option1"], True)
        self.assertEqual(result["kwargs"]["option2"], "value")


if __name__ == '__main__':
    unittest.main()
