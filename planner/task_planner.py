"""
Task planner for AI Builder.
Creates structured, ordered task plans from project analysis.
"""

from datetime import datetime
from core.logger import get_logger
from memory.memory_store import get_memory

log = get_logger("planner")


class Task:
    """Represents a single task in a plan."""

    def __init__(self, task_id, title, description="", priority="medium",
                 depends_on=None, status="pending", metadata=None):
        self.id = task_id
        self.title = title
        self.description = description
        self.priority = priority  # low, medium, high, critical
        self.depends_on = depends_on or []
        self.status = status  # pending, in_progress, completed, blocked, skipped
        self.metadata = metadata or {}
        self.created_at = datetime.now().isoformat()
        self.updated_at = self.created_at
        self.started_at = None
        self.completed_at = None

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "priority": self.priority,
            "depends_on": self.depends_on,
            "status": self.status,
            "metadata": self.metadata,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
        }

    @classmethod
    def from_dict(cls, data):
        task = cls(
            task_id=data["id"],
            title=data["title"],
            description=data.get("description", ""),
            priority=data.get("priority", "medium"),
            depends_on=data.get("depends_on", []),
            status=data.get("status", "pending"),
            metadata=data.get("metadata", {}),
        )
        task.created_at = data.get("created_at", task.created_at)
        task.updated_at = data.get("updated_at", task.updated_at)
        task.started_at = data.get("started_at")
        task.completed_at = data.get("completed_at")
        return task


class TaskPlanner:
    """Creates and manages structured task plans."""

    def __init__(self):
        self.memory = get_memory()

    def create_plan(self, plan_name, tasks_data, project_path=None):
        """
        Create a task plan from a list of task dictionaries.

        Each task dict must have: title (str).
        Optional: description, priority, depends_on, metadata.
        """
        plan_id = f"plan_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        tasks = []
        for i, td in enumerate(tasks_data):
            task = Task(
                task_id=f"{plan_id}_task_{i+1}",
                title=td["title"],
                description=td.get("description", ""),
                priority=td.get("priority", "medium"),
                depends_on=td.get("depends_on", []),
                metadata=td.get("metadata", {}),
            )
            tasks.append(task.to_dict())

        plan = {
            "plan_id": plan_id,
            "plan_name": plan_name,
            "project_path": project_path,
            "tasks": tasks,
            "status": "active",
            "total_tasks": len(tasks),
            "completed_tasks": 0,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }

        self.memory.store("plans", plan_id, plan)
        if project_path:
            self.memory.store("plan_index", project_path, plan_id)

        log.info(f"Created plan '{plan_name}' with {len(tasks)} tasks (ID: {plan_id})")
        return plan

    def get_plan(self, plan_id):
        """Retrieve a plan by ID."""
        return self.memory.retrieve("plans", plan_id)

    def list_plans(self):
        """List all plan IDs."""
        return self.memory.list_keys("plans")

    def get_plan_for_project(self, project_path):
        """Get the most recent plan for a project path."""
        return self.memory.retrieve("plan_index", project_path)

    def order_tasks(self, tasks):
        """Topologically sort tasks based on dependencies."""
        task_map = {t["id"]: t for t in tasks}
        visited = set()
        temp_mark = set()
        ordered = []

        def visit(task_id):
            if task_id in visited:
                return
            if task_id in temp_mark:
                log.warning(f"Circular dependency detected for task '{task_id}'")
                return
            temp_mark.add(task_id)
            task = task_map.get(task_id)
            if task:
                for dep in task.get("depends_on", []):
                    visit(dep)
            temp_mark.discard(task_id)
            if task_id not in visited:
                visited.add(task_id)
                ordered.append(task_map[task_id])

        for t in tasks:
            visit(t["id"])

        return ordered

    def suggest_plan_from_analysis(self, analysis):
        """
        Generate a suggested task plan from project analysis results.

        analysis: dict from ProjectAnalyser.analyze()
        """
        tasks_data = []
        issues = analysis.get("issues", [])

        # Bug-fix tasks
        for issue in issues:
            tasks_data.append({
                "title": f"Fix: {issue.get('type', 'issue')} — {issue.get('message', '')}",
                "description": issue.get("detail", ""),
                "priority": "high" if issue.get("severity") == "high" else "medium",
                "metadata": {"type": "bugfix", "source": issue},
            })

        # Improvement tasks
        suggestions = analysis.get("suggestions", [])
        for s in suggestions:
            tasks_data.append({
                "title": f"Improve: {s.get('title', 'improvement')}",
                "description": s.get("description", ""),
                "priority": s.get("priority", "low"),
                "metadata": {"type": "improvement", "source": s},
            })

        # Documentation task
        if not analysis.get("has_readme", False):
            tasks_data.append({
                "title": "Generate README.md",
                "description": "Project has no README. Generate documentation.",
                "priority": "medium",
                "metadata": {"type": "documentation"},
            })

        # Test coverage task
        if analysis.get("test_file_count", 0) == 0:
            tasks_data.append({
                "title": "Add test suite",
                "description": "No tests found. Create initial test suite.",
                "priority": "medium",
                "metadata": {"type": "testing"},
            })

        if not tasks_data:
            tasks_data.append({
                "title": "Review project",
                "description": "No issues detected. Review project manually.",
                "priority": "low",
                "metadata": {"type": "review"},
            })

        plan = self.create_plan(
            plan_name=f"Analysis: {analysis.get('project_name', 'project')}",
            tasks_data=tasks_data,
            project_path=analysis.get("root_path"),
        )
        return plan