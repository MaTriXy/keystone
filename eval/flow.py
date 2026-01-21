"""Prefect flow for MapReduce-style evaluation."""
import json
import os
import tarfile
import tempfile
from pathlib import Path
from typing import Optional

from prefect import flow, task
from prefect.futures import wait

from config import AgentConfig, EvalConfig, RepoEntry, WorkerResult
from worker import process_repo


@task(name="process_repo_local")
def process_repo_local_task(
    tarball_path: str,
    agent_config: AgentConfig,
    output_dir: str,
) -> WorkerResult:
    """Prefect task wrapper for local repo processing."""
    anthropic_api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not anthropic_api_key:
        return WorkerResult(
            s3_repo_tarball=tarball_path,
            success=False,
            error_message="ANTHROPIC_API_KEY not set",
        )
    
    return process_repo(
        tarball_path=Path(tarball_path),
        agent_config=agent_config,
        output_dir=Path(output_dir),
        anthropic_api_key=anthropic_api_key,
    )


@task(name="process_repo_modal")
def process_repo_modal_task(
    s3_repo_tarball: str,
    agent_config: AgentConfig,
    output_s3_prefix: str,
) -> WorkerResult:
    """Prefect task wrapper for Modal repo processing."""
    from modal_worker import process_repo_modal
    
    result_dict = process_repo_modal.remote(
        s3_repo_tarball=s3_repo_tarball,
        agent_config_dict=agent_config.model_dump(),
        output_s3_prefix=output_s3_prefix,
    )
    return WorkerResult(**result_dict)


@flow(name="eval_bootstrap_devcontainer")
def eval_flow(
    repo_list_path: str,
    eval_config: EvalConfig,
    output_dir: str,
) -> list[WorkerResult]:
    """Main evaluation flow.
    
    Args:
        repo_list_path: Path to JSONL file with repo entries
        eval_config: Evaluation configuration
        output_dir: Local directory for outputs (for local mode)
        
    Returns:
        List of WorkerResult for each repo
    """
    # Load repo list
    repos: list[RepoEntry] = []
    with open(repo_list_path) as f:
        for line in f:
            line = line.strip()
            if line:
                repos.append(RepoEntry(**json.loads(line)))
    
    results: list[WorkerResult] = []
    
    if eval_config.execution_mode == "local":
        # Local execution
        futures = []
        for i, repo in enumerate(repos):
            repo_output_dir = Path(output_dir) / f"repo_{i}"
            future = process_repo_local_task.submit(
                tarball_path=repo.s3_repo_tarball,  # For local, this can be a local path
                agent_config=eval_config.agent_config,
                output_dir=str(repo_output_dir),
            )
            futures.append(future)
        
        # Wait for all to complete
        wait(futures)
        results = [f.result() for f in futures]
        
    else:
        # Modal execution
        futures = []
        for repo in repos:
            future = process_repo_modal_task.submit(
                s3_repo_tarball=repo.s3_repo_tarball,
                agent_config=eval_config.agent_config,
                output_s3_prefix=eval_config.output_s3_prefix,
            )
            futures.append(future)
        
        wait(futures)
        results = [f.result() for f in futures]
    
    # Write summary
    summary_path = Path(output_dir) / "summary.json"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    with open(summary_path, "w") as f:
        json.dump([r.model_dump() for r in results], f, indent=2)
    
    return results


@flow(name="eval_local_tarball")
def eval_local_tarball_flow(
    tarball_path: str,
    agent_config: Optional[AgentConfig] = None,
    output_dir: Optional[str] = None,
) -> WorkerResult:
    """Convenience flow for testing with a local tarball.
    
    Args:
        tarball_path: Path to local tarball
        agent_config: Optional agent config (uses defaults if not provided)
        output_dir: Output directory (uses temp dir if not provided)
        
    Returns:
        WorkerResult
    """
    if agent_config is None:
        agent_config = AgentConfig()
    
    if output_dir is None:
        output_dir = tempfile.mkdtemp(prefix="eval_output_")
    
    return process_repo_local_task(
        tarball_path=tarball_path,
        agent_config=agent_config,
        output_dir=output_dir,
    )


def create_tarball_from_dir(source_dir: Path, output_path: Path) -> Path:
    """Create a tarball from a directory."""
    with tarfile.open(output_path, "w:gz") as tar:
        tar.add(source_dir, arcname=source_dir.name)
    return output_path
