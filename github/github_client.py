"""
GitHub API client for AI Builder.
Integrates with GitHub REST API for repository management.
"""

import json
import urllib.request
import urllib.error
import urllib.parse
import time
import base64
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

        self.headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "AI-Builder",
        }
        if self.token:
            self.headers["Authorization"] = f"token {self.token}"

    def is_authenticated(self):
        """Check if the client has a token configured."""
        return bool(self.token)

    def _request(self, method, endpoint, data=None, params=None, raw_response=False):
        """Make an API request using urllib (zero external dependencies).

        Returns parsed JSON for 200/201, {"success": True} for 204,
        or {"error": ..., "status_code": ...} on failure.
        If raw_response=True, returns {"status_code", "content", "headers"}.
        Retries on rate-limit (403) and server errors (5xx).
        """
        url = f"{GITHUB_API_BASE}{endpoint}"
        if params:
            url = f"{url}?{urllib.parse.urlencode(params)}"

        body = None
        headers = dict(self.headers)
        if data is not None:
            body = json.dumps(data).encode("utf-8")
            headers["Content-Type"] = "application/json"

        max_retries = 3
        for attempt in range(max_retries):
            try:
                req = urllib.request.Request(url, data=body, method=method, headers=headers)
                with urllib.request.urlopen(req, timeout=30) as response:
                    status = response.status
                    content = response.read().decode("utf-8")
                    resp_headers = dict(response.headers)

                    if raw_response:
                        return {"status_code": status, "content": content, "headers": resp_headers}

                    if status in (200, 201):
                        return json.loads(content) if content else {}
                    elif status == 204:
                        return {"success": True}
                    else:
                        return {"_status_code": status, "content": content}

            except urllib.error.HTTPError as e:
                status = e.code
                body_text = ""
                try:
                    body_text = e.read().decode("utf-8", errors="replace")
                except Exception:
                    pass

                if status == 403 and attempt < max_retries - 1:
                    reset = e.headers.get("X-RateLimit-Reset")
                    if reset:
                        wait = max(int(float(reset)) - int(time.time()), 1)
                        wait = min(wait, 60)
                        log.warning(f"Rate limited, waiting {wait}s (attempt {attempt+1}/{max_retries})")
                        time.sleep(wait)
                        continue

                if 500 <= status < 600 and attempt < max_retries - 1:
                    log.warning(f"Server error {status}, retrying (attempt {attempt+1}/{max_retries})")
                    time.sleep(2 ** attempt)
                    continue

                error_msg = f"GitHub API error {status}: {body_text}"
                log.error(error_msg)
                return {"error": error_msg, "status_code": status}

            except Exception as e:
                log.error(f"GitHub API request failed: {e}")
                return {"error": str(e)}

        return {"error": "Max retries exceeded"}

    def _request_all(self, endpoint, params=None, per_page=100, max_pages=10):
        """Fetch all pages of a list endpoint by iterating pages.

        Returns a flat list of items across all fetched pages.
        """
        all_items = []
        base_params = dict(params or {})
        base_params["per_page"] = per_page

        for page in range(1, max_pages + 1):
            base_params["page"] = page
            result = self._request("GET", endpoint, params=base_params)
            if isinstance(result, dict) and "error" in result:
                return result
            if not result:
                break
            all_items.extend(result)
            if len(result) < per_page:
                break

        return all_items

    def get_user(self):
        """Get authenticated user info."""
        if not self.is_authenticated():
            return {"error": "No GitHub token configured. Set github.token in config."}
        return self._request("GET", "/user")

    def list_repos(self, per_page=30, all_pages=False):
        """List repositories for the authenticated user.

        If all_pages=True, fetches up to 10 pages (1000 repos) via pagination.
        """
        if not self.is_authenticated():
            return {"error": "Not authenticated"}
        params = {"sort": "updated"}
        if all_pages:
            return self._request_all("/user/repos", params=params, per_page=100, max_pages=10)
        params["per_page"] = per_page
        return self._request("GET", "/user/repos", params=params)

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

    # ------------------------------------------------------------------
    # Git Data API — atomic multi-file commits
    # ------------------------------------------------------------------

    def get_ref(self, owner, repo, ref="heads/main"):
        """Get a Git reference (e.g. 'heads/main', 'tags/v1')."""
        return self._request("GET", f"/repos/{owner}/{repo}/git/refs/{ref}")

    def create_ref(self, owner, repo, ref, sha):
        """Create a new Git reference. ref is e.g. 'heads/feature'."""
        if not self.is_authenticated():
            return {"error": "Not authenticated"}
        data = {"ref": f"refs/{ref}", "sha": sha}
        return self._request("POST", f"/repos/{owner}/{repo}/git/refs", data=data)

    def update_ref(self, owner, repo, ref, sha, force=False):
        """Update a Git reference to point to a new commit SHA.

        ref is e.g. 'heads/main'. Set force=True for non-fast-forward updates.
        """
        if not self.is_authenticated():
            return {"error": "Not authenticated"}
        data = {"sha": sha, "force": force}
        return self._request("PATCH", f"/repos/{owner}/{repo}/git/refs/{ref}", data=data)

    def create_blob(self, owner, repo, content, encoding="utf-8"):
        """Create a blob (file content) in the repository."""
        if not self.is_authenticated():
            return {"error": "Not authenticated"}
        data = {"content": content, "encoding": encoding}
        return self._request("POST", f"/repos/{owner}/{repo}/git/blobs", data=data)

    def create_tree(self, owner, repo, tree_entries, base_tree=None):
        """Create a tree object from a list of entries.

        Each entry: {"path": str, "mode": "100644", "type": "blob",
                     "sha": <blob_sha> or "content": <inline_content>}.
        If base_tree is provided, entries are layered on top of it.
        """
        if not self.is_authenticated():
            return {"error": "Not authenticated"}
        processed = []
        for entry in tree_entries:
            if "content" in entry and "sha" not in entry:
                blob = self.create_blob(owner, repo, entry["content"])
                if isinstance(blob, dict) and "error" in blob:
                    return blob
                entry = {k: v for k, v in entry.items() if k != "content"}
                entry["sha"] = blob.get("sha")
            processed.append(entry)
        data = {"tree": processed}
        if base_tree:
            data["base_tree"] = base_tree
        return self._request("POST", f"/repos/{owner}/{repo}/git/trees", data=data)

    def create_commit(self, owner, repo, message, tree_sha, parent_shas):
        """Create a commit object pointing to tree_sha with parent_shas."""
        if not self.is_authenticated():
            return {"error": "Not authenticated"}
        data = {
            "message": message,
            "tree": tree_sha,
            "parents": parent_shas if isinstance(parent_shas, list) else [parent_shas],
        }
        return self._request("POST", f"/repos/{owner}/{repo}/git/commits", data=data)

    def create_or_update_file(self, owner, repo, path, message, content, branch="main", sha=None):
        """Create or update a single file via the Contents API.

        If updating an existing file, pass the current blob SHA as `sha`.
        """
        if not self.is_authenticated():
            return {"error": "Not authenticated"}
        encoded = base64.b64encode(content.encode("utf-8")).decode("utf-8")
        data = {"message": message, "content": encoded, "branch": branch}
        if sha:
            data["sha"] = sha
        return self._request("PUT", f"/repos/{owner}/{repo}/contents/{path}", data=data)

    def commit_files(self, owner, repo, message, files, branch="main"):
        """Atomically commit multiple files via the Git Data API.

        files: list of {"path": str, "content": str}
        Returns the updated ref object or {"error": ...}.
        """
        if not self.is_authenticated():
            return {"error": "Not authenticated"}

        # 1. Get current branch head commit
        ref = self.get_ref(owner, repo, f"heads/{branch}")
        if isinstance(ref, dict) and "error" in ref:
            return ref
        head_sha = ref["object"]["sha"]

        # 2. Get the tree SHA of the head commit
        head_commit = self._request("GET", f"/repos/{owner}/{repo}/git/commits/{head_sha}")
        if isinstance(head_commit, dict) and "error" in head_commit:
            return head_commit
        base_tree = head_commit["tree"]["sha"]

        # 3. Create a new tree with all file changes
        tree_entries = [
            {"path": f["path"], "mode": "100644", "type": "blob", "content": f["content"]}
            for f in files
        ]
        tree = self.create_tree(owner, repo, tree_entries, base_tree=base_tree)
        if isinstance(tree, dict) and "error" in tree:
            return tree
        tree_sha = tree["sha"]

        # 4. Create the commit
        commit = self.create_commit(owner, repo, message, tree_sha, [head_sha])
        if isinstance(commit, dict) and "error" in commit:
            return commit
        new_commit_sha = commit["sha"]

        # 5. Update the branch ref
        return self.update_ref(owner, repo, f"heads/{branch}", new_commit_sha)

    # ------------------------------------------------------------------
    # Pull Requests — merge
    # ------------------------------------------------------------------

    def merge_pull_request(self, owner, repo, pr_number, merge_method="merge",
                           commit_title=None, commit_message=None, sha=None):
        """Merge a pull request.

        merge_method: 'merge', 'squash', or 'rebase'.
        """
        if not self.is_authenticated():
            return {"error": "Not authenticated"}
        data = {"merge_method": merge_method}
        if commit_title:
            data["commit_title"] = commit_title
        if commit_message:
            data["commit_message"] = commit_message
        if sha:
            data["sha"] = sha
        return self._request("PUT", f"/repos/{owner}/{repo}/pulls/{pr_number}/merge", data=data)

    # ------------------------------------------------------------------
    # Repository — fork
    # ------------------------------------------------------------------

    def fork_repo(self, owner, repo, organization=None):
        """Fork a repository. If organization is set, forks into that org."""
        if not self.is_authenticated():
            return {"error": "Not authenticated"}
        data = {}
        if organization:
            data["organization"] = organization
        return self._request("POST", f"/repos/{owner}/{repo}/forks", data=data)

    # ------------------------------------------------------------------
    # GitHub Actions — CI/CD status
    # ------------------------------------------------------------------

    def list_workflow_runs(self, owner, repo, per_page=10):
        """List recent GitHub Actions workflow runs for a repository."""
        return self._request("GET", f"/repos/{owner}/{repo}/actions/runs",
                             params={"per_page": per_page})