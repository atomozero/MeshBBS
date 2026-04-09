"""
Plugin manager for MeshBBS.

MIT License - Copyright (c) 2026 MeshBBS Contributors
"""

import importlib
import importlib.util
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Type, Any

from .base import BasePlugin, PluginInfo, PluginState
from ..commands.base import CommandRegistry


logger = logging.getLogger(__name__)


class PluginManager:
    """
    Manages loading, enabling, and lifecycle of plugins.

    Plugins are loaded from Python modules in the plugins directory.
    Each plugin module must contain a class that inherits from BasePlugin.
    """

    def __init__(
        self,
        plugins_dir: Optional[str] = None,
        config_file: Optional[str] = None,
    ):
        """
        Initialize the plugin manager.

        Args:
            plugins_dir: Directory containing plugin modules
            config_file: Path to plugins configuration file
        """
        self._plugins: Dict[str, BasePlugin] = {}
        self._plugins_dir = Path(plugins_dir) if plugins_dir else None
        self._config_file = Path(config_file) if config_file else None
        self._config: Dict[str, Any] = {}

        # Load configuration
        if self._config_file and self._config_file.exists():
            self._load_config()

        logger.info(f"PluginManager initialized (dir={plugins_dir})")

    def _load_config(self) -> None:
        """Load plugin configuration from file."""
        try:
            with open(self._config_file, "r") as f:
                self._config = json.load(f)
            logger.debug(f"Loaded plugin config from {self._config_file}")
        except Exception as e:
            logger.error(f"Failed to load plugin config: {e}")
            self._config = {}

    def _save_config(self) -> None:
        """Save plugin configuration to file."""
        if not self._config_file:
            return

        try:
            self._config_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self._config_file, "w") as f:
                json.dump(self._config, f, indent=2)
            logger.debug(f"Saved plugin config to {self._config_file}")
        except Exception as e:
            logger.error(f"Failed to save plugin config: {e}")

    def discover_plugins(self) -> List[str]:
        """
        Discover available plugins in the plugins directory.

        Returns:
            List of plugin module names
        """
        if not self._plugins_dir or not self._plugins_dir.exists():
            return []

        plugins = []
        for item in self._plugins_dir.iterdir():
            # Check for Python files
            if item.suffix == ".py" and not item.name.startswith("_"):
                plugins.append(item.stem)
            # Check for packages
            elif item.is_dir() and (item / "__init__.py").exists():
                plugins.append(item.name)

        logger.debug(f"Discovered plugins: {plugins}")
        return plugins

    async def load_plugin(self, name: str) -> bool:
        """
        Load a plugin by name.

        Args:
            name: Plugin module name

        Returns:
            True if loaded successfully
        """
        if name in self._plugins:
            logger.warning(f"Plugin {name} already loaded")
            return True

        if not self._plugins_dir:
            logger.error("Plugins directory not configured")
            return False

        try:
            # Construct module path
            module_path = self._plugins_dir / f"{name}.py"
            package_path = self._plugins_dir / name / "__init__.py"

            if module_path.exists():
                spec = importlib.util.spec_from_file_location(
                    f"meshbbs_plugins.{name}",
                    module_path
                )
            elif package_path.exists():
                spec = importlib.util.spec_from_file_location(
                    f"meshbbs_plugins.{name}",
                    package_path,
                    submodule_search_locations=[str(self._plugins_dir / name)]
                )
            else:
                logger.error(f"Plugin {name} not found")
                return False

            if not spec or not spec.loader:
                logger.error(f"Failed to load spec for {name}")
                return False

            module = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = module
            spec.loader.exec_module(module)

            # Find BasePlugin subclass
            plugin_class = None
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (
                    isinstance(attr, type)
                    and issubclass(attr, BasePlugin)
                    and attr is not BasePlugin
                ):
                    plugin_class = attr
                    break

            if not plugin_class:
                logger.error(f"No BasePlugin subclass found in {name}")
                return False

            # Instantiate plugin
            plugin = plugin_class()
            plugin._state = PluginState.LOADING

            # Load configuration if available
            if name in self._config.get("plugins", {}):
                plugin.set_config(self._config["plugins"][name])

            # Call on_load
            success = await plugin.on_load()
            if not success:
                plugin._state = PluginState.ERROR
                plugin._error = "on_load returned False"
                logger.error(f"Plugin {name} failed to load")
                return False

            # Register commands
            for command_class in plugin.get_commands():
                CommandRegistry.register(command_class)
                logger.debug(f"Registered command /{command_class.name} from {name}")

            plugin._state = PluginState.LOADED
            plugin._loaded_at = datetime.utcnow()
            self._plugins[name] = plugin

            logger.info(f"Loaded plugin: {plugin.info.name} v{plugin.info.version}")
            return True

        except Exception as e:
            logger.exception(f"Error loading plugin {name}: {e}")
            return False

    async def unload_plugin(self, name: str) -> bool:
        """
        Unload a plugin.

        Args:
            name: Plugin name

        Returns:
            True if unloaded successfully
        """
        if name not in self._plugins:
            logger.warning(f"Plugin {name} not loaded")
            return False

        plugin = self._plugins[name]

        try:
            # Disable first if enabled
            if plugin.state == PluginState.ENABLED:
                await self.disable_plugin(name)

            # Call on_unload
            await plugin.on_unload()

            # Unregister commands
            for command_class in plugin.get_commands():
                # CommandRegistry doesn't have unregister, but we can note this limitation
                logger.debug(f"Plugin commands remain registered until restart")

            plugin._state = PluginState.UNLOADED
            del self._plugins[name]

            logger.info(f"Unloaded plugin: {name}")
            return True

        except Exception as e:
            logger.exception(f"Error unloading plugin {name}: {e}")
            plugin._state = PluginState.ERROR
            plugin._error = str(e)
            return False

    async def enable_plugin(self, name: str) -> bool:
        """
        Enable a plugin.

        Args:
            name: Plugin name

        Returns:
            True if enabled successfully
        """
        if name not in self._plugins:
            logger.warning(f"Plugin {name} not loaded")
            return False

        plugin = self._plugins[name]

        if plugin.state == PluginState.ENABLED:
            return True

        if plugin.state not in (PluginState.LOADED, PluginState.DISABLED):
            logger.warning(f"Cannot enable plugin {name} in state {plugin.state}")
            return False

        try:
            success = await plugin.on_enable()
            if not success:
                plugin._error = "on_enable returned False"
                logger.error(f"Plugin {name} failed to enable")
                return False

            plugin._state = PluginState.ENABLED

            # Save enabled state
            if "enabled" not in self._config:
                self._config["enabled"] = []
            if name not in self._config["enabled"]:
                self._config["enabled"].append(name)
            self._save_config()

            logger.info(f"Enabled plugin: {name}")
            return True

        except Exception as e:
            logger.exception(f"Error enabling plugin {name}: {e}")
            plugin._state = PluginState.ERROR
            plugin._error = str(e)
            return False

    async def disable_plugin(self, name: str) -> bool:
        """
        Disable a plugin.

        Args:
            name: Plugin name

        Returns:
            True if disabled successfully
        """
        if name not in self._plugins:
            logger.warning(f"Plugin {name} not loaded")
            return False

        plugin = self._plugins[name]

        if plugin.state != PluginState.ENABLED:
            return True

        try:
            await plugin.on_disable()
            plugin._state = PluginState.DISABLED

            # Save disabled state
            if "enabled" in self._config and name in self._config["enabled"]:
                self._config["enabled"].remove(name)
            self._save_config()

            logger.info(f"Disabled plugin: {name}")
            return True

        except Exception as e:
            logger.exception(f"Error disabling plugin {name}: {e}")
            plugin._state = PluginState.ERROR
            plugin._error = str(e)
            return False

    async def reload_plugin(self, name: str) -> bool:
        """
        Reload a plugin.

        Args:
            name: Plugin name

        Returns:
            True if reloaded successfully
        """
        was_enabled = name in self._plugins and self._plugins[name].state == PluginState.ENABLED

        if name in self._plugins:
            await self.unload_plugin(name)

        success = await self.load_plugin(name)
        if success and was_enabled:
            await self.enable_plugin(name)

        return success

    async def load_all(self) -> Dict[str, bool]:
        """
        Load all discovered plugins.

        Returns:
            Dictionary of plugin name -> load success
        """
        results = {}
        for name in self.discover_plugins():
            results[name] = await self.load_plugin(name)
        return results

    async def enable_configured(self) -> None:
        """Enable all plugins marked as enabled in configuration."""
        enabled = self._config.get("enabled", [])
        for name in enabled:
            if name in self._plugins:
                await self.enable_plugin(name)

    def get_plugin(self, name: str) -> Optional[BasePlugin]:
        """
        Get a plugin by name.

        Args:
            name: Plugin name

        Returns:
            Plugin instance or None
        """
        return self._plugins.get(name)

    def get_all_plugins(self) -> List[BasePlugin]:
        """Get all loaded plugins."""
        return list(self._plugins.values())

    def get_enabled_plugins(self) -> List[BasePlugin]:
        """Get all enabled plugins."""
        return [p for p in self._plugins.values() if p.state == PluginState.ENABLED]

    async def dispatch_hook(
        self,
        hook_name: str,
        *args,
        **kwargs
    ) -> List[Any]:
        """
        Dispatch a hook to all enabled plugins.

        Args:
            hook_name: Name of the hook method (e.g., 'on_message')
            *args: Positional arguments for the hook
            **kwargs: Keyword arguments for the hook

        Returns:
            List of non-None return values from plugins
        """
        results = []
        for plugin in self.get_enabled_plugins():
            hook = getattr(plugin, hook_name, None)
            if hook and callable(hook):
                try:
                    result = await hook(*args, **kwargs)
                    if result is not None:
                        results.append(result)
                except Exception as e:
                    logger.error(f"Error in {plugin.info.name}.{hook_name}: {e}")
        return results

    def get_status(self) -> Dict[str, Any]:
        """
        Get status of all plugins.

        Returns:
            Dictionary with plugin status information
        """
        return {
            "plugins_dir": str(self._plugins_dir) if self._plugins_dir else None,
            "discovered": self.discover_plugins(),
            "loaded": {
                name: plugin.get_status()
                for name, plugin in self._plugins.items()
            },
            "enabled_count": len(self.get_enabled_plugins()),
        }

    def set_plugin_config(self, name: str, config: Dict[str, Any]) -> bool:
        """
        Set configuration for a plugin.

        Args:
            name: Plugin name
            config: Configuration dictionary

        Returns:
            True if saved successfully
        """
        if "plugins" not in self._config:
            self._config["plugins"] = {}
        self._config["plugins"][name] = config
        self._save_config()

        # Apply to loaded plugin
        if name in self._plugins:
            self._plugins[name].set_config(config)

        return True
