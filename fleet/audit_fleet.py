#!/usr/bin/env python3
"""Launch every fleet profile once, measure what a page sees, and report
whether the (canvas, audio) pairs are unique across the whole set."""
from __future__ import annotations

import json
import os
import pathlib
import shutil
import subprocess
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent
FLEET = HERE / "fleet"
REGISTRY = FLEET / "registry.jsonl"
OUT = FLEET / "audit.jsonl"
NODE = os.environ.get("NODE") or shutil.which("node") or "node"


def rows() -> list[dict]:
    return [json.loads(l) for l in REGISTRY.read_text().splitlines() if l.strip()]


def measure(port: int) -> dict:
    try:
        out = subprocess.run([NODE, str(HERE / "measure.mjs"), str(port)],
                             capture_output=True, text=True, timeout=45)
    except subprocess.TimeoutExpired:
        return {"error": "measure timeout"}
    line = (out.stdout or "").strip().splitlines()[-1] if out.stdout.strip() else ""
    try:
        return json.loads(line)
    except json.JSONDecodeError:
        return {"error": (out.stderr or line or "no output")[:200]}


def main() -> int:
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    items = rows()
    if limit:
        items = items[:limit]
    done = 0
    OUT.write_text("")
    for i, row in enumerate(items):
        pid = row["profile_id"]
        port = 9950 + i
        proc = subprocess.Popen(
            [NODE, str(HERE / "launch.mjs"), "--profile", str(FLEET / "profiles" / pid), "--port", str(port)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        time.sleep(8)
        data = measure(port)
        proc.terminate()
        subprocess.run(["pkill", "-f", f"user-data-dir=.*fleet/profiles/{pid}"], capture_output=True)
        subprocess.run(["pkill", "-f", f"launch.mjs --profile .*{pid}"], capture_output=True)
        time.sleep(1)
        rec = {"i": i, "profile": pid, "persona": row["persona_id"], **data}
        with OUT.open("a") as fh:
            fh.write(json.dumps(rec) + "\n")
        done += 1
        print(f"[{done}/{len(items)}] {pid[:8]} {row['persona_id']:28} "
              f"canvas={data.get('canvas')} audio={data.get('audio')} "
              f"fonts={data.get('fonts')} err={data.get('error', '')}", flush=True)

    recs = [json.loads(l) for l in OUT.read_text().splitlines() if l.strip()]
    keys = [(r.get("canvas"), r.get("audio")) for r in recs]
    hw = [(r.get("hc"), r.get("gpu"), r.get("sw"), r.get("sh")) for r in recs]
    dup_keys = {k for k in keys if keys.count(k) > 1}
    font_ok = all(r.get("fonts", {}).get("PingFang SC") == r.get("tofu") for r in recs if r.get("tofu"))
    print(json.dumps({
        "profiles": len(recs),
        "unique_canvas_audio": len(set(keys)),
        "duplicate_pairs": len(dup_keys),
        "unique_hardware_tuples": len(set(hw)),
        "cjk_fonts_hidden": font_ok,
        "titles": sorted({r.get("persona") for r in recs})[:12],
    }, indent=2))
    return 0 if not dup_keys else 2


if __name__ == "__main__":
    sys.exit(main())
