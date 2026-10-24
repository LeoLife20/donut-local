#!/usr/bin/env python3
"""Move CJK / kana / hangul / fullwidth / emoji covering fonts out of an engine.

  strip_fonts.py --fonts DIR --backup DIR --blocklist FILE [--apply]

Without --apply it only reports. Files keep their relative path under the
backup root, and each moved path is appended to the block list.
"""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from fontscan import decide, inspect


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fonts", type=Path, required=True)
    ap.add_argument("--backup", type=Path, required=True)
    ap.add_argument("--blocklist", type=Path, required=True)
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    fonts = args.fonts.expanduser().resolve(strict=True)
    flagged = []
    for p in sorted(fonts.rglob("*")):
        if p.suffix.lower() not in {".ttf", ".ttc", ".otf", ".otc"}:
            continue
        info = inspect(p)
        if decide(info["hits"]):
            flagged.append(info)

    total = sum(1 for p in fonts.rglob("*") if p.suffix.lower() in {".ttf", ".ttc", ".otf", ".otc"})
    print(f"fonts={total} flagged={len(flagged)}")
    if not args.apply:
        for info in flagged[:10]:
            print("  would move", info["path"])
        return

    moved = []
    for info in flagged:
        src = Path(info["path"])
        rel = src.relative_to(fonts)
        dst = args.backup / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        if dst.exists():
            raise SystemExit(f"refusing to overwrite backup: {dst}")
        shutil.move(str(src), str(dst))
        moved.append(src)

    with args.blocklist.open("a", encoding="utf-8") as stream:
        stream.write(f"# {fonts} — {len(moved)} files moved {args.blocklist}\n")
        for src in moved:
            stream.write(str(src) + "\n")
    print(f"moved={len(moved)} backup={args.backup}")


if __name__ == "__main__":
    main()
