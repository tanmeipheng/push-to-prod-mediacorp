"""
Crash Runner — Executes a vulnerable worker against the mock server
and captures the stderr traceback for the agent pipeline.
"""

import subprocess
import sys
import os


# ── Scenario registry ────────────────────────────────────────
# Maps short names to (script_path, source_file_path) pairs.
SCENARIOS = {
    "429": ("vulnerable_app/integration.py", "vulnerable_app/integration.py"),
    "503": ("vulnerable_app/service_down.py", "vulnerable_app/service_down.py"),
    "504": ("vulnerable_app/gateway_timeout.py", "vulnerable_app/gateway_timeout.py"),
    "timeout": ("vulnerable_app/connection_timeout.py", "vulnerable_app/connection_timeout.py"),
    "deadlock": ("vulnerable_app/db_deadlock.py", "vulnerable_app/db_deadlock.py"),
}

DEFAULT_SCENARIO = "429"


def run_and_capture(script: str | None = None) -> str:
    """
    Run a vulnerable worker script and capture stdout+stderr.

    Args:
        script: Absolute or project-relative path to the script.
                Defaults to vulnerable_app/integration.py.

    Returns the combined output as a string (the crash traceback).
    """
    if script is None:
        script = os.path.join(
            os.path.dirname(__file__), "..", "vulnerable_app", "integration.py"
        )
    elif not os.path.isabs(script):
        script = os.path.join(os.path.dirname(__file__), "..", script)

    script = os.path.abspath(script)

    result = subprocess.run(
        [sys.executable, script],
        capture_output=True,
        text=True,
        timeout=30,
    )

    output = ""
    if result.stdout:
        output += result.stdout
    if result.stderr:
        output += result.stderr

    return output


if __name__ == "__main__":
    crash_output = run_and_capture()
    print("=== CAPTURED CRASH LOG ===")
    print(crash_output)
