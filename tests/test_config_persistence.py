"""
Tests for configuration persistence system.

MIT License - Copyright (c) 2026 MeshBBS Contributors
"""

import os
import json
import tempfile
import pytest
from pathlib import Path

# Add src to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from utils.config import Config, UPDATABLE_FIELDS, get_config, set_config, reload_config


class TestConfigPersistence:
    """Test suite for Config persistence functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        # Create a temporary directory for test config files
        self.temp_dir = tempfile.mkdtemp()
        self.config_file = os.path.join(self.temp_dir, "settings.json")
        self.db_file = os.path.join(self.temp_dir, "test.db")

    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
        # Reset global config
        set_config(None)

    def test_config_defaults(self):
        """Test that Config has sensible defaults."""
        config = Config()

        assert config.bbs_name == "MeshCore BBS"
        assert config.default_area == "generale"
        assert config.max_message_length == 200
        assert config.pm_retention_days == 30
        assert config.activity_log_retention_days == 90
        assert config.allow_ephemeral_pm is True

    def test_updatable_fields_defined(self):
        """Test that UPDATABLE_FIELDS contains expected fields."""
        expected = {
            "bbs_name",
            "default_area",
            "max_message_length",
            "pm_retention_days",
            "activity_log_retention_days",
            "allow_ephemeral_pm",
        }
        assert expected.issubset(UPDATABLE_FIELDS)

    def test_config_update_single_field(self):
        """Test updating a single config field."""
        config = Config()
        config.config_file_path = self.config_file

        updates = config.update({"bbs_name": "Test BBS"})

        assert "bbs_name" in updates
        assert config.bbs_name == "Test BBS"

    def test_config_update_multiple_fields(self):
        """Test updating multiple config fields."""
        config = Config()
        config.config_file_path = self.config_file

        updates = config.update({
            "bbs_name": "Updated BBS",
            "default_area": "test_area",
            "max_message_length": 500,
        })

        assert len(updates) == 3
        assert config.bbs_name == "Updated BBS"
        assert config.default_area == "test_area"
        assert config.max_message_length == 500

    def test_config_update_ignores_non_updatable(self):
        """Test that non-updatable fields are ignored."""
        config = Config()
        config.config_file_path = self.config_file
        original_port = config.serial_port

        updates = config.update({
            "serial_port": "/dev/ttyUSB999",  # Should be ignored
            "bbs_name": "Valid Update",
        })

        assert "serial_port" not in updates
        assert config.serial_port == original_port
        assert config.bbs_name == "Valid Update"

    def test_config_save_to_file(self):
        """Test saving config to file."""
        config = Config()
        config.config_file_path = self.config_file
        config.bbs_name = "Saved BBS"

        result = config.save_to_file()

        assert result is True
        assert os.path.exists(self.config_file)

        with open(self.config_file, "r") as f:
            data = json.load(f)
        assert data["bbs_name"] == "Saved BBS"

    def test_config_load_from_file(self):
        """Test loading config from file."""
        # Create a config file
        saved_data = {
            "bbs_name": "Loaded BBS",
            "default_area": "loaded_area",
            "max_message_length": 300,
        }
        os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
        with open(self.config_file, "w") as f:
            json.dump(saved_data, f)

        # Create config and load from file
        config = Config()
        config.config_file_path = self.config_file
        config._load_from_file()

        assert config.bbs_name == "Loaded BBS"
        assert config.default_area == "loaded_area"
        assert config.max_message_length == 300

    def test_config_update_persists(self):
        """Test that updates are persisted to file."""
        config = Config()
        config.config_file_path = self.config_file

        config.update({"bbs_name": "Persisted BBS"})

        # Verify file exists and contains updated value
        assert os.path.exists(self.config_file)
        with open(self.config_file, "r") as f:
            data = json.load(f)
        assert data["bbs_name"] == "Persisted BBS"

    def test_config_to_dict(self):
        """Test converting config to dictionary."""
        config = Config()
        config.bbs_name = "Dict Test"

        data = config.to_dict()

        assert data["bbs_name"] == "Dict Test"
        assert "serial_port" in data
        assert "database_key" not in data  # Sensitive field excluded

    def test_config_env_var_priority(self):
        """Test that environment variables have priority over file."""
        # Save a value to file first
        saved_data = {"bbs_name": "File BBS"}
        os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
        with open(self.config_file, "w") as f:
            json.dump(saved_data, f)

        # Set environment variable before creating config
        os.environ["BBS_NAME"] = "Env BBS"
        # Also set custom config path via env so from_env() finds our file
        os.environ["BBS_DATABASE_PATH"] = self.db_file

        try:
            # from_env() sets bbs_name from BBS_NAME env var
            # then _load_from_file() should NOT override it because env var is set
            config = Config.from_env()
            # Override config file path after creation but the bbs_name
            # was already set from env var in from_env()

            # The env var is applied in from_env(), so it should be "Env BBS"
            assert config.bbs_name == "Env BBS"
        finally:
            del os.environ["BBS_NAME"]
            if "BBS_DATABASE_PATH" in os.environ:
                del os.environ["BBS_DATABASE_PATH"]

    def test_config_update_no_change(self):
        """Test updating with same value returns empty dict."""
        config = Config()
        config.config_file_path = self.config_file

        # First update
        config.update({"bbs_name": "Same Name"})

        # Second update with same value
        updates = config.update({"bbs_name": "Same Name"})

        assert len(updates) == 0

    def test_config_file_only_contains_updatable(self):
        """Test that saved file only contains updatable fields."""
        config = Config()
        config.config_file_path = self.config_file

        config.update({"bbs_name": "Test"})

        with open(self.config_file, "r") as f:
            data = json.load(f)

        # Should not contain non-updatable fields
        assert "serial_port" not in data
        assert "database_path" not in data
        assert "baud_rate" not in data

        # Should contain updatable fields
        assert "bbs_name" in data


class TestConfigAPI:
    """Test config API integration."""

    def test_reload_config(self):
        """Test config reload functionality."""
        # Set initial config
        config = Config()
        config.bbs_name = "Initial"
        set_config(config)

        # Reload should get fresh config
        new_config = reload_config()

        # Should be a new instance with defaults
        assert new_config is not config
        assert new_config.bbs_name == "MeshCore BBS"  # Default


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
