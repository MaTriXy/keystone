"""OpenAI Codex CLI provider implementation.

Reference:
    https://github.com/openai/codex/blob/main/docs/exec.md
    https://github.com/openai/codex/blob/main/sdk/typescript/src/events.ts
"""

from __future__ import annotations

import json
import os
import shlex

from keystone.llm_provider.base import (
    AgentCostEvent,
    AgentErrorEvent,
    AgentEvent,
    AgentProvider,
    AgentTextEvent,
    AgentToolCallEvent,
    AgentToolResultEvent,
)

# Pricing per 1M tokens for OpenAI models used by the Codex CLI.
# Source: https://platform.openai.com/docs/pricing  (February 2026)
# Each entry maps a model-name prefix to (input, cached_input, output) rates.
_OPENAI_PRICING_PER_M: dict[str, tuple[float, float, float]] = {
    "gpt-5.2": (1.75, 0.18, 14.00),
    "gpt-5.1": (1.25, 0.125, 10.00),
    "gpt-5": (1.25, 0.125, 10.00),  # also matches gpt-5-codex
}

# Default pricing when the model name is unknown (codex CLI doesn't report it).
# Uses gpt-5-codex rates as a conservative default.
_DEFAULT_PRICING_PER_M: tuple[float, float, float] = (1.25, 0.125, 10.00)


def _estimate_cost_usd(
    input_tokens: int,
    cached_tokens: int,
    output_tokens: int,
    model: str | None = None,
) -> float:
    """Estimate dollar cost from token counts and (optional) model name.

    Cached tokens are a subset of input tokens, so we bill the non-cached
    portion at the full input rate and the cached portion at the discounted
    cached-input rate.
    """
    pricing = _DEFAULT_PRICING_PER_M
    if model:
        model_lower = model.lower()
        for prefix, rates in _OPENAI_PRICING_PER_M.items():
            if model_lower.startswith(prefix):
                pricing = rates
                break

    input_rate, cached_rate, output_rate = pricing
    non_cached = max(input_tokens - cached_tokens, 0)
    return (
        non_cached * input_rate / 1_000_000
        + cached_tokens * cached_rate / 1_000_000
        + output_tokens * output_rate / 1_000_000
    )


class CodexProvider(AgentProvider):
    """Provider for the ``codex`` CLI (OpenAI Codex)."""

    def __init__(self, model: str | None = None) -> None:
        super().__init__(model)
        self._cumulative_cost_usd: float = 0.0

    @property
    def name(self) -> str:
        return "codex"

    @property
    def default_cmd(self) -> str:
        return "codex"

    def build_command(
        self,
        prompt: str,
        max_budget_usd: float,  # noqa: ARG002  # required by interface
        agent_cmd: str,
    ) -> list[str]:
        cmd = [
            *shlex.split(agent_cmd),
            *((f"--model={self.model}",) if self.model else ()),
            "exec",
            "--sandbox",
            "danger-full-access",
            "--skip-git-repo-check",
            "--json",
            prompt,
        ]
        return cmd

    def parse_stdout_line(self, line: str) -> list[AgentEvent]:
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            return []

        event_type = data.get("type")
        events: list[AgentEvent] = []

        if event_type == "turn.completed":
            usage = data.get("usage", {})
            input_tok = usage.get("input_tokens", 0)
            output_tok = usage.get("output_tokens", 0)
            cached_tok = usage.get("cached_input_tokens", 0)
            turn_cost = _estimate_cost_usd(input_tok, cached_tok, output_tok, self.model)
            self._cumulative_cost_usd += turn_cost
            events.append(
                AgentCostEvent(
                    cost_usd=self._cumulative_cost_usd,
                    input_tokens=input_tok,
                    output_tokens=output_tok,
                    cached_tokens=cached_tok,
                )
            )

        elif event_type == "turn.failed":
            error = data.get("error", {})
            events.append(AgentErrorEvent(message=error.get("message", "Unknown error")))

        elif event_type in ("item.started", "item.completed"):
            events.extend(self._parse_item(data.get("item", {})))

        elif event_type == "thread.started":
            # Session lifecycle event; no action needed
            pass

        elif event_type == "error":
            events.append(AgentErrorEvent(message=data.get("message", "Unknown error")))

        return events

    def _parse_item(self, item: dict) -> list[AgentEvent]:
        """Parse a Codex thread item into agent events."""
        item_type = item.get("type")
        events: list[AgentEvent] = []

        if item_type == "agent_message":
            text = item.get("text", "").strip()
            if text:
                events.append(AgentTextEvent(text=text))

        elif item_type == "command_execution":
            status = item.get("status")
            if status == "in_progress":
                events.append(
                    AgentToolCallEvent(
                        name="bash",
                        input={"command": item.get("command", "")},
                    )
                )
            else:
                events.append(
                    AgentToolResultEvent(
                        tool_name="bash",
                        output=item.get("aggregated_output", ""),
                        exit_code=item.get("exit_code"),
                    )
                )

        elif item_type == "file_change":
            changes = item.get("changes", [])
            events.append(
                AgentToolCallEvent(
                    name="file_change",
                    input={"changes": changes},
                )
            )

        elif item_type == "reasoning":
            # Reasoning / thinking; skip for now
            pass

        elif item_type == "error":
            events.append(AgentErrorEvent(message=item.get("message", "Unknown error")))

        return events

    def env_vars(self) -> dict[str, str]:
        key = os.environ.get("OPENAI_API_KEY", "")
        # CODEX_API_KEY is read directly by ``codex exec`` for authentication,
        # avoiding the need for a separate ``codex login`` step.
        return {"OPENAI_API_KEY": key, "CODEX_API_KEY": key} if key else {}
