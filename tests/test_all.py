"""
Test suite for AI Builder Phase 1.
Run with: python -m pytest tests/ -v
Or:       python tests/run_tests.py
"""

import os
import sys
import json
import tempfile
from pathlib import Path

# Ensure project root is in path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import get_config
from core.logger import get_logger
from memory.memory_store import MemoryStore
from tools.file_reader import FileReader
from tools.file_writer import FileWriter
from tools.safe_editor import SafeEditor
from tools.project_analyser import ProjectAnalyser
from tools.error_analyser import ErrorAnalyser
from tools.bug_finder import BugFinder
from tools.bug_fixer import BugFixer
from tools.doc_generator import DocGenerator
from planner.task_planner import TaskPlanner
from planner.progress_tracker import ProgressTracker
from terminal.runner import TerminalRunner
from github.git_manager import GitManager
from github.github_client import GitHubClient
from supabase.supabase_client import SupabaseClient
from plugins.plugin_manager import PluginManager
from ai_agents.base_agent import BaseAgent
from ai_agents.agent_creator import AgentCreator
from core.engine import AIBuilderEngine
from utils.helpers import normalize_path, timestamp, safe_filename, merge_dicts

log = get_logger("tests")

TESTS_PASSED = 0
TESTS_FAILED = 0


def run_test(name, test_func):
    """Run a single test and track results."""
    global TESTS_PASSED, TESTS_FAILED
    try:
        test_func()
        TESTS_PASSED += 1
        print(f"  [PASS] {name}")
    except Exception as e:
        TESTS_FAILED += 1
        print(f"  [FAIL] {name}: {e}")


# --- Config tests ---

def test_config():
    config = get_config()
    assert config is not None
    assert config.get("app_name") == "AI Builder"
    assert config.get("version") == "1.0.0"


def test_config_set_get():
    config = get_config()
    config.set("test_key", "test_value")
    assert config.get("test_key") == "test_value"
    config.set("nested.key", "nested_value")
    assert config.get("nested.key") == "nested_value"


# --- Memory tests ---

def test_memory():
    mem = MemoryStore()
    mem.store("test_ns", "key1", "value1")
    assert mem.retrieve("test_ns", "key1") == "value1"
    assert mem.retrieve("test_ns", "nonexistent", "default") == "default"
    mem.delete("test_ns", "key1")
    assert mem.retrieve("test_ns", "key1") is None


def test_memory_search():
    mem = MemoryStore()
    mem.store("search_ns", "hello_key", "world value")
    results = mem.search("hello")
    assert len(results) > 0
    results = mem.search("world")
    assert len(results) > 0


# --- File reader/writer tests ---

def test_file_writer_reader():
    writer = FileWriter()
    reader = FileReader()
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        tmp_path = f.name
    try:
        writer.write(tmp_path, "Hello, World!")
        content = reader.read(tmp_path)
        assert content == "Hello, World!"
    finally:
        os.unlink(tmp_path)


def test_file_writer_json():
    writer = FileWriter()
    reader = FileReader()
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        tmp_path = f.name
    try:
        data = {"name": "test", "value": 42}
        writer.write_json(tmp_path, data)
        result = reader.read_json(tmp_path)
        assert result["name"] == "test"
        assert result["value"] == 42
    finally:
        os.unlink(tmp_path)


# --- Safe editor tests ---

def test_safe_editor_replace():
    writer = FileWriter()
    editor = SafeEditor()
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write("def hello():\n    return 'world'\n")
        tmp_path = f.name
    try:
        result = editor.replace_text(tmp_path, "'world'", "'universe'")
        assert result["success"]
        content = FileReader().read(tmp_path)
        assert "'universe'" in content
    finally:
        os.unlink(tmp_path)


def test_safe_editor_syntax_validation():
    editor = SafeEditor()
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write("def hello():\n    return 'world'\n")
        tmp_path = f.name
    try:
        # Try to introduce a syntax error — should be blocked
        result = editor.replace_text(tmp_path, "return 'world'", "return 'world'")
        assert result["success"]
    finally:
        os.unlink(tmp_path)


# --- Project analyser tests ---

def test_project_analyser():
    analyser = ProjectAnalyser()
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a simple project
        (Path(tmpdir) / "main.py").write_text("print('hello')\n")
        (Path(tmpdir) / "requirements.txt").write_text("requests>=2.0\n")
        (Path(tmpdir) / "README.md").write_text("# Test Project\n")

        analysis = analyser.analyze(tmpdir)
        assert analysis["project_name"] == Path(tmpdir).name
        assert analysis["file_count"] >= 2
        assert "Python" in analysis["languages"]
        assert analysis["has_readme"] is True
        assert "python" in analysis["project_types"]


# --- Error analyser tests ---

def test_error_analyser():
    analyser = ErrorAnalyser()
    result = analyser.analyze_error("NameError: name 'x' is not defined")
    assert result["error_type"] == "NameError"
    assert result["category"] == "name"
    assert len(result["suggestions"]) > 0


def test_error_analyser_syntax():
    analyser = ErrorAnalyser()
    result = analyser.analyze_error("SyntaxError: invalid syntax")
    assert result["error_type"] == "SyntaxError"
    assert result["category"] == "syntax"


# --- Bug finder tests ---

def test_bug_finder():
    finder = BugFinder()
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write("import os\nimport sys\n\ndef foo(x=[]):\n    if x == None:\n        pass\n")
        tmp_path = f.name
    try:
        bugs = finder.find_bugs(tmp_path)
        bug_types = [b["type"] for b in bugs]
        assert "mutable_default" in bug_types
        assert "comparison_none" in bug_types
        assert "unused_import" in bug_types
    finally:
        os.unlink(tmp_path)


def test_bug_finder_eval():
    finder = BugFinder()
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write("result = eval('1+1')\n")
        tmp_path = f.name
    try:
        bugs = finder.find_bugs(tmp_path)
        bug_types = [b["type"] for b in bugs]
        assert "eval_exec" in bug_types
    finally:
        os.unlink(tmp_path)


# --- Bug fixer tests ---

def test_bug_fixer_comparison_none():
    fixer = BugFixer()
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write("x = None\nif x == None:\n    print('yes')\n")
        tmp_path = f.name
    try:
        result = fixer.fix_file(tmp_path)
        assert result["bugs_fixed"] > 0
        content = FileReader().read(tmp_path)
        assert "is None" in content
        assert "== None" not in content
    finally:
        os.unlink(tmp_path)


def test_bug_fixer_bare_except():
    fixer = BugFixer()
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write("try:\n    x = 1\nexcept:\n    pass\n")
        tmp_path = f.name
    try:
        result = fixer.fix_file(tmp_path)
        content = FileReader().read(tmp_path)
        assert "except Exception:" in content
    finally:
        os.unlink(tmp_path)


# --- Planner tests ---

def test_task_planner():
    planner = TaskPlanner()
    plan = planner.create_plan("test_plan", [
        {"title": "Task 1", "priority": "high"},
        {"title": "Task 2", "priority": "medium", "depends_on": []},
        {"title": "Task 3", "priority": "low"},
    ])
    assert plan["total_tasks"] == 3
    assert plan["status"] == "active"
    assert len(plan["tasks"]) == 3


def test_progress_tracker():
    planner = TaskPlanner()
    tracker = ProgressTracker()
    plan = planner.create_plan("progress_test", [
        {"title": "Task A"},
        {"title": "Task B"},
    ])
    plan_id = plan["plan_id"]
    task_id = plan["tasks"][0]["id"]

    tracker.start_task(plan_id, task_id)
    progress = tracker.get_progress(plan_id)
    assert progress["in_progress"] == 1

    tracker.complete_task(plan_id, task_id)
    progress = tracker.get_progress(plan_id)
    assert progress["completed"] == 1


# --- Terminal tests ---

def test_terminal_runner():
    runner = TerminalRunner()
    result = runner.run("echo 'hello world'", check_dangerous=False)
    assert result["success"]
    assert "hello world" in result["stdout"]


def test_terminal_dangerous():
    runner = TerminalRunner()
    result = runner.run("rm -rf /", check_dangerous=True)
    assert not result["success"]
    assert result.get("blocked") is True


# --- Git tests ---

def test_git_manager():
    git = GitManager()
    with tempfile.TemporaryDirectory() as tmpdir:
        git.init(tmpdir)
        assert git.is_repo(tmpdir)


# --- Plugin tests ---

def test_plugin_manager():
    pm = PluginManager()
    pm.create_plugin("test_plugin", "A test plugin")
    pm.load_all()
    plugins = pm.list_plugins()
    assert "test_plugin" in plugins


# --- Agent tests ---

def test_base_agent():
    agent = BaseAgent(name="test_agent", role="assistant",
                      description="Test agent", capabilities=["test"])
    result = agent.execute({"type": "test", "input": "hello"})
    assert result["status"] == "processed"
    assert agent.status == "completed"


def test_agent_creator():
    creator = AgentCreator()
    info = creator.create_agent("test_created", template="code_reviewer")
    assert info["name"] == "test_created"
    assert info["template"] == "code_reviewer"
    assert "read_files" in info["capabilities"]


# --- Doc generator tests ---

def test_doc_generator():
    gen = DocGenerator()
    with tempfile.TemporaryDirectory() as tmpdir:
        (Path(tmpdir) / "main.py").write_text('"""Main module."""\n\ndef hello():\n    """Say hello."""\n    return "hi"\n')
        (Path(tmpdir) / "requirements.txt").write_text("requests\n")

        readme_path = gen.generate_readme(tmpdir, project_name="TestProj",
                                          description="A test project")
        assert Path(readme_path).exists()
        content = FileReader().read(readme_path)
        assert "# TestProj" in content


# --- Engine tests ---

def test_engine():
    engine = AIBuilderEngine()
    engine.initialize()
    status = engine.get_status()
    assert status["initialized"] is True
    assert "version" in status


# --- Utils tests ---

def test_utils_safe_filename():
    assert safe_filename("hello world!") == "hello_world"
    assert safe_filename("file/with/slashes") == "file_with_slashes"


def test_utils_merge_dicts():
    base = {"a": 1, "b": {"c": 2, "d": 3}}
    override = {"b": {"d": 4, "e": 5}}
    result = merge_dicts(base, override)
    assert result == {"a": 1, "b": {"c": 2, "d": 4, "e": 5}}


# --- Runner ---

def run_all_tests():
    """Run all tests."""
    print("")
    print("=" * 50)
    print("  AI Builder - Phase 1 Test Suite")
    print("=" * 50)
    print("")

    run_test("Config loads", test_config)
    run_test("Config set/get", test_config_set_get)
    run_test("Memory store/retrieve", test_memory)
    run_test("Memory search", test_memory_search)
    run_test("File writer/reader", test_file_writer_reader)
    run_test("File writer JSON", test_file_writer_json)
    run_test("Safe editor replace", test_safe_editor_replace)
    run_test("Safe editor syntax validation", test_safe_editor_syntax_validation)
    run_test("Project analyser", test_project_analyser)
    run_test("Error analyser", test_error_analyser)
    run_test("Error analyser syntax", test_error_analyser_syntax)
    run_test("Bug finder", test_bug_finder)
    run_test("Bug finder eval", test_bug_finder_eval)
    run_test("Bug fixer comparison_none", test_bug_fixer_comparison_none)
    run_test("Bug fixer bare_except", test_bug_fixer_bare_except)
    run_test("Task planner", test_task_planner)
    run_test("Progress tracker", test_progress_tracker)
    run_test("Terminal runner", test_terminal_runner)
    run_test("Terminal dangerous block", test_terminal_dangerous)
    run_test("Git manager", test_git_manager)
    run_test("Plugin manager", test_plugin_manager)
    run_test("Base agent", test_base_agent)
    run_test("Agent creator", test_agent_creator)
    run_test("Doc generator", test_doc_generator)
    run_test("Engine", test_engine)
    run_test("Utils safe_filename", test_utils_safe_filename)
    run_test("Utils merge_dicts", test_utils_merge_dicts)

    print("")
    print("-" * 50)
    print(f"  Results: {TESTS_PASSED} passed, {TESTS_FAILED} failed")
    print("-" * 50)
    print("")

    if TESTS_FAILED > 0:
        sys.exit(1)
    return True


if __name__ == "__main__":
    run_all_tests()