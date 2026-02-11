import os
import subprocess
import sys
from pathlib import Path

import modal

app = modal.App("bootstrap-devcontainer-docker-registry-cache")

REGISTRY_PORT = 5000

# Persistent storage for cached layers
registry_volume = modal.Volume.from_name(
    "bootstrap-devcontainer-docker-registry-cache-volume",
    create_if_missing=True,
)

# Base image: Start with Python image, then add registry binary
registry_image = (
    modal.Image.debian_slim(python_version="3.12")
    .apt_install("ca-certificates", "wget")
    .run_commands(
        # Download and install Docker registry binary
        "wget -O /tmp/registry.tar.gz https://github.com/distribution/distribution/releases/download/v2.8.3/registry_2.8.3_linux_amd64.tar.gz",
        "tar -xzf /tmp/registry.tar.gz -C /usr/local/bin",
        "chmod +x /usr/local/bin/registry",
        "rm /tmp/registry.tar.gz",
    )
    .add_local_file("registry_config.yml", "/etc/docker/registry/config.yml")
)

auth_secret = modal.Secret.from_name("bootstrap-devcontainer-docker-registry-auth")


@app.function(
    image=registry_image,
    volumes={"/var/lib/registry": registry_volume},
    secrets=[auth_secret],
    max_containers=1,  # enforce singleton writer
    min_containers=1,  # keep registry hot (faster builds)
    timeout=60 * 60 * 2,  # allow long pushes (2 hours)
    cpu=1,
    memory=1024,
)
@modal.concurrent(max_inputs=100)
@modal.web_server(REGISTRY_PORT)
def registry() -> None:
    """Start the Docker registry directly on the exposed port. No proxy needed."""
    # Write htpasswd file from secret
    Path("/auth").mkdir(parents=True, exist_ok=True)
    Path("/auth/htpasswd").write_text(os.environ["HT_PASSWD"], encoding="utf-8")

    print("Starting Docker registry on port {REGISTRY_PORT}...", file=sys.stderr)
    subprocess.Popen(
        ["registry", "serve", "/etc/docker/registry/config.yml"],
        stdout=sys.stderr,
        stderr=sys.stderr,
    )
