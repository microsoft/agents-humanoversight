# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for license information.

"""Logging utilities for the human oversight module."""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict

from .types import LogEvent

# Configure logger
logger = logging.getLogger(__name__)

# Constants
ISO_TIMESTAMP_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"


def log_approval_event(event_data: LogEvent) -> None:
    """
    Log an approval event with standardized format.
    
    Args:
        event_data: Dictionary containing event information including agent name,
                   correlation ID, status, timestamps, and other relevant metadata.
    """
    logger.info("Approval Event: %s", json.dumps(event_data))


def create_initial_log_event(
    agent_name: str,
    correlation_id: str,
    action_description: str,
    parameters: Dict[str, Any]
) -> LogEvent:
    """
    Create an initial log event for approval initiation.
    
    Args:
        agent_name: Name of the agent requesting approval
        correlation_id: Unique ID for tracking this approval request
        action_description: Human-readable description of the action requiring approval
        parameters: Parameters for the action that will be executed if approved
        
    Returns:
        Dictionary containing structured log event data with standardized fields
    """
    return {
        "PartitionKey": agent_name,
        "RowKey": correlation_id,
        "Status": "Initiated",
        "Timestamp": get_current_timestamp(),
        "ActionDescription": action_description,
        "Parameters": parameters
    }


def get_current_timestamp() -> str:
    """
    Get the current UTC timestamp in ISO format.
    
    Returns:
        ISO 8601 formatted timestamp string in UTC timezone
    """
    return datetime.now(timezone.utc).isoformat()
