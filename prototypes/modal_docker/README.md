# Modal Docker Sandbox Prototype

Prototype for running Docker builds in a Modal sandbox with SSH-like access.

## Setup

```bash
# Install modal if needed
uv add modal

# Authenticate with Modal
modal setup
```

## Usage

### Option 1: Interactive Sandbox (Recommended)

```bash
cd prototypes/modal_docker
uv run python sandbox_ssh.py
```

This creates a sandbox and gives you commands to:
- `modal sandbox exec <id> bash` - Get a shell
- `modal sandbox exec <id> docker build .` - Run docker commands

### Option 2: Function-based Test

```bash
uv run modal run modal_docker_sandbox.py
```

This runs a quick test to verify Docker works.

## Important Notes

- **Docker-in-Docker requires privileged mode** - Modal may have restrictions on this
- The sandbox approach uses `modal sandbox exec` for shell access (not true SSH)
- Sandboxes have a 1-hour timeout by default

## Files

- `sandbox_ssh.py` - Creates an interactive sandbox with Docker
- `modal_docker_sandbox.py` - Function-based Docker test
