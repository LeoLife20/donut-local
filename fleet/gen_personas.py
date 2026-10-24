#!/usr/bin/env python3
"""Generate the Apple Silicon persona pool.

Every entry is a real chip/thread count with a screen mode macOS actually
offers for that machine class, so (threads, GPU string, screen) is unique per
persona — the only tuple a page can see. 12 chips x 4 modes = 48 personas.
"""
from __future__ import annotations

import json
from pathlib import Path

OUT = Path("/Users/1bits/Documents/Codex/2026-10-14/https-github-com-zhom-donutbrowser-https/work/donutbrowser/src-tauri/personas/personas.json")

FONTS = ["Arial", "Arial Black", "Courier New", "Georgia", "Impact", "Tahoma",
         "Times New Roman", "Trebuchet MS", "Verdana", "Helvetica", "Helvetica Neue",
         "Menlo", "Monaco"]

# (model, chip, threads, [(w, h)])
CHIPS = [
    ("MacBookAir10,1", "M1", 8, [(1440, 900), (1280, 800), (1680, 1050), (2560, 1440)]),
    ("iMac21,1", "M1", 8, [(2240, 1260)]),
    ("MacBookPro18,3", "M1 Pro", 10, [(1512, 982), (1352, 878), (1728, 1117), (2056, 1329), (2560, 1440)]),
    ("MacBookPro18,2", "M1 Max", 10, [(1728, 1117), (1512, 982), (2056, 1329), (2560, 1440)]),
    ("Mac14,2", "M2", 8, [(1470, 956), (1280, 832), (1710, 1112), (1920, 1080), (2560, 1440)]),
    ("Mac14,9", "M2 Pro", 12, [(1512, 982), (1728, 1117), (1352, 878), (2056, 1329), (1920, 1080)]),
    ("Mac14,10", "M2 Max", 12, [(1728, 1117), (1512, 982), (2056, 1329), (2560, 1440)]),
    ("Mac15,3", "M3", 8, [(1512, 982), (1470, 956), (1710, 1112), (1280, 832), (1920, 1080)]),
    ("Mac15,6", "M3 Pro", 12, [(1512, 982), (1728, 1117), (2056, 1329), (1352, 878), (1920, 1080)]),
    ("Mac15,8", "M3 Max", 16, [(1728, 1117), (2056, 1329), (1512, 982), (2560, 1440)]),
    ("Mac16,10", "M4", 10, [(1920, 1080), (2560, 1440), (1512, 982), (1470, 956), (1710, 1112)]),
    ("Mac16,6", "M4 Pro", 12, [(1512, 982), (1728, 1117), (1920, 1080), (2560, 1440), (2056, 1329)]),
    ("Mac16,8", "M4 Max", 16, [(1728, 1117), (2056, 1329), (1512, 982), (2560, 1440), (1920, 1080)]),
]

# External displays report 24-bit; built-in Retina panels report 30-bit.
EXTERNAL = {(1920, 1080), (2560, 1440)}


def slug(model: str, chip: str, w: int, h: int) -> str:
    base = {
        "MacBookAir10,1": "mba",
        "MacBookPro17,1": "mbp13",
        "MacBookPro18,3": "mbp14",
        "MacBookPro18,2": "mbp16",
        "Mac14,2": "mba-m2",
        "Mac14,3": "mini-m2",
        "Mac14,9": "mbp14-m2pro",
        "Mac14,10": "mbp16-m2max",
        "Mac15,3": "mbp14-m3",
        "Mac15,6": "mbp14-m3pro",
        "Mac15,8": "mbp16-m3max",
        "Mac16,10": "mini-m4",
        "Mac16,6": "mbp14-m4pro",
        "Mac16,8": "mbp16-m4max",
        "iMac21,1": "imac-m1",
    }.get(model, "mac")
    return f"{base}-{w}x{h}".replace(",", "")


def main() -> None:
    rows = []
    seen = set()
    for model, chip, threads, modes in CHIPS:
        for (w, h) in modes:
            key = (threads, chip, w, h)
            if key in seen:
                continue
            seen.add(key)
            avail_h = h - 30 if h >= 900 else h - 25
            rows.append({
                "persona_id": slug(model, chip, w, h),
                "os": "macos",
                "hardware": {
                    "model": model,
                    "cpu": f"Apple {chip}",
                    "threads": threads,
                    "ram_gb": 16,
                    "gpu": f"Apple {chip}",
                    "screen": [w, h],
                    "avail": [w, avail_h],
                    "color_depth": 24 if (w, h) in EXTERNAL else 30,
                    "dpr": 1 if (w, h) in EXTERNAL else 2,
                },
                "browser": {
                    "ua": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36",
                    "platform": "MacIntel",
                    "platform_version": "26.6.2",
                },
                "webgl": {
                    "vendor": "Google Inc. (Apple)",
                    "renderer": f"ANGLE (Apple, ANGLE Metal Renderer: Apple {chip}, Unspecified Version)",
                },
                "fonts": FONTS,
                "do_not_track": "unspecified",
            })
    OUT.write_text(json.dumps(rows, indent=2) + "\n")
    print(f"wrote {len(rows)} personas to {OUT}")
    visible = {(r['hardware']['threads'], r['webgl']['renderer'], tuple(r['hardware']['screen'])) for r in rows}
    print("unique visible tuples:", len(visible))


if __name__ == "__main__":
    main()
