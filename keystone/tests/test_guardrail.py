"""Tests for the guardrail.sh validation script."""

import shutil
import subprocess
from pathlib import Path

import pytest
from conftest import SAMPLES_DIR, init_git_repo


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    """Create a workspace with a sample project for guardrail testing."""
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    # Copy a minimal Python project
    shutil.copytree(SAMPLES_DIR / "python_project", project_dir, dirs_exist_ok=True)
    init_git_repo(project_dir)

    # Copy guardrail.sh into the workspace (as the runners would)
    guardrail_src = Path(__file__).parent.parent / "src" / "keystone" / "guardrail.sh"
    guardrail_dst = project_dir / "guardrail.sh"
    guardrail_dst.write_bytes(guardrail_src.read_bytes())
    guardrail_dst.chmod(0o755)

    return project_dir


def _run_guardrail(workspace: Path) -> subprocess.CompletedProcess[str]:
    """Run guardrail.sh in the given workspace."""
    return subprocess.run(
        ["bash", str(workspace / "guardrail.sh")],
        cwd=workspace,
        capture_output=True,
        text=True,
    )


def test_guardrail_fails_with_no_devcontainer(workspace: Path) -> None:
    """Guardrail should fail when no .devcontainer directory exists."""
    result = _run_guardrail(workspace)
    assert result.returncode != 0
    assert "FAIL" in result.stdout
    assert ".devcontainer/ directory is MISSING" in result.stdout


def test_guardrail_fails_with_missing_dockerfile(workspace: Path) -> None:
    """Guardrail should fail when Dockerfile is missing."""
    devcontainer_dir = workspace / ".devcontainer"
    devcontainer_dir.mkdir()
    (devcontainer_dir / "devcontainer.json").write_text('{"build": {}}')
    (devcontainer_dir / "run_all_tests.sh").write_text(
        "#!/bin/bash\nmkdir -p /test_artifacts/junit\necho '{\"success\": true}' > /test_artifacts/final_result.json\n"
    )
    (devcontainer_dir / "run_all_tests.sh").chmod(0o755)

    result = _run_guardrail(workspace)
    assert result.returncode != 0
    assert "Dockerfile is MISSING" in result.stdout


def test_guardrail_fails_with_missing_run_all_tests(workspace: Path) -> None:
    """Guardrail should fail when run_all_tests.sh is missing."""
    devcontainer_dir = workspace / ".devcontainer"
    devcontainer_dir.mkdir()
    (devcontainer_dir / "devcontainer.json").write_text('{"build": {}}')
    (devcontainer_dir / "Dockerfile").write_text(
        "FROM python:3.12\nRUN mkdir -p /test_artifacts && chmod 777 /test_artifacts\nCOPY .devcontainer/run_all_tests.sh /run_all_tests.sh\nRUN chmod +x /run_all_tests.sh\n"
    )

    result = _run_guardrail(workspace)
    assert result.returncode != 0
    assert "run_all_tests.sh is MISSING" in result.stdout


def test_guardrail_checks_dockerfile_structure(workspace: Path) -> None:
    """Guardrail should pass file checks even with a minimal Dockerfile, then fail at Docker build."""
    devcontainer_dir = workspace / ".devcontainer"
    devcontainer_dir.mkdir()
    (devcontainer_dir / "devcontainer.json").write_text('{"build": {}}')
    # Dockerfile with minimal content - file exists but build would fail
    (devcontainer_dir / "Dockerfile").write_text("# empty dockerfile\n")
    run_script = devcontainer_dir / "run_all_tests.sh"
    run_script.write_text(
        "#!/bin/bash\nmkdir -p /test_artifacts/junit\necho '{\"success\": true}' > /test_artifacts/final_result.json\n"
    )
    run_script.chmod(0o755)

    result = _run_guardrail(workspace)
    assert result.returncode != 0
    # File existence checks pass
    assert "PASS: .devcontainer/Dockerfile exists" in result.stdout
    assert "PASS: .devcontainer/run_all_tests.sh exists" in result.stdout
    # Docker build fails (no clean project copy in test environment)
    assert "FAIL" in result.stdout


def test_guardrail_checks_run_all_tests_structure(workspace: Path) -> None:
    """Guardrail should pass file checks even with minimal run_all_tests.sh, then fail at Docker build."""
    devcontainer_dir = workspace / ".devcontainer"
    devcontainer_dir.mkdir()
    (devcontainer_dir / "devcontainer.json").write_text('{"build": {}}')
    (devcontainer_dir / "Dockerfile").write_text(
        "FROM python:3.12\nRUN mkdir -p /test_artifacts && chmod 777 /test_artifacts\nCOPY .devcontainer/run_all_tests.sh /run_all_tests.sh\nRUN chmod +x /run_all_tests.sh\n"
    )
    # run_all_tests.sh with minimal content
    run_script = devcontainer_dir / "run_all_tests.sh"
    run_script.write_text("echo 'hello'\n")
    run_script.chmod(0o755)

    result = _run_guardrail(workspace)
    assert result.returncode != 0
    # File existence checks pass
    assert "PASS: .devcontainer/run_all_tests.sh exists" in result.stdout
    # Docker build fails (no clean project copy in test environment)
    assert "FAIL" in result.stdout


def test_guardrail_passes_with_valid_files(workspace: Path) -> None:
    """Guardrail should pass all file existence checks with properly structured files."""
    devcontainer_dir = workspace / ".devcontainer"
    devcontainer_dir.mkdir()
    (devcontainer_dir / "devcontainer.json").write_text(
        '{"build": {"dockerfile": "Dockerfile", "context": ".."}}'
    )
    (devcontainer_dir / "Dockerfile").write_text(
        "FROM python:3.12-slim\n"
        "WORKDIR /project_src\n"
        "RUN mkdir -p /test_artifacts && chmod 777 /test_artifacts\n"
        "COPY pyproject.toml ./\n"
        "COPY .devcontainer/run_all_tests.sh /run_all_tests.sh\n"
        "RUN chmod +x /run_all_tests.sh\n"
    )
    run_script = devcontainer_dir / "run_all_tests.sh"
    run_script.write_text(
        "#!/bin/bash\n"
        "set -euo pipefail\n"
        "mkdir -p /test_artifacts/junit\n"
        "pytest --junitxml=/test_artifacts/junit/pytest.xml\n"
        "echo '{\"success\": true}' > /test_artifacts/final_result.json\n"
    )
    run_script.chmod(0o755)

    result = _run_guardrail(workspace)
    # File existence checks should all pass (Docker build will fail since
    # we don't have a clean project copy, but the file checks pass)
    assert "PASS: .devcontainer/ directory exists" in result.stdout
    assert "PASS: .devcontainer/devcontainer.json exists" in result.stdout
    assert "PASS: .devcontainer/Dockerfile exists" in result.stdout
    assert "PASS: .devcontainer/run_all_tests.sh exists" in result.stdout
    assert "PASS: .devcontainer/run_all_tests.sh is executable" in result.stdout


def test_guardrail_fails_without_clean_copy(workspace: Path) -> None:
    """Guardrail should fail at Docker build step when no clean project copy exists."""
    devcontainer_dir = workspace / ".devcontainer"
    devcontainer_dir.mkdir()
    (devcontainer_dir / "devcontainer.json").write_text('{"build": {}}')
    (devcontainer_dir / "Dockerfile").write_text(
        "FROM python:3.12\n"
        "WORKDIR /project_src\n"
        "RUN mkdir -p /test_artifacts && chmod 777 /test_artifacts\n"
        "COPY .devcontainer/run_all_tests.sh /run_all_tests.sh\n"
        "RUN chmod +x /run_all_tests.sh\n"
    )
    run_script = devcontainer_dir / "run_all_tests.sh"
    run_script.write_text(
        "#!/bin/bash\nmkdir -p /test_artifacts/junit\necho '{\"success\": true}' > /test_artifacts/final_result.json\n"
    )
    run_script.chmod(0o755)

    result = _run_guardrail(workspace)
    assert result.returncode != 0
    # File checks pass but Docker build fails (no clean copy)
    assert "PASS: .devcontainer/Dockerfile exists" in result.stdout
    assert "No clean project copy found" in result.stdout


def test_guardrail_checks_executable_permission(workspace: Path) -> None:
    """Guardrail should fail if run_all_tests.sh is not executable."""
    devcontainer_dir = workspace / ".devcontainer"
    devcontainer_dir.mkdir()
    (devcontainer_dir / "devcontainer.json").write_text('{"build": {}}')
    (devcontainer_dir / "Dockerfile").write_text(
        "FROM python:3.12\nRUN mkdir -p /test_artifacts && chmod 777 /test_artifacts\nCOPY .devcontainer/run_all_tests.sh /run_all_tests.sh\nRUN chmod +x /run_all_tests.sh\n"
    )
    run_script = devcontainer_dir / "run_all_tests.sh"
    run_script.write_text(
        "#!/bin/bash\nmkdir -p /test_artifacts/junit\necho '{\"success\": true}' > /test_artifacts/final_result.json\n"
    )
    # Intentionally NOT making it executable
    run_script.chmod(0o644)

    result = _run_guardrail(workspace)
    assert result.returncode != 0
    assert "NOT executable" in result.stdout
