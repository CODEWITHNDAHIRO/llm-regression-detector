"""
Phase 4 step 2: posts eval run diffs to a Discord
channel via webhook. Mirrors slack_alert.py's structure and purpose, but
uses Discord's "embed" JSON format instead of Slack's Block Kit.
"""
import json
import os
import sys
from pathlib import Path
import requests
from dotenv import load_dotenv

from diff_runs import RunDiff, compare_runs, find_latest_run_for_version

load_dotenv()

# Discord embed colors are decimal integers, not hex strings.
# These correspond to green / amber / red.
SEVERITY_COLOR = {"none": 3066993, "warning": 15105570, "critical": 15158332}
SEVERITY_EMOJI = {"none": "✅", "warning": "⚠️", "critical": "🚨"}


def build_discord_payload(diff: RunDiff, report_path: Path) -> dict:
    """Builds a Discord webhook payload (an 'embed') summarizing the diff."""
    emoji = SEVERITY_EMOJI[diff.severity]

    regressed_text = (
        "\n".join(f"• `{c}`" for c in diff.regressed_cases)
        if diff.regressed_cases
        else "_none_"
    )

    embed = {
        "title": f"{emoji} Eval {diff.severity.upper()}: {diff.baseline_prompt_version} → {diff.candidate_prompt_version}",
        "color": SEVERITY_COLOR[diff.severity],
        "fields": [
            {
                "name": "Category pass rate",
                "value": f"{diff.baseline_pass_rate:.0%} → {diff.candidate_pass_rate:.0%} "
                         f"({diff.pass_rate_delta:+.0%})",
                "inline": True,
            },
            {
                "name": "Avg summary score",
                "value": f"{diff.baseline_avg_summary_score:.2f} → {diff.candidate_avg_summary_score:.2f} "
                         f"({diff.summary_score_delta:+.2f})",
                "inline": True,
            },
            {
                "name": f"Regressed cases ({len(diff.regressed_cases)})",
                "value": regressed_text,
                "inline": False,
            },
            {
                "name": "Full report",
                "value": f"`{report_path}`",
                "inline": False,
            },
        ],
    }

    return {"embeds": [embed]}


def send_discord_alert(diff: RunDiff, report_path: Path, dry_run: bool = False) -> None:
    payload = build_discord_payload(diff, report_path)

    if dry_run:
        print("[DRY RUN] Would send this payload to Discord:\n")
        print(json.dumps(payload, indent=2))
        return

    webhook_url = os.environ.get("DISCORD_WEBHOOK_URL")
    if not webhook_url or webhook_url == "your-webhook-url-here":
        raise RuntimeError(
            "DISCORD_WEBHOOK_URL is not set in .env. Run with --dry-run to test "
            "without a real webhook, or add a real URL to send for real."
        )

    response = requests.post(webhook_url, json=payload, timeout=10)
    response.raise_for_status()
    print(f"Discord alert sent (status {response.status_code}).")


if __name__ == "__main__":
    # Usage: python src/discord_alert.py v1 v2 [--dry-run]
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    dry_run = "--dry-run" in sys.argv

    baseline_version = args[0] if len(args) > 0 else "v1"
    candidate_version = args[1] if len(args) > 1 else "v2"

    baseline_path = find_latest_run_for_version(baseline_version)
    candidate_path = find_latest_run_for_version(candidate_version)
    diff = compare_runs(baseline_path, candidate_path)

    send_discord_alert(diff, report_path=Path("reports/<latest report>.html"), dry_run=dry_run)