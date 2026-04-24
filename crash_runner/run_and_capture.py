"""
Crash Runner — Executes the vulnerable worker against the mock server
and captures the stderr traceback for the agent pipeline.
"""

import subprocess
import sys
import os


def run_and_capture() -> str:
    """
    Run vulnerable_app/integration.py and capture stdout+stderr.
    Returns the combined output as a string (the crash traceback).
    """
    script_path = os.path.join(
        os.path.dirname(__file__), "..", "vulnerable_app", "integration.py"
    )
    script_path = os.path.abspath(script_path)

    result = subprocess.run(
        [sys.executable, script_path],
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
