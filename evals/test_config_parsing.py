"""Test that all JSON config files parse as valid EvalRunConfig."""

from pathlib import Path

import json5
import pytest
from eval_schema import EvalRunConfig

EVALS_DIR = Path(__file__).parent

# All JSON config files that should parse as EvalRunConfig.
CONFIG_FILES = sorted(
    list(EVALS_DIR.glob("examples/*.json")) + list(EVALS_DIR.glob("test_data/*/config.json"))
)


@pytest.mark.parametrize("config_file", CONFIG_FILES, ids=lambda p: str(p.relative_to(EVALS_DIR)))
def test_config_file_parses(config_file: Path) -> None:
    """Each config file should parse as a valid EvalRunConfig."""
    config = EvalRunConfig.model_validate(json5.loads(config_file.read_text()))
    assert len(config.configs) > 0
    for ec in config.configs:
        assert ec.keystone_config.agent_config.agent_time_limit_seconds > 0
