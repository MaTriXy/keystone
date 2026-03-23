"""
Modal sandbox with Docker-in-Docker capability for running docker build commands.

Usage:
    # Deploy and get SSH access
    uv run modal run modal_docker_sandbox.py

    # Or run as a persistent app
    uv run modal deploy modal_docker_sandbox.py
"""

import modal

# Create a Modal image with Docker installed
image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install(
        "ca-certificates",
        "curl",
        "gnupg",
        "lsb-release",
        "openssh-server",
    )
    # Install Docker
    .run_commands(
        "install -m 0755 -d /etc/apt/keyrings",
        "curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg",
        "chmod a+r /etc/apt/keyrings/docker.gpg",
        'echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian $(lsb_release -cs) stable" > /etc/apt/sources.list.d/docker.list',
    )
    .apt_install(
        "docker-ce",
        "docker-ce-cli",
        "containerd.io",
        "docker-buildx-plugin",
    )
)

app = modal.App("docker-sandbox", image=image)


@app.function(
    # Enable Docker-in-Docker by requesting privileged mode
    # Note: This requires Modal's experimental DinD support
    timeout=3600,
)
def test_docker():
    """Test that Docker is available."""
    import subprocess

    # Start Docker daemon
    subprocess.run(
        ["dockerd", "--host=unix:///var/run/docker.sock"],
        start_new_session=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    import time

    time.sleep(3)

    result = subprocess.run(["docker", "version"], capture_output=True, text=True)
    print("Docker version output:")
    print(result.stdout)
    print(result.stderr)
    return result.returncode == 0


@app.local_entrypoint()
def main():
    """Run a quick Docker test."""
    print("Testing Docker in Modal sandbox...")
    success = test_docker.remote()
    if success:
        print("✓ Docker is working!")
    else:
        print("✗ Docker failed to start")
