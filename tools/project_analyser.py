"""
Project analyser for AI Builder.
Analyses project structure, languages, dependencies, and architecture.
"""

import os
import ast
import re
from pathlib import Path
from datetime import datetime
from collections import Counter

from core.logger import get_logger
from tools.file_reader import FileReader
from utils.helpers import get_platform_info

log = get_logger("tools")


# Patterns for identifying project types
PROJECT_MARKERS = {
    "package.json": "node",
    "requirements.txt": "python",
    "setup.py": "python",
    "pyproject.toml": "python",
    "Pipfile": "python",
    "Cargo.toml": "rust",
    "go.mod": "go",
    "pom.xml": "java",
    "build.gradle": "java",
    "build.gradle.kts": "kotlin",
    "Gemfile": "ruby",
    "composer.json": "php",
    "mix.exs": "elixir",
    "CMakeLists.txt": "cpp",
    "Makefile": "make",
    "Dockerfile": "docker",
    ".git": "git",
}

# Directories to skip during analysis
SKIP_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv", "env",
    ".env", "dist", "build", ".tox", ".mypy_cache", ".pytest_cache",
    "coverage", ".coverage", "htmlcov", ".idea", ".vscode",
    "target", "bin", "obj", ".next", ".nuxt", ".cache",
}

LANGUAGE_EXTENSIONS = {
    ".py": "Python",
    ".js": "JavaScript",
    ".jsx": "JavaScript (React)",
    ".ts": "TypeScript",
    ".tsx": "TypeScript (React)",
    ".java": "Java",
    ".c": "C",
    ".cpp": "C++",
    ".h": "C/C++ Header",
    ".cs": "C#",
    ".go": "Go",
    ".rs": "Rust",
    ".rb": "Ruby",
    ".php": "PHP",
    ".swift": "Swift",
    ".kt": "Kotlin",
    ".scala": "Scala",
    ".html": "HTML",
    ".css": "CSS",
    ".scss": "SCSS",
    ".sql": "SQL",
    ".sh": "Shell",
    ".lua": "Lua",
    ".r": "R",
    ".dart": "Dart",
}


class ProjectAnalyser:
    """Analyses existing project structure and content."""

    def __init__(self):
        self.reader = FileReader()

    def analyze(self, project_path, deep=False, max_files=None):
        """
        Analyze a project directory.

        project_path: Root directory of the project.
        deep: If True, also parse Python files for structure.
        max_files: Limit number of files to scan (None = no limit).

        Returns a comprehensive analysis dict.
        """
        root = Path(project_path).expanduser().resolve()
        if not root.exists():
            log.error(f"Project path does not exist: {project_path}")
            return {"error": f"Path not found: {project_path}"}
        if not root.is_dir():
            log.error(f"Project path is not a directory: {project_path}")
            return {"error": f"Not a directory: {project_path}"}

        log.info(f"Analyzing project: {root}")

        analysis = {
            "project_name": root.name,
            "root_path": str(root),
            "analyzed_at": datetime.now().isoformat(),
            "platform": get_platform_info(),
            "project_types": [],
            "languages": {},
            "file_count": 0,
            "dir_count": 0,
            "total_size_bytes": 0,
            "file_extensions": {},
            "has_readme": False,
            "has_tests": False,
            "has_git": False,
            "has_docker": False,
            "has_ci": False,
            "test_file_count": 0,
            "entry_points": [],
            "dependencies": [],
            "issues": [],
            "suggestions": [],
            "structure": {},
            "python_modules": [],
            "top_level_dirs": [],
        }

        files_scanned = 0
        all_files = []

        for dirpath, dirnames, filenames in os.walk(root):
            # Skip excluded directories
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]

            rel_dir = Path(dirpath).relative_to(root)
            analysis["dir_count"] += 1

            for filename in filenames:
                if max_files and files_scanned >= max_files:
                    break

                file_path = Path(dirpath) / filename
                rel_path = str(file_path.relative_to(root))
                all_files.append(rel_path)
                files_scanned += 1

                ext = file_path.suffix.lower()
                analysis["file_extensions"][ext] = analysis["file_extensions"].get(ext, 0) + 1

                # Language detection
                if ext in LANGUAGE_EXTENSIONS:
                    lang = LANGUAGE_EXTENSIONS[ext]
                    analysis["languages"][lang] = analysis["languages"].get(lang, 0) + 1

                # Size
                try:
                    analysis["total_size_bytes"] += file_path.stat().st_size
                except OSError:
                    pass

                # Test files
                if "test" in filename.lower() or ext == ".py" and filename.startswith("test_"):
                    analysis["test_file_count"] += 1
                    analysis["has_tests"] = True

                # Entry points
                if filename in {"main.py", "app.py", "index.js", "index.ts",
                                "main.js", "main.ts", "server.js", "manage.py",
                                "run.py", "__main__.py"}:
                    analysis["entry_points"].append(rel_path)

                # Parse Python for structure (deep mode)
                if deep and ext == ".py":
                    module_info = self._analyze_python_file(file_path)
                    if module_info:
                        analysis["python_modules"].append(module_info)

            if max_files and files_scanned >= max_files:
                break

        analysis["file_count"] = files_scanned

        # Detect project types
        analysis["project_types"] = self._detect_project_types(root)

        # Check for key files
        analysis["has_readme"] = (root / "README.md").exists() or (root / "README.rst").exists() or (root / "readme.md").exists()
        analysis["has_git"] = (root / ".git").exists()
        analysis["has_docker"] = (root / "Dockerfile").exists()
        ci_dirs = [".github", ".gitlab-ci.yml", ".circleci", ".travis.yml"]
        analysis["has_ci"] = any((root / d).exists() for d in ci_dirs)

        # Top-level directories
        analysis["top_level_dirs"] = [
            d.name for d in root.iterdir() if d.is_dir() and d.name not in SKIP_DIRS
        ]

        # Build structure tree
        analysis["structure"] = self._build_structure(root, max_depth=2)

        # Parse dependencies
        analysis["dependencies"] = self._parse_dependencies(root)

        # Generate issues and suggestions
        analysis["issues"] = self._detect_issues(analysis)
        analysis["suggestions"] = self._generate_suggestions(analysis)

        log.info(f"Analysis complete: {files_scanned} files, "
                 f"{len(analysis['languages'])} languages, "
                 f"{len(analysis['issues'])} issues found")

        return analysis

    def _detect_project_types(self, root):
        """Detect project type based on marker files."""
        types = []
        for marker, ptype in PROJECT_MARKERS.items():
            if (root / marker).exists():
                types.append(ptype)
        return types

    def _analyze_python_file(self, file_path):
        """Analyze a single Python file's structure using AST."""
        content = self.reader.read(file_path)
        if content is None:
            return None

        try:
            tree = ast.parse(content)
        except SyntaxError as e:
            return {
                "file": str(file_path),
                "error": f"Syntax error: {e.msg} (line {e.lineno})",
                "functions": [],
                "classes": [],
                "imports": [],
            }

        functions = []
        classes = []
        imports = []

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                args = [a.arg for a in node.args.args]
                functions.append({
                    "name": node.name,
                    "line": node.lineno,
                    "args": args,
                    "docstring": ast.get_docstring(node),
                })
            elif isinstance(node, ast.ClassDef):
                methods = []
                for item in node.body:
                    if isinstance(item, ast.FunctionDef):
                        methods.append(item.name)
                classes.append({
                    "name": node.name,
                    "line": node.lineno,
                    "methods": methods,
                    "docstring": ast.get_docstring(node),
                })
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.append(node.module)

        return {
            "file": str(file_path),
            "functions": functions,
            "classes": classes,
            "imports": imports,
            "line_count": len(content.splitlines()),
        }

    def _build_structure(self, root, max_depth=2, current_depth=0):
        """Build a simplified directory structure tree."""
        if current_depth >= max_depth:
            return {}

        structure = {}
        try:
            for item in sorted(root.iterdir()):
                if item.name in SKIP_DIRS or item.name.startswith("."):
                    continue
                if item.is_dir():
                    structure[item.name + "/"] = self._build_structure(item, max_depth, current_depth + 1)
                else:
                    structure[item.name] = "file"
        except PermissionError:
            pass
        return structure

    def _parse_dependencies(self, root):
        """Parse dependency files."""
        deps = []

        # Python requirements.txt
        req_file = root / "requirements.txt"
        if req_file.exists():
            content = self.reader.read(req_file)
            if content:
                for line in content.splitlines():
                    line = line.strip()
                    if line and not line.startswith("#"):
                        deps.append({"name": line, "source": "requirements.txt", "type": "python"})

        # Python pyproject.toml (basic)
        pyproject = root / "pyproject.toml"
        if pyproject.exists():
            content = self.reader.read(pyproject)
            if content:
                for line in content.splitlines():
                    line = line.strip()
                    if line and "=" in line and not line.startswith("[") and not line.startswith("#"):
                        deps.append({"name": line, "source": "pyproject.toml", "type": "python"})

        # Node package.json
        pkg_file = root / "package.json"
        if pkg_file.exists():
            data = self.reader.read_json(pkg_file)
            if data:
                for section in ("dependencies", "devDependencies"):
                    for name, version in (data.get(section) or {}).items():
                        deps.append({"name": f"{name}@{version}", "source": "package.json", "type": "node"})

        return deps

    def _detect_issues(self, analysis):
        """Detect potential issues in the project."""
        issues = []

        # No README
        if not analysis.get("has_readme"):
            issues.append({
                "type": "documentation",
                "severity": "medium",
                "message": "No README file found",
                "detail": "Project lacks documentation. Consider adding a README.md.",
            })

        # No tests
        if analysis.get("test_file_count", 0) == 0:
            issues.append({
                "type": "testing",
                "severity": "medium",
                "message": "No test files found",
                "detail": "No test files detected. Consider adding a test suite.",
            })

        # No git
        if not analysis.get("has_git"):
            issues.append({
                "type": "version_control",
                "severity": "low",
                "message": "No git repository",
                "detail": "Project is not under version control.",
            })

        # Too many files in root
        top_dirs = analysis.get("top_level_dirs", [])
        if len(top_dirs) > 15:
            issues.append({
                "type": "organization",
                "severity": "low",
                "message": "Many top-level directories",
                "detail": f"{len(top_dirs)} top-level directories. Consider organizing into fewer modules.",
            })

        # Python syntax errors in modules
        for mod in analysis.get("python_modules", []):
            if mod.get("error"):
                issues.append({
                    "type": "syntax_error",
                    "severity": "high",
                    "message": f"Syntax error in {mod['file']}",
                    "detail": mod["error"],
                })

        return issues

    def _generate_suggestions(self, analysis):
        """Generate improvement suggestions."""
        suggestions = []

        languages = analysis.get("languages", {})
        if "Python" in languages:
            suggestions.append({
                "title": "Add type hints",
                "description": "Add type annotations to Python functions for better maintainability.",
                "priority": "low",
            })
            suggestions.append({
                "title": "Add linting configuration",
                "description": "Add .flake8 or pylint config for code quality enforcement.",
                "priority": "low",
            })

        if not analysis.get("has_docker"):
            suggestions.append({
                "title": "Add Dockerfile",
                "description": "Containerize the project for consistent deployment.",
                "priority": "low",
            })

        if not analysis.get("has_ci"):
            suggestions.append({
                "title": "Add CI/CD pipeline",
                "description": "Add GitHub Actions or similar for automated testing.",
                "priority": "medium",
            })

        if analysis.get("file_count", 0) > 100:
            suggestions.append({
                "title": "Review project size",
                "description": f"Project has {analysis['file_count']} files. Consider modularizing.",
                "priority": "low",
            })

        return suggestions

    def get_summary(self, analysis):
        """Return a human-readable summary of the analysis."""
        lines = []
        lines.append(f"Project: {analysis.get('project_name', 'unknown')}")
        lines.append(f"Path: {analysis.get('root_path', 'unknown')}")
        lines.append(f"Files: {analysis.get('file_count', 0)}")
        lines.append(f"Directories: {analysis.get('dir_count', 0)}")
        lines.append(f"Languages: {', '.join(analysis.get('languages', {}).keys()) or 'none detected'}")
        lines.append(f"Project types: {', '.join(analysis.get('project_types', [])) or 'unknown'}")
        lines.append(f"Test files: {analysis.get('test_file_count', 0)}")
        lines.append(f"Entry points: {', '.join(analysis.get('entry_points', [])) or 'none'}")
        lines.append(f"Dependencies: {len(analysis.get('dependencies', []))}")
        lines.append(f"Issues found: {len(analysis.get('issues', []))}")
        lines.append(f"Suggestions: {len(analysis.get('suggestions', []))}")
        return "\n".join(lines)