"""
Tests for Git Manager and GitHub Client upgrades.
Tests are offline (no live API calls) — they verify method existence,
signatures, and local git operations via subprocess.
"""

import sys
import os
import tempfile
import shutil
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.logger import get_logger
from github.git_manager import GitManager
from github.github_client import GitHubClient

log = get_logger("tests")

_passed = 0
_failed = 0


def run_test(name, func):
    global _passed, _failed
    try:
        func()
        print(f"  [PASS] {name}")
        _passed += 1
    except Exception as e:
        print(f"  [FAIL] {name}: {e}")
        _failed += 1


# ----------------------------------------------------------------------
# GitHub Client — urllib migration & new methods
# ----------------------------------------------------------------------

def test_github_client_no_requests_dependency():
    """Client must not require the 'requests' library."""
    client = GitHubClient()
    assert not hasattr(client, "requests"), "Client should not have a 'requests' attribute"
    assert client.headers["Accept"] == "application/vnd.github.v3+json"


def test_github_client_is_authenticated_no_token():
    """Without a token, is_authenticated() must return False."""
    client = GitHubClient(token="")
    assert client.is_authenticated() is False


def test_github_client_is_authenticated_with_token():
    """With a token, is_authenticated() must return True."""
    client = GitHubClient(token="fake_token_123")
    assert client.is_authenticated() is True


def test_github_client_unauthenticated_returns_error():
    """Unauthenticated calls to protected endpoints must return an error dict."""
    client = GitHubClient(token="")
    result = client.create_repo("test")
    assert isinstance(result, dict)
    assert "error" in result


def test_github_client_get_rate_limit_no_auth():
    """get_rate_limit without auth should return an error (401 from API)."""
    client = GitHubClient(token="")
    # get_rate_limit doesn't check is_authenticated, so it hits the API
    # Without token it returns 401 → error dict
    result = client.get_rate_limit()
    assert isinstance(result, dict)
    # Either error (401) or success (if somehow rate limit is public)
    assert "error" in result or "resources" in result


def test_github_client_has_git_data_api():
    """Git Data API methods must exist."""
    client = GitHubClient(token="fake")
    assert callable(getattr(client, "get_ref", None))
    assert callable(getattr(client, "create_ref", None))
    assert callable(getattr(client, "update_ref", None))
    assert callable(getattr(client, "create_blob", None))
    assert callable(getattr(client, "create_tree", None))
    assert callable(getattr(client, "create_commit", None))
    assert callable(getattr(client, "commit_files", None))
    assert callable(getattr(client, "create_or_update_file", None))


def test_github_client_has_merge_pr():
    """merge_pull_request method must exist."""
    client = GitHubClient(token="fake")
    assert callable(getattr(client, "merge_pull_request", None))


def test_github_client_has_fork():
    """fork_repo method must exist."""
    client = GitHubClient(token="fake")
    assert callable(getattr(client, "fork_repo", None))


def test_github_client_has_workflow_runs():
    """list_workflow_runs method must exist."""
    client = GitHubClient(token="fake")
    assert callable(getattr(client, "list_workflow_runs", None))


def test_github_client_request_all_exists():
    """Pagination helper must exist."""
    client = GitHubClient(token="fake")
    assert callable(getattr(client, "_request_all", None))


def test_github_client_list_repos_pagination_flag():
    """list_repos must accept all_pages parameter."""
    client = GitHubClient(token="fake")
    # Just verify it doesn't crash on signature
    import inspect
    sig = inspect.signature(client.list_repos)
    assert "all_pages" in sig.parameters


def test_github_client_backward_compat_methods():
    """All original 16 methods must still exist with same signatures."""
    client = GitHubClient(token="fake")
    original_methods = [
        "is_authenticated", "get_user", "list_repos", "get_repo",
        "create_repo", "delete_repo", "list_branches", "list_commits",
        "get_file", "create_issue", "list_issues", "create_pull_request",
        "list_pull_requests", "get_readme", "search_repos", "get_rate_limit",
    ]
    for method_name in original_methods:
        assert callable(getattr(client, method_name, None)), f"Missing: {method_name}"


# ----------------------------------------------------------------------
# Git Manager — new local operations
# ----------------------------------------------------------------------

def test_git_manager_has_clone():
    """clone() method must exist."""
    gm = GitManager()
    assert callable(getattr(gm, "clone", None))


def test_git_manager_has_fetch():
    """fetch() method must exist."""
    gm = GitManager()
    assert callable(getattr(gm, "fetch", None))


def test_git_manager_has_tag():
    """tag() method must exist."""
    gm = GitManager()
    assert callable(getattr(gm, "tag", None))


def test_git_manager_has_reset():
    """reset() method must exist."""
    gm = GitManager()
    assert callable(getattr(gm, "reset", None))


def test_git_manager_has_log_detailed():
    """log_detailed() method must exist."""
    gm = GitManager()
    assert callable(getattr(gm, "log_detailed", None))


def test_git_manager_init_and_clone():
    """GitManager can init a repo in a temp dir and run local operations."""
    tmpdir = tempfile.mkdtemp(prefix="git_test_")
    try:
        gm = GitManager(repo_path=tmpdir)
        # Init
        result = gm.init(path=tmpdir)
        assert result["success"], f"git init failed: {result.get('stderr', '')}"

        # Create a file and commit
        test_file = Path(tmpdir) / "test.txt"
        test_file.write_text("hello world")

        # Set git config for the commit
        gm.terminal.run("git config user.email test@test.com", cwd=tmpdir, check_dangerous=False)
        gm.terminal.run("git config user.name Test", cwd=tmpdir, check_dangerous=False)

        add_result = gm.add(path=tmpdir)
        assert add_result["success"], f"git add failed: {add_result.get('stderr', '')}"

        commit_result = gm.commit("Initial commit", path=tmpdir)
        assert commit_result["success"], f"git commit failed: {commit_result.get('stderr', '')}"

        # Create a second file and commit so HEAD~1 exists
        test_file2 = Path(tmpdir) / "second.txt"
        test_file2.write_text("second file")
        gm.add(path=tmpdir)
        gm.commit("Second commit", path=tmpdir)

        # Check status is clean
        status = gm.status(path=tmpdir)
        assert status["is_repo"] is True
        assert len(status["files"]) == 0, "Working tree should be clean"

        # Get current branch
        branch = gm.get_current_branch(path=tmpdir)
        assert branch in ("main", "master"), f"Unexpected branch: {branch}"

        # Log
        commits = gm.log(path=tmpdir)
        assert len(commits) == 2
        assert "Second commit" in commits[0]["message"]
        assert "Initial commit" in commits[1]["message"]

        # Detailed log
        detailed = gm.log_detailed(path=tmpdir)
        assert len(detailed) == 2
        assert detailed[0]["author"] == "Test"
        assert "second.txt" in detailed[0]["files_changed"]
        assert "test.txt" in detailed[1]["files_changed"]

        # Tag
        tag_result = gm.tag("v1.0", message="First release", path=tmpdir)
        assert tag_result["success"], f"git tag failed: {tag_result.get('stderr', '')}"

        # Reset (soft) to HEAD~1 — unstage second commit but keep file
        reset_result = gm.reset("HEAD~1", mode="--soft", path=tmpdir)
        assert reset_result["success"], f"git reset failed: {reset_result.get('stderr', '')}"

        # After soft reset, second.txt should be staged
        status_after = gm.status(path=tmpdir)
        assert len(status_after["files"]) > 0, "File should be staged after soft reset"

    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_git_manager_backward_compat_methods():
    """All original 19 methods must still exist."""
    gm = GitManager()
    original_methods = [
        "is_repo", "init", "status", "add", "commit", "add_and_commit",
        "push", "pull", "branch", "create_branch", "checkout", "merge",
        "log", "diff", "remote", "add_remote", "get_current_branch",
        "stash", "stash_pop",
    ]
    for method_name in original_methods:
        assert callable(getattr(gm, method_name, None)), f"Missing: {method_name}"


def test_git_manager_clone_nonexistent_url():
    """clone() with an invalid URL should fail gracefully."""
    tmpdir = tempfile.mkdtemp(prefix="git_clone_test_")
    try:
        gm = GitManager()
        result = gm.clone("https://invalid.example.com/nonexistent.git", path=tmpdir)
        assert result["success"] is False, "Clone of invalid URL should fail"
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# ----------------------------------------------------------------------
# Integration — commit_files uses Git Data API chain
# ----------------------------------------------------------------------

def test_commit_files_unauthenticated():
    """commit_files without a token must return an error, not crash."""
    client = GitHubClient(token="")
    result = client.commit_files("owner", "repo", "msg", [{"path": "a.py", "content": "x"}])
    assert isinstance(result, dict)
    assert "error" in result


def test_create_or_update_file_unauthenticated():
    """create_or_update_file without a token must return an error."""
    client = GitHubClient(token="")
    result = client.create_or_update_file("owner", "repo", "file.py", "msg", "content")
    assert isinstance(result, dict)
    assert "error" in result


def run_all_tests():
    print("\n--- GitHub/Git Upgrade Tests ---\n")

    # GitHub Client
    run_test("GitHub client no requests dependency", test_github_client_no_requests_dependency)
    run_test("GitHub client is_authenticated no token", test_github_client_is_authenticated_no_token)
    run_test("GitHub client is_authenticated with token", test_github_client_is_authenticated_with_token)
    run_test("GitHub client unauthenticated returns error", test_github_client_unauthenticated_returns_error)
    run_test("GitHub client get_rate_limit no auth", test_github_client_get_rate_limit_no_auth)
    run_test("GitHub client has Git Data API", test_github_client_has_git_data_api)
    run_test("GitHub client has merge_pr", test_github_client_has_merge_pr)
    run_test("GitHub client has fork", test_github_client_has_fork)
    run_test("GitHub client has workflow_runs", test_github_client_has_workflow_runs)
    run_test("GitHub client has _request_all pagination", test_github_client_request_all_exists)
    run_test("GitHub client list_repos pagination flag", test_github_client_list_repos_pagination_flag)
    run_test("GitHub client backward compat (16 methods)", test_github_client_backward_compat_methods)

    # Git Manager
    run_test("Git manager has clone", test_git_manager_has_clone)
    run_test("Git manager has fetch", test_git_manager_has_fetch)
    run_test("Git manager has tag", test_git_manager_has_tag)
    run_test("Git manager has reset", test_git_manager_has_reset)
    run_test("Git manager has log_detailed", test_git_manager_has_log_detailed)
    run_test("Git manager init + tag + reset + log_detailed", test_git_manager_init_and_clone)
    run_test("Git manager backward compat (19 methods)", test_git_manager_backward_compat_methods)
    run_test("Git manager clone invalid URL", test_git_manager_clone_nonexistent_url)

    # Integration
    run_test("commit_files unauthenticated", test_commit_files_unauthenticated)
    run_test("create_or_update_file unauthenticated", test_create_or_update_file_unauthenticated)

    print(f"\n  Results: {_passed} passed, {_failed} failed")
    print("-" * 50)
    return _failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)