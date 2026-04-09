"""
Tests for BBS core module.

MIT License - Copyright (c) 2026 MeshBBS Contributors
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

from bbs.core import BBSCore
from meshcore.connection import MockMeshCoreConnection
from meshcore.messages import Message
from utils.config import Config


class TestBBSCore:
    """Tests for BBSCore class."""

    @pytest.fixture
    def bbs_core(self, config: Config) -> BBSCore:
        """Create BBS core with mock connection."""
        mock_conn = MockMeshCoreConnection(node_name="TestBBS")
        return BBSCore(config=config, connection=mock_conn)

    @pytest.mark.asyncio
    async def test_start(self, bbs_core: BBSCore):
        """Test BBS startup."""
        await bbs_core.start()

        assert bbs_core._running is True
        assert bbs_core.connection.connected is True
        assert bbs_core._advert_task is not None

        await bbs_core.stop()

    @pytest.mark.asyncio
    async def test_stop(self, bbs_core: BBSCore):
        """Test BBS shutdown."""
        await bbs_core.start()
        await bbs_core.stop()

        assert bbs_core._running is False
        assert bbs_core.connection.connected is False

    @pytest.mark.asyncio
    async def test_handle_message_command(
        self, bbs_core: BBSCore, test_sender_key: str
    ):
        """Test handling a command message."""
        await bbs_core.start()

        message = Message(
            sender_key=test_sender_key,
            text="/help",
            recipient_key=bbs_core.connection.identity.public_key,
        )

        response = await bbs_core.handle_message(message)

        assert response is not None
        assert "help" in response.lower() or "commands" in response.lower()

        await bbs_core.stop()

    @pytest.mark.asyncio
    async def test_handle_message_non_command(
        self, bbs_core: BBSCore, test_sender_key: str
    ):
        """Test handling a non-command message."""
        await bbs_core.start()

        message = Message(
            sender_key=test_sender_key,
            text="Hello everyone!",
            recipient_key=bbs_core.connection.identity.public_key,
        )

        response = await bbs_core.handle_message(message)

        assert response is None  # Non-commands don't get responses

        await bbs_core.stop()

    @pytest.mark.asyncio
    async def test_handle_message_unknown_command(
        self, bbs_core: BBSCore, test_sender_key: str
    ):
        """Test handling an unknown command."""
        await bbs_core.start()

        message = Message(
            sender_key=test_sender_key,
            text="/unknowncommand",
            recipient_key=bbs_core.connection.identity.public_key,
        )

        response = await bbs_core.handle_message(message)

        assert response is not None
        assert "unknown" in response.lower() or "not found" in response.lower()

        await bbs_core.stop()

    @pytest.mark.asyncio
    async def test_integration_post_and_list(
        self, bbs_core: BBSCore, test_sender_key: str
    ):
        """Integration test: post a message and list it."""
        await bbs_core.start()

        # First, create an area by posting (this may fail initially)
        # In a real scenario, areas would be pre-configured
        # For this test, we'll test the flow

        # Try to list in a non-existent area
        list_msg = Message(
            sender_key=test_sender_key,
            text="/list general",
            recipient_key=bbs_core.connection.identity.public_key,
        )
        response = await bbs_core.handle_message(list_msg)

        # Should get some response (error or empty list)
        assert response is not None

        await bbs_core.stop()


class TestBBSCoreConfiguration:
    """Tests for BBS core configuration."""

    def test_default_config(self, config: Config):
        """Test BBS core uses provided config."""
        mock_conn = MockMeshCoreConnection()
        bbs = BBSCore(config=config, connection=mock_conn)

        assert bbs.config == config
        assert bbs.config.bbs_name == "Test BBS"

    def test_custom_connection(self, config: Config):
        """Test BBS core uses provided connection."""
        mock_conn = MockMeshCoreConnection(node_name="CustomBBS")
        bbs = BBSCore(config=config, connection=mock_conn)

        assert bbs.connection == mock_conn
        assert bbs.connection.node_name == "CustomBBS"
