import modal

from bootstrap_devcontainer.modal_runner import create_modal_image, run_modal_command


def test_run_modal_command_interleaved_streaming():
    """
    Verify that run_modal_command correctly handles interleaved stdout/stderr.
    This uses a real Modal sandbox.
    """
    print("Connecting to Modal...")
    app = modal.App.lookup("bootstrap-devcontainer-test", create_if_missing=True)
    image = create_modal_image()

    sb = modal.Sandbox.create(app=app, image=image, timeout=300)
    try:
        print(f"Sandbox created: {sb.object_id}")

        # Command that produces interleaved output on stdout/stderr
        bash_script = """
        for i in $(seq 1 6); do
          if (( i % 2 == 0 )); then
            echo "OUT: $i"
          else
            echo "ERR: $i" >&2
          fi
          sleep 0.1
        done
        """

        print("\nExecuting command...")
        events = list(run_modal_command(sb, "bash", "-c", bash_script, pty=False))

        # Print events for inspection
        print("\nCaptured events:")
        for e in events:
            print(f"[{e.stream}] {e.line}")

        # Check that we got the interleaved output
        stdout_lines = [e.line for e in events if e.stream == "stdout" and "OUT:" in e.line]
        stderr_lines = [e.line for e in events if e.stream == "stderr" and "ERR:" in e.line]

        print(f"\nFound {len(stdout_lines)} stdout lines and {len(stderr_lines)} stderr lines.")

        assert len(stdout_lines) == 3, f"Expected 3 stdout lines, found {len(stdout_lines)}"
        assert len(stderr_lines) == 3, f"Expected 3 stderr lines, found {len(stderr_lines)}"

        # Verify interleaving order roughly
        sequence_lines = [e.line for e in events if "OUT:" in e.line or "ERR:" in e.line]
        expected = ["ERR: 1", "OUT: 2", "ERR: 3", "OUT: 4", "ERR: 5", "OUT: 6"]
        assert sequence_lines == expected, (
            f"Order mismatch. Expected {expected}, got {sequence_lines}"
        )
    finally:
        sb.terminate()


if __name__ == "__main__":
    test_run_modal_command_interleaved_streaming()
