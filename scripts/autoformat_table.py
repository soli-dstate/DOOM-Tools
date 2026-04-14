#!/usr/bin/env python3
"""autoformat_table.py

Reformat .sldtbl JSON table files to the project's canonical formatting style.

Formatting rules:
    - 4-space indentation, no trailing whitespace
    - Root keys expanded on separate lines
    - Root-level dicts (additional_settings, rarity_weights, etc.) expanded one level
    - "tables" dict: each table category array expanded, items expanded
    - Item property values are compact (single-line), EXCEPT:
      - Arrays of objects: one compact object per line
      - "variants" arrays: objects are fully expanded (one key per line)

Usage:
    python scripts/autoformat_table.py tables/lid.sldtbl           # reformat in-place
    python scripts/autoformat_table.py tables/*.sldtbl             # multiple files
    python scripts/autoformat_table.py tables/lid.sldtbl --check   # check only (exit 1 if changes needed)
    python scripts/autoformat_table.py tables/lid.sldtbl --stdout  # print to stdout instead of writing
"""
from __future__ import annotations

import argparse
import json
import os
import sys

I4 = "    "

# Keys whose array-of-objects values should have their objects expanded
# (one property per line) rather than compacted to a single line.
EXPANDED_ARRAY_KEYS = {"variants"}

# Keys whose values (dicts or simple arrays) should be expanded rather than
# compacted to a single line when they appear as direct item properties.
EXPANDED_VALUE_KEYS = {"overrides", "consumable_sounds", "prices"}


def compact(obj) -> str:
    """Serialize obj to a single-line JSON string."""
    return json.dumps(obj, ensure_ascii=False)


def format_expanded_value(val, indent: str) -> str:
    """Format a dict or array value expanded one level, with compact values."""
    next_indent = indent + I4
    if isinstance(val, dict):
        result = "{\n"
        keys = list(val.keys())
        for i, key in enumerate(keys):
            comma = "," if i < len(keys) - 1 else ""
            result += f"{next_indent}{json.dumps(key)}: {compact(val[key])}{comma}\n"
        result += f"{indent}}}"
        return result
    elif isinstance(val, list):
        result = "[\n"
        for i, item in enumerate(val):
            comma = "," if i < len(val) - 1 else ""
            result += f"{next_indent}{compact(item)}{comma}\n"
        result += f"{indent}]"
        return result
    return compact(val)


def format_expanded_object(obj: dict, indent: str) -> str:
    """Format an object with each property on its own line."""
    result = "{\n"
    keys = list(obj.keys())
    next_indent = indent + I4
    for i, key in enumerate(keys):
        comma = "," if i < len(keys) - 1 else ""
        result += f"{next_indent}{json.dumps(key)}: {compact(obj[key])}{comma}\n"
    result += f"{indent}}}"
    return result


def format_item_value(val, indent: str, key: str = "") -> str:
    """Format a value that's a property of a table item."""
    if isinstance(val, list) and val and isinstance(val[0], dict):
        expand_objects = key in EXPANDED_ARRAY_KEYS
        result = "[\n"
        next_indent = indent + I4
        for i, item in enumerate(val):
            comma = "," if i < len(val) - 1 else ""
            if expand_objects:
                formatted = format_expanded_object(item, next_indent)
            else:
                formatted = compact(item)
            result += f"{next_indent}{formatted}{comma}\n"
        result += f"{indent}]"
        return result
    elif key in EXPANDED_VALUE_KEYS and isinstance(val, (dict, list)):
        return format_expanded_value(val, indent)
    else:
        return compact(val)


def format_table_item(item: dict, indent: str) -> str:
    """Format a single item (object) within a table array."""
    result = "{\n"
    keys = list(item.keys())
    next_indent = indent + I4
    for i, key in enumerate(keys):
        comma = "," if i < len(keys) - 1 else ""
        val = item[key]
        formatted_val = format_item_value(val, next_indent, key)
        result += f"{next_indent}{json.dumps(key)}: {formatted_val}{comma}\n"
    result += f"{indent}}}"
    return result


def format_table_array(arr: list, indent: str) -> str:
    result = "[\n"
    next_indent = indent + I4
    for i, item in enumerate(arr):
        comma = "," if i < len(arr) - 1 else ""
        if isinstance(item, dict):
            formatted = format_table_item(item, next_indent)
            result += f"{next_indent}{formatted}{comma}\n"
        else:
            result += f"{next_indent}{compact(item)}{comma}\n"
    result += f"{indent}]"
    return result


def format_nested_dict(obj: dict, indent: str) -> str:
    """Format a nested dict (like npc_names) with standard indentation."""
    result = "{\n"
    keys = list(obj.keys())
    next_indent = indent + I4
    for i, key in enumerate(keys):
        comma = "," if i < len(keys) - 1 else ""
        val = obj[key]
        if isinstance(val, dict):
            formatted = format_nested_dict(val, next_indent)
        elif isinstance(val, list):
            formatted = compact(val)
        else:
            formatted = compact(val)
        result += f"{next_indent}{json.dumps(key)}: {formatted}{comma}\n"
    result += f"{indent}}}"
    return result


def format_tables(tables: dict, indent: str) -> str:
    result = "{\n"
    keys = list(tables.keys())
    next_indent = indent + I4
    for i, key in enumerate(keys):
        comma = "," if i < len(keys) - 1 else ""
        val = tables[key]
        if isinstance(val, list):
            formatted = format_table_array(val, next_indent)
        elif isinstance(val, dict):
            formatted = format_nested_dict(val, next_indent)
        else:
            formatted = compact(val)
        result += f"{next_indent}{json.dumps(key)}: {formatted}{comma}\n"
    result += f"{indent}}}"
    return result


def format_root(data: dict) -> str:
    result = "{\n"
    keys = list(data.keys())
    for i, key in enumerate(keys):
        comma = "," if i < len(keys) - 1 else ""
        val = data[key]
        if key == "tables" and isinstance(val, dict):
            formatted = format_tables(val, I4)
            result += f"{I4}{json.dumps(key)}: {formatted}{comma}\n"
        elif isinstance(val, dict):
            result += f"{I4}{json.dumps(key)}: {{\n"
            inner_keys = list(val.keys())
            for j, dk in enumerate(inner_keys):
                dcomma = "," if j < len(inner_keys) - 1 else ""
                result += f"{I4}{I4}{json.dumps(dk)}: {compact(val[dk])}{dcomma}\n"
            result += f"{I4}}}{comma}\n"
        else:
            result += f"{I4}{json.dumps(key)}: {compact(val)}{comma}\n"
    result += "}"
    return result


def format_file(filepath: str) -> tuple[str, str]:
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    data = json.loads(content)
    formatted = format_root(data)
    return content, formatted


def main():
    parser = argparse.ArgumentParser(
        description="Reformat .sldtbl table files to canonical formatting."
    )
    parser.add_argument(
        "files",
        nargs="+",
        help="Table file(s) to format.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check if files need reformatting (exit 1 if changes needed).",
    )
    parser.add_argument(
        "--stdout",
        action="store_true",
        help="Print formatted output to stdout instead of writing files.",
    )
    args = parser.parse_args()

    needs_changes = False

    for filepath in args.files:
        if not os.path.isfile(filepath):
            print(f"File not found: {filepath}", file=sys.stderr)
            continue

        try:
            original, formatted = format_file(filepath)
        except json.JSONDecodeError as e:
            print(f"Invalid JSON in {filepath}: {e}", file=sys.stderr)
            continue
        except Exception as e:
            print(f"Error processing {filepath}: {e}", file=sys.stderr)
            continue

        if args.stdout:
            print(formatted)
            continue

        if original.rstrip() == formatted.rstrip():
            print(f"  OK: {filepath}")
        else:
            needs_changes = True
            if args.check:
                print(f"  NEEDS FORMATTING: {filepath}")
            else:
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(formatted)
                print(f"  FORMATTED: {filepath}")

    if args.check and needs_changes:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
