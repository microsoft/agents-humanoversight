# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for license information.

"""
Tests for decorator.py module in the human_oversight package.
"""

import unittest
from unittest.mock import patch
from human_oversight.decorator import validate_configuration, execute_function_with_logging
from human_oversight.constants import ApprovalStatus

class TestDecorator(unittest.TestCase):
    """Test the decorator module."""

    @patch('human_oversight.decorator.HO_LOGIC_APP_URL', None)
    def test_validate_configuration_missing_url(self):
        """Test that validate_configuration raises an error when HO_LOGIC_APP_URL is not set."""
        with self.assertRaises(ValueError) as context:
            validate_configuration()
        self.assertIn("HO_LOGIC_APP_URL environment variable must be set", str(context.exception))

    @patch('human_oversight.logging_utils.get_current_timestamp', return_value="2025-04-13T12:00:00.000000Z")
    @patch('human_oversight.decorator.log_approval_event')  # Corrected patch target
    def test_execute_function_with_logging_success(self, mock_log_event):
        """Test successful function execution with logging."""
        def sample_function(x):  #pylint: disable=invalid-name
            return x * 2

        log_event = {
            "Status": ApprovalStatus.INITIATED,
            "ExecutionTimestamp": None
        }
        result = execute_function_with_logging(sample_function, (5,), {}, log_event, "test-correlation-id")

        self.assertEqual(result, 10)
        self.assertEqual(log_event["Status"], ApprovalStatus.EXECUTED)
        mock_log_event.assert_called_once()

    @patch('human_oversight.logging_utils.get_current_timestamp', return_value="2025-04-13T12:00:00.000000Z")
    @patch('human_oversight.decorator.log_approval_event')  # Corrected patch target
    def test_execute_function_with_logging_failure(self, mock_log_event):
        """Test failed function execution with logging."""
        def sample_function(x):  #pylint: disable=invalid-name
            raise ValueError("Test error")

        log_event = {
            "Status": ApprovalStatus.INITIATED,
            "ExecutionTimestamp": None
        }

        with self.assertRaises(ValueError):
            execute_function_with_logging(sample_function, (5,), {}, log_event, "test-correlation-id")

        self.assertEqual(log_event["Status"], ApprovalStatus.EXECUTION_FAILED)
        self.assertIn("Error", log_event)
        mock_log_event.assert_called_once()

if __name__ == '__main__':
    unittest.main()
