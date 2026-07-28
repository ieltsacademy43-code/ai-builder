"""
Base agent class for AI Builder.
Provides the foundation for all AI agents in the system.
"""

from datetime import datetime
from core.logger import get_logger
from memory.memory_store import get_memory

log = get_logger("agents")


class BaseAgent:
    """
    Foundation class for all AI agents.

    Each agent has:
    - A name and role
    - A set of capabilities
    - A memory namespace
    - An execute method that processes a task
    """

    def __init__(self, name, role="assistant", description="", capabilities=None):
        self.name = name
        self.role = role
        self.description = description
        self.capabilities = capabilities or []
        self.memory = get_memory()
        self.namespace = f"agent_{name}"
        self.created_at = datetime.now().isoformat()
        self.status = "idle"  # idle, running, completed, error
        self.last_run = None
        self.last_result = None

        # Register agent in memory
        self._register()

    def _register(self):
        """Register this agent in the agent registry."""
        agent_info = {
            "name": self.name,
            "role": self.role,
            "description": self.description,
            "capabilities": self.capabilities,
            "namespace": self.namespace,
            "created_at": self.created_at,
            "status": self.status,
        }
        self.memory.store("agents", self.name, agent_info)

    def execute(self, task, context=None):
        """
        Execute a task.

        task: dict with at least 'type' and 'input' keys.
        context: optional dict with additional context.

        Override in subclasses for specific agent behavior.
        """
        self.status = "running"
        self._update_status("running")

        try:
            result = self._process(task, context or {})
            self.last_result = result
            self.last_run = datetime.now().isoformat()
            self.status = "completed"
            self._update_status("completed")

            # Store in agent history
            self.memory.append_history(self.namespace, "history", {
                "task": task,
                "result": result,
                "timestamp": datetime.now().isoformat(),
            })

            log.info(f"Agent '{self.name}' completed task: {task.get('type', 'unknown')}")
            return result

        except Exception as e:
            self.status = "error"
            self.last_result = {"error": str(e)}
            self._update_status("error")
            log.error(f"Agent '{self.name}' error: {e}")
            return {"error": str(e), "agent": self.name}

    def _process(self, task, context):
        """Override this method in subclasses. Default returns the task unchanged."""
        return {
            "agent": self.name,
            "task": task,
            "status": "processed",
            "message": "Base agent processed task. Override _process for specific behavior.",
        }

    def _update_status(self, status):
        """Update agent status in memory."""
        agent_info = self.memory.retrieve("agents", self.name)
        if agent_info:
            agent_info["status"] = status
            agent_info["last_run"] = self.last_run
            self.memory.store("agents", self.name, agent_info)

    def get_info(self):
        """Return agent information."""
        return {
            "name": self.name,
            "role": self.role,
            "description": self.description,
            "capabilities": self.capabilities,
            "status": self.status,
            "created_at": self.created_at,
            "last_run": self.last_run,
            "last_result": self.last_result,
        }

    def add_capability(self, capability):
        """Add a capability to this agent."""
        if capability not in self.capabilities:
            self.capabilities.append(capability)
            self._register()

    def get_history(self, limit=20):
        """Return the agent's task history."""
        history = self.memory.retrieve(self.namespace, "history", [])
        if isinstance(history, list):
            return history[-limit:]
        return []

    def clear_history(self):
        """Clear the agent's task history."""
        self.memory.clear_namespace(self.namespace)
        self._register()

    def __repr__(self):
        return f"<BaseAgent name='{self.name}' role='{self.role}' status='{self.status}'>"