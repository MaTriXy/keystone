"""LLM evaluator for checking agent work completeness.

Makes a single, cheap LLM call (Haiku) to verify that the agent actually
completed its task rather than giving up or producing incomplete output.
"""

from __future__ import annotations

import json
import logging
import os

import anthropic

from keystone.schema import EvaluatorResult

logger = logging.getLogger(__name__)

EVALUATOR_MODEL = "claude-haiku-4-5-20251001"

EVALUATOR_SYSTEM_PROMPT = """\
You are a strict quality evaluator for an AI agent that creates devcontainer setups.
Your job is to determine whether the agent completed its task or gave up / produced incomplete work.

The agent's task was to create three files inside .devcontainer/:
1. devcontainer.json — copied from a pre-generated file
2. Dockerfile — a working Docker image definition
3. run_all_tests.sh — a test runner script that produces JUnit XML

You will be given:
- The generated files (if any)
- The agent's status messages and summary
- The verification result (build/test outcome)

Evaluate whether the agent:
- Created all three required files
- Made a genuine attempt at a working Dockerfile (not just a stub)
- Made a genuine attempt at a working test runner (not just a stub)
- Did not give up early with excuses

Respond with a JSON object:
{
  "passed": true/false,
  "reasoning": "Brief explanation of your assessment",
  "issues": ["list", "of", "specific", "issues"]  // empty if passed
}
"""


def evaluate_agent_work(
    generated_files: dict[str, str | None],
    agent_summary: str | None,
    status_messages: list[str],
    verification_success: bool,
    verification_error: str | None,
) -> EvaluatorResult:
    """Run the LLM evaluator on the agent's output.

    Args:
        generated_files: Dict with keys devcontainer_json, dockerfile, run_all_tests_sh.
        agent_summary: The agent's final summary message (if any).
        status_messages: List of status messages from the agent.
        verification_success: Whether the Docker build + tests passed.
        verification_error: Error message from verification (if any).

    Returns:
        EvaluatorResult with pass/fail and reasoning.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        logger.warning("ANTHROPIC_API_KEY not set, skipping LLM evaluation")
        return EvaluatorResult(
            passed=True,
            reasoning="Skipped: ANTHROPIC_API_KEY not available",
        )

    # Build the user message with all context
    user_parts: list[str] = []

    user_parts.append("## Generated Files\n")
    for name, content in generated_files.items():
        if content:
            # Truncate very long files to save tokens
            display = content[:3000] + "\n...(truncated)" if len(content) > 3000 else content
            user_parts.append(f"### {name}\n```\n{display}\n```\n")
        else:
            user_parts.append(f"### {name}\nNOT CREATED\n")

    if status_messages:
        user_parts.append("## Agent Status Messages\n")
        for msg in status_messages[-10:]:  # Last 10 messages
            user_parts.append(f"- {msg}")

    if agent_summary:
        user_parts.append(f"\n## Agent Summary\n{agent_summary}")

    user_parts.append("\n## Verification Result")
    user_parts.append(f"Success: {verification_success}")
    if verification_error:
        # Truncate very long verification errors
        err_display = (
            verification_error[:2000] + "\n...(truncated)"
            if len(verification_error) > 2000
            else verification_error
        )
        user_parts.append(f"Error: {err_display}")

    user_message = "\n".join(user_parts)

    try:
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model=EVALUATOR_MODEL,
            max_tokens=512,
            system=EVALUATOR_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )

        # Parse the response — only TextBlock has .text
        first_block = response.content[0]
        if not hasattr(first_block, "text"):
            return EvaluatorResult(
                passed=False,
                reasoning="Evaluator returned non-text content block",
                model=EVALUATOR_MODEL,
            )
        response_text = first_block.text.strip()  # type: ignore[union-attr]

        # Extract JSON from the response (handle markdown code blocks)
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0].strip()

        result_data = json.loads(response_text)

        cost_usd = 0.0
        if response.usage:
            # Haiku pricing: $0.80/1M input, $4/1M output
            cost_usd = (
                response.usage.input_tokens * 0.80 / 1_000_000
                + response.usage.output_tokens * 4.0 / 1_000_000
            )

        return EvaluatorResult(
            passed=result_data.get("passed", False),
            reasoning=result_data.get("reasoning", "No reasoning provided"),
            issues=result_data.get("issues", []),
            model=EVALUATOR_MODEL,
            cost_usd=cost_usd,
        )

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse evaluator response as JSON: {e}")
        return EvaluatorResult(
            passed=False,
            reasoning=f"Evaluator response was not valid JSON: {e}",
            model=EVALUATOR_MODEL,
        )
    except Exception as e:
        logger.error(f"Evaluator LLM call failed: {e}")
        return EvaluatorResult(
            passed=True,
            reasoning=f"Evaluator call failed (non-blocking): {e}",
            model=EVALUATOR_MODEL,
        )
