#!/usr/bin/env python3
"""Autoformat main.py files: remove comments/docstrings, normalize spacing, backup files."""
from __future__ import annotations
import argparse
import ast
import re
import datetime
import io
import os
import shutil
import tokenize
import sys
from typing import Set


def find_main_files(root: str) -> list[str]:
    # Only look in the specified root directory (non-recursive) per user request
    matches = []
    try:
        for entry in os.listdir(root):
            if entry == "main.py":
                matches.append(os.path.join(root, entry))
    except Exception:
        # fallback to recursive search if listing fails
        for dirpath, _, files in os.walk(root):
            if "main.py" in files:
                matches.append(os.path.join(dirpath, "main.py"))
    return matches


def make_backup(path: str) -> str:
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = os.path.join(os.getcwd(), "backup")
    os.makedirs(backup_dir, exist_ok=True)
    basename = os.path.basename(path)
    bak = os.path.join(backup_dir, f"{basename}.backup")
    shutil.copy2(path, bak)
    return bak


def docstring_line_numbers(source: str) -> Set[int]:
    lines = set()
    try:
        tree = ast.parse(source)
    except Exception:
        return lines

    def record(node):
        if not getattr(node, "body", None):
            return
        first = node.body[0]
        # docstring is an Expr whose value is a Constant/Str
        if isinstance(first, ast.Expr) and isinstance(getattr(first, "value", None), (ast.Constant, ast.Str)):
            # Python 3.8+ provides end_lineno
            start = getattr(first, "lineno", None)
            end = getattr(first, "end_lineno", None)
            if start is not None:
                if end is None:
                    end = start
                for ln in range(start, end + 1):
                    lines.add(ln)

    # module
    record(tree)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            record(node)

    return lines


def strip_comments_and_docstrings(source: str) -> str:
    doc_lines = docstring_line_numbers(source)
    out_tokens = []
    try:
        g = tokenize.generate_tokens(io.StringIO(source).readline)
    except Exception:
        return source

    for tok in g:
        ttype = tok.type
        tstring = tok.string
        start_row = tok.start[0]
        # drop comments except special ignores we want to keep
        if ttype == tokenize.COMMENT:
            c = tstring or ""
            low = c.lower()
            # preserve '# type: ignore' and any comment containing 'pyright'
            if re.search(r"type\s*:\s*ignore", low) or "pyright" in low:
                out_tokens.append((ttype, tstring))
            # otherwise drop the comment
            continue
        # drop docstring STRING tokens (the string literal that is the first statement)
        if ttype == tokenize.STRING and start_row in doc_lines:
            continue
        out_tokens.append((ttype, tstring))

    try:
        # adjust single '=' operator spacing (avoid changing '==', '!=', ':=', etc.)
        for i, (ttype, tstring) in enumerate(out_tokens):
            if ttype == tokenize.OP and tstring == '=':
                out_tokens[i] = (ttype, ' = ')

        new = tokenize.untokenize(out_tokens)
    except Exception:
        return source
    return new


def normalize_spacing(text: str) -> str:
    # strip trailing whitespace
    lines = [ln.rstrip() for ln in text.splitlines()]

    # collapse multiple blank lines to a single blank line
    out = []
    blank = False
    for ln in lines:
        if ln.strip() == "":
            if not blank:
                out.append("")
                blank = True
        else:
            out.append(ln)
            blank = False

    # ensure a single blank line after contiguous import block(s)
    i = 0
    while i < len(out):
        if out[i].startswith("import ") or out[i].startswith("from "):
            j = i
            while j + 1 < len(out) and (out[j + 1].startswith("import ") or out[j + 1].startswith("from ")):
                j += 1
            if j + 1 < len(out) and out[j + 1] != "":
                out.insert(j + 1, "")
            i = j + 1
        else:
            i += 1

    result = "\n".join(out)

    # Post-process token spacing per-line while preserving leading indentation
    new_lines = []
    for ln in result.splitlines():
        # preserve leading whitespace
        m = re.match(r"^(\s*)(.*)$", ln)
        indent = m.group(1)
        body = m.group(2)

        # remove spaces around dots and before parentheses/brackets
        body = re.sub(r"\s*\.\s*", ".", body)
        body = re.sub(r"\s+\(", "(", body)
        body = re.sub(r"\(\s+", "(", body)
        body = re.sub(r"\s+\)", ")", body)
        body = re.sub(r"\s*\[\s*", "[", body)
        body = re.sub(r"\s*\]\s*", "]", body)

        # remove spaces before commas, then ensure single space after commas
        body = re.sub(r"\s+,", ",", body)
        body = re.sub(r",\s*", ", ", body)

        # remove space before colons
        body = re.sub(r"\s+:", ":", body)

        # tighten spaces inside braces/brackets/parentheses (e.g., f"{ var }" -> f"{var}")
        body = re.sub(r"\{\s+", "{", body)
        body = re.sub(r"\s+\}", "}", body)

        # collapse multiple spaces in the body
        body = re.sub(r" {2,}", " ", body)

        new_lines.append(indent + body.rstrip())

    result = "\n".join(new_lines).rstrip() + "\n"
    return result


def process_file(path: str, dry_run: bool = False, verbose: bool = False) -> bool:
    try:
        with open(path, "r", encoding="utf-8") as f:
            src = f.read()
    except Exception as e:
        if verbose:
            print(f"Failed to read {path}: {e}")
        return False

    stripped = strip_comments_and_docstrings(src)
    normalized = normalize_spacing(stripped)

    if normalized == src:
        if verbose:
            print(f"No changes for {path}")
        return False

    if dry_run:
        print(f"--- DRY RUN: changes for {path} ---")
        print(normalized)
        return True

    bak = make_backup(path)
    with open(path, "w", encoding="utf-8") as f:
        f.write(normalized)
    if verbose:
        print(f"Updated {path}, backup: {bak}")
    return True


def main(argv=None):
    p = argparse.ArgumentParser(description="Autoformat any main.py files in a folder: remove comments/docstrings and normalize spacing.")
    p.add_argument("--root", "-r", default=".", help="Root directory to search (default: current directory)")
    p.add_argument("--dry-run", action="store_true", help="Print changes instead of writing files")
    p.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    args = p.parse_args(argv)

    mains = find_main_files(args.root)
    if not mains:
        print("No main.py files found.")
        return 0

    any_changed = False
    for m in mains:
        changed = process_file(m, dry_run=args.dry_run, verbose=args.verbose)
        any_changed = any_changed or changed

    if args.dry_run and not any_changed:
        print("No changes would be made.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
