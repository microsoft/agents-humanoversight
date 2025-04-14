# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for license information.

"""
Configuration module for Human Oversight functionality.

This module loads environment variables required for the human oversight
approval process, particularly the Logic App URL used for approvals.
"""

import os
import logging
from typing import Optional
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

load_dotenv()

HO_LOGIC_APP_URL: Optional[str] = os.getenv("HO_LOGIC_APP_URL")

if not HO_LOGIC_APP_URL:
    logger.warning(
        "HO_LOGIC_APP_URL environment variable not set. "
        "Human Oversight Approval Gate cannot be called. "
        "Set this variable to enable approval functionality."
    )
