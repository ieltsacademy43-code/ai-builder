"""
Local memory store for AI Builder.
Provides persistent JSON-based storage for context, history, and project data.
"""

import os
import json
from pathlib import Path
from datetime import datetime

from core.logger import get_logger

log = get_logger("memory")


class MemoryStore:
    """JSON file-based local memory with namespaces."""

    def __init__(self, memory_dir=None):
        root_dir = Path(__file__).resolve().parent.parent
        self.memory_dir = Path(memory_dir) if memory_dir else (root_dir / "memory" / "data")
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self.index_file = self.memory_dir / "_index.json"
        self._index = {}
        self._load_index()

    def _load_index(self):
        """Load the memory index."""
        if self.index_file.exists():
            try:
                with open(self.index_file, "r", encoding="utf-8") as f:
                    self._index = json.load(f)
                if "entries" not in self._index:
                    self._index = {"entries": {}, "created_at": datetime.now().isoformat()}
            except (json.JSONDecodeError, IOError):
                self._index = {"entries": {}, "created_at": datetime.now().isoformat()}
        else:
            self._index = {"entries": {}, "created_at": datetime.now().isoformat()}

    def _save_index(self):
        """Persist the memory index."""
        self._index["updated_at"] = datetime.now().isoformat()
        with open(self.index_file, "w", encoding="utf-8") as f:
            json.dump(self._index, f, indent=2, ensure_ascii=False)

    def _namespace_file(self, namespace):
        """Return the file path for a namespace."""
        safe_name = namespace.replace("/", "_").replace("\\", "_")
        return self.memory_dir / f"{safe_name}.json"

    def store(self, namespace, key, value):
        """Store a value under a namespace and key."""
        data = self._read_namespace(namespace)
        value_entry = {
            "value": value,
            "stored_at": datetime.now().isoformat(),
        }
        data["entries"][key] = value_entry
        self._write_namespace(namespace, data)

        # Update index
        if namespace not in self._index["entries"]:
            self._index["entries"][namespace] = {"keys": [], "created_at": datetime.now().isoformat()}
        if key not in self._index["entries"][namespace]["keys"]:
            self._index["entries"][namespace]["keys"].append(key)
        self._index["entries"][namespace]["updated_at"] = datetime.now().isoformat()
        self._save_index()

        log.debug(f"Stored '{key}' in namespace '{namespace}'")
        return True

    def retrieve(self, namespace, key, default=None):
        """Retrieve a value by namespace and key."""
        data = self._read_namespace(namespace)
        entry = data["entries"].get(key)
        if entry is None:
            return default
        return entry.get("value", default)

    def delete(self, namespace, key):
        """Delete a value by namespace and key."""
        data = self._read_namespace(namespace)
        if key in data["entries"]:
            del data["entries"][key]
            self._write_namespace(namespace, data)
            if namespace in self._index["entries"]:
                if key in self._index["entries"][namespace]["keys"]:
                    self._index["entries"][namespace]["keys"].remove(key)
                self._save_index()
            log.debug(f"Deleted '{key}' from namespace '{namespace}'")
            return True
        return False

    def list_keys(self, namespace):
        """List all keys in a namespace."""
        data = self._read_namespace(namespace)
        return list(data["entries"].keys())

    def list_namespaces(self):
        """List all namespaces."""
        return list(self._index.get("entries", {}).keys())

    def get_namespace_data(self, namespace):
        """Return all entries in a namespace."""
        data = self._read_namespace(namespace)
        return {k: v.get("value") for k, v in data["entries"].items()}

    def clear_namespace(self, namespace):
        """Clear all entries in a namespace."""
        file_path = self._namespace_file(namespace)
        if file_path.exists():
            file_path.unlink()
        if namespace in self._index["entries"]:
            del self._index["entries"][namespace]
            self._save_index()
        log.info(f"Cleared namespace '{namespace}'")
        return True

    def search(self, query, namespace=None):
        """Search keys and string values for a query string."""
        results = []
        namespaces = [namespace] if namespace else self.list_namespaces()
        for ns in namespaces:
            data = self._read_namespace(ns)
            for key, entry in data["entries"].items():
                value = entry.get("value")
                match = False
                if query.lower() in key.lower():
                    match = True
                elif isinstance(value, str) and query.lower() in value.lower():
                    match = True
                if match:
                    results.append({
                        "namespace": ns,
                        "key": key,
                        "value": value,
                        "stored_at": entry.get("stored_at"),
                    })
        return results

    def append_history(self, namespace, key, item, max_items=100):
        """Append an item to a list-valued key, capping the list size."""
        current = self.retrieve(namespace, key, [])
        if not isinstance(current, list):
            current = [current]
        current.append({"item": item, "timestamp": datetime.now().isoformat()})
        if len(current) > max_items:
            current = current[-max_items:]
        self.store(namespace, key, current)
        return True

    def _read_namespace(self, namespace):
        """Read raw namespace data."""
        file_path = self._namespace_file(namespace)
        if file_path.exists():
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return {"entries": {}, "namespace": namespace}
        return {"entries": {}, "namespace": namespace, "created_at": datetime.now().isoformat()}

    def _write_namespace(self, namespace, data):
        """Write raw namespace data."""
        file_path = self._namespace_file(namespace)
        data["namespace"] = namespace
        data["updated_at"] = datetime.now().isoformat()
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)


def get_memory():
    """Return a singleton MemoryStore instance."""
    if not hasattr(get_memory, "_instance"):
        get_memory._instance = MemoryStore()
    return get_memory._instance