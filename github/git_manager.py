"""
Git manager for AI Builder.
Manages git operations via subprocess.
"""

import os
from pathlib import Path
from datetime import datetime
from core.logger import get_logger
from config.settings import get_config
from terminal.runner import TerminalRunner

log = get_logger("github")


class GitManager:
    """Manages local git repository operations."""

    def __init__(self, repo_path=None):
        self.config = get_config()
        self.repo_path = repo_path or str(Path.cwd())
        self.terminal = TerminalRunner(cwd=self.repo_path)

    def is_repo(self, path=None):
        """Check if a path is inside a git repository."""
        check_path = path or self.repo_path
        result = self.terminal.run(
            "git rev-parse --git-dir",
            cwd=check_path,
            check_dangerous=False,
            timeout=10,
        )
        return result["success"]

    def init(self, path=None):
        """Initialize a new git repository."""
        init_path = path or self.repo_path
        result = self.terminal.run("git init", cwd=init_path, check_dangerous=False)
        if result["success"]:
            log.info(f"Initialized git repo at {init_path}")
        return result

    def status(self, path=None):
        """Get repository status."""
        result = self.terminal.run(
            "git status --porcelain",
            cwd=path or self.repo_path,
            check_dangerous=False,
            timeout=10,
        )
        if not result["success"]:
            return {"is_repo": False, "files": []}

        files = []
        for line in result["stdout"].splitlines():
            if line.strip():
                status_code = line[:2].strip()
                file_path = line[3:].strip()
                files.append({"status": status_code, "file": file_path})

        return {"is_repo": True, "files": files, "raw": result["stdout"]}

    def add(self, files=None, path=None):
        """Stage files. If files is None, stages all changes."""
        if files is None:
            cmd = "git add -A"
        elif isinstance(files, list):
            cmd = "git add " + " ".join(files)
        else:
            cmd = f"git add {files}"

        result = self.terminal.run(cmd, cwd=path or self.repo_path, check_dangerous=False)
        return result

    def commit(self, message, path=None, allow_empty=False):
        """Commit staged changes with a message."""
        if not message:
            return {"success": False, "stderr": "Commit message is required."}

        cmd = f"git commit -m {repr(message)}"
        if allow_empty:
            cmd += " --allow-empty"

        result = self.terminal.run(cmd, cwd=path or self.repo_path, check_dangerous=False)
        if result["success"]:
            log.info(f"Committed: {message}")
        return result

    def add_and_commit(self, message, files=None, path=None):
        """Stage and commit in one step."""
        add_result = self.add(files, path)
        if not add_result["success"]:
            return add_result
        return self.commit(message, path)

    def push(self, remote="origin", branch=None, path=None, force=False):
        """Push changes to remote."""
        from terminal.runner import DANGEROUS_COMMANDS
        cmd = f"git push {remote}"
        if branch:
            cmd += f" {branch}"
        if force:
            # Force push is dangerous — bypass the check but log it
            cmd += " --force"
            log.warning("Force push requested — use with caution!")

        result = self.terminal.run(cmd, cwd=path or self.repo_path,
                                   check_dangerous=False, timeout=120)
        return result

    def pull(self, remote="origin", branch=None, path=None):
        """Pull changes from remote."""
        cmd = f"git pull {remote}"
        if branch:
            cmd += f" {branch}"

        result = self.terminal.run(cmd, cwd=path or self.repo_path,
                                   check_dangerous=False, timeout=120)
        return result

    def branch(self, path=None):
        """List all branches."""
        result = self.terminal.run(
            "git branch -a",
            cwd=path or self.repo_path,
            check_dangerous=False,
            timeout=10,
        )
        if not result["success"]:
            return []

        branches = []
        for line in result["stdout"].splitlines():
            line = line.strip()
            if line:
                current = line.startswith("*")
                name = line.lstrip("* ").strip()
                branches.append({"name": name, "current": current})
        return branches

    def create_branch(self, branch_name, path=None):
        """Create and checkout a new branch."""
        result = self.terminal.run(
            f"git checkout -b {branch_name}",
            cwd=path or self.repo_path,
            check_dangerous=False,
            timeout=10,
        )
        return result

    def checkout(self, branch_name, path=None):
        """Checkout an existing branch."""
        result = self.terminal.run(
            f"git checkout {branch_name}",
            cwd=path or self.repo_path,
            check_dangerous=False,
            timeout=10,
        )
        return result

    def merge(self, branch_name, path=None):
        """Merge a branch into the current branch."""
        result = self.terminal.run(
            f"git merge {branch_name}",
            cwd=path or self.repo_path,
            check_dangerous=False,
            timeout=30,
        )
        return result

    def log(self, count=10, path=None):
        """Get recent commit log."""
        result = self.terminal.run(
            f"git log --oneline -{count}",
            cwd=path or self.repo_path,
            check_dangerous=False,
            timeout=10,
        )
        if not result["success"]:
            return []

        commits = []
        for line in result["stdout"].splitlines():
            parts = line.split(" ", 1)
            if len(parts) == 2:
                commits.append({"hash": parts[0], "message": parts[1]})
        return commits

    def diff(self, path=None, staged=False):
        """Get diff of changes."""
        cmd = "git diff"
        if staged:
            cmd += " --cached"
        result = self.terminal.run(cmd, cwd=path or self.repo_path,
                                   check_dangerous=False, timeout=15)
        return result

    def remote(self, path=None):
        """List configured remotes."""
        result = self.terminal.run(
            "git remote -v",
            cwd=path or self.repo_path,
            check_dangerous=False,
            timeout=10,
        )
        if not result["success"]:
            return []
        return result["stdout"].splitlines()

    def add_remote(self, name, url, path=None):
        """Add a remote repository."""
        result = self.terminal.run(
            f"git remote add {name} {url}",
            cwd=path or self.repo_path,
            check_dangerous=False,
            timeout=10,
        )
        return result

    def get_current_branch(self, path=None):
        """Get the current branch name."""
        result = self.terminal.run(
            "git rev-parse --abbrev-ref HEAD",
            cwd=path or self.repo_path,
            check_dangerous=False,
            timeout=10,
        )
        if result["success"]:
            return result["stdout"].strip()
        return None

    def stash(self, path=None):
        """Stash current changes."""
        return self.terminal.run("git stash", cwd=path or self.repo_path,
                                  check_dangerous=False, timeout=10)

    def stash_pop(self, path=None):
        """Pop stashed changes."""
        return self.terminal.run("git stash pop", cwd=path or self.repo_path,
                                  check_dangerous=False, timeout=10)