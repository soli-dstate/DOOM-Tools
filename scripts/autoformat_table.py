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

ID normalization (on by default):
    - Item ids must form a 0-based, contiguous, duplicate-free sequence.
    - If they don't, items are renumbered to 0..N-1 in document order and every
      "current" id reference is remapped to match. Tables that are already
      canonical (ids are exactly {0..N-1}, any order) are left untouched.
    - Disable with --no-fix-ids (e.g. for a table paired with a _wt working
      table that shares its id space across files).

Usage:
    python scripts/autoformat_table.py tables/lid.sldtbl           # reformat in-place
    python scripts/autoformat_table.py tables/*.sldtbl             # multiple files
    python scripts/autoformat_table.py tables/lid.sldtbl --check   # check only (exit 1 if changes needed)
    python scripts/autoformat_table.py tables/lid.sldtbl --stdout  # print to stdout instead of writing
    python scripts/autoformat_table.py tables/lid.sldtbl --no-fix-ids  # skip id renumbering
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import sys

I4 = "    "

# Key whose value is an item-id reference (an int, or a dict carrying an "id").
# References can nest (a part's "current" object may itself hold parts/
# accessories/subslots with their own "current"), so remapping walks the whole
# tree. Item *identity* is the top-level "id" on each subtable array element;
# lootcrate "id_lct" and store/table references live in separate namespaces and
# are intentionally left untouched.
REFERENCE_KEY = "current"

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


def _is_int(value) -> bool:
    """True for genuine ints (bools are ints in Python — exclude them)."""
    return isinstance(value, int) and not isinstance(value, bool)


def _iter_identity_items(tables: dict):
    """Yield, in document order, every item that owns a top-level 'id'."""
    for arr in tables.values():
        if isinstance(arr, list):
            for item in arr:
                if isinstance(item, dict) and _is_int(item.get("id")):
                    yield item


def _collect_reference_ids(node, out: set) -> None:
    """Recursively gather every id referenced by a 'current' field."""
    if isinstance(node, dict):
        for key, val in node.items():
            if key == REFERENCE_KEY:
                if _is_int(val):
                    out.add(val)
                elif isinstance(val, dict) and _is_int(val.get("id")):
                    out.add(val["id"])
            _collect_reference_ids(val, out)
    elif isinstance(node, list):
        for entry in node:
            _collect_reference_ids(entry, out)


def _remap_references(node, remap: dict, stats: dict) -> None:
    """Recursively rewrite every 'current' id reference using remap.

    Callers guarantee every referenced id is present in ``remap`` (dangling
    references are detected and rejected up front), so this is a clean rewrite.
    """
    if isinstance(node, dict):
        for key, val in node.items():
            if key == REFERENCE_KEY:
                if _is_int(val) and val in remap:
                    node[key] = remap[val]
                    stats["remapped"] += 1
                elif isinstance(val, dict) and _is_int(val.get("id")) and val["id"] in remap:
                    val["id"] = remap[val["id"]]
                    stats["remapped"] += 1
            _remap_references(val, remap, stats)
    elif isinstance(node, list):
        for entry in node:
            _remap_references(entry, remap, stats)


def check_and_fix_ids(data: dict, fix: bool = True) -> tuple[bool, list[str]]:
    """Verify item ids form a 0-based, contiguous, duplicate-free sequence.

    When they don't and ``fix`` is True, renumber id-bearing items to 0..N-1 in
    document order and remap every 'current' reference accordingly.

    Renumbering is refused (and nothing is mutated) when any 'current' reference
    points to an id that is not an identity in this file. Such "dangling"
    references mean either the file is broken or it shares an id space with a
    paired _wt table; renumbering anyway would silently re-point those stale ids
    at whichever item later inherited the number. Returns ``(problem_found,
    messages)``.
    """
    tables = data.get("tables")
    if not isinstance(tables, dict):
        return False, []

    items = list(_iter_identity_items(tables))
    if not items:
        return False, []

    old_ids = [item["id"] for item in items]
    n = len(old_ids)
    counts = collections.Counter(old_ids)
    dup_ids = sorted(i for i, c in counts.items() if c > 1)
    present = set(old_ids)
    canonical = not dup_ids and present == set(range(n))

    ref_ids: set[int] = set()
    _collect_reference_ids(tables, ref_ids)
    dangling = sorted(ref_ids - present)

    if canonical and not dangling:
        return False, []  # already canonical with sound references — untouched

    # ── Describe what's wrong (long id lists are truncated) ──────────────
    def _preview(ids: list) -> str:
        head = ", ".join(str(i) for i in ids[:10])
        return f"[{head}, ... +{len(ids) - 10} more]" if len(ids) > 10 else f"[{head}]"

    messages: list[str] = []
    if dup_ids:
        messages.append(f"{len(dup_ids)} duplicate id(s): {_preview(dup_ids)}")
    gaps = sorted(set(range(min(old_ids), max(old_ids) + 1)) - present)
    if gaps:
        messages.append(f"{len(gaps)} gap(s) in sequence, missing: {_preview(gaps)}")
    if min(old_ids) != 0:
        messages.append(f"sequence starts at {min(old_ids)} (expected 0)")
    if max(old_ids) != n - 1 and not gaps and not dup_ids:
        messages.append(f"highest id {max(old_ids)} != item count - 1 ({n - 1})")
    if dangling:
        messages.append(
            f"{len(dangling)} reference(s) point to id(s) not present in this "
            f"file: {_preview(dangling)}"
        )

    # Reference integrity must be sound before we dare renumber.
    if dangling:
        messages.append(
            "SKIPPED renumber: resolve the unresolved reference(s) above first, "
            "or pass --no-fix-ids if this table is paired with a _wt working table."
        )
        return True, messages

    if canonical:
        return True, messages  # numbering already fine; nothing else to do

    if not fix:
        messages.append(f"{n} item(s) would be renumbered to 0..{n - 1}")
        return True, messages

    # ── Build old->new map (first occurrence wins for duplicates) ─────────
    remap: dict[int, int] = {}
    ambiguous: set[int] = set()
    for new_id, item in enumerate(items):
        old = item["id"]
        if old in remap:
            ambiguous.add(old)  # duplicate identity — refs can't disambiguate
        else:
            remap[old] = new_id

    # Assign new identities, then remap all references off the old values.
    for new_id, item in enumerate(items):
        item["id"] = new_id

    stats = {"remapped": 0}
    _remap_references(tables, remap, stats)

    messages.append(
        f"renumbered {n} item(s) to 0..{n - 1}; "
        f"remapped {stats['remapped']} reference(s)"
    )
    if ambiguous:
        messages.append(
            f"WARNING: duplicate id(s) {_preview(sorted(ambiguous))} had references "
            f"remapped to their first occurrence — verify manually"
        )
    return True, messages


def format_file(filepath: str, fix_ids: bool = True) -> tuple[str, str, list[str], bool]:
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    data = json.loads(content)
    id_messages: list[str] = []
    id_problem = False
    if fix_ids:
        id_problem, id_messages = check_and_fix_ids(data, fix=True)
    formatted = format_root(data)
    return content, formatted, id_messages, id_problem


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
    parser.add_argument(
        "--no-fix-ids",
        action="store_true",
        help="Do not renumber item ids to a 0-based contiguous sequence. "
             "Use for tables paired with a _wt working table (shared id space).",
    )
    args = parser.parse_args()

    fix_ids = not args.no_fix_ids
    needs_changes = False

    for filepath in args.files:
        if not os.path.isfile(filepath):
            print(f"File not found: {filepath}", file=sys.stderr)
            continue

        try:
            original, formatted, id_messages, id_problem = format_file(filepath, fix_ids=fix_ids)
        except json.JSONDecodeError as e:
            print(f"Invalid JSON in {filepath}: {e}", file=sys.stderr)
            continue
        except Exception as e:
            print(f"Error processing {filepath}: {e}", file=sys.stderr)
            continue

        if args.stdout:
            print(formatted)
            continue

        for msg in id_messages:
            print(f"      id: {msg}")

        style_changed = original.rstrip() != formatted.rstrip()

        # id_problem with no style change means the renumber was skipped
        # (dangling references) — the file is left as-is and the issue stands.
        unresolved_ids = id_problem and not style_changed

        if not style_changed and not id_problem:
            print(f"  OK: {filepath}")
        else:
            needs_changes = True
            if args.check:
                print(f"  NEEDS FORMATTING: {filepath}")
            elif unresolved_ids:
                print(f"  UNRESOLVED ID ISSUES (not written, see above): {filepath}")
            else:
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(formatted)
                print(f"  FORMATTED: {filepath}")

    if args.check and needs_changes:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
