"""Snapshot tests for prompt generation.

Run with --snapshot-update to regenerate goldens after intentional changes.
"""

import pytest
from syrupy.assertion import SnapshotAssertion

from keystone.prompts import build_agent_prompt, build_agents_md_prompt
from keystone.schema import AgentConfig


def _make_config(
    *,
    guardrail: bool = True,
    agent_in_modal: bool = True,
    use_agents_md: bool = False,
) -> AgentConfig:
    """Helper to build an AgentConfig with sensible defaults for testing."""
    return AgentConfig(
        max_budget_usd=1.0,
        agent_time_limit_seconds=3600,
        agent_in_modal=agent_in_modal,
        provider="claude",
        evaluator=True,
        guardrail=guardrail,
        use_agents_md=use_agents_md,
    )


# -- Inline prompt (build_agent_prompt) ------------------------------------


@pytest.mark.parametrize(
    "guardrail,agent_in_modal",
    [
        (True, True),
        (True, False),
        (False, True),
        (False, False),
    ],
    ids=[
        "guardrail-modal",
        "guardrail-local",
        "no_guardrail-modal",
        "no_guardrail-local",
    ],
)
def test_inline_prompt(
    guardrail: bool,
    agent_in_modal: bool,
    snapshot: SnapshotAssertion,
) -> None:
    config = _make_config(guardrail=guardrail, agent_in_modal=agent_in_modal)
    prompt = build_agent_prompt(config)
    assert prompt == snapshot


# -- AGENTS.md prompt (build_agents_md_prompt) ------------------------------


@pytest.mark.parametrize(
    "guardrail,agent_in_modal",
    [
        (True, True),
        (True, False),
        (False, True),
        (False, False),
    ],
    ids=[
        "guardrail-modal",
        "guardrail-local",
        "no_guardrail-modal",
        "no_guardrail-local",
    ],
)
def test_agents_md_prompt(
    guardrail: bool,
    agent_in_modal: bool,
    snapshot: SnapshotAssertion,
) -> None:
    config = _make_config(guardrail=guardrail, agent_in_modal=agent_in_modal)
    agents_md, short_prompt = build_agents_md_prompt(config)
    assert {"agents_md": agents_md, "short_prompt": short_prompt} == snapshot
