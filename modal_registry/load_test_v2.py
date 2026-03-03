"""Load test v2: reproduce Docker Hub rate limiting from a single IP.

Uses a SINGLE Modal sandbox to run sequential devcontainer builds, each
followed by a full Docker prune. The entire build+prune loop runs as one
bash script inside the sandbox (zero Python↔Modal round-trips in the hot
loop), so the only time spent is actual Docker work.

Usage:
    cd modal_registry && uv run python load_test_v2.py [--iterations 50] [--with-cache]

Prerequisites:
    - Modal configured (modal token set)
    - For --with-cache: registry deployed and secret configured (see README.md)
"""

import argparse
import contextlib
import sys
import textwrap

import modal

# ---------------------------------------------------------------------------
# Reuse the keystone Modal image which already has Docker + devcontainer CLI
# ---------------------------------------------------------------------------
sys.path.insert(
    0, str(__import__("pathlib").Path(__file__).resolve().parent.parent / "keystone" / "src")
)
from keystone.modal.image import create_modal_image

DOCKERFILE = textwrap.dedent("""\
    FROM python:3.12-slim
    RUN echo "built"
""")

DEVCONTAINER_JSON = """\
{
  "name": "load-test",
  "build": {
    "dockerfile": "Dockerfile",
    "context": ".."
  }
}
"""

RATE_LIMIT_PHRASES = [
    "429 too many requests",
    "toomanyrequests",
    "rate limit",
    "you have reached your pull rate limit",
    "retry-after",
]


def _exec_script(
    sb: modal.Sandbox,
    script: str,
    *,
    label: str = "cmd",
) -> tuple[int, str]:
    """Execute a bash command/script in the sandbox and return (exit_code, output)."""
    proc = sb.exec("bash", "-c", script)

    output_lines: list[str] = []
    for line in proc.stdout:
        text = line.strip()
        print(f"  [{label}] {text}", file=sys.stderr)
        output_lines.append(text)
    for line in proc.stderr:
        text = line.strip()
        print(f"  [{label}] {text}", file=sys.stderr)
        output_lines.append(text)

    exit_code = proc.wait()
    return exit_code, "\n".join(output_lines)


def _build_loop_script(iterations: int, with_cache: bool) -> str:
    """Generate a bash script that runs the entire build+prune loop.

    The loop runs entirely inside the sandbox so there are no
    Python↔Modal round-trips between iterations.  Each iteration:
      1. devcontainer build (pulls base image from Docker Hub)
      2. docker system prune -af + docker buildx prune -af
    Results are printed as structured lines for parsing.
    """
    if with_cache:
        build_cmd = (
            'CACHE_REF="$DOCKER_BUILD_CACHE_REGISTRY_URL/loadtest-cache:latest"\n'
            "    devcontainer build "
            "--workspace-folder /project "
            "--image-name loadtest:latest "
            '"--cache-from" "type=registry,ref=$CACHE_REF" '
            '"--cache-to" "type=registry,ref=$CACHE_REF,mode=max" '
            "2>&1"
        )
    else:
        build_cmd = (
            "devcontainer build --workspace-folder /project --image-name loadtest:latest 2>&1"
        )

    return textwrap.dedent(f"""\
        #!/bin/bash
        set -uo pipefail

        ITERATIONS={iterations}

        for i in $(seq 1 $ITERATIONS); do
            echo "@@@ ITERATION $i/$ITERATIONS @@@"

            START_NS=$(date +%s%N)
            OUTPUT=$({build_cmd})
            EXIT_CODE=$?
            END_NS=$(date +%s%N)
            ELAPSED_MS=$(( (END_NS - START_NS) / 1000000 ))

            # Check for rate limiting
            RATE_LIMITED=0
            if echo "$OUTPUT" | grep -qiE '429 too many requests|toomanyrequests|rate.limit|pull rate limit|retry-after'; then
                RATE_LIMITED=1
            fi

            echo "@@@ RESULT iter=$i exit=$EXIT_CODE ms=$ELAPSED_MS rate_limited=$RATE_LIMITED @@@"
            if [ "$EXIT_CODE" -ne 0 ]; then
                echo "$OUTPUT" | tail -20 | while IFS= read -r errline; do
                    echo "@@@ ERR $errline"
                done
            fi

            # Prune everything so next iteration must pull fresh
            echo "@@@ PRUNING @@@"
            docker system prune -af --volumes >/dev/null 2>&1
            docker buildx prune -af >/dev/null 2>&1
            echo "@@@ PRUNE_DONE @@@"
        done

        echo "@@@ ALL_DONE @@@"
    """)


def run_load_test(iterations: int, with_cache: bool) -> None:
    """Run sequential devcontainer builds in a single sandbox."""
    modal.enable_output()

    app = modal.App.lookup("keystone-load-test-v2", create_if_missing=True)
    image = create_modal_image()

    secrets: list[modal.Secret] = []
    if with_cache:
        secrets.append(modal.Secret.from_name("keystone-docker-registry-config"))

    print(
        f"Creating Modal sandbox (iterations={iterations}, with_cache={with_cache})...",
        file=sys.stderr,
    )
    sb = modal.Sandbox.create(
        app=app,
        image=image,
        timeout=60 * 60 * 2,  # 2 hours
        region="us-west-2",
        secrets=secrets,
        experimental_options={"enable_docker": True},
    )
    sandbox_id = sb.object_id
    print(f"Sandbox created: {sandbox_id}", file=sys.stderr)
    print(f"  Shell: modal shell {sandbox_id}", file=sys.stderr)

    try:
        # Start Docker daemon
        print("Starting Docker daemon...", file=sys.stderr)
        sb.exec("/start-dockerd.sh")
        exit_code, _ = _exec_script(sb, "/wait_for_docker.sh", label="docker-wait")
        if exit_code != 0:
            raise RuntimeError("Docker daemon failed to start")

        # Docker login for cache registry (if enabled)
        if with_cache:
            print("Logging into cache registry...", file=sys.stderr)
            login_cmd = (
                'echo "$DOCKER_BUILD_CACHE_REGISTRY_PASSWORD" | '
                "docker login "
                '--username "$DOCKER_BUILD_CACHE_REGISTRY_USERNAME" '
                "--password-stdin "
                '"$DOCKER_BUILD_CACHE_REGISTRY_URL"'
            )
            exit_code, _ = _exec_script(sb, login_cmd, label="docker-login")
            if exit_code != 0:
                raise RuntimeError("Docker login failed")

        # Set up project directory
        print("Setting up project...", file=sys.stderr)
        _exec_script(sb, "mkdir -p /project/.devcontainer", label="setup")
        with sb.open("/project/.devcontainer/Dockerfile", "w") as f:
            f.write(DOCKERFILE)
        with sb.open("/project/.devcontainer/devcontainer.json", "w") as f:
            f.write(DEVCONTAINER_JSON)
        with sb.open("/project/README.md", "w") as f:
            f.write("# load test project\n")

        # Run the entire loop as a single bash script inside the sandbox
        print(f"\n{'=' * 60}", file=sys.stderr)
        print(
            f"Running {iterations} sequential build+prune cycles...",
            file=sys.stderr,
        )
        print(f"{'=' * 60}\n", file=sys.stderr)

        loop_script = _build_loop_script(iterations, with_cache)
        with sb.open("/tmp/_load_test_loop.sh", "w") as f:
            f.write(loop_script)

        proc = sb.exec("bash", "/tmp/_load_test_loop.sh")

        # Parse structured output as it streams
        results: list[dict[str, int]] = []
        for line in proc.stdout:
            text = line.strip()
            if text.startswith("@@@ RESULT"):
                # Parse: @@@ RESULT iter=1 exit=0 ms=12345 rate_limited=0 @@@
                parts: dict[str, int] = {}
                for token in text.split():
                    if "=" in token:
                        k, v = token.split("=", 1)
                        with contextlib.suppress(ValueError):
                            parts[k] = int(v)
                results.append(parts)
                rl = parts.get("rate_limited", 0)
                ec = parts.get("exit", -1)
                ms = parts.get("ms", 0)
                status = "RATE LIMITED" if rl else ("OK" if ec == 0 else "FAILED")
                print(
                    f"  [{parts.get('iter', '?'):3}] {status} (exit={ec}, {ms / 1000:.1f}s)",
                    file=sys.stderr,
                )
            elif text.startswith("@@@ ERR"):
                print(f"    {text[8:]}", file=sys.stderr)
            elif text.startswith("@@@ ITERATION"):
                print(f"\n{text.strip('@ ')}", file=sys.stderr)
            elif text.startswith("@@@"):
                pass  # skip markers
            else:
                print(f"  {text}", file=sys.stderr)
        for line in proc.stderr:
            text = line.strip()
            if text:
                print(f"  [stderr] {text}", file=sys.stderr)

        proc.wait()

        # Summary
        print(f"\n{'=' * 60}", file=sys.stderr)
        print("LOAD TEST RESULTS", file=sys.stderr)
        print(f"{'=' * 60}", file=sys.stderr)
        total = len(results)
        rate_limited_count = sum(1 for r in results if r.get("rate_limited"))
        failed_count = sum(1 for r in results if r.get("exit", 1) != 0)
        succeeded = total - failed_count
        print(f"Total iterations:  {total}", file=sys.stderr)
        print(f"Succeeded:         {succeeded}", file=sys.stderr)
        print(f"Rate limited:      {rate_limited_count}", file=sys.stderr)
        print(f"Other failures:    {failed_count - rate_limited_count}", file=sys.stderr)

        if succeeded > 0:
            ok_ms = sorted(r["ms"] for r in results if r.get("exit") == 0)
            print(f"Build time (min):  {ok_ms[0] / 1000:.1f}s", file=sys.stderr)
            print(f"Build time (med):  {ok_ms[len(ok_ms) // 2] / 1000:.1f}s", file=sys.stderr)
            print(f"Build time (max):  {ok_ms[-1] / 1000:.1f}s", file=sys.stderr)

        total_ms = sum(r.get("ms", 0) for r in results)
        print(f"Total build time:  {total_ms / 1000:.1f}s", file=sys.stderr)

        print(file=sys.stderr)
        for r in results:
            rl = r.get("rate_limited", 0)
            ec = r.get("exit", -1)
            ms = r.get("ms", 0)
            flag = " ⚠️  RATE LIMITED" if rl else (" ❌ FAILED" if ec != 0 else " ✅")
            print(
                f"  #{r.get('iter', '?'):3}: exit={ec} time={ms / 1000:6.1f}s{flag}",
                file=sys.stderr,
            )

        if rate_limited_count:
            print(
                f"\n🎯 {rate_limited_count}/{total} builds hit Docker Hub rate limits!",
                file=sys.stderr,
            )
        elif failed_count:
            print(
                f"\n❌ {failed_count}/{total} builds failed (not rate-limited)",
                file=sys.stderr,
            )
        else:
            print(
                "\n✅ All builds succeeded — no rate limiting observed",
                file=sys.stderr,
            )

    finally:
        print("\nTerminating sandbox...", file=sys.stderr)
        sb.terminate()


def main() -> None:
    parser = argparse.ArgumentParser(description="Load test: reproduce Docker Hub rate limiting")
    parser.add_argument(
        "--iterations",
        type=int,
        default=50,
        help="Number of build+prune cycles (default: 50)",
    )
    parser.add_argument(
        "--with-cache",
        action="store_true",
        help="Use the Modal registry cache (to test mitigation)",
    )
    args = parser.parse_args()
    run_load_test(iterations=args.iterations, with_cache=args.with_cache)


if __name__ == "__main__":
    main()
