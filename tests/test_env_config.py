"""
Tests for configuration precedence: CLI > BBS_* env > legacy env >
settings.json > defaults.

MIT License - Copyright (c) 2026 MeshBBS Contributors
"""

import json
import os

import pytest

from launcher import build_config, parse_args
from utils.config import ENV_VARS, Config


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for names in ENV_VARS.values():
        for name in names:
            monkeypatch.delenv(name, raising=False)
    yield


def _write_settings(db_path, data):
    path = os.path.join(os.path.dirname(db_path), "settings.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f)
    return path


class TestEnvPrecedence:
    def test_defaults(self, tmp_path, monkeypatch):
        monkeypatch.setenv("BBS_DATABASE_PATH", str(tmp_path / "bbs.db"))
        config = Config.from_env()
        assert config.bbs_name == "MeshCore BBS"
        assert config.log_level == "INFO"
        assert config.config_file_path == str(tmp_path / "settings.json")

    def test_legacy_names_accepted(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "legacy.db"))
        monkeypatch.setenv("LOG_FILE", str(tmp_path / "legacy.log"))
        monkeypatch.setenv("LOG_LEVEL", "WARNING")
        monkeypatch.setenv("SERIAL_PORT", "/dev/ttyACM0")
        monkeypatch.setenv("BAUD_RATE", "9600")
        config = Config.from_env()
        assert config.database_path == str(tmp_path / "legacy.db")
        assert config.log_path == str(tmp_path / "legacy.log")
        assert config.log_level == "WARNING"
        assert config.serial_port == "/dev/ttyACM0"
        assert config.baud_rate == 9600

    def test_canonical_beats_legacy(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "legacy.db"))
        monkeypatch.setenv("BBS_DATABASE_PATH", str(tmp_path / "new.db"))
        monkeypatch.setenv("LOG_LEVEL", "WARNING")
        monkeypatch.setenv("BBS_LOG_LEVEL", "ERROR")
        config = Config.from_env()
        assert config.database_path == str(tmp_path / "new.db")
        assert config.log_level == "ERROR"

    def test_empty_canonical_falls_back_to_legacy(self, tmp_path, monkeypatch):
        monkeypatch.setenv("BBS_DATABASE_PATH", "")
        monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "legacy.db"))
        assert Config.from_env().database_path == str(tmp_path / "legacy.db")

    def test_overrides_beat_env(self, tmp_path, monkeypatch):
        monkeypatch.setenv("BBS_DATABASE_PATH", str(tmp_path / "env.db"))
        monkeypatch.setenv("BBS_NAME", "Env BBS")
        config = Config.from_env({
            "database_path": str(tmp_path / "cli.db"),
            "bbs_name": None,  # not given: ignored
        })
        assert config.database_path == str(tmp_path / "cli.db")
        assert config.bbs_name == "Env BBS"

    def test_invalid_value_ignored(self, tmp_path, monkeypatch):
        monkeypatch.setenv("BBS_DATABASE_PATH", str(tmp_path / "bbs.db"))
        monkeypatch.setenv("BBS_BAUD_RATE", "fast")
        assert Config.from_env().baud_rate == 115200

    def test_bool_values(self, tmp_path, monkeypatch):
        monkeypatch.setenv("BBS_DATABASE_PATH", str(tmp_path / "bbs.db"))
        monkeypatch.setenv("BBS_ALLOW_EPHEMERAL_PM", "0")
        assert Config.from_env().allow_ephemeral_pm is False
        monkeypatch.setenv("BBS_ALLOW_EPHEMERAL_PM", "yes")
        assert Config.from_env().allow_ephemeral_pm is True


class TestSettingsFile:
    def test_settings_file_beats_defaults(self, tmp_path, monkeypatch):
        db = str(tmp_path / "bbs.db")
        monkeypatch.setenv("BBS_DATABASE_PATH", db)
        _write_settings(db, {"bbs_name": "File BBS", "send_delay": 4.0, "beacon_interval": 60})
        config = Config.from_env()
        assert config.bbs_name == "File BBS"
        assert config.send_delay == 4.0
        assert config.beacon_interval == 60

    def test_env_beats_settings_file(self, tmp_path, monkeypatch):
        db = str(tmp_path / "bbs.db")
        monkeypatch.setenv("BBS_DATABASE_PATH", db)
        monkeypatch.setenv("BBS_NAME", "Env BBS")
        monkeypatch.setenv("BBS_LOG_RETENTION_DAYS", "10")
        _write_settings(db, {"bbs_name": "File BBS", "activity_log_retention_days": 99})
        config = Config.from_env()
        assert config.bbs_name == "Env BBS"
        assert config.activity_log_retention_days == 10

    def test_unread_env_var_does_not_block_file(self, tmp_path, monkeypatch):
        """BBS_SEND_DELAY is not a supported variable: settings.json wins."""
        db = str(tmp_path / "bbs.db")
        monkeypatch.setenv("BBS_DATABASE_PATH", db)
        monkeypatch.setenv("BBS_SEND_DELAY", "1")
        _write_settings(db, {"send_delay": 7.5})
        assert Config.from_env().send_delay == 7.5


class TestLauncherConfig:
    def test_no_cli_args_uses_env_and_settings(self, tmp_path, monkeypatch):
        db = str(tmp_path / "bbs.db")
        monkeypatch.setenv("DATABASE_PATH", db)
        monkeypatch.setenv("LOG_LEVEL", "WARNING")
        _write_settings(db, {"bbs_name": "Saved Name"})
        config = build_config(parse_args([]))
        assert config.database_path == db
        assert config.log_level == "WARNING"
        assert config.bbs_name == "Saved Name"
        assert config.config_file_path == str(tmp_path / "settings.json")

    def test_cli_beats_env_and_settings(self, tmp_path, monkeypatch):
        db_env = str(tmp_path / "env" / "bbs.db")
        db_cli = str(tmp_path / "cli.db")
        monkeypatch.setenv("BBS_DATABASE_PATH", db_env)
        monkeypatch.setenv("BBS_LOG_LEVEL", "WARNING")
        _write_settings(db_cli, {"bbs_name": "Saved Name"})
        config = build_config(parse_args([
            "-d", db_cli, "--log-file", str(tmp_path / "x.log"),
            "-n", "Cli Name", "--debug",
        ]))
        assert config.database_path == db_cli
        assert config.log_path == str(tmp_path / "x.log")
        assert config.bbs_name == "Cli Name"
        assert config.log_level == "DEBUG"
        assert config.config_file_path == str(tmp_path / "settings.json")

    def test_cli_default_value_does_not_override_env(self, tmp_path, monkeypatch):
        monkeypatch.setenv("BBS_DATABASE_PATH", str(tmp_path / "bbs.db"))
        monkeypatch.setenv("BBS_SERIAL_PORT", "/dev/ttyACM1")
        args = parse_args([])
        assert args.port == "/dev/ttyUSB0"  # parser default still visible
        assert "port" not in args.explicit
        assert build_config(args).serial_port == "/dev/ttyACM1"

    def test_tcp_mode(self, tmp_path, monkeypatch):
        monkeypatch.setenv("BBS_DATABASE_PATH", str(tmp_path / "bbs.db"))
        config = build_config(parse_args(["--tcp", "--tcp-host", "10.0.0.5"]))
        assert config.connection_mode == "tcp"
        assert config.tcp_host == "10.0.0.5"
        assert config.tcp_port == 5000
