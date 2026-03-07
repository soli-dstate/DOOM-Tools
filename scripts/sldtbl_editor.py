"""
SLDTBL Editor - A CustomTkinter-based UI editor for .sldtbl table files.
Provides fast item creation, duplication, autofill, UI-based accessory/part
editing, search, and compact JSON output matching the hand-written format.
"""

import customtkinter as ctk
import json
import os
import re
import copy
import tkinter as tk
from tkinter import filedialog, messagebox
from typing import Any

# ─── Constants ────────────────────────────────────────────────────────────────

RARITY_OPTIONS = ["Common", "Uncommon", "Rare", "Legendary", "Mythic"]
FIREARM_TYPES = ["conventional", "magic"]
FIREARM_SUBTYPES = ["pistol", "rifle", "shotgun", "smg", "lmg", "launcher", "sniper"]
ACTION_OPTIONS = ["Semi", "Auto", "Burst", "Bolt", "Double", "Single", "Pump", "Lever"]
BOLT_OPTIONS = ["closed", "open"]
MAGAZINE_TYPES = ["Detachable box", "Internal Box", "Internal tube", "Cylinder",
                  "Break Action", "Belt", "Drum", "Helical"]
PART_TYPES = ["barrel", "trigger_spring", "recoil_spring", "gas_piston",
              "bolt_carrier_group", "buffer_spring"]
DURABILITY_OPTIONS = ["null", "set_by_looting"]
MARKING_SYSTEMS = ["Tape", "Magpul Dot Matrix", "Magpul Dot Matrix (Pistol)"]

# Keys whose array elements should each be serialised on a single line
_INLINE_ELEMENT_KEYS = frozenset({"accessories", "parts", "subslots"})
# Keys whose entire array value should be written inline
_INLINE_ARRAY_KEYS = frozenset({"caliber", "action", "magazinesystem", "conflicts_with"})
# Fields copied during platform-based autofill
_AUTOFILL_FIELDS = [
    "type", "subtype", "caliber", "action", "bolt", "bolt_catch",
    "cyclic", "magazinetype", "magazinesystem", "jamrate",
    "burst_count", "burst_cyclic", "magicsoundsystem",
    "temp_gain_per_shot", "temp_loss_per_cooling_cycle", "capacity",
]

ITEM_TEMPLATES = {
    "Generic Item": {
        "name": "New Item",
        "value": 0,
        "description": "",
        "rarity": "Common",
        "random_quantity": False,
        "weight": 0.0,
        "id": 0,
        "can_stack": False,
    },
    "Firearm (Pistol)": {
        "name": "New Pistol",
        "value": 0,
        "description": "",
        "rarity": "Common",
        "random_quantity": False,
        "weight": 0.0,
        "id": 0,
        "firearm": True,
        "type": "conventional",
        "subtype": "pistol",
        "platform": "",
        "caliber": [],
        "action": ["Semi"],
        "bolt": "closed",
        "bolt_catch": True,
        "cyclic": 400,
        "magazinetype": "Detachable box",
        "magazinesystem": "",
        "jamrate": 0.01,
        "accessories": [],
        "can_stack": False,
        "parts": [],
    },
    "Firearm (Rifle)": {
        "name": "New Rifle",
        "value": 0,
        "description": "",
        "rarity": "Common",
        "random_quantity": False,
        "weight": 0.0,
        "id": 0,
        "firearm": True,
        "type": "conventional",
        "subtype": "rifle",
        "platform": "",
        "caliber": [],
        "action": ["Semi"],
        "bolt": "closed",
        "bolt_catch": True,
        "cyclic": 700,
        "magazinetype": "Detachable box",
        "magazinesystem": "",
        "jamrate": 0.005,
        "accessories": [],
        "can_stack": False,
        "parts": [],
    },
    "Firearm (Shotgun)": {
        "name": "New Shotgun",
        "value": 0,
        "description": "",
        "rarity": "Common",
        "random_quantity": False,
        "weight": 0.0,
        "id": 0,
        "firearm": True,
        "type": "conventional",
        "subtype": "shotgun",
        "platform": "",
        "caliber": [],
        "action": ["Semi"],
        "bolt": "closed",
        "bolt_catch": True,
        "cyclic": 300,
        "magazinetype": "Internal tube",
        "capacity": 4,
        "jamrate": 0.01,
        "accessories": [],
        "can_stack": False,
        "parts": [],
    },
    "Magazine": {
        "name": "New Magazine",
        "value": 0,
        "description": "",
        "rarity": "Common",
        "random_quantity": False,
        "weight": 0.0,
        "id": 0,
        "caliber": [],
        "capacity": 30,
        "magazinesystem": "",
        "can_stack": False,
        "in_armory": True,
        "spring_durability": None,
        "reliability": 85,
        "armory_category": "Magazines",
        "armory_subcategory": "",
        "marking_system": "Tape",
    },
    "Part": {
        "name": "New Part",
        "value": 0,
        "description": "",
        "rarity": "Common",
        "random_quantity": False,
        "weight": 0.0,
        "id": 0,
        "type": "barrel",
        "platform": "",
        "slot": "",
        "caliber": [],
        "can_stack": False,
        "in_armory": True,
        "durability": "set_by_looting",
        "armory_category": "Parts",
        "armory_subcategory": "",
    },
    "Attachment": {
        "name": "New Attachment",
        "value": 0,
        "description": "",
        "rarity": "Common",
        "random_quantity": False,
        "weight": 0.0,
        "id": 0,
        "attachment": True,
        "slot": "",
        "modifiers": None,
        "subslots": [],
        "can_stack": False,
        "in_armory": True,
        "armory_category": "Attachments",
        "armory_subcategory": "",
    },
}


# ─── Compact JSON Serialiser ─────────────────────────────────────────────────

def sldtbl_dumps(data: dict) -> str:
    """Serialise *data* to JSON matching the hand-written .sldtbl conventions.

    * 4-space indentation for the overall structure.
    * ``accessories``, ``parts``, ``subslots`` – each element on one line.
    * ``caliber``, ``action``, ``magazinesystem``, ``conflicts_with`` – entire
      array on one line.
    """

    def _s(obj: Any, depth: int, parent_key: str | None = None) -> str:
        sp = "    " * depth
        sp1 = "    " * (depth + 1)

        # ── primitives ──
        if isinstance(obj, str):
            return json.dumps(obj, ensure_ascii=False)
        if isinstance(obj, (bool, int, float, type(None))):
            return json.dumps(obj)

        # ── lists ──
        if isinstance(obj, list):
            if not obj:
                return "[]"

            # Whole array inline (caliber, action, …)
            if parent_key in _INLINE_ARRAY_KEYS and depth >= 4:
                inner = ", ".join(json.dumps(x, ensure_ascii=False) for x in obj)
                return f"[{inner}]"

            # Each element inline (accessories, parts, subslots)
            if parent_key in _INLINE_ELEMENT_KEYS and depth >= 4:
                lines = ["["]
                for i, elem in enumerate(obj):
                    comma = "," if i < len(obj) - 1 else ""
                    inline = json.dumps(elem, ensure_ascii=False, separators=(", ", ": "))
                    lines.append(f"{sp1}{inline}{comma}")
                lines.append(f"{sp}]")
                return "\n".join(lines)

            # Normal array
            lines = ["["]
            for i, elem in enumerate(obj):
                comma = "," if i < len(obj) - 1 else ""
                val = _s(elem, depth + 1)
                lines.append(f"{sp1}{val}{comma}")
            lines.append(f"{sp}]")
            return "\n".join(lines)

        # ── dicts ──
        if isinstance(obj, dict):
            if not obj:
                return "{}"
            lines = ["{"]
            items = list(obj.items())
            for i, (k, v) in enumerate(items):
                comma = "," if i < len(items) - 1 else ""
                k_str = json.dumps(k, ensure_ascii=False)
                v_str = _s(v, depth + 1, parent_key=k)
                lines.append(f"{sp1}{k_str}: {v_str}{comma}")
            lines.append(f"{sp}}}")
            return "\n".join(lines)

        return json.dumps(obj, ensure_ascii=False)

    return _s(data, 0) + "\n"


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _slot_from_name(name: str) -> str:
    """Derive a slot identifier from a human-readable name."""
    s = name.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    return s.strip("_")


# ─── Accessories Editor Dialog ───────────────────────────────────────────────

class AccessoriesEditorDialog(ctk.CTkToplevel):
    """Full UI editor for the ``accessories`` list of a firearm item."""

    def __init__(self, parent, accessories_data: list | None, callback):
        super().__init__(parent)
        self.title("Edit Accessories")
        self.geometry("850x600")
        self.transient(parent)
        self.grab_set()
        self.callback = callback
        self.entries: list[dict] = copy.deepcopy(accessories_data) if accessories_data else []
        self._widgets: list[dict] = []

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self.scroll = ctk.CTkScrollableFrame(self)
        self.scroll.grid(row=0, column=0, padx=10, pady=(10, 5), sticky="nsew")

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.grid(row=1, column=0, padx=10, pady=(5, 10), sticky="ew")
        ctk.CTkButton(btn_frame, text="+ Add Accessory", width=140, command=self._add).pack(side="left", padx=5)
        ctk.CTkButton(btn_frame, text="Cancel", width=90, fg_color="gray30", command=self.destroy).pack(side="right", padx=5)
        ctk.CTkButton(btn_frame, text="Save", width=90, command=self._save).pack(side="right", padx=5)

        self._rebuild()
        self.after(100, self.focus_force)

    # ── internal ──

    def _collect(self):
        """Read widget values back into *self.entries*."""
        for i, w in enumerate(self._widgets):
            if i >= len(self.entries):
                break
            self.entries[i]["name"] = w["name"].get()
            self.entries[i]["slot"] = w["slot"].get()
            cfl = w["conflicts"].get().strip()
            if cfl:
                self.entries[i]["conflicts_with"] = [s.strip() for s in cfl.split(",") if s.strip()]
            elif "conflicts_with" in self.entries[i]:
                del self.entries[i]["conflicts_with"]

    def _rebuild(self):
        for child in self.scroll.winfo_children():
            child.destroy()
        self._widgets = []

        for i, entry in enumerate(self.entries):
            frame = ctk.CTkFrame(self.scroll)
            frame.pack(fill="x", padx=5, pady=4)
            frame.grid_columnconfigure(1, weight=1)
            frame.grid_columnconfigure(3, weight=1)

            # Row 0 — Name & Slot
            ctk.CTkLabel(frame, text="Name:", width=45, font=("", 11)).grid(row=0, column=0, padx=4, pady=2, sticky="w")
            name_var = ctk.StringVar(value=entry.get("name", ""))
            ctk.CTkEntry(frame, textvariable=name_var, font=("", 11)).grid(row=0, column=1, padx=4, pady=2, sticky="ew")

            ctk.CTkLabel(frame, text="Slot:", width=35, font=("", 11)).grid(row=0, column=2, padx=4, pady=2, sticky="w")
            slot_var = ctk.StringVar(value=entry.get("slot", ""))
            ctk.CTkEntry(frame, textvariable=slot_var, font=("", 11)).grid(row=0, column=3, padx=4, pady=2, sticky="ew")

            # Auto-gen slot button
            ctk.CTkButton(frame, text="Gen", width=36, height=24, font=("", 10),
                          command=lambda nv=name_var, sv=slot_var: sv.set(_slot_from_name(nv.get()))
                          ).grid(row=0, column=4, padx=2)

            ctk.CTkButton(frame, text="✕", width=28, height=28, fg_color="darkred", hover_color="red",
                          command=lambda idx=i: self._delete(idx)).grid(row=0, column=5, padx=4)

            # Row 1 — Current & Conflicts
            current = entry.get("current")
            if current is None:
                cur_text = "Empty"
            elif isinstance(current, dict):
                cur_text = f"Attached: {current.get('name', '?')}"
            else:
                cur_text = str(current)[:40]

            ctk.CTkLabel(frame, text="Current:", width=60, font=("", 11)).grid(row=1, column=0, padx=4, pady=2, sticky="w")
            ctk.CTkLabel(frame, text=cur_text, font=("", 11), anchor="w").grid(row=1, column=1, padx=4, pady=2, sticky="w")

            cur_btns = ctk.CTkFrame(frame, fg_color="transparent")
            cur_btns.grid(row=1, column=2, padx=4, pady=2, sticky="w")
            ctk.CTkButton(cur_btns, text="Edit", width=44, height=24, font=("", 10),
                          command=lambda idx=i: self._edit_current(idx)).pack(side="left", padx=2)
            ctk.CTkButton(cur_btns, text="Clear", width=44, height=24, font=("", 10),
                          command=lambda idx=i: self._clear_current(idx)).pack(side="left", padx=2)

            conflicts = entry.get("conflicts_with")
            cfl_str = ", ".join(conflicts) if isinstance(conflicts, list) else ""
            ctk.CTkLabel(frame, text="Conflicts:", width=65, font=("", 11)).grid(row=1, column=3, padx=(15, 4), pady=2, sticky="w")
            conflicts_var = ctk.StringVar(value=cfl_str)
            ctk.CTkEntry(frame, textvariable=conflicts_var, font=("", 11), placeholder_text="slot1, slot2").grid(row=2, column=0, columnspan=4, padx=4, pady=(0, 4), sticky="ew") if cfl_str else None
            # put conflicts entry on row 1 col 3 spanning
            if not cfl_str:
                ctk.CTkEntry(frame, textvariable=conflicts_var, font=("", 11), width=160,
                             placeholder_text="slot1, slot2").grid(row=1, column=3, padx=4, pady=2, sticky="ew")

            # Row 2 — Move buttons
            mv = ctk.CTkFrame(frame, fg_color="transparent")
            mv.grid(row=2, column=0, columnspan=6, padx=4, pady=(0, 4), sticky="w")
            ctk.CTkButton(mv, text="▲", width=28, height=22, font=("", 10),
                          command=lambda idx=i: self._move(idx, -1)).pack(side="left", padx=1)
            ctk.CTkButton(mv, text="▼", width=28, height=22, font=("", 10),
                          command=lambda idx=i: self._move(idx, 1)).pack(side="left", padx=1)

            self._widgets.append({"name": name_var, "slot": slot_var, "conflicts": conflicts_var})

    def _add(self):
        self._collect()
        self.entries.append({"name": "", "slot": "", "current": None})
        self._rebuild()

    def _delete(self, idx):
        self._collect()
        self.entries.pop(idx)
        self._rebuild()

    def _move(self, idx, direction):
        new = idx + direction
        if 0 <= new < len(self.entries):
            self._collect()
            self.entries[idx], self.entries[new] = self.entries[new], self.entries[idx]
            self._rebuild()

    def _edit_current(self, idx):
        self._collect()
        cur = self.entries[idx].get("current")

        def on_save(val):
            self.entries[idx]["current"] = val
            self._rebuild()

        JSONEditorDialog(self, f"Current – {self.entries[idx].get('name', '?')}", cur, on_save)

    def _clear_current(self, idx):
        self._collect()
        self.entries[idx]["current"] = None
        self._rebuild()

    def _save(self):
        self._collect()
        self.callback(self.entries if self.entries else None)
        self.destroy()


# ─── Parts Editor Dialog ─────────────────────────────────────────────────────

class PartsEditorDialog(ctk.CTkToplevel):
    """Full UI editor for the ``parts`` list of a firearm item."""

    def __init__(self, parent, parts_data: list | None, callback):
        super().__init__(parent)
        self.title("Edit Parts")
        self.geometry("850x600")
        self.transient(parent)
        self.grab_set()
        self.callback = callback
        self.entries: list[dict] = copy.deepcopy(parts_data) if parts_data else []
        self._widgets: list[dict] = []

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self.scroll = ctk.CTkScrollableFrame(self)
        self.scroll.grid(row=0, column=0, padx=10, pady=(10, 5), sticky="nsew")

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.grid(row=1, column=0, padx=10, pady=(5, 10), sticky="ew")
        ctk.CTkButton(btn_frame, text="+ Add Part", width=120, command=self._add).pack(side="left", padx=5)
        ctk.CTkButton(btn_frame, text="Cancel", width=90, fg_color="gray30", command=self.destroy).pack(side="right", padx=5)
        ctk.CTkButton(btn_frame, text="Save", width=90, command=self._save).pack(side="right", padx=5)

        self._rebuild()
        self.after(100, self.focus_force)

    # ── internal ──

    def _collect(self):
        for i, w in enumerate(self._widgets):
            if i >= len(self.entries):
                break
            self.entries[i]["name"] = w["name"].get()
            self.entries[i]["slot"] = w["slot"].get()
            self.entries[i]["type"] = w["type"].get()
            # current id
            id_str = w["cur_id"].get().strip()
            if id_str.lower() == "null" or id_str == "":
                self.entries[i]["current"] = {"id": None}
            else:
                try:
                    self.entries[i]["current"] = {"id": int(id_str)}
                except ValueError:
                    self.entries[i]["current"] = {"id": None}
            # durability
            dur = w["dur"].get().strip()
            self.entries[i]["durability"] = None if dur.lower() == "null" or dur == "" else dur

    def _rebuild(self):
        for child in self.scroll.winfo_children():
            child.destroy()
        self._widgets = []

        for i, entry in enumerate(self.entries):
            frame = ctk.CTkFrame(self.scroll)
            frame.pack(fill="x", padx=5, pady=4)
            frame.grid_columnconfigure(1, weight=1)
            frame.grid_columnconfigure(3, weight=1)

            # Row 0 — Name & Slot
            ctk.CTkLabel(frame, text="Name:", width=45, font=("", 11)).grid(row=0, column=0, padx=4, pady=2, sticky="w")
            name_var = ctk.StringVar(value=entry.get("name", ""))
            ctk.CTkEntry(frame, textvariable=name_var, font=("", 11)).grid(row=0, column=1, padx=4, pady=2, sticky="ew")

            ctk.CTkLabel(frame, text="Slot:", width=35, font=("", 11)).grid(row=0, column=2, padx=4, pady=2, sticky="w")
            slot_var = ctk.StringVar(value=entry.get("slot", ""))
            ctk.CTkEntry(frame, textvariable=slot_var, font=("", 11)).grid(row=0, column=3, padx=4, pady=2, sticky="ew")

            ctk.CTkButton(frame, text="Gen", width=36, height=24, font=("", 10),
                          command=lambda nv=name_var, sv=slot_var: sv.set(_slot_from_name(nv.get()))
                          ).grid(row=0, column=4, padx=2)
            ctk.CTkButton(frame, text="✕", width=28, height=28, fg_color="darkred", hover_color="red",
                          command=lambda idx=i: self._delete(idx)).grid(row=0, column=5, padx=4)

            # Row 1 — Type, Current ID, Durability
            ctk.CTkLabel(frame, text="Type:", width=40, font=("", 11)).grid(row=1, column=0, padx=4, pady=2, sticky="w")
            type_var = ctk.StringVar(value=entry.get("type", "barrel"))
            ctk.CTkComboBox(frame, values=PART_TYPES, variable=type_var, width=170, font=("", 11)).grid(
                row=1, column=1, padx=4, pady=2, sticky="w")

            cur = entry.get("current", {})
            cur_id = cur.get("id") if isinstance(cur, dict) else None
            cur_id_str = "null" if cur_id is None else str(cur_id)

            ctk.CTkLabel(frame, text="Cur ID:", width=50, font=("", 11)).grid(row=1, column=2, padx=4, pady=2, sticky="w")
            id_var = ctk.StringVar(value=cur_id_str)
            ctk.CTkEntry(frame, textvariable=id_var, width=80, font=("", 11)).grid(row=1, column=3, padx=4, pady=2, sticky="w")

            dur = entry.get("durability")
            dur_str = "null" if dur is None else str(dur)
            dur_frame = ctk.CTkFrame(frame, fg_color="transparent")
            dur_frame.grid(row=2, column=0, columnspan=4, padx=4, pady=(0, 4), sticky="w")
            ctk.CTkLabel(dur_frame, text="Durability:", width=70, font=("", 11)).pack(side="left")
            dur_var = ctk.StringVar(value=dur_str)
            ctk.CTkComboBox(dur_frame, values=DURABILITY_OPTIONS, variable=dur_var, width=160, font=("", 11)).pack(
                side="left", padx=5)

            # Move buttons
            mv = ctk.CTkFrame(dur_frame, fg_color="transparent")
            mv.pack(side="right", padx=5)
            ctk.CTkButton(mv, text="▲", width=28, height=22, font=("", 10),
                          command=lambda idx=i: self._move(idx, -1)).pack(side="left", padx=1)
            ctk.CTkButton(mv, text="▼", width=28, height=22, font=("", 10),
                          command=lambda idx=i: self._move(idx, 1)).pack(side="left", padx=1)

            self._widgets.append({"name": name_var, "slot": slot_var, "type": type_var,
                                  "cur_id": id_var, "dur": dur_var})

    def _add(self):
        self._collect()
        self.entries.append({"name": "", "slot": "", "current": {"id": None},
                             "durability": None, "type": "barrel"})
        self._rebuild()

    def _delete(self, idx):
        self._collect()
        self.entries.pop(idx)
        self._rebuild()

    def _move(self, idx, direction):
        new = idx + direction
        if 0 <= new < len(self.entries):
            self._collect()
            self.entries[idx], self.entries[new] = self.entries[new], self.entries[idx]
            self._rebuild()

    def _save(self):
        self._collect()
        self.callback(self.entries if self.entries else None)
        self.destroy()


# ─── JSON Field Editor Dialog ────────────────────────────────────────────────

class JSONEditorDialog(ctk.CTkToplevel):
    """Raw JSON editor for complex / unknown fields."""

    def __init__(self, parent, title: str, data: Any, callback):
        super().__init__(parent)
        self.title(title)
        self.geometry("700x500")
        self.transient(parent)
        self.grab_set()
        self.callback = callback

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self.textbox = ctk.CTkTextbox(self, font=("Consolas", 13), wrap="none")
        self.textbox.grid(row=0, column=0, padx=10, pady=(10, 5), sticky="nsew")

        try:
            formatted = json.dumps(data, indent=4, ensure_ascii=False)
        except (TypeError, ValueError):
            formatted = str(data) if data is not None else "null"
        self.textbox.insert("1.0", formatted)

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.grid(row=1, column=0, padx=10, pady=(5, 10), sticky="ew")
        ctk.CTkButton(btn_frame, text="Format JSON", width=120, command=self._format).pack(side="left", padx=5)
        ctk.CTkButton(btn_frame, text="Cancel", width=100, command=self.destroy).pack(side="right", padx=5)
        ctk.CTkButton(btn_frame, text="Save", width=100, command=self._save).pack(side="right", padx=5)

        self.after(100, self.focus_force)

    def _format(self):
        try:
            parsed = json.loads(self.textbox.get("1.0", "end").strip())
            self.textbox.delete("1.0", "end")
            self.textbox.insert("1.0", json.dumps(parsed, indent=4, ensure_ascii=False))
        except json.JSONDecodeError as e:
            messagebox.showerror("JSON Error", f"Invalid JSON:\n{e}", parent=self)

    def _save(self):
        raw = self.textbox.get("1.0", "end").strip()
        try:
            result = None if raw.lower() == "null" else json.loads(raw)
            self.callback(result)
            self.destroy()
        except json.JSONDecodeError as e:
            messagebox.showerror("JSON Error", f"Invalid JSON:\n{e}", parent=self)


# ─── Settings Editor Dialog ──────────────────────────────────────────────────

class SettingsDialog(ctk.CTkToplevel):
    """Editor for file metadata, additional_settings and rarity_weights."""

    def __init__(self, parent, file_data: dict, callback):
        super().__init__(parent)
        self.title("File Settings")
        self.geometry("600x700")
        self.transient(parent)
        self.grab_set()
        self.callback = callback
        self.file_data = copy.deepcopy(file_data)

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        scroll = ctk.CTkScrollableFrame(self)
        scroll.grid(row=0, column=0, padx=10, pady=(10, 5), sticky="nsew")
        scroll.grid_columnconfigure(1, weight=1)

        row = 0
        ctk.CTkLabel(scroll, text="── File Metadata ──", font=("", 14, "bold")).grid(
            row=row, column=0, columnspan=2, pady=(5, 10), sticky="w"); row += 1

        self.meta_vars = {}
        for key in ("prettyname", "filename", "version"):
            ctk.CTkLabel(scroll, text=key).grid(row=row, column=0, padx=5, pady=2, sticky="w")
            var = ctk.StringVar(value=str(self.file_data.get(key, "")))
            ctk.CTkEntry(scroll, textvariable=var).grid(row=row, column=1, padx=5, pady=2, sticky="ew")
            self.meta_vars[key] = var; row += 1

        ctk.CTkLabel(scroll, text="── Additional Settings ──", font=("", 14, "bold")).grid(
            row=row, column=0, columnspan=2, pady=(15, 10), sticky="w"); row += 1

        self.settings_vars: dict[str, tuple] = {}
        for key, val in self.file_data.get("additional_settings", {}).items():
            ctk.CTkLabel(scroll, text=key).grid(row=row, column=0, padx=5, pady=2, sticky="w")
            if isinstance(val, bool):
                var = ctk.BooleanVar(value=val)
                ctk.CTkSwitch(scroll, variable=var, text="").grid(row=row, column=1, padx=5, pady=2, sticky="w")
            else:
                var = ctk.StringVar(value=str(val))
                ctk.CTkEntry(scroll, textvariable=var).grid(row=row, column=1, padx=5, pady=2, sticky="ew")
            self.settings_vars[key] = (var, type(val)); row += 1

        ctk.CTkLabel(scroll, text="── Rarity Weights ──", font=("", 14, "bold")).grid(
            row=row, column=0, columnspan=2, pady=(15, 10), sticky="w"); row += 1

        self.rarity_vars: dict[str, ctk.StringVar] = {}
        for key, val in self.file_data.get("rarity_weights", {}).items():
            ctk.CTkLabel(scroll, text=key).grid(row=row, column=0, padx=5, pady=2, sticky="w")
            var = ctk.StringVar(value=str(val))
            ctk.CTkEntry(scroll, textvariable=var, width=100).grid(row=row, column=1, padx=5, pady=2, sticky="w")
            self.rarity_vars[key] = var; row += 1

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.grid(row=1, column=0, padx=10, pady=(5, 10), sticky="ew")
        ctk.CTkButton(btn_frame, text="Cancel", width=100, command=self.destroy).pack(side="right", padx=5)
        ctk.CTkButton(btn_frame, text="Save", width=100, command=self._save).pack(side="right", padx=5)
        self.after(100, self.focus_force)

    def _save(self):
        for key, var in self.meta_vars.items():
            self.file_data[key] = var.get()

        settings = self.file_data.get("additional_settings", {})
        for key, (var, orig_type) in self.settings_vars.items():
            if orig_type == bool:
                settings[key] = var.get()
            elif orig_type == int:
                try:
                    settings[key] = int(var.get())
                except ValueError:
                    settings[key] = var.get()
            elif orig_type == float:
                try:
                    settings[key] = float(var.get())
                except ValueError:
                    settings[key] = var.get()
            else:
                settings[key] = var.get()
        self.file_data["additional_settings"] = settings

        rarity = self.file_data.get("rarity_weights", {})
        for key, var in self.rarity_vars.items():
            try:
                rarity[key] = float(var.get())
            except ValueError:
                rarity[key] = var.get()
        self.file_data["rarity_weights"] = rarity

        self.callback(self.file_data)
        self.destroy()


# ─── Autofill Picker Dialog ──────────────────────────────────────────────────

class AutofillPickerDialog(ctk.CTkToplevel):
    """Let the user pick a source item for autofill."""

    def __init__(self, parent, matches: list[tuple[str, int, dict]], callback):
        super().__init__(parent)
        self.title("Pick Source for Autofill")
        self.geometry("550x420")
        self.transient(parent)
        self.grab_set()
        self.callback = callback

        ctk.CTkLabel(self, text="Choose an item to copy fields from:",
                     font=("", 14, "bold")).pack(padx=15, pady=(15, 10))

        scroll = ctk.CTkScrollableFrame(self)
        scroll.pack(fill="both", expand=True, padx=15, pady=5)

        for table_name, _idx, item in matches:
            name = item.get("name", "Unknown")
            ctk.CTkButton(scroll, text=f"[{table_name}] {name}", anchor="w", height=32,
                          command=lambda src=item: self._pick(src)).pack(fill="x", padx=5, pady=2)

        ctk.CTkButton(self, text="Cancel", width=280, fg_color="gray30",
                      command=self.destroy).pack(padx=15, pady=(5, 15))
        self.after(100, self.focus_force)

    def _pick(self, source):
        self.callback(source)
        self.destroy()


# ─── Template Selection Dialog ───────────────────────────────────────────────

class TemplateDialog(ctk.CTkToplevel):
    def __init__(self, parent, callback):
        super().__init__(parent)
        self.title("New Item from Template")
        self.geometry("350x380")
        self.transient(parent)
        self.grab_set()
        self.callback = callback

        ctk.CTkLabel(self, text="Choose a template:", font=("", 14, "bold")).pack(padx=15, pady=(15, 10))
        for t in ITEM_TEMPLATES:
            ctk.CTkButton(self, text=t, width=280, height=35,
                          command=lambda n=t: (self.callback(n), self.destroy())).pack(padx=15, pady=3)
        ctk.CTkButton(self, text="Cancel", width=280, fg_color="gray30",
                      command=self.destroy).pack(padx=15, pady=(10, 15))
        self.after(100, self.focus_force)


# ─── Move Item Dialog ────────────────────────────────────────────────────────

class MoveDialog(ctk.CTkToplevel):
    def __init__(self, parent, tables: list[str], callback):
        super().__init__(parent)
        self.title("Move Item to Table")
        self.geometry("350x400")
        self.transient(parent)
        self.grab_set()
        self.callback = callback

        ctk.CTkLabel(self, text="Select target table:", font=("", 14, "bold")).pack(padx=15, pady=(15, 10))
        scroll = ctk.CTkScrollableFrame(self)
        scroll.pack(fill="both", expand=True, padx=15, pady=5)
        for t in tables:
            ctk.CTkButton(scroll, text=t, width=280, height=32, anchor="w",
                          command=lambda n=t: (self.callback(n), self.destroy())).pack(padx=5, pady=2, fill="x")
        ctk.CTkButton(self, text="Cancel", width=280, fg_color="gray30",
                      command=self.destroy).pack(padx=15, pady=(5, 15))
        self.after(100, self.focus_force)


# ─── Add Field Dialog ────────────────────────────────────────────────────────

class AddFieldDialog(ctk.CTkToplevel):
    def __init__(self, parent, callback):
        super().__init__(parent)
        self.title("Add Field")
        self.geometry("350x250")
        self.transient(parent)
        self.grab_set()
        self.callback = callback

        ctk.CTkLabel(self, text="Field name:").pack(padx=15, pady=(15, 2), anchor="w")
        self.name_var = ctk.StringVar()
        ctk.CTkEntry(self, textvariable=self.name_var, width=300).pack(padx=15, pady=(0, 10))

        ctk.CTkLabel(self, text="Field type:").pack(padx=15, pady=(0, 2), anchor="w")
        self.type_var = ctk.StringVar(value="string")
        ctk.CTkComboBox(self, values=["string", "number", "float", "boolean", "list", "object", "null"],
                        variable=self.type_var, width=300).pack(padx=15, pady=(0, 15))

        bf = ctk.CTkFrame(self, fg_color="transparent")
        bf.pack(padx=15, pady=(0, 15), fill="x")
        ctk.CTkButton(bf, text="Cancel", width=130, fg_color="gray30", command=self.destroy).pack(side="right", padx=5)
        ctk.CTkButton(bf, text="Add", width=130, command=self._add).pack(side="right", padx=5)
        self.after(100, self.focus_force)

    def _add(self):
        name = self.name_var.get().strip()
        if not name:
            messagebox.showwarning("Empty", "Field name cannot be empty.", parent=self)
            return
        self.callback(name, self.type_var.get())
        self.destroy()


# ─── Main Editor Application ─────────────────────────────────────────────────

class SLDTBLEditor(ctk.CTk):
    """Main application window."""

    def __init__(self):
        super().__init__()
        self.title("SLDTBL Editor")
        self.geometry("1400x850")
        self.minsize(1000, 600)

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.file_data: dict | None = None
        self.current_filepath: str | None = None
        self.current_table: str | None = None
        self.current_item_index: int | None = None
        self.unsaved_changes = False
        self.field_widgets: dict = {}

        self._build_ui()
        self._bind_shortcuts()

    # ── UI Construction ──────────────────────────────────────────────────────

    def _build_ui(self):
        self._build_toolbar()

        self.main_pane = ctk.CTkFrame(self, fg_color="transparent")
        self.main_pane.pack(fill="both", expand=True, padx=5, pady=(0, 5))
        self.main_pane.grid_columnconfigure(0, weight=0, minsize=320)
        self.main_pane.grid_columnconfigure(1, weight=1)
        self.main_pane.grid_rowconfigure(0, weight=1)

        self._build_left_panel()
        self._build_right_panel()

        self.status_var = ctk.StringVar(value="No file loaded")
        ctk.CTkLabel(self, textvariable=self.status_var, anchor="w",
                     font=("", 11), fg_color=("gray85", "gray20"), corner_radius=0).pack(fill="x", side="bottom")

    def _build_toolbar(self):
        toolbar = ctk.CTkFrame(self, height=40, corner_radius=0)
        toolbar.pack(fill="x", padx=5, pady=5)

        ctk.CTkButton(toolbar, text="Open", width=70, command=self.open_file).pack(side="left", padx=2)
        ctk.CTkButton(toolbar, text="Save", width=70, command=self.save_file).pack(side="left", padx=2)
        ctk.CTkButton(toolbar, text="Save As", width=80, command=self.save_file_as).pack(side="left", padx=2)

        ctk.CTkFrame(toolbar, width=2, height=28, fg_color="gray50").pack(side="left", padx=8)
        ctk.CTkButton(toolbar, text="File Settings", width=100, command=self.open_settings).pack(side="left", padx=2)

        ctk.CTkFrame(toolbar, width=2, height=28, fg_color="gray50").pack(side="left", padx=8)
        ctk.CTkButton(toolbar, text="+ Add Table", width=100, command=self.add_table).pack(side="left", padx=2)

        ctk.CTkFrame(toolbar, width=2, height=28, fg_color="gray50").pack(side="left", padx=8)
        ctk.CTkButton(toolbar, text="Autofill", width=90,
                      fg_color="#8B4513", hover_color="#A0522D",
                      command=self._autofill_from_platform).pack(side="left", padx=2)

        ctk.CTkFrame(toolbar, width=2, height=28, fg_color="gray50").pack(side="left", padx=8)
        ctk.CTkLabel(toolbar, text="Search:").pack(side="left", padx=(5, 2))
        self.search_var = ctk.StringVar()
        self.search_var.trace_add("write", lambda *_: self._filter_items())
        ctk.CTkEntry(toolbar, textvariable=self.search_var, width=200,
                     placeholder_text="Filter items by name...").pack(side="left", padx=2)

        self.file_label = ctk.CTkLabel(toolbar, text="", font=("", 12, "bold"))
        self.file_label.pack(side="right", padx=10)

    def _build_left_panel(self):
        left = ctk.CTkFrame(self.main_pane, width=320)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 3))
        left.grid_rowconfigure(1, weight=0)
        left.grid_rowconfigure(5, weight=1)
        left.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(left, text="Tables", font=("", 13, "bold")).grid(row=0, column=0, padx=10, pady=(8, 2), sticky="w")

        self.tables_frame = ctk.CTkScrollableFrame(left, height=150)
        self.tables_frame.grid(row=1, column=0, padx=5, pady=2, sticky="nsew")
        self.tables_frame.grid_columnconfigure(0, weight=1)

        items_hdr = ctk.CTkFrame(left, fg_color="transparent")
        items_hdr.grid(row=2, column=0, padx=5, pady=(8, 2), sticky="ew")
        ctk.CTkLabel(items_hdr, text="Items", font=("", 13, "bold")).pack(side="left", padx=5)
        self.item_count_label = ctk.CTkLabel(items_hdr, text="", font=("", 11))
        self.item_count_label.pack(side="left", padx=5)

        ibf = ctk.CTkFrame(left, fg_color="transparent")
        ibf.grid(row=3, column=0, padx=5, pady=2, sticky="new")
        ibf.grid_columnconfigure((0, 1, 2, 3), weight=1)
        ctk.CTkButton(ibf, text="+ New", width=60, height=28, font=("", 11),
                      command=self.add_item_from_template).grid(row=0, column=0, padx=1, sticky="ew")
        ctk.CTkButton(ibf, text="Duplicate", width=70, height=28, font=("", 11),
                      command=self.duplicate_item).grid(row=0, column=1, padx=1, sticky="ew")
        ctk.CTkButton(ibf, text="Delete", width=60, height=28, font=("", 11),
                      fg_color="darkred", hover_color="red",
                      command=self.delete_item).grid(row=0, column=2, padx=1, sticky="ew")
        ctk.CTkButton(ibf, text="Move", width=60, height=28, font=("", 11),
                      command=self.move_item).grid(row=0, column=3, padx=1, sticky="ew")

        mf = ctk.CTkFrame(left, fg_color="transparent")
        mf.grid(row=4, column=0, padx=5, pady=2, sticky="new")
        mf.grid_columnconfigure((0, 1), weight=1)
        ctk.CTkButton(mf, text="▲ Move Up", width=80, height=26, font=("", 11),
                      command=lambda: self._reorder_item(-1)).grid(row=0, column=0, padx=1, sticky="ew")
        ctk.CTkButton(mf, text="▼ Move Down", width=80, height=26, font=("", 11),
                      command=lambda: self._reorder_item(1)).grid(row=0, column=1, padx=1, sticky="ew")

        self.items_frame = ctk.CTkScrollableFrame(left)
        self.items_frame.grid(row=5, column=0, padx=5, pady=(2, 5), sticky="nsew")
        self.items_frame.grid_columnconfigure(0, weight=1)

    def _build_right_panel(self):
        self.right = ctk.CTkFrame(self.main_pane)
        self.right.grid(row=0, column=1, sticky="nsew", padx=(3, 0))
        self.right.grid_rowconfigure(1, weight=1)
        self.right.grid_columnconfigure(0, weight=1)

        header = ctk.CTkFrame(self.right, fg_color="transparent")
        header.grid(row=0, column=0, padx=10, pady=(8, 2), sticky="ew")
        header.grid_columnconfigure(0, weight=1)
        self.editor_title = ctk.CTkLabel(header, text="Select an item to edit", font=("", 15, "bold"))
        self.editor_title.pack(side="left")
        ctk.CTkButton(header, text="Apply Changes", width=120, command=self._apply_changes).pack(side="right", padx=5)
        ctk.CTkButton(header, text="+ Add Field", width=100, command=self._add_custom_field).pack(side="right", padx=5)

        self.editor_scroll = ctk.CTkScrollableFrame(self.right)
        self.editor_scroll.grid(row=1, column=0, padx=5, pady=5, sticky="nsew")
        self.editor_scroll.grid_columnconfigure(1, weight=1)

    # ── Shortcuts ────────────────────────────────────────────────────────────

    def _bind_shortcuts(self):
        self.bind("<Control-o>", lambda e: self.open_file())
        self.bind("<Control-s>", lambda e: self.save_file())
        self.bind("<Control-Shift-S>", lambda e: self.save_file_as())
        self.bind("<Control-d>", lambda e: self.duplicate_item())
        self.bind("<Control-n>", lambda e: self.add_item_from_template())
        self.bind("<Control-f>", lambda e: self.search_var.set("") or None)

    # ── File Operations ──────────────────────────────────────────────────────

    def open_file(self):
        if self.unsaved_changes:
            if not messagebox.askyesno("Unsaved Changes", "You have unsaved changes. Open anyway?"):
                return
        filepath = filedialog.askopenfilename(
            title="Open SLDTBL File",
            filetypes=[("SLDTBL Files", "*.sldtbl"), ("JSON Files", "*.json"), ("All Files", "*.*")],
            initialdir=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tables"),
        )
        if not filepath:
            return
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                self.file_data = json.load(f)
            self.current_filepath = filepath
            self.current_table = None
            self.current_item_index = None
            self.unsaved_changes = False
            self._refresh_tables()
            fname = os.path.basename(filepath)
            self.file_label.configure(text=f"{self.file_data.get('prettyname', fname)} ({fname})")
            self._set_status(f"Opened: {filepath}")
            self.title(f"SLDTBL Editor - {fname}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open file:\n{e}")

    def save_file(self):
        if not self.file_data:
            return
        if not self.current_filepath:
            self.save_file_as()
            return
        self._write_file(self.current_filepath)

    def save_file_as(self):
        if not self.file_data:
            return
        filepath = filedialog.asksaveasfilename(
            title="Save SLDTBL File",
            filetypes=[("SLDTBL Files", "*.sldtbl"), ("JSON Files", "*.json")],
            defaultextension=".sldtbl",
            initialdir=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tables"),
        )
        if filepath:
            self._write_file(filepath)
            self.current_filepath = filepath
            fname = os.path.basename(filepath)
            self.file_label.configure(text=f"{self.file_data.get('prettyname', fname)} ({fname})")
            self.title(f"SLDTBL Editor - {fname}")

    def _write_file(self, filepath: str):
        if not self.file_data:
            return
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(sldtbl_dumps(self.file_data))
            self.unsaved_changes = False
            self._set_status(f"Saved: {filepath}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save file:\n{e}")

    # ── Settings ─────────────────────────────────────────────────────────────

    def open_settings(self):
        if not self.file_data:
            messagebox.showinfo("No File", "Open a file first.")
            return
        SettingsDialog(self, self.file_data, self._apply_settings)

    def _apply_settings(self, updated: dict):
        for k in ("prettyname", "filename", "version", "additional_settings", "rarity_weights"):
            if k in updated:
                self.file_data[k] = updated[k]
        self.unsaved_changes = True
        fname = os.path.basename(self.current_filepath) if self.current_filepath else "untitled"
        self.file_label.configure(text=f"{self.file_data.get('prettyname', fname)} ({fname})")
        self._set_status("Settings updated")

    # ── Table Management ─────────────────────────────────────────────────────

    def _refresh_tables(self):
        for w in self.tables_frame.winfo_children():
            w.destroy()
        if not self.file_data or "tables" not in self.file_data:
            return
        for name in self.file_data["tables"]:
            count = len(self.file_data["tables"][name])
            ctk.CTkButton(
                self.tables_frame, text=f"{name} ({count})", anchor="w", height=30, font=("", 12),
                fg_color="transparent" if name != self.current_table else None,
                command=lambda t=name: self._select_table(t),
            ).pack(fill="x", pady=1)

    def _select_table(self, name: str):
        self.current_table = name
        self.current_item_index = None
        self._refresh_tables()
        self._refresh_items()
        self._clear_editor()
        self._set_status(f"Table: {name}")

    def add_table(self):
        if not self.file_data:
            messagebox.showinfo("No File", "Open a file first.")
            return
        dialog = ctk.CTkInputDialog(text="Enter table name:", title="Add Table")
        name = dialog.get_input()
        if name and name.strip():
            name = name.strip().lower().replace(" ", "_")
            if name in self.file_data.get("tables", {}):
                messagebox.showwarning("Exists", f"Table '{name}' already exists.")
                return
            self.file_data.setdefault("tables", {})[name] = []
            self.unsaved_changes = True
            self._refresh_tables()
            self._select_table(name)

    # ── Item List ────────────────────────────────────────────────────────────

    def _refresh_items(self):
        for w in self.items_frame.winfo_children():
            w.destroy()
        if not self.current_table or not self.file_data:
            self.item_count_label.configure(text="")
            return
        items = self.file_data["tables"].get(self.current_table, [])
        search = self.search_var.get().strip().lower()

        rarity_colors = {"Common": "#808080", "Uncommon": "#2ecc71", "Rare": "#3498db",
                         "Legendary": "#f39c12", "Mythic": "#9b59b6"}

        filtered = [(i, it) for i, it in enumerate(items)
                    if not search or search in it.get("name", f"Item {i}").lower()]
        self.item_count_label.configure(text=f"({len(filtered)}/{len(items)})")

        for idx, item in filtered:
            name = item.get("name", f"Item {idx}")
            item_id = item.get("id", "?")
            color = rarity_colors.get(item.get("rarity", ""), "#808080")

            row_frame = ctk.CTkFrame(self.items_frame, fg_color="transparent", height=32)
            row_frame.pack(fill="x", pady=1)
            row_frame.grid_columnconfigure(1, weight=1)

            ctk.CTkFrame(row_frame, width=4, height=26, fg_color=color, corner_radius=2).grid(row=0, column=0, padx=(0, 4))

            is_sel = (idx == self.current_item_index)
            ctk.CTkButton(row_frame, text=f"[{item_id}] {name}", anchor="w", height=28, font=("", 11),
                          fg_color="gray35" if is_sel else "transparent", hover_color="gray30",
                          command=lambda i=idx: self._select_item(i)).grid(row=0, column=1, sticky="ew")

    def _filter_items(self):
        self._refresh_items()

    def _select_item(self, index: int):
        self.current_item_index = index
        self._refresh_items()
        self._load_item_editor()

    # ── Item Operations ──────────────────────────────────────────────────────

    def _get_next_id(self) -> int:
        if not self.file_data:
            return 0
        max_id = -1
        for table in self.file_data.get("tables", {}).values():
            for item in table:
                iid = item.get("id", 0)
                if isinstance(iid, int) and iid > max_id:
                    max_id = iid
        return max_id + 1

    def add_item_from_template(self):
        if not self.current_table:
            messagebox.showinfo("No Table", "Select a table first.")
            return
        TemplateDialog(self, self._insert_from_template)

    def _insert_from_template(self, template_name: str):
        tpl = ITEM_TEMPLATES.get(template_name)
        if not tpl:
            return
        new = copy.deepcopy(tpl)
        new["id"] = self._get_next_id()
        items = self.file_data["tables"][self.current_table]
        items.append(new)
        self.unsaved_changes = True
        self.current_item_index = len(items) - 1
        self._refresh_items()
        self._load_item_editor()
        self._set_status(f"Added from template: {template_name}")

    def duplicate_item(self):
        if self.current_table is None or self.current_item_index is None:
            messagebox.showinfo("No Item", "Select an item to duplicate.")
            return
        items = self.file_data["tables"][self.current_table]
        orig = items[self.current_item_index]
        new = copy.deepcopy(orig)
        new["id"] = self._get_next_id()
        new["name"] = orig.get("name", "Item") + " (Copy)"
        items.insert(self.current_item_index + 1, new)
        self.current_item_index += 1
        self.unsaved_changes = True
        self._refresh_items()
        self._load_item_editor()
        self._set_status(f"Duplicated: {orig.get('name', 'Item')}")

    def delete_item(self):
        if self.current_table is None or self.current_item_index is None:
            return
        items = self.file_data["tables"][self.current_table]
        name = items[self.current_item_index].get("name", "this item")
        if not messagebox.askyesno("Confirm Delete", f"Delete '{name}'?"):
            return
        items.pop(self.current_item_index)
        self.unsaved_changes = True
        if self.current_item_index >= len(items):
            self.current_item_index = len(items) - 1 if items else None
        self._refresh_items()
        if self.current_item_index is not None:
            self._load_item_editor()
        else:
            self._clear_editor()
        self._set_status(f"Deleted: {name}")

    def move_item(self):
        if self.current_table is None or self.current_item_index is None:
            messagebox.showinfo("No Item", "Select an item to move.")
            return
        tables = [t for t in self.file_data["tables"] if t != self.current_table]
        if not tables:
            messagebox.showinfo("No Target", "No other tables to move to.")
            return
        MoveDialog(self, tables, self._execute_move)

    def _execute_move(self, target: str):
        items = self.file_data["tables"][self.current_table]
        item = items.pop(self.current_item_index)
        self.file_data["tables"][target].append(item)
        self.unsaved_changes = True
        self.current_item_index = None
        self._refresh_tables()
        self._refresh_items()
        self._clear_editor()
        self._set_status(f"Moved '{item.get('name', 'Item')}' to {target}")

    def _reorder_item(self, direction: int):
        if self.current_table is None or self.current_item_index is None:
            return
        items = self.file_data["tables"][self.current_table]
        new_idx = self.current_item_index + direction
        if 0 <= new_idx < len(items):
            items[self.current_item_index], items[new_idx] = items[new_idx], items[self.current_item_index]
            self.current_item_index = new_idx
            self.unsaved_changes = True
            self._refresh_items()

    # ── Autofill ─────────────────────────────────────────────────────────────

    def _autofill_from_platform(self):
        """Copy firearm fields from an existing item that shares the same platform."""
        if not self.file_data or self.current_table is None or self.current_item_index is None:
            messagebox.showinfo("No Item", "Select an item first.")
            return

        self._apply_changes()
        item = self.file_data["tables"][self.current_table][self.current_item_index]
        platform = item.get("platform", "").strip()

        if not platform:
            # Let user pick from known platforms
            platforms = self._collect_known_platforms()
            if not platforms:
                messagebox.showinfo("No Platforms", "No platforms found in the loaded file.")
                return
            dialog = ctk.CTkInputDialog(text=f"Enter platform ({', '.join(list(platforms)[:15])}):",
                                        title="Autofill – Enter Platform")
            platform = dialog.get_input()
            if not platform or not platform.strip():
                return
            platform = platform.strip()

        # Find matching items
        matches = []
        for tname, titems in self.file_data["tables"].items():
            for idx, other in enumerate(titems):
                if other.get("platform") == platform and other is not item:
                    matches.append((tname, idx, other))

        if not matches:
            messagebox.showinfo("No Matches", f"No other items with platform '{platform}'.")
            return

        if len(matches) == 1:
            self._apply_autofill(item, matches[0][2])
        else:
            AutofillPickerDialog(self, matches, lambda src: self._apply_autofill(item, src))

    def _apply_autofill(self, item: dict, source: dict):
        for key in _AUTOFILL_FIELDS:
            if key in source:
                item[key] = copy.deepcopy(source[key])

        # Accessories – copy template, clear current
        if "accessories" in source:
            acc = copy.deepcopy(source["accessories"])
            if isinstance(acc, list):
                for a in acc:
                    if isinstance(a, dict):
                        a["current"] = None
            item["accessories"] = acc

        # Parts – copy template, clear current/durability
        if "parts" in source:
            parts = copy.deepcopy(source["parts"])
            if isinstance(parts, list):
                for p in parts:
                    if isinstance(p, dict):
                        p["current"] = {"id": None}
                        p["durability"] = None
            item["parts"] = parts

        if not item.get("platform"):
            item["platform"] = source.get("platform", "")

        self.unsaved_changes = True
        self._load_item_editor()
        self._set_status(f"Autofilled from: {source.get('name', 'Unknown')}")

    def _collect_known_platforms(self) -> set[str]:
        platforms: set[str] = set()
        if not self.file_data:
            return platforms
        for table in self.file_data.get("tables", {}).values():
            for item in table:
                p = item.get("platform")
                if p and isinstance(p, str):
                    platforms.add(p)
        return platforms

    # ── Item Editor ──────────────────────────────────────────────────────────

    def _clear_editor(self):
        for w in self.editor_scroll.winfo_children():
            w.destroy()
        self.field_widgets.clear()
        self.editor_title.configure(text="Select an item to edit")

    def _load_item_editor(self):
        self._clear_editor()
        if self.current_table is None or self.current_item_index is None:
            return
        items = self.file_data["tables"][self.current_table]
        if self.current_item_index >= len(items):
            return

        item = items[self.current_item_index]
        self.editor_title.configure(text=f"Editing: {item.get('name', 'Unknown')} (ID: {item.get('id', '?')})")

        row = 0
        priority = ["name", "id", "value", "description", "rarity", "weight",
                     "random_quantity", "can_stack", "firearm", "attachment",
                     "type", "subtype", "platform", "caliber", "action",
                     "bolt", "bolt_catch", "cyclic", "burst_count", "burst_cyclic",
                     "magazinetype", "magazinesystem", "capacity", "jamrate",
                     "in_armory", "armory_category", "armory_subcategory",
                     "reliability", "spring_durability", "durability", "marking_system",
                     "slot", "modifiers", "window",
                     "magicsoundsystem", "temp_gain_per_shot", "temp_loss_per_cooling_cycle"]
        ui_fields = {"accessories", "parts", "subslots"}

        shown: set[str] = set()
        # Priority scalar fields
        for key in priority:
            if key in item and key not in ui_fields:
                row = self._add_field_row(row, key, item[key], item)
                shown.add(key)

        # Accessories / Parts / Subslots with dedicated UI
        for key in ("accessories", "parts", "subslots"):
            if key in item:
                row = self._add_ui_field_row(row, key, item[key])
                shown.add(key)

        # Remaining fields
        for key, val in item.items():
            if key not in shown:
                if key in ui_fields:
                    row = self._add_ui_field_row(row, key, val)
                elif isinstance(val, (list, dict)) and key not in _INLINE_ARRAY_KEYS.union({"magazinesystem"}):
                    row = self._add_complex_field_row(row, key, val)
                else:
                    row = self._add_field_row(row, key, val, item)

    def _add_field_row(self, row: int, key: str, value: Any, item: dict) -> int:
        frame = ctk.CTkFrame(self.editor_scroll, fg_color="transparent")
        frame.grid(row=row, column=0, columnspan=2, padx=5, pady=2, sticky="ew")
        frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(frame, text=key, font=("", 12), width=180, anchor="w").grid(row=0, column=0, padx=(5, 10), sticky="w")

        # Delete button
        ctk.CTkButton(frame, text="✕", width=24, height=24, font=("", 10),
                      fg_color="transparent", hover_color="darkred",
                      command=lambda k=key: self._remove_field(k)).grid(row=0, column=2, padx=2)

        # ── field-specific widgets ──
        if key == "rarity":
            var = ctk.StringVar(value=str(value))
            ctk.CTkComboBox(frame, values=RARITY_OPTIONS, variable=var, width=200).grid(row=0, column=1, sticky="w")
            self.field_widgets[key] = ("combobox", var)

        elif key == "bolt" and item.get("firearm"):
            var = ctk.StringVar(value=str(value))
            ctk.CTkComboBox(frame, values=BOLT_OPTIONS, variable=var, width=200).grid(row=0, column=1, sticky="w")
            self.field_widgets[key] = ("combobox", var)

        elif key == "magazinetype" and item.get("firearm"):
            var = ctk.StringVar(value=str(value))
            ctk.CTkComboBox(frame, values=MAGAZINE_TYPES, variable=var, width=250).grid(row=0, column=1, sticky="w")
            self.field_widgets[key] = ("combobox", var)

        elif key == "subtype" and item.get("firearm"):
            var = ctk.StringVar(value=str(value))
            ctk.CTkComboBox(frame, values=FIREARM_SUBTYPES, variable=var, width=200).grid(row=0, column=1, sticky="w")
            self.field_widgets[key] = ("combobox", var)

        elif key == "type" and item.get("firearm"):
            var = ctk.StringVar(value=str(value))
            ctk.CTkComboBox(frame, values=FIREARM_TYPES, variable=var, width=200).grid(row=0, column=1, sticky="w")
            self.field_widgets[key] = ("combobox", var)

        elif key == "marking_system":
            var = ctk.StringVar(value=str(value) if value else "")
            ctk.CTkComboBox(frame, values=MARKING_SYSTEMS, variable=var, width=250).grid(row=0, column=1, sticky="w")
            self.field_widgets[key] = ("combobox", var)

        elif key == "action" and isinstance(value, list):
            var = ctk.StringVar(value=", ".join(value))
            ef = ctk.CTkFrame(frame, fg_color="transparent")
            ef.grid(row=0, column=1, sticky="ew"); ef.grid_columnconfigure(0, weight=1)
            ctk.CTkEntry(ef, textvariable=var).grid(row=0, column=0, sticky="ew")
            for ci, act in enumerate(ACTION_OPTIONS[:4]):
                ctk.CTkButton(ef, text=f"+{act}", width=50, height=24, font=("", 10),
                              command=lambda a=act, v=var: self._toggle_csv(v, a)).grid(row=0, column=ci + 1, padx=1)
            self.field_widgets[key] = ("csv_list", var)

        elif key in ("caliber", "conflicts_with") or (key == "magazinesystem" and isinstance(value, list)):
            joined = ", ".join(str(v) for v in value) if isinstance(value, list) else str(value)
            var = ctk.StringVar(value=joined)
            ctk.CTkEntry(frame, textvariable=var).grid(row=0, column=1, sticky="ew")
            self.field_widgets[key] = ("csv_list", var)

        elif key == "description":
            tb = ctk.CTkTextbox(frame, height=60, font=("", 12))
            tb.grid(row=0, column=1, sticky="ew")
            tb.insert("1.0", str(value) if value is not None else "")
            self.field_widgets[key] = ("textbox", tb)

        elif isinstance(value, bool):
            var = ctk.BooleanVar(value=value)
            ctk.CTkSwitch(frame, variable=var, text="").grid(row=0, column=1, sticky="w")
            self.field_widgets[key] = ("bool", var)

        elif value is None:
            var = ctk.StringVar(value="null")
            ctk.CTkEntry(frame, textvariable=var, width=200).grid(row=0, column=1, sticky="w")
            self.field_widgets[key] = ("nullable", var)

        elif isinstance(value, (int, float)):
            var = ctk.StringVar(value=str(value))
            ctk.CTkEntry(frame, textvariable=var, width=200).grid(row=0, column=1, sticky="w")
            self.field_widgets[key] = ("number", var)

        elif isinstance(value, str):
            var = ctk.StringVar(value=value)
            ctk.CTkEntry(frame, textvariable=var).grid(row=0, column=1, sticky="ew")
            self.field_widgets[key] = ("string", var)

        else:
            var = ctk.StringVar(value=json.dumps(value, ensure_ascii=False))
            ctk.CTkEntry(frame, textvariable=var).grid(row=0, column=1, sticky="ew")
            self.field_widgets[key] = ("json_string", var)

        return row + 1

    # ── UI-based editors for accessories / parts / subslots ──

    def _add_ui_field_row(self, row: int, key: str, value: Any) -> int:
        frame = ctk.CTkFrame(self.editor_scroll, fg_color="transparent")
        frame.grid(row=row, column=0, columnspan=2, padx=5, pady=2, sticky="ew")
        frame.grid_columnconfigure(1, weight=1)

        count = len(value) if isinstance(value, list) else ("null" if value is None else "?")
        ctk.CTkLabel(frame, text=f"{key}", font=("", 12, "bold"), width=180, anchor="w").grid(
            row=0, column=0, padx=(5, 10), sticky="w")
        ctk.CTkLabel(frame, text=f"[{count} entries]" if isinstance(count, int) else str(count),
                     font=("", 11)).grid(row=0, column=1, sticky="w")

        btn_frame = ctk.CTkFrame(frame, fg_color="transparent")
        btn_frame.grid(row=0, column=2, padx=5)

        if key == "accessories":
            ctk.CTkButton(btn_frame, text="Edit UI", width=70, height=26,
                          command=lambda: self._open_accessories_editor(key, value)).pack(side="left", padx=2)
        elif key == "parts":
            ctk.CTkButton(btn_frame, text="Edit UI", width=70, height=26,
                          command=lambda: self._open_parts_editor(key, value)).pack(side="left", padx=2)
        else:
            ctk.CTkButton(btn_frame, text="Edit UI", width=70, height=26,
                          command=lambda: self._open_accessories_editor(key, value)).pack(side="left", padx=2)

        ctk.CTkButton(btn_frame, text="JSON", width=50, height=26,
                      command=lambda k=key, v=value: self._open_json_editor(k, v)).pack(side="left", padx=2)
        ctk.CTkButton(btn_frame, text="✕", width=24, height=26, font=("", 10),
                      fg_color="transparent", hover_color="darkred",
                      command=lambda k=key: self._remove_field(k)).pack(side="left", padx=2)

        self.field_widgets[key] = ("complex", value)
        return row + 1

    def _open_accessories_editor(self, key: str, value: Any):
        def on_save(new_val):
            if self.current_table and self.current_item_index is not None:
                self.file_data["tables"][self.current_table][self.current_item_index][key] = new_val
                self.field_widgets[key] = ("complex", new_val)
                self.unsaved_changes = True
                self._load_item_editor()
        AccessoriesEditorDialog(self, value if isinstance(value, list) else [], on_save)

    def _open_parts_editor(self, key: str, value: Any):
        def on_save(new_val):
            if self.current_table and self.current_item_index is not None:
                self.file_data["tables"][self.current_table][self.current_item_index][key] = new_val
                self.field_widgets[key] = ("complex", new_val)
                self.unsaved_changes = True
                self._load_item_editor()
        PartsEditorDialog(self, value if isinstance(value, list) else [], on_save)

    # ── Generic complex field (fallback JSON editor) ──

    def _add_complex_field_row(self, row: int, key: str, value: Any) -> int:
        frame = ctk.CTkFrame(self.editor_scroll, fg_color="transparent")
        frame.grid(row=row, column=0, columnspan=2, padx=5, pady=2, sticky="ew")
        frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(frame, text=key, font=("", 12, "bold"), width=180, anchor="w").grid(
            row=0, column=0, padx=(5, 10), sticky="w")

        if isinstance(value, list):
            summary = f"[{len(value)} items]"
        elif isinstance(value, dict):
            summary = f"{{{len(value)} keys}}"
        elif value is None:
            summary = "null"
        else:
            summary = str(value)[:50]
        ctk.CTkLabel(frame, text=summary, font=("", 11)).grid(row=0, column=1, sticky="w")

        ctk.CTkButton(frame, text="Edit JSON", width=90, height=26,
                      command=lambda k=key, v=value: self._open_json_editor(k, v)).grid(row=0, column=2, padx=5)
        ctk.CTkButton(frame, text="✕", width=24, height=24, font=("", 10),
                      fg_color="transparent", hover_color="darkred",
                      command=lambda k=key: self._remove_field(k)).grid(row=0, column=3, padx=2)

        self.field_widgets[key] = ("complex", value)
        return row + 1

    def _open_json_editor(self, key: str, value: Any):
        def on_save(new_val):
            self.field_widgets[key] = ("complex", new_val)
            if self.current_table and self.current_item_index is not None:
                self.file_data["tables"][self.current_table][self.current_item_index][key] = new_val
                self.unsaved_changes = True
                self._load_item_editor()
        JSONEditorDialog(self, f"Edit: {key}", value, on_save)

    # ── Field helpers ────────────────────────────────────────────────────────

    def _toggle_csv(self, var: ctk.StringVar, value: str):
        current = [v.strip() for v in var.get().split(",") if v.strip()]
        if value in current:
            current.remove(value)
        else:
            current.append(value)
        var.set(", ".join(current))

    def _remove_field(self, key: str):
        if self.current_table is None or self.current_item_index is None:
            return
        if key in ("name", "id"):
            messagebox.showwarning("Cannot Remove", f"'{key}' is a required field.")
            return
        if not messagebox.askyesno("Remove Field", f"Remove field '{key}'?"):
            return
        item = self.file_data["tables"][self.current_table][self.current_item_index]
        if key in item:
            del item[key]
            self.unsaved_changes = True
            self._load_item_editor()
            self._set_status(f"Removed field: {key}")

    def _add_custom_field(self):
        if self.current_table is None or self.current_item_index is None:
            messagebox.showinfo("No Item", "Select an item first.")
            return
        AddFieldDialog(self, self._execute_add_field)

    def _execute_add_field(self, field_name: str, field_type: str):
        item = self.file_data["tables"][self.current_table][self.current_item_index]
        if field_name in item:
            messagebox.showwarning("Exists", f"Field '{field_name}' already exists.")
            return
        defaults = {"string": "", "number": 0, "float": 0.0, "boolean": False,
                    "list": [], "object": {}, "null": None}
        item[field_name] = defaults.get(field_type, "")
        self.unsaved_changes = True
        self._load_item_editor()
        self._set_status(f"Added field: {field_name} ({field_type})")

    # ── Apply Changes ────────────────────────────────────────────────────────

    def _apply_changes(self):
        if self.current_table is None or self.current_item_index is None:
            return
        item = self.file_data["tables"][self.current_table][self.current_item_index]

        for key, (ftype, wov) in self.field_widgets.items():
            try:
                if ftype == "string":
                    item[key] = wov.get()
                elif ftype == "combobox":
                    item[key] = wov.get()
                elif ftype == "number":
                    raw = wov.get().strip()
                    orig = item.get(key)
                    if isinstance(orig, int) and "." not in raw:
                        item[key] = int(raw)
                    else:
                        item[key] = float(raw)
                elif ftype == "bool":
                    item[key] = wov.get()
                elif ftype == "nullable":
                    raw = wov.get().strip()
                    if raw.lower() == "null" or raw == "":
                        item[key] = None
                    else:
                        try:
                            item[key] = float(raw) if "." in raw else int(raw)
                        except ValueError:
                            item[key] = raw
                elif ftype == "csv_list":
                    raw = wov.get().strip()
                    item[key] = [v.strip() for v in raw.split(",") if v.strip()] if raw else []
                elif ftype == "textbox":
                    item[key] = wov.get("1.0", "end").strip()
                elif ftype == "json_string":
                    raw = wov.get().strip()
                    try:
                        item[key] = json.loads(raw)
                    except json.JSONDecodeError:
                        item[key] = raw
                elif ftype == "complex":
                    item[key] = wov
            except (ValueError, TypeError) as e:
                messagebox.showwarning("Field Error", f"Could not apply field '{key}': {e}")

        self.unsaved_changes = True
        self._refresh_items()
        self.editor_title.configure(text=f"Editing: {item.get('name', 'Unknown')} (ID: {item.get('id', '?')})")
        self._set_status("Changes applied")

    # ── Status ───────────────────────────────────────────────────────────────

    def _set_status(self, text: str):
        prefix = "● " if self.unsaved_changes else ""
        self.status_var.set(f"{prefix}{text}")


# ─── Entry Point ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = SLDTBLEditor()
    app.mainloop()
