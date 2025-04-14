# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for license information.

"""
Decorator for creating approval gates on sensitive operations.

This module provides a decorator that wraps functions requiring human approval
before execution, implementing a approval workflow.
"""

import functools
import inspect
import logging
import uuid
from typing import Any, Callable, List, Optional, cast

from .approval import (create_approval_payload,
                              create_serializable_parameters,
                              format_approval_result_message, is_approval_granted,
                              request_approval)
from .config import HO_LOGIC_APP_URL
from .constants import ApprovalStatus, DEFAULT_REFUSAL_VALUE
from .logging_utils import create_initial_log_event, get_current_timestamp, log_approval_event
from .types import ApprovalResponse, F, LogEvent

# Configure logger
logger = logging.getLogger(__name__)


def validate_configuration() -> None:
    """
    Validate that required configuration is available.
    
    Raises:
        ValueError: If required environment variables are not set
    """
    if not HO_LOGIC_APP_URL:
        raise ValueError(
            "HO_LOGIC_APP_URL environment variable must be set to use the approval_gate decorator. "
            "Set this variable to the URL of your approval Logic App."
        )


def execute_function_with_logging(
    func: Callable,
    args: Any,
    kwargs: Any,
    log_event: LogEvent,
    correlation_id: str
) -> Any:
    """
    Execute the function and log the result.
    
    Args:
        func: Function to execute
        args: Positional arguments
        kwargs: Keyword arguments
        log_event: Current log event to update
        correlation_id: Unique ID for this approval
        
    Returns:
        Result of the function execution
        
    Raises:
        Exception: Any exception raised by the function
    """
    try:
        result = func(*args, **kwargs)

        log_event.update({
            "Status": ApprovalStatus.EXECUTED.value,
            "ExecutionTimestamp": get_current_timestamp()
        })
        log_approval_event(log_event)

        return result

    except Exception as exception:
        logger.error("Error during function execution after approval (ID: %s): %s", correlation_id, exception)
        log_event.update({
            "Status": ApprovalStatus.EXECUTION_FAILED.value,
            "Error": str(exception),
            "ExecutionTimestamp": get_current_timestamp()
        })
        log_approval_event(log_event)
        raise


def handle_approval_response(
    response_data: Optional[ApprovalResponse],
    func: Callable,
    args: Any,
    kwargs: Any,
    log_event: LogEvent,
    correlation_id: str,
    refusal_return_value: Any
) -> Any:
    """
    Handle the approval response and execute the function if approved.
    
    Args:
        response_data: Response from the approval request
        func: Function to execute if approved
        args: Positional arguments for the function
        kwargs: Keyword arguments for the function
        log_event: Current log event to update
        correlation_id: Unique ID for this approval
        refusal_return_value: Value to return if approval is denied
        
    Returns:
        Result of function execution if approved, or refusal value
    """
    if not response_data:
        return refusal_return_value

    if is_approval_granted(response_data):
        message = format_approval_result_message(response_data, correlation_id)
        logger.info("%s Executing function...", message)
        return execute_function_with_logging(func, args, kwargs, log_event, correlation_id)
    message = format_approval_result_message(response_data, correlation_id)
    logger.warning(message)
    return refusal_return_value


def approval_gate(
    agent_name: str,
    action_description: str,
    approver_emails: List[str],
    refusal_return_value: Any = DEFAULT_REFUSAL_VALUE
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """
    Decorator that creates an approval gate for sensitive operations.
    
    This decorator wraps a function to require human approval before execution.
    If approval is granted, the function executes normally. If denied or timed out,
    the specified refusal value is returned instead.
    
    Args:
        agent_name: Name of the agent requesting approval
        action_description: Description of the action requiring approval
        approver_emails: List of email addresses for approvers
        refusal_return_value: Value to return if approval is denied or times out
        
    Returns:
        Decorated function that will only execute after approval
        
    Raises:
        ValueError: If HO_LOGIC_APP_URL environment variable is not set
    """
    validate_configuration()

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            correlation_id = str(uuid.uuid4())

            # Create a combined parameters dict that includes both positional and keyword args
            parameters = {}

            # Add positional args with arg index as key
            sig = inspect.signature(func)
            param_names = list(sig.parameters.keys())

            # Map positional args to their parameter names
            for i, arg in enumerate(args):
                if i < len(param_names):
                    arg_name = param_names[i]
                    parameters[arg_name] = arg
                else:
                    parameters[f"arg{i}"] = arg

            # Add keyword args
            parameters.update(create_serializable_parameters(kwargs))

            log_event = create_initial_log_event(
                agent_name,
                correlation_id,
                action_description,
                parameters
            )
            log_approval_event(log_event)

            payload = create_approval_payload(
                agent_name,
                action_description,
                parameters,
                approver_emails,
                correlation_id
            )

            success, response_data, log_event = request_approval(
                payload,
                log_event,
                correlation_id
            )

            if not success:
                return refusal_return_value

            return handle_approval_response(
                response_data,
                func,
                args,
                kwargs,
                log_event,
                correlation_id,
                refusal_return_value
            )

        return cast(F, wrapper)
    return decorator
