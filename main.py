#!/usr/bin/env python3
"""
AI Builder — Phase 1 Entry Point
A modular AI Builder foundation designed to evolve into a CEO AI.

Usage:
  python main.py                      # Interactive mode
  python main.py --analyze <path>     # Analyze a project
  python main.py --bugs <file>        # Find bugs in a file
  python main.py --fix <file>         # Find and fix bugs
  python main.py --docs <path>        # Generate documentation
  python main.py --git <path>          # Git status
  python main.py --agents              # List agents
  python main.py --plugins             # List plugins
  python main.py --status              # Engine status
  python main.py --test                # Run test suite
"""

import sys
import os
from pathlib import Path

# Ensure project root is in path
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.engine import AIBuilderEngine
from core.logger import get_logger
from config.settings import get_config
from tools.file_reader import FileReader
from tools.project_analyser import ProjectAnalyser
from utils.helpers import get_platform_info, is_termux

log = get_logger("main")


BANNER = """
╔══════════════════════════════════════════════════╗
║                                                  ║
║          AI  B U I L D E R  —  Phase 1          ║
║                                                  ║
║   Modular AI Builder → Future CEO AI            ║
║                                                  ║
╚══════════════════════════════════════════════════╝
"""

HELP_TEXT = """
Available Commands:
  analyze <path>      Analyze a project
  read <file>         Read a file
  write <file>        Write to a file (prompts for content)
  bugs <file>         Find bugs in a file
  fix <file>          Find and fix bugs
  docs <path>         Generate documentation
  git <path>          Git status
  agents              List AI agents
  create-agent <name> Create a new agent
  plugins             List plugins
  status              Show engine status
  memory              Show memory namespaces
  plan <path>         Analyze and create a task plan
  help                Show this help
  exit                Quit

CLI Flags:
  --analyze <path>    Analyze and exit
  --bugs <file>      Find bugs and exit
  --fix <file>       Fix bugs and exit
  --docs <path>      Generate docs and exit
  --status           Show status and exit
  --test             Run tests and exit
"""


def print_banner():
    print(BANNER)


def cmd_analyze(engine, args):
    if not args:
        print("Usage: analyze <path>")
        return
    path = args[0]
    print(f"\nAnalyzing: {path}\n")
    analysis = engine.analyze_project(path, deep=True)
    if "error" in analysis:
        print(f"Error: {analysis['error']}")
        return
    print(engine.analyser.get_summary(analysis))
    print("")
    issues = analysis.get("issues", [])
    if issues:
        print(f"Issues found ({len(issues)}):")
        for i, issue in enumerate(issues, 1):
            print(f"  {i}. [{issue['severity']}] {issue['message']}")
    suggestions = analysis.get("suggestions", [])
    if suggestions:
        print(f"\nSuggestions ({len(suggestions)}):")
        for i, s in enumerate(suggestions, 1):
            print(f"  {i}. [{s['priority']}] {s['title']}: {s['description']}")


def cmd_read(engine, args):
    if not args:
        print("Usage: read <file>")
        return
    reader = FileReader()
    content = reader.read(args[0])
    if content is None:
        print(f"Could not read: {args[0]}")
        return
    print(f"\n--- {args[0]} ---\n")
    print(content)
    print(f"\n--- End ({len(content)} chars) ---")


def cmd_write(engine, args):
    if not args:
        print("Usage: write <file>")
        return
    file_path = args[0]
    print(f"Enter content for {file_path} (Ctrl+D or empty line to finish):")
    lines = []
    try:
        while True:
            line = input()
            if line == "":
                break
            lines.append(line)
    except EOFError:
        pass
    content = "\n".join(lines)
    if engine.writer.write(file_path, content):
        print(f"Wrote {len(content)} chars to {file_path}")
    else:
        print("Write failed.")


def cmd_bugs(engine, args):
    if not args:
        print("Usage: bugs <file>")
        return
    bugs = engine.find_bugs(args[0])
    if not bugs:
        print("No bugs found!")
        return
    print(f"\nFound {len(bugs)} potential bugs:\n")
    for i, bug in enumerate(bugs, 1):
        print(f"  {i}. [{bug['severity']}] {bug['type']} (line {bug.get('line', '?')})")
        print(f"     {bug['message']}")
        print(f"     {bug['detail']}")
        print("")


def cmd_fix(engine, args):
    if not args:
        print("Usage: fix <file>")
        return
    result = engine.fix_bugs(args[0])
    print(f"\nBugs found: {result['bugs_found']}")
    print(f"Bugs fixed: {result['bugs_fixed']}")
    if result.get("backup_path"):
        print(f"Backup: {result['backup_path']}")
    if result.get("failed_fixes"):
        print(f"Failed fixes: {len(result['failed_fixes'])}")
        for fail in result["failed_fixes"]:
            print(f"  - {fail}")


def cmd_docs(engine, args):
    if not args:
        print("Usage: docs <path>")
        return
    print(f"\nGenerating documentation for: {args[0]}\n")
    result = engine.generate_docs(args[0])
    print(f"README: {result['readme']}")
    print(f"Module docs: {len(result['module_docs'])} files")
    print(f"API reference: {result['api_docs']}")


def cmd_git(engine, args):
    path = args[0] if args else str(Path.cwd())
    status = engine.git_status(path)
    if not status.get("is_repo"):
        print("Not a git repository.")
        return
    files = status.get("files", [])
    if not files:
        print("Working tree clean.")
    else:
        print(f"\n{len(files)} changed files:")
        for f in files:
            print(f"  {f['status']} {f['file']}")


def cmd_agents(engine, args):
    agents = engine.list_agents()
    if not agents:
        print("No agents registered. Use 'create-agent <name>' to create one.")
        return
    print(f"\nRegistered agents ({len(agents)}):")
    for name in agents:
        info = engine.agent_creator.get_agent_info(name)
        if info:
            print(f"  - {name} [{info.get('template', 'custom')}]")
            print(f"    {info.get('description', '')}")
            print(f"    Capabilities: {', '.join(info.get('capabilities', []))}")


def cmd_create_agent(engine, args):
    if not args:
        print("Usage: create-agent <name> [template]")
        return
    name = args[0]
    template = args[1] if len(args) > 1 else "custom"
    templates = engine.agent_creator.list_templates()
    if template not in templates:
        print(f"Unknown template. Available: {', '.join(templates.keys())}")
        return
    info = engine.create_agent(name, template=template)
    print(f"\nCreated agent: {info['name']}")
    print(f"  Template: {info['template']}")
    print(f"  Role: {info['role']}")
    print(f"  Description: {info['description']}")
    print(f"  File: {info['file']}")


def cmd_plugins(engine, args):
    plugins = engine.list_plugins()
    if not plugins:
        print("No plugins loaded.")
        return
    print(f"\nLoaded plugins ({len(plugins)}):")
    for name, info in plugins.items():
        print(f"  - {name} v{info['version']} [{'ON' if info['enabled'] else 'OFF'}]")
        print(f"    {info['description']}")


def cmd_status(engine, args):
    status = engine.get_status()
    print(f"\nAI Builder Status:")
    print(f"  Initialized: {status['initialized']}")
    print(f"  Version: {status['version']}")
    print(f"  Environment: {status['config'].get('environment', 'development')}")
    print(f"  Agents: {len(status.get('agents', []))}")
    print(f"  Plugins: {len(status.get('plugins', {}))}")
    print(f"  Memory namespaces: {len(status.get('memory_namespaces', []))}")
    print(f"  Platform: {get_platform_info()['system']} {get_platform_info()['python_version']}")
    print(f"  Termux: {'Yes' if is_termux() else 'No'}")


def cmd_memory(engine, args):
    namespaces = engine.memory.list_namespaces()
    if not namespaces:
        print("No memory namespaces.")
        return
    print(f"\nMemory namespaces ({len(namespaces)}):")
    for ns in namespaces:
        keys = engine.memory.list_keys(ns)
        print(f"  {ns}: {len(keys)} entries")


def cmd_plan(engine, args):
    if not args:
        print("Usage: plan <path>")
        return
    print(f"\nAnalyzing and planning for: {args[0]}\n")
    result = engine.analyze_and_plan(args[0], deep=True)
    if "error" in result:
        print(f"Error: {result['error']}")
        return
    plan = result["plan"]
    print(f"Plan: {plan['plan_name']}")
    print(f"Tasks: {plan['total_tasks']}")
    print(f"Plan ID: {plan['plan_id']}\n")
    for i, task in enumerate(plan["tasks"], 1):
        print(f"  {i}. [{task['priority']}] {task['title']}")
        if task.get("description"):
            print(f"     {task['description']}")


COMMANDS = {
    "analyze": cmd_analyze,
    "read": cmd_read,
    "write": cmd_write,
    "bugs": cmd_bugs,
    "fix": cmd_fix,
    "docs": cmd_docs,
    "git": cmd_git,
    "agents": cmd_agents,
    "create-agent": cmd_create_agent,
    "plugins": cmd_plugins,
    "status": cmd_status,
    "memory": cmd_memory,
    "plan": cmd_plan,
    "help": lambda e, a: print(HELP_TEXT),
}


def interactive_mode(engine):
    """Run the interactive CLI."""
    print_banner()
    print(f"Python {get_platform_info()['python_version']} | "
          f"{'Termux' if is_termux() else get_platform_info()['system']}")
    print("Type 'help' for commands, 'exit' to quit.\n")

    while True:
        try:
            user_input = input("ai_builder> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if not user_input:
            continue
        if user_input.lower() in ("exit", "quit", "q"):
            print("Goodbye!")
            break

        parts = user_input.split()
        command = parts[0].lower()
        args = parts[1:]

        if command in COMMANDS:
            try:
                COMMANDS[command](engine, args)
            except Exception as e:
                print(f"Error: {e}")
                log.error(f"Command '{command}' error: {e}")
        else:
            print(f"Unknown command: {command}. Type 'help' for commands.")


def main():
    """Main entry point — handle CLI flags or start interactive mode."""
    engine = AIBuilderEngine()
    engine.initialize()

    args = sys.argv[1:]

    # CLI flag handling
    if not args:
        interactive_mode(engine)
        return

    if args[0] == "--analyze" and len(args) > 1:
        cmd_analyze(engine, [args[1]])
    elif args[0] == "--bugs" and len(args) > 1:
        cmd_bugs(engine, [args[1]])
    elif args[0] == "--fix" and len(args) > 1:
        cmd_fix(engine, [args[1]])
    elif args[0] == "--docs" and len(args) > 1:
        cmd_docs(engine, [args[1]])
    elif args[0] == "--status":
        cmd_status(engine, [])
    elif args[0] == "--agents":
        cmd_agents(engine, [])
    elif args[0] == "--plugins":
        cmd_plugins(engine, [])
    elif args[0] == "--test":
        from tests.test_all import run_all_tests
        run_all_tests()
    elif args[0] in ("--help", "-h"):
        print(HELP_TEXT)
    else:
        print(f"Unknown flag: {args[0]}")
        print("Use --help for usage.")
        sys.exit(1)

    engine.shutdown()


if __name__ == "__main__":
    main()