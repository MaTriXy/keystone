import subprocess
import json
import logging
import os
import shutil
import threading
import pytest
from pathlib import Path

logger = logging.getLogger(__name__)


def test_cli_help():
    result = subprocess.run(
        ["python3", "bootstrap_devcontainer.py", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "bootstrap_devcontainer.py [OPTIONS] PROJECT_ROOT" in result.stdout


def _stream_reader(stream, lines_list, log_prefix):
    """Read lines from stream and log them in real-time."""
    for line in stream:
        line = line.rstrip('\n')
        logger.info("%s: %s", log_prefix, line)
        lines_list.append(line)


@pytest.mark.manual
def test_e2e_sample_project(tmp_path):
    # Copy sample project to tmp_path to avoid modifying the original source tree
    original_project_root = Path("samples/python_project").resolve()
    project_root = tmp_path / "project"
    shutil.copytree(original_project_root, project_root)

    scratch_dir = tmp_path / "scratch"

    logger.info("=" * 60)
    logger.info("E2E Test Starting")
    logger.info("Project root: %s", project_root)
    logger.info("Scratch dir: %s", scratch_dir)
    logger.info("=" * 60)

    # Use -u for unbuffered Python output
    cmd = [
        "python3", "-u",
        "bootstrap_devcontainer.py",
        str(project_root),
        "--scratch-dir",
        str(scratch_dir),
    ]

    logger.info("Running: %s", ' '.join(cmd))

    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
        env=env,
    )

    stdout_lines = []
    stderr_lines = []

    # Spin up threads to read both streams concurrently
    stdout_thread = threading.Thread(
        target=_stream_reader,
        args=(process.stdout, stdout_lines, "STDOUT"),
    )
    stderr_thread = threading.Thread(
        target=_stream_reader,
        args=(process.stderr, stderr_lines, "STDERR"),
    )

    stdout_thread.start()
    stderr_thread.start()

    stdout_thread.join()
    stderr_thread.join()
    process.wait()

    # Create a result-like object for compatibility
    class Result:
        def __init__(self, returncode, stdout, stderr):
            self.returncode = returncode
            self.stdout = stdout
            self.stderr = stderr

    result = Result(
        process.returncode,
        '\n'.join(stdout_lines),
        '\n'.join(stderr_lines),
    )

    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert "success" in output
    assert "total_time" in output
    assert "token_spending" in output

    # Check if .devcontainer was created
    assert (project_root / ".devcontainer" / "devcontainer.json").exists()
    assert (project_root / ".devcontainer" / "Dockerfile").exists()
    assert (project_root / ".devcontainer" / "run_all_tests.sh").exists()
