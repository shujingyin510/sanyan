import json
import os
from typing import Any, Dict, Optional


class ConfigLoader:
    """A simple configuration loader that supports JSON and YAML files."""

    def __init__(self, config_path: Optional[str] = None) -> None:
        """
        Initialize the ConfigLoader with an optional path to a configuration file.
        If a path is provided, the configuration is automatically loaded.
        """
        self.config: Dict[str, Any] = {}
        self.config_path: Optional[str] = config_path
        if config_path:
            self.load(config_path)

    def load(self, path: str) -> None:
        """
        Load configuration from a file.
        Supports .json and .yaml/.yml extensions. 
        If the file is YAML, PyYAML must be installed.
        """
        if not os.path.exists(path):
            raise FileNotFoundError(f"Configuration file not found: {path}")
        _, ext = os.path.splitext(path)
        ext = ext.lower()

        with open(path, 'r', encoding='utf-8') as f:
            if ext == '.json':
                self.config = json.load(f)
            elif ext in ('.yaml', '.yml'):
                try:
                    import yaml
                except ImportError:
                    raise ImportError("PyYAML is required to load YAML files. Install it with 'pip install pyyaml'")
                self.config = yaml.safe_load(f)
            else:
                raise ValueError(f"Unsupported configuration file format: {ext}")
        self.config_path = path

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a configuration value by key. Supports dot‑notation for nested keys.
        Example: "database.host"
        """
        keys = key.split('.')
        value = self.config
        try:
            for k in keys:
                value = value[k]
            return value
        except (KeyError, TypeError):
            return default

    def set(self, key: str, value: Any) -> None:
        """Set a configuration value using dot‑notation."""
        keys = key.split('.')
        config = self.config
        for k in keys[:-1]:
            if k not in config or not isinstance(config[k], dict):
                config[k] = {}
            config = config[k]
        config[keys[-1]] = value

    def save(self, path: Optional[str] = None) -> None:
        """
        Save the current configuration to a file.
        The format is inferred from the file extension.
        """
        if path is None:
            if self.config_path is None:
                raise ValueError("No path specified and no previous path set.")
            path = self.config_path

        _, ext = os.path.splitext(path)
        ext = ext.lower()
        with open(path, 'w', encoding='utf-8') as f:
            if ext == '.json':
                json.dump(self.config, f, indent=4, ensure_ascii=False)
            elif ext in ('.yaml', '.yml'):
                try:
                    import yaml
                except ImportError:
                    raise ImportError("PyYAML is required to save YAML files.")
                yaml.safe_dump(self.config, f, default_flow_style=False)
            else:
                raise ValueError(f"Unsupported file format: {ext}")

    def reload(self) -> None:
        """Reload the configuration from the original file path."""
        if self.config_path is None:
            raise ValueError("No configuration path set to reload from.")
        self.load(self.config_path)

    def to_dict(self) -> Dict[str, Any]:
        """Return the configuration as a dictionary."""
        return self.config.copy()


if __name__ == "__main__":
    # Example usage
    loader = ConfigLoader()
    # Create a sample config dict for demonstration
    sample_config = {
        "app": {
            "name": "MyApp",
            "version": "1.0",
            "debug": True
        },
        "database": {
            "host": "localhost",
            "port": 5432,
            "credentials": {
                "user": "admin",
                "password": "secret"
            }
        }
    }
    loader.config = sample_config
    loader.config_path = "config.json"

    print("Host:", loader.get("database.host"))
    print("Debug:", loader.get("app.debug"))
    print("Missing:", loader.get("missing.key", "default_value"))

    # Uncomment to save to file
    # loader.save("config.json")