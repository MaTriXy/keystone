#!/usr/bin/env python3
"""Docker Registry running on Modal with persistent storage.

This provides a build cache for docker builds running in Modal sandboxes.
The registry persists data to a Modal Volume for durability.

ARCHITECTURE:
- Uses Modal's @web_server to expose the registry:2 container on port 5000
- Data persisted to a Modal Volume
- Sandboxes can reach it via the public URL

Usage:
    # Deploy the registry
    uv run modal deploy scripts/modal_registry.py

    # The URL will be printed, something like:
    # https://<workspace>--docker-registry-registry.modal.run

    # In your docker builds (inside Modal sandbox):
    docker buildx build \\
        --cache-to type=registry,ref=<registry-url>/cache:latest \\
        --cache-from type=registry,ref=<registry-url>/cache:latest \\
        -t myimage .

LIMITATIONS:
- Docker registry protocol requires specific HTTP handling
- Modal's web_server may need adjustments for chunked uploads
- Consider using Modal Volumes directly for simpler caching
"""

import modal

app = modal.App("docker-registry")

# Persistent volume for registry data
registry_volume = modal.Volume.from_name("docker-registry-data", create_if_missing=True)

# Build image with registry installed
registry_image = (
    modal.Image.debian_slim()
    .apt_install("ca-certificates", "curl")
    .run_commands(
        # Install docker registry binary
        "curl -L https://github.com/distribution/distribution/releases/download/v2.8.3/registry_2.8.3_linux_amd64.tar.gz | tar xz",
        "mv registry /usr/local/bin/",
        "mkdir -p /etc/docker/registry /var/lib/registry",
    )
    .run_commands(
        # Create config
        "echo 'version: 0.1' > /etc/docker/registry/config.yml",
        "echo 'log:' >> /etc/docker/registry/config.yml",
        "echo '  level: info' >> /etc/docker/registry/config.yml",
        "echo 'storage:' >> /etc/docker/registry/config.yml",
        "echo '  filesystem:' >> /etc/docker/registry/config.yml",
        "echo '    rootdirectory: /var/lib/registry' >> /etc/docker/registry/config.yml",
        "echo '  delete:' >> /etc/docker/registry/config.yml",
        "echo '    enabled: true' >> /etc/docker/registry/config.yml",
        "echo 'http:' >> /etc/docker/registry/config.yml",
        "echo '  addr: :5000' >> /etc/docker/registry/config.yml",
    )
)


@app.function(
    image=registry_image,
    volumes={"/var/lib/registry": registry_volume},
    timeout=86400,  # 24 hours
    cpu=1.0,
    memory=512,
)
@modal.web_server(port=5000, startup_timeout=60)
def registry():
    """Run the Docker registry."""
    import subprocess

    # Start registry as subprocess (not execv - Modal needs to manage the process)
    subprocess.Popen(
        ["/usr/local/bin/registry", "serve", "/etc/docker/registry/config.yml"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


@app.function(
    image=registry_image,
    volumes={"/var/lib/registry": registry_volume},
)
def get_info() -> dict:
    """Get registry storage info."""
    import os
    from pathlib import Path

    data_path = Path("/var/lib/registry")
    total_size = 0
    file_count = 0

    if data_path.exists():
        for root, _dirs, files in os.walk(data_path):
            for f in files:
                fp = Path(root) / f
                try:
                    total_size += fp.stat().st_size
                    file_count += 1
                except OSError:
                    pass

    return {
        "file_count": file_count,
        "total_size_mb": round(total_size / (1024 * 1024), 2),
    }


@app.local_entrypoint()
def main(info: bool = False):
    """Check registry status."""
    if info:
        data = get_info.remote()
        print(f"Registry cache: {data['file_count']} files, {data['total_size_mb']} MB")
    else:
        print("Deploy with: modal deploy scripts/modal_registry.py")
        print("Check info with: modal run scripts/modal_registry.py --info")
