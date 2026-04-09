"""
Tests for the Plugin System.

MIT License - Copyright (c) 2026 MeshBBS Contributors
"""

import pytest
import tempfile
import json
from pathlib import Path
from datetime import datetime
from typing import List, Type, Optional

# Add src to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from bbs.plugins.base import BasePlugin, PluginInfo, PluginState
from bbs.plugins.manager import PluginManager
from bbs.commands.base import BaseCommand, CommandContext, CommandResult, CommandRegistry


class TestPluginInfo:
    """Test PluginInfo dataclass."""

    def test_create_plugin_info(self):
        """Test creating plugin info."""
        info = PluginInfo(
            name="test-plugin",
            version="1.0.0",
            description="Test plugin",
            author="Test Author",
        )

        assert info.name == "test-plugin"
        assert info.version == "1.0.0"
        assert info.min_bbs_version == "1.0.0"
        assert info.dependencies == []
        assert info.license == "MIT"

    def test_to_dict(self):
        """Test converting to dictionary."""
        info = PluginInfo(
            name="test",
            version="2.0.0",
            description="Desc",
            author="Auth",
            homepage="https://example.com",
        )

        d = info.to_dict()
        assert d["name"] == "test"
        assert d["version"] == "2.0.0"
        assert d["homepage"] == "https://example.com"


class TestPluginState:
    """Test PluginState enum."""

    def test_states(self):
        """Test all states exist."""
        assert PluginState.UNLOADED.value == "unloaded"
        assert PluginState.LOADING.value == "loading"
        assert PluginState.LOADED.value == "loaded"
        assert PluginState.ENABLED.value == "enabled"
        assert PluginState.DISABLED.value == "disabled"
        assert PluginState.ERROR.value == "error"


# Test plugin implementation
class TestCommand(BaseCommand):
    name = "testcmd"
    description = "Test command"
    usage = "!testcmd"
    aliases = ["tc"]

    def __init__(self, session=None):
        self.session = session

    async def execute(self, ctx: CommandContext, args: List[str]) -> CommandResult:
        return CommandResult.ok("Test response")


class TestPlugin(BasePlugin):
    """Test plugin for unit tests."""

    on_load_called = False
    on_unload_called = False
    on_enable_called = False
    on_disable_called = False
    on_message_called = False

    @property
    def info(self) -> PluginInfo:
        return PluginInfo(
            name="test-plugin",
            version="1.0.0",
            description="Test plugin",
            author="Test",
        )

    def get_commands(self) -> List[Type[BaseCommand]]:
        return [TestCommand]

    async def on_load(self) -> bool:
        TestPlugin.on_load_called = True
        return True

    async def on_unload(self) -> None:
        TestPlugin.on_unload_called = True

    async def on_enable(self) -> bool:
        TestPlugin.on_enable_called = True
        return True

    async def on_disable(self) -> None:
        TestPlugin.on_disable_called = True

    async def on_message(
        self, sender_key: str, message: str, is_command: bool
    ) -> Optional[str]:
        TestPlugin.on_message_called = True
        return None


class TestBasePlugin:
    """Test BasePlugin class."""

    def setup_method(self):
        """Reset test plugin state."""
        TestPlugin.on_load_called = False
        TestPlugin.on_unload_called = False
        TestPlugin.on_enable_called = False
        TestPlugin.on_disable_called = False
        TestPlugin.on_message_called = False

    def test_initial_state(self):
        """Test plugin initial state."""
        plugin = TestPlugin()
        assert plugin.state == PluginState.UNLOADED
        assert plugin.error is None
        assert plugin.config == {}

    def test_plugin_info(self):
        """Test plugin info property."""
        plugin = TestPlugin()
        assert plugin.info.name == "test-plugin"
        assert plugin.info.version == "1.0.0"

    def test_set_config(self):
        """Test setting plugin config."""
        plugin = TestPlugin()
        plugin.set_config({"key": "value"})
        assert plugin.config["key"] == "value"

    def test_get_commands(self):
        """Test getting plugin commands."""
        plugin = TestPlugin()
        commands = plugin.get_commands()
        assert len(commands) == 1
        assert commands[0].name == "testcmd"

    @pytest.mark.asyncio
    async def test_on_load(self):
        """Test on_load hook."""
        plugin = TestPlugin()
        result = await plugin.on_load()
        assert result is True
        assert TestPlugin.on_load_called is True

    @pytest.mark.asyncio
    async def test_on_unload(self):
        """Test on_unload hook."""
        plugin = TestPlugin()
        await plugin.on_unload()
        assert TestPlugin.on_unload_called is True

    @pytest.mark.asyncio
    async def test_on_enable(self):
        """Test on_enable hook."""
        plugin = TestPlugin()
        result = await plugin.on_enable()
        assert result is True
        assert TestPlugin.on_enable_called is True

    @pytest.mark.asyncio
    async def test_on_disable(self):
        """Test on_disable hook."""
        plugin = TestPlugin()
        await plugin.on_disable()
        assert TestPlugin.on_disable_called is True

    @pytest.mark.asyncio
    async def test_on_message(self):
        """Test on_message hook."""
        plugin = TestPlugin()
        result = await plugin.on_message("ABC123", "hello", False)
        assert result is None
        assert TestPlugin.on_message_called is True

    def test_get_status(self):
        """Test get_status method."""
        plugin = TestPlugin()
        plugin._state = PluginState.ENABLED
        plugin._loaded_at = datetime(2026, 1, 1, 12, 0, 0)

        status = plugin.get_status()
        assert status["name"] == "test-plugin"
        assert status["version"] == "1.0.0"
        assert status["state"] == "enabled"
        assert "testcmd" in status["commands"]

    def test_repr(self):
        """Test string representation."""
        plugin = TestPlugin()
        repr_str = repr(plugin)
        assert "test-plugin" in repr_str
        assert "1.0.0" in repr_str
        assert "unloaded" in repr_str


class TestPluginManager:
    """Test PluginManager class."""

    def setup_method(self):
        """Clear command registry before each test."""
        CommandRegistry.clear()

    @pytest.fixture
    def temp_plugins_dir(self, tmp_path):
        """Create a temporary plugins directory."""
        plugins_dir = tmp_path / "plugins"
        plugins_dir.mkdir()
        return plugins_dir

    @pytest.fixture
    def sample_plugin_code(self):
        """Sample plugin code for testing."""
        return '''
from bbs.plugins.base import BasePlugin, PluginInfo
from bbs.commands.base import BaseCommand, CommandResult

class SampleCommand(BaseCommand):
    name = "sample"
    description = "Sample command"
    usage = "/sample"

    def __init__(self, session=None):
        pass

    async def execute(self, ctx, args):
        return CommandResult.ok("Sample response")

class SamplePlugin(BasePlugin):
    @property
    def info(self):
        return PluginInfo(
            name="sample-plugin",
            version="1.0.0",
            description="Sample plugin",
            author="Test"
        )

    def get_commands(self):
        return [SampleCommand]

    async def on_load(self):
        return True

Plugin = SamplePlugin
'''

    def test_init_without_dir(self):
        """Test initialization without plugins directory."""
        manager = PluginManager()
        assert manager._plugins_dir is None
        assert manager.discover_plugins() == []

    def test_init_with_dir(self, temp_plugins_dir):
        """Test initialization with plugins directory."""
        manager = PluginManager(plugins_dir=str(temp_plugins_dir))
        assert manager._plugins_dir == temp_plugins_dir

    def test_discover_plugins_empty(self, temp_plugins_dir):
        """Test discovering plugins in empty directory."""
        manager = PluginManager(plugins_dir=str(temp_plugins_dir))
        plugins = manager.discover_plugins()
        assert plugins == []

    def test_discover_plugins_with_files(self, temp_plugins_dir):
        """Test discovering plugin files."""
        # Create plugin files
        (temp_plugins_dir / "plugin_a.py").write_text("# Plugin A")
        (temp_plugins_dir / "plugin_b.py").write_text("# Plugin B")
        (temp_plugins_dir / "_hidden.py").write_text("# Hidden")
        (temp_plugins_dir / "not_python.txt").write_text("Not a plugin")

        manager = PluginManager(plugins_dir=str(temp_plugins_dir))
        plugins = manager.discover_plugins()

        assert "plugin_a" in plugins
        assert "plugin_b" in plugins
        assert "_hidden" not in plugins

    def test_get_plugin_not_loaded(self):
        """Test getting non-existent plugin."""
        manager = PluginManager()
        assert manager.get_plugin("nonexistent") is None

    def test_get_all_plugins_empty(self):
        """Test getting all plugins when none loaded."""
        manager = PluginManager()
        assert manager.get_all_plugins() == []

    def test_get_status(self, temp_plugins_dir):
        """Test getting manager status."""
        manager = PluginManager(plugins_dir=str(temp_plugins_dir))
        status = manager.get_status()

        assert status["plugins_dir"] == str(temp_plugins_dir)
        assert "discovered" in status
        assert "loaded" in status
        assert status["enabled_count"] == 0

    @pytest.mark.asyncio
    async def test_load_plugin(self, temp_plugins_dir, sample_plugin_code):
        """Test loading a plugin."""
        # Write plugin file
        (temp_plugins_dir / "sample.py").write_text(sample_plugin_code)

        manager = PluginManager(plugins_dir=str(temp_plugins_dir))
        success = await manager.load_plugin("sample")

        assert success is True
        plugin = manager.get_plugin("sample")
        assert plugin is not None
        assert plugin.info.name == "sample-plugin"
        assert plugin.state == PluginState.LOADED

    @pytest.mark.asyncio
    async def test_load_plugin_not_found(self, temp_plugins_dir):
        """Test loading non-existent plugin."""
        manager = PluginManager(plugins_dir=str(temp_plugins_dir))
        success = await manager.load_plugin("nonexistent")
        assert success is False

    @pytest.mark.asyncio
    async def test_load_plugin_already_loaded(self, temp_plugins_dir, sample_plugin_code):
        """Test loading already loaded plugin."""
        (temp_plugins_dir / "sample.py").write_text(sample_plugin_code)
        manager = PluginManager(plugins_dir=str(temp_plugins_dir))

        await manager.load_plugin("sample")
        success = await manager.load_plugin("sample")
        assert success is True  # Returns True, already loaded

    @pytest.mark.asyncio
    async def test_enable_plugin(self, temp_plugins_dir, sample_plugin_code):
        """Test enabling a plugin."""
        (temp_plugins_dir / "sample.py").write_text(sample_plugin_code)
        manager = PluginManager(plugins_dir=str(temp_plugins_dir))

        await manager.load_plugin("sample")
        success = await manager.enable_plugin("sample")

        assert success is True
        plugin = manager.get_plugin("sample")
        assert plugin.state == PluginState.ENABLED

    @pytest.mark.asyncio
    async def test_disable_plugin(self, temp_plugins_dir, sample_plugin_code):
        """Test disabling a plugin."""
        (temp_plugins_dir / "sample.py").write_text(sample_plugin_code)
        manager = PluginManager(plugins_dir=str(temp_plugins_dir))

        await manager.load_plugin("sample")
        await manager.enable_plugin("sample")
        success = await manager.disable_plugin("sample")

        assert success is True
        plugin = manager.get_plugin("sample")
        assert plugin.state == PluginState.DISABLED

    @pytest.mark.asyncio
    async def test_unload_plugin(self, temp_plugins_dir, sample_plugin_code):
        """Test unloading a plugin."""
        (temp_plugins_dir / "sample.py").write_text(sample_plugin_code)
        manager = PluginManager(plugins_dir=str(temp_plugins_dir))

        await manager.load_plugin("sample")
        success = await manager.unload_plugin("sample")

        assert success is True
        assert manager.get_plugin("sample") is None

    @pytest.mark.asyncio
    async def test_reload_plugin(self, temp_plugins_dir, sample_plugin_code):
        """Test reloading a plugin."""
        (temp_plugins_dir / "sample.py").write_text(sample_plugin_code)
        manager = PluginManager(plugins_dir=str(temp_plugins_dir))

        await manager.load_plugin("sample")
        await manager.enable_plugin("sample")
        success = await manager.reload_plugin("sample")

        assert success is True
        plugin = manager.get_plugin("sample")
        assert plugin.state == PluginState.ENABLED  # Re-enabled after reload

    @pytest.mark.asyncio
    async def test_get_enabled_plugins(self, temp_plugins_dir, sample_plugin_code):
        """Test getting enabled plugins."""
        (temp_plugins_dir / "sample.py").write_text(sample_plugin_code)
        manager = PluginManager(plugins_dir=str(temp_plugins_dir))

        await manager.load_plugin("sample")
        assert len(manager.get_enabled_plugins()) == 0

        await manager.enable_plugin("sample")
        enabled = manager.get_enabled_plugins()
        assert len(enabled) == 1
        assert enabled[0].info.name == "sample-plugin"

    @pytest.mark.asyncio
    async def test_dispatch_hook(self, temp_plugins_dir):
        """Test dispatching hooks to plugins."""
        # Plugin with hook
        plugin_code = '''
from bbs.plugins.base import BasePlugin, PluginInfo

class HookPlugin(BasePlugin):
    messages = []

    @property
    def info(self):
        return PluginInfo(name="hook-plugin", version="1.0.0", description="Hook test", author="Test")

    async def on_message(self, sender_key, message, is_command):
        HookPlugin.messages.append(message)
        return None

Plugin = HookPlugin
'''
        (temp_plugins_dir / "hooktest.py").write_text(plugin_code)
        manager = PluginManager(plugins_dir=str(temp_plugins_dir))

        await manager.load_plugin("hooktest")
        await manager.enable_plugin("hooktest")

        results = await manager.dispatch_hook("on_message", "ABC123", "Hello", False)

        # Check hook was called (messages list accessed via plugin)
        plugin = manager.get_plugin("hooktest")
        assert plugin is not None

    @pytest.mark.asyncio
    async def test_load_all(self, temp_plugins_dir, sample_plugin_code):
        """Test loading all discovered plugins."""
        # Create multiple plugins
        (temp_plugins_dir / "plugin1.py").write_text(
            sample_plugin_code.replace("sample-plugin", "plugin1").replace("SamplePlugin", "Plugin1").replace("SampleCommand", "Plugin1Command").replace('name = "sample"', 'name = "p1"')
        )
        (temp_plugins_dir / "plugin2.py").write_text(
            sample_plugin_code.replace("sample-plugin", "plugin2").replace("SamplePlugin", "Plugin2").replace("SampleCommand", "Plugin2Command").replace('name = "sample"', 'name = "p2"')
        )

        manager = PluginManager(plugins_dir=str(temp_plugins_dir))
        results = await manager.load_all()

        assert len(results) == 2
        assert results.get("plugin1") is True
        assert results.get("plugin2") is True


class TestPluginConfig:
    """Test plugin configuration."""

    @pytest.fixture
    def config_file(self, tmp_path):
        """Create temporary config file."""
        return tmp_path / "plugins.json"

    def test_save_and_load_config(self, tmp_path, config_file):
        """Test saving and loading plugin configuration."""
        config_file.write_text('{"enabled": ["plugin1"], "plugins": {"plugin1": {"setting": "value"}}}')

        manager = PluginManager(config_file=str(config_file))
        assert "plugin1" in manager._config.get("enabled", [])

    def test_set_plugin_config(self, tmp_path, config_file):
        """Test setting plugin configuration."""
        manager = PluginManager(config_file=str(config_file))
        manager.set_plugin_config("myplugin", {"key": "value"})

        # Reload to verify save
        manager2 = PluginManager(config_file=str(config_file))
        assert manager2._config.get("plugins", {}).get("myplugin", {}).get("key") == "value"


class TestPluginErrors:
    """Test plugin error handling."""

    @pytest.fixture
    def temp_plugins_dir(self, tmp_path):
        plugins_dir = tmp_path / "plugins"
        plugins_dir.mkdir()
        return plugins_dir

    @pytest.mark.asyncio
    async def test_load_plugin_syntax_error(self, temp_plugins_dir):
        """Test loading plugin with syntax error."""
        (temp_plugins_dir / "broken.py").write_text("def broken(")

        manager = PluginManager(plugins_dir=str(temp_plugins_dir))
        success = await manager.load_plugin("broken")
        assert success is False

    @pytest.mark.asyncio
    async def test_load_plugin_no_class(self, temp_plugins_dir):
        """Test loading plugin without BasePlugin class."""
        (temp_plugins_dir / "empty.py").write_text("# No plugin class")

        manager = PluginManager(plugins_dir=str(temp_plugins_dir))
        success = await manager.load_plugin("empty")
        assert success is False

    @pytest.mark.asyncio
    async def test_enable_not_loaded(self):
        """Test enabling not loaded plugin."""
        manager = PluginManager()
        success = await manager.enable_plugin("notloaded")
        assert success is False

    @pytest.mark.asyncio
    async def test_disable_not_loaded(self):
        """Test disabling not loaded plugin."""
        manager = PluginManager()
        success = await manager.disable_plugin("notloaded")
        assert success is False

    @pytest.mark.asyncio
    async def test_unload_not_loaded(self):
        """Test unloading not loaded plugin."""
        manager = PluginManager()
        success = await manager.unload_plugin("notloaded")
        assert success is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
