#!/usr/bin/env python3
"""convert_legacy_saves.py

Batch-convert legacy pickle-format save/transfer/loot/preset files to JSON,
and sign them with HMAC-SHA256 for tamper protection.

The old format stored data as: base85(pickle.dumps(data))
The new format stores data as: base85(json({"_sig": "<hmac hex>", "_data": <json data>}))

Usage:
    python scripts/convert_legacy_saves.py             # convert & sign
    python scripts/convert_legacy_saves.py --dry-run   # preview without writing
    python scripts/convert_legacy_saves.py --resign     # re-sign already-converted JSON files

Scans:
    saves/          *.sldsv   (save files & persistent data)
    saves/backups/  *.sldsv   (backup saves, recursively)
    transfers/      *.sldtrf  (transfer files)
    lootcrates/     *.sldlct  (loot crate files)
    lootcrates/presets/ *.sldlct (loot crate presets)
    enemyloot/      *.sldenlt (enemy loot files)
"""

from __future__ import annotations

import argparse
import base64
import glob
import hashlib
import hmac as _hmac
import json
import os
import pickle
import secrets
import shutil
import sys
from datetime import datetime
from pathlib import Path


def _get_save_key() -> bytes:
    """Load or generate the per-installation HMAC key."""
    key_path = os.path.join("saves", ".save_key")
    if os.path.isfile(key_path):
        with open(key_path, "rb") as f:
            key = f.read()
        if len(key) >= 32:
            return key[:32]
    key = secrets.token_bytes(32)
    os.makedirs(os.path.dirname(key_path), exist_ok=True)
    with open(key_path, "wb") as f:
        f.write(key)
    return key


def _sign_data(json_str: str) -> str:
    """Return hex HMAC-SHA256 signature for a JSON string."""
    key = _get_save_key()
    return _hmac.new(key, json_str.encode("utf-8"), hashlib.sha256).hexdigest()


def _make_signed_payload(data: dict | list, comment_lines: list[str] | None = None) -> str:
    """Build the base85-encoded signed envelope string, optionally prepending comment lines."""
    payload_str = json.dumps(data, ensure_ascii=False, sort_keys=True)
    sig = _sign_data(payload_str)
    envelope = {"_sig": sig, "_data": data}
    json_str = json.dumps(envelope, ensure_ascii=False, indent=None)
    encoded = base64.b85encode(json_str.encode("utf-8")).decode("ascii")
    output = ""
    if comment_lines:
        for cl in comment_lines:
            output += cl if cl.endswith("\n") else cl + "\n"
    output += encoded
    return output


def _try_decode_signed_b85(payload: str) -> dict | None:
    """Try to base85-decode and JSON-parse a signed envelope. Returns parsed dict or None."""
    try:
        decoded = base64.b85decode(payload.encode("ascii")).decode("utf-8")
        parsed = json.loads(decoded)
        if isinstance(parsed, dict) and "_sig" in parsed and "_data" in parsed:
            return parsed
    except Exception:
        pass
    return None


def is_json(text: str) -> bool:
    try:
        json.loads(text)
        return True
    except (json.JSONDecodeError, ValueError):
        return False


def try_decode_legacy(raw: bytes | str) -> dict | list | None:
    """Attempt to decode a legacy pickle+base85 payload.

    Returns the deserialized Python object, or None if it isn't legacy format.
    """
    if isinstance(raw, str):
        raw_bytes = raw.encode("utf-8")
    else:
        raw_bytes = raw

    try:
        decoded = base64.b85decode(raw_bytes)
    except Exception:
        return None

    try:
        obj = pickle.loads(decoded)  # noqa: S301  — intentional for migration only
        return obj
    except Exception:
        return None


def convert_file(filepath: str, *, dry_run: bool = False, backup: bool = True) -> str:
    """Convert a single file from legacy pickle format to signed JSON.

    Returns a status string: 'converted', 'already_signed', 'already_json', 'skipped', or 'error:...'.
    """
    try:
        # Read the file (try text first, fall back to binary)
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
        except UnicodeDecodeError:
            with open(filepath, "rb") as f:
                content = f.read()

        # Strip leading comment lines (saves can have // comments at the top)
        lines = content.splitlines(True) if isinstance(content, str) else content.decode("utf-8", errors="replace").splitlines(True)
        comment_lines = []
        data_lines = []
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("//"):
                comment_lines.append(line)
            elif stripped == "" and not data_lines:
                comment_lines.append(line)
            else:
                data_lines.append(line)
        payload = "".join(data_lines).strip()

        if not payload:
            return "skipped"

        # Already signed + base85 encoded?
        signed_envelope = _try_decode_signed_b85(payload)
        if signed_envelope is not None:
            return "already_signed"

        # Plain JSON (unsigned)?
        if is_json(payload):
            parsed = json.loads(payload)
            if isinstance(parsed, dict) and "_sig" in parsed and "_data" in parsed:
                return "already_signed"
            return "already_json"

        # Try legacy pickle decode
        data = try_decode_legacy(payload)
        if data is None:
            # Try reading as raw binary for files opened in 'wb' mode
            with open(filepath, "rb") as f:
                raw_bytes = f.read()
            data = try_decode_legacy(raw_bytes)

        if data is None:
            return "skipped"

        if dry_run:
            return "converted"

        # Back up the original
        if backup:
            backup_dir = os.path.join(os.path.dirname(filepath), ".legacy_backup")
            os.makedirs(backup_dir, exist_ok=True)
            backup_name = os.path.basename(filepath) + ".bak"
            backup_path = os.path.join(backup_dir, backup_name)
            # Avoid overwriting existing backups
            if os.path.exists(backup_path):
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_path = os.path.join(backup_dir, f"{os.path.basename(filepath)}.{ts}.bak")
            shutil.copy2(filepath, backup_path)

        # Write signed JSON
        output = _make_signed_payload(data, comment_lines)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(output)

        return "converted"

    except Exception as e:
        return f"error: {e}"


def resign_file(filepath: str, *, dry_run: bool = False) -> str:
    """Sign an existing unsigned JSON file with HMAC.

    Returns: 'signed', 'already_signed', 'not_json', or 'error:...'.
    """
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        lines = content.splitlines(True)
        comment_lines = []
        data_lines = []
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("//"):
                comment_lines.append(line)
            elif stripped == "" and not data_lines:
                comment_lines.append(line)
            else:
                data_lines.append(line)
        payload = "".join(data_lines).strip()

        if not payload:
            return "not_json"

        # Already signed + base85 encoded?
        signed_envelope = _try_decode_signed_b85(payload)
        if signed_envelope is not None:
            return "already_signed"

        # Plain JSON (possibly unsigned, or already signed without base85)
        if not is_json(payload):
            return "not_json"

        parsed = json.loads(payload)

        # Already signed (plain JSON envelope)?
        if isinstance(parsed, dict) and "_sig" in parsed and "_data" in parsed:
            # Re-encode as base85 if not dry-run
            parsed = parsed["_data"]

        if not isinstance(parsed, (dict, list)):
            return "not_json"

        if dry_run:
            return "signed"

        output = _make_signed_payload(parsed, comment_lines)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(output)

        return "signed"

    except Exception as e:
        return f"error: {e}"


def main():
    parser = argparse.ArgumentParser(
        description="Convert legacy pickle-format files to signed JSON, or re-sign existing JSON files."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview what would be converted/signed without writing any files.",
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Skip creating backups of original files.",
    )
    parser.add_argument(
        "--resign",
        action="store_true",
        help="Sign existing unsigned JSON files with HMAC (no pickle conversion needed).",
    )
    parser.add_argument(
        "--root",
        default=None,
        help="Root directory of the DOOM-Tools project (defaults to parent of scripts/).",
    )
    args = parser.parse_args()

    if args.root:
        root = os.path.abspath(args.root)
    else:
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    os.chdir(root)

    scan_patterns = [
        ("saves/*.sldsv", "Save files"),
        ("saves/backups/**/*.sldsv", "Backup saves"),
        ("remotedata/*.sldsv", "Remote data"),
        ("transfers/*.sldtrf", "Transfer files"),
        ("lootcrates/*.sldlct", "Loot crate files"),
        ("lootcrates/presets/*.sldlct", "Loot crate presets"),
        ("enemyloot/*.sldenlt", "Enemy loot files"),
    ]

    total = 0
    converted = 0
    signed = 0
    already_ok = 0
    skipped = 0
    errors = 0

    mode_label = "RESIGN" if args.resign else "CONVERT"
    if args.dry_run:
        print(f"=== DRY RUN ({mode_label}) — no files will be modified ===\n")

    for pattern, label in scan_patterns:
        files = sorted(glob.glob(pattern, recursive=True))
        if not files:
            continue

        print(f"--- {label} ({pattern}) ---")
        for filepath in files:
            total += 1

            if args.resign:
                status = resign_file(filepath, dry_run=args.dry_run)
                if status == "signed":
                    signed += 1
                    action = "WOULD SIGN" if args.dry_run else "SIGNED"
                    print(f"  {action}: {filepath}")
                elif status == "already_signed":
                    already_ok += 1
                    print(f"  OK (already signed): {filepath}")
                elif status == "not_json":
                    skipped += 1
                    print(f"  SKIPPED (not JSON — convert first): {filepath}")
                else:
                    errors += 1
                    print(f"  ERROR: {filepath} — {status}")
            else:
                status = convert_file(filepath, dry_run=args.dry_run, backup=not args.no_backup)
                if status == "converted":
                    converted += 1
                    action = "WOULD CONVERT" if args.dry_run else "CONVERTED"
                    print(f"  {action}: {filepath}")
                elif status == "already_signed":
                    already_ok += 1
                    print(f"  OK (already signed): {filepath}")
                elif status == "already_json":
                    skipped += 1
                    action = "WOULD SIGN" if args.dry_run else "UNSIGNED JSON"
                    print(f"  {action} (use --resign to sign): {filepath}")
                elif status == "skipped":
                    skipped += 1
                    print(f"  SKIPPED (unrecognized format): {filepath}")
                else:
                    errors += 1
                    print(f"  ERROR: {filepath} — {status}")
        print()

    print("=" * 50)
    print(f"Total files scanned:  {total}")
    if args.resign:
        print(f"Signed:               {signed}")
    else:
        print(f"Converted & signed:   {converted}")
    print(f"Already OK:           {already_ok}")
    print(f"Skipped:              {skipped}")
    print(f"Errors:               {errors}")

    if converted > 0 and not args.dry_run:
        print(f"\nOriginal files backed up to '.legacy_backup/' folders.")
    if (converted > 0 or signed > 0) and args.dry_run:
        print(f"\nRe-run without --dry-run to apply changes.")

    return 0 if errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
