# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for license information.

"""
Service for handling approval requests and responses.

This module contains functions for creating approval payloads,
sending approval requests, and processing approval responses.
"""

import json
import logging
from typing import Any, Dict, List, Optional, Tuple

import requests

from .config import HO_LOGIC_APP_URL
from .constants import ApprovalStatus, TIMEOUT_SECONDS
from .logging_utils import get_current_timestamp, log_approval_event
from .types import ApprovalPayload, ApprovalResponse, LogEvent, Parameters

# Configure logger
logger = logging.getLogger(__name__)


def create_serializable_parameters(kwargs: Dict[str, Any]) -> Parameters:
    """
    Create a dictionary of serializable parameters from function arguments.
    
    Converts non-serializable objects to string representations to ensure
    the parameters can be safely serialized to JSON.
    
    Args:
        kwargs: Function keyword arguments to be serialized
        
    Returns:
        Dictionary with serializable values
    """
    parameters = {}
    for name, value in kwargs.items():
        try:
            json.dumps({name: value})
            parameters[name] = value
        except (TypeError, OverflowError, ValueError):
            parameters[name] = f"<unserializable: {type(value).__name__}>"
    return parameters


def create_approval_payload(
    agent_name: str,
    action_description: str,
    parameters: Parameters,
    approver_emails: List[str],
    correlation_id: str
) -> ApprovalPayload:
    """
    Create the payload for an approval request.
    
    Args:
        agent_name: Name of the agent requesting approval
        action_description: Description of the action requiring approval
        parameters: Parameters for the action (must be serializable)
        approver_emails: List of email addresses for approvers
        correlation_id: Unique ID for tracking this approval request
        
    Returns:
        Dictionary containing the structured payload for the approval request
    """
    return {
        "agentName": agent_name,
        "actionDescription": action_description,
        "parameters": parameters,
        "approverEmails": approver_emails,
        "correlationId": correlation_id,
        "timestamp": get_current_timestamp()
    }


def send_approval_request(payload: ApprovalPayload) -> Tuple[bool, Optional[ApprovalResponse]]:
    """
    Send an approval request to the Logic App endpoint.
    
    Args:
        payload: Payload for the approval request
        
    Returns:
        Tuple containing:
        - Boolean indicating success or failure of the HTTP request
        - Response data if successful, None otherwise
    """
    try:
        response = requests.post(
            HO_LOGIC_APP_URL,
            json=payload,
            timeout=TIMEOUT_SECONDS
        )
        response.raise_for_status()
        return True, response.json()

    except requests.exceptions.Timeout:
        logger.error("Request to Logic App timed out (ID: %s).", payload['correlationId'])
        return False, None

    except requests.exceptions.RequestException as exception:
        logger.error("Error calling Logic App (ID: %s): %s", payload['correlationId'], exception)
        return False, None


def update_log_with_response(
    log_event: LogEvent,
    success: bool,
    response_data: Optional[ApprovalResponse]
) -> LogEvent:
    """
    Update the log event with response data from the approval request.
    
    Args:
        log_event: Current log event to update
        success: Whether the HTTP request was successful
        response_data: Response data from the approval request
        
    Returns:
        Updated log event dictionary
    """
    if not success:
        status = ApprovalStatus.TIMEOUT.value if isinstance(success, requests.exceptions.Timeout) else ApprovalStatus.ERROR.value
        log_event.update({
            "Status": status,
            "CompletionTimestamp": get_current_timestamp()
        })
        if not isinstance(success, requests.exceptions.Timeout):
            log_event["Error"] = "HTTP request failed"
        return log_event

    # Request succeeded and we have response data
    if response_data:
        approval_status = response_data.get("status")
        approver = response_data.get("approver", "Unknown")

        log_event.update({
            "Status": approval_status,
            "Approver": approver,
            "CompletionTimestamp": get_current_timestamp()
        })

    return log_event


def request_approval(
    payload: ApprovalPayload,
    log_event: LogEvent,
    correlation_id: str
) -> Tuple[bool, Optional[ApprovalResponse], LogEvent]:
    """
    Send an approval request and handle the response logging.
    
    Args:
        payload: Payload for the approval request
        log_event: Current log event to update
        correlation_id: Unique ID for this approval request
        
    Returns:
        Tuple containing:
        - Boolean indicating success or failure
        - Response data if successful, None otherwise
        - Updated log event
    """
    logger.info("Requesting approval (ID: %s)...", correlation_id)

    success, response_data = send_approval_request(payload)

    updated_log = update_log_with_response(log_event, success, response_data)
    log_approval_event(updated_log)

    return success, response_data, updated_log


def is_approval_granted(response_data: ApprovalResponse) -> bool:
    """
    Check if approval was granted based on response data.
    
    Args:
        response_data: Response from the approval request
        
    Returns:
        Boolean indicating if approval was granted
    """
    return response_data.get("status") == ApprovalStatus.APPROVED.value


def format_approval_result_message(
    response_data: ApprovalResponse,
    correlation_id: str
) -> str:
    """
    Format a message describing the approval result.
    
    Args:
        response_data: Response from the approval request
        correlation_id: Unique ID for this approval request
        
    Returns:
        Formatted message string for logging or notification
    """
    approval_status = response_data.get("status")
    approver = response_data.get("approver", "Unknown")

    if approval_status == ApprovalStatus.APPROVED.value:
        return f"Approval received (ID: {correlation_id}) from {approver}."

    status_message = "rejected" if approval_status == ApprovalStatus.REJECTED.value else "timed out or status unclear"
    approver_info = f" by {approver}" if approval_status == ApprovalStatus.REJECTED.value else f". Status: {approval_status}"

    return f"Approval {status_message} (ID: {correlation_id}){approver_info}"
