"""
Reasoning Engine for AI Builder.
Breaks large tasks into smaller subtasks, detects dependencies, and determines execution order.
Uses heuristic pattern matching to decompose common software development tasks.
"""

import re
from datetime import datetime
from core.logger import get_logger
from memory.memory_store import get_memory

log = get_logger("reasoning")


# Task decomposition patterns — keyword → subtask templates
TASK_PATTERNS = [
    {
        "keywords": ["create", "build", "develop", "implement", "add"],
        "subtypes": ["create", "build"],
        "tasks": [
            {"title": "Define requirements and scope", "priority": "high", "category": "planning"},
            {"title": "Design data structures and interfaces", "priority": "high", "category": "design"},
            {"title": "Implement core logic", "priority": "high", "category": "implementation"},
            {"title": "Add error handling and edge cases", "priority": "medium", "category": "implementation"},
            {"title": "Write tests", "priority": "medium", "category": "testing"},
            {"title": "Generate documentation", "priority": "low", "category": "documentation"},
        ],
    },
    {
        "keywords": ["fix", "debug", "repair", "resolve", "patch"],
        "subtypes": ["fix", "debug"],
        "tasks": [
            {"title": "Reproduce the issue", "priority": "high", "category": "investigation"},
            {"title": "Identify root cause", "priority": "high", "category": "investigation"},
            {"title": "Implement fix", "priority": "high", "category": "implementation"},
            {"title": "Verify fix resolves the issue", "priority": "high", "category": "verification"},
            {"title": "Check for regressions", "priority": "medium", "category": "verification"},
            {"title": "Update tests if needed", "priority": "medium", "category": "testing"},
        ],
    },
    {
        "keywords": ["refactor", "restructure", "reorganize", "clean up", "optimize"],
        "subtypes": ["refactor"],
        "tasks": [
            {"title": "Analyze current structure", "priority": "high", "category": "analysis"},
            {"title": "Identify improvement areas", "priority": "high", "category": "analysis"},
            {"title": "Plan refactoring steps", "priority": "high", "category": "planning"},
            {"title": "Apply refactoring changes", "priority": "high", "category": "implementation"},
            {"title": "Verify behavior unchanged", "priority": "high", "category": "verification"},
            {"title": "Update documentation", "priority": "low", "category": "documentation"},
        ],
    },
    {
        "keywords": ["test", "validate", "verify", "qa", "quality"],
        "subtypes": ["test"],
        "tasks": [
            {"title": "Review existing test coverage", "priority": "high", "category": "analysis"},
            {"title": "Identify untested paths", "priority": "high", "category": "analysis"},
            {"title": "Write test cases", "priority": "high", "category": "implementation"},
            {"title": "Run tests and collect results", "priority": "high", "category": "verification"},
            {"title": "Fix failing tests", "priority": "medium", "category": "implementation"},
        ],
    },
    {
        "keywords": ["deploy", "release", "publish", "ship", "rollout"],
        "subtypes": ["deploy"],
        "tasks": [
            {"title": "Run full test suite", "priority": "high", "category": "verification"},
            {"title": "Update version numbers", "priority": "high", "category": "implementation"},
            {"title": "Generate changelog", "priority": "medium", "category": "documentation"},
            {"title": "Create release artifacts", "priority": "high", "category": "implementation"},
            {"title": "Deploy to target environment", "priority": "high", "category": "deployment"},
            {"title": "Verify deployment health", "priority": "high", "category": "verification"},
        ],
    },
    {
        "keywords": ["document", "document", "readme", "docs", "explain"],
        "subtypes": ["document"],
        "tasks": [
            {"title": "Analyze project structure and purpose", "priority": "high", "category": "analysis"},
            {"title": "Generate README", "priority": "high", "category": "documentation"},
            {"title": "Generate API documentation", "priority": "medium", "category": "documentation"},
            {"title": "Generate module-level docs", "priority": "low", "category": "documentation"},
        ],
    },
]

# Dependency rules — categories that typically depend on others
# A task in category X depends on tasks in the categories listed
DEPENDENCY_RULES = {
    "implementation": ["planning", "design", "analysis", "investigation"],
    "testing": ["implementation"],
    "verification": ["implementation", "testing"],
    "documentation": ["implementation"],
    "deployment": ["verification", "testing"],
}


class SubTask:
    """Represents a decomposed subtask with dependency tracking."""

    def __init__(self, task_id, title, priority="medium", category="general",
                 depends_on=None, metadata=None):
        self.id = task_id
        self.title = title
        self.priority = priority
        self.category = category
        self.depends_on = depends_on or []
        self.metadata = metadata or {}
        self.status = "pending"
        self.created_at = datetime.now().isoformat()

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "priority": self.priority,
            "category": self.category,
            "depends_on": self.depends_on,
            "metadata": self.metadata,
            "status": self.status,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            task_id=data["id"],
            title=data["title"],
            priority=data.get("priority", "medium"),
            category=data.get("category", "general"),
            depends_on=data.get("depends_on", []),
            metadata=data.get("metadata", {}),
        )


class ReasoningEngine:
    """
    Breaks large tasks into smaller subtasks, detects dependencies,
    and determines execution order using heuristic analysis.
    """

    def __init__(self, memory=None):
        self.memory = memory or get_memory()

    def decompose(self, task_description, context=None):
        """
        Break a large task into smaller subtasks.

        task_description: Natural language description of the task.
        context: Optional dict with project_path, analysis, etc.

        Returns a list of SubTask objects.
        """
        task_lower = task_description.lower()
        matched_pattern = None
        for pattern in TASK_PATTERNS:
            if any(kw in task_lower for kw in pattern["keywords"]):
                matched_pattern = pattern
                break

        if not matched_pattern:
            matched_pattern = TASK_PATTERNS[0]

        subtasks = []
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        for i, task_def in enumerate(matched_pattern["tasks"]):
            subtask = SubTask(
                task_id=f"subtask_{timestamp}_{i+1}",
                title=task_def["title"],
                priority=task_def.get("priority", "medium"),
                category=task_def.get("category", "general"),
            )
            subtasks.append(subtask)

        self._apply_context(subtasks, task_description, context)
        self._detect_dependencies(subtasks)

        log.info(f"Decomposed task into {len(subtasks)} subtasks "
                 f"(pattern: {matched_pattern['subtypes']})")
        return subtasks

    def _apply_context(self, subtasks, task_description, context):
        """Customize subtask titles based on the original task description."""
        if not context:
            return
        project_path = context.get("project_path")
        if project_path:
            for st in subtasks:
                st.metadata["project_path"] = project_path

        for st in subtasks:
            st.metadata["original_task"] = task_description

    def _detect_dependencies(self, subtasks):
        """
        Detect dependencies between subtasks based on category rules.

        A subtask in category X depends on all earlier subtasks
        whose category is listed in DEPENDENCY_RULES[X].
        """
        for i, task in enumerate(subtasks):
            deps = DEPENDENCY_RULES.get(task.category, [])
            for j in range(i):
                earlier = subtasks[j]
                if earlier.category in deps:
                    task.depends_on.append(earlier.id)
            task.depends_on = list(dict.fromkeys(task.depends_on))

    def order_execution(self, subtasks):
        """
        Topologically sort subtasks by dependencies.
        Returns a new list in execution order.
        """
        task_map = {st.id: st for st in subtasks}
        visited = set()
        in_progress = set()
        ordered = []

        def visit(task_id):
            if task_id in visited:
                return
            if task_id in in_progress:
                log.warning(f"Circular dependency detected for task '{task_id}'")
                return
            in_progress.add(task_id)
            task = task_map.get(task_id)
            if task:
                for dep_id in task.depends_on:
                    visit(dep_id)
                if task_id not in visited:
                    visited.add(task_id)
                    ordered.append(task)
            in_progress.discard(task_id)

        for st in subtasks:
            visit(st.id)

        return ordered

    def detect_dependencies(self, subtasks):
        """Return a dict mapping task_id -> list of dependency IDs."""
        return {st.id: list(st.depends_on) for st in subtasks}

    def reason(self, task_description, context=None):
        """
        Full reasoning pipeline: decompose → detect dependencies → order.

        Returns an ExecutionPlan dict.
        """
        subtasks = self.decompose(task_description, context)
        dependencies = self.detect_dependencies(subtasks)
        ordered = self.order_execution(subtasks)

        plan = {
            "original_task": task_description,
            "subtask_count": len(subtasks),
            "subtasks": [st.to_dict() for st in subtasks],
            "ordered_ids": [st.id for st in ordered],
            "dependencies": dependencies,
            "reasoned_at": datetime.now().isoformat(),
            "context": context or {},
        }

        self.memory.store("reasoning", plan["reasoned_at"], plan)
        log.info(f"Reasoning complete: {len(subtasks)} subtasks, "
                 f"{sum(len(d) for d in dependencies.values())} dependencies")
        return plan

    def get_summary(self, plan):
        """Return a human-readable summary of an execution plan."""
        lines = [
            f"Task: {plan['original_task']}",
            f"Subtasks: {plan['subtask_count']}",
            f"Dependencies: {sum(len(d) for d in plan['dependencies'].values())}",
            "",
            "Execution order:",
        ]
        task_map = {st["id"]: st for st in plan["subtasks"]}
        for i, task_id in enumerate(plan["ordered_ids"], 1):
            task = task_map.get(task_id, {})
            deps = plan["dependencies"].get(task_id, [])
            dep_str = f" (depends on: {', '.join(deps)})" if deps else ""
            lines.append(f"  {i}. [{task.get('priority', '?')}] {task.get('title', task_id)}{dep_str}")
        return "\n".join(lines)


def get_reasoning_engine():
    """Return a singleton ReasoningEngine instance."""
    if not hasattr(get_reasoning_engine, "_instance"):
        get_reasoning_engine._instance = ReasoningEngine()
    return get_reasoning_engine._instance