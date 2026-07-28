"""
Progress tracker for AI Builder.
Tracks task and plan completion status.
"""

from datetime import datetime
from core.logger import get_logger
from memory.memory_store import get_memory

log = get_logger("planner")


class ProgressTracker:
    """Tracks progress of tasks within plans."""

    def __init__(self):
        self.memory = get_memory()

    def start_task(self, plan_id, task_id):
        """Mark a task as in-progress."""
        plan = self.memory.retrieve("plans", plan_id)
        if not plan:
            log.error(f"Plan not found: {plan_id}")
            return False

        for task in plan["tasks"]:
            if task["id"] == task_id:
                task["status"] = "in_progress"
                task["started_at"] = datetime.now().isoformat()
                task["updated_at"] = datetime.now().isoformat()
                break
        else:
            log.error(f"Task not found: {task_id}")
            return False

        plan["updated_at"] = datetime.now().isoformat()
        self.memory.store("plans", plan_id, plan)
        log.info(f"Started task '{task_id}' in plan '{plan_id}'")
        return True

    def complete_task(self, plan_id, task_id, result=None):
        """Mark a task as completed."""
        plan = self.memory.retrieve("plans", plan_id)
        if not plan:
            log.error(f"Plan not found: {plan_id}")
            return False

        for task in plan["tasks"]:
            if task["id"] == task_id:
                task["status"] = "completed"
                task["completed_at"] = datetime.now().isoformat()
                task["updated_at"] = datetime.now().isoformat()
                if result:
                    task["metadata"]["result"] = result
                break
        else:
            log.error(f"Task not found: {task_id}")
            return False

        plan["completed_tasks"] = sum(1 for t in plan["tasks"] if t["status"] == "completed")
        plan["updated_at"] = datetime.now().isoformat()

        if plan["completed_tasks"] >= plan["total_tasks"]:
            plan["status"] = "completed"

        self.memory.store("plans", plan_id, plan)
        log.info(f"Completed task '{task_id}' in plan '{plan_id}' "
                 f"({plan['completed_tasks']}/{plan['total_tasks']})")
        return True

    def block_task(self, plan_id, task_id, reason=""):
        """Mark a task as blocked."""
        plan = self.memory.retrieve("plans", plan_id)
        if not plan:
            return False

        for task in plan["tasks"]:
            if task["id"] == task_id:
                task["status"] = "blocked"
                task["metadata"]["block_reason"] = reason
                task["updated_at"] = datetime.now().isoformat()
                break
        else:
            return False

        plan["updated_at"] = datetime.now().isoformat()
        self.memory.store("plans", plan_id, plan)
        log.warning(f"Blocked task '{task_id}': {reason}")
        return True

    def skip_task(self, plan_id, task_id, reason=""):
        """Mark a task as skipped."""
        plan = self.memory.retrieve("plans", plan_id)
        if not plan:
            return False

        for task in plan["tasks"]:
            if task["id"] == task_id:
                task["status"] = "skipped"
                task["metadata"]["skip_reason"] = reason
                task["updated_at"] = datetime.now().isoformat()
                break
        else:
            return False

        plan["updated_at"] = datetime.now().isoformat()
        self.memory.store("plans", plan_id, plan)
        log.info(f"Skipped task '{task_id}': {reason}")
        return True

    def get_progress(self, plan_id):
        """Return a progress summary for a plan."""
        plan = self.memory.retrieve("plans", plan_id)
        if not plan:
            return None

        total = plan["total_tasks"]
        completed = sum(1 for t in plan["tasks"] if t["status"] == "completed")
        in_progress = sum(1 for t in plan["tasks"] if t["status"] == "in_progress")
        blocked = sum(1 for t in plan["tasks"] if t["status"] == "blocked")
        pending = sum(1 for t in plan["tasks"] if t["status"] == "pending")
        skipped = sum(1 for t in plan["tasks"] if t["status"] == "skipped")

        percentage = (completed / total * 100) if total > 0 else 0

        return {
            "plan_id": plan_id,
            "plan_name": plan.get("plan_name", ""),
            "status": plan.get("status", ""),
            "total": total,
            "completed": completed,
            "in_progress": in_progress,
            "blocked": blocked,
            "pending": pending,
            "skipped": skipped,
            "percentage": round(percentage, 1),
            "tasks": plan["tasks"],
            "updated_at": plan.get("updated_at"),
        }

    def get_active_plans(self):
        """Return all plans that are not completed."""
        plan_ids = self.memory.list_keys("plans")
        active = []
        for pid in plan_ids:
            plan = self.memory.retrieve("plans", pid)
            if plan and plan.get("status") == "active":
                active.append(pid)
        return active

    def render_progress_bar(self, plan_id, width=30):
        """Return an ASCII progress bar string for a plan."""
        progress = self.get_progress(plan_id)
        if not progress:
            return "[No plan found]"
        pct = progress["percentage"]
        filled = int(width * pct / 100)
        bar = "█" * filled + "░" * (width - filled)
        return f"[{bar}] {pct:.1f}% ({progress['completed']}/{progress['total']})"