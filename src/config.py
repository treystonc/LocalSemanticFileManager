"""Configuration loader for Socrates.

Loads settings from YAML and JSON configuration files.
"""

import json
from pathlib import Path
from typing import Any

import yaml


class Config:
    """Configuration manager for Socrates."""
    
    _instance = None
    _config: dict[str, Any] = {}
    _rules: list[dict[str, Any]] = []
    
    def __new__(cls) -> "Config":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self) -> None:
        if not self._config:
            self._load_config()
            self._load_rules()
    
    def _get_config_dir(self) -> Path:
        """Get the configuration directory path."""
        return Path(__file__).parent.parent / "config"
    
    def _load_config(self) -> None:
        """Load settings from YAML file."""
        config_path = self._get_config_dir() / "settings.yaml"
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                self._config = yaml.safe_load(f) or {}
        else:
            self._config = self._get_default_config()
    
    def _load_rules(self) -> None:
        """Load janitor rules from JSON file."""
        rules_path = self._get_config_dir() / "rules.json"
        if rules_path.exists():
            with open(rules_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self._rules = data.get("rules", [])
        else:
            self._rules = []
    
    def _get_default_config(self) -> dict[str, Any]:
        """Return default configuration."""
        return {
            "watcher": {
                "monitored_folders": [
                    {"path": "~/Downloads", "recursive": False},
                    {"path": "~/Documents", "recursive": True},
                ],
                "debounce_seconds": 2,
            },
            "file_filtering": {
                "max_file_size_mb": 10,
                "skip_extensions": [".exe", ".dll", ".zip", ".rar", ".bin", ".iso"],
                "supported_extensions": [".pdf", ".docx", ".xlsx", ".txt", ".md"],
            },
            "janitor": {
                "auto_move_enabled": False,
                "require_confirmation": True,
            },
            "embedding": {
                "model": "all-MiniLM-L6-v2",
                "chunk_size": 500,
                "chunk_overlap": 50,
            },
            "database": {
                "path": ".socrates/db",
            },
        }
    
    @property
    def watcher(self) -> dict[str, Any]:
        """Get watcher configuration."""
        return self._config.get("watcher", {})
    
    @property
    def file_filtering(self) -> dict[str, Any]:
        """Get file filtering configuration."""
        return self._config.get("file_filtering", {})
    
    @property
    def janitor(self) -> dict[str, Any]:
        """Get janitor configuration."""
        return self._config.get("janitor", {})
    
    @property
    def embedding(self) -> dict[str, Any]:
        """Get embedding configuration."""
        return self._config.get("embedding", {})
    
    @property
    def database(self) -> dict[str, Any]:
        """Get database configuration."""
        return self._config.get("database", {})
    
    @property
    def rules(self) -> list[dict[str, Any]]:
        """Get janitor rules."""
        return self._rules
    
    def get_monitored_folders(self) -> list[tuple[Path, bool]]:
        """Get list of monitored folders with their recursive setting.
        
        Returns:
            List of tuples (path, recursive)
        """
        folders = []
        for folder_config in self.watcher.get("monitored_folders", []):
            path = Path(folder_config["path"]).expanduser()
            recursive = folder_config.get("recursive", False)
            folders.append((path, recursive))
        return folders
    
    def get_supported_extensions(self) -> list[str]:
        """Get list of supported file extensions."""
        return self.file_filtering.get("supported_extensions", [])
    
    def get_skip_extensions(self) -> list[str]:
        """Get list of extensions to skip."""
        return self.file_filtering.get("skip_extensions", [])
    
    def get_max_file_size_bytes(self) -> int:
        """Get maximum file size in bytes."""
        max_mb = self.file_filtering.get("max_file_size_mb", 10)
        return max_mb * 1024 * 1024
    
    def get_debounce_seconds(self) -> float:
        """Get debounce time in seconds."""
        return self.watcher.get("debounce_seconds", 2)
    
    def get_model_name(self) -> str:
        """Get embedding model name."""
        return self.embedding.get("model", "all-MiniLM-L6-v2")
    
    def get_chunk_size(self) -> int:
        """Get text chunk size."""
        return self.embedding.get("chunk_size", 500)
    
    def get_chunk_overlap(self) -> int:
        """Get text chunk overlap."""
        return self.embedding.get("chunk_overlap", 50)
    
    def get_database_path(self) -> Path:
        """Get database path."""
        db_path = self.database.get("path", ".socrates/db")
        return Path(db_path).expanduser()
    
    def is_auto_move_enabled(self) -> bool:
        """Check if auto-move is enabled for janitor."""
        return self.janitor.get("auto_move_enabled", False)
    
    def requires_confirmation(self) -> bool:
        """Check if janitor requires confirmation."""
        return self.janitor.get("require_confirmation", True)


def get_config() -> Config:
    """Get the singleton Config instance."""
    return Config()
