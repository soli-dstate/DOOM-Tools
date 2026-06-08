#!/usr/bin/env python3
"""GUI for decoding DOOM-Tools signed save files (debugging tool).

Saves are a base85-encoded JSON envelope ``{"_sig": ..., "_data": ...}`` — not
encrypted. The ``.save_key`` is only used to HMAC-verify the signature. This
window lets you browse to a save, decode it, verify the signature, view the
JSON, and copy/save it. Pointing it at a ``.save_key`` shows the key bytes.

Run:  python scripts/decrypt_save_gui.py
"""

import json
import os
import sys

import customtkinter
from tkinter import filedialog

# Reuse the console tool's decode logic (same folder).
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from decrypt_save import (  # noqa: E402
    PORTABLE_KEY,
    _autofind_key,
    _looks_like_raw_key,
    decode_save,
    key_info_text,
    write_save,
)

STATUS_COLORS = {
    "ok": "#3FB950",
    "unsigned": "#D29922",
    "no_key": "#D29922",
    "tampered": "#F85149",
    "key": "#58A6FF",
    "error": "#F85149",
}


class DecryptApp(customtkinter.CTk):
    def __init__(self):
        super().__init__()
        self.title("DOOM-Tools Save Decoder")
        self.geometry("980x720")
        customtkinter.set_appearance_mode("dark")

        self._last_data = None  # decoded python object, for Save JSON

        pad = {"padx": 10, "pady": 6}

        # ── File row ──────────────────────────────────────────────────────
        file_row = customtkinter.CTkFrame(self)
        file_row.pack(fill="x", **pad)
        customtkinter.CTkLabel(file_row, text="Save file:", width=80, anchor="w").pack(side="left", padx=(10, 4), pady=8)
        self.file_var = customtkinter.StringVar()
        customtkinter.CTkEntry(file_row, textvariable=self.file_var).pack(side="left", fill="x", expand=True, padx=4, pady=8)
        customtkinter.CTkButton(file_row, text="Browse…", width=90, command=self._browse_file).pack(side="left", padx=(4, 10), pady=8)

        # ── Key row ───────────────────────────────────────────────────────
        key_row = customtkinter.CTkFrame(self)
        key_row.pack(fill="x", **pad)
        customtkinter.CTkLabel(key_row, text="Save key:", width=80, anchor="w").pack(side="left", padx=(10, 4), pady=8)
        self.key_var = customtkinter.StringVar()
        self.key_entry = customtkinter.CTkEntry(key_row, textvariable=self.key_var, placeholder_text="auto-find next to save")
        self.key_entry.pack(side="left", fill="x", expand=True, padx=4, pady=8)
        customtkinter.CTkButton(key_row, text="Browse…", width=90, command=self._browse_key).pack(side="left", padx=4, pady=8)
        self.portable_var = customtkinter.BooleanVar(value=False)
        customtkinter.CTkCheckBox(key_row, text="Portable key", variable=self.portable_var,
                                  command=self._sync_key_state).pack(side="left", padx=(4, 10), pady=8)

        # ── Action row ────────────────────────────────────────────────────
        act_row = customtkinter.CTkFrame(self)
        act_row.pack(fill="x", **pad)
        customtkinter.CTkButton(act_row, text="Decode", width=110, command=self._decode).pack(side="left", padx=10, pady=8)
        self.compact_var = customtkinter.BooleanVar(value=False)
        customtkinter.CTkCheckBox(act_row, text="Compact JSON", variable=self.compact_var,
                                  command=self._redisplay).pack(side="left", padx=6, pady=8)
        customtkinter.CTkButton(act_row, text="Copy", width=90, command=self._copy).pack(side="right", padx=6, pady=8)
        customtkinter.CTkButton(act_row, text="Save JSON…", width=110, command=self._save_json).pack(side="right", padx=6, pady=8)
        customtkinter.CTkButton(act_row, text="Encode → save…", width=130,
                                fg_color="#1F6F43", hover_color="#2D8A57",
                                command=self._encode).pack(side="right", padx=6, pady=8)

        self.status_label = customtkinter.CTkLabel(self, text="Choose a save file and click Decode.",
                                                   anchor="w", font=customtkinter.CTkFont(size=13, weight="bold"))
        self.status_label.pack(fill="x", padx=14, pady=(0, 4))

        # ── Output ────────────────────────────────────────────────────────
        self.output = customtkinter.CTkTextbox(self, font=customtkinter.CTkFont(family="Consolas", size=13), wrap="none")
        self.output.pack(fill="both", expand=True, padx=10, pady=(0, 10))

    # ── helpers ──────────────────────────────────────────────────────────
    def _sync_key_state(self):
        state = "disabled" if self.portable_var.get() else "normal"
        self.key_entry.configure(state=state)

    def _browse_file(self):
        path = filedialog.askopenfilename(
            title="Select save or .save_key",
            filetypes=[("DOOM-Tools saves", "*.sldsv *.sldenlt *.sldlct"),
                       ("Save key", ".save_key"), ("All files", "*.*")],
        )
        if path:
            self.file_var.set(path)

    def _browse_key(self):
        path = filedialog.askopenfilename(title="Select .save_key",
                                          filetypes=[("Save key", ".save_key"), ("All files", "*.*")])
        if path:
            self.key_var.set(path)

    def _set_status(self, text, kind):
        self.status_label.configure(text=text, text_color=STATUS_COLORS.get(kind, "#FFFFFF"))

    def _set_output(self, text):
        self.output.configure(state="normal")
        self.output.delete("1.0", "end")
        self.output.insert("1.0", text)

    def _load_key(self):
        if self.portable_var.get():
            return PORTABLE_KEY, "portable key"
        key_path = self.key_var.get().strip()
        if not key_path:
            key_path = _autofind_key(self.file_var.get().strip())
            if key_path:
                self.key_var.set(key_path)
        if key_path and os.path.isfile(key_path):
            with open(key_path, "rb") as f:
                return f.read(), key_path
        return None, None

    def _decode(self):
        path = self.file_var.get().strip()
        if not path or not os.path.isfile(path):
            self._set_status("File not found.", "error")
            return

        # A raw .save_key → just show its bytes.
        if _looks_like_raw_key(path):
            try:
                self._last_data = None
                self._set_output(key_info_text(path))
                self._set_status("Key file (32 raw bytes) — not a save.", "key")
            except Exception as e:
                self._set_status(f"Error: {e}", "error")
            return

        # Build candidate keys to try, in order. If the user forced portable or
        # gave a key, honour that first; then fall back to the other so the user
        # doesn't have to know whether a file was signed with the local or the
        # portable key (.sldlct/.sldenlt use portable).
        primary_key, key_src = self._load_key()
        candidates = []
        if primary_key is not None:
            candidates.append((primary_key, key_src))
        if not self.portable_var.get():
            candidates.append((PORTABLE_KEY, "portable key"))
        if not candidates:
            candidates.append((None, None))

        data = sig = status = None
        chosen_src = None
        try:
            for cand_key, cand_src in candidates:
                data, sig, status = decode_save(path, key=cand_key)
                chosen_src = cand_src
                if status in ("ok", "unsigned"):
                    break
        except Exception as e:
            self._last_data = None
            self._set_output(f"{type(e).__name__}: {e}")
            self._set_status("Failed to decode (not a valid save?).", "error")
            return

        key_src = chosen_src
        self._last_data = data
        self._redisplay()

        messages = {
            "ok": f"Signature OK  (verified with {key_src}).",
            "tampered": f"SIGNATURE MISMATCH — data was modified or wrong key ({key_src}).",
            "no_key": "Decoded. No key provided — signature NOT verified.",
            "unsigned": "Decoded. Legacy unsigned file.",
        }
        self._set_status(messages.get(status, f"Status: {status}"), status)

    def _redisplay(self):
        if self._last_data is None:
            return
        indent = None if self.compact_var.get() else 2
        self._set_output(json.dumps(self._last_data, ensure_ascii=False, indent=indent))

    def _copy(self):
        text = self.output.get("1.0", "end-1c")
        if text:
            self.clipboard_clear()
            self.clipboard_append(text)
            self._set_status("Copied to clipboard.", "ok")

    def _encode(self):
        """Parse the JSON in the textbox, sign it, and write a valid save."""
        text = self.output.get("1.0", "end-1c").strip()
        if not text:
            self._set_status("Nothing to encode — decode/paste JSON first.", "error")
            return
        try:
            data = json.loads(text)
        except (json.JSONDecodeError, ValueError) as e:
            self._set_status(f"Invalid JSON: {e}", "error")
            return

        portable = self.portable_var.get()
        key = None
        key_src = "portable key"
        if not portable:
            key, key_src = self._load_key()
            if key is None:
                self._set_status("No key found — pick a .save_key or tick Portable key.", "error")
                return

        suggested = os.path.basename(self.file_var.get().strip() or "save")
        if suggested.endswith(".json"):
            suggested = suggested[:-5]
        if not suggested.endswith((".sldsv", ".sldenlt", ".sldlct")):
            suggested += ".sldsv"
        out = filedialog.asksaveasfilename(
            title="Write signed save", defaultextension=".sldsv", initialfile=suggested,
            filetypes=[("DOOM-Tools save", "*.sldsv"), ("Loot transfer", "*.sldenlt *.sldlct"), ("All files", "*.*")],
        )
        if not out:
            return
        try:
            write_save(out, data, key=key, portable=portable)
            self._set_status(f"Encoded + signed ({key_src}) → {out}", "ok")
        except Exception as e:
            self._set_status(f"Encode failed: {e}", "error")

    def _save_json(self):
        if self._last_data is None:
            self._set_status("Nothing to save — decode a file first.", "error")
            return
        suggested = os.path.splitext(os.path.basename(self.file_var.get().strip() or "save"))[0] + ".json"
        out = filedialog.asksaveasfilename(title="Save decoded JSON", defaultextension=".json",
                                           initialfile=suggested, filetypes=[("JSON", "*.json"), ("All files", "*.*")])
        if not out:
            return
        try:
            with open(out, "w", encoding="utf-8") as f:
                json.dump(self._last_data, f, ensure_ascii=False, indent=2)
            self._set_status(f"Wrote {out}", "ok")
        except Exception as e:
            self._set_status(f"Save failed: {e}", "error")


def main():
    app = DecryptApp()
    # If a path was passed on the command line, prefill it.
    if len(sys.argv) > 1:
        app.file_var.set(sys.argv[1])
    app.mainloop()


if __name__ == "__main__":
    main()
