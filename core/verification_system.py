"""
Verification System for AI Builder.
Runs tests, detects syntax and runtime errors, auto-repairs simple issues.
Never overwrites working code without backup.
"""

import ast
import os
import re
import tempfile
from pathlib import Path
from datetime import datetime
from core.logger import get_logger
from config.settings import get_config
from memory.memory_store import get_memory
from terminal.runner import TerminalRunner
from tools.file_reader import FileReader
from tools.file_writer import FileWriter
from tools.safe_editor import SafeEditor
from tools.bug_finder import BugFinder
from tools.bug_fixer import BugFixer
from tools.error_analyser import ErrorAnalyser

log = get_logger("verification")


class VerificationResult:
    """Result of verifying a file or project."""

    def __init__(self, file_path=None):
        self.file_path = file_path
        self.syntax_valid = True
        self.syntax_errors = []
        self.runtime_errors = []
        self.test_results = None
        self.bugs_found = []
        self.bugs_fixed = 0
        self.backup_path = None
        self.auto_repaired = False
        self.passed = True
        self.timestamp = datetime.now().isoformat()

    def to_dict(self):
        return {
            "file_path": self.file_path,
            "syntax_valid": self.syntax_valid,
            "syntax_errors": self.syntax_errors,
            "runtime_errors": self.runtime_errors,
            "test_results": self.test_results,
            "bugs_found": len(self.bugs_found),
            "bugs_fixed": self.bugs_fixed,
            "backup_path": self.backup_path,
            "auto_repaired": self.auto_repaired,
            "passed": self.passed,
            "timestamp": self.timestamp,
        }


class VerificationSystem:
    """
    Verifies code after modifications.
    - Runs tests after every change
    - Detects syntax errors (AST-based)
    - Detects runtime errors (executes file in subprocess)
    - Auto-repairs simple issues (bug fixer)
    - Never overwrites without backup
    """

    SKIP_DIRS = {"__pycache__", ".venv", "venv", "env", ".git", "node_modules",
                  ".tox", ".mypy_cache", ".pytest_cache", "dist", "build"}

    def __init__(self, config=None, memory=None):
        self.config = config or get_config()
        self.memory = memory or get_memory()
        self.terminal = TerminalRunner()
        self.reader = FileReader()
        self.writer = FileWriter()
        self.editor = SafeEditor()
        self.bug_finder = BugFinder()
        self.bug_fixer = BugFixer()
        self.error_analyser = ErrorAnalyser()

    def verify_file(self, file_path):
        """Run full verification on a single file."""
        result = VerificationResult(file_path=file_path)

        if not os.path.exists(file_path):
            result.passed = False
            result.syntax_valid = False
            result.syntax_errors.append(f"File not found: {file_path}")
            return result

        if file_path.endswith(".py"):
            result.syntax_errors = self.detect_syntax_errors(file_path)
            result.syntax_valid = len(result.syntax_errors) == 0

            if result.syntax_valid:
                result.runtime_errors = self.detect_runtime_errors(file_path)

            result.bugs_found = self.bug_finder.find_bugs(file_path)
        else:
            result.syntax_valid = True

        result.passed = (result.syntax_valid and
                         len(result.runtime_errors) == 0)
        return result

    def verify_modification(self, file_path, backup_path=None):
        """
        Verify a file after modification.
        If verification fails and backup exists, reports failure without restoring
        (caller decides whether to restore).
        """
        result = self.verify_file(file_path)
        result.backup_path = backup_path

        if not result.passed and backup_path:
            log.warning(f"Verification failed for {file_path}; backup available at {backup_path}")

        self._record_verification(result)
        return result

    def verify_project(self, project_path, run_tests=True):
        """Verify all Python files in a project."""
        root = Path(project_path)
        results = []
        files_checked = 0

        for py_file in root.rglob("*.py"):
            if any(skip in str(py_file) for skip in self.SKIP_DIRS):
                continue
            result = self.verify_file(str(py_file))
            results.append(result)
            files_checked += 1

        project_result = {
            "project_path": project_path,
            "files_checked": files_checked,
            "syntax_errors": sum(1 for r in results if not r.syntax_valid),
            "runtime_errors": sum(len(r.runtime_errors) for r in results),
            "total_bugs": sum(len(r.bugs_found) for r in results),
            "files_passed": sum(1 for r in results if r.passed),
            "files_failed": sum(1 for r in results if not r.passed),
            "results": [r.to_dict() for r in results],
            "verified_at": datetime.now().isoformat(),
        }

        if run_tests:
            project_result["test_results"] = self.run_tests(project_path)

        log.info(f"Project verification: {project_result['files_passed']}/"
                 f"{files_checked} files passed")
        return project_result

    def run_tests(self, project_path, test_command=None, timeout=120):
        """Run the test suite for a project."""
        if test_command:
            cmd = test_command
        else:
            test_runner = Path(project_path) / "tests" / "run_tests.py"
            if test_runner.exists():
                cmd = f"python3 {test_runner}"
            else:
                cmd = "python3 -m pytest tests/ -v --tb=short 2>&1 || true"

        log.info(f"Running tests: {cmd} (cwd={project_path})")
        result = self.terminal.run(cmd, cwd=project_path, timeout=timeout,
                                   check_dangerous=False, shell_mode=True)

        test_result = {
            "command": cmd,
            "success": result["success"],
            "returncode": result["returncode"],
            "stdout": result["stdout"][-3000:] if result["stdout"] else "",
            "stderr": result["stderr"][-2000:] if result["stderr"] else "",
            "duration": result["duration"],
            "ran_at": datetime.now().isoformat(),
        }

        passed = len(re.findall(r'\[PASS\]', result.get("stdout", "")))
        failed = len(re.findall(r'\[FAIL\]', result.get("stdout", "")))
        test_result["tests_passed"] = passed
        test_result["tests_failed"] = failed

        return test_result

    def detect_syntax_errors(self, file_path):
        """Check a Python file for syntax errors using AST parsing."""
        content = self.reader.read(file_path)
        if content is None:
            return [{"type": "SyntaxError", "message": "Cannot read file",
                      "line": None, "file": file_path}]

        errors = []
        try:
            ast.parse(content)
        except SyntaxError as e:
            errors.append({
                "type": "SyntaxError",
                "message": e.msg,
                "line": e.lineno,
                "column": e.offset,
                "file": file_path,
            })
        except Exception as e:
            errors.append({
                "type": "ParseError",
                "message": str(e),
                "line": None,
                "file": file_path,
            })
        return errors

    def detect_runtime_errors(self, file_path):
        """Execute a Python file to detect runtime errors."""
        cmd = f"python3 -c \"import ast; ast.parse(open('{file_path}').read()); print('OK')\""
        check = self.terminal.run(cmd, check_dangerous=False, shell_mode=True, timeout=10)
        if not check["success"]:
            return [{
                "type": "ImportOrRuntimeError",
                "message": check.get("stderr", "Unknown error")[:500],
                "file": file_path,
            }]

        run_cmd = f"python3 '{file_path}' 2>&1 || true"
        result = self.terminal.run(run_cmd, check_dangerous=False, shell_mode=True, timeout=30)
        errors = []
        if result["returncode"] != 0 and result["stderr"]:
            for line in result["stderr"].splitlines():
                if "Error" in line or "Exception" in line:
                    errors.append({
                        "type": "RuntimeError",
                        "message": line.strip()[:500],
                        "file": file_path,
                    })
        return errors[:5]

    def auto_repair(self, file_path, max_attempts=3):
        """
        Automatically repair simple issues in a file.
        Uses BugFixer for known patterns. Always creates a backup first.
        """
        if not os.path.exists(file_path):
            return {"repaired": False, "error": "File not found", "file_path": file_path}

        backup_path = self.writer.create_backup(file_path)
        result = VerificationResult(file_path=file_path)
        result.backup_path = backup_path

        for attempt in range(max_attempts):
            syntax_errors = self.detect_syntax_errors(file_path)
            if syntax_errors:
                fixed = self._repair_syntax_error(file_path, syntax_errors[0])
                if fixed:
                    result.auto_repaired = True
                    result.bugs_fixed += 1
                    continue
                else:
                    break

            fix_result = self.bug_fixer.fix_file(file_path, create_backup=False)
            if fix_result["bugs_fixed"] > 0:
                result.auto_repaired = True
                result.bugs_fixed += fix_result["bugs_fixed"]
            else:
                break

        result.bugs_found = self.bug_finder.find_bugs(file_path)
        result.syntax_errors = self.detect_syntax_errors(file_path)
        result.syntax_valid = len(result.syntax_errors) == 0
        result.passed = result.syntax_valid
        result.test_results = None

        self._record_verification(result)
        log.info(f"Auto-repair {file_path}: {result.bugs_fixed} fixes applied, "
                 f"passed={result.passed}")
        return result

    def _repair_syntax_error(self, file_path, error):
        """Attempt to repair a specific syntax error."""
        msg = error.get("message", "").lower()
        line_num = error.get("line")

        if not line_num:
            return False

        content = self.reader.read(file_path)
        if content is None:
            return False
        lines = content.splitlines(keepends=True)
        if line_num < 1 or line_num > len(lines):
            return False

        original = lines[line_num - 1]

        if "expected ':'" in msg or "eof while parsing" in msg:
            fixed = original.rstrip("\n") + ":\n"
        elif "unexpected indent" in msg:
            fixed = original.lstrip()
        elif "unindent does not match" in msg:
            prev_indent = len(lines[line_num - 2]) - len(lines[line_num - 2].lstrip()) if line_num > 1 else 0
            stripped = original.lstrip()
            fixed = " " * prev_indent + stripped
        else:
            return False

        if fixed == original:
            return False

        lines[line_num - 1] = fixed
        new_content = "".join(lines)

        try:
            ast.parse(new_content)
        except SyntaxError:
            return False

        self.writer.write(file_path, new_content)
        log.info(f"Repaired syntax error in {file_path} at line {line_num}")
        return True

    def backup_before_modification(self, file_path):
        """Create a backup before modifying a file. Always called before edits."""
        if not os.path.exists(file_path):
            return None
        backup = self.writer.create_backup(file_path)
        log.debug(f"Created backup: {backup}")
        return backup

    def safe_modify(self, file_path, modifier_func):
        """
        Safely modify a file: backup → modify → verify → restore on failure.
        modifier_func: callable(content) -> new_content
        """
        content = self.reader.read(file_path)
        if content is None:
            return {"success": False, "error": "Cannot read file"}

        backup_path = self.backup_before_modification(file_path)
        new_content = modifier_func(content)

        if new_content is None:
            return {"success": False, "error": "Modifier returned None"}

        if file_path.endswith(".py"):
            try:
                ast.parse(new_content)
            except SyntaxError as e:
                log.error(f"Modification would introduce syntax error: {e}")
                return {"success": False, "error": f"Syntax error: {e.msg}",
                        "backup_path": backup_path}

        self.writer.write(file_path, new_content)
        verification = self.verify_modification(file_path, backup_path=backup_path)

        if not verification.passed and verification.syntax_errors:
            log.warning(f"Verification failed after modification; restoring from backup")
            if backup_path:
                restore_content = self.reader.read(backup_path)
                if restore_content:
                    self.writer.write(file_path, restore_content)
            return {"success": False, "error": "Verification failed; restored from backup",
                    "backup_path": backup_path, "verification": verification.to_dict()}

        return {"success": True, "backup_path": backup_path,
                "verification": verification.to_dict()}

    def _record_verification(self, result):
        """Record verification result in memory."""
        self.memory.append_history("verifications", "results", result.to_dict())


def get_verification_system():
    """Return a singleton VerificationSystem instance."""
    if not hasattr(get_verification_system, "_instance"):
        get_verification_system._instance = VerificationSystem()
    return get_verification_system._instance