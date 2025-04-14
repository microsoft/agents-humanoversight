# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for license information.

"""
GitHub Plugin for Semantic Kernel
"""

from typing import Dict, Any

import base64
import os
import requests

from .constants import HTTP_TIMEOUT_SECONDS

class GitHubAPI:
    """
    Plugin for interacting with GitHub API
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

    def search_code(self, query: str, page: int = 1, per_page: int = 5) -> Dict[str, Any]:
        """Search GitHub code with the given query."""
        url = f"{self.base_url}/search/code"
        params = {
            "q": query,
            "page": page,
            "per_page": per_page,
            "timeout": HTTP_TIMEOUT_SECONDS,
        }
        response = requests.get(url, headers=self._get_headers(), params=params, timeout=HTTP_TIMEOUT_SECONDS)
        if response.status_code != 200:
            print(f"Error searching code: {response.status_code}")
            print(response.text)
            return {"items": [], "error": response.text}
        return response.json()

    def get_file_content(self, repo: str, path: str, ref: str = "main") -> str:
        """Get contents of a file from GitHub."""
        url = f"{self.base_url}/repos/{repo}/contents/{path}"
        params = {"ref": ref}
        response = requests.get(url, headers=self._get_headers(), params=params, timeout=HTTP_TIMEOUT_SECONDS)
        if response.status_code != 200:
            print(f"Error getting file content: {response.status_code}")
            print(response.text)
            return ""
        content_data = response.json()
        if content_data.get("encoding") == "base64":
            return base64.b64decode(content_data["content"]).decode("utf-8")
        return ""

    def create_gist(self, description: str, content: str, public: bool = False) -> str:
        """Create a GitHub Gist with the provided content."""
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
