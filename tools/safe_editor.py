"""
Safe code editor for AI Builder.
Analyzes files before editing, creates backups, applies targeted changes,
and validates syntax after edits.
"""

import ast
import re
from pathlib import Path
from datetime import datetime
from core.logger import get_logger
from config.settings import get_config
from tools.file_reader import FileReader
from tools.file_writer import FileWriter

log = get_logger("tools")


class SafeEditor:
    """Edits code files with analysis, backup, and validation."""

    def __init__(self):
        self.config = get_config()
        self.reader = FileReader()
        self.writer = FileWriter()
        self.auto_backup = self.config.get("backup_on_edit", True)
        self.auto_validate = self.config.get("auto_validate_syntax", True)

    def edit(self, file_path, changes, create_backup=None, validate=None):
        """
        Apply a list of changes to a file safely.

        Each change is a dict with:
          - type: 'replace' | 'insert_before' | 'insert_after' | 'delete_lines' | 'replace_line'
          - For 'replace': old_text (str), new_text (str)
          - For 'insert_before'/'insert_after': anchor (str), content (str)
          - For 'delete_lines': start (int), end (int) [1-indexed, inclusive]
          - For 'replace_line': line_num (int), content (str)

        Returns dict: {success, file_path, backup_path, changes_applied, errors}
        """
        create_backup = self.auto_backup if create_backup is None else create_backup
        validate = self.auto_validate if validate is None else validate

        result = {
            "success": False,
            "file_path": file_path,
            "backup_path": None,
            "changes_applied": 0,
            "errors": [],
        }

        # Read current content
        content = self.reader.read(file_path)
        if content is None:
            result["errors"].append(f"Cannot read file: {file_path}")
            return result

        # Create backup
        backup_path = None
        if create_backup:
            backup_path = self.writer.create_backup(file_path)
            result["backup_path"] = backup_path

        original_content = content
        modified_content = content

        for i, change in enumerate(changes):
            try:
                modified_content = self._apply_change(modified_content, change)
                result["changes_applied"] += 1
            except Exception as e:
                error_msg = f"Change {i+1} failed: {e}"
                result["errors"].append(error_msg)
                log.error(error_msg)

        if result["changes_applied"] == 0:
            result["errors"].append("No changes were applied.")
            return result

        # Validate syntax if Python
        if validate and file_path.endswith(".py"):
            is_valid, syntax_error = self._validate_python(modified_content)
            if not is_valid:
                result["errors"].append(f"Syntax validation failed: {syntax_error}")
                log.error(f"Syntax error in modified {file_path}: {syntax_error}")
                # Restore from backup
                if backup_path:
                    restore_content = self.reader.read(backup_path)
                    if restore_content:
                        self.writer.write(file_path, restore_content)
                        result["errors"].append("File restored from backup due to syntax error.")
                return result

        # Write modified content
        if self.writer.write(file_path, modified_content):
            result["success"] = True
            log.info(f"Successfully edited {file_path} ({result['changes_applied']} changes)")
        else:
            result["errors"].append("Failed to write modified file.")
            if backup_path:
                restore_content = self.reader.read(backup_path)
                if restore_content:
                    self.writer.write(file_path, restore_content)

        return result

    def replace_text(self, file_path, old_text, new_text, create_backup=None):
        """Replace a specific text block in a file."""
        return self.edit(
            file_path,
            [{"type": "replace", "old_text": old_text, "new_text": new_text}],
            create_backup=create_backup,
        )

    def insert_before(self, file_path, anchor, content, create_backup=None):
        """Insert content before a line containing the anchor text."""
        return self.edit(
            file_path,
            [{"type": "insert_before", "anchor": anchor, "content": content}],
            create_backup=create_backup,
        )

    def insert_after(self, file_path, anchor, content, create_backup=None):
        """Insert content after a line containing the anchor text."""
        return self.edit(
            file_path,
            [{"type": "insert_after", "anchor": anchor, "content": content}],
            create_backup=create_backup,
        )

    def delete_lines(self, file_path, start_line, end_line, create_backup=None):
        """Delete a range of lines (1-indexed, inclusive)."""
        return self.edit(
            file_path,
            [{"type": "delete_lines", "start": start_line, "end": end_line}],
            create_backup=create_backup,
        )

    def replace_line(self, file_path, line_num, content, create_backup=None):
        """Replace a specific line (1-indexed)."""
        return self.edit(
            file_path,
            [{"type": "replace_line", "line_num": line_num, "content": content}],
            create_backup=create_backup,
        )

    def _apply_change(self, content, change):
        """Apply a single change to content and return modified content."""
        change_type = change.get("type")

        if change_type == "replace":
            old_text = change["old_text"]
            new_text = change["new_text"]
            if old_text not in content:
                raise ValueError(f"old_text not found in file")
            if content.count(old_text) > 1 and not change.get("replace_all"):
                raise ValueError(f"old_text appears {content.count(old_text)} times; "
                                 f"set replace_all=True to replace all")
            if change.get("replace_all"):
                return content.replace(old_text, new_text)
            return content.replace(old_text, new_text, 1)

        elif change_type == "insert_before":
            anchor = change["anchor"]
            insert_content = change["content"]
            lines = content.splitlines(keepends=True)
            for i, line in enumerate(lines):
                if anchor in line:
                    if not insert_content.endswith("\n"):
                        insert_content += "\n"
                    lines.insert(i, insert_content)
                    return "".join(lines)
            raise ValueError(f"Anchor not found: {anchor}")

        elif change_type == "insert_after":
            anchor = change["anchor"]
            insert_content = change["content"]
            lines = content.splitlines(keepends=True)
            for i, line in enumerate(lines):
                if anchor in line:
                    if not insert_content.endswith("\n"):
                        insert_content += "\n"
                    lines.insert(i + 1, insert_content)
                    return "".join(lines)
            raise ValueError(f"Anchor not found: {anchor}")

        elif change_type == "delete_lines":
            start = change["start"]  # 1-indexed
            end = change["end"]
            lines = content.splitlines(keepends=True)
            if start < 1 or end > len(lines) or start > end:
                raise ValueError(f"Invalid line range: {start}-{end}")
            del lines[start - 1:end]
            return "".join(lines)

        elif change_type == "replace_line":
            line_num = change["line_num"]  # 1-indexed
            new_content = change["content"]
            lines = content.splitlines(keepends=True)
            if line_num < 1 or line_num > len(lines):
                raise ValueError(f"Invalid line number: {line_num}")
            if not new_content.endswith("\n"):
                new_content += "\n"
            lines[line_num - 1] = new_content
            return "".join(lines)

        else:
            raise ValueError(f"Unknown change type: {change_type}")

    def _validate_python(self, content):
        """Validate Python syntax. Returns (is_valid, error_message)."""
        try:
            ast.parse(content)
            return True, None
        except SyntaxError as e:
            return False, f"{e.msg} (line {e.lineno})"
        except Exception as e:
            return False, str(e)

    def validate_file(self, file_path):
        """Validate the syntax of an existing file."""
        content = self.reader.read(file_path)
        if content is None:
            return False, "Cannot read file"
        if file_path.endswith(".py"):
            return self._validate_python(content)
        return True, None

    def analyze_before_edit(self, file_path):
        """Analyze a file before editing to understand its structure."""
        content = self.reader.read(file_path)
        if content is None:
            return None

        analysis = {
            "file_path": file_path,
            "size": len(content),
            "line_count": len(content.splitlines()),
            "is_python": file_path.endswith(".py"),
            "syntax_valid": True,
            "syntax_error": None,
            "has_functions": False,
            "has_classes": False,
            "function_names": [],
            "class_names": [],
            "imports": [],
        }

        if analysis["is_python"]:
            is_valid, error = self._validate_python(content)
            analysis["syntax_valid"] = is_valid
            analysis["syntax_error"] = error

            if is_valid:
                try:
                    tree = ast.parse(content)
                    for node in ast.walk(tree):
                        if isinstance(node, ast.FunctionDef):
                            analysis["has_functions"] = True
                            analysis["function_names"].append(node.name)
                        elif isinstance(node, ast.ClassDef):
                            analysis["has_classes"] = True
                            analysis["class_names"].append(node.name)
                        elif isinstance(node, ast.Import):
                            for alias in node.names:
                                analysis["imports"].append(alias.name)
                        elif isinstance(node, ast.ImportFrom):
                            if node.module:
                                analysis["imports"].append(node.module)
                except Exception as e:
                    log.warning(f"AST analysis failed for {file_path}: {e}")

        return analysis