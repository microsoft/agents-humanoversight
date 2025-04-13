# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for license information.

import unittest
import json

from human_oversight.constants import (
    ApprovalStatus,
    DEFAULT_REFUSAL_VALUE,
    TIMEOUT_SECONDS,
    STATUS_APPROVED,
    STATUS_REJECTED
)


class TestConstants(unittest.TestCase):
    """Test constants definitions and enumerations."""
    
    def test_approval_status_enum(self):
        """Test the ApprovalStatus enum values."""
        self.assertEqual(ApprovalStatus.INITIATED, "Initiated")
        self.assertEqual(ApprovalStatus.APPROVED, "Approved")
        self.assertEqual(ApprovalStatus.REJECTED, "Rejected")
        self.assertEqual(ApprovalStatus.TIMEOUT, "Timeout")
        self.assertEqual(ApprovalStatus.ERROR, "Error")
        self.assertEqual(ApprovalStatus.EXECUTED, "Executed")
        self.assertEqual(ApprovalStatus.EXECUTION_FAILED, "ExecutionFailed")
    
    def test_approval_status_aliases(self):
        """Test the status aliases for backwards compatibility."""
        self.assertEqual(STATUS_APPROVED, ApprovalStatus.APPROVED)
        self.assertEqual(STATUS_REJECTED, ApprovalStatus.REJECTED)
    
    def test_approval_status_serializable(self):
        """Test that enum values can be serialized to JSON."""
        status_dict = {
            "initiated": ApprovalStatus.INITIATED,
            "approved": ApprovalStatus.APPROVED,
            "rejected": ApprovalStatus.REJECTED
        }
        
        # Should not raise any exceptions
        json_str = json.dumps(status_dict)
        
        # Verify serialization is correct
        parsed = json.loads(json_str)
        self.assertEqual(parsed["initiated"], "Initiated")
        self.assertEqual(parsed["approved"], "Approved")
        self.assertEqual(parsed["rejected"], "Rejected")
    
    def test_default_values(self):
        """Test default configuration values."""
        self.assertIsInstance(TIMEOUT_SECONDS, int)
        self.assertGreater(TIMEOUT_SECONDS, 0)
        
        self.assertIsInstance(DEFAULT_REFUSAL_VALUE, str)
        self.assertIn("denied", DEFAULT_REFUSAL_VALUE)


if __name__ == '__main__':
    unittest.main()
