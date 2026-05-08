"""
DOOM-Tools Table Manager — CustomTkinter GUI

Tab 1 – Parts ID Fixer
    Scans .sldtbl tables for firearms with null part IDs,
    uses DuckDuckGo + gpt-oss-120b to match or generate parts.

Tab 2 – Category Manager
    Steps through every item missing shop_category or armory_category,
    lets you edit all six category fields with optional AI suggestions.

Usage:  python firearm_fixer.py
Deps:   pip install customtkinter ddgs openai
"""

import json
import os
import threading
import argparse
import textwrap
import time
from tkinter import filedialog
from typing import Optional
import subprocess
import sys

import customtkinter

try:
    from ddgs import DDGS as _DDGS
except ImportError:
    try:
        from duckduckgo_search import DDGS as _DDGS
    except ImportError:
        _DDGS = None

from openai import OpenAI

# ─── Config ───────────────────────────────────────────────────────────────────

OPENROUTER_API_KEY = None  # Set your OpenRouter API key here or via environment variable OPENROUTER_API_KEY
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
MODEL = "nvidia/nemotron-3-super-120b-a12b:free"

# Known category values mined from the table (used as combo-box hints)
KNOWN_SHOP_CATEGORIES    = ["Ammunition", "Handguns", "Magazines", "Rifles", "Shotguns", "Weapon Parts"]
KNOWN_ARMORY_CATEGORIES  = [
    "Ammunition", "Assault Rifle", "Battle Rifle", "Designated Marksman Rifle",
    "General Purpose Machine Gun", "Handgun", "Handguns", "Light Machine Gun",
    "Long Range Rifle", "Magazines", "Parts", "Personal Defense Weapon",
    "Sniper Rifle", "Submachine Gun",
]

# ─── Data helpers ─────────────────────────────────────────────────────────────

def load_table(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_table(path: str, data: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

    if AUTOFORMAT_ON_SAVE:
        def _run_formatter(p: str):
            try:
                repo_root = os.path.dirname(os.path.dirname(__file__))
                script = os.path.join(repo_root, "scripts", "autoformat_table.py")
                if os.path.isfile(script):
                    args = [sys.executable, script, p]
                    if AUTOFORMAT_PRINT_OUTPUT:
                        subprocess.run(args)
                    else:
                        subprocess.run(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception:
                pass

        threading.Thread(target=_run_formatter, args=(path,), daemon=True).start()

def find_null_part_firearms(table_data: dict) -> list:
    results = []
    for subtable_name, items in (table_data.get("tables") or {}).items():
        if not isinstance(items, list):
            continue
        for item_idx, item in enumerate(items):
            if not isinstance(item, dict) or not item.get("firearm"):
                continue
            for part_idx, part in enumerate(item.get("parts") or []):
                if not isinstance(part, dict):
                    continue
                cur = part.get("current")
                is_null = (
                    cur is None
                    or (isinstance(cur, dict) and cur.get("id") is None)
                    or (isinstance(cur, str) and cur.strip().lower() == "null")
                )
                if is_null:
                    results.append({
                        "firearm_name":     item.get("name", "<unnamed>"),
                        "firearm_id":       item.get("id"),
                        "firearm_platform": item.get("platform", ""),
                        "firearm_caliber":  item.get("caliber", []),
                        "subtable":         subtable_name,
                        "part_name":        part.get("name", ""),
                        "part_slot":        part.get("slot", ""),
                        "part_type":        part.get("type", ""),
                        "part_index":       part_idx,
                        "item_index":       item_idx,
                    })
    return results

def get_all_parts(table_data: dict) -> list:
    return [i for i in (table_data.get("tables") or {}).get("parts") or [] if isinstance(i, dict)]

def next_available_id(table_data: dict) -> int:
    max_id = -1
    for items in (table_data.get("tables") or {}).values():
        if isinstance(items, list):
            for item in items:
                if isinstance(item, dict) and isinstance(item.get("id"), int):
                    max_id = max(max_id, item["id"])
    return max_id + 1

def apply_fix(table_data: dict, subtable: str, item_index: int, part_index: int, new_id: int):
    part = table_data["tables"][subtable][item_index]["parts"][part_index]
    if part.get("current") is None or isinstance(part["current"], str):
        part["current"] = {"id": new_id}
    else:
        part["current"]["id"] = new_id

def insert_new_part(table_data: dict, new_part: dict) -> int:
    parts_list = table_data.setdefault("tables", {}).setdefault("parts", [])
    new_id = next_available_id(table_data)
    new_part["id"] = new_id
    parts_list.append(new_part)
    return new_id

def find_missing_category_items(table_data: dict) -> list:
    """
    Return every item (across all subtables) that is missing
    shop_category OR armory_category.
    Each entry: subtable, item_index, id, name, type, platform, caliber,
                + current values of all 6 category fields.
    """
    results = []
    for subtable_name, items in (table_data.get("tables") or {}).items():
        if not isinstance(items, list):
            continue
        for idx, item in enumerate(items):
            if not isinstance(item, dict):
                continue
            missing_shop   = not bool(item.get("shop_category", "").strip())
            missing_armory = not bool(item.get("armory_category", "").strip())
            if missing_shop or missing_armory:
                results.append({
                    "subtable":           subtable_name,
                    "item_index":         idx,
                    "id":                 item.get("id"),
                    "name":               item.get("name", "<unnamed>"),
                    "type":               item.get("type", ""),
                    "platform":           item.get("platform", ""),
                    "caliber":            item.get("caliber", []),
                    "missing_shop":       missing_shop,
                    "missing_armory":     missing_armory,
                    # current values (may be empty string)
                    "shop_category":      item.get("shop_category", ""),
                    "shop_subcategory":   item.get("shop_subcategory", ""),
                    "shop_subcategory2":  item.get("shop_subcategory2", ""),
                    "armory_category":    item.get("armory_category", ""),
                    "armory_subcategory": item.get("armory_subcategory", ""),
                    "armory_subcategory2":item.get("armory_subcategory2", ""),
                })
    return results

def collect_known_subcategories(table_data: dict) -> tuple:
    """Return (shop_sub1, shop_sub2, armory_sub1, armory_sub2) as sorted lists."""
    s1, s2, a1, a2 = set(), set(), set(), set()
    for items in (table_data.get("tables") or {}).values():
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            if item.get("shop_subcategory"):   s1.add(item["shop_subcategory"])
            if item.get("shop_subcategory2"):  s2.add(item["shop_subcategory2"])
            if item.get("armory_subcategory"): a1.add(item["armory_subcategory"])
            if item.get("armory_subcategory2"):a2.add(item["armory_subcategory2"])
    return sorted(s1), sorted(s2), sorted(a1), sorted(a2)

# ─── AI helpers ───────────────────────────────────────────────────────────────

client = OpenAI(api_key=OPENROUTER_API_KEY, base_url=OPENROUTER_BASE_URL)

# AI interaction logging (controls whether prompts/responses are recorded)
AI_LOG_INTERACTIONS = True
AI_INTERACTIONS_LOGFILE = os.path.join(os.getcwd(), "ai_interactions.log")
AI_PRINT_INTERACTIONS = False

def _default_log_fn(msg: str):
    try:
        with open(AI_INTERACTIONS_LOGFILE, "a", encoding="utf-8") as f:
            f.write(msg + "\n")
    except Exception:
        pass

# Run autoformat_table.py after saving tables
AUTOFORMAT_ON_SAVE = True
AUTOFORMAT_PRINT_OUTPUT = False

def ddg_search(query: str, max_results: int = 5) -> str:
    if _DDGS is None:
        return "DuckDuckGo search unavailable — install the 'ddgs' package."
    try:
        with _DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
        if not results:
            return "No search results found."
        return "\n".join(f"* {r.get('title','')}: {r.get('body','')}" for r in results)
    except Exception as e:
        return f"(Search unavailable: {e})"

def _call_model(prompt: str, log_fn=None) -> str:
    if log_fn is None:
        log_fn = _default_log_fn if AI_LOG_INTERACTIONS else (lambda *a, **k: None)

    ts = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    try:
        if AI_LOG_INTERACTIONS:
            log_fn(f"--- AI REQUEST {ts} ---")
            log_fn(prompt)
    except Exception:
        pass

    resp = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=1024,
        temperature=0.1,
    )
    raw = resp.choices[0].message.content.strip()
    if raw.startswith("```"):
        parts = raw.split("```")
        raw = parts[1] if len(parts) > 1 else raw
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    try:
        if AI_LOG_INTERACTIONS:
            log_fn(f"--- AI RESPONSE {ts} ---")
            log_fn(raw)
            log_fn("--- END ---")
        if AI_PRINT_INTERACTIONS:
            print(f"[AI {ts}] {raw}")
    except Exception:
        pass

    return raw

def type_to_subcategory(part_type: str) -> str:
    mapping = {
        "barrel": "Barrels", "bolt": "Bolts",
        "bolt_carrier_group": "Bolt Carrier Groups",
        "buffer_spring": "Buffer Springs", "feed_tray": "Feed Trays",
        "gas_block": "Gas Blocks", "gas_piston": "Gas Pistons",
        "recoil_spring": "Recoil Springs",
        "secondary_recoil_spring": "Secondary Recoil Springs",
        "trigger_spring": "Trigger Springs",
    }
    return mapping.get(part_type, part_type.replace("_", " ").title() + "s")

def ask_ai_for_part(firearm_name, firearm_platform, firearm_caliber,
                    part_name, part_slot, part_type, available_parts,
                    next_id, log_fn=None) -> dict:
    caliber_str = (", ".join(firearm_caliber) if isinstance(firearm_caliber, list)
                   else str(firearm_caliber))
    search_query = f"{firearm_name} {part_name} {part_type} specifications"
    if log_fn: log_fn(f"  searching: {search_query}")
    web_ctx = ddg_search(search_query)
    catalogue = "\n".join(
        f"  ID {p.get('id')}: name={p.get('name','')!r}, slot={p.get('slot','')!r}, "
        f"platform={p.get('platform','')!r}, type={p.get('type','')!r}"
        for p in available_parts
    ) or "  (empty)"
    platform_title = firearm_platform.replace("-", " ").title() if firearm_platform else "Unknown"
    sub2 = f"{platform_title} {type_to_subcategory(part_type)}"
    caliber_specific_types = {"barrel", "bolt", "bolt_carrier_group", "feed_tray"}
    caliber_field = (json.dumps(firearm_caliber)
                     if part_type in caliber_specific_types and firearm_caliber else None)
    prompt = textwrap.dedent(f"""
        You are an expert gunsmith assistant for a tabletop RPG firearms database.
        Firearm: {firearm_name} | Platform: {firearm_platform} | Caliber: {caliber_str}
        Missing part slot: {part_slot} | Part type: {part_type} | Hint: {part_name}
        Web context: {web_ctx}
        Existing parts:
        {catalogue}
        Instructions:
        1. Try to find a genuine match (correct platform, slot, AND type). If found:
           {{"action":"match","id":<int>,"reason":"<one sentence>"}}
        2. If no genuine match, create a realistic new part:
           {{"action":"create","reason":"<why>","part":{{
             "name":"<Manufacturer Model OEM Part Name>",
             "value":<retail price float>,"description":"<one sentence>",
             "rarity":"<Common|Uncommon|Rare|Legendary|Mythic>",
             "random_quantity":false,"weight":<kg float>,
             "type":"{part_type}","platform":"{firearm_platform}","slot":"{part_slot}",
             {f'"caliber":{caliber_field},' if caliber_field else ""}
             "can_stack":false,"in_armory":true,"durability":"set_by_looting",
             "armory_category":"Parts","armory_subcategory":"{platform_title} Parts",
             "armory_subcategory2":"{sub2}","shop_category":"Weapon Parts",
             "shop_subcategory":"{platform_title} Parts","shop_subcategory2":"{sub2}"
           }}}}
        Respond with ONLY valid JSON, no markdown.
    """).strip()
    try:
        resp_text = _call_model(prompt, log_fn=log_fn)
        return json.loads(resp_text)
    except Exception as e:
        if log_fn: log_fn(f"  AI error: {e}")
        return {"action": "error", "reason": str(e), "id": None, "part": None}

def ask_ai_for_categories(item_name: str, item_type: str, platform: str,
                           caliber, subtable: str,
                           existing_shop: str, existing_armory: str,
                           log_fn=None) -> dict:
    """
    Ask the model to suggest all 6 category fields for an item.
    Returns a dict with keys: shop_category, shop_subcategory, shop_subcategory2,
                               armory_category, armory_subcategory, armory_subcategory2
    """
    caliber_str = (", ".join(caliber) if isinstance(caliber, list) else str(caliber))
    search_query = f"{item_name} {item_type} firearm category classification"
    if log_fn: log_fn(f"  searching: {search_query}")
    web_ctx = ddg_search(search_query)

    prompt = textwrap.dedent(f"""
        You are an expert gunsmith assistant categorising items for a tabletop RPG
        firearms database.

        Item name    : {item_name}
        Item type    : {item_type}
        Platform     : {platform}
        Caliber      : {caliber_str}
        Subtable     : {subtable}
        Existing shop_category   : {existing_shop!r}
        Existing armory_category : {existing_armory!r}

        Web context:
        {web_ctx}

        Known shop_category values  : {KNOWN_SHOP_CATEGORIES}
        Known armory_category values: {KNOWN_ARMORY_CATEGORIES}

        Rules:
        - shop_category is REQUIRED. Pick the best fit from the known list, or create
          a sensible new one if none applies.
        - All other fields are optional — use empty string "" if not applicable.
        - armory_category should reflect the weapon class (e.g. "Handgun",
          "Assault Rifle", "Magazines", "Parts").
        - subcategory fields should follow patterns like "Glock Parts", "AR-15 Parts",
          "Glock Magazines", "Glock Barrels" etc.
        - If existing_shop_category or existing_armory_category is already filled,
          keep it unless it is clearly wrong.

        Respond with ONLY a JSON object, no markdown:
        {{
          "shop_category":      "<value>",
          "shop_subcategory":   "<value or empty>",
          "shop_subcategory2":  "<value or empty>",
          "armory_category":    "<value or empty>",
          "armory_subcategory": "<value or empty>",
          "armory_subcategory2":"<value or empty>"
        }}
    """).strip()
    try:
        resp_text = _call_model(prompt, log_fn=log_fn)
        return json.loads(resp_text)
    except Exception as e:
        if log_fn: log_fn(f"  AI error: {e}")
        return {}

def check_ai_api(timeout: float = 6.0) -> tuple:
    """
    Quick connectivity check for the AI API.
    Returns (True, message) on success, (False, error_message) on failure.
    """
    try:
        # Try a lightweight call to list models (should be fast and not consume tokens)
        resp = client.models.list()
        models_count = None
        if hasattr(resp, "data"):
            models_count = len(resp.data) if resp.data is not None else 0
        elif isinstance(resp, dict) and "data" in resp:
            models_count = len(resp["data"]) if resp["data"] is not None else 0
        else:
            models_count = 1
        return True, f"AI reachable ({models_count} model(s))"
    except Exception as e:
        return False, f"AI unreachable: {e}"

# ─── UI Colours ───────────────────────────────────────────────────────────────

ERROR_COLOR   = "#e05555"
WARN_COLOR    = "#e0a030"
OK_COLOR      = "#50c878"
HEAD_COLOR    = "#5dade2"
INFO_COLOR    = "#aaaaaa"
PREFILLED_BG  = "#2a3a2a"   # dark green tint — field was already set
EMPTY_BG      = "#1a1a2e"   # dark blue tint — field was empty


# ─── Folder-picker dialog ─────────────────────────────────────────────────────

class FolderPicker(customtkinter.CTkToplevel):
    def __init__(self, parent, default_path: str):
        super().__init__(parent)
        self.title("Select Tables Directory")
        self.geometry("560x185")
        self.resizable(False, False)
        self.attributes("-topmost", True)
        self.result: Optional[str] = None
        self.grab_set()

        customtkinter.CTkLabel(
            self, text="Choose the folder containing your .sldtbl table files:",
            font=customtkinter.CTkFont(size=13), anchor="w",
        ).pack(fill="x", padx=16, pady=(16, 4))

        row = customtkinter.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=4)
        row.columnconfigure(0, weight=1)
        self._path_var = customtkinter.StringVar(value=default_path)
        customtkinter.CTkEntry(row, textvariable=self._path_var,
                               font=customtkinter.CTkFont(size=12),
                               ).grid(row=0, column=0, sticky="ew", padx=(0, 8))
        customtkinter.CTkButton(row, text="Browse…", width=90,
                                command=self._browse).grid(row=0, column=1)

        self._err_lbl = customtkinter.CTkLabel(self, text="",
                                               text_color=ERROR_COLOR,
                                               font=customtkinter.CTkFont(size=11))
        self._err_lbl.pack(fill="x", padx=16)

        btn_row = customtkinter.CTkFrame(self, fg_color="transparent")
        btn_row.pack(fill="x", padx=16, pady=(4, 12))
        customtkinter.CTkButton(btn_row, text="Open", width=100,
                                command=self._confirm).pack(side="right", padx=(8, 0))
        customtkinter.CTkButton(btn_row, text="Cancel", width=80,
                                fg_color="#555", hover_color="#444",
                                command=self.destroy).pack(side="right")
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.wait_window()

    def _browse(self):
        chosen = filedialog.askdirectory(title="Select tables directory",
                                         initialdir=self._path_var.get() or os.getcwd())
        if chosen:
            self._path_var.set(chosen)

    def _confirm(self):
        path = self._path_var.get().strip()
        if not os.path.isdir(path):
            self._err_lbl.configure(text=f"Directory not found: {path}")
            return
        self.result = path
        self.destroy()


# ─── Category Manager Tab ─────────────────────────────────────────────────────

def build_category_tree(table_data: dict) -> dict:
    """
    Build a nested dict representing the full shop and armory category trees.
    Returns:
      {
        "shop":   { cat: { sub1: {sub2, ...}, ... }, ... },
        "armory": { cat: { sub1: {sub2, ...}, ... }, ... },
      }
    All keys/values are strings; empty string means "no subcategory".
    """
    from collections import defaultdict
    shop   = defaultdict(lambda: defaultdict(set))
    armory = defaultdict(lambda: defaultdict(set))
    for items in (table_data.get("tables") or {}).values():
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            sc  = (item.get("shop_category")   or "").strip()
            ss1 = (item.get("shop_subcategory") or "").strip()
            ss2 = (item.get("shop_subcategory2") or "").strip()
            ac  = (item.get("armory_category")   or "").strip()
            as1 = (item.get("armory_subcategory") or "").strip()
            as2 = (item.get("armory_subcategory2") or "").strip()
            if sc:
                shop[sc][ss1].add(ss2)
            if ac:
                armory[ac][as1].add(as2)
    # Convert to plain dicts with sorted lists for stable rendering
    def _freeze(d):
        return {k: {s1: sorted(s for s in s2s) for s1, s2s in sorted(subs.items())}
                for k, subs in sorted(d.items())}
    return {"shop": _freeze(shop), "armory": _freeze(armory)}


class CategoryTreeSidebar(customtkinter.CTkFrame):
    """
    Collapsible tree sidebar showing the full shop + armory category hierarchy.
    Highlighted nodes follow the currently-edited item.
    """
    # Indent per level in pixels (simulated with leading spaces in label text)
    _INDENT = ("", "  ", "    ")          # level 0,1,2
    _CAT_COLOR    = "#c9d1d9"
    _SUB1_COLOR   = "#8b949e"
    _SUB2_COLOR   = "#6e7681"
    _HL_BG        = "#1f3a5f"             # highlight background — active node
    _HL_COLOR     = "#79c0ff"             # highlight text colour
    _SEC_COLOR    = HEAD_COLOR            # section header colour

    def __init__(self, parent):
        super().__init__(parent, fg_color="#161b22", corner_radius=8, width=240)
        self.pack_propagate(False)
        self.configure(width=240)

        self._tree: dict = {}
        self._active_shop   = ("", "", "")   # (cat, sub1, sub2)
        self._active_armory = ("", "", "")

        # Collapse state: key = ("shop"|"armory", cat, sub1)  value = bool collapsed
        self._collapsed: dict = {}

        self._build_header()

        self._scroll = customtkinter.CTkScrollableFrame(
            self, fg_color="transparent", width=226)
        self._scroll.pack(fill="both", expand=True, padx=4, pady=(0, 4))

        self._row_widgets: list = []   # list of (widget, meta) for highlight tracking

    def _build_header(self):
        hdr = customtkinter.CTkFrame(self, fg_color="#0d1117", corner_radius=0)
        hdr.pack(fill="x", padx=0, pady=(0, 4))
        customtkinter.CTkLabel(
            hdr, text="Category Browser",
            font=customtkinter.CTkFont(size=12, weight="bold"),
            text_color=HEAD_COLOR, anchor="w",
        ).pack(fill="x", padx=10, pady=6)

        btn_row = customtkinter.CTkFrame(hdr, fg_color="transparent")
        btn_row.pack(fill="x", padx=6, pady=(0, 6))
        customtkinter.CTkButton(
            btn_row, text="Expand All", width=90,
            font=customtkinter.CTkFont(size=10),
            fg_color="#21262d", hover_color="#30363d",
            command=self._expand_all,
        ).pack(side="left", padx=2)
        customtkinter.CTkButton(
            btn_row, text="Collapse All", width=90,
            font=customtkinter.CTkFont(size=10),
            fg_color="#21262d", hover_color="#30363d",
            command=self._collapse_all,
        ).pack(side="left", padx=2)

    def load_tree(self, tree: dict):
        self._tree = tree
        self._collapsed.clear()
        self._render()

    def highlight(self, shop_vals: tuple, armory_vals: tuple):
        """
        shop_vals  = (shop_category, shop_subcategory, shop_subcategory2)
        armory_vals = (armory_category, armory_subcategory, armory_subcategory2)
        """
        self._active_shop   = tuple(v.strip() for v in shop_vals)
        self._active_armory = tuple(v.strip() for v in armory_vals)
        self._apply_highlights()
        self._ensure_active_visible()

    def _render(self):
        for w in self._scroll.winfo_children():
            w.destroy()
        self._row_widgets.clear()

        for section_key, section_label in [("shop", "Shop"), ("armory", "Armory")]:
            tree_section = self._tree.get(section_key, {})

            # Section header
            sec_lbl = customtkinter.CTkLabel(
                self._scroll,
                text=f"▸ {section_label}",
                font=customtkinter.CTkFont(size=12, weight="bold"),
                text_color=self._SEC_COLOR,
                anchor="w", cursor="hand2",
            )
            sec_lbl.pack(fill="x", padx=4, pady=(8, 2))
            self._row_widgets.append((sec_lbl, {"kind": "section", "section": section_key}))

            for cat, subs in sorted(tree_section.items()):
                ckey = (section_key, cat, "")
                collapsed_cat = self._collapsed.get(ckey, False)

                # Category row (level 0) — clickable to collapse
                cat_frame = customtkinter.CTkFrame(
                    self._scroll, fg_color="transparent", corner_radius=4)
                cat_frame.pack(fill="x", padx=2, pady=1)

                toggle_text = "▸ " if collapsed_cat else "▾ "
                cat_lbl = customtkinter.CTkLabel(
                    cat_frame,
                    text=toggle_text + cat,
                    font=customtkinter.CTkFont(size=11, weight="bold"),
                    text_color=self._CAT_COLOR,
                    anchor="w", cursor="hand2",
                )
                cat_lbl.pack(fill="x", padx=6, pady=1)
                cat_lbl.bind("<Button-1>", lambda e, k=ckey: self._toggle(k))
                self._row_widgets.append((cat_frame, {
                    "kind": "cat", "section": section_key,
                    "cat": cat, "sub1": "", "sub2": "",
                    "frame": cat_frame,
                }))

                if collapsed_cat:
                    continue

                for sub1, sub2s in sorted(subs.items()):
                    s1key = (section_key, cat, sub1)
                    collapsed_sub1 = self._collapsed.get(s1key, False)

                    if sub1:
                        # sub1 row (level 1)
                        s1_frame = customtkinter.CTkFrame(
                            self._scroll, fg_color="transparent", corner_radius=4)
                        s1_frame.pack(fill="x", padx=2, pady=0)

                        has_sub2 = any(s for s in sub2s if s)
                        toggle = ("▸ " if collapsed_sub1 else "▾ ") if has_sub2 else "  "
                        s1_lbl = customtkinter.CTkLabel(
                            s1_frame,
                            text="  " + toggle + sub1,
                            font=customtkinter.CTkFont(size=10),
                            text_color=self._SUB1_COLOR,
                            anchor="w",
                            cursor="hand2" if has_sub2 else "",
                        )
                        s1_lbl.pack(fill="x", padx=6, pady=0)
                        if has_sub2:
                            s1_lbl.bind("<Button-1>", lambda e, k=s1key: self._toggle(k))
                        self._row_widgets.append((s1_frame, {
                            "kind": "sub1", "section": section_key,
                            "cat": cat, "sub1": sub1, "sub2": "",
                            "frame": s1_frame,
                        }))

                        if collapsed_sub1:
                            continue

                    for sub2 in sorted(sub2s):
                        if not sub2:
                            continue
                        s2_frame = customtkinter.CTkFrame(
                            self._scroll, fg_color="transparent", corner_radius=4)
                        s2_frame.pack(fill="x", padx=2, pady=0)
                        s2_lbl = customtkinter.CTkLabel(
                            s2_frame,
                            text="      • " + sub2,
                            font=customtkinter.CTkFont(size=10),
                            text_color=self._SUB2_COLOR,
                            anchor="w",
                        )
                        s2_lbl.pack(fill="x", padx=6, pady=0)
                        self._row_widgets.append((s2_frame, {
                            "kind": "sub2", "section": section_key,
                            "cat": cat, "sub1": sub1, "sub2": sub2,
                            "frame": s2_frame,
                        }))

        self._apply_highlights()

    def _toggle(self, key: tuple):
        self._collapsed[key] = not self._collapsed.get(key, False)
        self._render()

    def _expand_all(self):
        self._collapsed.clear()
        self._render()

    def _collapse_all(self):
        for section_key, tree_section in self._tree.items():
            for cat, subs in tree_section.items():
                self._collapsed[(section_key, cat, "")] = True
                for sub1 in subs:
                    if sub1:
                        self._collapsed[(section_key, cat, sub1)] = True
        self._render()

    def _apply_highlights(self):
        for widget, meta in self._row_widgets:
            if meta.get("kind") not in ("cat", "sub1", "sub2"):
                continue
            section = meta["section"]
            active  = self._active_shop if section == "shop" else self._active_armory
            a_cat, a_sub1, a_sub2 = active

            is_active = False
            kind = meta["kind"]
            if kind == "cat":
                is_active = (meta["cat"] == a_cat and a_cat != "")
            elif kind == "sub1":
                is_active = (meta["cat"] == a_cat and meta["sub1"] == a_sub1
                             and a_sub1 != "")
            elif kind == "sub2":
                is_active = (meta["cat"] == a_cat and meta["sub1"] == a_sub1
                             and meta["sub2"] == a_sub2 and a_sub2 != "")

            try:
                frame = meta.get("frame", widget)
                frame.configure(fg_color=self._HL_BG if is_active else "transparent")
                # Recolour the label inside
                for child in frame.winfo_children():
                    if isinstance(child, customtkinter.CTkLabel):
                        child.configure(
                            text_color=self._HL_COLOR if is_active else (
                                self._CAT_COLOR if kind == "cat" else
                                self._SUB1_COLOR if kind == "sub1" else
                                self._SUB2_COLOR
                            )
                        )
            except Exception:
                pass

    def _ensure_active_visible(self):
        # Expand any collapsed ancestors of active nodes
        changed = False
        for section_key, active in [("shop", self._active_shop), ("armory", self._active_armory)]:
            a_cat, a_sub1, _ = active
            if not a_cat:
                continue
            if self._collapsed.get((section_key, a_cat, ""), False):
                self._collapsed[(section_key, a_cat, "")] = False
                changed = True
            if a_sub1 and self._collapsed.get((section_key, a_cat, a_sub1), False):
                self._collapsed[(section_key, a_cat, a_sub1)] = False
                changed = True
        if changed:
            self._render()


class CategoryManagerTab(customtkinter.CTkFrame):
    """
    Category Manager tab — steps through items missing shop/armory categories,
    lets the user edit all six fields, with an optional AI suggest button.
    A live sidebar tree shows the full category hierarchy with the current
    item's categories highlighted.
    """
    CAT_FIELDS = [
        ("shop_category",       "Shop Category *",      True,  "shop"),
        ("shop_subcategory",    "Shop Subcategory",     False, "shop"),
        ("shop_subcategory2",   "Shop Subcategory 2",   False, "shop"),
        ("armory_category",     "Armory Category",      False, "armory"),
        ("armory_subcategory",  "Armory Subcategory",   False, "armory"),
        ("armory_subcategory2", "Armory Subcategory 2", False, "armory"),
    ]

    def __init__(self, parent, get_table_data, get_table_path, save_callback, log_fn):
        super().__init__(parent, fg_color="transparent")
        self._get_table_data = get_table_data
        self._get_table_path = get_table_path
        self._save_callback  = save_callback
        self._log            = log_fn

        self._items:      list  = []
        self._cursor:     int   = 0
        self._ai_running: bool  = False
        self._known_sub:  tuple = ([], [], [], [])
        self._vars:       dict  = {}
        self._was_empty:  dict  = {}

        self._build_ui()
        # Wire up live sidebar updates whenever any field changes
        for key in ("shop_category", "shop_subcategory", "shop_subcategory2",
                    "armory_category", "armory_subcategory", "armory_subcategory2"):
            self._vars[key].trace_add("write", lambda *_, k=key: self._on_field_change())

    # ── Build ──────────────────────────────────────────────────────────────

    def _build_ui(self):
        self.columnconfigure(0, weight=1)   # main area
        self.columnconfigure(1, weight=0)   # sidebar (fixed width)
        self.rowconfigure(1, weight=1)

        # ── Top toolbar ───────────────────────────────────────────────────
        toolbar = customtkinter.CTkFrame(self, fg_color="transparent")
        toolbar.grid(row=0, column=0, columnspan=2, sticky="ew", padx=8, pady=(8, 4))

        customtkinter.CTkButton(
            toolbar, text="🔍 Scan Missing", width=140,
            command=self.scan,
        ).pack(side="left", padx=(0, 6))

        customtkinter.CTkButton(
            toolbar, text="💾 Save Table", width=120,
            fg_color=WARN_COLOR, hover_color="#c0862a",
            command=self._save,
        ).pack(side="left", padx=6)

        self._progress_lbl = customtkinter.CTkLabel(
            toolbar, text="", font=customtkinter.CTkFont(size=12))
        self._progress_lbl.pack(side="left", padx=12)

        nav = customtkinter.CTkFrame(toolbar, fg_color="transparent")
        nav.pack(side="right")
        self._prev_btn = customtkinter.CTkButton(
            nav, text="◀ Prev", width=80, command=self._go_prev)
        self._prev_btn.pack(side="left", padx=4)
        self._next_btn = customtkinter.CTkButton(
            nav, text="Next ▶", width=80,
            fg_color="#2ecc71", hover_color="#27ae60",
            command=self._go_next)
        self._next_btn.pack(side="left", padx=4)

        # ── Main editing area ─────────────────────────────────────────────
        content = customtkinter.CTkFrame(self)
        content.grid(row=1, column=0, sticky="nsew", padx=(8, 4), pady=(0, 8))
        content.columnconfigure(0, weight=1)
        content.rowconfigure(1, weight=1)

        self._item_hdr = customtkinter.CTkLabel(
            content, text="Load a table and click Scan to begin.",
            font=customtkinter.CTkFont(size=14, weight="bold"),
            anchor="w", text_color=HEAD_COLOR,
        )
        self._item_hdr.grid(row=0, column=0, sticky="ew", padx=12, pady=(10, 2))

        self._item_sub = customtkinter.CTkLabel(
            content, text="",
            font=customtkinter.CTkFont(size=11), anchor="w", text_color=INFO_COLOR,
        )
        self._item_sub.grid(row=0, column=0, sticky="ew", padx=12, pady=(30, 2))

        fields_frame = customtkinter.CTkScrollableFrame(content, fg_color="transparent")
        fields_frame.grid(row=1, column=0, sticky="nsew", padx=4, pady=4)
        fields_frame.columnconfigure(1, weight=1)

        self._field_widgets = {}
        row_idx = 0
        last_section = None

        for key, label, required, section in self.CAT_FIELDS:
            if section != last_section:
                last_section = section
                section_title = "Shop Categories" if section == "shop" else "Armory Categories"
                customtkinter.CTkFrame(fields_frame, fg_color="#333", height=1).grid(
                    row=row_idx, column=0, columnspan=2, sticky="ew", padx=4, pady=(10, 2))
                row_idx += 1
                customtkinter.CTkLabel(
                    fields_frame, text=section_title,
                    font=customtkinter.CTkFont(size=12, weight="bold"),
                    text_color=HEAD_COLOR,
                ).grid(row=row_idx, column=0, columnspan=2, sticky="w", padx=4, pady=(0, 6))
                row_idx += 1

            customtkinter.CTkLabel(
                fields_frame, text=label,
                font=customtkinter.CTkFont(size=12), anchor="e", width=160,
            ).grid(row=row_idx, column=0, sticky="e", padx=(8, 6), pady=3)

            var = customtkinter.StringVar()
            self._vars[key] = var

            entry = customtkinter.CTkEntry(
                fields_frame, textvariable=var,
                font=customtkinter.CTkFont(size=12),
                placeholder_text=f"Enter {label.rstrip(' *').lower()}…",
            )
            entry.grid(row=row_idx, column=1, sticky="ew", padx=(0, 8), pady=3)
            self._field_widgets[key] = {"entry": entry}
            row_idx += 1

        # AI button row
        ai_row = customtkinter.CTkFrame(fields_frame, fg_color="transparent")
        ai_row.grid(row=row_idx, column=0, columnspan=2, sticky="ew", pady=(14, 4), padx=4)
        self._ai_btn = customtkinter.CTkButton(
            ai_row, text="🤖 AI Suggest All Fields", width=200,
            fg_color="#8e44ad", hover_color="#6c3483",
            command=self._ai_suggest,
        )
        self._ai_btn.pack(side="left", padx=4)
        self._ai_status = customtkinter.CTkLabel(
            ai_row, text="", font=customtkinter.CTkFont(size=11), text_color=INFO_COLOR)
        self._ai_status.pack(side="left", padx=8)
        row_idx += 1

        # Legend
        legend_frame = customtkinter.CTkFrame(fields_frame, fg_color="transparent")
        legend_frame.grid(row=row_idx, column=0, columnspan=2, sticky="w", padx=4, pady=(8, 4))
        for color, lbl_text in [(PREFILLED_BG, "Already had a value"), (EMPTY_BG, "Was empty")]:
            customtkinter.CTkFrame(legend_frame, width=14, height=14,
                                   fg_color=color, corner_radius=3).pack(side="left", padx=(0, 4))
            customtkinter.CTkLabel(legend_frame, text=lbl_text,
                                   font=customtkinter.CTkFont(size=10),
                                   text_color=INFO_COLOR).pack(side="left", padx=(0, 12))

        # ── Sidebar tree ──────────────────────────────────────────────────
        self._sidebar = CategoryTreeSidebar(self)
        self._sidebar.grid(row=1, column=1, sticky="nsew", padx=(0, 8), pady=(0, 8))

        self._update_nav_buttons()

    # ── Scan ──────────────────────────────────────────────────────────────

    def scan(self):
        td = self._get_table_data()
        if not td:
            return
        self._items = find_missing_category_items(td)
        self._known_sub = collect_known_subcategories(td)
        self._cursor = 0
        # Always rebuild the full tree from the live table data
        tree = build_category_tree(td)
        self._sidebar.load_tree(tree)
        total = len(self._items)
        if total == 0:
            self._item_hdr.configure(text="All items have categories — nothing to do!")
            self._item_sub.configure(text="")
            self._progress_lbl.configure(text="Complete ✓", text_color=OK_COLOR)
        else:
            self._log(f"Category scan: {total} item(s) missing categories.", "warn")
            self._show_current()
        self._update_nav_buttons()

    # ── Navigation ────────────────────────────────────────────────────────

    def _go_prev(self):
        if self._cursor > 0:
            self._commit_current()
            self._cursor -= 1
            self._show_current()
        self._update_nav_buttons()

    def _go_next(self):
        if not self._items:
            return
        if not self._vars["shop_category"].get().strip():
            self._ai_status.configure(
                text="⚠ shop_category is required before moving on.",
                text_color=ERROR_COLOR)
            return
        self._commit_current()
        if self._cursor < len(self._items) - 1:
            self._cursor += 1
            self._show_current()
        else:
            self._item_hdr.configure(text="All done! Save the table to write changes.")
            self._item_sub.configure(text="")
            self._progress_lbl.configure(
                text=f"Finished — {len(self._items)} item(s) reviewed",
                text_color=OK_COLOR)
            # Rebuild sidebar with any new categories that were added
            td = self._get_table_data()
            if td:
                self._sidebar.load_tree(build_category_tree(td))
        self._update_nav_buttons()

    def _update_nav_buttons(self):
        total = len(self._items)
        self._prev_btn.configure(state="normal" if self._cursor > 0 else "disabled")
        at_end = (total == 0 or self._cursor >= total - 1)
        self._next_btn.configure(state="normal" if not at_end else "disabled")

    # ── Show item ─────────────────────────────────────────────────────────

    def _show_current(self):
        if not self._items:
            return
        entry = self._items[self._cursor]
        total = len(self._items)

        self._progress_lbl.configure(
            text=f"Item {self._cursor + 1} of {total}", text_color=INFO_COLOR)

        missing_flags = []
        if entry["missing_shop"]:   missing_flags.append("shop_category")
        if entry["missing_armory"]: missing_flags.append("armory_category")

        self._item_hdr.configure(
            text=f"[{entry['subtable']}]  {entry['name']}  (ID {entry['id']})")
        cal = entry["caliber"]
        cal_str = ", ".join(cal) if isinstance(cal, list) else str(cal)
        self._item_sub.configure(
            text=f"type: {entry['type']}  |  platform: {entry['platform']}"
                 + (f"  |  caliber: {cal_str}" if cal_str else "")
                 + (f"  |  missing: {', '.join(missing_flags)}" if missing_flags else ""))

        # Populate fields with colours
        for key, _, _, _ in self.CAT_FIELDS:
            current_val = entry.get(key, "")
            was_empty = not bool(current_val.strip())
            self._was_empty[key] = was_empty
            self._vars[key].set(current_val)
            bg = EMPTY_BG if was_empty else PREFILLED_BG
            try:
                self._field_widgets[key]["entry"].configure(fg_color=bg)
            except Exception:
                pass

        self._ai_status.configure(text="")
        self._update_sidebar_highlight()

    # ── Sidebar highlight ─────────────────────────────────────────────────

    def _on_field_change(self):
        """Called on every field edit — updates sidebar highlight live."""
        self._update_sidebar_highlight()

    def _update_sidebar_highlight(self):
        shop_vals   = (self._vars["shop_category"].get(),
                       self._vars["shop_subcategory"].get(),
                       self._vars["shop_subcategory2"].get())
        armory_vals = (self._vars["armory_category"].get(),
                       self._vars["armory_subcategory"].get(),
                       self._vars["armory_subcategory2"].get())
        self._sidebar.highlight(shop_vals, armory_vals)

    # ── Commit edits ──────────────────────────────────────────────────────

    def _commit_current(self):
        if not self._items:
            return
        entry = self._items[self._cursor]
        td = self._get_table_data()
        if not td:
            return
        item = td["tables"][entry["subtable"]][entry["item_index"]]
        for key, _, _, _ in self.CAT_FIELDS:
            val = self._vars[key].get().strip()
            if val:
                item[key] = val
        # After committing, rebuild sidebar tree so new categories appear immediately
        self._sidebar.load_tree(build_category_tree(td))

    # ── AI suggest ────────────────────────────────────────────────────────

    def _ai_suggest(self):
        if self._ai_running or not self._items:
            return
        threading.Thread(target=self._ai_suggest_worker, daemon=True).start()

    def _ai_suggest_worker(self):
        self._ai_running = True
        self.after(0, lambda: self._ai_status.configure(
            text="AI working…", text_color=HEAD_COLOR))
        entry = self._items[self._cursor]
        self._log(f"\n[AI Categories] {entry['name']} ({entry['subtable']})", "head")

        result = ask_ai_for_categories(
            item_name=entry["name"],
            item_type=entry["type"],
            platform=entry["platform"],
            caliber=entry["caliber"],
            subtable=entry["subtable"],
            existing_shop=self._vars["shop_category"].get(),
            existing_armory=self._vars["armory_category"].get(),
            log_fn=self._log,
        )

        if result:
            def _apply():
                for key, _, _, _ in self.CAT_FIELDS:
                    if key in result and result[key]:
                        self._vars[key].set(result[key])
                        try:
                            self._field_widgets[key]["entry"].configure(fg_color=PREFILLED_BG)
                        except Exception:
                            pass
                self._ai_status.configure(
                    text="AI suggestions applied — review and click Next ▶",
                    text_color=OK_COLOR)
                self._log(f"  shop={result.get('shop_category','')!r}, "
                          f"armory={result.get('armory_category','')!r}", "ok")
            self.after(0, _apply)
        else:
            self.after(0, lambda: self._ai_status.configure(
                text="AI returned no result.", text_color=ERROR_COLOR))

        self._ai_running = False

    # ── Save ──────────────────────────────────────────────────────────────

    def _save(self):
        self._commit_current()
        self._save_callback()


# ─── Main application ─────────────────────────────────────────────────────────

class FirearmFixerApp(customtkinter.CTk):
    def __init__(self, tables_dir: str):
        super().__init__()
        self.title("DOOM-Tools Table Manager")
        self.geometry("1200x780")
        self.minsize(900, 550)

        self._tables_dir = tables_dir
        self._table_data: Optional[dict] = None
        self._table_path: Optional[str] = None
        self._null_parts: list = []
        self._available_parts: list = []
        self._ai_running = False

        self._build_ui()
        self._populate_table_selector()
        # Start background AI connectivity check (non-blocking)
        threading.Thread(target=self._background_ai_check, daemon=True).start()

    # ── Build UI ──────────────────────────────────────────────────────────

    def _build_ui(self):
        # ── Global top bar (shared across tabs) ───────────────────────────
        top = customtkinter.CTkFrame(self, fg_color="transparent")
        top.pack(fill="x", padx=12, pady=(10, 4))

        customtkinter.CTkLabel(
            top, text="Table:",
            font=customtkinter.CTkFont(size=13, weight="bold"),
        ).pack(side="left")

        self._table_var = customtkinter.StringVar()
        self._table_menu = customtkinter.CTkOptionMenu(
            top, variable=self._table_var, width=290,
            command=self._on_table_selected,
            font=customtkinter.CTkFont(size=12),
        )
        self._table_menu.pack(side="left", padx=8)

        customtkinter.CTkButton(
            top, text="📂 Change Folder", width=140,
            fg_color="#555", hover_color="#444",
            command=self._change_folder,
        ).pack(side="left", padx=4)

        self._status_lbl = customtkinter.CTkLabel(
            top, text="", anchor="e",
            font=customtkinter.CTkFont(size=12),
        )
        self._status_lbl.pack(side="right", fill="x", expand=True)

        # ── Tab view ──────────────────────────────────────────────────────
        self._tabs = customtkinter.CTkTabview(self)
        self._tabs.pack(fill="both", expand=True, padx=12, pady=(0, 8))

        self._tabs.add("🔧 Parts ID Fixer")
        self._tabs.add("🏷 Category Manager")

        self._build_parts_tab(self._tabs.tab("🔧 Parts ID Fixer"))
        self._build_category_tab(self._tabs.tab("🏷 Category Manager"))

    # ── Parts ID Fixer tab ────────────────────────────────────────────────

    def _build_parts_tab(self, parent):
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(1, weight=1)

        # Tab-level toolbar
        toolbar = customtkinter.CTkFrame(parent, fg_color="transparent")
        toolbar.grid(row=0, column=0, sticky="ew", padx=0, pady=(4, 4))

        for text, color, hover, cmd in [
            ("🔍 Scan",       "#1f6aa5", "#174f80", self._scan_table),
            ("⚡ AI-Fix All", "#2ecc71", "#27ae60", self._ai_fix_all),
            ("💾 Save",       WARN_COLOR,"#c0862a", self._save_table),
        ]:
            customtkinter.CTkButton(
                toolbar, text=text, width=110,
                fg_color=color, hover_color=hover, command=cmd,
            ).pack(side="left", padx=4)

        # Split pane
        split = customtkinter.CTkFrame(parent, fg_color="transparent")
        split.grid(row=1, column=0, sticky="nsew")
        split.columnconfigure(0, weight=2)
        split.columnconfigure(1, weight=3)
        split.rowconfigure(0, weight=1)

        # Left — parts list
        left = customtkinter.CTkFrame(split)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        left.rowconfigure(1, weight=1)
        left.columnconfigure(0, weight=1)
        customtkinter.CTkLabel(
            left, text="Firearms with Null Part IDs",
            font=customtkinter.CTkFont(size=13, weight="bold"), anchor="w",
        ).grid(row=0, column=0, sticky="w", padx=8, pady=(8, 4))
        self._parts_box = customtkinter.CTkScrollableFrame(left)
        self._parts_box.grid(row=1, column=0, sticky="nsew", padx=4, pady=(0, 8))
        self._part_widgets: list = []

        # Right — log
        right = customtkinter.CTkFrame(split)
        right.grid(row=0, column=1, sticky="nsew")
        right.rowconfigure(1, weight=1)
        right.columnconfigure(0, weight=1)
        hdr = customtkinter.CTkFrame(right, fg_color="transparent")
        hdr.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 4))
        customtkinter.CTkLabel(
            hdr, text="AI Activity Log",
            font=customtkinter.CTkFont(size=13, weight="bold"), anchor="w",
        ).pack(side="left")
        customtkinter.CTkButton(
            hdr, text="Clear", width=60,
            font=customtkinter.CTkFont(size=11),
            command=self._clear_log,
        ).pack(side="right")
        self._log_box = customtkinter.CTkTextbox(
            right, wrap="word",
            font=customtkinter.CTkFont(family="Consolas", size=12),
            state="disabled",
        )
        self._log_box.grid(row=1, column=0, sticky="nsew", padx=4, pady=(0, 8))
        for tag, color in [("ok", OK_COLOR), ("error", ERROR_COLOR),
                           ("warn", WARN_COLOR), ("head", HEAD_COLOR), ("info", INFO_COLOR)]:
            self._log_box.tag_config(tag, foreground=color)

    # ── Category Manager tab ──────────────────────────────────────────────

    def _build_category_tab(self, parent):
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)

        self._cat_tab = CategoryManagerTab(
            parent,
            get_table_data=lambda: self._table_data,
            get_table_path=lambda: self._table_path,
            save_callback=self._save_table,
            log_fn=self._log,
        )
        self._cat_tab.grid(row=0, column=0, sticky="nsew")

    # ── Logging (shared) ──────────────────────────────────────────────────

    def _log(self, text: str, tag: str = ""):
        def _do():
            self._log_box.configure(state="normal")
            self._log_box.insert("end", text + "\n", tag if tag else ())
            self._log_box.see("end")
            self._log_box.configure(state="disabled")
        self.after(0, _do)

    def _clear_log(self):
        self._log_box.configure(state="normal")
        self._log_box.delete("1.0", "end")
        self._log_box.configure(state="disabled")

    def _set_status(self, text: str, color: str = "white"):
        self.after(0, lambda: self._status_lbl.configure(text=text, text_color=color))

    def _background_ai_check(self):
        """Background thread: check AI API connectivity and update status."""
        try:
            self._set_status("Checking AI connectivity…", INFO_COLOR)
            ok, msg = check_ai_api()
            color = OK_COLOR if ok else ERROR_COLOR
            self._set_status(msg, color)
            self._log(f"AI check: {msg}", "info" if ok else "error")
        except Exception as e:
            self._set_status(f"AI check failed: {e}", ERROR_COLOR)
            self._log(f"AI check exception: {e}", "error")

    # ── Folder management ─────────────────────────────────────────────────

    def _change_folder(self):
        picker = FolderPicker(self, self._tables_dir)
        if picker.result:
            self._tables_dir = picker.result
            self._log(f"Folder: {self._tables_dir}", "info")
            self._populate_table_selector()

    def _populate_table_selector(self):
        if not os.path.isdir(self._tables_dir):
            self._log(f"Tables directory not found: {self._tables_dir}", "error")
            return
        files = sorted(f for f in os.listdir(self._tables_dir) if f.endswith(".sldtbl"))
        if not files:
            self._log("No .sldtbl files found.", "warn")
            return
        self._table_menu.configure(values=files)
        self._table_var.set(files[0])
        self._on_table_selected(files[0])

    def _on_table_selected(self, filename: str):
        path = os.path.join(self._tables_dir, filename)
        try:
            self._table_data = load_table(path)
            self._table_path = path
            pretty = self._table_data.get("prettyname", filename)
            self._log(f"Loaded: {pretty} ({filename})", "head")
            self._scan_table()
        except Exception as e:
            self._log(f"Failed to load {filename}: {e}", "error")

    # ── Parts scan ────────────────────────────────────────────────────────

    def _scan_table(self):
        if not self._table_data:
            return
        self._null_parts = find_null_part_firearms(self._table_data)
        self._available_parts = get_all_parts(self._table_data)
        self._rebuild_parts_list()
        count = len(self._null_parts)
        if count:
            unique_guns = len({p["firearm_name"] for p in self._null_parts})
            self._set_status(f"{count} null part ID(s) across {unique_guns} firearm(s)", WARN_COLOR)
            self._log(f"Found {count} null part IDs across {unique_guns} firearm(s).", "warn")
        else:
            self._set_status("No null part IDs — table is clean!", OK_COLOR)
            self._log("✓ No null part IDs found.", "ok")

    def _rebuild_parts_list(self):
        for w in self._parts_box.winfo_children():
            w.destroy()
        self._part_widgets.clear()

        if not self._null_parts:
            customtkinter.CTkLabel(
                self._parts_box, text="No null parts found.", text_color=OK_COLOR,
            ).pack(pady=20)
            return

        groups: dict = {}
        for entry in self._null_parts:
            groups.setdefault(entry["firearm_name"], []).append(entry)

        for firearm_name, parts in groups.items():
            hdr = customtkinter.CTkFrame(self._parts_box, fg_color="#2b2b2b", corner_radius=6)
            hdr.pack(fill="x", pady=(6, 2), padx=2)
            customtkinter.CTkLabel(
                hdr,
                text=f"  {firearm_name}  (ID {parts[0]['firearm_id']})",
                font=customtkinter.CTkFont(size=12, weight="bold"),
                text_color=HEAD_COLOR, anchor="w",
            ).pack(fill="x", padx=8, pady=4)

            for entry in parts:
                row = customtkinter.CTkFrame(self._parts_box, fg_color="#242424", corner_radius=4)
                row.pack(fill="x", pady=1, padx=8)
                row.columnconfigure(1, weight=1)

                status_var = customtkinter.StringVar(value="●")
                status_lbl = customtkinter.CTkLabel(
                    row, textvariable=status_var,
                    text_color=WARN_COLOR, width=20,
                    font=customtkinter.CTkFont(size=14),
                )
                status_lbl.grid(row=0, column=0, padx=(6, 2), pady=4)

                customtkinter.CTkLabel(
                    row,
                    text=f"{entry['part_name']}  [{entry['part_type']}]  slot: {entry['part_slot']}",
                    anchor="w", font=customtkinter.CTkFont(size=11), text_color="white",
                ).grid(row=0, column=1, sticky="w", padx=4)

                id_var = customtkinter.StringVar(value="")
                customtkinter.CTkEntry(
                    row, textvariable=id_var, width=70,
                    placeholder_text="ID",
                    font=customtkinter.CTkFont(size=11),
                ).grid(row=0, column=2, padx=4, pady=4)

                customtkinter.CTkButton(
                    row, text="Apply", width=60,
                    font=customtkinter.CTkFont(size=11),
                    command=lambda e=entry, iv=id_var, sl=status_lbl, sv=status_var:
                        self._manual_apply(e, iv, sl, sv),
                ).grid(row=0, column=3, padx=(2, 4), pady=4)

                customtkinter.CTkButton(
                    row, text="AI", width=50,
                    fg_color="#8e44ad", hover_color="#6c3483",
                    font=customtkinter.CTkFont(size=11),
                    command=lambda e=entry, iv=id_var, sl=status_lbl, sv=status_var:
                        self._ai_fix_single(e, iv, sl, sv),
                ).grid(row=0, column=4, padx=(2, 8), pady=4)

                self._part_widgets.append({
                    "entry": entry, "id_var": id_var,
                    "status_lbl": status_lbl, "status_var": status_var,
                })

    # ── Manual apply ──────────────────────────────────────────────────────

    def _manual_apply(self, entry, id_var, status_lbl, status_var):
        try:
            new_id = int(id_var.get().strip())
        except ValueError:
            self._log(f"Invalid ID '{id_var.get()}' — must be an integer.", "error")
            return
        self._apply_fix_to_data(entry, new_id, status_lbl, status_var, reason="manual")

    # ── AI fix (single) ───────────────────────────────────────────────────

    def _ai_fix_single(self, entry, id_var, status_lbl, status_var):
        if self._ai_running:
            self._log("AI is already running — please wait.", "warn")
            return
        threading.Thread(
            target=self._ai_worker,
            args=([entry], [{"id_var": id_var, "status_lbl": status_lbl, "status_var": status_var}]),
            daemon=True,
        ).start()

    # ── AI fix (all) ──────────────────────────────────────────────────────

    def _ai_fix_all(self):
        if self._ai_running:
            self._log("AI is already running — please wait.", "warn")
            return
        if not self._null_parts:
            self._log("No null parts to fix.", "info")
            return
        widgets = []
        for entry in self._null_parts:
            match = next(
                (w for w in self._part_widgets
                 if w["entry"]["item_index"] == entry["item_index"]
                 and w["entry"]["part_index"] == entry["part_index"]), None)
            widgets.append(match)
        threading.Thread(target=self._ai_worker, args=(self._null_parts, widgets), daemon=True).start()

    def _ai_worker(self, entries: list, widgets: list):
        self._ai_running = True
        total = len(entries)
        self._log(f"\n[AI] Processing {total} null part(s)…", "head")

        for i, (entry, w) in enumerate(zip(entries, widgets)):
            self._set_status(f"AI: {i+1}/{total} — {entry['firearm_name']}", HEAD_COLOR)
            self._log(f"\n[{i+1}/{total}] {entry['firearm_name']} → {entry['part_name']}", "head")

            result = ask_ai_for_part(
                firearm_name=entry["firearm_name"],
                firearm_platform=entry["firearm_platform"],
                firearm_caliber=entry["firearm_caliber"],
                part_name=entry["part_name"],
                part_slot=entry["part_slot"],
                part_type=entry["part_type"],
                available_parts=self._available_parts,
                next_id=next_available_id(self._table_data),
                log_fn=self._log,
            )

            action = result.get("action")
            if action == "match":
                new_id = result["id"]
                self._log(f"  matched existing ID {new_id}: {result.get('reason','')}", "ok")
                if w:
                    self.after(0, lambda iv=w["id_var"], nid=new_id: iv.set(str(nid)))
                    self._apply_fix_to_data(entry, new_id, w["status_lbl"], w["status_var"],
                                            reason=result.get("reason", ""))
            elif action == "create":
                new_part = result.get("part")
                if new_part:
                    new_id = insert_new_part(self._table_data, new_part)
                    self._available_parts = get_all_parts(self._table_data)
                    self._log(f"  created new part ID {new_id}: {new_part.get('name','')}", "ok")
                    if w:
                        self.after(0, lambda iv=w["id_var"], nid=new_id: iv.set(str(nid)))
                        self._apply_fix_to_data(entry, new_id, w["status_lbl"], w["status_var"],
                                                reason=f"new: {new_part.get('name','')}")
                else:
                    self._log(f"  create action but no part data: {result.get('reason','')}", "error")
            else:
                self._log(f"  {result.get('reason', 'Unknown error')}", "error")

            time.sleep(0.4)

        self._ai_running = False
        self._set_status("AI done — review and save when ready.", OK_COLOR)
        self._log("\n✓ AI run complete. Press Save when satisfied.", "ok")

    def _apply_fix_to_data(self, entry, new_id: int, status_lbl, status_var, reason: str = ""):
        apply_fix(self._table_data, entry["subtable"],
                  entry["item_index"], entry["part_index"], new_id)
        self.after(0, lambda: (
            status_lbl.configure(text_color=OK_COLOR),
            status_var.set("✓"),
        ))

    # ── Save (shared) ─────────────────────────────────────────────────────

    def _save_table(self):
        if not self._table_data or not self._table_path:
            self._log("No table loaded.", "error")
            return
        try:
            save_table(self._table_path, self._table_data)
            fname = os.path.basename(self._table_path)
            self._log(f"✓ Saved to {fname}", "ok")
            self._set_status(f"Saved: {fname}", OK_COLOR)
            self._scan_table()
        except Exception as e:
            self._log(f"Save failed: {e}", "error")
            self._set_status("Save failed!", ERROR_COLOR)


# ─── Entry point ──────────────────────────────────────────────────────────────

def main():
    customtkinter.set_appearance_mode("dark")
    customtkinter.set_default_color_theme("dark-blue")

    parser = argparse.ArgumentParser(description="DOOM-Tools Table Manager", add_help=False)
    parser.add_argument("--tables-dir", default=None)
    args, _ = parser.parse_known_args()

    script_dir = os.path.dirname(os.path.abspath(__file__))
    default_dir = args.tables_dir or os.path.join(script_dir, "tables")

    _tmp = customtkinter.CTk()
    _tmp.withdraw()
    picker = FolderPicker(_tmp, default_dir)
    _tmp.destroy()

    if not picker.result:
        return

    app = FirearmFixerApp(tables_dir=picker.result)
    app.mainloop()


if __name__ == "__main__":
    main()