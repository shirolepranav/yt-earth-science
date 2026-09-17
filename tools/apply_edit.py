"""Replace a run's script with an edited version pasted into a GitHub comment.

Gate 2 is meant to be a real edit, not a rubber stamp. So the approval comment
can contain a corrected script inside a fenced code block:

    approve

    ```
    ...your edited script...
    ```

This script pulls that block out and writes it over runs/<id>/script.txt.
If there's no code block, the comment is a plain approval and nothing changes.

Usage:  python tools/apply_edit.py --run <id> --comment-file comment.txt
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MIN_WORDS = 200  # a real script is far longer; anything shorter is a stray snippet


def extract_script(comment: str) -> str | None:
    """Find the longest fenced code block in the comment."""
    blocks = re.findall(r"```(?:\w+)?\s*\n(.*?)```", comment, re.DOTALL)
    if not blocks:
        return None

    longest = max(blocks, key=len).strip()
    if len(longest.split()) < MIN_WORDS:
        return None
    return longest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", required=True)
    parser.add_argument("--comment-file", required=True)
    args = parser.parse_args()

    comment = Path(args.comment_file).read_text()
    edited = extract_script(comment)

    if not edited:
        print("No edited script found in the comment - keeping the generated one.")
        return

    target = ROOT / "runs" / args.run / "script.txt"
    if not target.exists():
        sys.exit(f"{target} not found.")

    # Keep the original so you can compare if the edit went wrong.
    (target.parent / "script_before_edit.txt").write_text(target.read_text())
    target.write_text(edited + "\n")

    print(f"Applied your edited script ({len(edited.split()):,} words).")


if __name__ == "__main__":
    main()
