#!/usr/bin/env python3
"""Classify font files by real cmap coverage, not by filename.

Interval-based: never materialises codepoint sets, so a font that maps
0..0x10FFFF costs nothing. Flags a face when its cmap overlaps any codepoint
in the CJK / kana / hangul / fullwidth / emoji blocks the plan names.
Supports .ttf/.otf and .ttc (every face in the collection is merged).
"""
from __future__ import annotations

import json
import struct
import sys
from pathlib import Path

RANGES = {
    "han": [(0x2E80, 0x2EFF), (0x3005, 0x3005), (0x3007, 0x3007), (0x3400, 0x4DBF),
            (0x4E00, 0x9FFF), (0xF900, 0xFAFF), (0x20000, 0x2A6DF), (0x2A700, 0x2EBEF),
            (0x2F800, 0x2FA1F), (0x30000, 0x323AF)],
    "kana": [(0x3040, 0x30FF), (0x31F0, 0x31FF), (0x1B000, 0x1B16F)],
    "hangul": [(0x1100, 0x11FF), (0x3130, 0x318F), (0xA960, 0xA97F), (0xAC00, 0xD7FF)],
    "fullwidth": [(0x3000, 0x303F), (0xFF00, 0xFFEF)],
    # Supplementary emoji plane only: dingbats (U+2600-27BF) are ordinary text
    # symbols that Arial, Helvetica and Menlo all carry; counting them would
    # delete the very Latin faces the identity advertises.
    "emoji": [(0x1F000, 0x1FAFF), (0x1F1E6, 0x1F1FF)],
}


def _cmap_intervals(data: bytes, off: int) -> list[tuple[int, int]]:
    out: list[tuple[int, int]] = []
    num = struct.unpack_from(">H", data, off + 2)[0]
    seen: set[int] = set()
    for i in range(num):
        pid, eid, sub = struct.unpack_from(">HHI", data, off + 4 + i * 8)
        if not (pid == 0 or (pid == 3 and eid in (1, 10))):
            continue
        p = off + sub
        if p in seen or p + 4 > len(data):
            continue
        seen.add(p)
        fmt = struct.unpack_from(">H", data, p)[0]
        if fmt == 4:
            segx2 = struct.unpack_from(">H", data, p + 6)[0]
            seg = segx2 // 2
            ends = struct.unpack_from(f">{seg}H", data, p + 14)
            starts = struct.unpack_from(f">{seg}H", data, p + 16 + segx2)
            for s, e in zip(starts, ends):
                if s != 0xFFFF and e >= s:
                    out.append((s, e))
        elif fmt == 12:
            ngroups = struct.unpack_from(">I", data, p + 12)[0]
            for g in range(ngroups):
                s, e, _gid = struct.unpack_from(">III", data, p + 16 + g * 12)
                if e >= s:
                    out.append((s, e))
        elif fmt == 6:
            first, count = struct.unpack_from(">HH", data, p + 6)
            if count:
                out.append((first, first + count - 1))
        elif fmt == 0:
            glyphs = data[p + 6:p + 262]
            run = None
            for cp, gid in enumerate(glyphs):
                if gid:
                    run = cp if run is None else run
                elif run is not None:
                    out.append((run, cp - 1))
                    run = None
            if run is not None:
                out.append((run, 261))
    return out


def _faces(data: bytes) -> list[int]:
    if data[:4] == b"ttcf":
        n = struct.unpack_from(">I", data, 8)[0]
        return list(struct.unpack_from(f">{n}I", data, 12))
    return [0]


def _name(data: bytes, base: int) -> str:
    try:
        num = struct.unpack_from(">H", data, base + 4)[0]
        str_off = struct.unpack_from(">H", data, base + 6)[0]
        for i in range(num):
            pid, eid, lid, nid, length, off = struct.unpack_from(
                ">HHHHHH", data, base + 8 + i * 12)
            if nid in (1, 4) and pid == 3 and lid == 0x409:
                raw = data[base + str_off + off: base + str_off + off + length]
                return raw.decode("utf-16-be", "replace")
    except Exception:
        pass
    return ""


# A face is CJK/emoji-bearing when it actually offers CJK typography or the
# supplementary emoji plane. Thresholds calibrated against the 78 files the
# earlier pass removed: Arial/Helvetica/Verdana/Menlo stayed, Arial Unicode,
# Apple Symbols, DejaVu and the CJK families went.
THRESHOLDS = {"han": 100, "kana": 50, "hangul": 50, "fullwidth": 20, "emoji": 1}


def decide(hits: dict[str, int]) -> bool:
    return any(hits.get(k, 0) >= v for k, v in THRESHOLDS.items())


def _overlap(intervals, ranges) -> int:
    total = 0
    for s, e in intervals:
        for rs, re_ in ranges:
            lo, hi = max(s, rs), min(e, re_)
            if hi >= lo:
                total += hi - lo + 1
    return total


def inspect(path: Path) -> dict:
    data = path.read_bytes()
    hits: dict[str, int] = {}
    family = ""
    for base in _faces(data):
        try:
            num = struct.unpack_from(">H", data, base + 4)[0]
        except struct.error:
            continue
        cmap = None
        for i in range(num):
            tag, _sum, off, _len = struct.unpack_from(">4sIII", data, base + 12 + i * 16)
            if tag == b"cmap":
                cmap = off
            elif tag == b"name" and not family:
                family = _name(data, off)
        if cmap is None:
            continue
        try:
            intervals = _cmap_intervals(data, cmap)
        except struct.error:
            continue
        for key, ranges in RANGES.items():
            n = _overlap(intervals, ranges)
            if n:
                hits[key] = hits.get(key, 0) + n
    return {"path": str(path), "name": family, "hits": hits}


def main() -> None:
    roots = [Path(p) for p in sys.argv[1:]]
    flagged, clean = [], []
    for root in roots:
        for p in sorted(root.rglob("*")):
            if p.suffix.lower() not in {".ttf", ".ttc", ".otf", ".otc"}:
                continue
            info = inspect(p)
            (flagged if info["hits"] else clean).append(info)
    print(json.dumps({
        "scanned": len(flagged) + len(clean),
        "flagged": len(flagged),
        "clean": len(clean),
        "flagged_files": flagged,
    }, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
