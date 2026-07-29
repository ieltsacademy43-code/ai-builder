"""
Improvement Engine for AI Builder.
Analyzes project weaknesses, suggests improvements, and generates improvement plans.
Never modifies itself without explicit approval.
"""

from datetime import datetime
from pathlib import Path
from core.logger import get_logger
from memory.memory_store import get_memory
from config.settings import get_config
from tools.project_analyser import ProjectAnalyser
from tools.bug_finder import BugFinder
from tools.error_analyser import ErrorAnalyser
from planner.task_planner import TaskPlanner
from llm.llm_manager import get_llm_manager

log = get_logger("improvement")


# Severity scoring weights
SEVERITY_SCORES = {
    "critical": 100,
    "high": 50,
    "medium": 25,
    "low": 10,
    "info": 5,
}

PRIORITY_MAP = {
    "critical": "critical",
    "high": "high",
    "medium": "medium",
    "low": "low",
    "info": "low",
}


class Weakness:
    """Represents a detected weakness in the project."""

    def __init__(self, weakness_id, title, description, severity="medium",
                 category="general", file_path=None, line=None, suggestion=""):
        self.id = weakness_id
        self.title = title
        self.description = description
        self.severity = severity
        self.category = category
        self.file_path = file_path
        self.line = line
        self.suggestion = suggestion
        self.score = SEVERITY_SCORES.get(severity, 25)

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "severity": self.severity,
            "category": self.category,
            "file_path": self.file_path,
            "line": self.line,
            "suggestion": self.suggestion,
            "score": self.score,
        }


class Improvement:
    """Represents a suggested improvement."""

    def __init__(self, improvement_id, title, description, priority="medium",
                 category="general", effort="medium", impact="medium",
                 files_affected=None, steps=None):
        self.id = improvement_id
        self.title = title
        self.description = description
        self.priority = priority  # critical, high, medium, low
        self.category = category
        self.effort = effort  # low, medium, high
        self.impact = impact  # low, medium, high
        self.files_affected = files_affected or []
        self.steps = steps or []
        self.estimated_score = self._estimate_score()

    def _estimate_score(self):
        impact_scores = {"high": 30, "medium": 15, "low": 5}
        effort_scores = {"low": 20, "medium": 10, "high": 5}
        priority_scores = {"critical": 50, "high": 30, "medium": 15, "low": 5}
        return (impact_scores.get(self.impact, 15) +
                effort_scores.get(self.effort, 10) +
                priority_scores.get(self.priority, 15))

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "priority": self.priority,
            "category": self.category,
            "effort": self.effort,
            "impact": self.impact,
            "files_affected": self.files_affected,
            "steps": self.steps,
            "score": self.estimated_score,
        }


class ImprovementEngine:
    """
    Analyzes project weaknesses, suggests improvements, and generates plans.
    Never modifies its own code without explicit approval.
    """

    # Files that belong to the improvement engine itself — never auto-modify
    SELF_FILES = {
        "core/improvement_engine.py",
        "core/verification_system.py",
        "core/autonomous_engine.py",
        "core/reasoning_engine.py",
        "ai_agents/dev_agent.py",
        "ai_agents/conversation_manager.py",
        "llm/llm_manager.py",
    }

    def __init__(self, config=None, memory=None):
        self.config = config or get_config()
        self.memory = memory or get_memory()
        self.analyser = ProjectAnalyser()
        self.bug_finder = BugFinder()
        self.error_analyser = ErrorAnalyser()
        self.planner = TaskPlanner()
        self.llm = get_llm_manager()
        self._approval_required = True

    def analyze_weaknesses(self, project_path, deep=True):
        """
        Analyze a project and return a list of detected weaknesses.
        """
        analysis = self.analyser.analyze(project_path, deep=deep)
        if "error" in analysis:
            return {"error": analysis["error"]}

        weaknesses = []
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # 1. Issues from project analysis
        for i, issue in enumerate(analysis.get("issues", [])):
            w = Weakness(
                weakness_id=f"weakness_{timestamp}_{i+1}",
                title=issue.get("message", "Unknown issue"),
                description=issue.get("detail", ""),
                severity=issue.get("severity", "medium"),
                category=issue.get("type", "general"),
                suggestion=self._suggest_for_issue(issue),
            )
            weaknesses.append(w)

        # 2. Bugs from static analysis
        bugs = self.bug_finder.find_bugs_in_project(project_path, max_files=50)
        for i, bug in enumerate(bugs):
            w = Weakness(
                weakness_id=f"bug_{timestamp}_{i+1}",
                title=bug.get("message", "Bug found"),
                description=bug.get("detail", ""),
                severity=bug.get("severity", "low"),
                category=bug.get("type", "bug"),
                file_path=bug.get("file"),
                line=bug.get("line"),
                suggestion=bug.get("detail", "Review and fix"),
            )
            weaknesses.append(w)

        # 3. Structural weaknesses
        weaknesses.extend(self._detect_structural_weaknesses(analysis, timestamp))

        # 4. Code quality weaknesses
        weaknesses.extend(self._detect_quality_weaknesses(analysis, timestamp))

        # 5. Security weaknesses
        weaknesses.extend(self._detect_security_weaknesses(analysis, bugs, timestamp))

        # Deduplicate by title+file
        seen = set()
        unique = []
        for w in weaknesses:
            key = (w.title, w.file_path)
            if key not in seen:
                seen.add(key)
                unique.append(w)

        unique.sort(key=lambda x: x.score, reverse=True)

        result = {
            "project_path": project_path,
            "analyzed_at": datetime.now().isoformat(),
            "total_weaknesses": len(unique),
            "by_severity": self._count_by_severity(unique),
            "by_category": self._count_by_category(unique),
            "weaknesses": [w.to_dict() for w in unique],
        }

        self.memory.store("improvements", f"weaknesses_{timestamp}", result)
        log.info(f"Found {len(unique)} weaknesses in {project_path}")
        return result

    def suggest_improvements(self, project_path, weaknesses_result=None):
        """
        Generate improvement suggestions based on detected weaknesses.
        """
        if weaknesses_result is None:
            weaknesses_result = self.analyze_weaknesses(project_path)
        if "error" in weaknesses_result:
            return weaknesses_result

        improvements = []
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        weakness_map = {w["id"]: w for w in weaknesses_result["weaknesses"]}

        for i, weakness in enumerate(weaknesses_result["weaknesses"]):
            improvement = self._weakness_to_improvement(weakness, i + 1, timestamp)
            improvements.append(improvement)

        # Add proactive improvements
        improvements.extend(self._proactive_improvements(project_path, timestamp))

        # Deduplicate
        seen = set()
        unique = []
        for imp in improvements:
            if imp.title not in seen:
                seen.add(imp.title)
                unique.append(imp)

        unique.sort(key=lambda x: x.estimated_score, reverse=True)

        result = {
            "project_path": project_path,
            "generated_at": datetime.now().isoformat(),
            "total_improvements": len(unique),
            "by_priority": self._count_improvements_by_priority(unique),
            "improvements": [imp.to_dict() for imp in unique],
        }

        # Try LLM-enhanced suggestions if available
        if self.llm.is_available():
            llm_suggestions = self._llm_suggest_improvements(weaknesses_result)
            if llm_suggestions:
                result["llm_enhanced"] = llm_suggestions

        self.memory.store("improvements", f"suggestions_{timestamp}", result)
        log.info(f"Suggested {len(unique)} improvements for {project_path}")
        return result

    def prioritize_improvements(self, improvements):
        """Sort improvements by priority and estimated impact."""
        priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        sorted_list = sorted(
            improvements.get("improvements", improvements),
            key=lambda x: (priority_order.get(x.get("priority", "medium"), 2),
                           -x.get("score", 0))
        )
        return sorted_list

    def generate_improvement_plan(self, project_path, max_tasks=20):
        """Generate a task plan from improvement suggestions."""
        suggestions = self.suggest_improvements(project_path)
        if "error" in suggestions:
            return suggestions

        improvements = suggestions.get("improvements", [])[:max_tasks]
        tasks_data = []
        for imp in improvements:
            tasks_data.append({
                "title": imp["title"],
                "description": imp["description"],
                "priority": imp["priority"],
                "metadata": {
                    "type": "improvement",
                    "category": imp["category"],
                    "effort": imp["effort"],
                    "impact": imp["impact"],
                    "files": imp.get("files_affected", []),
                    "steps": imp.get("steps", []),
                },
            })

        plan = self.planner.create_plan(
            plan_name=f"Improvement plan: {project_path}",
            tasks_data=tasks_data,
            project_path=project_path,
        )

        self.memory.store("improvements", f"plan_{plan['plan_id']}", {
            "project_path": project_path,
            "suggestions": suggestions,
            "plan": plan,
            "created_at": datetime.now().isoformat(),
        })

        log.info(f"Generated improvement plan with {len(tasks_data)} tasks for {project_path}")
        return plan

    def propose_self_modification(self):
        """
        Analyze the improvement engine's own code and propose modifications.
        NEVER auto-applies — always returns a proposal requiring approval.
        """
        root = Path(self.config.get("root_dir", "."))
        self_files = [str(root / f) for f in self.SELF_FILES if (root / f).exists()]

        proposal = {
            "type": "self_modification",
            "warning": "This proposal modifies the improvement engine itself. "
                       "Explicit approval is required before any changes are applied.",
            "requires_approval": True,
            "approval_granted": False,
            "files_analyzed": self_files,
            "weaknesses_found": [],
            "proposed_changes": [],
            "created_at": datetime.now().isoformat(),
        }

        for file_path in self_files:
            bugs = self.bug_finder.find_bugs(file_path)
            for bug in bugs:
                if bug.get("severity") in ("high", "medium"):
                    proposal["weaknesses_found"].append({
                        "file": file_path,
                        "bug": bug,
                        "proposed_fix": bug.get("detail", "Manual review required"),
                    })

        proposal["total_weaknesses"] = len(proposal["weaknesses_found"])
        log.info(f"Self-modification proposal: {proposal['total_weaknesses']} weaknesses found "
                 f"(approval required)")
        return proposal

    def review_proposal(self, proposal):
        """Review a self-modification proposal and assess risk."""
        review = {
            "safe_to_apply": True,
            "risk_level": "low",
            "concerns": [],
            "recommendations": [],
            "reviewed_at": datetime.now().isoformat(),
        }

        if not proposal.get("requires_approval"):
            review["safe_to_apply"] = False
            review["risk_level"] = "high"
            review["concerns"].append("Proposal does not require approval — cannot proceed")

        weaknesses = proposal.get("weaknesses_found", [])
        high_risk = [w for w in weaknesses if w.get("bug", {}).get("severity") == "high"]
        if high_risk:
            review["risk_level"] = "medium"
            review["concerns"].append(f"{len(high_risk)} high-severity issues in self files")

        if len(weaknesses) > 10:
            review["risk_level"] = "medium"
            review["concerns"].append("Large number of changes — apply incrementally")

        review["recommendations"].append("Review each change manually before applying")
        review["recommendations"].append("Create a git commit before applying any changes")
        review["recommendations"].append("Run full test suite after changes")

        return review

    def apply_self_modification(self, proposal, approval=False):
        """
        Apply a self-modification proposal.
        Only executes if approval=True — otherwise returns a rejection.
        """
        if not approval:
            return {
                "applied": False,
                "reason": "Self-modification requires explicit approval. "
                          "Call with approval=True to proceed.",
                "warning": "The improvement engine never modifies itself without approval.",
            }

        if not proposal.get("requires_approval"):
            return {"applied": False, "reason": "Invalid proposal format"}

        review = self.review_proposal(proposal)
        if review["risk_level"] == "high":
            return {"applied": False, "reason": "Risk too high",
                    "review": review}

        changes_applied = 0
        from tools.bug_fixer import BugFixer
        fixer = BugFixer()

        for weakness in proposal.get("weaknesses_found", []):
            file_path = weakness.get("file")
            if file_path and file_path in proposal.get("files_analyzed", []):
                result = fixer.fix_file(file_path, create_backup=True)
                changes_applied += result.get("bugs_fixed", 0)

        return {
            "applied": True,
            "changes_applied": changes_applied,
            "review": review,
            "applied_at": datetime.now().isoformat(),
        }

    def _detect_structural_weaknesses(self, analysis, timestamp):
        """Detect structural weaknesses from project analysis."""
        weaknesses = []

        if not analysis.get("has_readme"):
            weaknesses.append(Weakness(
                weakness_id=f"struct_{timestamp}_1",
                title="Missing README documentation",
                description="Project has no README file",
                severity="medium",
                category="documentation",
                suggestion="Create a README.md with project overview, setup, and usage",
            ))

        if not analysis.get("has_tests"):
            weaknesses.append(Weakness(
                weakness_id=f"struct_{timestamp}_2",
                title="No test suite",
                description="No test files detected in the project",
                severity="high",
                category="testing",
                suggestion="Add unit tests for core functionality",
            ))

        if not analysis.get("has_git"):
            weaknesses.append(Weakness(
                weakness_id=f"struct_{timestamp}_3",
                title="No version control",
                description="Project is not under git version control",
                severity="low",
                category="version_control",
                suggestion="Initialize a git repository",
            ))

        if not analysis.get("has_ci"):
            weaknesses.append(Weakness(
                weakness_id=f"struct_{timestamp}_4",
                title="No CI/CD pipeline",
                description="No continuous integration configured",
                severity="low",
                category="ci_cd",
                suggestion="Add GitHub Actions or similar CI pipeline",
            ))

        file_count = analysis.get("file_count", 0)
        if file_count > 100:
            weaknesses.append(Weakness(
                weakness_id=f"struct_{timestamp}_5",
                title="Large project size",
                description=f"Project has {file_count} files — may need modularization",
                severity="low",
                category="organization",
                suggestion="Consider splitting into smaller modules",
            ))

        return weaknesses

    def _detect_quality_weaknesses(self, analysis, timestamp):
        """Detect code quality weaknesses."""
        weaknesses = []

        for mod in analysis.get("python_modules", []):
            if mod.get("error"):
                weaknesses.append(Weakness(
                    weakness_id=f"quality_{timestamp}_{len(weaknesses)+1}",
                    title=f"Syntax error in {mod.get('file', 'unknown')}",
                    description=mod["error"],
                    severity="high",
                    category="syntax_error",
                    file_path=mod.get("file"),
                    suggestion="Fix the syntax error before proceeding",
                ))

            functions = mod.get("functions", [])
            for func in functions:
                if not func.get("docstring"):
                    weaknesses.append(Weakness(
                        weakness_id=f"quality_{timestamp}_{len(weaknesses)+1}",
                        title=f"Missing docstring: {func['name']}",
                        description=f"Function '{func['name']}' in {mod.get('file')} has no docstring",
                        severity="info",
                        category="documentation",
                        file_path=mod.get("file"),
                        line=func.get("line"),
                        suggestion="Add a docstring describing the function's purpose",
                    ))

        return weaknesses

    def _detect_security_weaknesses(self, analysis, bugs, timestamp):
        """Detect security-related weaknesses."""
        weaknesses = []

        for i, bug in enumerate(bugs):
            if bug.get("type") == "hardcoded_secret":
                weaknesses.append(Weakness(
                    weakness_id=f"security_{timestamp}_{i+1}",
                    title="Hardcoded secret detected",
                    description=bug.get("message", "Potential hardcoded password/key"),
                    severity="critical",
                    category="security",
                    file_path=bug.get("file"),
                    line=bug.get("line"),
                    suggestion="Move secrets to environment variables or config files",
                ))
            elif bug.get("type") == "eval_exec":
                weaknesses.append(Weakness(
                    weakness_id=f"security_{timestamp}_{i+1}",
                    title="Use of eval/exec",
                    description=bug.get("message", "eval() or exec() used"),
                    severity="high",
                    category="security",
                    file_path=bug.get("file"),
                    line=bug.get("line"),
                    suggestion="Replace eval/exec with safer alternatives",
                ))

        return weaknesses

    def _weakness_to_improvement(self, weakness, index, timestamp):
        """Convert a weakness to an improvement suggestion."""
        severity = weakness.get("severity", "medium")
        return Improvement(
            improvement_id=f"improvement_{timestamp}_{index}",
            title=f"Fix: {weakness.get('title', 'Unknown')}",
            description=weakness.get("description", ""),
            priority=PRIORITY_MAP.get(severity, "medium"),
            category=weakness.get("category", "general"),
            effort="medium",
            impact="high" if severity in ("critical", "high") else "medium",
            files_affected=[weakness["file_path"]] if weakness.get("file_path") else [],
            steps=[weakness.get("suggestion", "Review and address the issue")],
        )

    def _proactive_improvements(self, project_path, timestamp):
        """Generate proactive improvements not tied to specific weaknesses."""
        improvements = []
        improvements.append(Improvement(
            improvement_id=f"proactive_{timestamp}_1",
            title="Add type hints to Python functions",
            description="Type annotations improve code clarity and enable static analysis",
            priority="low",
            category="code_quality",
            effort="medium",
            impact="medium",
            steps=["Add type hints to function signatures", "Run mypy for validation"],
        ))
        improvements.append(Improvement(
            improvement_id=f"proactive_{timestamp}_2",
            title="Add linting configuration",
            description="Configure flake8 or pylint for automated code quality checks",
            priority="low",
            category="code_quality",
            effort="low",
            impact="medium",
            steps=["Create .flake8 or pyproject.toml config", "Add to CI pipeline"],
        ))
        improvements.append(Improvement(
            improvement_id=f"proactive_{timestamp}_3",
            title="Add Dockerfile for containerization",
            description="Containerize the project for consistent deployment",
            priority="low",
            category="deployment",
            effort="medium",
            impact="medium",
            steps=["Create Dockerfile", "Add .dockerignore", "Test build"],
        ))
        return improvements

    def _llm_suggest_improvements(self, weaknesses_result):
        """Use LLM to generate enhanced improvement suggestions."""
        weakness_summary = "\n".join(
            f"- [{w['severity']}] {w['title']}: {w['description']}"
            for w in weaknesses_result["weaknesses"][:10]
        )
        prompt = (
            "Based on these project weaknesses, suggest 3 specific, actionable "
            "improvements with clear steps:\n\n"
            f"{weakness_summary}\n\n"
            "Format as a list of improvements with title, description, and steps."
        )
        response = self.llm.generate(prompt, max_tokens=500)
        if response.success:
            return response.text
        return None

    def _suggest_for_issue(self, issue):
        """Generate a suggestion for a specific issue type."""
        issue_type = issue.get("type", "")
        suggestions = {
            "documentation": "Add comprehensive documentation",
            "testing": "Create test suite with unit and integration tests",
            "version_control": "Initialize git repository and add .gitignore",
            "organization": "Reorganize into clearer module structure",
            "syntax_error": "Fix the syntax error in the affected file",
        }
        return suggestions.get(issue_type, issue.get("detail", "Review and address"))

    def _count_by_severity(self, weaknesses):
        counts = {}
        for w in weaknesses:
            counts[w.severity] = counts.get(w.severity, 0) + 1
        return counts

    def _count_by_category(self, weaknesses):
        counts = {}
        for w in weaknesses:
            counts[w.category] = counts.get(w.category, 0) + 1
        return counts

    def _count_improvements_by_priority(self, improvements):
        counts = {}
        for imp in improvements:
            counts[imp.priority] = counts.get(imp.priority, 0) + 1
        return counts


def get_improvement_engine():
    """Return a singleton ImprovementEngine instance."""
    if not hasattr(get_improvement_engine, "_instance"):
        get_improvement_engine._instance = ImprovementEngine()
    return get_improvement_engine._instance