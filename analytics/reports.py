"""Reports — generate analytics summaries and export data.

Provides reporting on non-followers analysis and automation activity history.
Future: integrate with PyWebUI for local machine dashboard.
"""

import json
from pathlib import Path
from datetime import datetime
from collections import Counter

from config import settings


def action_history_report(log_path: Path | None = None) -> dict:
    """
    Generate a report from the action log.

    Returns:
        Dict with action counts, recent activity, and trends.
    """
    _log = log_path or settings.LOG_PATH

    if not _log.exists():
        return {"total_actions": 0, "message": "No action history found."}

    try:
        data = json.loads(_log.read_text())
    except json.JSONDecodeError:
        return {"total_actions": 0, "message": "Action log is corrupted."}

    rate_log = data.get("rate_log", {})

    report = {
        "summary": {},
        "generated_at": datetime.now().isoformat(),
    }

    for action_type, timestamps in rate_log.items():
        report["summary"][action_type] = {
            "total": len(timestamps),
            "last_action": (
                datetime.fromtimestamp(max(timestamps)).isoformat()
                if timestamps else None
            ),
        }

    return report


def print_action_report(log_path: Path | None = None):
    """Print a formatted action history report."""
    report = action_history_report(log_path)

    print("\n" + "=" * 50)
    print("  AUTOMATION ACTIVITY REPORT")
    print("=" * 50)

    if report.get("message"):
        print(f"  {report['message']}")
        return

    for action, info in report.get("summary", {}).items():
        last = info["last_action"][:16] if info["last_action"] else "never"
        print(f"  {action:<15} {info['total']:>5} total    (last: {last})")

    print("=" * 50 + "\n")


def queue_status_report():
    """Print the current state of the task queue."""
    if not settings.TASK_QUEUE_PATH.exists():
        print("[report] No task queue found. Run analytics first.")
        return

    try:
        queue = json.loads(settings.TASK_QUEUE_PATH.read_text())
    except json.JSONDecodeError:
        print("[report] Task queue file is corrupted.")
        return

    pending_unfollow = len(queue.get("unfollow", []))
    pending_follow = len(queue.get("follow", []))
    done_unfollow = len(queue.get("completed", {}).get("unfollow", []))
    done_follow = len(queue.get("completed", {}).get("follow", []))

    print("\n" + "=" * 50)
    print("  TASK QUEUE STATUS")
    print("=" * 50)
    print(f"  Unfollow:  {pending_unfollow:>5} pending  /  {done_unfollow:>5} completed")
    print(f"  Follow:    {pending_follow:>5} pending  /  {done_follow:>5} completed")
    print("=" * 50)

    generated = queue.get("generated_at", "unknown")
    print(f"  Queue generated: {generated}")
    print()


def export_non_followers_csv(
    analysis: dict,
    output_path: str | Path | None = None,
) -> Path:
    """
    Export non-followers list to CSV for external use.

    Args:
        analysis: Output from compute_non_followers().
        output_path: CSV file path. Defaults to data/non_followers.csv.

    Returns:
        Path to the generated CSV file.
    """
    _output = Path(output_path) if output_path else settings.DATA_DIR / "non_followers.csv"

    lines = ["username,followed_at,url"]
    for user in analysis["non_followers"]:
        lines.append(
            f"{user['username']},{user.get('followed_at', '')},{user.get('url', '')}"
        )

    _output.write_text("\n".join(lines))
    print(f"[report] Exported {len(analysis['non_followers'])} non-followers to {_output}")
    return _output
