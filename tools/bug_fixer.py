"""
Bug fixer for AI Builder.
Applies fixes for bugs found by the BugFinder using the SafeEditor.
"""

import ast
import re
from pathlib import Path
from core.logger import get_logger
from tools.file_reader import FileReader
from tools.file_writer import FileWriter
from tools.safe_editor import SafeEditor
from tools.bug_finder import BugFinder

log = get_logger("tools")


class BugFixer:
    """Fixes common bugs found by static analysis."""

    def __init__(self):
        self.reader = FileReader()
        self.writer = FileWriter()
        self.editor = SafeEditor()
        self.finder = BugFinder()

    def fix_file(self, file_path, create_backup=True):
        """
        Find and fix bugs in a single file.

        Returns dict: {file_path, bugs_found, bugs_fixed, failed_fixes, details}
        """
        bugs = self.finder.find_bugs(file_path)
        if not bugs:
            return {
                "file_path": file_path,
                "bugs_found": 0,
                "bugs_fixed": 0,
                "failed_fixes": [],
                "details": "No bugs found.",
            }

        content = self.reader.read(file_path)
        if content is None:
            return {
                "file_path": file_path,
                "bugs_found": len(bugs),
                "bugs_fixed": 0,
                "failed_fixes": [{"bug": b, "reason": "Cannot read file"} for b in bugs],
                "details": "Cannot read file.",
            }

        fixed_count = 0
        failed_fixes = []
        changes = []

        # Group bugs by line for efficient fixing
        # Process from bottom to top to avoid line number shifts
        sorted_bugs = sorted(bugs, key=lambda b: b.get("line", 0), reverse=True)

        for bug in sorted_bugs:
            change = self._generate_fix(bug, content)
            if change:
                changes.append(change)

        if not changes:
            return {
                "file_path": file_path,
                "bugs_found": len(bugs),
                "bugs_fixed": 0,
                "failed_fixes": [{"bug": b, "reason": "No automatic fix available"} for b in bugs],
                "details": "No automatic fixes available for detected bugs.",
            }

        # Apply all changes
        result = self.editor.edit(file_path, changes, create_backup=create_backup, validate=True)

        if result["success"]:
            fixed_count = result["changes_applied"]
            log.info(f"Fixed {fixed_count} bugs in {file_path}")
        else:
            failed_fixes = result.get("errors", [])

        return {
            "file_path": file_path,
            "bugs_found": len(bugs),
            "bugs_fixed": fixed_count,
            "failed_fixes": failed_fixes,
            "details": f"Applied {fixed_count} of {len(bugs)} fixes.",
            "backup_path": result.get("backup_path"),
        }

    def fix_project(self, project_path, max_files=50):
        """Fix bugs across all Python files in a project."""
        root = Path(project_path)
        results = []
        files_processed = 0

        for py_file in root.rglob("*.py"):
            if any(skip in str(py_file) for skip in
                   ["__pycache__", ".venv", "venv", ".git", "node_modules"]):
                continue
            if max_files and files_processed >= max_files:
                break
            result = self.fix_file(str(py_file))
            results.append(result)
            files_processed += 1

        total_found = sum(r["bugs_found"] for r in results)
        total_fixed = sum(r["bugs_fixed"] for r in results)

        log.info(f"Project fix: {total_fixed}/{total_found} bugs fixed in {files_processed} files")
        return {
            "files_processed": files_processed,
            "total_bugs_found": total_found,
            "total_bugs_fixed": total_fixed,
            "results": results,
        }

    def _generate_fix(self, bug, content):
        """Generate a change dict for a specific bug type."""
        bug_type = bug.get("type")
        line = bug.get("line")

        if bug_type == "comparison_none":
            return self._fix_comparison_none(bug, content, line)

        elif bug_type == "bare_except":
            return self._fix_bare_except(bug, content, line)

        elif bug_type == "mutable_default":
            return self._fix_mutable_default(bug, content, line)

        elif bug_type == "unused_import":
            return self._fix_unused_import(bug, content, line)

        # No automatic fix for other bug types
        return None

    def _fix_comparison_none(self, bug, content, line):
        """Fix '== None' to 'is None' and '!= None' to 'is not None'."""
        lines = content.splitlines(keepends=True)
        if line < 1 or line > len(lines):
            return None

        original = lines[line - 1]
        fixed = original.replace("== None", "is None").replace("!= None", "is not None")

        if fixed == original:
            return None

        return {
            "type": "replace_line",
            "line_num": line,
            "content": fixed.rstrip("\n"),
        }

    def _fix_bare_except(self, bug, content, line):
        """Fix bare 'except:' to 'except Exception:'."""
        lines = content.splitlines(keepends=True)
        if line < 1 or line > len(lines):
            return None

        original = lines[line - 1]
        fixed = re.sub(r'\bexcept\s*:', 'except Exception:', original)

        if fixed == original:
            return None

        return {
            "type": "replace_line",
            "line_num": line,
            "content": fixed.rstrip("\n"),
        }

    def _fix_mutable_default(self, bug, content, line):
        """
        Fix mutable default arguments by replacing with None.
        Note: This only replaces the default; the function body needs
        manual adjustment to initialize the mutable object.
        """
        lines = content.splitlines(keepends=True)
        if line < 1 or line > len(lines):
            return None

        original = lines[line - 1]
        # Replace [] -> None, {} -> None, set() -> None in default args
        fixed = re.sub(r'=\s*\[\]', '= None', original)
        fixed = re.sub(r'=\s*\{\}', '= None', fixed)
        fixed = re.sub(r'=\s*set\(\)', '= None', fixed)

        if fixed == original:
            return None

        return {
            "type": "replace_line",
            "line_num": line,
            "content": fixed.rstrip("\n"),
        }

    def _fix_unused_import(self, bug, content, line):
        """Remove an unused import line."""
        lines = content.splitlines(keepends=True)
        if line < 1 or line > len(lines):
            return None

        return {
            "type": "delete_lines",
            "start": line,
            "end": line,
        }

    def get_fix_suggestions(self, bugs):
        """Return human-readable fix suggestions for a list of bugs."""
        suggestions = []
        for bug in bugs:
            suggestion = {
                "bug_type": bug.get("type"),
                "severity": bug.get("severity"),
                "file": bug.get("file"),
                "line": bug.get("line"),
                "message": bug.get("message"),
                "fix": bug.get("detail", "No automatic fix available. Manual review required."),
                "auto_fixable": bug.get("type") in (
                    "comparison_none", "bare_except", "mutable_default", "unused_import"
                ),
            }
            suggestions.append(suggestion)
        return suggestions