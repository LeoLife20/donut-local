#!/usr/bin/env python3
"""Experimental, version-bound local gate patch for a NEW private app copy.

Never modifies the source app, never reads profiles or credentials, and never
patches the server response/JWT/signature verification routines. It cannot
grant access to cloud services. Do not distribute the vendor binary copy.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import plistlib
import subprocess
import sys
from datetime import datetime, timezone

VERSION = "152.0.7977.64"
SOURCE_SHA256 = "76281696840949fbaa4fc0a23d69b899b6e88364646483c9ae3951985b29ae02"
FRAMEWORK = Path("Contents/Frameworks/Wayfern Framework.framework/Versions") / VERSION / "Wayfern Framework"
OFFSET = 0x3ACB844
ORIGINAL = bytes.fromhex("ff0301d1f44f02a9")
# AArch64: mov w0, #0; ret. The original ABI returns a small state in x0/w0.
REPLACEMENT = bytes.fromhex("00008052c0035fd6")

# These nine software-local consumers read the same custom-fingerprint
# capability. The cached server response itself is not changed.
CUSTOM_CONSUMERS = [
    0x3ABE164, 0x3ABE300, 0x3ABF234, 0x3AC2494, 0x3AC8CC4,
    0x3ACBBBC, 0x3ACDC58, 0x3AE08B4, 0x3AE3000,
]
CROSS_OS_CONDITIONS = {
    0x3AC3A08: "c1010054",
    0x3AC4E54: "c1010054",
    0x3ACCCBC: "810b0054",
    0x3AC0128: "410e0054",
}

# The local patch set must never edit server-response verification or replace
# storage failures with success. These are retained native code ranges.
PROTECTED_CODE_RANGES = [
    (0x3AD1540, 0x3AD3840, "token verification network function"),
    (0x3AD99EC, 0x3AD9F20, "signed response integrity verifier"),
    (0x3AB40C0, 0x3AB4B54, "generation store I/O and integrity checks"),
    (0x3AB4FF0, 0x3AB500C, "generation atomic-write failure propagation"),
]


def validate_patch_scope(patches: list[dict]) -> None:
    previous_end = -1
    for patch in sorted(patches, key=lambda entry: entry["offset"]):
        start = patch["offset"]
        width = len(patch["before"])
        if start % 4 or not width or width % 4 or width != len(patch["after"]):
            raise ValueError("A patch must preserve aligned ARM64 instruction widths")
        if start < previous_end:
            raise ValueError("Overlapping patches are not allowed")
        end = start + width
        for low, high, purpose in PROTECTED_CODE_RANGES:
            if start < high and end > low:
                raise ValueError(f"Refusing to alter retained {purpose}")
        previous_end = end


def selected_patches(fingerprints: bool, unlimited_rate: bool = False,
                     unlimited_instances: bool = False,
                     unlimited_generation: bool = False) -> list[dict]:
    patches = [{"offset": OFFSET, "before": ORIGINAL, "after": REPLACEMENT,
                "purpose": "Local browser automation entitlement state returns allowed"}]
    if fingerprints:
        patches.extend({"offset": offset,
                        "before": bytes.fromhex("08c16c39"),
                        "after": bytes.fromhex("28008052"),
                        "purpose": "Local custom-fingerprint policy read returns true; field validation remains"}
                       for offset in CUSTOM_CONSUMERS)
        patches.extend({"offset": offset,
                        "before": bytes.fromhex(before),
                        "after": bytes.fromhex("1f2003d5"),
                        "purpose": "Skip only the software-local cross-OS token-required conditional; requested OS remains"}
                       for offset, before in CROSS_OS_CONDITIONS.items())
    if unlimited_rate:
        patches.append({"offset": 0x3AF1780,
                        "before": bytes.fromhex("f44fbea9fd7b01a9"),
                        "after": bytes.fromhex("20008052c0035fd6"),
                        "purpose": "Software-local automation token bucket returns allowed; cloud quotas are unchanged"})
    if unlimited_instances:
        patches.append({"offset": 0x3271E4,
                        "before": bytes.fromhex("2b060054"),
                        "after": bytes.fromhex("31000014"),
                        "purpose": "Software-local plan instance cap: allow the existing locked slot-recording path regardless of count; lock and I/O checks remain"})
    if unlimited_generation:
        patches.extend([
            {"offset": 0x3AB4C08, "before": bytes.fromhex("4d010054"),
             "after": bytes.fromhex("0a000014"),
             "purpose": "Local generation quota cooldown: use the existing allowed path; monotonic time, lock, checksum, and I/O failures remain"},
            {"offset": 0x3AB4F78, "before": bytes.fromhex("8a020054"),
             "after": bytes.fromhex("14000014"),
             "purpose": "Local hourly generation quota: use the normal charged/persisted success path regardless of count; storage failures remain status 2"},
        ])
    return sorted(patches, key=lambda patch: patch["offset"])


def digest(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-app", required=True, type=Path)
    parser.add_argument("--destination", required=True, type=Path)
    parser.add_argument("--ad-hoc-sign", action="store_true")
    parser.add_argument("--include-fingerprints", action="store_true",
                        help="Experimental local custom and cross-OS fingerprint policy changes")
    parser.add_argument("--include-unlimited-rate", action="store_true",
                        help="Experimental removal of the software-local automation rate quota")
    parser.add_argument("--include-unlimited-instances", action="store_true",
                        help="Experimental removal of the software-local plan instance cap")
    parser.add_argument("--include-unlimited-generation", action="store_true",
                        help="Experimental removal of the software-local plan generation quota")
    parser.add_argument("--profile", choices=["automation", "fingerprints", "local-all"],
                        default="local-all",
                        help="Fixed patch profile; cloud permissions and limits are unchanged")
    options = parser.parse_args()
    source = options.source_app.resolve(strict=True)
    destination = options.destination.expanduser().resolve(strict=False)
    work_root = Path(__file__).resolve().parent
    if not destination.is_relative_to(work_root):
        raise ValueError("The experiment destination must remain below this work directory")
    if destination.exists() or destination.is_symlink():
        raise ValueError("Refusing to overwrite an existing app or destination")
    if destination.suffix != ".app" or source.suffix != ".app":
        raise ValueError("Both source and destination must be app bundles")
    original = source / FRAMEWORK
    if not original.resolve(strict=True).is_relative_to(source):
        raise ValueError("The framework must be contained in the selected source app")
    with (source / "Contents/Info.plist").open("rb") as handle:
        info = plistlib.load(handle)
    if info.get("CFBundleShortVersionString") != VERSION:
        raise ValueError("Unsupported Wayfern version")
    if digest(original) != SOURCE_SHA256:
        raise ValueError("Unsupported framework SHA-256; no files were modified")
    fingerprints = options.include_fingerprints or options.profile in {"fingerprints", "local-all"}
    unlimited_rate = options.include_unlimited_rate or options.profile == "local-all"
    unlimited_instances = options.include_unlimited_instances or options.profile == "local-all"
    unlimited_generation = options.include_unlimited_generation or options.profile == "local-all"
    patches = selected_patches(fingerprints, unlimited_rate, unlimited_instances, unlimited_generation)
    validate_patch_scope(patches)
    with original.open("rb") as handle:
        for patch in patches:
            handle.seek(patch["offset"])
            if handle.read(len(patch["before"])) != patch["before"]:
                raise ValueError(f"Original instructions did not match at {patch['offset']:#x}")

    destination.parent.mkdir(parents=True, exist_ok=True)
    # macOS APFS clone preserves bundle contents/symlinks, with independent
    # copy-on-write bytes. No fallback changes the source on failure.
    subprocess.run(["/bin/cp", "-cRp", str(source), str(destination)], check=True)
    copied = destination / FRAMEWORK
    if not copied.resolve(strict=True).is_relative_to(destination.resolve()):
        raise ValueError("The copied framework is not inside the new bundle")
    if digest(copied) != SOURCE_SHA256:
        raise ValueError("Copied framework did not match the verified source")
    with copied.open("r+b") as handle:
        for patch in patches:
            handle.seek(patch["offset"])
            if handle.read(len(patch["before"])) != patch["before"]:
                raise ValueError(f"Copied instructions did not match at {patch['offset']:#x}")
            handle.seek(patch["offset"])
            handle.write(patch["after"])
        handle.flush()

    unsigned_hash = digest(copied)
    changed: list[int] = []
    with original.open("rb") as before, copied.open("rb") as after:
        position = 0
        while True:
            left = before.read(4 * 1024 * 1024)
            right = after.read(len(left))
            if not left:
                if after.read(1):
                    raise ValueError("Unexpected framework length change")
                break
            if len(right) != len(left):
                raise ValueError("Unexpected framework length change")
            if left != right:
                changed.extend(position + i for i, (a, b) in enumerate(zip(left, right)) if a != b)
            position += len(left)
    expected = [patch["offset"] + i for patch in patches
                for i, (a, b) in enumerate(zip(patch["before"], patch["after"])) if a != b]
    if changed != expected:
        raise ValueError("Unexpected changes outside the selected local gate patches")

    signing = {"requested": options.ad_hoc_sign, "verified": False}
    if options.ad_hoc_sign:
        subprocess.run(["/usr/bin/codesign", "--force", "--deep", "--sign", "-", str(destination)], check=True)
        subprocess.run(["/usr/bin/codesign", "--verify", "--deep", "--strict", str(destination)], check=True)
        signing["verified"] = True
    final_hash = digest(copied)
    if digest(original) != SOURCE_SHA256:
        raise ValueError("Source changed during analysis; stop and inspect it")
    manifest = {
        "experimental": True,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "source_app": str(source),
        "private_experiment_app": str(destination),
        "version": VERSION,
        "patch_profile": options.profile,
        "fingerprint_policy_patches_requested": fingerprints,
        "local_rate_policy_patch_requested": unlimited_rate,
        "local_instance_policy_patch_requested": unlimited_instances,
        "local_generation_policy_patches_requested": unlimited_generation,
        "framework_relative_path": str(FRAMEWORK),
        "source_sha256_before_and_after": SOURCE_SHA256,
        "patch": {
            "file_offset": OFFSET,
            "file_offset_hex": hex(OFFSET),
            "original_bytes": ORIGINAL.hex(),
            "replacement_bytes": REPLACEMENT.hex(),
            "replacement_instructions": ["mov w0, #0", "ret"],
            "original_instructions": ["sub sp, sp, #0x40", "stp x20, x19, [sp, #0x20]"],
            "changed_byte_offsets_before_signing": [
                OFFSET + i for i, (a, b) in enumerate(zip(ORIGINAL, REPLACEMENT)) if a != b
            ],
            "unsigned_patched_sha256": unsigned_hash,
        },
        "binary_diff_before_signing": {
            "changed_byte_count": len(changed),
            "changed_byte_offsets": changed,
            "matches_listed_patches_only": True,
        },
        "all_patches": [
            {"file_offset": patch["offset"], "file_offset_hex": hex(patch["offset"]),
             "original_bytes": patch["before"].hex(), "replacement_bytes": patch["after"].hex(),
             "purpose": patch["purpose"]}
            for patch in patches
        ],
        "ad_hoc_signing": signing,
        "final_framework_sha256": final_hash,
        "scope": "Only software-local native feature policy checks; no cloud account, token, JWT, or signature verifier changes",
        "limitations": [
            "The function's initialization/cache side effects are skipped; runtime consequences must be measured",
            "The browser's local rate limiter is removed only by the local-all profile or the explicit rate option; server quotas are unchanged",
            "Signing also changes code-signature metadata; the pre-signing byte diff is exactly the listed local patches",
            "This does not establish that every local feature works",
            "The new app copy is private experimental material; do not distribute the vendor binary",
        ],
    }
    manifest_path = destination.parent / "patch-manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"manifest": str(manifest_path), "framework_sha256": final_hash, "source_unchanged": True}))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print(f"Experiment stopped: {error}", file=sys.stderr)
        raise SystemExit(1) from error
