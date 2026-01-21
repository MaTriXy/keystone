#!/usr/bin/env python
"""Test script that runs the eval harness on samples/python_project.

This test uses caching to avoid repeated agent runs.

Usage:
    cd eval
    uv run python test_local_worker.py
"""
import os
import sys
import tempfile
from pathlib import Path

from config import AgentConfig
from flow import create_tarball_from_dir, eval_local_tarball_flow


def main():
    # Check for API key
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ERROR: ANTHROPIC_API_KEY environment variable not set")
        sys.exit(1)
    
    # Paths
    samples_dir = Path(__file__).parent.parent / "samples" / "python_project"
    if not samples_dir.exists():
        print(f"ERROR: Sample project not found at {samples_dir}")
        sys.exit(1)
    
    # Create output directory
    output_dir = Path(tempfile.mkdtemp(prefix="eval_test_"))
    print(f"Output directory: {output_dir}")
    
    # Create tarball
    tarball_path = output_dir / "python_project.tar.gz"
    create_tarball_from_dir(samples_dir, tarball_path)
    print(f"Created tarball: {tarball_path}")
    
    # Configure with caching enabled
    agent_config = AgentConfig(
        max_budget_usd=1.0,
        use_cache=True,  # Use cache to avoid re-running agent
        timeout_minutes=30,
    )
    
    print(f"Agent config: {agent_config}")
    print("\nRunning eval flow...")
    
    # Run the flow
    result = eval_local_tarball_flow(
        tarball_path=str(tarball_path),
        agent_config=agent_config,
        output_dir=str(output_dir / "result"),
    )
    
    # Print results
    print("\n" + "=" * 60)
    if result.success:
        print("✅ SUCCESS")
        if result.bootstrap_result:
            print(f"\nBootstrap result:")
            for key, value in result.bootstrap_result.items():
                print(f"  {key}: {value}")
    else:
        print("❌ FAILED")
        print(f"Error: {result.error_message}")
    
    print(f"\nOutputs written to: {output_dir}")
    
    # List output files
    result_dir = output_dir / "result"
    if result_dir.exists():
        print("\nOutput files:")
        for f in sorted(result_dir.iterdir()):
            size = f.stat().st_size
            print(f"  {f.name} ({size} bytes)")
    
    return 0 if result.success else 1


if __name__ == "__main__":
    sys.exit(main())
