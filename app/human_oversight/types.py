# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for license information.

"""Type definitions for the human oversight module."""

from typing import Any, Callable, Dict, TypeVar

# Function type for the decorator
F = TypeVar('F', bound=Callable[..., Any])

# Type definitions for commonly used structures
ApprovalPayload = Dict[str, Any]
ApprovalResponse = Dict[str, str]
LogEvent = Dict[str, Any]
Parameters = Dict[str, Any]
