#!/usr/bin/env python3
"""Exit 0 when no CJK/kana/hangul/fullwidth/emoji font remains under DIR."""
import sys
from pathlib import Path

sys.path.insert(0, "/Users/1bits/Desktop/dount/work/unlock-pro")
from fontscan import decide, inspect  # noqa: E402


def main() -> int:
    root = Path(sys.argv[1])
    if not root.is_dir():
        print(f"   missing: {root}")
        return 1
    left = []
    for p in root.rglob("*"):
        if p.suffix.lower() not in {".ttf", ".ttc", ".otf", ".otc"}:
            continue
        if decide(inspect(p)["hits"]):
            left.append(p.name)
    if left:
        print(f"   remaining ({len(left)}): {left[:8]}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
