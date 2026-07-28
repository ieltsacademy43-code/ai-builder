# AI Builder — Phase 1

A modular AI Builder foundation designed to evolve into a CEO AI.
Built with Python, runs on Termux, fully modular and production-ready.

## Folder Structure

```
ai_builder/
├── main.py                  # Entry point / CLI
├── requirements.txt
├── setup.sh                 # Termux installation
├── run.sh                   # Quick run script
├── core/                    # Core engine
├── agents/                  # Agent system + AI Agent Creator
├── memory/                  # Local memory store
├── planner/                 # Task planner + progress tracker
├── terminal/                # Terminal command runner
├── github/                  # Git manager + GitHub API
├── supabase/                # Supabase integration
├── tools/                   # File reader, writer, safe editor, analyser, bug tools, doc generator
├── plugins/                 # Plugin system
├── config/                  # Configuration
├── logs/                    # Logging system
├── tests/                   # Test suite
├── utils/                   # Shared utilities
└── docs/                    # Generated documentation
```

## Installation

### Termux
```bash
bash setup.sh
```

### Standard Python
```bash
pip install -r requirements.txt
```

## Running

```bash
python main.py
```

Or with arguments:
```bash
python main.py --analyze ./my_project
python main.py --interactive
```

## Capabilities (Phase 1)

- Analyse existing projects (structure, languages, dependencies)
- Read and write project files safely
- Safe code editor with backups and syntax validation
- Task planner and progress tracker
- Terminal command runner
- Error analyser, bug finder, bug fixer
- Git manager (init, add, commit, push, pull, branch)
- GitHub API integration
- Supabase integration
- Documentation generator
- Plugin system
- Local memory (JSON-based)
- AI Agent Creator foundation

## Phase 1 Status

✅ Complete — waiting for Phase 2 instructions.