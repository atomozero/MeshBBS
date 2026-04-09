"""
Tests for command parser.

MIT License - Copyright (c) 2026 MeshBBS Contributors
"""

import pytest
from bbs.commands.parser import parse_command, ParsedCommand


class TestParseCommand:
    """Tests for parse_command function."""

    def test_parse_simple_command(self):
        """Test parsing a simple command without arguments."""
        result = parse_command("/help")
        assert result is not None
        assert result.command == "help"
        assert result.raw_args == ""
        assert result.args == []

    def test_parse_command_with_args(self):
        """Test parsing a command with arguments."""
        result = parse_command("/post general Hello world!")
        assert result is not None
        assert result.command == "post"
        assert result.raw_args == "general Hello world!"
        assert "general" in result.args
        assert "Hello" in result.args

    def test_parse_command_with_whitespace(self):
        """Test parsing a command with extra whitespace."""
        result = parse_command("  /list   general  ")
        assert result is not None
        assert result.command == "list"
        assert "general" in result.raw_args

    def test_parse_non_command(self):
        """Test parsing a non-command message."""
        result = parse_command("Hello everyone!")
        assert result is None

    def test_parse_empty_string(self):
        """Test parsing an empty string."""
        result = parse_command("")
        assert result is None

    def test_parse_just_slash(self):
        """Test parsing just a slash."""
        result = parse_command("/")
        assert result is None

    def test_parse_command_case_insensitive(self):
        """Test that command parsing is case-insensitive."""
        result = parse_command("/HELP")
        assert result is not None
        assert result.command == "help"

    def test_parse_command_with_numbers(self):
        """Test parsing a command with numeric arguments."""
        result = parse_command("/read 123")
        assert result is not None
        assert result.command == "read"
        assert result.raw_args == "123"
        assert "123" in result.args

    def test_parse_command_multiline(self):
        """Test parsing command with multiline content."""
        result = parse_command("/post general Line 1\nLine 2\nLine 3")
        assert result is not None
        assert result.command == "post"
        # Parser takes full message, command handles multiline
        assert "Line 1" in result.raw_args

    def test_parsed_command_has_args(self):
        """Test ParsedCommand.has_args property."""
        with_args = parse_command("/post hello")
        without_args = parse_command("/help")

        assert with_args.has_args is True
        assert without_args.has_args is False

    def test_parsed_command_get_arg(self):
        """Test ParsedCommand.get_arg method."""
        result = parse_command("/post area message text")
        assert result.get_arg(0) == "area"
        assert result.get_arg(1) == "message"
        assert result.get_arg(99, "default") == "default"
