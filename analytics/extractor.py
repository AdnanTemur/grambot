"""Instagram Data Export Parser.

Parses the JSON files from Instagram's "Download Your Information" export.
Handles both the old and new export format structures.

Export path structure (varies by format):
  Old:  followers_and_following/followers_1.json, following.json
  New:  connections/followers_and_following/followers_1.json, following.json
"""

import json
from pathlib import Path
from datetime import datetime


def find_export_files(export_path: str | Path) -> dict[str, Path | None]:
    """
    Locate followers and following JSON files within an export directory.
    Searches common Instagram export directory structures.

    Args:
        export_path: Root path of the Instagram data export.

    Returns:
        Dict with 'followers' and 'following' keys pointing to file paths.
    """
    root = Path(export_path)

    # Possible locations for followers file
    followers_candidates = [
        root / "followers_and_following" / "followers_1.json",
        root / "connections" / "followers_and_following" / "followers_1.json",
        root / "followers_1.json",
        root / "followers.json",
    ]

    # Possible locations for following file
    following_candidates = [
        root / "followers_and_following" / "following.json",
        root / "connections" / "followers_and_following" / "following.json",
        root / "following.json",
    ]

    result = {"followers": None, "following": None}

    for path in followers_candidates:
        if path.exists():
            result["followers"] = path
            break

    for path in following_candidates:
        if path.exists():
            result["following"] = path
            break

    return result


def parse_followers(file_path: Path) -> list[dict]:
    """
    Parse followers JSON file.

    Instagram export format (typical):
    [
      {
        "title": "",
        "media_list_data": [],
        "string_list_data": [
          {
            "href": "https://www.instagram.com/username",
            "value": "username",
            "timestamp": 1234567890
          }
        ]
      },
      ...
    ]

    Returns:
        List of dicts with 'username', 'url', and 'timestamp' keys.
    """
    data = json.loads(file_path.read_text(encoding="utf-8"))

    followers = []
    items = data if isinstance(data, list) else data.get("relationships_followers", data)

    for item in items:
        try:
            string_data = item.get("string_list_data", [{}])
            if not string_data:
                continue

            entry = string_data[0]
            username = entry.get("value", "")
            href = entry.get("href", "")
            timestamp = entry.get("timestamp", 0)

            if username:
                followers.append({
                    "username": username,
                    "url": href,
                    "timestamp": timestamp,
                    "followed_at": (
                        datetime.fromtimestamp(timestamp).isoformat()
                        if timestamp else None
                    ),
                })
        except (IndexError, KeyError, TypeError):
            continue

    return followers


def parse_following(file_path: Path) -> list[dict]:
    """
    Parse following JSON file.

    Format is similar to followers but wrapped in a
    "relationships_following" key in newer exports.

    Returns:
        List of dicts with 'username', 'url', and 'timestamp' keys.
    """
    data = json.loads(file_path.read_text(encoding="utf-8"))

    following = []

    # Handle both formats
    if isinstance(data, list):
        items = data
    elif "relationships_following" in data:
        items = data["relationships_following"]
    else:
        items = data

    for item in items:
        try:
            string_data = item.get("string_list_data", [{}])
            if not string_data:
                continue

            entry = string_data[0]
            username = entry.get("value", "")
            href = entry.get("href", "")
            timestamp = entry.get("timestamp", 0)

            if username:
                following.append({
                    "username": username,
                    "url": href,
                    "timestamp": timestamp,
                    "followed_at": (
                        datetime.fromtimestamp(timestamp).isoformat()
                        if timestamp else None
                    ),
                })
        except (IndexError, KeyError, TypeError):
            continue

    return following


def load_export(export_path: str | Path) -> dict:
    """
    Load and parse a complete Instagram data export.

    Args:
        export_path: Root path of the export folder.

    Returns:
        Dict with 'followers' and 'following' lists,
        plus metadata about the export.
    """
    files = find_export_files(export_path)

    result = {
        "export_path": str(export_path),
        "followers": [],
        "following": [],
        "files_found": {k: str(v) if v else None for k, v in files.items()},
    }

    if files["followers"]:
        result["followers"] = parse_followers(files["followers"])
        print(f"[export] Parsed {len(result['followers'])} followers from {files['followers'].name}")
    else:
        print("[export] WARNING: Followers file not found")

    if files["following"]:
        result["following"] = parse_following(files["following"])
        print(f"[export] Parsed {len(result['following'])} following from {files['following'].name}")
    else:
        print("[export] WARNING: Following file not found")

    return result
