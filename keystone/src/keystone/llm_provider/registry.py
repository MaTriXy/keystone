"""Provider registry for name-based lookup."""

from __future__ import annotations

from typing import TYPE_CHECKING

from keystone.llm_provider.claude import ClaudeProvider
from keystone.llm_provider.codex import CodexProvider
from keystone.llm_provider.opencode import OpencodeProvider

if TYPE_CHECKING:
    from keystone.llm_provider.base import AgentProvider
    from keystone.schema import AgentConfig

PROVIDER_REGISTRY: dict[str, type[AgentProvider]] = {
    "claude": ClaudeProvider,
    "codex": CodexProvider,
    "opencode": OpencodeProvider,
}


def get_provider(config: AgentConfig) -> AgentProvider:
    """Instantiate a provider from an AgentConfig.

    Raises ``ValueError`` if the provider name is not registered.
    """
    cls = PROVIDER_REGISTRY.get(config.provider)
    if cls is None:
        available = ", ".join(sorted(PROVIDER_REGISTRY.keys()))
        raise ValueError(f"Unknown LLM provider {config.provider!r}. Available: {available}")
    return cls(config=config)
