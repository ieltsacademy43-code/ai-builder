"""
Terminal command runner for AI Builder.
Safely executes shell commands with timeout and output capture.
"""

import os
import shlex
import subprocess
from pathlib import Path
from datetime import datetime

from core.logger import get_logger
from config.settings import get_config
from utils.helpers import is_termux

log = get_logger("terminal")


# Commands that are considered dangerous and require explicit confirmation
DANGEROUS_COMMANDS = [
    "rm -rf", "rmdir", "mkfs", "dd if=", "shutdown", "reboot",
    "> /dev/sd", "chmod -R 777", "chown -R", "kill -9",
    "git push --force", "git reset --hard", ":(){:|:&};:",
]


class TerminalRunner:
    """Runs shell commands safely with output capture."""

    def __init__(self, cwd=None, timeout=None):
        self.config = get_config()
        self.cwd = cwd or str(Path.cwd())
        self.timeout = timeout or self.config.get("terminal_timeout", 60)
        self.is_termux = is_termux()

    def run(self, command, cwd=None, timeout=None, check_dangerous=True, shell_mode=False):
        """
        Execute a command and return structured output.

        Returns dict: {command, returncode, stdout, stderr, success, duration, cwd}
        """
        if check_dangerous and self._is_dangerous(command):
            return {
                "command": command,
                "returncode": -1,
                "stdout": "",
                "stderr": "BLOCKED: Dangerous command detected. Set check_dangerous=False to override.",
                "success": False,
                "duration": 0,
                "cwd": cwd or self.cwd,
                "blocked": True,
            }

        work_dir = cwd or self.cwd
        timeout = timeout or self.timeout
        start = datetime.now()

        log.info(f"Running: {command} (cwd={work_dir})")

        try:
            if shell_mode:
                proc = subprocess.run(
                    command,
                    shell=True,
                    cwd=work_dir,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                )
            else:
                args = shlex.split(command)
                proc = subprocess.run(
                    args,
                    cwd=work_dir,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                )

            duration = (datetime.now() - start).total_seconds()
            success = proc.returncode == 0

            result = {
                "command": command,
                "returncode": proc.returncode,
                "stdout": proc.stdout.strip(),
                "stderr": proc.stderr.strip(),
                "success": success,
                "duration": round(duration, 3),
                "cwd": work_dir,
                "blocked": False,
            }

            if success:
                log.debug(f"Command succeeded in {duration:.2f}s: {command}")
            else:
                log.warning(f"Command failed (rc={proc.returncode}): {command}")

            return result

        except subprocess.TimeoutExpired:
            duration = (datetime.now() - start).total_seconds()
            log.error(f"Command timed out after {timeout}s: {command}")
            return {
                "command": command,
                "returncode": -1,
                "stdout": "",
                "stderr": f"TIMEOUT: Command exceeded {timeout}s limit.",
                "success": False,
                "duration": round(duration, 3),
                "cwd": work_dir,
                "blocked": False,
            }
        except FileNotFoundError:
            duration = (datetime.now() - start).total_seconds()
            log.error(f"Command not found: {command}")
            return {
                "command": command,
                "returncode": -1,
                "stdout": "",
                "stderr": "Command not found.",
                "success": False,
                "duration": round(duration, 3),
                "cwd": work_dir,
                "blocked": False,
            }
        except Exception as e:
            duration = (datetime.now() - start).total_seconds()
            log.error(f"Command error: {e}")
            return {
                "command": command,
                "returncode": -1,
                "stdout": "",
                "stderr": str(e),
                "success": False,
                "duration": round(duration, 3),
                "cwd": work_dir,
                "blocked": False,
            }

    def run_batch(self, commands, cwd=None, stop_on_failure=False):
        """Run multiple commands sequentially."""
        results = []
        for cmd in commands:
            result = self.run(cmd, cwd=cwd)
            results.append(result)
            if stop_on_failure and not result["success"]:
                log.warning(f"Stopping batch: command failed: {cmd}")
                break
        return results

    def run_python(self, script_path, args=None, cwd=None, timeout=None):
        """Run a Python script."""
        cmd = f"python {script_path}"
        if args:
            if isinstance(args, list):
                cmd += " " + " ".join(shlex.quote(a) for a in args)
            else:
                cmd += " " + str(args)
        return self.run(cmd, cwd=cwd, timeout=timeout, check_dangerous=False)

    def pip_install(self, package, cwd=None):
        """Install a pip package."""
        return self.run(f"pip install {package}", cwd=cwd, check_dangerous=False)

    def _is_dangerous(self, command):
        """Check if a command matches known dangerous patterns."""
        cmd_lower = command.lower()
        for pattern in DANGEROUS_COMMANDS:
            if pattern.lower() in cmd_lower:
                return True
        return False

    def which(self, command):
        """Check if a command is available on the system."""
        result = self.run(f"which {command}", check_dangerous=False, timeout=5)
        return result["success"] and result["stdout"] != ""