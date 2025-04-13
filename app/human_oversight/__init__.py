# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for license information.


"""
Human Oversight module providing approval gate functionality for AI agents.

This module enables sensitive operations performed by AI agents to be reviewed 
and approved by human operators before execution. It provides:

1. A decorator for wrapping sensitive functions with approval workflows
2. Services for sending and receiving approval requests
3. Comprehensive logging of the approval process

Usage:
    from human_oversight import approval_gate

    @approval_gate(
        agent_name="MyAgent",
        action_description="Delete user data",
        approver_emails=["approver@example.com"]
    )
    def delete_user(user_id):
        # This function will only execute after human approval
        ...
"""

from .constants import DEFAULT_REFUSAL_VALUE, ApprovalStatus
from .decorator import approval_gate

__all__ = ['approval_gate', 'DEFAULT_REFUSAL_VALUE', 'ApprovalStatus']
