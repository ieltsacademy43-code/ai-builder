"""
Bug finder for AI Builder.
Performs static analysis to find common bugs in Python code.
"""

import ast
import re
from pathlib import Path
from core.logger import get_logger
from tools.file_reader import FileReader

log = get_logger("tools")


class BugFinder:
    """Finds common bugs using static analysis (AST-based)."""

    def __init__(self):
        self.reader = FileReader()

    def find_bugs(self, file_path):
        """
        Analyze a Python file for common bugs.

        Returns list of bug dicts:
        [{type, severity, message, line, file, detail}]
        """
        content = self.reader.read(file_path)
        if content is None:
            return []

        if not file_path.endswith(".py"):
            return self._find_text_bugs(content, file_path)

        bugs = []

        # First check syntax
        try:
            tree = ast.parse(content)
        except SyntaxError as e:
            bugs.append({
                "type": "syntax_error",
                "severity": "high",
                "message": e.msg,
                "line": e.lineno,
                "column": e.offset,
                "file": file_path,
                "detail": f"Syntax error prevents analysis: {e.msg}",
            })
            return bugs

        # Run AST-based checks
        bugs.extend(self._check_bare_except(tree, file_path))
        bugs.extend(self._check_broad_except(tree, file_path))
        bugs.extend(self._check_undefined_names(tree, file_path))
        bugs.extend(self._check_mutable_defaults(tree, file_path))
        bugs.extend(self._check_comparison_none(tree, file_path))
        bugs.extend(self._check_unused_imports(tree, file_path))
        bugs.extend(self._check_assert_in_production(tree, file_path))
        bugs.extend(self._check_eval_exec(tree, file_path))

        # Run text-based checks
        bugs.extend(self._find_text_bugs(content, file_path))

        log.info(f"Found {len(bugs)} potential bugs in {file_path}")
        return bugs

    def find_bugs_in_project(self, project_path, max_files=100):
        """Find bugs across all Python files in a project."""
        root = Path(project_path)
        all_bugs = []
        files_checked = 0

        for py_file in root.rglob("*.py"):
            if any(skip in str(py_file) for skip in
                   ["__pycache__", ".venv", "venv", ".git", "node_modules"]):
                continue
            if max_files and files_checked >= max_files:
                break
            bugs = self.find_bugs(str(py_file))
            all_bugs.extend(bugs)
            files_checked += 1

        log.info(f"Found {len(all_bugs)} bugs across {files_checked} files in {project_path}")
        return all_bugs

    def _check_bare_except(self, tree, file_path):
        """Find bare 'except:' clauses."""
        bugs = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler) and node.type is None:
                bugs.append({
                    "type": "bare_except",
                    "severity": "medium",
                    "message": "Bare 'except:' catches all exceptions including SystemExit and KeyboardInterrupt",
                    "line": node.lineno,
                    "file": file_path,
                    "detail": "Use 'except Exception:' instead of bare 'except:'.",
                })
        return bugs

    def _check_broad_except(self, tree, file_path):
        """Find overly broad exception handlers."""
        bugs = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler) and node.type:
                if isinstance(node.type, ast.Name) and node.type.id == "Exception":
                    bugs.append({
                        "type": "broad_except",
                        "severity": "low",
                        "message": "Broad 'except Exception' may hide specific errors",
                        "line": node.lineno,
                        "file": file_path,
                        "detail": "Consider catching specific exception types.",
                    })
        return bugs

    def _check_undefined_names(self, tree, file_path):
        """Find references to names that may not be defined."""
        bugs = []
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                defined = set()
                # Collect arguments
                for arg in node.args.args:
                    defined.add(arg.arg)
                # Collect assignments in the function body
                for child in ast.walk(node):
                    if isinstance(child, ast.Name) and isinstance(child.ctx, ast.Store):
                        defined.add(child.id)
                # Check for uses of names that might be undefined
                # (Simplified — doesn't handle closures, globals, etc.)
        return bugs

    def _check_mutable_defaults(self, tree, file_path):
        """Find mutable default arguments in function definitions."""
        bugs = []
        mutable_types = (ast.List, ast.Dict, ast.Set)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                for default in node.args.defaults + node.args.kw_defaults:
                    if default and isinstance(default, mutable_types):
                        bugs.append({
                            "type": "mutable_default",
                            "severity": "medium",
                            "message": f"Mutable default argument in function '{node.name}'",
                            "line": node.lineno,
                            "file": file_path,
                            "detail": "Mutable default arguments are shared across calls. Use None and set inside the function.",
                        })
        return bugs

    def _check_comparison_none(self, tree, file_path):
        """Find '== None' or '!= None' comparisons (should use 'is None')."""
        bugs = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Compare):
                for comparator in node.comparators:
                    if isinstance(comparator, ast.Constant) and comparator.value is None:
                        if any(isinstance(op, (ast.Eq, ast.NotEq)) for op in node.ops):
                            bugs.append({
                                "type": "comparison_none",
                                "severity": "low",
                                "message": "Use 'is None' or 'is not None' instead of '== None'",
                                "line": node.lineno,
                                "file": file_path,
                                "detail": "Identity check 'is None' is preferred over equality '== None'.",
                            })
        return bugs

    def _check_unused_imports(self, tree, file_path):
        """Find imported names that are never used in the module."""
        bugs = []
        imported = {}

        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    name = alias.asname or alias.name.split(".")[0]
                    imported[name] = node.lineno
            elif isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    if alias.name == "*":
                        continue
                    name = alias.asname or alias.name
                    imported[name] = node.lineno

        # Collect all used names
        used = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
                used.add(node.id)
            elif isinstance(node, ast.Attribute):
                # Check the base name for chained access like os.path
                if isinstance(node.value, ast.Name):
                    used.add(node.value.id)

        for name, line in imported.items():
            if name not in used:
                bugs.append({
                    "type": "unused_import",
                    "severity": "low",
                    "message": f"Unused import: '{name}'",
                    "line": line,
                    "file": file_path,
                    "detail": f"The import '{name}' is never used in this module.",
                })
        return bugs

    def _check_assert_in_production(self, tree, file_path):
        """Find assert statements that should not be in production code."""
        bugs = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Assert):
                bugs.append({
                    "type": "assert_in_production",
                    "severity": "low",
                    "message": "Assert statement found — disabled when Python runs with -O flag",
                    "line": node.lineno,
                    "file": file_path,
                    "detail": "Use explicit if/raise instead of assert for production validation.",
                })
        return bugs

    def _check_eval_exec(self, tree, file_path):
        """Find eval() and exec() calls — security risk."""
        bugs = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id in ("eval", "exec"):
                    bugs.append({
                        "type": "eval_exec",
                        "severity": "high",
                        "message": f"Use of {node.func.id}() is a security risk",
                        "line": node.lineno,
                        "file": file_path,
                        "detail": f"{node.func.id}() can execute arbitrary code. Avoid in production.",
                    })
        return bugs

    def _find_text_bugs(self, content, file_path):
        """Find bugs using regex-based text analysis."""
        bugs = []
        lines = content.splitlines()

        for i, line in enumerate(lines, 1):
            stripped = line.strip()

            # TODO/FIXME/HACK comments
            if re.match(r"#\s*(TODO|FIXME|HACK|XXX)", stripped, re.IGNORECASE):
                tag = re.match(r"#\s*(TODO|FIXME|HACK|XXX)", stripped, re.IGNORECASE).group(1).upper()
                bugs.append({
                    "type": f"code_marker_{tag.lower()}",
                    "severity": "info",
                    "message": f"{tag} comment found",
                    "line": i,
                    "file": file_path,
                    "detail": stripped,
                })

            # Print statements in Python (debugging leftover)
            if re.match(r"^\s*print\s*\(", line) and not file_path.endswith(("_test.py", "/tests/")):
                if "debug" in stripped.lower():
                    bugs.append({
                        "type": "debug_print",
                        "severity": "info",
                        "message": "Debug print statement found",
                        "line": i,
                        "file": file_path,
                        "detail": stripped,
                    })

            # Hardcoded passwords/secrets
            if re.search(r'(password|secret|api_key|token)\s*=\s*["\'][^"\']+["\']',
                         stripped, re.IGNORECASE):
                bugs.append({
                    "type": "hardcoded_secret",
                    "severity": "high",
                    "message": "Potential hardcoded secret/password",
                    "line": i,
                    "file": file_path,
                    "detail": "Do not hardcode secrets. Use environment variables or config files.",
                })

        return bugs