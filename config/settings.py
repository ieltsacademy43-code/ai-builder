"""
Configuration system for AI Builder.
Loads, saves, and manages application settings.
"""

import os
import json
from pathlib import Path
from datetime import datetime


DEFAULT_CONFIG = {
    "app_name": "AI Builder",
    "version": "1.0.0",
    "environment": "development",
    "root_dir": str(Path(__file__).resolve().parent.parent),
    "memory_dir": "memory",
    "logs_dir": "logs",
    "plugins_dir": "plugins",
    "docs_dir": "docs",
    "max_file_size_mb": 10,
    "backup_on_edit": True,
    "auto_validate_syntax": True,
    "terminal_timeout": 60,
    "github": {
        "token": "",
        "username": "",
        "default_branch": "main",
    },
    "supabase": {
        "url": "",
        "anon_key": "",
        "service_key": "",
    },
    "ai": {
        "provider": "local",
        "api_key": "",
        "model": "",
        "base_url": "",
    },
    "created_at": None,
    "updated_at": None,
}


class Config:
    """Manages application configuration with file persistence and env overrides."""

    def __init__(self, config_path=None):
        self.root_dir = Path(__file__).resolve().parent.parent
        self.config_dir = self.root_dir / "config"
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.config_file = config_path or (self.config_dir / "settings.json")
        self.settings = {}
        self.load()

    def load(self):
        """Load configuration from file, falling back to defaults."""
        if self.config_file.exists():
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    self.settings = json.load(f)
            except (json.JSONDecodeError, IOError):
                self.settings = dict(DEFAULT_CONFIG)
        else:
            self.settings = dict(DEFAULT_CONFIG)

        # Deep-merge any missing default keys
        self._merge_defaults(DEFAULT_CONFIG, self.settings)

        # Apply environment variable overrides
        self._apply_env_overrides()

        # Ensure directories exist
        self._ensure_directories()

        if not self.settings.get("created_at"):
            self.settings["created_at"] = datetime.now().isoformat()

    def save(self):
        """Persist current configuration to disk."""
        self.settings["updated_at"] = datetime.now().isoformat()
        self.config_dir.mkdir(parents=True, exist_ok=True)
        with open(self.config_file, "w", encoding="utf-8") as f:
            json.dump(self.settings, f, indent=2, ensure_ascii=False)

    def get(self, key, default=None):
        """Get a top-level or nested config value using dot notation."""
        keys = key.split(".")
        value = self.settings
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        return value

    def set(self, key, value):
        """Set a top-level or nested config value using dot notation."""
        keys = key.split(".")
        target = self.settings
        for k in keys[:-1]:
            if k not in target or not isinstance(target[k], dict):
                target[k] = {}
            target = target[k]
        target[keys[-1]] = value

    def _merge_defaults(self, defaults, target):
        """Recursively fill missing keys from defaults into target."""
        for key, value in defaults.items():
            if key not in target:
                target[key] = value if not isinstance(value, dict) else dict(value)
            elif isinstance(value, dict) and isinstance(target[key], dict):
                self._merge_defaults(value, target[key])

    def _apply_env_overrides(self):
        """Override specific settings from environment variables."""
        env_map = {
            "AIBUILDER_GITHUB_TOKEN": "github.token",
            "AIBUILDER_GITHUB_USERNAME": "github.username",
            "AIBUILDER_SUPABASE_URL": "supabase.url",
            "AIBUILDER_SUPABASE_ANON_KEY": "supabase.anon_key",
            "AIBUILDER_SUPABASE_SERVICE_KEY": "supabase.service_key",
            "AIBUILDER_AI_API_KEY": "ai.api_key",
            "AIBUILDER_AI_MODEL": "ai.model",
            "AIBUILDER_ENVIRONMENT": "environment",
        }
        for env_var, config_key in env_map.items():
            env_value = os.environ.get(env_var)
            if env_value:
                self.set(config_key, env_value)

    def _ensure_directories(self):
        """Create required runtime directories."""
        for dir_key in ("memory_dir", "logs_dir", "plugins_dir", "docs_dir"):
            dir_name = self.settings.get(dir_key)
            if dir_name:
                dir_path = self.root_dir / dir_name
                dir_path.mkdir(parents=True, exist_ok=True)

    def to_dict(self):
        """Return a copy of the full configuration."""
        return dict(self.settings)

    def reset(self):
        """Reset configuration to defaults."""
        self.settings = dict(DEFAULT_CONFIG)
        self.settings["created_at"] = datetime.now().isoformat()
        self.save()


def get_config():
    """Return a singleton Config instance."""
    if not hasattr(get_config, "_instance"):
        get_config._instance = Config()
    return get_config._instance