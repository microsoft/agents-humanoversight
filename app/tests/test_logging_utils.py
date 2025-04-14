# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for license information.

"""
Tests for logging_utils.py module in the human_oversight package.
"""

import unittest
from unittest.mock import patch
import json
from datetime import datetime, timezone

from human_oversight.logging_utils import (
    log_approval_event,
    create_initial_log_event,
    get_current_timestamp
)


class TestLoggingUtils(unittest.TestCase):
    """Test logging utility functions."""

    def setUp(self):
        self.agent_name = "TestAgent"
        self.correlation_id = "test-correlation-id"
        self.action_desc = "Test Action"
        self.parameters = {"param1": "value1", "param2": 123}
        self.mock_timestamp = "2025-04-13T12:00:00.000000Z"

    @patch('human_oversight.logging_utils.logger')
    def test_log_approval_event(self, mock_logger):
        """Test logging of approval events."""
        event_data = {
            "PartitionKey": self.agent_name,
            "RowKey": self.correlation_id,
            "Status": "Initiated",
            "ActionDescription": self.action_desc
        }

        log_approval_event(event_data)

        # Check that logger.info was called with the correct format and arguments
        mock_logger.info.assert_called_once_with(
            "Approval Event: %s", 
            json.dumps(event_data)
        )

    @patch('human_oversight.logging_utils.get_current_timestamp')
    def test_create_initial_log_event(self, mock_timestamp):
        """Test creation of initial log event."""
        mock_timestamp.return_value = self.mock_timestamp

        log_event = create_initial_log_event(
            self.agent_name,
            self.correlation_id,
            self.action_desc,
            self.parameters
        )

        self.assertEqual(log_event["PartitionKey"], self.agent_name)
        self.assertEqual(log_event["RowKey"], self.correlation_id)
        self.assertEqual(log_event["Status"], "Initiated")
        self.assertEqual(log_event["Timestamp"], self.mock_timestamp)
        self.assertEqual(log_event["ActionDescription"], self.action_desc)
        self.assertEqual(log_event["Parameters"], self.parameters)

    @patch('human_oversight.logging_utils.datetime')
    def test_get_current_timestamp(self, mock_datetime):
        """Test timestamp generation."""
        # Create a fixed datetime for testing
        test_dt = datetime(2025, 4, 13, 12, 0, 0, tzinfo=timezone.utc)
        mock_datetime.now.return_value = test_dt
        mock_datetime.timezone = timezone

        timestamp = get_current_timestamp()

        mock_datetime.now.assert_called_once_with(timezone.utc)
        self.assertEqual(timestamp, test_dt.isoformat())


if __name__ == '__main__':
    unittest.main()
