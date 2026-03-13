"""Non-followers analysis.

Computes the diff between following and followers lists
to identify accounts that don't follow you back.
Supports a whitelist and generates task queue for automation.
"""

import json
from pathlib import Path
from datetime import datetime

from config import settings
from analytics.extractor import load_export


def compute_non_followers(
    export_path: str | Path,
    whitelist: list[str] | None = None,
) -> dict:
    """
    Compute non-followers from an Instagram data export.

    non_followers = following - followers
    (people you follow who don't follow you back)

    Args:
        export_path: Path to the Instagram export folder.
        whitelist: Usernames to never unfollow (celebrities, brands, friends, etc.)

    Returns:
        Dict with analysis results:
        - non_followers: list of usernames not following back
        - mutual: list of mutual follow usernames
        - fans: list of followers you don't follow back
        - stats: summary counts
    """
    export = load_export(export_path)

    followers_set = {u["username"].lower() for u in export["followers"]}
    following_set = {u["username"].lower() for u in export["following"]}

    # Build lookup dicts (preserve original casing)
    followers_map = {u["username"].lower(): u for u in export["followers"]}
    following_map = {u["username"].lower(): u for u in export["following"]}

    # Whitelist (case-insensitive)
    _whitelist = {w.lower() for w in (whitelist or [])}

    # Core calculations
    non_followers_raw = following_set - followers_set
    non_followers = non_followers_raw - _whitelist
    mutual = followers_set & following_set
    fans = followers_set - following_set  # Follow you but you don't follow back

    # Build detailed non-followers list with metadata
    non_followers_detail = []
    for username in sorted(non_followers):
        info = following_map.get(username, {})
        non_followers_detail.append({
            "username": info.get("username", username),  # Original casing
            "followed_at": info.get("followed_at"),
            "url": info.get("url", f"https://www.instagram.com/{username}/"),
        })

    # Sort by follow date (oldest first — you've been following them longest)
    non_followers_detail.sort(key=lambda x: x.get("followed_at") or "9999")

    result = {
        "non_followers": non_followers_detail,
        "mutual_count": len(mutual),
        "fans_count": len(fans),
        "whitelisted_non_followers": len(non_followers_raw & _whitelist),
        "stats": {
            "total_followers": len(followers_set),
            "total_following": len(following_set),
            "non_followers": len(non_followers),
            "mutual": len(mutual),
            "fans": len(fans),
            "whitelisted": len(non_followers_raw & _whitelist),
        },
        "computed_at": datetime.now().isoformat(),
    }

    return result


def print_report(analysis: dict):
    """Print a formatted report of the non-followers analysis."""
    stats = analysis["stats"]

    print("\n" + "=" * 50)
    print("  INSTAGRAM NON-FOLLOWERS REPORT")
    print("=" * 50)
    print(f"  Followers:      {stats['total_followers']:>6}")
    print(f"  Following:      {stats['total_following']:>6}")
    print(f"  ─────────────────────────")
    print(f"  Mutual:         {stats['mutual']:>6}")
    print(f"  Non-followers:  {stats['non_followers']:>6}  ← don't follow you back")
    print(f"  Fans:           {stats['fans']:>6}  ← you don't follow back")
    print(f"  Whitelisted:    {stats['whitelisted']:>6}  ← excluded from unfollow")
    print("=" * 50)

    # Show first 20 non-followers
    nf = analysis["non_followers"]
    if nf:
        print(f"\n  Top non-followers (oldest first, showing {min(20, len(nf))}/{len(nf)}):")
        for i, user in enumerate(nf[:20]):
            date = user.get("followed_at", "unknown")
            if date and date != "unknown":
                date = date[:10]  # Just the date part
            print(f"    {i+1:>3}. @{user['username']:<25} (followed: {date})")

        if len(nf) > 20:
            print(f"    ... and {len(nf) - 20} more")
    print()


def generate_unfollow_queue(
    analysis: dict,
    output_path: str | Path | None = None,
    limit: int | None = None,
) -> Path:
    """
    Generate a task queue JSON file from the non-followers analysis.

    Args:
        analysis: Output from compute_non_followers().
        output_path: Where to save the task queue. Defaults to config path.
        limit: Max number of users to queue. None = all.

    Returns:
        Path to the generated task queue file.
    """
    _output = Path(output_path) if output_path else settings.TASK_QUEUE_PATH

    # Load existing queue to preserve completed history
    existing = {}
    if _output.exists():
        try:
            existing = json.loads(_output.read_text())
        except json.JSONDecodeError:
            pass

    # Get list of already completed unfollows
    completed = set(existing.get("completed", {}).get("unfollow", []))

    # Filter out already completed
    pending = [
        u["username"]
        for u in analysis["non_followers"]
        if u["username"] not in completed
    ]

    if limit:
        pending = pending[:limit]

    queue = {
        "unfollow": pending,
        "follow": existing.get("follow", []),
        "completed": existing.get("completed", {"unfollow": [], "follow": []}),
        "generated_at": datetime.now().isoformat(),
        "source": "instagram_data_export",
    }

    _output.parent.mkdir(parents=True, exist_ok=True)
    _output.write_text(json.dumps(queue, indent=2))

    print(f"[queue] Generated unfollow queue: {len(pending)} pending")
    print(f"[queue] Previously completed: {len(completed)}")
    print(f"[queue] Saved to: {_output}")

    return _output


def load_whitelist(path: str | Path | None = None) -> list[str]:
    """
    Load whitelist from a text file (one username per line).
    Lines starting with # are comments.
    """
    if path is None:
        default_path = settings.DATA_DIR / "whitelist.txt"
        if not default_path.exists():
            return []
        path = default_path

    path = Path(path)
    if not path.exists():
        return []

    lines = path.read_text().strip().splitlines()
    return [
        line.strip().lstrip("@")
        for line in lines
        if line.strip() and not line.strip().startswith("#")
    ]
