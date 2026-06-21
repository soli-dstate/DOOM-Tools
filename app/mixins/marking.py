"""MarkingMixin — App methods for the "marking" feature area."""
from app.foundation import *
import logging


class MarkingMixin:

    def _open_magazine_marking_dialog(self, magazine, weapon, save_data, update_callback=None):
        if not magazine or not isinstance(magazine, dict):
            self._popup_show_info("Mark Magazine", "No magazine to mark.")
            return

        marking_system = str(magazine.get("marking_system", "Tape") or "Tape")
        is_dot_matrix = "dot matrix" in marking_system.lower() or "magpul" in marking_system.lower()
        is_pistol = "pistol" in marking_system.lower()

        if is_dot_matrix:
            weapon_subtype = str(weapon.get("subtype", "") or weapon.get("type", "") or "").lower()
            if is_pistol or weapon_subtype in ("pistol", "handgun", "revolver"):
                max_chars = 2
            else:
                max_chars = 4
        else:
            max_chars = 12

        current_marking = magazine.get("marking_text", "")
        current_color = magazine.get("marking_color", "white")

        dialog = customtkinter.CTkToplevel(self.root)
        dialog.title("Mark Magazine" if is_dot_matrix else "Tape Label Magazine")
        dialog.transient(self.root)

        if is_dot_matrix:
            dw, dh = 500, 420
        else:
            dw, dh = 400, 300
        self._center_popup_on_window(dialog, dw, dh)

        customtkinter.CTkLabel(
            dialog,
            text=f"Marking System: {marking_system}",
            font=customtkinter.CTkFont(size=14, weight="bold")
        ).pack(pady=(10, 5))

        color_var = customtkinter.StringVar(value=current_color)
        color_frame = customtkinter.CTkFrame(dialog, fg_color="transparent")
        color_frame.pack(pady=5)
        customtkinter.CTkLabel(color_frame, text="Color:", font=customtkinter.CTkFont(size=12)).pack(side="left", padx=5)
        for cname, chex in MARKING_COLORS.items():
            rb = customtkinter.CTkRadioButton(
                color_frame, text=cname.capitalize(), variable=color_var, value=cname,
                font=customtkinter.CTkFont(size=11)
            )
            rb.pack(side="left", padx=5)

        text_var = customtkinter.StringVar(value=current_marking)
        text_frame = customtkinter.CTkFrame(dialog, fg_color="transparent")
        text_frame.pack(pady=5)
        customtkinter.CTkLabel(text_frame, text=f"Text (max {max_chars} chars):", font=customtkinter.CTkFont(size=12)).pack(side="left", padx=5)
        text_entry = customtkinter.CTkEntry(text_frame, textvariable=text_var, width=150)
        text_entry.pack(side="left", padx=5)

        preview_frame = customtkinter.CTkFrame(dialog, fg_color="#1a1a1a", corner_radius=8)
        preview_frame.pack(pady=10, padx=20, fill="x")
        customtkinter.CTkLabel(preview_frame, text="Preview:", font=customtkinter.CTkFont(size=11)).pack(pady=(5, 2))
        dot_canvas = None
        tape_label = None

        if is_dot_matrix:
            import tkinter as _tk_dm
            canvas_w = max_chars * 4 * 8 + (max_chars - 1) * 10 + 20
            canvas_h = 5 * 8 + 20
            dot_canvas = _tk_dm.Canvas(preview_frame, width=canvas_w, height=canvas_h, bg="#1a1a1a", highlightthickness=0)
            dot_canvas.pack(pady=5)
        else:
            tape_label = customtkinter.CTkLabel(
                preview_frame, text="", font=customtkinter.CTkFont(size=16, weight="bold"),
                fg_color="#d4c896", text_color="#000000", corner_radius=4, width=200, height=30
            )
            tape_label.pack(pady=5)

        def update_preview(*_args):
            txt = text_var.get()[:max_chars]
            col = MARKING_COLORS.get(color_var.get(), "#FFFFFF")

            if is_dot_matrix and dot_canvas:
                dot_canvas.delete("all")
                grids = render_dot_matrix_text(txt, max_chars)
                dot_size = 6
                gap = 2
                char_gap = 10
                x_off = 10
                y_off = 10
                for ci, grid in enumerate(grids):
                    for row_i, row in enumerate(grid):
                        for col_i, val in enumerate(row):
                            x = x_off + ci * (3 * (dot_size + gap) + char_gap) + col_i * (dot_size + gap)
                            y = y_off + row_i * (dot_size + gap)
                            fill = col if val else "#333333"
                            dot_canvas.create_oval(x, y, x + dot_size, y + dot_size, fill=fill, outline="")
            elif tape_label:
                tape_label.configure(text=txt or " ", text_color=col if col != "#FFFFFF" else "#000000")

        text_var.trace_add("write", update_preview)
        color_var.trace_add("write", update_preview)
        update_preview()

        def apply_marking():
            txt = text_var.get()[:max_chars].strip()
            col = color_var.get()
            magazine["marking_text"] = txt
            magazine["marking_color"] = col
            try:
                self._save_combat_state(save_data)
            except Exception:
                logging.exception("Suppressed exception")
            dialog.destroy()
            if update_callback:
                try:
                    update_callback()
                except Exception:
                    logging.exception("Suppressed exception")

        def clear_marking():
            magazine.pop("marking_text", None)
            magazine.pop("marking_color", None)
            try:
                self._save_combat_state(save_data)
            except Exception:
                logging.exception("Suppressed exception")
            dialog.destroy()
            if update_callback:
                try:
                    update_callback()
                except Exception:
                    logging.exception("Suppressed exception")

        btn_frame = customtkinter.CTkFrame(dialog, fg_color="transparent")
        btn_frame.pack(pady=10)
        customtkinter.CTkButton(btn_frame, text="Apply", command=apply_marking, width=100, fg_color="#1a4d1a", hover_color="#2d7a2d").pack(side="left", padx=5)
        customtkinter.CTkButton(btn_frame, text="Clear", command=clear_marking, width=100, fg_color="#8B0000", hover_color="#A00000").pack(side="left", padx=5)
        customtkinter.CTkButton(btn_frame, text="Cancel", command=dialog.destroy, width=100).pack(side="left", padx=5)

        try:
            dialog.grab_set()
            dialog.lift()
            self._safe_focus(dialog)
        except Exception:
            logging.exception("Suppressed exception")

    def _render_magazine_marking_widget(self, parent, magazine, weapon=None):
        if not magazine or not isinstance(magazine, dict):
            return
        marking_text = magazine.get("marking_text")
        if not marking_text:
            return

        marking_system = str(magazine.get("marking_system", "Tape") or "Tape")
        marking_color = magazine.get("marking_color", "white")
        color_hex = MARKING_COLORS.get(marking_color, "#FFFFFF")
        is_dot_matrix = "dot matrix" in marking_system.lower() or "magpul" in marking_system.lower()
        is_pistol = "pistol" in marking_system.lower()

        if is_dot_matrix:
            weapon_subtype = str((weapon or {}).get("subtype", "") or (weapon or {}).get("type", "") or "").lower()
            if is_pistol or weapon_subtype in ("pistol", "handgun", "revolver"):
                max_chars = 2
            else:
                max_chars = 4

            import tkinter as _tk_render
            mark_frame = customtkinter.CTkFrame(parent, fg_color="#1a1a1a", corner_radius=6)
            mark_frame.pack(pady=(2, 5))

            dot_size = 5
            gap = 1
            char_gap = 6
            grids = render_dot_matrix_text(marking_text, max_chars)
            canvas_w = max_chars * 3 * (dot_size + gap) + (max_chars - 1) * char_gap + 12
            canvas_h = 5 * (dot_size + gap) + 10
            canvas = _tk_render.Canvas(mark_frame, width=canvas_w, height=canvas_h, bg="#1a1a1a", highlightthickness=0)
            canvas.pack(padx=4, pady=4)

            x_off = 6
            y_off = 5
            for ci, grid in enumerate(grids):
                for row_i, row in enumerate(grid):
                    for col_i, val in enumerate(row):
                        x = x_off + ci * (3 * (dot_size + gap) + char_gap) + col_i * (dot_size + gap)
                        y = y_off + row_i * (dot_size + gap)
                        fill = color_hex if val else "#2a2a2a"
                        canvas.create_oval(x, y, x + dot_size, y + dot_size, fill=fill, outline="")
        else:
            tape_frame = customtkinter.CTkFrame(parent, fg_color="#d4c896", corner_radius=4)
            tape_frame.pack(pady=(2, 5))
            display_color = color_hex if color_hex != "#FFFFFF" else "#000000"
            customtkinter.CTkLabel(
                tape_frame, text=f" {marking_text} ",
                font=customtkinter.CTkFont(size=11, weight="bold"),
                text_color=display_color, fg_color="transparent"
            ).pack(padx=6, pady=2)
