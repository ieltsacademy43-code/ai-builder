"""
Shared utility helpers for AI Builder.
"""

import os
import json
import hashlib
import platform
from pathlib import Path
from datetime import datetime


def normalize_path(path_str):
    """Normalize a path string, expanding ~ and resolving to absolute."""
    if not path_str:
        return str(Path.cwd())
    return str(Path(path_str).expanduser().resolve())


def ensure_dir(path_str):
    """Create directory if it does not exist."""
    Path(path_str).mkdir(parents=True, exist_ok=True)
    return path_str


def read_json(path_str):
    """Read a JSON file and return parsed content."""
    with open(path_str, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path_str, data, indent=2):
    """Write data to a JSON file."""
    ensure_dir(str(Path(path_str).parent))
    with open(path_str, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=indent, ensure_ascii=False)
    return path_str


def read_text(path_str, encoding="utf-8"):
    """Read a text file and return its content."""
    with open(path_str, "r", encoding=encoding, errors="replace") as f:
        return f.read()


def write_text(path_str, content, encoding="utf-8"):
    """Write text content to a file."""
    ensure_dir(str(Path(path_str).parent))
    with open(path_str, "w", encoding=encoding) as f:
        f.write(content)
    return path_str


def file_hash(path_str, algorithm="sha256"):
    """Compute a hash of a file's content."""
    h = hashlib.new(algorithm)
    with open(path_str, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def string_hash(text, algorithm="sha256"):
    """Compute a hash of a string."""
    h = hashlib.new(algorithm)
    h.update(text.encode("utf-8"))
    return h.hexdigest()


def timestamp(fmt="%Y-%m-%d_%H-%M-%S"):
    """Return a formatted timestamp string."""
    return datetime.now().strftime(fmt)


def is_termux():
    """Detect if running inside Termux."""
    return "com.termux" in os.environ.get("PREFIX", "") or os.path.isdir("/data/data/com.termux")


def get_platform_info():
    """Return a dict with platform information."""
    return {
        "system": platform.system(),
        "node": platform.node(),
        "release": platform.release(),
        "version": platform.version(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "python_version": platform.python_version(),
        "is_termux": is_termux(),
        "cwd": str(Path.cwd()),
    }


def safe_filename(name):
    """Sanitize a string for use as a filename."""
    keep = "-_.()"
    return "".join(c if c.isalnum() or c in keep else "_" for c in name).strip("._")


def chunk_text(text, max_length=4000):
    """Split text into chunks of at most max_length characters."""
    return [text[i:i + max_length] for i in range(0, len(text), max_length)]


def truncate(text, max_length=200, suffix="..."):
    """Truncate text to max_length, appending a suffix."""
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix


def merge_dicts(base, override):
    """Deep-merge override into base, returning a new dict."""
    result = dict(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = merge_dicts(result[key], value)
        else:
            result[key] = value
    return result