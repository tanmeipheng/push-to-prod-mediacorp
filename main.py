"""
TFAH Main — Entry point for the Transient Fault Auto-Healer.

Usage:
    # Full flow: crash mock server → capture → classify → fix → PR → notify
    python main.py

    # Skip crash capture, feed a log file directly:
    python main.py --log /path/to/crash.log
"""

import argparse
import os
import sys

from dotenv import load_dotenv

load_dotenv()


def main():
    parser = argparse.ArgumentParser(description="Transient Fault Auto-Healer")
    parser.add_argument(
        "--log",
        type=str,
        default=None,
        help="Path to a crash log file. If omitted, runs the vulnerable worker to generate one.",
    )
    parser.add_argument(
        "--source",
        type=str,
        default=None,
        help="Path to the vulnerable source file. Defaults to vulnerable_app/integration.py.",
    )
    args = parser.parse_args()

    # ── Step 1: Get the crash log ─────────────────────────────
    if args.log:
        with open(args.log, "r") as f:
            crash_log = f.read()
        print(f"📄 Loaded crash log from {args.log}")
    else:
        print("💥 Running vulnerable worker against mock server…")
        from crash_runner.run_and_capture import run_and_capture
        crash_log = run_and_capture()

    if not crash_log.strip():
        print("❌ No crash output captured. Is the mock server running?")
        print("   Start it with:  python mock_server/server.py")
        sys.exit(1)

    print("\n" + "=" * 60)
    print("CAPTURED CRASH LOG:")
    print("=" * 60)
    print(crash_log)
    print("=" * 60)

    # ── Step 2: Read the vulnerable source ────────────────────
    source_path = args.source or os.path.join(
        os.path.dirname(__file__), "vulnerable_app", "integration.py"
    )
    source_path = os.path.abspath(source_path)

    with open(source_path, "r") as f:
        source_code = f.read()

    print(f"\n📂 Source file: {source_path}")

    # ── Step 3: Run the LangGraph pipeline ────────────────────
    print("\n🚀 Starting TFAH Agent Pipeline…\n")
    from agent.pipeline import run_pipeline

    final_state = run_pipeline(
        crash_log=crash_log,
        source_code=source_code,
        source_file_path="vulnerable_app/integration.py",
    )

    # ── Step 4: Summary ───────────────────────────────────────
    print("\n" + "=" * 60)
    print("✅ TFAH Pipeline Complete!")
    print("=" * 60)
    print(f"   Fault Type  : {final_state.get('fault_type', 'N/A')}")
    print(f"   Action      : {final_state.get('action', 'N/A')}")
    print(f"   Confidence  : {final_state.get('confidence', 'N/A')}")
    print(f"   Status      : {final_state.get('pipeline_status', 'N/A')}")
    print(f"   Jira Issue  : {final_state.get('jira_issue_key', 'N/A')}")
    print(f"   Jira Status : {final_state.get('jira_status', 'N/A')}")
    print(f"   PR URL      : {final_state.get('pr_url', 'N/A')}")
    print(f"   Slack Steps : {', '.join(final_state.get('notifications_sent', [])) or 'N/A'}")
    print(f"   Notified    : {final_state.get('notified', False)}")


if __name__ == "__main__":
    main()
