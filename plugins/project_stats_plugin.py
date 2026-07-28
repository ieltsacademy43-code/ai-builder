"""
Sample plugin: Project Stats
Counts files by extension and reports statistics.
"""

from plugins.plugin_manager import Plugin
from core.logger import get_logger

log = get_logger("plugins")


class ProjectStatsPlugin(Plugin):
    """Reports file statistics for a project directory."""

    name = "project_stats"
    version = "1.0.0"
    description = "Counts files by extension and reports project statistics."

    def execute(self, project_path=None, *args, **kwargs):
        """Run the project stats analysis."""
        if not project_path:
            return {"error": "project_path is required"}

        import os
        from pathlib import Path
        from collections import Counter

        root = Path(project_path)
        if not root.exists():
            return {"error": f"Path not found: {project_path}"}

        extensions = Counter()
        total_files = 0
        total_dirs = 0
        total_size = 0

        skip_dirs = {".git", "node_modules", "__pycache__", ".venv", "venv", "env",
                     "dist", "build", ".tox", ".mypy_cache", ".pytest_cache"}

        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in skip_dirs]
            total_dirs += 1
            for f in filenames:
                total_files += 1
                ext = Path(f).suffix.lower() or "(no extension)"
                extensions[ext] += 1
                try:
                    total_size += (Path(dirpath) / f).stat().st_size
                except OSError:
                    pass

        result = {
            "project_path": str(root),
            "total_files": total_files,
            "total_dirs": total_dirs,
            "total_size_mb": round(total_size / (1024 * 1024), 3),
            "extensions": dict(extensions.most_common(20)),
        }

        log.info(f"ProjectStats: {total_files} files, {total_dirs} dirs, "
                 f"{result['total_size_mb']}MB")
        return result