# Keystone: an agentic tool to configure Dockerfiles for any repo

Keystone automatically generates a working `.devcontainer/` configuration for any project using an AI agent.
Given a source repo, it analyzes the project structure and creates:

- `//devcontainer/devcontainer.json` - VS Code dev container configuration
- `//devcontainer/Dockerfile` - Container image definition
- `//devcontainer/run_all_tests.sh` - Test runner script with artifact collection

## Prerequisite setup

* A [Modal account] (https://modal.com/docs/guide#getting-started) -- we use this to safely sandbox Claude Code as it works on your container.
* `$ANTHROPIC_API_KEY` -- Keystone uses your API key to run Claude Code in its Modal sandbox.
* [`uvx`](https://docs.astral.sh/uv/getting-started/installation/) to run Keystone.

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

Not currently supported:
* Setting up environments for projects that use Docker. (Keystone does not currently work on itself.)

---

## Developer Notes

### Running from source

```bash
# Run local code tree on a project.
uvx run keystone \
  --max_budget_usd 3.0 \
  --test_artifacts_dir /tmp/test_artifacts \
  --project_root ./samples/python_project
```
