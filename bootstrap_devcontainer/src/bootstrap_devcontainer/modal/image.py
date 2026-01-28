import base64
from pathlib import Path

import modal

_MODAL_DIR = Path(__file__).parent
START_DOCKERD_SCRIPT_PATH = _MODAL_DIR / "start_dockerd.sh"
WAIT_FOR_DOCKER_SCRIPT_PATH = _MODAL_DIR / "wait_for_docker.sh"


def create_modal_image() -> modal.Image:
    """Create the Modal image with Docker and Claude CLI installed."""
    start_dockerd_content = START_DOCKERD_SCRIPT_PATH.read_text()
    wait_for_docker_content = WAIT_FOR_DOCKER_SCRIPT_PATH.read_text()
    # Base64 encode the scripts to avoid heredoc issues in Modal
    start_dockerd_b64 = base64.b64encode(start_dockerd_content.encode()).decode()
    wait_for_docker_b64 = base64.b64encode(wait_for_docker_content.encode()).decode()

    return (
        modal.Image.debian_slim(python_version="3.11")
        .apt_install(
            "ca-certificates",
            "curl",
            "gnupg",
            "lsb-release",
            "git",
            "vim",
            "iptables",
            "iproute2",
            "wget",
            # Nice-to-have CLI utilities
            "ncdu",
            "less",
            "gawk",
            "mawk",
            "coreutils",  # includes cut, head, tail, etc.
            "findutils",  # find, xargs
            "grep",
            "sed",
            "diffutils",
            "procps",  # ps, top, etc.
            "htop",
            "tree",
            "jq",
            "file",
            "ripgrep",
            "fd-find",
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
            "docker-compose-plugin",
        )
        # Fix runc for Modal/gVisor compatibility
        .run_commands(
            "rm -f $(which runc) || true",
            "wget https://github.com/opencontainers/runc/releases/download/v1.3.0/runc.amd64",
            "chmod +x runc.amd64",
            "mv runc.amd64 /usr/local/bin/runc",
        )
        # Install Node.js (required for devcontainer CLI)
        .run_commands(
            "curl -fsSL https://deb.nodesource.com/setup_20.x | bash -",
        )
        .apt_install("nodejs")
        # Install devcontainer CLI and Claude CLI
        .run_commands("npm install -g @devcontainers/cli @anthropic-ai/claude-code")
        # Add scripts via base64 (heredocs don't work in Modal)
        .run_commands(
            f"echo '{start_dockerd_b64}' | base64 -d > /start-dockerd.sh",
            "chmod 4755 /start-dockerd.sh",
            f"echo '{wait_for_docker_b64}' | base64 -d > /wait_for_docker.sh",
            "chmod +x /wait_for_docker.sh",
        )
        .run_commands(
            "useradd -m -s /bin/bash agent",
            "usermod -aG docker agent",
        )
    )
