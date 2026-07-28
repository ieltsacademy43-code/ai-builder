"""
File reader for AI Builder.
Reads files with encoding detection, size limits, and format awareness.
"""

import os
from pathlib import Path
from core.logger import get_logger
from config.settings import get_config
from utils.helpers import truncate

log = get_logger("tools")

# Extensions considered text-readable
TEXT_EXTENSIONS = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".java", ".c", ".cpp", ".h", ".hpp",
    ".cs", ".go", ".rs", ".rb", ".php", ".swift", ".kt", ".scala",
    ".html", ".css", ".scss", ".less", ".xml", ".svg",
    ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf",
    ".md", ".rst", ".txt", ".log", ".csv", ".tsv",
    ".sh", ".bash", ".zsh", ".fish", ".bat", ".ps1",
    ".sql", ".graphql", ".proto", ".dockerfile",
    ".env", ".gitignore", ".editorconfig", ".makefile",
    ".lua", ".r", ".dart", ".elm", ".ex", ".exs", ".clj", ".cljs",
}

BINARY_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".webp", ".tiff",
    ".pdf", ".zip", ".tar", ".gz", ".rar", ".7z",
    ".mp3", ".mp4", ".avi", ".mov", ".wav", ".flv",
    ".exe", ".dll", ".so", ".dylib", ".bin",
    ".pyc", ".pyo", ".class", ".o", ".a",
    ".db", ".sqlite", ".sqlite3",
}


class FileReader:
    """Reads project files with safety checks."""

    def __init__(self):
        self.config = get_config()
        self.max_size_mb = self.config.get("max_file_size_mb", 10)

    def read(self, file_path, encoding="utf-8"):
        """Read a text file and return its content."""
        path = Path(file_path)
        if not path.exists():
            log.error(f"File not found: {file_path}")
            return None
        if not path.is_file():
            log.error(f"Not a file: {file_path}")
            return None

        size_mb = path.stat().st_size / (1024 * 1024)
        if size_mb > self.max_size_mb:
            log.error(f"File too large ({size_mb:.1f}MB > {self.max_size_mb}MB): {file_path}")
            return None

        try:
            with open(file_path, "r", encoding=encoding, errors="replace") as f:
                content = f.read()
            log.debug(f"Read {len(content)} chars from {file_path}")
            return content
        except Exception as e:
            log.error(f"Error reading {file_path}: {e}")
            return None

    def read_lines(self, file_path, encoding="utf-8"):
        """Read a file and return a list of lines."""
        content = self.read(file_path, encoding)
        if content is None:
            return []
        return content.splitlines()

    def read_binary(self, file_path):
        """Read a binary file and return bytes."""
        path = Path(file_path)
        if not path.exists():
            return None
        try:
            with open(file_path, "rb") as f:
                return f.read()
        except Exception as e:
            log.error(f"Error reading binary {file_path}: {e}")
            return None

    def read_partial(self, file_path, start_line=0, num_lines=50, encoding="utf-8"):
        """Read a specific range of lines from a file."""
        lines = self.read_lines(file_path, encoding)
        return lines[start_line:start_line + num_lines]

    def read_json(self, file_path):
        """Read and parse a JSON file."""
        import json
        content = self.read(file_path)
        if content is None:
            return None
        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            log.error(f"JSON parse error in {file_path}: {e}")
            return None

    def read_yaml(self, file_path):
        """Read a YAML file (basic parsing without external deps)."""
        content = self.read(file_path)
        if content is None:
            return None
        result = {}
        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if ":" in line:
                key, _, value = line.partition(":")
                result[key.strip()] = value.strip()
        return result

    def is_text_file(self, file_path):
        """Determine if a file is text-readable based on extension."""
        path = Path(file_path)
        ext = path.suffix.lower()
        name = path.name.lower()

        if ext in TEXT_EXTENSIONS:
            return True
        if ext in BINARY_EXTENSIONS:
            return False
        # Files without extension
        if name in {"dockerfile", "makefile", "rakefile", "gemfile"}:
            return True

        # Try to detect by content
        try:
            with open(file_path, "rb") as f:
                chunk = f.read(1024)
            return b"\x00" not in chunk
        except Exception:
            return False

    def get_file_info(self, file_path):
        """Return metadata about a file."""
        path = Path(file_path)
        if not path.exists():
            return None
        stat = path.stat()
        import time
        return {
            "path": str(path),
            "name": path.name,
            "extension": path.suffix,
            "size_bytes": stat.st_size,
            "size_mb": round(stat.st_size / (1024 * 1024), 3),
            "is_text": self.is_text_file(file_path),
            "modified": time.ctime(stat.st_mtime),
            "is_dir": path.is_dir(),
            "is_file": path.is_file(),
        }

    def read_multiple(self, file_paths):
        """Read multiple files and return a dict of path -> content."""
        results = {}
        for fp in file_paths:
            content = self.read(fp)
            results[fp] = content
        return results