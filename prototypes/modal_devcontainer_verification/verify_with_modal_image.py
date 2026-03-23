#!/usr/bin/env python3
"""
Prototype: Use modal.Image.from_dockerfile for verification.

This bypasses Docker-in-Docker and leverages Modal's native image caching.
"""

import time
from pathlib import Path

import modal

# Path to the sample project (relative to this file)
SAMPLE_PROJECT = Path(__file__).parent / "node_project"


def run_verification():
    """Build and verify using Modal's from_dockerfile."""

    dockerfile_path = SAMPLE_PROJECT / ".devcontainer" / "Dockerfile"

    print(f"Building image from: {dockerfile_path}")
    print(f"Context: {SAMPLE_PROJECT}")

    start = time.time()

    # Create Modal image from the Dockerfile
    # Modal caches this across runs!
    image = modal.Image.from_dockerfile(
        path=dockerfile_path,
        context_dir=SAMPLE_PROJECT,
    )

    build_time = time.time() - start
    print(f"Image definition created in {build_time:.2f}s")

    # Create app and run verification
    app = modal.App.lookup("modal-dockerfile-verify-prototype", create_if_missing=True)

    start = time.time()

    with modal.enable_output():
        sandbox = modal.Sandbox.create(
            app=app,
            image=image,
            timeout=300,
        )

        # Run the test script
        print("\n--- Running tests ---")
        proc = sandbox.exec("bash", "/project_src/.devcontainer/run_all_tests.sh")

        for line in proc.stdout:
            print(f"[stdout] {line}", end="")
        for line in proc.stderr:
            print(f"[stderr] {line}", end="")

        proc.wait()
        print(f"\n--- Tests completed with exit code: {proc.returncode} ---")

        sandbox.terminate()

    verify_time = time.time() - start
    print(f"\nVerification completed in {verify_time:.2f}s")

    return proc.returncode


if __name__ == "__main__":
    exit_code = run_verification()
    exit(exit_code)
