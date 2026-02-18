# Keystone: a managed agent to configure Dockerfiles for any repo

Keystone is an open source agentic tool that automatically generates a working `.devcontainer/` configuration for any git code repository. We built it because we kept running into the same problem: *what's the shortest path to make this arbitrary code actually run?*

Given a source repo, Keystone analyzes the project structure and creates:

- `.devcontainer/devcontainer.json` — VS Code dev container configuration
- `.devcontainer/Dockerfile` — Container image definition
- `.devcontainer/run_all_tests.sh` — Test runner script with artifact collection

Keystone builds on the existing [dev container standard](https://containers.dev/), which is also supported by [VS Code](https://code.visualstudio.com/docs/devcontainers/containers) and [GitHub Codespaces](https://github.com/features/codespaces).

## Why bother?

There are several good reasons to configure a standardized container environment for a code repo:

- Have the repo self-describe a suitable execution environment
- Use reproducible environments across development and CI/CD
- Run coding agents safely inside containers

## How to use it

1. Create a [Modal account](https://modal.com/docs/guide#getting-started) and sign in
2. Create or clone a git repository
3. Run Keystone on it
4. Check in the resulting `.devcontainer/` directory

## How it works

Keystone creates a short-lived Modal sandbox and copies your repo into it so that it can run Claude Code safely, without interfering with your local environment. The sandbox is specially configured to allow Claude to run `devcontainer build` and `docker run` commands. The agent works to create an environment suitable for the project and tries to get the project's automated tests passing in that environment.

## Why not just use plain Claude Code?

Iterating on a containerized environment is a bit trickier than writing ordinary code. Although Claude Code can run `docker build` and `docker run` to iterate on a Dockerfile, doing so requires full access to your Docker daemon. In practice, we've observed Claude attempting potentially dangerous changes to the host system — clearing Docker configuration, changing kernel settings, and so on.

In short: containerization is especially important for safety when your agent is acting like a sysadmin.

## Prerequisites

- A [Modal account](https://modal.com/docs/guide#getting-started) — used to safely sandbox Claude Code as it works on your container
- `$ANTHROPIC_API_KEY` — Keystone uses your API key to run Claude Code inside the Modal sandbox
- [`uvx`](https://docs.astral.sh/uv/getting-started/installation/) to run Keystone


## Example usage

Run directly from the repository using `uvx`:

```bash
# Make a repo.
git clone https://github.com/fastapi/fastapi

# Make a devcontainer for it.
uvx --from 'git+https://github.com/imbue-ai/keystone@prod' \
  keystone \
  --max_budget_usd 1.0 \
  --test_artifacts_dir /tmp/test_artifacts \
  --project_root ./fastapi
```

---

## Developer Notes

### Running from source

```bash
# Run local code tree on a project.
uv run keystone \
  --log_db ~/.imbue_keystone/log.sqlite \
  --max_budget_usd 3.0 \
  --test_artifacts_dir /tmp/test_artifacts \
  --project_root ./samples/python_project
```

## Feedback welcome

Bug reports and PRs are welcome. If you're interested in this space, feel free to reach out.
