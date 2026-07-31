"""
Core engine for AI Builder.
Orchestrates all modules and provides high-level operations.
"""

from datetime import datetime
from pathlib import Path
from core.logger import get_logger
from config.settings import get_config
from memory.memory_store import get_memory
from planner.task_planner import TaskPlanner
from planner.progress_tracker import ProgressTracker
from terminal.runner import TerminalRunner
from github.git_manager import GitManager
from github.github_client import GitHubClient
from supabase.supabase_client import SupabaseClient
from tools.file_reader import FileReader
from tools.file_writer import FileWriter
from tools.safe_editor import SafeEditor
from tools.project_analyser import ProjectAnalyser
from tools.error_analyser import ErrorAnalyser
from tools.bug_finder import BugFinder
from tools.bug_fixer import BugFixer
from tools.doc_generator import DocGenerator
from plugins.plugin_manager import PluginManager
from ai_agents.agent_creator import AgentCreator
from core.reasoning_engine import get_reasoning_engine
from core.verification_system import get_verification_system
from core.autonomous_engine import get_autonomous_engine
from core.improvement_engine import get_improvement_engine
from ai_agents.dev_agent import DevelopmentAgent
from ai_agents.conversation_manager import get_conversation_manager
from ai_agents.human_interaction import get_human_interaction_engine
from llm.llm_manager import get_llm_manager

log = get_logger("core")


class AIBuilderEngine:
    """
    Central engine that orchestrates all AI Builder modules.
    This is the core that will evolve into the CEO AI.
    """

    def __init__(self):
        self.config = get_config()
        self.memory = get_memory()

        # Initialize all modules
        self.reader = FileReader()
        self.writer = FileWriter()
        self.editor = SafeEditor()
        self.analyser = ProjectAnalyser()
        self.error_analyser = ErrorAnalyser()
        self.bug_finder = BugFinder()
        self.bug_fixer = BugFixer()
        self.doc_generator = DocGenerator()
        self.planner = TaskPlanner()
        self.tracker = ProgressTracker()
        self.terminal = TerminalRunner()
        self.git = GitManager()
        self.github = GitHubClient()
        self.supabase = SupabaseClient()
        self.plugins = PluginManager()
        self.agent_creator = AgentCreator()
        self.llm = get_llm_manager()
        self.reasoning = get_reasoning_engine()
        self.verification = get_verification_system()
        self.autonomous = get_autonomous_engine()
        self.improvement = get_improvement_engine()
        self.conversation = get_conversation_manager()
        self.dev_agent = DevelopmentAgent()
        self.interaction = get_human_interaction_engine()

        self._initialized = False

    def initialize(self):
        """Initialize the engine and load plugins."""
        log.info("Initializing AI Builder Engine...")
        self.plugins.load_all()
        self._initialized = True
        log.info("AI Builder Engine initialized successfully.")

        # Store engine state
        self.memory.store("engine", "state", {
            "initialized_at": datetime.now().isoformat(),
            "version": self.config.get("version", "1.0.0"),
            "modules": [
                "file_reader", "file_writer", "safe_editor",
                "project_analyser", "error_analyser", "bug_finder",
                "bug_fixer", "doc_generator", "task_planner",
                "progress_tracker", "terminal", "git",
                "github", "supabase", "plugins", "agent_creator",
                "llm_manager", "reasoning_engine", "conversation_manager",
                "dev_agent", "autonomous_engine", "verification_system",
                "improvement_engine", "human_interaction_engine",
            ],
        })

        return True

    # --- High-level operations ---

    def analyze_project(self, project_path, deep=False):
        """Analyze a project and optionally create a task plan."""
        analysis = self.analyser.analyze(project_path, deep=deep)
        if "error" not in analysis:
            self.memory.store("analyses", project_path, {
                "analysis": analysis,
                "timestamp": datetime.now().isoformat(),
            })
        return analysis

    def analyze_and_plan(self, project_path, deep=False):
        """Analyze a project and generate a task plan from the analysis."""
        analysis = self.analyze_project(project_path, deep=deep)
        if "error" in analysis:
            return {"error": analysis["error"]}
        plan = self.planner.suggest_plan_from_analysis(analysis)
        return {"analysis": analysis, "plan": plan}

    def read_file(self, file_path):
        """Read a file."""
        return self.reader.read(file_path)

    def write_file(self, file_path, content):
        """Write a file."""
        return self.writer.write(file_path, content)

    def edit_file(self, file_path, changes):
        """Safely edit a file."""
        return self.editor.edit(file_path, changes)

    def find_bugs(self, file_path):
        """Find bugs in a file."""
        return self.bug_finder.find_bugs(file_path)

    def fix_bugs(self, file_path):
        """Find and fix bugs in a file."""
        return self.bug_fixer.fix_file(file_path)

    def generate_docs(self, project_path):
        """Generate documentation for a project."""
        readme = self.doc_generator.generate_readme(project_path)
        module_docs = self.doc_generator.generate_module_docs(project_path)
        api_docs = self.doc_generator.generate_api_docs(project_path)
        return {
            "readme": readme,
            "module_docs": module_docs,
            "api_docs": api_docs,
        }

    def run_command(self, command, cwd=None):
        """Run a terminal command."""
        return self.terminal.run(command, cwd=cwd)

    def git_status(self, path=None):
        """Get git status."""
        return self.git.status(path)

    def git_commit(self, message, files=None, path=None):
        """Stage and commit changes."""
        return self.git.add_and_commit(message, files, path)

    def create_agent(self, name, template="custom", **kwargs):
        """Create a new AI agent."""
        return self.agent_creator.create_agent(name, template=template, **kwargs)

    def list_agents(self):
        """List all registered agents."""
        return self.agent_creator.list_agents()

    def list_plugins(self):
        """List all loaded plugins."""
        return self.plugins.list_plugins()

    def reason(self, task_description, context=None):
        """Decompose a task into subtasks with dependencies and execution order."""
        return self.reasoning.reason(task_description, context=context)

    def generate_code(self, task, context=None, file_path=None, language="python"):
        """Generate code using LLM or rule-based fallback."""
        return self.dev_agent.generate_code(task, context, file_path, language)

    def execute_development_task(self, task_description, project_path=None, context=None):
        """Execute a full development task: analyze → identify → generate → edit → review."""
        return self.dev_agent.execute_task(task_description, project_path=project_path, context=context)

    def verify_project(self, project_path, run_tests=True):
        """Verify a project for syntax, runtime, and test errors."""
        return self.verification.verify_project(project_path, run_tests=run_tests)

    def run_autonomous_goal(self, goal, project_path=None, max_retries=3):
        """Set a goal and autonomously execute it."""
        plan = self.autonomous.set_goal(goal, project_path=project_path)
        return self.autonomous.execute_plan(plan["plan_id"], max_retries=max_retries,
                                             project_path=project_path)

    def analyze_weaknesses(self, project_path):
        """Analyze project weaknesses and suggest improvements."""
        return self.improvement.analyze_weaknesses(project_path)

    def suggest_improvements(self, project_path):
        """Generate improvement suggestions for a project."""
        return self.improvement.suggest_improvements(project_path)

    def get_llm_status(self):
        """Return LLM manager status."""
        return self.llm.status()

    def chat(self, message, conversation_id=None):
        """Converse with the assistant via the Human Interaction Layer.

        Returns an InteractionResult dict (response, intent, emotion, tone,
        strategy, followup, conversation_id).
        """
        result = self.interaction.respond(message, conversation_id=conversation_id)
        return result.to_dict()

    def get_status(self):
        """Return the overall engine status."""
        return {
            "initialized": self._initialized,
            "version": self.config.get("version", "1.0.0"),
            "config": self.config.to_dict(),
            "agents": self.list_agents(),
            "plugins": self.list_plugins(),
            "memory_namespaces": self.memory.list_namespaces(),
            "llm": self.llm.status() if hasattr(self, "llm") else None,
            "interaction": self.interaction.status(),
        }

    def shutdown(self):
        """Save state and shut down."""
        self.config.save()
        self.memory.store("engine", "shutdown", {
            "shutdown_at": datetime.now().isoformat(),
        })
        log.info("AI Builder Engine shut down.")