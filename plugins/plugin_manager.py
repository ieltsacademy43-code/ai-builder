"""
Plugin system for AI Builder.
Discovers, loads, and manages plugins dynamically.
"""

import os
import importlib
import importlib.util
from pathlib import Path
from datetime import datetime
from core.logger import get_logger
from config.settings import get_config
from memory.memory_store import get_memory
from tools.file_reader import FileReader
from tools.file_writer import FileWriter

log = get_logger("plugins")


class Plugin:
    """Base class for plugins. Override execute() to implement plugin behavior."""

    name = "base_plugin"
    version = "1.0.0"
    description = "Base plugin"

    def __init__(self):
        self.enabled = True

    def execute(self, *args, **kwargs):
        """Execute the plugin. Override in subclasses."""
        raise NotImplementedError("Plugin must implement execute()")

    def get_info(self):
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "enabled": self.enabled,
        }


class PluginManager:
    """Discovers, loads, and manages plugins."""

    def __init__(self, plugins_dir=None):
        self.config = get_config()
        self.root_dir = Path(self.config.get("root_dir", str(Path.cwd())))
        self.plugins_dir = Path(plugins_dir) if plugins_dir else (self.root_dir / "plugins")
        self.plugins_dir.mkdir(parents=True, exist_ok=True)
        self.memory = get_memory()
        self._plugins = {}  # name -> plugin instance
        self._loaded = False

    def discover(self):
        """Find all Python files in the plugins directory."""
        plugin_files = []
        for py_file in self.plugins_dir.glob("*.py"):
            if py_file.name.startswith("_") or py_file.name == "__init__.py":
                continue
            plugin_files.append(str(py_file))
        return plugin_files

    def load_all(self):
        """Load all discovered plugins."""
        if self._loaded:
            return self._plugins

        plugin_files = self.discover()
        for file_path in plugin_files:
            self.load(file_path)

        self._loaded = True
        self._save_registry()
        log.info(f"Loaded {len(self._plugins)} plugins")
        return self._plugins

    def load(self, file_path):
        """Load a single plugin from a file."""
        path = Path(file_path)
        if not path.exists():
            log.error(f"Plugin file not found: {file_path}")
            return False

        module_name = f"plugin_{path.stem}"

        try:
            spec = importlib.util.spec_from_file_location(module_name, str(path))
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            # Find a Plugin subclass in the module
            plugin_instance = None
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (isinstance(attr, type) and issubclass(attr, Plugin)
                        and attr is not Plugin):
                    try:
                        plugin_instance = attr()
                        break
                    except Exception as e:
                        log.error(f"Failed to instantiate plugin {attr_name}: {e}")

            if plugin_instance:
                self._plugins[plugin_instance.name] = plugin_instance
                log.info(f"Loaded plugin: {plugin_instance.name} v{plugin_instance.version}")
                return True
            else:
                log.warning(f"No valid Plugin subclass found in {file_path}")
                return False

        except Exception as e:
            log.error(f"Failed to load plugin {file_path}: {e}")
            return False

    def get_plugin(self, name):
        """Get a loaded plugin by name."""
        if not self._loaded:
            self.load_all()
        return self._plugins.get(name)

    def list_plugins(self):
        """List all loaded plugins."""
        if not self._loaded:
            self.load_all()
        return {name: plugin.get_info() for name, plugin in self._plugins.items()}

    def execute_plugin(self, name, *args, **kwargs):
        """Execute a specific plugin."""
        plugin = self.get_plugin(name)
        if not plugin:
            return {"error": f"Plugin '{name}' not found"}
        if not plugin.enabled:
            return {"error": f"Plugin '{name}' is disabled"}
        try:
            result = plugin.execute(*args, **kwargs)
            return {"success": True, "result": result, "plugin": name}
        except Exception as e:
            log.error(f"Plugin '{name}' execution error: {e}")
            return {"error": str(e), "plugin": name}

    def enable(self, name):
        """Enable a plugin."""
        plugin = self.get_plugin(name)
        if plugin:
            plugin.enabled = True
            self._save_registry()
            return True
        return False

    def disable(self, name):
        """Disable a plugin."""
        plugin = self.get_plugin(name)
        if plugin:
            plugin.enabled = False
            self._save_registry()
            return True
        return False

    def create_plugin(self, name, description="Custom plugin", code=None):
        """Create a new plugin file from a template."""
        class_name = "".join(w.capitalize() for w in name.split("_")) + "Plugin"
        file_name = f"{name.lower().replace(' ', '_')}.py"
        file_path = self.plugins_dir / file_name

        if code is None:
            code = f'''"""
Plugin: {name}
{description}

Created by AI Builder Plugin Manager on {datetime.now().isoformat()}
"""

from plugins.plugin_manager import Plugin
from core.logger import get_logger

log = get_logger("plugins")


class {class_name}(Plugin):
    """Plugin: {name} - {description}"""

    name = "{name}"
    version = "1.0.0"
    description = "{description}"

    def execute(self, *args, **kwargs):
        """Execute the plugin logic."""
        log.info(f"[{self.name}] Executing with args={{args}}, kwargs={{kwargs}}")
        return {{
            "plugin": self.name,
            "status": "executed",
            "args": args,
            "kwargs": kwargs,
        }}
'''

        writer = FileWriter()
        writer.write(file_path, code)
        log.info(f"Created plugin '{name}' at {file_path}")
        return str(file_path)

    def _save_registry(self):
        """Save plugin registry to memory."""
        registry = {name: plugin.get_info() for name, plugin in self._plugins.items()}
        self.memory.store("plugins", "registry", registry)

    def get_registry(self):
        """Get the plugin registry from memory."""
        return self.memory.retrieve("plugins", "registry", {})