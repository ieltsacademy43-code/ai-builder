"""
AI Agent Creator for AI Builder.
Foundation for creating new AI agents programmatically.
"""

import os
from datetime import datetime
from pathlib import Path
from core.logger import get_logger
from config.settings import get_config
from memory.memory_store import get_memory
from tools.file_reader import FileReader
from tools.file_writer import FileWriter
from ai_agents.base_agent import BaseAgent

log = get_logger("agents")


# Agent templates
AGENT_TEMPLATES = {
    "code_reviewer": {
        "role": "code_reviewer",
        "description": "Reviews code for quality, style, and potential issues.",
        "capabilities": ["read_files", "analyze_code", "suggest_improvements"],
    },
    "bug_hunter": {
        "role": "bug_hunter",
        "description": "Finds and reports bugs in source code.",
        "capabilities": ["read_files", "find_bugs", "report_issues"],
    },
    "architect": {
        "role": "architect",
        "description": "Analyzes project architecture and suggests structural improvements.",
        "capabilities": ["analyze_project", "suggest_architecture", "review_structure"],
    },
    "doc_writer": {
        "role": "doc_writer",
        "description": "Generates documentation for code and projects.",
        "capabilities": ["read_files", "generate_docs", "write_docs"],
    },
    "test_generator": {
        "role": "test_generator",
        "description": "Generates test cases for code.",
        "capabilities": ["read_files", "analyze_code", "generate_tests"],
    },
    "devops": {
        "role": "devops",
        "description": "Manages deployment, CI/CD, and infrastructure.",
        "capabilities": ["run_commands", "manage_git", "deploy"],
    },
    "custom": {
        "role": "assistant",
        "description": "Custom agent with user-defined capabilities.",
        "capabilities": [],
    },
}


class AgentCreator:
    """
    Creates and manages AI agents.
    Foundation for the future CEO AI's agent-building capability.
    """

    def __init__(self):
        self.config = get_config()
        self.memory = get_memory()
        self.reader = FileReader()
        self.writer = FileWriter()
        self.root_dir = Path(self.config.get("root_dir", str(Path.cwd())))
        self.agents_dir = self.root_dir / "ai_agents" / "generated"
        self.agents_dir.mkdir(parents=True, exist_ok=True)

    def create_agent(self, name, template="custom", description=None,
                     capabilities=None, config=None):
        """
        Create a new agent definition.

        name: Agent name (used for file and class name).
        template: One of AGENT_TEMPLATES keys.
        description: Override template description.
        capabilities: Override template capabilities.
        config: Agent-specific configuration dict.

        Returns the agent info dict.
        """
        if template not in AGENT_TEMPLATES:
            log.warning(f"Unknown template '{template}', using 'custom'")
            template = "custom"

        tmpl = AGENT_TEMPLATES[template]
        description = description or tmpl["description"]
        capabilities = capabilities or tmpl["capabilities"]
        config = config or {}

        # Generate the agent file
        agent_code = self._generate_agent_code(name, description, capabilities, config, template)
        file_name = f"{name.lower().replace(' ', '_')}.py"
        file_path = self.agents_dir / file_name
        self.writer.write(file_path, agent_code)

        # Register in memory
        agent_info = {
            "name": name,
            "template": template,
            "role": tmpl["role"],
            "description": description,
            "capabilities": capabilities,
            "config": config,
            "file": str(file_path),
            "created_at": datetime.now().isoformat(),
            "status": "created",
        }
        self.memory.store("agent_registry", name, agent_info)

        log.info(f"Created agent '{name}' using template '{template}' at {file_path}")
        return agent_info

    def list_agents(self):
        """List all registered agents."""
        return self.memory.list_keys("agent_registry")

    def get_agent_info(self, name):
        """Get information about a registered agent."""
        return self.memory.retrieve("agent_registry", name)

    def delete_agent(self, name):
        """Delete a registered agent."""
        info = self.memory.retrieve("agent_registry", name)
        if not info:
            return False

        # Delete the file
        file_path = Path(info.get("file", ""))
        if file_path.exists():
            self.writer.delete_file(str(file_path))

        # Remove from registry
        self.memory.delete("agent_registry", name)
        log.info(f"Deleted agent '{name}'")
        return True

    def list_templates(self):
        """List available agent templates."""
        return {k: v["description"] for k, v in AGENT_TEMPLATES.items()}

    def _generate_agent_code(self, name, description, capabilities, config, template):
        """Generate Python source code for a new agent."""
        class_name = "".join(word.capitalize() for word in name.split("_")) + "Agent"
        caps_str = ", ".join(f'"{c}"' for c in capabilities) if capabilities else ""

        code = f'''"""
Auto-generated agent: {name}
{description}

Created by AI Builder Agent Creator on {datetime.now().isoformat()}
Template: {template}
"""

from ai_agents.base_agent import BaseAgent
from core.logger import get_logger

log = get_logger("agents")


class {class_name}(BaseAgent):
    """Agent: {name} - {description}"""

    def __init__(self):
        super().__init__(
            name="{name}",
            role="{template}",
            description="{description}",
            capabilities=[{caps_str}],
        )
        self.agent_config = {repr(config)}

    def _process(self, task, context):
        """Process a task. Customize this for specific agent behavior."""
        task_type = task.get("type", "unknown")
        task_input = task.get("input", {{}})

        log.info(f"[{{self.name}}] Processing task: {{task_type}}")

        result = {{
            "agent": self.name,
            "task_type": task_type,
            "status": "processed",
            "input": task_input,
            "context": context,
            "config": self.agent_config,
        }}

        # Add task-specific logic here
        if task_type == "analyze":
            result["message"] = "Analysis complete."
        elif task_type == "review":
            result["message"] = "Review complete."
        elif task_type == "execute":
            result["message"] = "Execution complete."
        else:
            result["message"] = f"Task type '{{task_type}}' processed."

        return result


# Convenience function to get an instance
def get_agent():
    return {class_name}()


if __name__ == "__main__":
    agent = {class_name}()
    print(agent.get_info())
'''
        return code

    def instantiate_agent(self, name):
        """Dynamically load and instantiate a generated agent."""
        import importlib.util

        info = self.memory.retrieve("agent_registry", name)
        if not info:
            log.error(f"Agent not found: {name}")
            return None

        file_path = info.get("file")
        if not file_path or not Path(file_path).exists():
            log.error(f"Agent file not found: {file_path}")
            return None

        try:
            spec = importlib.util.spec_from_file_location(name, file_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            if hasattr(module, "get_agent"):
                return module.get_agent()
            else:
                log.error(f"Agent module {name} has no get_agent() function")
                return None
        except Exception as e:
            log.error(f"Failed to instantiate agent {name}: {e}")
            return None