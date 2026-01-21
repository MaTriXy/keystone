"""Modal worker definition for distributed execution."""
import os

import modal

# Define the Modal image with all required dependencies
image = (
    modal.Image.debian_slim(python_version="3.11")
    # Install Node.js and npm for Claude Code and devcontainer CLI
    .apt_install("curl", "git", "docker.io")
    .run_commands(
        # Install Node.js 20 LTS
        "curl -fsSL https://deb.nodesource.com/setup_20.x | bash -",
        "apt-get install -y nodejs",
        # Install Claude Code globally
        "npm install -g @anthropic-ai/claude-code",
        # Install devcontainer CLI
        "npm install -g @devcontainers/cli",
    )
    # Install uv for Python package management
    .run_commands(
        "curl -LsSf https://astral.sh/uv/install.sh | sh",
    )
    # Install Python dependencies
    .pip_install(
        "pydantic>=2.0",
        "boto3",
    )
)

app = modal.App("bootstrap-devcontainer-eval")


@app.function(
    image=image,
    secrets=[
        modal.Secret.from_name("anthropic-api-key"),
        modal.Secret.from_name("aws-credentials"),
    ],
    timeout=3600,  # 1 hour max
    # Enable Docker-in-Docker via privileged mode
    # Note: This requires Modal's container runtime support
)
def process_repo_modal(
    s3_repo_tarball: str,
    agent_config_dict: dict,
    output_s3_prefix: str,
) -> dict:
    """Process a single repo on Modal.
    
    Args:
        s3_repo_tarball: S3 URI to the input tarball
        agent_config_dict: AgentConfig as a dict
        output_s3_prefix: S3 prefix for outputs
        
    Returns:
        WorkerResult as a dict
    """
    import json
    import shutil
    import tarfile
    import tempfile
    from pathlib import Path

    import boto3

    # Import our local modules
    from eval.config import AgentConfig
    from eval.worker import process_repo

    # Parse config
    agent_config = AgentConfig(**agent_config_dict)
    
    # Get API key from secret
    anthropic_api_key = os.environ["ANTHROPIC_API_KEY"]
    
    # Set up S3 client
    s3 = boto3.client("s3")
    
    # Parse S3 URI
    # s3://bucket/key -> bucket, key
    bucket, key = s3_repo_tarball.replace("s3://", "").split("/", 1)
    
    # Download tarball
    work_dir = Path(tempfile.mkdtemp(prefix="modal_worker_"))
    tarball_path = work_dir / "input.tar.gz"
    
    s3.download_file(bucket, key, str(tarball_path))
    
    # Process the repo
    output_dir = work_dir / "output"
    result = process_repo(
        tarball_path=tarball_path,
        agent_config=agent_config,
        output_dir=output_dir,
        anthropic_api_key=anthropic_api_key,
    )
    
    # Upload outputs to S3
    result.s3_repo_tarball = s3_repo_tarball
    
    output_bucket, output_prefix = output_s3_prefix.replace("s3://", "").split("/", 1)
    repo_name = Path(key).stem.replace(".tar", "")
    
    if result.devcontainer_tarball_s3 and Path(result.devcontainer_tarball_s3).exists():
        output_key = f"{output_prefix}{repo_name}/devcontainer.tar.gz"
        s3.upload_file(result.devcontainer_tarball_s3, output_bucket, output_key)
        result.devcontainer_tarball_s3 = f"s3://{output_bucket}/{output_key}"
    
    if result.session_jsonl_s3 and Path(result.session_jsonl_s3).exists():
        output_key = f"{output_prefix}{repo_name}/session.jsonl"
        s3.upload_file(result.session_jsonl_s3, output_bucket, output_key)
        result.session_jsonl_s3 = f"s3://{output_bucket}/{output_key}"
    
    # Clean up
    shutil.rmtree(work_dir, ignore_errors=True)
    
    return result.model_dump()
