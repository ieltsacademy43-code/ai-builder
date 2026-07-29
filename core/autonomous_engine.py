"""
Autonomous Task Engine for AI Builder.
Receives a goal, creates a task list, executes tasks one by one,
retries failed tasks, and produces progress reports.
Integrates ReasoningEngine, TaskPlanner, DevelopmentAgent, and VerificationSystem.
"""

from datetime import datetime
from core.logger import get_logger
from memory.memory_store import get_memory
from config.settings import get_config
from core.reasoning_engine import get_reasoning_engine
from planner.task_planner import TaskPlanner
from planner.progress_tracker import ProgressTracker
from ai_agents.dev_agent import DevelopmentAgent
from core.verification_system import get_verification_system

log = get_logger("autonomous")


class TaskResult:
    """Result of executing a single task."""

    def __init__(self, task_id, title):
        self.task_id = task_id
        self.title = title
        self.status = "pending"  # pending, running, completed, failed, retried
        self.attempts = 0
        self.max_retries = 3
        self.result = None
        self.error = None
        self.started_at = None
        self.completed_at = None
        self.duration = 0

    def to_dict(self):
        return {
            "task_id": self.task_id,
            "title": self.title,
            "status": self.status,
            "attempts": self.attempts,
            "max_retries": self.max_retries,
            "result": self.result,
            "error": self.error,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "duration": self.duration,
        }


class AutonomousTaskEngine:
    """
    Receives high-level goals, decomposes them into tasks,
    executes each task autonomously, retries failures, and reports progress.
    """

    def __init__(self, config=None, memory=None):
        self.config = config or get_config()
        self.memory = memory or get_memory()
        self.reasoning = get_reasoning_engine()
        self.planner = TaskPlanner()
        self.tracker = ProgressTracker()
        self.dev_agent = DevelopmentAgent()
        self.verification = get_verification_system()
        self._active_goals = {}

    def set_goal(self, goal_description, project_path=None, context=None):
        """
        Receive a high-level goal, decompose it into tasks, and create a plan.
        Returns the created plan.
        """
        log.info(f"Setting goal: {goal_description}")

        reasoning_context = {"project_path": project_path, **(context or {})}
        reasoning_plan = self.reasoning.reason(goal_description, context=reasoning_context)

        tasks_data = []
        for subtask in reasoning_plan["subtasks"]:
            tasks_data.append({
                "title": subtask["title"],
                "description": subtask.get("description", ""),
                "priority": subtask.get("priority", "medium"),
                "depends_on": [],
                "metadata": {
                    "category": subtask.get("category", "general"),
                    "original_task": goal_description,
                    "reasoning_id": subtask.get("id"),
                },
            })

        plan = self.planner.create_plan(
            plan_name=goal_description[:80],
            tasks_data=tasks_data,
            project_path=project_path,
        )

        goal_id = plan["plan_id"]
        self._active_goals[goal_id] = {
            "goal": goal_description,
            "plan_id": goal_id,
            "project_path": project_path,
            "context": context or {},
            "status": "planned",
            "created_at": datetime.now().isoformat(),
        }

        self.memory.store("goals", goal_id, self._active_goals[goal_id])
        log.info(f"Goal set: {goal_id} with {len(tasks_data)} tasks")
        return plan

    def execute_plan(self, plan_id, max_retries=3, project_path=None):
        """
        Execute all tasks in a plan one by one.
        Retries failed tasks up to max_retries.
        """
        plan = self.planner.get_plan(plan_id)
        if not plan:
            return {"error": f"Plan not found: {plan_id}"}

        goal_info = self.memory.retrieve("goals", plan_id, {})
        project_path = project_path or goal_info.get("project_path") or plan.get("project_path")
        context = goal_info.get("context", {})

        ordered_tasks = self.planner.order_tasks(plan["tasks"])
        results = []

        log.info(f"Executing plan '{plan_id}' with {len(ordered_tasks)} tasks")

        for task in ordered_tasks:
            deps = task.get("depends_on", [])
            dep_results = [r for r in results if r.task_id in deps]
            dep_failed = [r for r in dep_results if r.status == "failed"]
            if dep_failed:
                log.warning(f"Skipping task '{task['title']}' — dependency failed")
                result = TaskResult(task["id"], task["title"])
                result.status = "skipped"
                result.error = "Dependency failed"
                results.append(result)
                continue

            result = self._execute_task_with_retry(task, max_retries, project_path, context)
            results.append(result)

            self.tracker.start_task(plan_id, task["id"])
            if result.status == "completed":
                self.tracker.complete_task(plan_id, task["id"], result=result.to_dict())
            else:
                self.tracker.block_task(plan_id, task["id"],
                                       reason=result.error or "Unknown failure")

        report = self.generate_progress_report(plan_id)
        report["task_results"] = [r.to_dict() for r in results]

        goal = self._active_goals.get(plan_id, {})
        goal["status"] = "completed" if all(r.status == "completed" for r in results) else "partial"
        goal["executed_at"] = datetime.now().isoformat()
        self.memory.store("goals", plan_id, goal)

        log.info(f"Plan '{plan_id}' execution complete: "
                 f"{sum(1 for r in results if r.status == 'completed')}/{len(results)} tasks completed")
        return report

    def _execute_task_with_retry(self, task, max_retries, project_path, context):
        """Execute a single task with retry logic."""
        result = TaskResult(task["id"], task["title"])
        result.max_retries = max_retries
        result.started_at = datetime.now().isoformat()

        while result.attempts < max_retries:
            result.attempts += 1
            result.status = "running"
            log.info(f"Executing task '{task['title']}' (attempt {result.attempts}/{max_retries})")

            try:
                task_result = self._execute_single_task(task, project_path, context)
                result.result = task_result
                result.status = "completed"
                result.completed_at = datetime.now().isoformat()
                result.duration = self._calc_duration(result)
                break
            except Exception as e:
                result.error = str(e)
                log.warning(f"Task '{task['title']}' failed (attempt {result.attempts}): {e}")
                if result.attempts < max_retries:
                    result.status = "retried"
                else:
                    result.status = "failed"
                    result.completed_at = datetime.now().isoformat()
                    result.duration = self._calc_duration(result)

        return result

    def _execute_single_task(self, task, project_path, context):
        """Execute a single task based on its category."""
        category = task.get("metadata", {}).get("category", "general")
        title = task.get("title", "")

        if category in ("planning", "design", "analysis", "investigation"):
            return self._execute_analysis_task(task, project_path, context)

        elif category in ("implementation", "deployment"):
            return self._execute_implementation_task(task, project_path, context)

        elif category == "testing":
            return self._execute_testing_task(task, project_path, context)

        elif category == "verification":
            return self._execute_verification_task(task, project_path, context)

        elif category == "documentation":
            return self._execute_documentation_task(task, project_path, context)

        else:
            return {"status": "completed", "message": f"Task '{title}' acknowledged"}

    def _execute_analysis_task(self, task, project_path, context):
        """Execute an analysis/investigation task."""
        if project_path:
            analysis = self.dev_agent.analyze_project(project_path, deep=True)
            return {"status": "completed", "analysis": analysis}
        return {"status": "completed", "message": "Analysis completed (no project path)"}

    def _execute_implementation_task(self, task, project_path, context):
        """Execute an implementation task using the dev agent."""
        result = self.dev_agent.execute_task(
            task_description=task.get("title", ""),
            project_path=project_path,
            context=context,
        )
        if project_path:
            verification = self.verification.verify_project(project_path, run_tests=False)
            result["verification"] = verification
        return result

    def _execute_testing_task(self, task, project_path, context):
        """Execute a testing task."""
        if project_path:
            test_result = self.verification.run_tests(project_path)
            return {"status": "completed", "test_results": test_result}
        return {"status": "completed", "message": "Testing task completed"}

    def _execute_verification_task(self, task, project_path, context):
        """Execute a verification task."""
        if project_path:
            result = self.verification.verify_project(project_path, run_tests=True)
            return {"status": "completed", "verification": result}
        return {"status": "completed", "message": "Verification completed"}

    def _execute_documentation_task(self, task, project_path, context):
        """Execute a documentation task."""
        if project_path:
            from tools.doc_generator import DocGenerator
            gen = DocGenerator()
            readme = gen.generate_readme(project_path)
            module_docs = gen.generate_module_docs(project_path)
            return {"status": "completed", "readme": readme,
                    "module_docs": module_docs}
        return {"status": "completed", "message": "Documentation task completed"}

    def retry_failed(self, plan_id, max_retries=2):
        """Retry all failed tasks in a plan."""
        plan = self.planner.get_plan(plan_id)
        if not plan:
            return {"error": f"Plan not found: {plan_id}"}

        failed_tasks = [t for t in plan["tasks"] if t.get("status") in ("blocked", "pending")]
        if not failed_tasks:
            return {"status": "completed", "message": "No failed tasks to retry"}

        goal_info = self.memory.retrieve("goals", plan_id, {})
        project_path = goal_info.get("project_path")
        context = goal_info.get("context", {})

        results = []
        for task in failed_tasks:
            result = self._execute_task_with_retry(task, max_retries, project_path, context)
            results.append(result)
            if result.status == "completed":
                self.tracker.complete_task(plan_id, task["id"], result=result.to_dict())

        return {
            "retried": len(failed_tasks),
            "completed": sum(1 for r in results if r.status == "completed"),
            "failed": sum(1 for r in results if r.status == "failed"),
            "results": [r.to_dict() for r in results],
        }

    def generate_progress_report(self, plan_id):
        """Generate a detailed progress report for a plan."""
        progress = self.tracker.get_progress(plan_id)
        if not progress:
            return {"error": f"Plan not found: {plan_id}"}

        goal = self.memory.retrieve("goals", plan_id, {})

        report = {
            "plan_id": plan_id,
            "goal": goal.get("goal", progress.get("plan_name", "")),
            "status": progress["status"],
            "progress": f"{progress['completed']}/{progress['total']} ({progress['percentage']}%)",
            "tasks": {
                "total": progress["total"],
                "completed": progress["completed"],
                "in_progress": progress["in_progress"],
                "pending": progress["pending"],
                "blocked": progress["blocked"],
                "skipped": progress["skipped"],
            },
            "percentage": progress["percentage"],
            "task_details": [],
            "generated_at": datetime.now().isoformat(),
        }

        for task in progress.get("tasks", []):
            report["task_details"].append({
                "id": task["id"],
                "title": task["title"],
                "status": task["status"],
                "priority": task.get("priority", "medium"),
                "category": task.get("metadata", {}).get("category", "general"),
            })

        self.memory.store("progress_reports", plan_id, report)
        return report

    def get_active_goals(self):
        """Return all active goals."""
        return self.memory.list_keys("goals")

    def get_goal_status(self, goal_id):
        """Get the status of a specific goal."""
        return self.memory.retrieve("goals", goal_id)

    def _calc_duration(self, result):
        """Calculate duration in seconds."""
        if result.started_at and result.completed_at:
            try:
                start = datetime.fromisoformat(result.started_at)
                end = datetime.fromisoformat(result.completed_at)
                return round((end - start).total_seconds(), 3)
            except (ValueError, TypeError):
                pass
        return 0

    def render_report(self, report):
        """Render a progress report as a human-readable string."""
        lines = [
            "=" * 60,
            f"  Progress Report: {report.get('goal', 'Unknown')}",
            "=" * 60,
            f"  Status: {report['status']}",
            f"  Progress: {report['progress']}",
            "",
            "  Task Breakdown:",
        ]
        for task in report.get("task_details", []):
            status_icon = {"completed": "✓", "in_progress": "→",
                           "blocked": "✗", "pending": "○",
                           "skipped": "-"}.get(task["status"], "?")
            lines.append(f"    {status_icon} [{task['priority']}] {task['title']}")
        lines.append("")
        lines.append("=" * 60)
        return "\n".join(lines)


def get_autonomous_engine():
    """Return a singleton AutonomousTaskEngine instance."""
    if not hasattr(get_autonomous_engine, "_instance"):
        get_autonomous_engine._instance = AutonomousTaskEngine()
    return get_autonomous_engine._instance