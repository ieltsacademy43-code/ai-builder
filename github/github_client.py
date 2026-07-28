"""
GitHub API client for AI Builder.
Integrates with GitHub REST API for repository management.
"""

import json
from datetime import datetime
from core.logger import get_logger
from config.settings import get_config

log = get_logger("github")

GITHUB_API_BASE = "https://api.github.com"


class GitHubClient:
    """GitHub REST API client."""

    def __init__(self, token=None, username=None):
        self.config = get_config()
        self.token = token or self.config.get("github.token", "")
        self.username = username or self.config.get("github.username", "")

        try:
            import requests
            self.requests = requests
        except ImportError:
            self.requests = None
            log.warning("requests library not installed. GitHub features will be limited.")

        self.headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "AI-Builder",
        }
        if self.token:
            self.headers["Authorization"] = f"token {self.token}"

    def is_authenticated(self):
        """Check if the client has a token configured."""
        return bool(self.token)

    def _request(self, method, endpoint, data=None, params=None):
        """Make an API request."""
        if not self.requests:
            return {"error": "requests library not installed. Run: pip install requests"}

        url = f"{GITHUB_API_BASE}{endpoint}"
        try:
            response = self.requests.request(
                method,
                url,
                headers=self.headers,
                json=data,
                params=params,
                timeout=30,
            )

            if response.status_code == 200:
                return response.json()
            elif response.status_code == 201:
                return response.json()
            elif response.status_code == 204:
                return {"success": True}
            else:
                error_msg = f"GitHub API error {response.status_code}: {response.text}"
                log.error(error_msg)
                return {"error": error_msg, "status_code": response.status_code}

        except Exception as e:
            log.error(f"GitHub API request failed: {e}")
            return {"error": str(e)}

    def get_user(self):
        """Get authenticated user info."""
        if not self.is_authenticated():
            return {"error": "No GitHub token configured. Set github.token in config."}
        return self._request("GET", "/user")

    def list_repos(self, per_page=30):
        """List repositories for the authenticated user."""
        if not self.is_authenticated():
            return {"error": "Not authenticated"}
        return self._request("GET", "/user/repos", params={"per_page": per_page, "sort": "updated"})

    def get_repo(self, owner, repo):
        """Get repository info."""
        return self._request("GET", f"/repos/{owner}/{repo}")

    def create_repo(self, name, description="", private=True, auto_init=True):
        """Create a new repository."""
        if not self.is_authenticated():
            return {"error": "Not authenticated"}
        data = {
            "name": name,
            "description": description,
            "private": private,
            "auto_init": auto_init,
        }
        return self._request("POST", "/user/repos", data=data)

    def delete_repo(self, owner, repo):
        """Delete a repository."""
        if not self.is_authenticated():
            return {"error": "Not authenticated"}
        return self._request("DELETE", f"/repos/{owner}/{repo}")

    def list_branches(self, owner, repo):
        """List branches in a repository."""
        return self._request("GET", f"/repos/{owner}/{repo}/branches")

    def list_commits(self, owner, repo, per_page=10):
        """List recent commits in a repository."""
        return self._request("GET", f"/repos/{owner}/{repo}/commits",
                             params={"per_page": per_page})

    def get_file(self, owner, repo, path, ref=None):
        """Get file contents from a repository."""
        endpoint = f"/repos/{owner}/{repo}/contents/{path}"
        params = {}
        if ref:
            params["ref"] = ref
        return self._request("GET", endpoint, params=params)

    def create_issue(self, owner, repo, title, body="", labels=None):
        """Create an issue in a repository."""
        if not self.is_authenticated():
            return {"error": "Not authenticated"}
        data = {"title": title, "body": body}
        if labels:
            data["labels"] = labels
        return self._request("POST", f"/repos/{owner}/{repo}/issues", data=data)

    def list_issues(self, owner, repo, state="open", per_page=30):
        """List issues in a repository."""
        return self._request("GET", f"/repos/{owner}/{repo}/issues",
                             params={"state": state, "per_page": per_page})

    def create_pull_request(self, owner, repo, title, head, base, body=""):
        """Create a pull request."""
        if not self.is_authenticated():
            return {"error": "Not authenticated"}
        data = {"title": title, "head": head, "base": base, "body": body}
        return self._request("POST", f"/repos/{owner}/{repo}/pulls", data=data)

    def list_pull_requests(self, owner, repo, state="open"):
        """List pull requests in a repository."""
        return self._request("GET", f"/repos/{owner}/{repo}/pulls", params={"state": state})

    def get_readme(self, owner, repo):
        """Get the README of a repository."""
        return self._request("GET", f"/repos/{owner}/{repo}/readme")

    def search_repos(self, query, per_page=10):
        """Search public repositories."""
        return self._request("GET", "/search/repositories",
                             params={"q": query, "per_page": per_page})

    def get_rate_limit(self):
        """Get API rate limit info."""
        return self._request("GET", "/rate_limit")