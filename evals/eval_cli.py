"""CLI for the eval harness."""

import logging
from pathlib import Path

import json5
import typer
from config import AgentConfig, EvalConfig, EvalOutput, EvalRunConfig, LLMModel
from flow import eval_flow
from rich.console import Console

DEFAULT_LOG_PATH = Path.home() / ".imbue_keystone" / "log.sqlite"

# Configure logging: WARNING for third-party, INFO for our code and prefect
logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
# Allow INFO from our own modules; DEBUG for prefect task runs so keystone
# stderr lines (logged at DEBUG) appear in the Prefect UI.
for _logger_name in ("flow", "eval_cli", "prefect.flow_runs"):
    logging.getLogger(_logger_name).setLevel(logging.INFO)
logging.getLogger("prefect.task_runs").setLevel(logging.DEBUG)

app = typer.Typer(help="Eval harness for keystone")
console = Console()


def _print_results(outputs: list[EvalOutput], eval_configs: list[EvalConfig]) -> None:
    """Print a summary of results for each eval config."""
    for output, eval_config in zip(outputs, eval_configs, strict=True):
        label = eval_config.name or "unnamed"
        success_count = sum(1 for r in output.results if r.success)
        console.print(
            f"\n[bold]Results [{label}]: {success_count}/{len(output.results)} succeeded[/bold]"
        )

        for result in output.results:
            status = "[green]✓[/green]" if result.success else "[red]✗[/red]"
            console.print(f"  {status} {result.repo_entry.id}")
            if not result.success and result.error_message:
                for line in result.error_message.strip().split("\n")[:3]:
                    console.print(f"      {line[:100]}")

        console.print(f"  Results uploaded to: {eval_config.s3_output_prefix}")


@app.command()
def run(
    config_file: Path | None = typer.Option(
        None,
        "--config_file",
        help="Path to JSON config file (EvalRunConfig).",
    ),
    repo_list_path: Path | None = typer.Option(
        None, "--repo_list_path", help="Path to repo_list.jsonl"
    ),
    s3_output_prefix: str | None = typer.Option(
        None,
        "--s3_output_prefix",
        help="S3 prefix for per-repo results (e.g. s3://bucket/evals/2026-02-20/)",
    ),
    s3_repo_cache_prefix: str = typer.Option(
        "s3://int8-datasets/keystone/evals/repo-tarballs/",
        "--s3_repo_cache_prefix",
        help="S3 prefix for cached repo tarballs",
    ),
    provider: str = typer.Option(
        "claude", "--provider", help="LLM provider name (claude, codex, or opencode)"
    ),
    max_budget_usd: float = typer.Option(
        1.0, "--max_budget_usd", help="Maximum budget per repo in USD"
    ),
    timeout_minutes: int = typer.Option(
        60, "--timeout_minutes", help="Timeout per repo in minutes"
    ),
    log_db: str = typer.Option(
        str(DEFAULT_LOG_PATH), "--log_db", help="Database for logging/caching"
    ),
    max_workers: int = typer.Option(4, "--max_workers", help="Max parallel workers"),
    trials_per_repo: int = typer.Option(
        1, "--trials_per_repo", help="Number of trials per repo (>1 disables caching)"
    ),
    model: LLMModel | None = typer.Option(
        None,
        "--model",
        help="LLM model to use",
    ),
    require_cache_hit: bool = typer.Option(False, "--require_cache_hit", help="Fail if cache miss"),
    no_cache_replay: bool = typer.Option(False, "--no_cache_replay", help="Force fresh execution"),
    docker_cache_secret: str = typer.Option(
        "keystone-docker-registry-config",
        "--docker_cache_secret",
        help="Modal secret name for Docker build cache registry credentials",
    ),
    limit: int | None = typer.Option(None, "--limit", help="Limit to first N repos"),
) -> None:
    """Run the eval harness on a list of repos.

    Provide ``--config_file`` to load an ``EvalRunConfig`` JSON file, or pass
    individual CLI flags to build an equivalent single-config run.  Either way
    the same code path is used.  CLI flags like ``--no_cache_replay`` and
    ``--require_cache_hit`` are applied as overrides on top of the config file.
    """
    # --- Build run_config from either a config file or CLI flags ----------
    if config_file is not None:
        raw: dict = json5.loads(config_file.read_text())  # type: ignore[assignment]
        run_config = EvalRunConfig(**raw)
    else:
        if repo_list_path is None:
            console.print("[red]Error:[/red] --repo_list_path is required (or use --config_file)")
            raise typer.Exit(1)
        if s3_output_prefix is None:
            console.print("[red]Error:[/red] --s3_output_prefix is required (or use --config_file)")
            raise typer.Exit(1)

        run_config = EvalRunConfig(
            repo_list_path=str(repo_list_path),
            s3_output_prefix=s3_output_prefix,
            s3_repo_cache_prefix=s3_repo_cache_prefix,
            limit=limit,
            configs=[
                EvalConfig(
                    name="cli",
                    agent_config=AgentConfig(
                        provider=provider,
                        max_budget_usd=max_budget_usd,
                        timeout_minutes=timeout_minutes,
                        log_db=log_db,
                        docker_cache_secret=docker_cache_secret,
                        model=model,
                    ),
                    max_workers=max_workers,
                    trials_per_repo=trials_per_repo,
                ),
            ],
        )

    effective_limit = limit if limit is not None else run_config.limit

    resolved_configs = [
        run_config.resolve_config(cfg, i) for i, cfg in enumerate(run_config.configs)
    ]

    # Apply CLI overrides to all configs
    if no_cache_replay:
        for cfg in resolved_configs:
            cfg.agent_config = cfg.agent_config.model_copy(update={"no_cache_replay": True})
    if require_cache_hit:
        for cfg in resolved_configs:
            cfg.agent_config = cfg.agent_config.model_copy(update={"require_cache_hit": True})

    # Print plan
    console.print(f"\n[bold]Eval run: {len(resolved_configs)} configs[/bold]")
    console.print(f"  Repos: {run_config.repo_list_path}")
    console.print(f"  S3 output: {run_config.s3_output_prefix}")
    console.print(f"  S3 repo cache: {run_config.s3_repo_cache_prefix}")
    for cfg in resolved_configs:
        console.print(
            f"  - {cfg.name}: provider={cfg.agent_config.provider}, "
            f"model={cfg.agent_config.model.value if cfg.agent_config.model else 'default'}"
        )

    outputs = eval_flow(
        repo_list_path=run_config.repo_list_path,
        eval_configs=resolved_configs,
        s3_repo_cache_prefix=run_config.s3_repo_cache_prefix,
        limit=effective_limit,
    )

    _print_results(outputs, resolved_configs)


if __name__ == "__main__":
    app()
