#!/usr/bin/env python3
"""Create and track fleet profiles that the launcher runs directly.

The app is not in this path: a profile is a directory with metadata.json plus a
Chromium user-data dir, and `launch.mjs` starts the patched engine against it.
That keeps a 1000-profile fleet independent of the app's version pruning and
plan gates.

    python3 fleet.py create --count 5
    python3 fleet.py list
    python3 fleet.py report
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
import sys
import time
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
PERSONAS = HERE / "personas.json"
LOCATIONS = HERE / "locations.json"
FLEET = HERE
PROFILES = FLEET / "profiles"
REGISTRY = FLEET / "registry.jsonl"
VERSION = "152.0.7977.64"


def personas() -> list[dict]:
    return json.loads(PERSONAS.read_text())


def overrides_of(p: dict) -> dict:
    h, b, w = p["hardware"], p["browser"], p["webgl"]
    return {
        "hardwareConcurrency": h["threads"],
        "deviceMemory": max(1, min(h["ram_gb"], 8)),
        "screenWidth": h["screen"][0],
        "screenHeight": h["screen"][1],
        "screenAvailWidth": h["avail"][0],
        "screenAvailHeight": h["avail"][1],
        "screenColorDepth": h["color_depth"],
        "platform": b["platform"],
        "platformVersion": b["platform_version"],
        "userAgent": b["ua"],
        "maxTouchPoints": 0,
        "webglVendor": w["vendor"],
        "webglRenderer": w["renderer"],
        "doNotTrack": p.get("do_not_track") or "unspecified",
        "fonts": json.dumps(p["fonts"], separators=(",", ":")),
    }


def locations() -> list[dict]:
    return json.loads(LOCATIONS.read_text())


def offset_minutes(tz_name: str) -> int:
    from datetime import datetime
    from zoneinfo import ZoneInfo
    delta = datetime.now(ZoneInfo(tz_name)).utcoffset() or 0
    return int(delta.total_seconds() // 60)


def fp_key(overrides: dict, identity_id: str) -> str:
    blob = json.dumps({"o": overrides, "id": identity_id}, sort_keys=True)
    return hashlib.sha256(blob.encode()).hexdigest()[:16]


def rows() -> list[dict]:
    if not REGISTRY.exists():
        return []
    return [json.loads(line) for line in REGISTRY.read_text().splitlines() if line.strip()]


def create(count: int, city: str | None, country: str | None) -> int:
    pool = personas()
    places = locations()
    if country:
        places = [p for p in places if p["country"] == country.upper()]
    if city:
        places = [p for p in places if p["city"].lower() == city.lower()]
    if not places:
        raise SystemExit("no location matches that filter")
    existing = rows()
    made = []
    for i in range(count):
        pid = str(uuid.uuid4())
        persona = pool[(len(existing) + i) % len(pool)]
        place = places[(len(existing) + i) % len(places)]
        ov = overrides_of(persona)
        tz = place["timezone"]
        off = offset_minutes(tz)
        pdir = PROFILES / pid
        (pdir / "profile").mkdir(parents=True, exist_ok=True)
        location = {
            "timezone": tz,
            "language": place["language"],
            "languages": place["languages"],
            "latitude": place["latitude"],
            "longitude": place["longitude"],
            "timezoneOffset": off,
            "city": place["city"],
            "country": place["country"],
        }
        metadata = {
            "id": pid,
            "name": f"{persona['persona_id'].split('-')[0]}-{pid[:8]}",
            "browser": "wayfern",
            "version": VERSION,
            "created_at": int(time.time()),
            "city": place["city"],
            "country": place["country"],
            "wayfern_config": {
                "identity_id": pid,
                "identity_overrides": json.dumps(ov, separators=(",", ":")),
                "os": "macos",
                "location": json.dumps(location),
                "screen_max_width": persona["hardware"]["screen"][0],
                "screen_max_height": persona["hardware"]["screen"][1],
                "randomize_fingerprint_on_launch": False,
            },
        }
        (pdir / "metadata.json").write_text(json.dumps(metadata, indent=2))
        row = {
            "profile_id": pid,
            "name": metadata["name"],
            "persona_id": persona["persona_id"],
            "version": VERSION,
            "city": place["city"],
            "country": place["country"],
            "tz": tz,
            "language": place["language"],
            "fp_key": fp_key(ov, pid),
            "created_at": int(time.time()),
        }
        with REGISTRY.open("a") as fh:
            fh.write(json.dumps(row) + "\n")
        made.append(row)
        print(f"  + {pid[:8]} {persona['persona_id']:30} {place['city']:<15} {tz:<22} {place['language']}")
    print(f"created {len(made)} profiles under {PROFILES}")
    return 0


LANG_BY_COUNTRY = {"US": "en-US", "CA": "en-CA", "GB": "en-GB", "AU": "en-AU", "NZ": "en-NZ", "IE": "en-IE"}


def geo_lookup(ip: str) -> dict:
    import urllib.request
    url = f"http://ip-api.com/json/{ip}?fields=status,countryCode,city,lat,lon,timezone"
    with urllib.request.urlopen(url, timeout=10) as r:
        data = json.loads(r.read())
    if data.get("status") != "success":
        raise SystemExit(f"geo lookup failed for {ip}: {data}")
    cc = data.get("countryCode") or "US"
    lang = LANG_BY_COUNTRY.get(cc, "en-US")
    return {
        "city": data.get("city") or "unknown",
        "country": cc,
        "timezone": data.get("timezone") or "America/Denver",
        "language": lang,
        "languages": [lang, lang.split("-")[0]],
        "latitude": data.get("lat"),
        "longitude": data.get("lon"),
    }


def apply_location(profile_id: str, place: dict) -> int:
    tz = place["timezone"]
    location = {
        "timezone": tz, "language": place["language"], "languages": place["languages"],
        "latitude": place["latitude"], "longitude": place["longitude"],
        "timezoneOffset": offset_minutes(tz),
        "city": place["city"], "country": place["country"],
    }
    meta_path = PROFILES / profile_id / "metadata.json"
    meta = json.loads(meta_path.read_text())
    meta["wayfern_config"]["location"] = json.dumps(location)
    meta["city"] = place["city"]
    meta["country"] = place["country"]
    meta_path.write_text(json.dumps(meta, indent=2))
    print(f"{profile_id[:8]} -> {place['city']} {tz} {place['language']}")
    return 0


def set_proxy(profile_id: str, proxy: str) -> int:
    meta_path = PROFILES / profile_id / "metadata.json"
    meta = json.loads(meta_path.read_text())
    meta["proxy_url"] = proxy
    meta_path.write_text(json.dumps(meta, indent=2))
    print(f"{profile_id[:8]} proxy set")
    return 0


def assign(profile_id: str, city: str | None, ip: str | None) -> int:
    if ip:
        return apply_location(profile_id, geo_lookup(ip))
    place = next((p for p in locations() if p["city"].lower() == (city or "").lower()), None)
    if not place:
        raise SystemExit(f"unknown city: {city}")

    return apply_location(profile_id, place)


def cmd_list(_a) -> int:
    for r in rows():
        print(f'{r["profile_id"]}  {r["persona_id"]:28} {r["city"]:12} fp={r["fp_key"]}')
    return 0


def cmd_report(_a) -> int:
    rs = rows()
    keys = [r["fp_key"] for r in rs]
    dup = {k for k in keys if keys.count(k) > 1}
    print(json.dumps({
        "profiles": len(rs),
        "unique_fp_keys": len(set(keys)),
        "duplicates": sorted(dup),
        "personas": len({r["persona_id"] for r in rs}),
        "cities": len({r["city"] for r in rs}),
        "countries": len({r.get("country", "US") for r in rs}),
    }, indent=2))
    return 0 if not dup else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("create")
    c.add_argument("--count", type=int, default=1)
    c.add_argument("--city", default=None)
    c.add_argument("--country", default=None)
    c.set_defaults(func=lambda a: create(a.count, a.city, a.country))
    asn = sub.add_parser("assign")
    asn.add_argument("--profile", required=True)
    asn.add_argument("--city")
    asn.add_argument("--ip")
    asn.set_defaults(func=lambda a: assign(a.profile, a.city, a.ip))
    sp = sub.add_parser("set-proxy")
    sp.add_argument("--profile", required=True)
    sp.add_argument("--proxy", required=True)
    sp.set_defaults(func=lambda a: set_proxy(a.profile, a.proxy))
    sub.add_parser("list").set_defaults(func=cmd_list)
    sub.add_parser("report").set_defaults(func=cmd_report)
    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
