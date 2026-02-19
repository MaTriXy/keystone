"""Tests for the LLM provider abstraction."""

import json

import pytest

from keystone.llm_provider import (
    ClaudeProvider,
    ProviderConfig,
    get_provider,
)


class TestClaudeProvider:
    """Tests for the Claude provider."""

    def setup_method(self) -> None:
        self.provider = ClaudeProvider()

    def test_name(self) -> None:
        assert self.provider.name == "claude"

    def test_default_cmd(self) -> None:
        assert self.provider.default_cmd == "claude"

    def test_build_command(self) -> None:
        cmd = self.provider.build_command("Fix the bug", 5.0, "claude")
        assert cmd[0] == "claude"
        assert "--dangerously-skip-permissions" in cmd
        assert "--output-format" in cmd
        assert "stream-json" in cmd
        assert "--max-budget-usd" in cmd
        assert "5.0" in cmd
        assert "-p" in cmd
        assert "Fix the bug" in cmd

    def test_build_command_custom_agent_cmd(self) -> None:
        cmd = self.provider.build_command("prompt", 1.0, "/usr/local/bin/claude")
        assert cmd[0] == "/usr/local/bin/claude"

    def test_parse_assistant_text(self) -> None:
        line = json.dumps(
            {
                "type": "assistant",
                "message": {
                    "content": [{"type": "text", "text": "Hello world"}],
                },
            }
        )
        parsed = self.provider.parse_stdout_line(line)
        assert parsed.text == "Hello world"
        assert parsed.unparsed is False

    def test_parse_assistant_tool_use(self) -> None:
        line = json.dumps(
            {
                "type": "assistant",
                "message": {
                    "content": [
                        {"type": "tool_use", "name": "bash", "input": {"cmd": "ls"}}
                    ],
                },
            }
        )
        parsed = self.provider.parse_stdout_line(line)
        assert parsed.tool_call == ("bash", {"cmd": "ls"})

    def test_parse_result(self) -> None:
        line = json.dumps(
            {
                "type": "result",
                "total_cost_usd": 0.42,
                "model": "claude-sonnet-4-20250514",
                "usage": {
                    "input_tokens": 100,
                    "cache_read_input_tokens": 50,
                    "output_tokens": 200,
                    "cache_creation_input_tokens": 10,
                },
            }
        )
        parsed = self.provider.parse_stdout_line(line)
        assert parsed.cost_usd == 0.42
        assert parsed.model == "claude-sonnet-4-20250514"
        assert parsed.input_tokens == 100
        assert parsed.cached_tokens == 50
        assert parsed.output_tokens == 200
        assert parsed.cache_creation_tokens == 10

    def test_parse_non_json(self) -> None:
        parsed = self.provider.parse_stdout_line("not json at all")
        assert parsed.unparsed is True

    def test_parse_unknown_type(self) -> None:
        line = json.dumps({"type": "system", "data": "something"})
        parsed = self.provider.parse_stdout_line(line)
        assert parsed.raw_type == "system"
        assert parsed.unparsed is False


class TestProviderRegistry:
    """Tests for the provider registry."""

    def test_get_claude_provider(self) -> None:
        config = ProviderConfig(name="claude")
        provider = get_provider(config)
        assert isinstance(provider, ClaudeProvider)

    def test_get_unknown_provider(self) -> None:
        config = ProviderConfig(name="nonexistent")
        with pytest.raises(ValueError, match="Unknown LLM provider"):
            get_provider(config)

    def test_provider_config_cache_key_stable(self) -> None:
        config1 = ProviderConfig(name="claude", agent_cmd="claude")
        config2 = ProviderConfig(name="claude", agent_cmd="claude")
        assert config1.to_cache_key_json() == config2.to_cache_key_json()

    def test_provider_config_cache_key_changes(self) -> None:
        config1 = ProviderConfig(name="claude", agent_cmd="claude")
        config2 = ProviderConfig(name="claude", agent_cmd="/opt/claude")
        assert config1.to_cache_key_json() != config2.to_cache_key_json()
