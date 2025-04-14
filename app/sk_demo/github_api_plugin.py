# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for license information.

"""
GitHub Plugin for Semantic Kernel
"""

from typing import Annotated

import os
import json
import base64
import requests

from semantic_kernel.functions.kernel_function_decorator import kernel_function

from .constants import HTTP_TIMEOUT_SECONDS

class GitHubPlugin:
    """
    Plugin for interacting with GitHub API
    
    Usage:
        kernel.add_plugin(GitHubPlugin(), plugin_name="github")
    """

    def __init__(self):
        self.token = os.getenv("GITHUB_TOKEN")
        self.base_url = "https://api.github.com"
        if not self.token:
            print("Warning: GITHUB_TOKEN not set. API calls may be rate-limited.")

    def _get_headers(self):
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "GithubSearchAgent"
        }
        if self.token:
            headers["Authorization"] = f"token {self.token}"
        return headers

    @kernel_function(
        description="Search GitHub code with the given query",
        name="search_code"
    )
    def search_code(
        self,
        query: Annotated[str, "The search query for GitHub code search"],
        page: Annotated[int, "The page number for paginated results"] = 1,
        per_page: Annotated[int, "Number of results per page"] = 5
    ) -> Annotated[str, "JSON string containing search results"]:
        """Search GitHub code with the given query."""
        print(f"Executing search_code(query='{query}', page={page}, per_page={per_page})...")

        url = f"{self.base_url}/search/code"
        params = {
            "q": query,
            "page": page,
            "per_page": per_page,
        }

        response = requests.get(url, headers=self._get_headers(), params=params, timeout=HTTP_TIMEOUT_SECONDS)
        if response.status_code != 200:
            print(f"Error searching code: {response.status_code}")
            print(response.text)
            return json.dumps({"items": [], "error": response.text})

        result_data = response.json()

        # Format results with content previews
        formatted_results = []
        for item in result_data.get("items", []):
            repo = item.get("repository", {}).get("full_name", "")
            path = item.get("path", "")
            url = item.get("html_url", "")

            # Try to get the file content - don't specify a ref to try multiple branches
            content = self.get_file_content(repo, path, ref=None)
            content_preview = content[:1000] + "..." if len(content) > 1000 else content

            formatted_results.append({
                "repo": repo,
                "path": path,
                "url": url,
                "content_preview": content_preview
            })

        return json.dumps({
            "status": "success", 
            "total_count": result_data.get("total_count", 0),
            "items": formatted_results
        })

    @kernel_function(
        description="Get contents of a file from GitHub",
        name="get_file_content"
    )
    def get_file_content(
        self,
        repo: Annotated[str, "Repository name (owner/repo)"],
        path: Annotated[str, "File path within the repository"],
        ref: Annotated[str, "The branch, tag, or commit SHA"] = None
    ) -> Annotated[str, "The content of the file"]:
        """Get contents of a file from GitHub."""
        print(f"Executing get_file_content(repo='{repo}', path='{path}', ref='{ref}')...")

        # Try multiple common branch names if no ref is specified
        branches_to_try = [ref] if ref else ["main", "master", "develop", "dev"]
        branches_to_try = [b for b in branches_to_try if b]  # Remove None values

        for branch in branches_to_try:
            url = f"{self.base_url}/repos/{repo}/contents/{path}"
            params = {"ref": branch} if branch else {}

            try:
                response = requests.get(url, headers=self._get_headers(), params=params, timeout=HTTP_TIMEOUT_SECONDS)

                if response.status_code == 200:
                    content_data = response.json()
                    if content_data.get("encoding") == "base64":
                        try:
                            return base64.b64decode(content_data["content"]).decode("utf-8")
                        except Exception as exception:  #pylint: disable=broad-except
                            print(f"Error decoding content: {exception}")
                            continue
                else:
                    # Only show error for the last branch attempt
                    if branch == branches_to_try[-1]:
                        print(f"Error getting file content: {response.status_code}")
                        print(response.text)
            except Exception as exception:  #pylint: disable=broad-except
                # Only show error for the last branch attempt
                if branch == branches_to_try[-1]:
                    print(f"Exception while getting file content: {exception}")

        # If we get here, we couldn't find the file on any branch
        return f"[Could not retrieve content for {repo}/{path}]"

    @kernel_function(
        description="Create a GitHub Gist with the provided content",
        name="create_gist"
    )
    def create_gist(
        self,
        description: Annotated[str, "The description/title for the GitHub Gist"],
        content: Annotated[str, "The markdown content of the report to publish"],
        public: Annotated[bool, "Whether the gist should be public"] = False
    ) -> Annotated[str, "The URL of the created Gist or error message"]:
        """Create a GitHub Gist with the provided content."""
        print(f"Executing create_gist(description='{description}', public={public})...")

        if not self.token:
            return "Error: GitHub token is required to create gists."

        url = f"{self.base_url}/gists"
        payload = {
            "description": description,
            "public": public,
            "files": {
                "report.md": {
                    "content": content
                }
            }
        }

        response = requests.post(url, headers=self._get_headers(), json=payload, timeout=HTTP_TIMEOUT_SECONDS)
        if response.status_code != 201:
            print(f"Error creating gist: {response.status_code}")
            print(response.text)
            return f"Error creating gist: {response.text}"

        return response.json()["html_url"]
