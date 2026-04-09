"""
Tests for MeshBBS unified launcher.

MIT License - Copyright (c) 2026 MeshBBS Contributors
"""

import pytest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock

from launcher import get_bbs_instance, parse_args, run_all


class TestLauncherConfig:
    """Tests for launcher configuration and argument parsing."""

    def test_default_args(self):
        """Verify default argument values."""
        with patch("sys.argv", ["launcher.py"]):
            args = parse_args()

        assert args.port == "/dev/ttyUSB0"
        assert args.baud == 115200
        assert args.database == "data/bbs.db"
        assert args.name == "MeshCore BBS"
        assert args.web_host == "0.0.0.0"
        assert args.web_port == 8080
        assert args.debug is False
        assert args.web_only is False
        assert args.bbs_only is False

    def test_custom_args(self):
        """Verify custom arguments are parsed correctly."""
        with patch("sys.argv", [
            "launcher.py",
            "-p", "/dev/ttyACM0",
            "-b", "9600",
            "-n", "Test BBS",
            "--web-port", "9090",
            "--debug",
        ]):
            args = parse_args()

        assert args.port == "/dev/ttyACM0"
        assert args.baud == 9600
        assert args.name == "Test BBS"
        assert args.web_port == 9090
        assert args.debug is True

    def test_web_only_flag(self):
        """Verify --web-only flag."""
        with patch("sys.argv", ["launcher.py", "--web-only"]):
            args = parse_args()

        assert args.web_only is True
        assert args.bbs_only is False

    def test_bbs_only_flag(self):
        """Verify --bbs-only flag."""
        with patch("sys.argv", ["launcher.py", "--bbs-only"]):
            args = parse_args()

        assert args.bbs_only is False or args.bbs_only is True
        # Verify it's set
        assert args.bbs_only is True


class TestBBSInstance:
    """Tests for global BBS instance management."""

    def test_initial_instance_is_none(self):
        """Verify no BBS instance exists initially."""
        from bbs.runtime import set_bbs_instance
        set_bbs_instance(None)

        assert get_bbs_instance() is None

    def test_get_bbs_instance_returns_set_value(self):
        """Verify get_bbs_instance returns the global instance."""
        from bbs.runtime import set_bbs_instance

        mock_bbs = MagicMock()
        set_bbs_instance(mock_bbs)

        assert get_bbs_instance() is mock_bbs

        # Cleanup
        set_bbs_instance(None)


class TestRunAll:
    """Tests for the run_all orchestrator."""

    @pytest.mark.asyncio
    async def test_run_all_both_modes(self, config):
        """Verify both BBS and web tasks are created in default mode."""
        with patch("sys.argv", ["launcher.py"]):
            args = parse_args()

        tasks_created = []

        async def mock_run_bbs(cfg):
            tasks_created.append("bbs")
            await asyncio.sleep(0.1)

        async def mock_run_web(host, port, debug):
            tasks_created.append("web")
            await asyncio.sleep(0.1)

        with patch("launcher.run_bbs", side_effect=mock_run_bbs), \
             patch("launcher.run_web_server", side_effect=mock_run_web), \
             patch("launcher.logger", MagicMock()):
            await run_all(args, config)

        assert "bbs" in tasks_created
        assert "web" in tasks_created

    @pytest.mark.asyncio
    async def test_run_all_web_only(self, config):
        """Verify only web task is created with --web-only."""
        with patch("sys.argv", ["launcher.py", "--web-only"]):
            args = parse_args()

        tasks_created = []

        async def mock_run_web(host, port, debug):
            tasks_created.append("web")
            await asyncio.sleep(0.1)

        with patch("launcher.run_web_server", side_effect=mock_run_web), \
             patch("launcher.logger", MagicMock()):
            await run_all(args, config)

        assert "web" in tasks_created
        assert "bbs" not in tasks_created

    @pytest.mark.asyncio
    async def test_run_all_bbs_only(self, config):
        """Verify only BBS task is created with --bbs-only."""
        with patch("sys.argv", ["launcher.py", "--bbs-only"]):
            args = parse_args()

        tasks_created = []

        async def mock_run_bbs(cfg):
            tasks_created.append("bbs")
            await asyncio.sleep(0.1)

        with patch("launcher.run_bbs", side_effect=mock_run_bbs), \
             patch("launcher.logger", MagicMock()):
            await run_all(args, config)

        assert "bbs" in tasks_created
        assert "web" not in tasks_created
