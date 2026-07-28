"""
File writer for AI Builder.
Writes files with atomic operations and backup support.
"""

import os
import shutil
from pathlib import Path
from datetime import datetime
from core.logger import get_logger
from config.settings import get_config
from utils.helpers import ensure_dir

log = get_logger("tools")


class FileWriter:
    """Writes files safely with atomic writes and backups."""

    def __init__(self):
        self.config = get_config()
        self.backup_on_write = self.config.get("backup_on_edit", True)
        self.root_dir = Path(self.config.get("root_dir", str(Path.cwd())))

    def write(self, file_path, content, encoding="utf-8", create_dirs=True):
        """Write content to a file atomically."""
        path = Path(file_path)

        if create_dirs:
            ensure_dir(str(path.parent))

        # Write to temp file first, then rename (atomic on same filesystem)
        temp_path = path.with_suffix(path.suffix + ".tmp")

        try:
            with open(temp_path, "w", encoding=encoding) as f:
                f.write(content)

            # Atomic rename
            temp_path.replace(path)
            log.info(f"Wrote {len(content)} chars to {file_path}")
            return True
        except Exception as e:
            log.error(f"Error writing {file_path}: {e}")
            if temp_path.exists():
                temp_path.unlink()
            return False

    def write_lines(self, file_path, lines, encoding="utf-8"):
        """Write a list of lines to a file."""
        content = "\n".join(lines) + "\n"
        return self.write(file_path, content, encoding)

    def append(self, file_path, content, encoding="utf-8"):
        """Append content to an existing file."""
        path = Path(file_path)
        ensure_dir(str(path.parent))
        try:
            with open(file_path, "a", encoding=encoding) as f:
                f.write(content)
            log.debug(f"Appended {len(content)} chars to {file_path}")
            return True
        except Exception as e:
            log.error(f"Error appending to {file_path}: {e}")
            return False

    def write_json(self, file_path, data, indent=2):
        """Write data as JSON to a file."""
        import json
        content = json.dumps(data, indent=indent, ensure_ascii=False)
        return self.write(file_path, content)

    def create_backup(self, file_path):
        """Create a backup copy of a file."""
        path = Path(file_path)
        if not path.exists():
            return None

        backup_dir = path.parent / ".backups"
        ensure_dir(str(backup_dir))

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"{path.stem}_{timestamp}{path.suffix}"
        backup_path = backup_dir / backup_name

        try:
            shutil.copy2(str(path), str(backup_path))
            log.info(f"Backup created: {backup_path}")
            return str(backup_path)
        except Exception as e:
            log.error(f"Backup failed for {file_path}: {e}")
            return None

    def create_file(self, file_path, content="", encoding="utf-8"):
        """Create a new file (fails if it already exists)."""
        path = Path(file_path)
        if path.exists():
            log.warning(f"File already exists: {file_path}")
            return False
        return self.write(file_path, content, encoding)

    def delete_file(self, file_path):
        """Delete a file safely."""
        path = Path(file_path)
        if not path.exists():
            log.warning(f"File not found for deletion: {file_path}")
            return False
        try:
            path.unlink()
            log.info(f"Deleted: {file_path}")
            return True
        except Exception as e:
            log.error(f"Error deleting {file_path}: {e}")
            return False

    def copy_file(self, src, dest):
        """Copy a file from src to dest."""
        src_path = Path(src)
        dest_path = Path(dest)
        if not src_path.exists():
            log.error(f"Source not found: {src}")
            return False
        ensure_dir(str(dest_path.parent))
        try:
            shutil.copy2(str(src_path), str(dest_path))
            log.info(f"Copied {src} -> {dest}")
            return True
        except Exception as e:
            log.error(f"Copy failed {src} -> {dest}: {e}")
            return False

    def move_file(self, src, dest):
        """Move a file from src to dest."""
        src_path = Path(src)
        dest_path = Path(dest)
        if not src_path.exists():
            log.error(f"Source not found: {src}")
            return False
        ensure_dir(str(dest_path.parent))
        try:
            shutil.move(str(src_path), str(dest_path))
            log.info(f"Moved {src} -> {dest}")
            return True
        except Exception as e:
            log.error(f"Move failed {src} -> {dest}: {e}")
            return False