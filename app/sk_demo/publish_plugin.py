# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for license information.

"""
GitHub Plugin for Semantic Kernel
"""

import json
from semantic_kernel.functions import kernel_function

from sk_demo.github_api_plugin import GitHubPlugin
from human_oversight import approval_gate

class PublishPlugin:
    """
    Plugin for publishing content to GitHub Gists.
    Includes human approval flow for sensitive operations.
    """

    def __init__(self, agent_name=None, approvers=None, conversation_state=None):
        self.github_plugin = GitHubPlugin()
        self.agent_name = agent_name
        self.approvers = approvers
        self.conversation_state = conversation_state

    @kernel_function(
        description="Publish the final report as a GitHub Gist",
        name="publish_gist"
    )
    def publish_gist(self, title: str, content: str) -> str:
        """
        Publish the final report as a GitHub Gist.
        
        Args:
            title: The title/description for the Gist
            content: The content to include in the Gist
            
        Returns:
            JSON string with the status and URL of the created Gist
        """
        approved_function = self._get_approval_gated_function()
        return approved_function(title, content)

    def _get_approval_gated_function(self):
        """Create and return the approval-gated function for publishing gists."""
        @approval_gate(
            agent_name=self.agent_name,
            action_description="Publish GitHub Gist",
            approver_emails=self.approvers,
            refusal_return_value="DENIED: Gist publication was not approved."
        )
        def _publish_gist_with_approval(title: str, content: str) -> str:
            print(f"Executing publish_gist(title='{title}')...")

            if self.conversation_state is not None:
                self.conversation_state.final_report = content

            gist_url = self.github_plugin.create_gist(title, content, False)

            return json.dumps({
                "status": "success",
                "message": "Gist published successfully.",
                "url": gist_url
            })

        return _publish_gist_with_approval
