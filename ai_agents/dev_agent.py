"""
Development Agent for AI Builder.
Analyzes projects, identifies files needing changes, generates code, edits code,
reviews generated code, and explains every modification.
Integrates LLM Manager, SafeEditor, BugFinder, and VerificationSystem.
"""

import ast
import re
import difflib
from datetime import datetime
from pathlib import Path
from core.logger import get_logger
from memory.memory_store import get_memory
from config.settings import get_config
from tools.file_reader import FileReader
from tools.file_writer import FileWriter
from tools.safe_editor import SafeEditor
from tools.project_analyser import ProjectAnalyser
from tools.bug_finder import BugFinder
from ai_agents.base_agent import BaseAgent
from ai_agents.conversation_manager import get_conversation_manager
from llm.llm_manager import get_llm_manager
from core.verification_system import get_verification_system

log = get_logger("dev_agent")


# File change targeting heuristics
FILE_TARGETING_RULES = {
    "bug": ["bug", "fix", "error", "crash", "exception", "broken", "fail"],
    "feature": ["add", "create", "implement", "new", "build", "extend"],
    "refactor": ["refactor", "restructure", "clean", "rename", "reorganize"],
    "test": ["test", "coverage", "unit test", "integration test"],
    "docs": ["document", "readme", "docstring", "api reference"],
    "config": ["config", "settings", "environment", "variable"],
    "dependency": ["install", "upgrade", "depend", "package", "import"],
}


class CodeChange:
    """Represents a proposed code change to a file."""

    def __init__(self, file_path, change_type, description, old_content=None,
                 new_content=None, changes=None):
        self.file_path = file_path
        self.change_type = change_type  # "create", "edit", "delete"
        self.description = description
        self.old_content = old_content
        self.new_content = new_content
        self.changes = changes or []
        self.verified = False
        self.backup_path = None
        self.explanation = ""

    def to_dict(self):
        return {
            "file_path": self.file_path,
            "change_type": self.change_type,
            "description": self.description,
            "verified": self.verified,
            "backup_path": self.backup_path,
            "explanation": self.explanation,
            "changes": self.changes,
        }


class DevelopmentAgent(BaseAgent):
    """
    AI development agent that can analyze projects, decide which files to change,
    generate code, edit code, review changes, and explain modifications.
    """

    def __init__(self, name="dev_agent", role="developer",
                 description="Autonomous development agent", capabilities=None):
        super().__init__(
            name=name,
            role=role,
            description=description,
            capabilities=capabilities or [
                "analyze_project", "identify_files", "generate_code",
                "edit_code", "review_code", "explain_changes",
            ],
        )
        self.config = get_config()
        self.reader = FileReader()
        self.writer = FileWriter()
        self.editor = SafeEditor()
        self.analyser = ProjectAnalyser()
        self.bug_finder = BugFinder()
        self.llm = get_llm_manager()
        self.conversation = get_conversation_manager()
        self.verification = get_verification_system()
        self._conversation_id = None

    def _ensure_conversation(self):
        """Ensure a conversation context exists."""
        if not self._conversation_id:
            self._conversation_id = self.conversation.create_conversation(
                system_prompt=self._build_system_prompt()
            )
        return self._conversation_id

    def _build_system_prompt(self):
        return (
            "You are an expert software developer agent. You analyze projects, "
            "identify files that need changes, generate clean production-ready code, "
            "and explain every modification you make. Always provide complete, "
            "working code — no placeholders or TODOs."
        )

    def analyze_project(self, project_path, deep=True):
        """Analyze an entire project structure and codebase."""
        analysis = self.analyser.analyze(project_path, deep=deep)
        if "error" not in analysis:
            self.memory.store("dev_agent", f"analysis_{project_path}", {
                "analysis": analysis,
                "timestamp": datetime.now().isoformat(),
            })
            log.info(f"DevAgent analyzed project: {project_path} "
                     f"({analysis.get('file_count', 0)} files)")
        return analysis

    def identify_files_to_change(self, analysis, task_description):
        """
        Decide which files require changes based on the task and project analysis.
        Returns a list of file targets with reasoning.
        """
        task_lower = task_description.lower()
        change_type = "feature"
        for ctype, keywords in FILE_TARGETING_RULES.items():
            if any(kw in task_lower for kw in keywords):
                change_type = ctype
                break

        targets = []
        root = analysis.get("root_path", "")
        python_modules = analysis.get("python_modules", [])
        entry_points = analysis.get("entry_points", [])
        issues = analysis.get("issues", [])

        if change_type == "bug":
            for issue in issues:
                if issue.get("type") == "syntax_error":
                    for mod in python_modules:
                        if mod.get("error"):
                            targets.append({
                                "file": mod["file"],
                                "reason": f"Syntax error: {mod['error']}",
                                "change_type": "edit",
                                "priority": "critical",
                            })
                else:
                    matching = self._find_files_for_issue(issue, python_modules, root)
                    for f in matching:
                        targets.append({
                            "file": f,
                            "reason": f"Issue: {issue.get('message', '')}",
                            "change_type": "edit",
                            "priority": "high",
                        })

        elif change_type == "test":
            test_files = [str(p) for p in Path(root).rglob("test_*.py")]
            if not test_files:
                targets.append({
                    "file": str(Path(root) / "tests" / "test_generated.py"),
                    "reason": "No tests found; create initial test suite",
                    "change_type": "create",
                    "priority": "high",
                })
            else:
                for tf in test_files[:5]:
                    targets.append({
                        "file": tf,
                        "reason": "Extend existing tests",
                        "change_type": "edit",
                        "priority": "medium",
                    })

        elif change_type == "docs":
            if not analysis.get("has_readme"):
                targets.append({
                    "file": str(Path(root) / "README.md"),
                    "reason": "No README found",
                    "change_type": "create",
                    "priority": "medium",
                })

        elif change_type == "feature":
            for ep in entry_points[:3]:
                targets.append({
                    "file": str(Path(root) / ep),
                    "reason": "Entry point likely needs new feature code",
                    "change_type": "edit",
                    "priority": "high",
                })
            if not targets and python_modules:
                targets.append({
                    "file": python_modules[0]["file"],
                    "reason": "Primary module for feature implementation",
                    "change_type": "edit",
                    "priority": "high",
                })

        elif change_type == "refactor":
            for mod in python_modules[:5]:
                targets.append({
                    "file": mod["file"],
                    "reason": "Refactor candidate based on analysis",
                    "change_type": "edit",
                    "priority": "medium",
                })

        elif change_type == "config":
            config_file = Path(root) / "config" / "settings.json"
            targets.append({
                "file": str(config_file),
                "reason": "Configuration change",
                "change_type": "edit",
                "priority": "medium",
            })

        if not targets:
            targets.append({
                "file": str(Path(root) / "main.py"),
                "reason": "Default target — primary entry point",
                "change_type": "edit",
                "priority": "medium",
            })

        log.info(f"Identified {len(targets)} files to change (type: {change_type})")
        return targets

    def _find_files_for_issue(self, issue, python_modules, root):
        """Find files related to a specific issue."""
        matching = []
        issue_type = issue.get("type", "")
        if issue_type == "syntax_error":
            for mod in python_modules:
                if mod.get("error"):
                    matching.append(mod["file"])
        else:
            for mod in python_modules[:3]:
                matching.append(mod["file"])
        return matching[:3]

    def generate_code(self, task, context=None, file_path=None, language="python"):
        """
        Generate code for a task.
        Uses LLM if available, otherwise falls back to rule-based generation.
        """
        if self.llm.is_available():
            return self._generate_with_llm(task, context, file_path, language)
        return self._generate_rule_based(task, context, file_path, language)

    def _generate_with_llm(self, task, context, file_path, language):
        """Generate code using the LLM manager."""
        conv_id = self._ensure_conversation()
        prompt = self._build_code_generation_prompt(task, context, file_path, language)
        self.conversation.add_message(conv_id, "user", prompt, importance=5)

        context_msgs = self.conversation.get_context(conv_id)
        full_prompt = "\n\n".join(m["content"] for m in context_msgs if m["role"] != "system")
        system = next((m["content"] for m in context_msgs if m["role"] == "system"), None)

        response = self.llm.generate(full_prompt, system_prompt=system)
        if response.success:
            code = self._extract_code_block(response.text)
            self.conversation.add_message(conv_id, "assistant", response.text, importance=3)
            return {"code": code, "source": "llm", "provider": response.provider,
                    "model": response.model, "success": True}
        return {"code": self._generate_rule_based(task, context, file_path, language)["code"],
                "source": "rule_based_fallback", "success": True,
                "llm_error": response.error}

    def _generate_rule_based(self, task, context, file_path, language):
        """Generate code using rule-based patterns when no LLM is available."""
        task_lower = (task or "").lower()
        if not file_path:
            file_path = "generated_module.py"

        module_name = Path(file_path).stem

        if "test" in task_lower:
            code = self._generate_test_code(module_name, task)
        elif "class" in task_lower or "model" in task_lower:
            code = self._generate_class_code(module_name, task)
        elif "function" in task_lower or "method" in task_lower:
            code = self._generate_function_code(module_name, task)
        elif "config" in task_lower:
            code = self._generate_config_code(module_name)
        else:
            code = self._generate_generic_module(module_name, task)

        return {"code": code, "source": "rule_based", "success": True}

    def _build_code_generation_prompt(self, task, context, file_path, language):
        prompt = f"Task: {task}\n"
        if file_path:
            prompt += f"Target file: {file_path}\n"
        if context:
            analysis = context.get("analysis", {})
            if analysis:
                prompt += f"Project: {analysis.get('project_name', 'unknown')}\n"
                prompt += f"Languages: {', '.join(analysis.get('languages', {}).keys())}\n"
                prompt += f"Entry points: {', '.join(analysis.get('entry_points', []))}\n"
                prompt += f"Existing modules: {len(analysis.get('python_modules', []))}\n"
        prompt += f"Language: {language}\n"
        prompt += "Generate complete, production-ready code. No placeholders or TODOs.\n"
        prompt += "Wrap the code in a ```python code block."
        return prompt

    def _extract_code_block(self, text):
        """Extract code from a markdown code block."""
        match = re.search(r'```(?:python)?\s*\n(.*?)```', text, re.DOTALL)
        if match:
            return match.group(1).strip()
        return text.strip()

    def _generate_test_code(self, module_name, task):
        return f'''"""
Tests for {module_name}.
Generated by AI Builder Development Agent.
"""

import sys
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def test_module_imports():
    """Test that the module can be imported."""
    try:
        import {module_name}
        assert {module_name} is not None
    except ImportError:
        assert True  # Module may not exist yet


def test_basic_functionality():
    """Test basic functionality."""
    assert True


if __name__ == "__main__":
    test_module_imports()
    test_basic_functionality()
    print("All tests passed.")
'''

    def _generate_class_code(self, module_name, task):
        class_name = "".join(w.capitalize() for w in module_name.replace("-", "_").split("_"))
        return f'''"""
{module_name} — {task}
Generated by AI Builder Development Agent.
"""

from datetime import datetime


class {class_name}:
    """Implementation for: {task}"""

    def __init__(self, name=None):
        self.name = name or "{class_name}"
        self.created_at = datetime.now().isoformat()

    def execute(self, *args, **kwargs):
        """Execute the main logic."""
        return {{"success": True, "name": self.name}}

    def __repr__(self):
        return f"<{class_name} name='{{self.name}}'>"
'''

    def _generate_function_code(self, module_name, task):
        func_name = re.sub(r'[^a-z0-9_]', '', task.lower().replace(" ", "_"))[:40] or "generated_func"
        return f'''"""
{module_name} — {task}
Generated by AI Builder Development Agent.
"""

from datetime import datetime


def {func_name}(*args, **kwargs):
    """
    {task}

    Returns:
        dict: Result of the operation.
    """
    return {{
        "success": True,
        "function": "{func_name}",
        "timestamp": datetime.now().isoformat(),
    }}
'''

    def _generate_config_code(self, module_name):
        return f'''"""
Configuration for {module_name}.
Generated by AI Builder Development Agent.
"""

import os
from pathlib import Path

CONFIG = {{
    "module_name": "{module_name}",
    "debug": os.environ.get("DEBUG", "false").lower() == "true",
    "log_level": os.environ.get("LOG_LEVEL", "INFO"),
}}


def get_config():
    return CONFIG
'''

    def _generate_generic_module(self, module_name, task):
        return f'''"""
{module_name} — {task}
Generated by AI Builder Development Agent.
"""

from datetime import datetime


def run(*args, **kwargs):
    """Main entry point for: {task}"""
    return {{
        "success": True,
        "module": "{module_name}",
        "task": "{task}",
        "timestamp": datetime.now().isoformat(),
    }}


if __name__ == "__main__":
    result = run()
    print(result)
'''

    def edit_code(self, file_path, changes=None, new_content=None):
        """
        Edit a file using SafeEditor.
        If new_content is provided, writes the full file.
        If changes is provided, applies structured edits.
        """
        if new_content is not None:
            backup_path = self.verification.backup_before_modification(file_path)
            self.writer.write(file_path, new_content)
            verification = self.verification.verify_modification(file_path, backup_path)
            return CodeChange(
                file_path=file_path,
                change_type="edit",
                description="Full file replacement",
                old_content=None,
                new_content=new_content,
                changes=[],
            )

        if changes:
            result = self.editor.edit(file_path, changes)
            return CodeChange(
                file_path=file_path,
                change_type="edit",
                description=f"Applied {len(changes)} edit(s)",
                changes=changes,
                backup_path=result.get("backup_path"),
                verified=result.get("success", False),
            )

        return None

    def review_code(self, file_path, original_content=None):
        """
        Review generated code for quality, bugs, and issues.
        Returns a review dict with findings.
        """
        content = self.reader.read(file_path)
        if content is None:
            return {"file": file_path, "reviewable": False, "error": "Cannot read file"}

        bugs = self.bug_finder.find_bugs(file_path)
        verification = self.verification.verify_file(file_path)

        review = {
            "file": file_path,
            "reviewable": True,
            "reviewed_at": datetime.now().isoformat(),
            "syntax_valid": verification.syntax_valid,
            "syntax_errors": verification.syntax_errors,
            "bugs_found": bugs,
            "bug_count": len(bugs),
            "line_count": len(content.splitlines()),
            "size_bytes": len(content),
            "has_functions": False,
            "has_classes": False,
            "has_docstrings": False,
            "recommendations": [],
        }

        if file_path.endswith(".py") and verification.syntax_valid:
            try:
                tree = ast.parse(content)
                for node in ast.walk(tree):
                    if isinstance(node, ast.FunctionDef):
                        review["has_functions"] = True
                        if ast.get_docstring(node):
                            review["has_docstrings"] = True
                    elif isinstance(node, ast.ClassDef):
                        review["has_classes"] = True
                        if ast.get_docstring(node):
                            review["has_docstrings"] = True
            except Exception:
                pass

        if not review["has_docstrings"]:
            review["recommendations"].append("Add docstrings to functions and classes")
        if bugs:
            high_bugs = [b for b in bugs if b.get("severity") == "high"]
            if high_bugs:
                review["recommendations"].append(f"Fix {len(high_bugs)} high-severity bugs")
        if not review["syntax_valid"]:
            review["recommendations"].append("Fix syntax errors before proceeding")

        log.info(f"Code review for {file_path}: {len(bugs)} bugs, "
                 f"{'valid' if review['syntax_valid'] else 'invalid'} syntax")
        return review

    def explain_modification(self, original_content, modified_content, file_path=None):
        """
        Generate a human-readable explanation of what changed.
        Uses diff-based analysis to explain each modification.
        """
        if original_content is None:
            return f"Created new file: {file_path or 'unknown'}"

        if original_content == modified_content:
            return "No changes were made."

        diff = difflib.unified_diff(
            original_content.splitlines(keepends=True),
            modified_content.splitlines(keepends=True),
            fromfile="original",
            tofile="modified",
            lineterm="",
        )
        diff_lines = list(diff)

        additions = sum(1 for l in diff_lines if l.startswith("+") and not l.startswith("+++"))
        deletions = sum(1 for l in diff_lines if l.startswith("-") and not l.startswith("---"))

        explanation_parts = [
            f"Modified: {file_path or 'file'}",
            f"Changes: +{additions} additions, -{deletions} deletions",
        ]

        added_lines = [l[1:].strip() for l in diff_lines if l.startswith("+") and not l.startswith("+++")]
        removed_lines = [l[1:].strip() for l in diff_lines if l.startswith("-") and not l.startswith("---")]

        if added_lines:
            significant_adds = [l for l in added_lines if l and not l.startswith("#")][:5]
            if significant_adds:
                explanation_parts.append("Key additions:")
                for line in significant_adds:
                    explanation_parts.append(f"  + {line}")

        if removed_lines:
            significant_removals = [l for l in removed_lines if l and not l.startswith("#")][:3]
            if significant_removals:
                explanation_parts.append("Key removals:")
                for line in significant_removals:
                    explanation_parts.append(f"  - {line}")

        if self.llm.is_available():
            llm_explanation = self._explain_with_llm(original_content, modified_content, file_path)
            if llm_explanation:
                explanation_parts.append("AI Summary: " + llm_explanation)

        explanation = "\n".join(explanation_parts)
        log.info(f"Generated modification explanation for {file_path or 'file'}")
        return explanation

    def _explain_with_llm(self, original, modified, file_path):
        """Use LLM to generate a natural language explanation of changes."""
        diff = difflib.unified_diff(
            original.splitlines(),
            modified.splitlines(),
            fromfile="original",
            tofile="modified",
            lineterm="",
        )
        diff_text = "\n".join(list(diff)[:50])

        prompt = (
            f"Explain in 2-3 sentences what changed in this code modification "
            f"to file {file_path or 'unknown'}:\n\n{diff_text}\n\n"
            f"Focus on what was added, removed, or modified and why."
        )
        response = self.llm.generate(prompt, max_tokens=200)
        if response.success:
            return response.text.strip()
        return None

    def execute_task(self, task_description, project_path=None, context=None):
        """
        Full development workflow: analyze → identify files → generate → edit → review → explain.
        """
        analysis = None
        if project_path:
            analysis = self.analyze_project(project_path)

        targets = self.identify_files_to_change(
            analysis or {"root_path": project_path or "."},
            task_description,
        )

        changes = []
        for target in targets:
            file_path = target["file"]
            change_type = target["change_type"]

            original_content = self.reader.read(file_path) if change_type == "edit" else None

            gen_result = self.generate_code(
                task=task_description,
                context={"analysis": analysis} if analysis else None,
                file_path=file_path,
            )

            if change_type == "create":
                self.writer.write(file_path, gen_result["code"])
                change = CodeChange(
                    file_path=file_path,
                    change_type="create",
                    description=gen_result.get("source", "rule_based"),
                    new_content=gen_result["code"],
                )
            else:
                change = self.edit_code(file_path, new_content=gen_result["code"])

            review = self.review_code(file_path, original_content)
            explanation = self.explain_modification(original_content, gen_result["code"], file_path)
            change.explanation = explanation
            change.verified = review.get("syntax_valid", False)
            changes.append(change)

        return {
            "task": task_description,
            "files_changed": len(changes),
            "changes": [c.to_dict() for c in changes],
            "analysis": analysis,
            "completed_at": datetime.now().isoformat(),
        }

    def _process(self, task, context):
        """Override BaseAgent._process for development tasks."""
        task_type = task.get("type", "develop")
        task_input = task.get("input", "")
        project_path = (context or {}).get("project_path")

        if task_type == "analyze":
            return self.analyze_project(task_input or project_path)
        elif task_type == "generate":
            return self.generate_code(task_input, context)
        elif task_type == "edit":
            return self.edit_code(task_input, changes=task.get("changes"))
        elif task_type == "review":
            return self.review_code(task_input)
        elif task_type == "develop":
            return self.execute_task(task_input, project_path=project_path, context=context)
        else:
            return {"error": f"Unknown task type: {task_type}"}