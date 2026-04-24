"""
Slack Webhook Notifier — Posts triage alerts to a Slack channel.
"""

import os
import httpx


def send_triage_alert(
    fault_type: str,
    action: str,
    confidence: float,
    summary: str,
    pr_url: str = "pending",
) -> None:
    """Post a structured incident triage message to Slack."""
    webhook_url = os.environ.get("SLACK_WEBHOOK_URL", "")
    if not webhook_url:
        print("   ⚠️  SLACK_WEBHOOK_URL not set — skipping notification.")
        return

    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": "🚨 TFAH Incident Detected"},
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Fault Type:*\n`{fault_type}`"},
                {"type": "mrkdwn", "text": f"*Action:*\n`{action}`"},
                {"type": "mrkdwn", "text": f"*Confidence:*\n`{confidence:.0%}`"},
                {"type": "mrkdwn", "text": f"*Status:*\n🔧 Auto-remediated"},
            ],
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Summary:* {summary}"},
        },
        {"type": "divider"},
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"📎 *Pull Request:* {pr_url}"},
        },
    ]

    payload = {"blocks": blocks, "text": f"TFAH Alert: {fault_type}"}

    resp = httpx.post(webhook_url, json=payload, timeout=10)
    resp.raise_for_status()
