# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for license information.

"""Constants used in the human oversight module."""
from enum import Enum


# Request configuration
TIMEOUT_SECONDS = 120  # HTTP request timeout in seconds

# Default values
DEFAULT_REFUSAL_VALUE = "Approval denied or timed out via Human Oversight Approval Gate."


class ApprovalStatus(str, Enum):
    """
    Enumeration of possible approval status values.
    
    Using string enum for easy JSON serialization while maintaining type safety.
    """
    # Approval process statuses
    INITIATED = "Initiated"
    APPROVED = "Approved"
    REJECTED = "Rejected"
    TIMEOUT = "Timeout"
    ERROR = "Error"
    
    # Execution statuses
    EXECUTED = "Executed"
    EXECUTION_FAILED = "ExecutionFailed"
    

# Backwards compatibility aliases
STATUS_APPROVED = ApprovalStatus.APPROVED
STATUS_REJECTED = ApprovalStatus.REJECTED
STATUS_INITIATED = ApprovalStatus.INITIATED
STATUS_EXECUTED = ApprovalStatus.EXECUTED
STATUS_EXECUTION_FAILED = ApprovalStatus.EXECUTION_FAILED
STATUS_TIMEOUT = ApprovalStatus.TIMEOUT
STATUS_ERROR = ApprovalStatus.ERROR
