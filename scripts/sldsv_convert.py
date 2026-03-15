#!/usr/bin/env python3
"""sldsv_convert.py

Convert .sldsv (binary/pickled/base85) <-> .sldsvraw (human-readable) files.

Usage:
  python scripts/sldsv_convert.py file.sldsv         # produces file.sldsvraw
  python scripts/sldsv_convert.py file.sldsvraw      # restores file.sldsv

Behavior:
- When converting from .sldsv to .sldsvraw the script attempts to
  unpickle the file, decode any base85 payloads and produce a
  pretty-printed, human-readable text file. The raw (base85-encoded)
  original binary payload is stored after a separator so conversion
  back to the original binary is lossless.
- When converting from .sldsvraw to .sldsv the script looks for the
  stored base85 block and writes it back as binary. If no block is
  found the script will pickle the textual content and write that.
"""

from __future__ import annotations

import argparse
import base64
import os
import pickle
import pprint
import zlib
from pathlib import Path
import sys
import re
from typing import Any

BASE85_MARKER = "---BASE85---"


def read_binary(path: Path) -> bytes:
    return path.read_bytes()


def try_unpickle(data: bytes):
    try:
        return pickle.loads(data)
    except Exception:
        return None


def try_zlib_decompress(data: bytes) -> bytes | None:
    try:
        return zlib.decompress(data)
    except Exception:
        return None


def try_decode_blob(data: bytes) -> Any:
    """Try multiple strategies to decode a binary blob.

    Returns either a text string, a Python object (from pickle), or None.
    """
    # direct utf-8
    try:
        return data.decode("utf-8")
    except Exception:
        pass

    # base85 (b85 then a85)
    for fn in (base64.b85decode, base64.a85decode):
        try:
            dec = fn(data)
        except Exception:
            dec = None
        if dec is None:
            continue
        # try to load as pickle
        obj = try_unpickle(dec)
        if obj is not None:
            return obj
        # try utf-8
        try:
            return dec.decode("utf-8")
        except Exception:
            pass
        # try zlib then utf-8
        dec2 = try_zlib_decompress(dec)
        if dec2 is not None:
            try:
                return dec2.decode("utf-8")
            except Exception:
                obj2 = try_unpickle(dec2)
                if obj2 is not None:
                    return obj2

    # try zlib on original
    dec = try_zlib_decompress(data)
    if dec is not None:
        try:
            return dec.decode("utf-8")
        except Exception:
            obj = try_unpickle(dec)
            if obj is not None:
                return obj

    # try unpickle original
    obj = try_unpickle(data)
    if obj is not None:
        return obj

    return None


def is_likely_base85_text(s: str) -> bool:
    # Base85 uses a limited ASCII range; be permissive but require length
    s = s.strip()
    if not s:
        return False
    # require at least 16 chars and only printable ascii (no newlines check)
    return len(s) >= 16 and all(32 <= ord(c) <= 126 for c in s)


def decode_base85_try(s: bytes) -> bytes | None:
    # try b85decode, then a85decode if needed
    for fn in (base64.b85decode, base64.a85decode):
        try:
            return fn(s)
        except Exception:
            continue
    return None


def encode_base85(b: bytes) -> str:
    return base64.b85encode(b).decode("ascii")


def pretty_for_obj(obj) -> str:
    try:
        return pprint.pformat(obj, width=120)
    except Exception:
        return str(obj)


def sldsv_to_raw(in_path: Path, out_path: Path) -> None:
    data = read_binary(in_path)
    # Always keep the original binary encoded so conversion is reversible
    original_b85 = encode_base85(data)

    # Try to decode and produce a human-readable structure
    top = try_decode_blob(data)

    if top is None:
        pretty = "<binary content could not be decoded to text>"
    else:
        # If we got a python object, pretty-print recursively decoded structure
        def traverse(o):
            if isinstance(o, (list, tuple, set)):
                return type(o)(traverse(x) for x in o)
            if isinstance(o, dict):
                return {k: traverse(v) for k, v in o.items()}
            if isinstance(o, (bytes, bytearray)):
                dec = try_decode_blob(bytes(o))
                if dec is None:
                    # show repr to avoid binary in text
                    try:
                        return repr(bytes(o))
                    except Exception:
                        return str(o)
                return traverse(dec)
            if isinstance(o, str):
                # maybe it's base85 text
                if is_likely_base85_text(o):
                    try:
                        dec = base64.b85decode(o.encode("ascii"))
                    except Exception:
                        dec = None
                    if dec is not None:
                        dec2 = try_decode_blob(dec)
                        if dec2 is not None:
                            return traverse(dec2)
                return o
            return o

        if isinstance(top, (bytes, bytearray)):
            # try to get text
            txt = try_decode_blob(bytes(top))
            pretty = pretty_for_obj(txt if txt is not None else top)
        else:
            pretty = pretty_for_obj(traverse(top))

    parts = []
    parts.append(f"# Converted from: {in_path.name}")
    parts.append("# Human-readable view (editable).\n")
    parts.append(pretty)
    parts.append("\n" + BASE85_MARKER + "\n")
    parts.append(original_b85)

    out_path.write_text("\n".join(parts), encoding="utf-8")


def raw_to_sldsv(in_path: Path, out_path: Path) -> None:
    txt = in_path.read_text(encoding="utf-8")

    # Find the base85 block
    m = re.search(rf"{BASE85_MARKER}\s*\n(.+)$", txt, flags=re.S)
    if m:
        b85 = m.group(1).strip()
        try:
            binary = base64.b85decode(b85.encode("ascii"))
            out_path.write_bytes(binary)
            return
        except Exception:
            pass

    # No base85 block found: as fallback, pickle the text and write
    try:
        blob = pickle.dumps(txt)
        out_path.write_bytes(blob)
    except Exception as e:
        print(f"Failed to write .sldsv: {e}")


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    p = argparse.ArgumentParser(description="Convert .sldsv <-> .sldsvraw")
    p.add_argument("paths", nargs="+", help="File(s) to convert")
    args = p.parse_args(argv)

    for raw in args.paths:
        path = Path(raw)
        if not path.exists():
            print(f"File not found: {path}")
            continue

        suffix = path.suffix.lower()
        # support both `.sldsv` and `.sdlsv` just in case
        if suffix in (".sldsv", ".sdlsv"):
            out = path.with_suffix(path.suffix + "raw") if not path.suffix.endswith("raw") else path.with_suffix(".sldsvraw")
            # prefer .sldsvraw extension
            out = path.with_name(path.stem + ".sldsvraw")
            print(f"Converting {path} -> {out}")
            sldsv_to_raw(path, out)
        elif path.name.lower().endswith(".sldsvraw"):
            # restore
            out_name = path.stem
            if out_name.endswith(".sldsv"):
                out_name = out_name
            else:
                out_name = path.stem + ".sldsv"
            out = path.with_name(out_name)
            print(f"Restoring {path} -> {out}")
            raw_to_sldsv(path, out)
        else:
            # Unknown extension: attempt to convert based on content
            print(f"Unknown extension for {path}, attempting to convert to .sldsvraw")
            out = path.with_name(path.name + ".sldsvraw")
            sldsv_to_raw(path, out)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
