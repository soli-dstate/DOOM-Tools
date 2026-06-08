#!/usr/bin/env python3
"""Decode DOOM-Tools signed save files for debugging.

Saves are NOT encrypted — they are a base85-encoded JSON envelope
``{"_sig": <hmac-sha256-hex>, "_data": <data>}`` optionally preceded by ``//``
comment lines. The ``.save_key`` (32 random bytes) is only used to HMAC-sign the
payload for tamper detection; it is not needed to read the data.

Usage:
    python scripts/decrypt_save.py <file.sldsv> [--key path/to/.save_key]
                                   [--out out.json] [--raw]

    python scripts/decrypt_save.py path/to/.save_key      # dump the key as hex

If --key (or an auto-found saves/.save_key) is provided, the signature is also
verified and reported. Without it, the data is still decoded (signature skipped).
"""

import argparse
import base64
import hashlib
import hmac
import json
import os
import sys

# Mirror main.py's portable transfer key (used for *.sldenlt / loot transfer files).
PORTABLE_KEY = hashlib.sha256(b"DOOM-Tools-portable-transfer-signing-key-v1").digest()


def _looks_like_raw_key(path):
    """A .save_key is ~32 raw bytes that are not valid base85 text."""
    if os.path.basename(path) == ".save_key":
        return True
    try:
        with open(path, "rb") as f:
            blob = f.read()
    except OSError:
        return False
    if not (16 <= len(blob) <= 256):
        return False
    # Heuristic: raw key has non-printable bytes; encoded saves are ascii text.
    return any(b < 9 or (13 < b < 32) for b in blob)


def key_info_text(path):
    with open(path, "rb") as f:
        key = f.read()
    return (
        f"# {path}  ({len(key)} bytes)\n"
        f"hex   : {key.hex()}\n"
        f"base64: {base64.b64encode(key).decode('ascii')}"
    )


def dump_key(path):
    print(key_info_text(path))


def decode_save(path, key=None):
    """Return (data, signature, status). status is one of:
    ok / unsigned / tampered / no_key / incompatible_format."""
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        text = f.read()

    # Strip leading // comment lines and blank lines, like _signed_json_read.
    data_lines = []
    for line in text.splitlines(True):
        stripped = line.strip()
        if stripped.startswith("//") and not data_lines:
            continue
        if stripped == "" and not data_lines:
            continue
        data_lines.append(line)
    payload = "".join(data_lines).strip()
    if not payload:
        raise ValueError("empty payload")

    # Current format: base85-encoded envelope. Legacy: raw JSON.
    try:
        envelope_json = base64.b85decode(payload.encode("ascii")).decode("utf-8")
    except Exception:
        envelope_json = payload

    parsed = json.loads(envelope_json)

    if isinstance(parsed, dict) and "_sig" in parsed and "_data" in parsed:
        sig = parsed["_sig"]
        data = parsed["_data"]
        status = "no_key"
        if key is not None:
            payload_str = json.dumps(data, ensure_ascii=False, sort_keys=True)
            expected = hmac.new(key, payload_str.encode("utf-8"), hashlib.sha256).hexdigest()
            status = "ok" if hmac.compare_digest(expected, sig) else "tampered"
        return data, sig, status

    # Unsigned legacy file.
    return parsed, None, "unsigned"


def encode_save(data, key=None, *, portable=False, comment_lines=None):
    """Build the on-disk text for a signed save (inverse of decode_save).

    Mirrors main.py's _signed_json_write: HMAC-sign the canonical payload, wrap
    it as {"_sig", "_data"}, base85-encode, and prepend any // comment lines.
    Pass portable=True to use the built-in portable transfer key.
    """
    if portable:
        key = PORTABLE_KEY
    if key is None:
        raise ValueError("a key is required to sign a save (or pass portable=True)")

    payload_str = json.dumps(data, ensure_ascii=False, sort_keys=True)
    sig = hmac.new(key, payload_str.encode("utf-8"), hashlib.sha256).hexdigest()
    envelope = json.dumps({"_sig": sig, "_data": data}, ensure_ascii=False)
    encoded = base64.b85encode(envelope.encode("utf-8")).decode("ascii")

    prefix = ""
    if comment_lines:
        prefix = "".join(cl if cl.endswith("\n") else cl + "\n" for cl in comment_lines)
    return prefix + encoded


def write_save(path, data, key=None, *, portable=False, comment_lines=None):
    """Encode `data` and write a valid signed save to `path`."""
    text = encode_save(data, key=key, portable=portable, comment_lines=comment_lines)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return path


def _autofind_key(save_path):
    """Look for a .save_key next to the save or in a sibling saves/ folder."""
    candidates = [
        os.path.join(os.path.dirname(os.path.abspath(save_path)), ".save_key"),
        os.path.join(os.path.dirname(os.path.abspath(save_path)), "saves", ".save_key"),
    ]
    for c in candidates:
        if os.path.isfile(c):
            return c
    return None


def main(argv=None):
    # Save data can contain non-ASCII (e.g. "→"); force UTF-8 stdout/stderr so
    # printing to a legacy Windows console (cp1252) doesn't crash.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    ap = argparse.ArgumentParser(description="Decode DOOM-Tools signed saves / dump save keys.")
    ap.add_argument("file", help="Path to a .sldsv/.sldenlt save, or a .save_key file")
    ap.add_argument("--key", help="Path to .save_key for signature verification")
    ap.add_argument("--portable", action="store_true",
                    help="Verify with the portable transfer key (loot transfer files)")
    ap.add_argument("--out", help="Write output here instead of stdout")
    ap.add_argument("--raw", action="store_true", help="Print compact JSON (no indent)")
    ap.add_argument("--encode", action="store_true",
                    help="Encode: read JSON from `file`, sign it, and write a save to --out")
    args = ap.parse_args(argv)

    # ── Encode mode: plain JSON in -> signed save out ─────────────────────
    if args.encode:
        if not args.out:
            ap.error("--encode requires --out (destination save path)")
        with open(args.file, "r", encoding="utf-8") as f:
            data = json.load(f)
        key = None
        if not args.portable:
            key_path = args.key or _autofind_key(args.out) or _autofind_key(args.file)
            if not key_path or not os.path.isfile(key_path):
                ap.error("no key found; pass --key <.save_key> or --portable")
            with open(key_path, "rb") as f:
                key = f.read()
            print(f"# signing with key: {key_path}", file=sys.stderr)
        else:
            print("# signing with portable key", file=sys.stderr)
        write_save(args.out, data, key=key, portable=args.portable)
        print(f"# wrote signed save: {args.out}", file=sys.stderr)
        return 0

    if _looks_like_raw_key(args.file):
        dump_key(args.file)
        return 0

    key = None
    if args.portable:
        key = PORTABLE_KEY
    elif args.key:
        with open(args.key, "rb") as f:
            key = f.read()
    else:
        auto = _autofind_key(args.file)
        if auto:
            with open(auto, "rb") as f:
                key = f.read()
            print(f"# using auto-found key: {auto}", file=sys.stderr)

    data, sig, status = decode_save(args.file, key=key)
    print(f"# signature status: {status}", file=sys.stderr)
    if sig:
        print(f"# _sig: {sig}", file=sys.stderr)

    text = json.dumps(data, ensure_ascii=False, indent=None if args.raw else 2)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"# wrote {args.out}", file=sys.stderr)
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
