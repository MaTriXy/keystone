"""LLM provider abstraction for swappable agent backends.

Each provider knows how to:
1. Build a CLI command to invoke the agent
2. Parse streaming stdout into structured data (cost, tokens, messages)
3. Report a stable identifier for cache keys

To add a new provider, subclass LLMProvider and register it in PROVIDER_REGISTRY.
"""

from __future__ import annotations

import json
import logging
import shlex
from abc import ABC, abstractmethod
from dataclasses import dataclass

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class ProviderConfig(BaseModel):
    """Serializable provider configuration, used as part of the cache key.

    Attributes:
        name: Provider registry name (e.g. "claude", "aider-gpt4").
        agent_cmd: Base CLI command/path to invoke.  Defaults vary per provider.
        extra: Provider-specific key/value overrides (forwarded to the provider).
    """

    name: str = "claude"
    agent_cmd: str | None = None  # None → provider default
    extra: dict[str, str] = {}

    def to_cache_key_json(self) -> str:
        """Stable JSON for cache key computation."""
        return self.model_dump_json(indent=None)


# ── Parsed output from a single stdout line ──────────────────────────


@dataclass
class ParsedLine:
    """Result of parsing one stdout line from the agent process.

    Fields are *additive* - a single line may set several at once (e.g. a
    ``result`` message carries cost, model, *and* token deltas).
    """

    # Human-readable text the agent emitted (assistant turn text)
    text: str | None = None
    # Tool call info (name, input dict)
    tool_call: tuple[str, dict] | None = None
    # Cumulative cost so far (provider sets this when it sees cost info)
    cost_usd: float | None = None
    # Model identifier string
    model: str | None = None
    # Token usage deltas for this turn
    input_tokens: int = 0
    cached_tokens: int = 0
    output_tokens: int = 0
    cache_creation_tokens: int = 0
    # Raw message type (for debug logging of unhandled types)
    raw_type: str | None = None
    # If True the line was not parseable JSON — just debug noise
    unparsed: bool = False


# ── Abstract provider ─────────────────────────────────────────────────


class LLMProvider(ABC):
    """Interface that each LLM backend must implement."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Short identifier used in CLI flags and cache keys (e.g. ``'claude'``)."""
        ...

    @property
    @abstractmethod
    def default_cmd(self) -> str:
        """Default executable / command when the user doesn't override ``agent_cmd``."""
        ...

    @abstractmethod
    def build_command(
        self,
        prompt: str,
        max_budget_usd: float,
        agent_cmd: str,
    ) -> list[str]:
        """Return the full argv list to execute the agent.

        Parameters
        ----------
        prompt:
            The task prompt to send to the agent.
        max_budget_usd:
            Spending cap for this run.
        agent_cmd:
            Base command (may be overridden by user; falls back to *default_cmd*).
        """
        ...

    @abstractmethod
    def parse_stdout_line(self, line: str) -> ParsedLine:
        """Parse a single line of agent stdout into structured data.

        Providers that emit non-JSON on stdout should return
        ``ParsedLine(unparsed=True)`` for those lines.
        """
        ...

    def env_vars(self) -> dict[str, str]:
        """Extra environment variables required by this provider.

        Override if the provider needs e.g. ``OPENAI_API_KEY``.
        Returns an empty dict by default.
        """
        return {}


# ── Claude Code provider ──────────────────────────────────────────────


class ClaudeProvider(LLMProvider):
    """Provider for the ``claude`` CLI (Claude Code)."""

    @property
    def name(self) -> str:
        return "claude"

    @property
    def default_cmd(self) -> str:
        return "claude"

    def build_command(
        self,
        prompt: str,
        max_budget_usd: float,
        agent_cmd: str,
    ) -> list[str]:
        return [
            *shlex.split(agent_cmd),
            "--dangerously-skip-permissions",
            *("--output-format", "stream-json"),
            "--verbose",
            *("--max-budget-usd", str(max_budget_usd)),
            *("-p", prompt),
        ]

    def parse_stdout_line(self, line: str) -> ParsedLine:
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            return ParsedLine(unparsed=True)

        msg_type = data.get("type")
        result = ParsedLine(raw_type=msg_type)

        if msg_type == "assistant":
            content = data.get("message", {}).get("content", [])
            for item in content:
                if item.get("type") == "text":
                    txt = item.get("text", "").strip()
                    if txt:
                        result.text = txt
                elif item.get("type") == "tool_use":
                    result.tool_call = (item.get("name", ""), item.get("input", {}))

        elif msg_type == "result":
            result.cost_usd = data.get("total_cost_usd", 0.0)
            result.model = data.get("model", "")
            usage = data.get("usage", {})
            result.input_tokens = usage.get("input_tokens", 0)
            result.cached_tokens = usage.get("cache_read_input_tokens", 0)
            result.output_tokens = usage.get("output_tokens", 0)
            result.cache_creation_tokens = usage.get("cache_creation_input_tokens", 0)

        return result


# ── Provider registry ─────────────────────────────────────────────────

PROVIDER_REGISTRY: dict[str, type[LLMProvider]] = {
    "claude": ClaudeProvider,
}


def get_provider(config: ProviderConfig) -> LLMProvider:
    """Instantiate an LLM provider from a :class:`ProviderConfig`.

    Raises ``ValueError`` if the provider name is not registered.
    """
    cls = PROVIDER_REGISTRY.get(config.name)
    if cls is None:
        available = ", ".join(sorted(PROVIDER_REGISTRY.keys()))
        raise ValueError(
            f"Unknown LLM provider {config.name!r}. Available: {available}"
        )
    return cls()
