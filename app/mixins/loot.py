"""LootMixin — App methods for the "loot" feature area."""
from app.foundation import *
import logging


class LootMixin:
    def _open_loot_tool(self):
        logging.info("Looting definition called")
        self._clear_window()

        try:
            self._set_dnd_refresh_handler(
                callback = self._open_loot_tool,
                exts = [
                    global_variables.get("lootcrate_extension", ".sldlct"),
                    global_variables.get("enemyloot_extension", ".sldenlt"),
                ],
            )
        except Exception:
            logging.exception("Suppressed exception")

        try:
            self.root.after(50, self._setup_drag_drop)
        except Exception:
            logging.exception("Suppressed exception")

        self.root.grid_rowconfigure(0, weight = 1)
        self.root.grid_columnconfigure(0, weight = 1)

        main_frame = customtkinter.CTkFrame(self.root)
        main_frame.grid(row = 0, column = 0, sticky = "nsew")

        title_label = customtkinter.CTkLabel(main_frame, text = "Looting", font = customtkinter.CTkFont(size = 24, weight = "bold"))
        title_label.pack(pady = 20)

        try:
            tbl_path = get_current_table_path()
            if not tbl_path or not os.path.exists(tbl_path):
                self._popup_show_info("Error", "No table files found.", sound = "error")
                return

            with open(tbl_path, 'r', encoding = 'utf-8-sig')as f:
                table_data = json.load(f)

            lootcrates = table_data.get("lootcrates", [])

            crate_files = glob.glob(os.path.join("lootcrates", f"*{global_variables['lootcrate_extension']}"))
            for crate_file in crate_files:
                try:
                    crate_data, _, c_status = _signed_json_read(crate_file, allow_unsigned = False, portable = True)
                    if c_status == "tampered":
                        logging.warning(f"Loot crate '{crate_file}' has been tampered with — skipping.")
                        continue
                    elif c_status in ("unsigned", "incompatible_format"):
                        logging.warning(f"Loot crate '{crate_file}' is unsigned or incompatible. Download and run convert_legacy_saves.py from github and run with --resign flag to sign it.")
                        continue
                    elif crate_data is None:
                        continue
                    crate_data["_file_path"]= crate_file
                    lootcrates.append(crate_data)
                    logging.info(f"Loaded custom loot crate: {_sanitize_log(crate_data.get('name', os.path.basename(crate_file)))}")
                except Exception as e:
                    logging.warning(f"Failed to load loot crate file {crate_file}: {e}")

            enemyloots =[]
            enemyloot_files = glob.glob(os.path.join("enemyloot", "*.sldenlt"))
            for el_file in enemyloot_files:
                try:
                    el_data, _, e_status = _signed_json_read(el_file, allow_unsigned = False, portable = True)
                    if e_status == "tampered":
                        logging.warning(f"Enemy loot '{el_file}' has been tampered with — skipping.")
                        continue
                    elif e_status in ("unsigned", "incompatible_format"):
                        logging.warning(f"Enemy loot '{el_file}' is unsigned or incompatible. Download and run convert_legacy_saves.py from github and run with --resign flag to sign it.")
                        continue
                    elif el_data is None:
                        continue
                    el_data["_file_path"]= el_file
                    enemyloots.append(el_data)
                    logging.info(f"Loaded enemy loot: {_sanitize_log(el_data.get('enemy_name', os.path.basename(el_file)))}")
                except Exception as e:
                    logging.warning(f"Failed to load enemy loot file {el_file}: {e}")

            if not lootcrates and not enemyloots:
                error_label = customtkinter.CTkLabel(main_frame, text = "No loot crates or enemy loot available.", font = customtkinter.CTkFont(size = 14), text_color = "orange")
                error_label.pack(pady = 20)
                back_button = self._create_sound_button(main_frame, "Back", lambda:[self._clear_window(), self._build_main_menu()], width = 500, height = 50, font = customtkinter.CTkFont(size = 16))
                back_button.pack(pady = 20)
                return

            scroll_frame = customtkinter.CTkScrollableFrame(main_frame)
            scroll_frame.pack(fill = "both", expand = True, padx = 20, pady = 20)

            def _open_lockpick_minigame(crate, crate_file_path, on_success):
                """Fallout/Skyrim-style rotary lockpick minigame.

                A circular lock face is shown. The player drags a bobby pin
                around the rim to find the sweet spot, then holds the tension
                wrench button to rotate the lock. If the pin is in the sweet
                spot the lock turns; otherwise the pin takes damage. Pins (picks)
                are limited – run out and the crate stays locked.

                Difficulty is derived from crate rarity:
                  Common    → 3 picks, large sweet-spot  (~60°)
                  Uncommon  → 3 picks, medium sweet-spot (~40°)
                  Rare      → 2 picks, small sweet-spot  (~25°)
                  Legendary → 2 picks, tiny sweet-spot   (~15°)
                  Mythic    → 1 pick,  hair-trigger       (~8°)
                """
                import tkinter as _tk_lp
                import math as _math_lp

                rarity = str(crate.get("rarity", "Common")).strip()
                _DIFF = {
                    "Common":    {"picks": 3, "sweet": 60.0, "resistance": 0.6},
                    "Uncommon":  {"picks": 3, "sweet": 40.0, "resistance": 1.0},
                    "Rare":      {"picks": 2, "sweet": 25.0, "resistance": 1.4},
                    "Legendary": {"picks": 2, "sweet": 15.0, "resistance": 1.9},
                    "Mythic":    {"picks": 1, "sweet":  8.0, "resistance": 2.5},
                }
                diff = _DIFF.get(rarity, _DIFF["Common"])
                max_picks      = diff["picks"]
                sweet_half     = diff["sweet"] / 2.0           # half-width of sweet spot in degrees
                resistance     = diff["resistance"]            # pin durability drain multiplier

                _lp_state = {
                    "picks_left":   max_picks,
                    "pin_angle":    0.0,           # degrees, 0 = top, CW positive
                    "lock_rotation": 0.0,          # 0 → 360 = unlocked
                    "sweet_center": random.uniform(0.0, 360.0),
                    "pin_hp":       1.0,           # 1.0 = intact, 0.0 = snapped
                    "tensioning":   False,
                    "dragging":     False,
                    "drag_last_angle": 0.0,
                    "unlocked":     False,
                    "failed":       False,
                    "shake_offset": 0,
                    "shake_job":    None,
                    "pick_playing": False,   # whether pick.wav channel is active
                    "pick_channel": None,    # dedicated pygame channel for pick.wav
                }

                CANVAS_W, CANVAS_H = 460, 480
                LOCK_CX, LOCK_CY   = 230, 220
                LOCK_R             = 140   # outer lock ring radius
                PIN_ORBIT_R        = LOCK_R + 22  # orbit the pin around outside the ring
                PIN_LEN            = 38
                PIN_THICK          = 4

                RARITY_COLORS = {
                    "Common":    "#aaaaaa",
                    "Uncommon":  "#55cc55",
                    "Rare":      "#4499ff",
                    "Legendary": "#cc88ff",
                    "Mythic":    "#ff8844",
                }
                accent_col = RARITY_COLORS.get(rarity, "#aaaaaa")

                win = customtkinter.CTkToplevel(self.root)
                win.title(f"Lockpicking – {crate.get('name', 'Locked Crate')} [{rarity}]")
                win.resizable(False, False)
                win.grab_set()
                win.transient(self.root)
                self._center_popup_on_window(win, CANVAS_W, CANVAS_H + 60)

                canvas = _tk_lp.Canvas(win, width = CANVAS_W, height = CANVAS_H,
                                        bg = "#1a1a1a", highlightthickness = 0)
                canvas.pack()

                info_frame = _tk_lp.Frame(win, bg = "#111111")
                info_frame.pack(fill = "x")

                picks_label = _tk_lp.Label(info_frame, text = "", bg = "#111111",
                                            fg = "#dddddd", font = ("Consolas", 11))
                picks_label.pack(side = "left", padx = 12, pady = 6)

                hint_label = _tk_lp.Label(info_frame, text = "Drag pin · Hold SPACE or button to tension",
                                           bg = "#111111", fg = "#888888", font = ("Consolas", 10))
                hint_label.pack(side = "left", padx = 6)

                # ── sound helpers ──────────────────────────────────────────────
                _PICK_SND_PATH   = os.path.join("sounds", "misc", "lockpicking", "pick.wav")
                _SNAP_SND_PATH   = os.path.join("sounds", "misc", "lockpicking", "snap.ogg")
                _UNLOCK_SND_PATH = os.path.join("sounds", "misc", "lockpicking", "unlock.ogg")

                def _pick_sound_start():
                    """Begin looping pick.wav on a dedicated channel."""
                    if _lp_state["pick_playing"]:
                        return
                    if not os.path.exists(_PICK_SND_PATH):
                        return
                    try:
                        snd = pygame.mixer.Sound(_PICK_SND_PATH)
                        ch  = _lp_state.get("pick_channel")
                        if ch is None:
                            ch = pygame.mixer.find_channel()
                            _lp_state["pick_channel"] = ch
                        if ch:
                            ch.play(snd, loops = -1)  # loop until stopped
                            _lp_state["pick_playing"] = True
                    except Exception:
                        logging.exception("Suppressed exception")

                def _pick_sound_stop():
                    """Stop pick.wav without affecting other channels."""
                    if not _lp_state["pick_playing"]:
                        return
                    try:
                        ch = _lp_state.get("pick_channel")
                        if ch:
                            ch.stop()
                    except Exception:
                        logging.exception("Suppressed exception")
                    _lp_state["pick_playing"] = False

                def _lp_sound(name):
                    p = {"snap": _SNAP_SND_PATH, "unlock": _UNLOCK_SND_PATH}.get(name)
                    if p and os.path.exists(p):
                        try:
                            snd = pygame.mixer.Sound(p)
                            ch  = pygame.mixer.find_channel()
                            if ch:
                                ch.play(snd)
                        except Exception:
                            logging.exception("Suppressed exception")

                # ── geometry helpers ───────────────────────────────────────────
                def _deg_to_rad(d):
                    return d * _math_lp.pi / 180.0

                def _pin_tip_pos(angle_deg):
                    a = _deg_to_rad(angle_deg - 90)
                    bx = LOCK_CX + PIN_ORBIT_R * _math_lp.cos(a)
                    by = LOCK_CY + PIN_ORBIT_R * _math_lp.sin(a)
                    # pin points inward toward lock center
                    dx = LOCK_CX - bx
                    dy = LOCK_CY - by
                    mag = _math_lp.sqrt(dx * dx + dy * dy) or 1
                    return (bx, by,
                            bx + dx / mag * PIN_LEN, by + dy / mag * PIN_LEN)

                def _angle_of(x, y):
                    """Screen-angle of (x,y) relative to lock center, in [0,360)."""
                    a = _math_lp.degrees(_math_lp.atan2(y - LOCK_CY, x - LOCK_CX)) + 90
                    return a % 360

                def _angular_dist(a, b):
                    """Shortest signed distance from a to b on a circle."""
                    d = (b - a + 180) % 360 - 180
                    return d

                # ── drawing ────────────────────────────────────────────────────
                def _draw():
                    canvas.delete("all")
                    sx = _lp_state.get("shake_offset", 0)
                    cx = LOCK_CX + sx
                    cy = LOCK_CY

                    # --- proximity indicator ---
                    # Compute how close the pin currently is to the sweet spot
                    # (always, so the player can hunt without tensioning).
                    _sc   = _lp_state["sweet_center"]
                    _lr   = _lp_state["lock_rotation"]
                    _eff  = (_lp_state["pin_angle"] - _lr) % 360
                    _pdist = abs(_angular_dist(_eff, _sc))   # 0 = dead-on, 180 = furthest
                    # proximity 0.0 (far) → 1.0 (inside sweet spot)
                    _prox = max(0.0, 1.0 - (_pdist / (sweet_half * 4)))
                    _prox = min(1.0, _prox)

                    # Glow ring: radius shrinks and brightens the closer you are.
                    if _prox > 0.05 and not _lp_state["unlocked"]:
                        _gr = int(LOCK_R + 32 - _prox * 22)
                        _ga = int(30 + _prox * 140)    # alpha-simulated via intensity
                        _gcol = f"#{_ga:02x}{min(0xff, _ga + 0x30):02x}{_ga // 4:02x}"
                        _gwidth = max(1, int(_prox * 7))
                        canvas.create_oval(cx - _gr, cy - _gr, cx + _gr, cy + _gr,
                                            outline = _gcol, width = _gwidth)

                    # --- lock body ---
                    # sweet-spot arc (only shown faintly when tensioning)
                    if _lp_state["tensioning"] and not _lp_state["unlocked"]:
                        sc  = _lp_state["sweet_center"]
                        lr  = _lp_state["lock_rotation"]
                        vis_sc = (sc - lr) % 360  # where it appears on the face now
                        arc_start = vis_sc - sweet_half - 90
                        arc_extent = sweet_half * 2
                        canvas.create_arc(
                            cx - LOCK_R, cy - LOCK_R, cx + LOCK_R, cy + LOCK_R,
                            start = arc_start, extent = arc_extent,
                            outline = "#2a5a2a", width = 8, style = "arc"
                        )

                    # outer ring — tint toward green when very close
                    _ring_col = accent_col
                    if _prox > 0.7 and not _lp_state["unlocked"]:
                        _ring_col = "#55ff55"
                    elif _prox > 0.35 and not _lp_state["unlocked"]:
                        _ring_col = "#aacc44"
                    canvas.create_oval(cx - LOCK_R, cy - LOCK_R,
                                        cx + LOCK_R, cy + LOCK_R,
                                        outline = _ring_col, width = 4, fill = "#1e1e1e")

                    # notch marks every 30°
                    for nm in range(12):
                        na = _deg_to_rad(nm * 30 - 90)
                        nx0 = cx + (LOCK_R - 12) * _math_lp.cos(na)
                        ny0 = cy + (LOCK_R - 12) * _math_lp.sin(na)
                        nx1 = cx + LOCK_R       * _math_lp.cos(na)
                        ny1 = cy + LOCK_R       * _math_lp.sin(na)
                        canvas.create_line(nx0, ny0, nx1, ny1, fill = "#444444", width = 2)

                    # rotation indicator line (rotates with lock_rotation)
                    lr_a = _deg_to_rad(_lp_state["lock_rotation"] - 90)
                    canvas.create_line(
                        cx, cy,
                        cx + (LOCK_R - 20) * _math_lp.cos(lr_a),
                        cy + (LOCK_R - 20) * _math_lp.sin(lr_a),
                        fill = "#666666", width = 3
                    )

                    # inner keyhole
                    canvas.create_oval(cx - 22, cy - 22, cx + 22, cy + 22,
                                        outline = "#555555", width = 2, fill = "#111111")
                    canvas.create_rectangle(cx - 10, cy, cx + 10, cy + 28,
                                            fill = "#111111", outline = "#555555", width = 2)

                    # lock_rotation progress arc (green sector behind the ring)
                    if _lp_state["lock_rotation"] > 1:
                        canvas.create_arc(
                            cx - LOCK_R + 6, cy - LOCK_R + 6,
                            cx + LOCK_R - 6, cy + LOCK_R - 6,
                            start = 90, extent = min(359.9, _lp_state["lock_rotation"]),
                            outline = "#225522", width = 4, style = "arc"
                        )

                    # --- pin health bar ---
                    bar_x, bar_y, bar_w, bar_h = cx - 60, cy + LOCK_R + 14, 120, 10
                    canvas.create_rectangle(bar_x, bar_y, bar_x + bar_w, bar_y + bar_h,
                                            fill = "#333333", outline = "#555555")
                    php = max(0.0, _lp_state["pin_hp"])
                    hp_col = "#55ff55" if php > 0.5 else ("#ffaa33" if php > 0.25 else "#ff4444")
                    canvas.create_rectangle(bar_x, bar_y,
                                            bar_x + int(bar_w * php), bar_y + bar_h,
                                            fill = hp_col, outline = "")
                    canvas.create_text(bar_x + bar_w // 2, bar_y + bar_h + 12,
                                        text = "PIN INTEGRITY",
                                        fill = "#666666", font = ("Consolas", 8))

                    # --- bobby pin ---
                    pa = _lp_state["pin_angle"]
                    bx0, by0, bx1, by1 = _pin_tip_pos(pa)
                    pin_col = hp_col
                    canvas.create_line(bx0, by0, bx1, by1,
                                        fill = pin_col, width = PIN_THICK,
                                        capstyle = "round")
                    # small circle at base of pin — glows green when in sweet spot
                    _base_col = "#55ff55" if _pdist <= sweet_half else pin_col
                    canvas.create_oval(bx0 - 5, by0 - 5, bx0 + 5, by0 + 5,
                                        fill = _base_col, outline = "")

                    # proximity distance label below the pin
                    if not _lp_state["unlocked"] and not _lp_state["failed"]:
                        if _pdist <= sweet_half:
                            _prox_text = "● SWEET SPOT"
                            _prox_tcol = "#55ff55"
                        elif _prox > 0.5:
                            _prox_text = "Getting warmer..."
                            _prox_tcol = "#aacc44"
                        elif _prox > 0.2:
                            _prox_text = "Cold..."
                            _prox_tcol = "#cc8833"
                        else:
                            _prox_text = "Very cold"
                            _prox_tcol = "#886655"
                        canvas.create_text(LOCK_CX, LOCK_CY + LOCK_R + 52,
                                            text = _prox_text, fill = _prox_tcol,
                                            font = ("Consolas", 10, "bold"))

                    # tension wrench visual (L-shaped bracket at bottom)
                    tw_col = "#ffcc44" if _lp_state["tensioning"] else "#666666"
                    canvas.create_line(cx - 8, cy + LOCK_R - 8,
                                        cx - 8, cy + LOCK_R + 6,
                                        cx + 24, cy + LOCK_R + 6,
                                        fill = tw_col, width = 5, joinstyle = "round")

                    # status overlay
                    if _lp_state["unlocked"]:
                        canvas.create_text(LOCK_CX, CANVAS_H // 2 - 20,
                                            text = "UNLOCKED", fill = "#55ff55",
                                            font = ("Consolas", 28, "bold"))
                    elif _lp_state["failed"]:
                        canvas.create_text(LOCK_CX, CANVAS_H // 2 - 20,
                                            text = "JAMMED", fill = "#ff4444",
                                            font = ("Consolas", 28, "bold"))

                    # picks remaining
                    picks_label.config(
                        text = f"Picks: {'●' * _lp_state['picks_left']}{'○' * (max_picks - _lp_state['picks_left'])}"
                    )

                # ── tension / animation loop ────────────────────────────────────
                _tension_job = [None]

                def _tension_tick():
                    if _lp_state["unlocked"] or _lp_state["failed"]:
                        return
                    if not _lp_state["tensioning"]:
                        return

                    sc  = _lp_state["sweet_center"]
                    pa  = _lp_state["pin_angle"]
                    lr  = _lp_state["lock_rotation"]
                    # effective pin position relative to lock face (lock face rotates)
                    effective_pa = (pa - lr) % 360
                    dist = abs(_angular_dist(effective_pa, sc))

                    if dist <= sweet_half:
                        # In sweet spot: rotate lock; loop pick.wav while here
                        _pick_sound_start()
                        turn_rate = 18.0 * (1.0 - dist / sweet_half)  # deg per tick
                        _lp_state["lock_rotation"] = lr + turn_rate
                        if _lp_state["lock_rotation"] >= 360:
                            _lp_state["lock_rotation"] = 360
                            _lp_state["unlocked"] = True
                            _draw()
                            _lp_sound("unlock")
                            win.after(900, lambda: (win.grab_release(), win.destroy(), on_success()))
                            return
                    else:
                        # Wrong position: drain pin HP; stop the pick sound
                        _pick_sound_stop()
                        overshot = (dist - sweet_half) / 180.0
                        drain = 0.022 * resistance * (1.0 + min(overshot, 1.0))
                        _lp_state["pin_hp"] -= drain
                        if _lp_state["pin_hp"] <= 0:
                            _lp_state["pin_hp"] = 0
                            _lp_state["picks_left"] -= 1
                            _lp_sound("snap")
                            _lp_state["tensioning"] = False
                            # reset pin to top, reassign sweet spot
                            _lp_state["pin_angle"]    = 0.0
                            _lp_state["pin_hp"]       = 1.0
                            _lp_state["lock_rotation"] = max(0.0, _lp_state["lock_rotation"] - 45)
                            _lp_state["sweet_center"] = random.uniform(0.0, 360.0)
                            _draw()
                            if _lp_state["picks_left"] <= 0:
                                _lp_state["failed"] = True
                                _draw()
                                win.after(1200, lambda: win.destroy())
                            else:
                                # quick shake animation
                                _shake(4)
                            return

                    _draw()
                    _tension_job[0] = win.after(60, _tension_tick)

                def _shake(n):
                    if n <= 0:
                        _lp_state["shake_offset"] = 0
                        _draw()
                        return
                    _lp_state["shake_offset"] = random.choice([-6, 6])
                    _draw()
                    win.after(55, lambda: _shake(n - 1))

                def _start_tension(evt = None):
                    if _lp_state["unlocked"] or _lp_state["failed"] or _lp_state["picks_left"] <= 0:
                        return
                    if _lp_state["tensioning"]:
                        return
                    _lp_state["tensioning"] = True
                    _draw()
                    _tension_tick()

                def _stop_tension(evt = None):
                    _lp_state["tensioning"] = False
                    _pick_sound_stop()
                    if _tension_job[0]:
                        try:
                            win.after_cancel(_tension_job[0])
                        except Exception:
                            logging.exception("Suppressed exception")
                        _tension_job[0] = None
                    _draw()

                # ── mouse / keyboard input ─────────────────────────────────────
                def _on_mouse_press(evt):
                    if _lp_state["unlocked"] or _lp_state["failed"]:
                        return
                    a = _angle_of(evt.x, evt.y)
                    dx = evt.x - LOCK_CX
                    dy = evt.y - LOCK_CY
                    dist = _math_lp.sqrt(dx * dx + dy * dy)
                    if abs(dist - PIN_ORBIT_R) <= 28:
                        _lp_state["dragging"] = True
                        _lp_state["drag_last_angle"] = a
                        _lp_state["pin_angle"] = a
                        _draw()

                def _on_mouse_drag(evt):
                    if not _lp_state["dragging"]:
                        return
                    if _lp_state["unlocked"] or _lp_state["failed"]:
                        return
                    a = _angle_of(evt.x, evt.y)
                    _lp_state["pin_angle"] = a
                    _lp_state["drag_last_angle"] = a
                    _draw()

                def _on_mouse_release(evt):
                    _lp_state["dragging"] = False

                canvas.bind("<ButtonPress-1>",   _on_mouse_press)
                canvas.bind("<B1-Motion>",       _on_mouse_drag)
                canvas.bind("<ButtonRelease-1>", _on_mouse_release)
                win.bind("<KeyPress-space>",   _start_tension)
                win.bind("<KeyRelease-space>", _stop_tension)
                win.bind("<KeyPress-Return>",   _start_tension)
                win.bind("<KeyRelease-Return>", _stop_tension)

                # Tension wrench button
                tw_btn = customtkinter.CTkButton(
                    info_frame, text = "Hold: Tension Wrench",
                    width = 180,
                    fg_color = "#444400", hover_color = "#666600",
                    font = customtkinter.CTkFont(family = "Consolas", size = 11)
                )
                tw_btn.pack(side = "right", padx = 8, pady = 4)
                tw_btn.bind("<ButtonPress-1>",   _start_tension)
                tw_btn.bind("<ButtonRelease-1>", _stop_tension)

                win.focus_set()
                _draw()

            def loot_crate(crate, crate_file_path = None):

                try:

                    if crate.get("locked", False):
                        def _on_unlock_success():
                            crate["locked"] = False
                            if crate_file_path and os.path.exists(crate_file_path):
                                try:
                                    updated = {k: v for k, v in crate.items() if k != "_file_path"}
                                    updated["locked"] = False
                                    _signed_json_write(crate_file_path, updated, portable = True)
                                except Exception:
                                    logging.exception("Suppressed exception")
                            loot_crate(crate, crate_file_path)
                        _open_lockpick_minigame(crate, crate_file_path, _on_unlock_success)
                        return

                    save_path = os.path.join(saves_folder or "", (self.currentsave or "")+".sldsv")
                    save_data = self._load_file((self.currentsave or "")+".sldsv")
                    if save_data is None:
                        raise RuntimeError("Failed to load current save for add_item")

                    if crate.get("generated_items"):

                        available_items = crate.get("generated_items", [])
                        logging.info(f"Using {len(available_items)} pre-generated items from crate '{crate.get('name')}'")
                    else:

                        loot_table = crate.get("loot_table", [])
                        pulls = crate.get("pulls", 3)
                        if isinstance(pulls, dict):
                            num_pulls = random.randint(pulls.get("min", 1), pulls.get("max", 3))
                        else:
                            num_pulls = int(pulls)

                        rarity_weights = table_data.get("rarity_weights", {})

                        luck_stat = save_data.get("stats", {}).get("luck", 0)if save_data else 0
                        luck_effect = rarity_weights.get("Luck Effect", 1.5)

                        available_items =[]
                        for _ in range(num_pulls):

                            weighted_entries =[]
                            for entry in loot_table:
                                entry_rarity = entry.get("rarity", "Common")
                                base_weight = rarity_weights.get(entry_rarity, 1)

                                if luck_stat >0:
                                    weight = base_weight *(1 +(luck_stat *luck_effect /100))
                                else:
                                    weight = base_weight

                                weight = max(1, int(weight))
                                weighted_entries.extend([entry]*weight)

                            if weighted_entries:
                                selected_entry = random.choice(weighted_entries)
                                items_to_add = self._resolve_loot_entry(selected_entry, table_data, save_data)
                                for item in items_to_add:
                                    item_copy = {k:v for k, v in item.items()if k !="table_category"}
                                    item_copy = add_subslots_to_item(item_copy)
                                    available_items.append(item_copy)

                        if crate_file_path and available_items:
                            updated_crate = crate.copy()
                            updated_crate["generated_items"]= available_items
                            updated_crate.pop("loot_table", None)
                            try:
                                _signed_json_write(crate_file_path, updated_crate, portable = True)
                                logging.info(f"Saved {len(available_items)} generated items to crate file: {crate_file_path}")

                                crate["generated_items"]= available_items
                                crate.pop("loot_table", None)
                            except Exception as e:
                                logging.error(f"Failed to save generated items to crate file: {e}")

                    # ── opensound ────────────────────────────────────────────
                    try:
                        opensound = crate.get("opensound")
                        logging.debug("Crate opensound field: %r", opensound)
                        _crate_snd_base = os.path.join(os.path.dirname(__file__), "sounds", "misc", "crate")
                        def _play_crate_snd(snd, block=False):
                            fname = snd if str(snd).endswith((".ogg", ".wav")) else str(snd) + ".ogg"
                            path = os.path.join(_crate_snd_base, fname)
                            logging.debug("Playing crate sound: %s (exists=%s)", path, os.path.exists(path))
                            if os.path.exists(path):
                                try:
                                    sound = pygame.mixer.Sound(path)
                                    channel = sound.play()
                                    if block and channel:
                                        while channel.get_busy():
                                            time.sleep(0.05)
                                except Exception:
                                    logging.exception("Failed to play crate sound: %s", path)
                            else:
                                logging.warning("Crate opensound not found: %s", path)
                        if isinstance(opensound, str) and opensound:
                            _play_crate_snd(opensound)
                        elif isinstance(opensound, list) and opensound:
                            # list format: ["snd1.ogg", "snd2.ogg", {"type": "OR"}]
                            sound_type = "OR"
                            sounds = []
                            for item in opensound:
                                if isinstance(item, dict) and "type" in item:
                                    sound_type = str(item["type"]).upper()
                                elif isinstance(item, str) and item:
                                    sounds.append(item)
                            if sounds:
                                if sound_type == "AND":
                                    for snd in sounds:
                                        _play_crate_snd(snd, block=True)
                                else:
                                    _play_crate_snd(random.choice(sounds))
                            else:
                                logging.debug("No opensound on this crate (value: %r)", opensound)
                        elif isinstance(opensound, dict):
                            sound_type = str(opensound.get("type", "OR")).upper()
                            sounds = opensound.get("sounds", [])
                            if isinstance(sounds, list) and sounds:
                                if sound_type == "AND":
                                    for snd in sounds:
                                        if snd:
                                            _play_crate_snd(snd, block=True)
                                else:
                                    chosen = random.choice(sounds)
                                    if chosen:
                                        _play_crate_snd(chosen)
                        else:
                            logging.debug("No opensound on this crate (value: %r)", opensound)
                    except Exception:
                        logging.exception("Failed to play crate opensound")

                    self._open_loot_selection_menu(crate, available_items, save_data, save_path, crate_file_path, table_data)

                except Exception as e:
                    logging.error(f"Failed to open loot crate: {e}")
                    self._popup_show_info("Error", f"Failed to open loot crate: {e}", sound = "error")

            if lootcrates:
                crate_section_label = customtkinter.CTkLabel(
                scroll_frame,
                text = "Loot Crates",
                font = customtkinter.CTkFont(size = 18, weight = "bold")
                )
                crate_section_label.pack(pady =(10, 10), anchor = "w", padx = 10)

            for crate in lootcrates:
                crate_frame = customtkinter.CTkFrame(scroll_frame)
                crate_frame.pack(fill = "x", pady = 10, padx = 10)
                crate_frame.grid_columnconfigure(1, weight = 1)

                header_frame = customtkinter.CTkFrame(crate_frame, fg_color = "transparent")
                header_frame.grid(row = 0, column = 0, columnspan = 2, sticky = "ew", pady =(0, 10))
                header_frame.grid_columnconfigure(0, weight = 1)

                name_label = customtkinter.CTkLabel(
                header_frame,
                text = crate.get("name", "Unknown Crate"),
                font = customtkinter.CTkFont(size = 14, weight = "bold"),
                anchor = "w"
                )
                name_label.grid(row = 0, column = 0, sticky = "w")

                rarity_label = customtkinter.CTkLabel(
                header_frame,
                text = f"Rarity: {crate.get('rarity', 'N/A')}",
                font = customtkinter.CTkFont(size = 11),
                text_color = "gray",
                anchor = "e"
                )
                rarity_label.grid(row = 0, column = 1, sticky = "e", padx =(10, 0))

                if "description"in crate and crate["description"]:
                    desc_label = customtkinter.CTkLabel(
                    crate_frame,
                    text = crate["description"],
                    font = customtkinter.CTkFont(size = 11),
                    text_color = "gray",
                    wraplength = 400,
                    justify = "left",
                    anchor = "w"
                    )
                    desc_label.grid(row = 1, column = 0, columnspan = 2, sticky = "ew", pady =(0, 10), padx = 10)

                contents_text = self._get_loot_crate_contents_preview(crate, table_data)
                if contents_text:
                    contents_label = customtkinter.CTkLabel(
                    crate_frame,
                    text = contents_text,
                    font = customtkinter.CTkFont(size = 10),
                    text_color = "orange",
                    wraplength = 400,
                    justify = "left",
                    anchor = "w"
                    )
                    contents_label.grid(row = 2, column = 0, columnspan = 2, sticky = "ew", pady =(0, 10), padx = 10)

                crate_file = crate.get("_file_path")
                loot_button = self._create_sound_button(
                crate_frame,
                "Loot Crate",
                lambda c = crate, f = crate_file:loot_crate(c, f),
                width = 150,
                height = 40,
                font = customtkinter.CTkFont(size = 12)
                )
                loot_button.grid(row = 3, column = 0, columnspan = 2, sticky = "ew", padx = 10, pady = 10)

            if enemyloots:
                enemy_section_label = customtkinter.CTkLabel(
                scroll_frame,
                text = "Enemy Loot",
                font = customtkinter.CTkFont(size = 18, weight = "bold")
                )
                enemy_section_label.pack(pady =(20, 10), anchor = "w", padx = 10)

                def loot_enemy(el_data, el_file_path = None):
                    try:
                        save_path = os.path.join(saves_folder or "", (self.currentsave or "")+".sldsv")
                        save_data = self._load_file((self.currentsave or "")+".sldsv")
                        if save_data is None:
                            raise RuntimeError("Failed to load current save for enemy loot")

                        available_items =[]
                        for item in el_data.get("items", []):
                            if isinstance(item, dict):
                                item_copy = {k:v for k, v in item.items()if k !="table_category"}
                                item_copy = add_subslots_to_item(item_copy)
                                available_items.append(item_copy)

                        pseudo_crate = {
                        "name":f"Enemy Loot: {el_data.get('enemy_name', 'Unknown')}",
                        "description":f"Loot from {el_data.get('enemy_name', 'Unknown')} - {el_data.get('timestamp', 'Unknown time')}"
                        }
                        self._open_loot_selection_menu(pseudo_crate, available_items, save_data, save_path, el_file_path, table_data)

                    except Exception as e:
                        logging.error(f"Failed to open enemy loot: {e}")
                        self._popup_show_info("Error", f"Failed to open enemy loot: {e}", sound = "error")

                for el in enemyloots:
                    el_frame = customtkinter.CTkFrame(scroll_frame)
                    el_frame.pack(fill = "x", pady = 10, padx = 10)
                    el_frame.grid_columnconfigure(1, weight = 1)

                    enemy_name = el.get("enemy_name", "Unknown Enemy")
                    timestamp = el.get("timestamp", "")
                    items_list = el.get("items", [])
                    item_count = len(items_list)

                    header_frame = customtkinter.CTkFrame(el_frame, fg_color = "transparent")
                    header_frame.grid(row = 0, column = 0, columnspan = 2, sticky = "ew", pady =(0, 5))
                    header_frame.grid_columnconfigure(0, weight = 1)

                    name_label = customtkinter.CTkLabel(
                    header_frame,
                    text = f"Loot from: {enemy_name}",
                    font = customtkinter.CTkFont(size = 14, weight = "bold"),
                    anchor = "w"
                    )
                    name_label.grid(row = 0, column = 0, sticky = "w")

                    items_label = customtkinter.CTkLabel(
                    header_frame,
                    text = f"{item_count} item(s)",
                    font = customtkinter.CTkFont(size = 11),
                    text_color = "gray",
                    anchor = "e"
                    )
                    items_label.grid(row = 0, column = 1, sticky = "e", padx =(10, 0))

                    if timestamp:
                        try:
                            from datetime import datetime as dt
                            ts_parsed = dt.fromisoformat(timestamp)
                            ts_display = ts_parsed.strftime("%Y-%m-%d %H:%M")
                        except Exception:
                            ts_display = timestamp
                        ts_label = customtkinter.CTkLabel(
                        el_frame,
                        text = f"Generated: {ts_display}",
                        font = customtkinter.CTkFont(size = 10),
                        text_color = "gray",
                        anchor = "w"
                        )
                        ts_label.grid(row = 1, column = 0, columnspan = 2, sticky = "w", padx = 10)

                    if items_list:
                        preview_items = items_list[:3]
                        preview_names =[it.get("name", "Unknown")if isinstance(it, dict)else "Unknown"for it in preview_items]
                        preview_text = ", ".join(preview_names)
                        if len(items_list)>3:
                            preview_text +=f", ...(+{len(items_list)-3} more)"
                        preview_label = customtkinter.CTkLabel(
                        el_frame,
                        text = preview_text,
                        font = customtkinter.CTkFont(size = 10),
                        text_color = "orange",
                        anchor = "w",
                        wraplength = 400
                        )
                        preview_label.grid(row = 2, column = 0, columnspan = 2, sticky = "w", padx = 10, pady =(5, 0))

                    el_file = el.get("_file_path")
                    loot_btn = self._create_sound_button(
                    el_frame,
                    "Loot",
                    lambda e = el, f = el_file:loot_enemy(e, f),
                    width = 150,
                    height = 40,
                    font = customtkinter.CTkFont(size = 12)
                    )
                    loot_btn.grid(row = 3, column = 0, columnspan = 2, sticky = "ew", padx = 10, pady = 10)

            back_button = self._create_sound_button(main_frame, "Back to Main Menu", lambda:[self._clear_window(), self._build_main_menu()], width = 500, height = 50, font = customtkinter.CTkFont(size = 16))
            back_button.pack(pady = 20)

        except Exception as e:
            logging.error(f"Failed to load loot tool: {e}")
            self._popup_show_info("Error", f"Failed to load loot tool: {e}", sound = "error")

    def _compute_item_value_with_installed_components(self, item, _seen = None):
        if not isinstance(item, dict):
            return 0.0

        if _seen is None:
            _seen = set()
        obj_id = id(item)
        if obj_id in _seen:
            return 0.0
        _seen.add(obj_id)

        qty = item.get("quantity", 1)
        try:
            qty = max(1, int(qty))
        except Exception:
            qty = 1

        try:
            base_value = float(item.get("value", 0) or 0)
        except Exception:
            base_value = 0.0

        total_value = base_value * qty

        for field_name in ("accessories", "subslots", "parts"):
            entries = item.get(field_name)
            if not isinstance(entries, list):
                continue
            for entry_data in entries:
                if not isinstance(entry_data, dict):
                    continue
                current_item = entry_data.get("current")
                if isinstance(current_item, dict):
                    total_value += self._compute_item_value_with_installed_components(current_item, _seen)

        return total_value

    def _normalize_to_lower_set(self, value):
        if value is None:
            return set()
        if isinstance(value, list):
            return {str(v).strip().lower() for v in value if str(v).strip()}
        if isinstance(value, str):
            s = value.strip().lower()
            return {s} if s else set()
        s = str(value).strip().lower()
        return {s} if s else set()

    def _attachment_fits_accessory_slot(self, attachment_item, accessory_slot):
        if not isinstance(attachment_item, dict):
            return False
        att_slot = str(attachment_item.get("slot") or "").strip().lower()
        if not att_slot:
            return False

        acc_slot = str(accessory_slot or "").strip().lower()
        if not acc_slot:
            return False

        if att_slot == acc_slot:
            return True

        compatible_slots = attachment_item.get("compatible_slots")
        if isinstance(compatible_slots, list):
            return acc_slot in {str(s).strip().lower() for s in compatible_slots if str(s).strip()}

        return False

    def _attachment_matches_firearm(self, attachment_item, firearm_item):
        if not isinstance(attachment_item, dict) or not isinstance(firearm_item, dict):
            return False

        firearm_calibers = self._normalize_to_lower_set(firearm_item.get("caliber"))
        firearm_platforms = self._normalize_to_lower_set(firearm_item.get("platform"))
        firearm_platforms.update(self._normalize_to_lower_set(firearm_item.get("secondary_platform")))

        att_calibers = self._normalize_to_lower_set(attachment_item.get("caliber"))
        att_platforms = self._normalize_to_lower_set(attachment_item.get("platform"))
        att_platforms.update(self._normalize_to_lower_set(attachment_item.get("secondary_platform")))

        if att_calibers and firearm_calibers and not att_calibers.intersection(firearm_calibers):
            return False
        if att_platforms and firearm_platforms and not att_platforms.intersection(firearm_platforms):
            return False

        return True

    def _extract_override_calibers(self, attachment_item):
        if not isinstance(attachment_item, dict):
            return []
        overrides = attachment_item.get("overrides")
        if not isinstance(overrides, dict):
            return []
        cal_val = overrides.get("caliber")
        if isinstance(cal_val, str):
            return [cal_val]
        if isinstance(cal_val, list):
            return [c for c in cal_val if isinstance(c, str) and c.strip()]
        return []

    def _get_effective_firearm_calibers_for_loot(self, firearm_item):
        if not isinstance(firearm_item, dict):
            return []

        override_calibers = []
        for acc in firearm_item.get("accessories", []) or []:
            if not isinstance(acc, dict):
                continue
            cur = acc.get("current")
            if not isinstance(cur, dict):
                continue
            override_calibers.extend(self._extract_override_calibers(cur))

        cleaned_overrides = [str(c).strip() for c in override_calibers if str(c).strip()]
        if cleaned_overrides:
            return cleaned_overrides

        caliber = firearm_item.get("caliber")
        if isinstance(caliber, str):
            return [caliber]
        if isinstance(caliber, (list, tuple)):
            return [str(c).strip() for c in caliber if str(c).strip()]
        return []

    def _platforms_compatible(self, firearm_item, candidate_part):
        firearm_platforms = self._normalize_to_lower_set(firearm_item.get("platform"))
        firearm_platforms.update(self._normalize_to_lower_set(firearm_item.get("secondary_platform")))
        if not firearm_platforms:
            return True

        part_platforms = self._normalize_to_lower_set(candidate_part.get("platform"))
        part_platforms.update(self._normalize_to_lower_set(candidate_part.get("secondary_platform")))
        if not part_platforms:
            return True

        return bool(set(firearm_platforms).intersection(set(part_platforms)))

    def _sync_firearm_parts_to_caliber(self, firearm_item, table_data, target_calibers):
        if not isinstance(firearm_item, dict):
            return False
        if not isinstance(table_data, dict):
            return False
        if not target_calibers:
            return False

        target_lower = {str(c).strip().lower() for c in target_calibers if str(c).strip()}
        if not target_lower:
            return False

        parts = firearm_item.get("parts")
        if not isinstance(parts, list) or not parts:
            return False

        tables = table_data.get("tables", {})
        if not isinstance(tables, dict):
            return False

        all_items = []
        for table_items in tables.values():
            if isinstance(table_items, list):
                all_items.extend([it for it in table_items if isinstance(it, dict)])

        changed = False
        for part_ref in parts:
            if not isinstance(part_ref, dict):
                continue

            current_part = part_ref.get("current")
            if not isinstance(current_part, dict):
                continue

            part_calibers = self._normalize_to_lower_set(current_part.get("caliber"))
            if part_calibers and set(part_calibers).intersection(target_lower):
                continue

            req_type = part_ref.get("type")
            req_slot = part_ref.get("slot")

            compatible_candidates = []
            fallback_candidates = []
            for item in all_items:
                item_type = item.get("type")
                item_slot = item.get("slot")

                if req_type and item_type != req_type:
                    continue
                if req_slot and item_slot != req_slot and req_type is None:
                    continue
                if not self._platforms_compatible(firearm_item, item):
                    continue

                item_calibers = self._normalize_to_lower_set(item.get("caliber"))
                if item_calibers and set(item_calibers).intersection(target_lower):
                    compatible_candidates.append(item)
                elif not item_calibers:
                    fallback_candidates.append(item)

            replacement_pool = compatible_candidates if compatible_candidates else fallback_candidates
            if not replacement_pool:
                continue

            replacement = json.loads(json.dumps(random.choice(replacement_pool)))
            part_ref["current"] = replacement
            changed = True

        return changed

    def _apply_random_firearm_attachments(self, firearm_item, table_data, chance = 0.25):
        if not isinstance(firearm_item, dict) or not firearm_item.get("firearm"):
            return False
        if not isinstance(table_data, dict):
            return False
        if random.random() >= max(0.0, min(1.0, float(chance))):
            return False

        attachments_table = table_data.get("tables", {}).get("attachments", [])
        if not isinstance(attachments_table, list) or not attachments_table:
            return False

        accessories = firearm_item.get("accessories", [])
        if not isinstance(accessories, list) or not accessories:
            return False

        empty_slots = []
        for accessory in accessories:
            if not isinstance(accessory, dict):
                continue
            if isinstance(accessory.get("current"), dict):
                continue
            slot_name = str(accessory.get("slot") or "").strip()
            if not slot_name:
                continue
            empty_slots.append(accessory)

        if not empty_slots:
            return False

        random.shuffle(empty_slots)
        max_slots = random.randint(1, len(empty_slots))
        applied = 0
        override_calibers = []
        blocked_slots = set()  # slot names blocked by already-installed attachments

        def _collect_conflicts(conflicts_val):
            if isinstance(conflicts_val, list):
                return {str(c).strip().lower() for c in conflicts_val if c}
            if isinstance(conflicts_val, str) and conflicts_val.strip():
                return {conflicts_val.strip().lower()}
            return set()

        for accessory in empty_slots:
            if applied >= max_slots:
                break

            slot_name = accessory.get("slot")
            if str(slot_name or "").strip().lower() in blocked_slots:
                continue

            compatible = []
            for attachment_item in attachments_table:
                if not isinstance(attachment_item, dict):
                    continue
                if not self._attachment_fits_accessory_slot(attachment_item, slot_name):
                    continue
                if not self._attachment_matches_firearm(attachment_item, firearm_item):
                    continue
                compatible.append(attachment_item)

            if not compatible:
                continue

            chosen = random.choice(compatible)
            attachment_copy = json.loads(json.dumps(chosen))
            accessory["current"] = attachment_copy
            _add_attachment_subslots_to_weapon(firearm_item, accessory, attachment_copy)
            override_calibers.extend(self._extract_override_calibers(attachment_copy))
            applied += 1

            # Mark any slots this accessory slot or the installed attachment conflicts with
            blocked_slots.update(_collect_conflicts(accessory.get("conflicts_with")))
            blocked_slots.update(_collect_conflicts(attachment_copy.get("conflicts_with")))

        if override_calibers:
            self._sync_firearm_parts_to_caliber(firearm_item, table_data, override_calibers)

        return applied > 0

    def _resolve_loot_entry(self, entry, table_data, save_data = None):

        items =[]
        debug_info =[]

        def _walk_item_tree(item, out_items, seen):
            if not isinstance(item, dict):
                return
            oid = id(item)
            if oid in seen:
                return
            seen.add(oid)
            out_items.append(item)

            contained_items = item.get("items")
            if isinstance(contained_items, list):
                for sub_item in contained_items:
                    _walk_item_tree(sub_item, out_items, seen)

            for field_name in ("parts", "subslots", "accessories"):
                field_value = item.get(field_name)
                if isinstance(field_value, list):
                    for entry_data in field_value:
                        if isinstance(entry_data, dict):
                            current_item = entry_data.get("current")
                            if isinstance(current_item, dict):
                                _walk_item_tree(current_item, out_items, seen)

        def _build_player_firearm_profile(current_save_data):
            if not isinstance(current_save_data, dict):
                return {"has_firearms":False}

            collected_items =[]
            seen = set()

            hands = current_save_data.get("hands")
            if isinstance(hands, dict):
                for hand_item in hands.get("items", [])or[]:
                    _walk_item_tree(hand_item, collected_items, seen)

            for storage_item in current_save_data.get("storage", [])or[]:
                _walk_item_tree(storage_item, collected_items, seen)

            equipment = current_save_data.get("equipment", {})
            if isinstance(equipment, dict):
                for equipped in equipment.values():
                    if isinstance(equipped, dict):
                        _walk_item_tree(equipped, collected_items, seen)
                    elif isinstance(equipped, list):
                        for equipped_item in equipped:
                            _walk_item_tree(equipped_item, collected_items, seen)

            firearms = [it for it in collected_items if isinstance(it, dict)and it.get("firearm")]
            if not firearms:
                return {"has_firearms":False}

            caliber_set = set()
            magazine_set = set()
            submag_set = set()
            platform_set = set()
            secondary_platform_set = set()

            for firearm in firearms:
                caliber_set.update(self._normalize_to_lower_set(firearm.get("caliber")))
                magazine_set.update(self._normalize_to_lower_set(firearm.get("magazinesystem")))
                submag_set.update(self._normalize_to_lower_set(firearm.get("submagazinesystem")))
                platform_set.update(self._normalize_to_lower_set(firearm.get("platform")))
                secondary_platform_set.update(self._normalize_to_lower_set(firearm.get("secondary_platform")))

            return {
            "has_firearms":True,
            "calibers":caliber_set,
            "magazinesystems":magazine_set,
            "submagazinesystems":submag_set,
            "platforms":platform_set,
            "secondary_platforms":secondary_platform_set
            }

        def _is_weapon_part_candidate(item_obj, table_name_hint):
            if not isinstance(item_obj, dict)or item_obj.get("firearm"):
                return False

            if item_obj.get("attachment")or item_obj.get("part")or item_obj.get("part_type"):
                return True

            slot_name = str(item_obj.get("slot", "")).strip().lower()
            if slot_name in {"weapon_slot", "attachment", "barrel", "receiver", "bolt", "trigger", "stock", "rail", "optic"}:
                return True

            hint = str(table_name_hint or "").strip().lower()
            return hint in {"attachments", "parts", "firearm_parts", "weapon_parts", "optics", "barrels", "stocks", "receivers", "triggers", "bolts"}

        compatibility_profile = _build_player_firearm_profile(save_data)if save_data else {"has_firearms":False}

        def _compatibility_weight_multiplier(item_obj, table_name_hint = None):
            if not isinstance(item_obj, dict):
                return 1.0
            if not compatibility_profile.get("has_firearms"):
                return 1.0

            is_firearm_item = bool(item_obj.get("firearm"))
            is_ammo_item = bool(item_obj.get("caliber"))and not is_firearm_item and not item_obj.get("magazinesystem")
            is_part_item = _is_weapon_part_candidate(item_obj, table_name_hint)

            if not(is_firearm_item or is_ammo_item or is_part_item):
                return 1.0

            candidate_calibers = self._normalize_to_lower_set(item_obj.get("caliber"))
            candidate_mags = self._normalize_to_lower_set(item_obj.get("magazinesystem"))
            candidate_submags = self._normalize_to_lower_set(item_obj.get("submagazinesystem"))
            candidate_platforms = self._normalize_to_lower_set(item_obj.get("platform"))
            candidate_secondary_platforms = self._normalize_to_lower_set(item_obj.get("secondary_platform"))

            matches = 0
            if candidate_calibers and candidate_calibers.intersection(compatibility_profile.get("calibers", set())):
                matches +=1
            if candidate_mags and candidate_mags.intersection(compatibility_profile.get("magazinesystems", set())):
                matches +=1
            if candidate_submags and candidate_submags.intersection(compatibility_profile.get("submagazinesystems", set())):
                matches +=1

            platform_overlap = set(candidate_platforms)
            platform_overlap.update(candidate_secondary_platforms)
            player_platforms = set(compatibility_profile.get("platforms", set()))
            player_platforms.update(compatibility_profile.get("secondary_platforms", set()))
            if platform_overlap and platform_overlap.intersection(player_platforms):
                matches +=1

            if is_ammo_item:
                return 1.5 if matches >0 else 1.0
            if is_part_item:
                if matches <=0:
                    return 1.0
                return min(1.35 +(matches *0.12), 1.75)
            if is_firearm_item:
                if matches <=0:
                    return 1.0
                return min(1.28 +(matches *0.1), 1.7)

            return 1.0

        def _weighted_compatibility_pick(candidates, table_name_hint = None):
            if not candidates:
                return None
            if len(candidates)==1:
                return candidates[0]

            weighted_candidates =[]
            for candidate in candidates:
                item_obj = candidate
                candidate_table = table_name_hint
                if isinstance(candidate, tuple)and candidate and isinstance(candidate[0], dict):
                    item_obj = candidate[0]
                    if len(candidate)>1 and isinstance(candidate[1], str):
                        candidate_table = candidate[1]

                mult = _compatibility_weight_multiplier(item_obj, candidate_table)
                extra_slots = 0
                if mult >1.0:
                    extra_slots = max(1, int((mult -1.0)*3))
                weighted_candidates.extend([candidate]*(1 +extra_slots))

            return random.choice(weighted_candidates)if weighted_candidates else random.choice(candidates)

        try:
            if entry.get("type")=="table":

                table_name = entry.get("table")
                entry_rarity = entry.get("rarity", "Common")
                table = table_data.get("tables", {}).get(table_name, [])

                luck_stat = 0
                if save_data:
                    luck_stat = save_data.get("stats", {}).get("luck", 0)

                rarity_weights = table_data.get("rarity_weights", {})
                special_chance = rarity_weights.get("Special Chance", 0)
                luck_effect = rarity_weights.get("Luck Effect", 1.5)

                if global_variables.get("devmode", {}).get("value", False):
                    debug_info.append(f"[DEBUG]Resolving table entry: {table_name}")
                    debug_info.append(f" Entry rarity(selection weight): {entry_rarity}")
                    debug_info.append(f" Luck stat: {luck_stat}")
                    debug_info.append(f" Luck effect multiplier: {luck_effect}")
                    debug_info.append(f" Special chance: {special_chance}%")
                    debug_info.append(f" Available items in table: {len(table)}")
                    if compatibility_profile.get("has_firearms"):
                        debug_info.append(" Compatibility bias active for ammo/parts/firearms")

                special_roll = random.random()*100
                if global_variables.get("devmode", {}).get("value", False):
                    debug_info.append(f" Special roll: {special_roll:.2f}(needs < {special_chance} for special)")

                if special_roll <special_chance:

                    special_table = table_data.get("tables", {}).get("special_items", [])
                    if special_table:
                        selected_item = random.choice(special_table)
                        item_copy = selected_item.copy()
                        item_copy["table_category"]= "special_items"
                        if global_variables.get("devmode", {}).get("value", False):
                            debug_info.append(f" ★ SPECIAL ITEM TRIGGERED! Selected: {selected_item.get('name', 'Unknown')}")
                            item_copy["_debug_info"]= "\n".join(debug_info)
                        items.append(item_copy)
                        return self._apply_random_quantity(items, table_data)

                weighted_pool =[]
                rarity_counts = {}
                for item in table:
                    item_rarity = item.get("rarity", "Common")
                    weight = rarity_weights.get(item_rarity, 1)

                    if luck_stat >0:
                        weight = weight *(1 +(luck_stat *luck_effect /100))

                    compatibility_mult = _compatibility_weight_multiplier(item, table_name)
                    effective_weight = weight *compatibility_mult

                    base_count = max(1, int(weight))
                    count = max(1, int(effective_weight))
                    if compatibility_mult >1.0 and count <=base_count:
                        count = base_count +1

                    weighted_pool.extend([item]*count)
                    rarity_counts[item_rarity]= rarity_counts.get(item_rarity, 0)+count

                if global_variables.get("devmode", {}).get("value", False):
                    debug_info.append(f" Weighted pool breakdown:")
                    for rarity, count in sorted(rarity_counts.items(), key = lambda x:-x[1]):
                        base_w = rarity_weights.get(rarity, 1)
                        pct =(count /len(weighted_pool)*100)if weighted_pool else 0
                        debug_info.append(f" {rarity}: {count} entries({pct:.1f}%)[base weight: {base_w}]")
                    debug_info.append(f" Total pool size: {len(weighted_pool)}")

                if weighted_pool:
                    selected_item = random.choice(weighted_pool)
                    item_copy = selected_item.copy()
                    item_copy["table_category"]= table_name
                    if global_variables.get("devmode", {}).get("value", False):
                        debug_info.append(f" → Selected: {selected_item.get('name', 'Unknown')}({selected_item.get('rarity', 'Unknown')})")
                        item_copy["_debug_info"]= "\n".join(debug_info)
                    items.append(item_copy)

            elif isinstance(entry.get("type"), list)and "table"in entry.get("type")and "id"in entry.get("type"):

                table_name = entry.get("table")
                item_id = entry.get("id")
                requested_rarity = entry.get("rarity")
                multi_type = entry.get("multi_type", "or")
                spawn_magazine = entry.get("spawn_magazine", False)
                magazines_to_spawn = entry.get("magazines_to_spawn", 1)
                loading_type = entry.get("loading", "full")

                if global_variables.get("devmode", {}).get("value", False):
                    debug_info.append(f"[DEBUG]Resolving table+id entry: table={table_name}, id={item_id}")
                    if requested_rarity:
                        debug_info.append(f" Requested rarity: {requested_rarity}")
                    if spawn_magazine:
                        debug_info.append(f" Spawn magazines: {spawn_magazine}, count: {magazines_to_spawn}, loading: {loading_type}")

                def spawn_magazines_for_item_tableid(firearm_item, table_data, debug_info):
                    spawned_mags =[]
                    mag_system = firearm_item.get("magazinesystem")
                    caliber = self._get_effective_firearm_calibers_for_loot(firearm_item)

                    if not mag_system:
                        if global_variables.get("devmode", {}).get("value", False):
                            debug_info.append(f" ⚠ No magazinesystem found for {firearm_item.get('name', 'Unknown')}")
                        return spawned_mags

                    magazines_table = table_data.get("tables", {}).get("magazines", [])
                    compatible_mags =[]
                    for mag in magazines_table:
                        if mag.get("magazinesystem")==mag_system:
                            mag_caliber = mag.get("caliber")
                            if isinstance(mag_caliber, str):
                                mag_caliber =[mag_caliber]

                            if caliber and mag_caliber and any(c in mag_caliber for c in caliber):
                                compatible_mags.append(mag)

                    if not compatible_mags:
                        if global_variables.get("devmode", {}).get("value", False):
                            debug_info.append(f" ⚠ No compatible magazines found for {mag_system}")
                        return spawned_mags

                    if isinstance(magazines_to_spawn, dict):
                        num_mags = random.randint(magazines_to_spawn.get("min", 1), magazines_to_spawn.get("max", 1))
                    else:
                        num_mags = int(magazines_to_spawn)

                    if global_variables.get("devmode", {}).get("value", False):
                        debug_info.append(f" Spawning {num_mags} magazine(s) for {firearm_item.get('name', 'Unknown')}")

                    ammo_table = table_data.get("tables", {}).get("ammunition", [])
                    ammo_def = None
                    first_variant = None
                    for ammo in ammo_table:
                        ammo_caliber = ammo.get("caliber")
                        if isinstance(ammo_caliber, str):
                            ammo_caliber =[ammo_caliber]
                        if caliber and ammo_caliber and any(c in ammo_caliber for c in caliber):
                            ammo_def = ammo
                            variants = ammo.get("variants", [])
                            if variants:
                                first_variant = variants[0]
                            break

                    for i in range(num_mags):
                        mag_template = random.choice(compatible_mags)
                        mag_copy = json.loads(json.dumps(mag_template))
                        mag_copy["table_category"]= "magazines"
                        mag_copy["rounds"]=[]

                        capacity = mag_copy.get("capacity", 30)

                        if loading_type =="full":
                            rounds_to_load = capacity
                        elif loading_type =="random":
                            if random.random()<0.5:
                                rounds_to_load = capacity
                            else:
                                rounds_to_load = random.randint(1, capacity)
                        else:
                            rounds_to_load = capacity

                        if ammo_def and first_variant:
                            for _ in range(rounds_to_load):
                                round_data = {
                                "name":ammo_def.get("name"),
                                "caliber":caliber[0]if caliber else ammo_def.get("caliber"),
                                "variant":first_variant.get("name"),
                                "type":first_variant.get("type"),
                                "pen":first_variant.get("pen"),
                                "modifiers":first_variant.get("modifiers"),
                                "tip":first_variant.get("tip")
                                }
                                mag_copy["rounds"].append(round_data)

                        if global_variables.get("devmode", {}).get("value", False):
                            debug_info.append(f" → Spawned {mag_copy.get('name')} with {len(mag_copy['rounds'])}/{capacity} rounds({first_variant.get('name')if first_variant else 'unknown variant'})")

                        spawned_mags.append(mag_copy)

                    return spawned_mags

                table = table_data.get("tables", {}).get(table_name, [])

                if isinstance(item_id, list):

                    matching_items =[]
                    for single_id in item_id:
                        for item in table:
                            if item.get("id")==single_id:
                                if not requested_rarity or item.get("rarity")==requested_rarity:
                                    matching_items.append(item)
                                    if global_variables.get("devmode", {}).get("value", False):
                                        debug_info.append(f" Found ID {single_id} in '{table_name}': {item.get('name', 'Unknown')}")
                                break

                    if matching_items:
                        if multi_type =="or":

                            chosen_item = _weighted_compatibility_pick(matching_items, table_name)
                            item_copy = chosen_item.copy()
                            item_copy["table_category"]= table_name
                            if global_variables.get("devmode", {}).get("value", False):
                                debug_info.append(f" → OR logic: randomly selected '{chosen_item.get('name', 'Unknown')}'")
                                item_copy["_debug_info"]= "\n".join(debug_info)
                            items.append(item_copy)

                            if spawn_magazine and item_copy.get("firearm"):
                                spawned_mags = spawn_magazines_for_item_tableid(item_copy, table_data, debug_info)
                                items.extend(spawned_mags)
                        elif multi_type =="and":

                            if global_variables.get("devmode", {}).get("value", False):
                                debug_info.append(f" → AND logic: giving all {len(matching_items)} items")
                            for idx, matched_item in enumerate(matching_items):
                                item_copy = matched_item.copy()
                                item_copy["table_category"]= table_name
                                if global_variables.get("devmode", {}).get("value", False)and idx ==0:
                                    item_copy["_debug_info"]= "\n".join(debug_info)
                                items.append(item_copy)

                                if spawn_magazine and item_copy.get("firearm"):
                                    spawned_mags = spawn_magazines_for_item_tableid(item_copy, table_data, debug_info)
                                    items.extend(spawned_mags)
                else:

                    for item in table:
                        if item.get("id")==item_id:
                            if not requested_rarity or item.get("rarity")==requested_rarity:
                                item_copy = item.copy()
                                item_copy["table_category"]= table_name
                                if global_variables.get("devmode", {}).get("value", False):
                                    debug_info.append(f" Found ID {item_id} in '{table_name}': {item.get('name', 'Unknown')}")
                                    item_copy["_debug_info"]= "\n".join(debug_info)
                                items.append(item_copy)

                                if spawn_magazine and item_copy.get("firearm"):
                                    spawned_mags = spawn_magazines_for_item_tableid(item_copy, table_data, debug_info)
                                    items.extend(spawned_mags)
                            break

                return self._apply_random_quantity(items, table_data)

            elif entry.get("type")=="id":

                item_id = entry.get("id")
                multi_type = entry.get("multi_type", "or")
                spawn_magazine = entry.get("spawn_magazine", False)
                magazines_to_spawn = entry.get("magazines_to_spawn", 1)
                loading_type = entry.get("loading", "full")

                if global_variables.get("devmode", {}).get("value", False):
                    if isinstance(item_id, list):
                        debug_info.append(f"[DEBUG]Resolving multi-ID entry: {item_id}")
                        debug_info.append(f" Multi-type: {multi_type}({'pick one'if multi_type =='or'else 'give all'})")
                    else:
                        debug_info.append(f"[DEBUG]Resolving ID entry: {item_id}")
                    if spawn_magazine:
                        debug_info.append(f" Spawn magazines: {spawn_magazine}, count: {magazines_to_spawn}, loading: {loading_type}")

                def spawn_magazines_for_item(firearm_item, table_data, debug_info):
                    spawned_mags =[]
                    mag_system = firearm_item.get("magazinesystem")
                    caliber = self._get_effective_firearm_calibers_for_loot(firearm_item)

                    if not mag_system:
                        if global_variables.get("devmode", {}).get("value", False):
                            debug_info.append(f" ⚠ No magazinesystem found for {firearm_item.get('name', 'Unknown')}")
                        return spawned_mags

                    magazines_table = table_data.get("tables", {}).get("magazines", [])
                    compatible_mags =[]
                    for mag in magazines_table:
                        if mag.get("magazinesystem")==mag_system:
                            mag_caliber = mag.get("caliber")
                            if isinstance(mag_caliber, str):
                                mag_caliber =[mag_caliber]

                            if caliber and mag_caliber and any(c in mag_caliber for c in caliber):
                                compatible_mags.append(mag)

                    if not compatible_mags:
                        if global_variables.get("devmode", {}).get("value", False):
                            debug_info.append(f" ⚠ No compatible magazines found for {mag_system}")
                        return spawned_mags

                    if isinstance(magazines_to_spawn, dict):
                        num_mags = random.randint(magazines_to_spawn.get("min", 1), magazines_to_spawn.get("max", 1))
                    else:
                        num_mags = int(magazines_to_spawn)

                    if global_variables.get("devmode", {}).get("value", False):
                        debug_info.append(f" Spawning {num_mags} magazine(s) for {firearm_item.get('name', 'Unknown')}")

                    ammo_table = table_data.get("tables", {}).get("ammunition", [])
                    ammo_def = None
                    first_variant = None
                    for ammo in ammo_table:
                        ammo_caliber = ammo.get("caliber")
                        if isinstance(ammo_caliber, str):
                            ammo_caliber =[ammo_caliber]
                        if caliber and ammo_caliber and any(c in ammo_caliber for c in caliber):
                            ammo_def = ammo

                            variants = ammo.get("variants", [])
                            if variants:
                                first_variant = variants[0]
                            break

                    for i in range(num_mags):

                        mag_template = random.choice(compatible_mags)
                        mag_copy = json.loads(json.dumps(mag_template))
                        mag_copy["table_category"]= "magazines"
                        mag_copy["rounds"]=[]

                        capacity = mag_copy.get("capacity", 30)

                        if loading_type =="full":
                            rounds_to_load = capacity
                        elif loading_type =="random":

                            if random.random()<0.5:
                                rounds_to_load = capacity
                            else:
                                rounds_to_load = random.randint(1, capacity)
                        else:
                            rounds_to_load = capacity

                        if ammo_def and first_variant:
                            for _ in range(rounds_to_load):
                                round_data = {
                                "name":ammo_def.get("name"),
                                "caliber":caliber[0]if caliber else ammo_def.get("caliber"),
                                "variant":first_variant.get("name"),
                                "type":first_variant.get("type"),
                                "pen":first_variant.get("pen"),
                                "modifiers":first_variant.get("modifiers"),
                                "tip":first_variant.get("tip")
                                }
                                mag_copy["rounds"].append(round_data)

                        if global_variables.get("devmode", {}).get("value", False):
                            debug_info.append(f" → Spawned {mag_copy.get('name')} with {len(mag_copy['rounds'])}/{capacity} rounds({first_variant.get('name')if first_variant else 'unknown variant'})")

                        spawned_mags.append(mag_copy)

                    return spawned_mags

                if isinstance(item_id, list):

                    matching_items =[]
                    for single_id in item_id:
                        for table_name, table_items in table_data.get("tables", {}).items():
                            if not isinstance(table_items, list):
                                continue
                            for item in table_items:
                                if not isinstance(item, dict):
                                    continue
                                if item.get("id")==single_id:
                                    matching_items.append((item, table_name))
                                    if global_variables.get("devmode", {}).get("value", False):
                                        debug_info.append(f" Found ID {single_id} in '{table_name}': {item.get('name', 'Unknown')}")
                                    break

                    if matching_items:
                        if multi_type =="or":

                            chosen_item, chosen_table = _weighted_compatibility_pick(matching_items)
                            item_copy = chosen_item.copy()
                            item_copy["table_category"]= chosen_table
                            if global_variables.get("devmode", {}).get("value", False):
                                debug_info.append(f" → OR logic: randomly selected '{chosen_item.get('name', 'Unknown')}'")
                                item_copy["_debug_info"]= "\n".join(debug_info)
                            items.append(item_copy)

                            if spawn_magazine and item_copy.get("firearm"):
                                spawned_mags = spawn_magazines_for_item(item_copy, table_data, debug_info)
                                items.extend(spawned_mags)
                        elif multi_type =="and":

                            if global_variables.get("devmode", {}).get("value", False):
                                debug_info.append(f" → AND logic: giving all {len(matching_items)} items")
                            for idx, (matched_item, matched_table)in enumerate(matching_items):
                                item_copy = matched_item.copy()
                                item_copy["table_category"]= matched_table
                                if global_variables.get("devmode", {}).get("value", False)and idx ==0:
                                    item_copy["_debug_info"]= "\n".join(debug_info)
                                items.append(item_copy)

                                if spawn_magazine and item_copy.get("firearm"):
                                    spawned_mags = spawn_magazines_for_item(item_copy, table_data, debug_info)
                                    items.extend(spawned_mags)
                    return self._apply_random_quantity(items, table_data)
                else:

                    for table_name, table_items in table_data.get("tables", {}).items():
                        if not isinstance(table_items, list):
                            continue
                        for item in table_items:
                            if not isinstance(item, dict):
                                continue
                            if item.get("id")==item_id:
                                item_copy = item.copy()
                                item_copy["table_category"]= table_name
                                if global_variables.get("devmode", {}).get("value", False):
                                    debug_info.append(f" Found in table '{table_name}': {item.get('name', 'Unknown')}")
                                    item_copy["_debug_info"]= "\n".join(debug_info)
                                items.append(item_copy)

                                if spawn_magazine and item_copy.get("firearm"):
                                    spawned_mags = spawn_magazines_for_item(item_copy, table_data, debug_info)
                                    items.extend(spawned_mags)
                                return self._apply_random_quantity(items, table_data)
        except Exception as e:
            logging.error(f"Failed to resolve loot entry {entry}: {e}")

        return self._apply_random_quantity(items, table_data)

    def _apply_random_quantity(self, items, table_data = None):

        def _rescale_blackpowder_weight(powder_item, full_grains_hint = None, full_weight_hint = None):
            if not isinstance(powder_item, dict):
                return
            if str(powder_item.get("type", "") or "").strip().lower() != "gunpowder":
                return

            try:
                current_grains = int(powder_item.get("grains_left", 0) or 0)
            except(Exception, ValueError, TypeError):
                return
            if current_grains < 0:
                current_grains = 0

            if full_grains_hint is not None:
                full_grains = int(full_grains_hint)
            else:
                try:
                    full_grains = int(powder_item.get("grain_storage", 0) or 0)
                except(Exception, ValueError, TypeError):
                    full_grains = 0
                if full_grains <= 0:
                    full_grains = max(1, current_grains)

            powder_item["grain_storage"] = max(1, int(full_grains))

            if full_weight_hint is not None:
                try:
                    full_weight = float(full_weight_hint)
                except(Exception, ValueError, TypeError):
                    full_weight = None
            else:
                try:
                    full_weight = float(powder_item.get("weight_full", powder_item.get("weight", 0)) or 0)
                except(Exception, ValueError, TypeError):
                    full_weight = None

            if full_weight is None or full_weight < 0:
                return

            powder_item["weight_full"] = full_weight
            fill_ratio = 0.0 if full_grains <= 0 else max(0.0, min(1.0, float(current_grains) / float(full_grains)))
            powder_item["weight"] = round(full_weight * fill_ratio, 6)

        for item in items:
            if not isinstance(item, dict):
                continue

            rq = item.get("random_quantity")
            if rq and isinstance(rq, dict):
                min_qty = rq.get("min", 1)
                max_qty = rq.get("max", 1)
                try:
                    actual_qty = random.randint(int(min_qty), int(max_qty))
                except(ValueError, TypeError):
                    actual_qty = 1
                item["quantity"]= actual_qty
                del item["random_quantity"]
                logging.debug(f"Applied random_quantity to {item.get('name', 'Unknown')}: {actual_qty}(range {min_qty}-{max_qty})")

            # Looted multi-use consumables have a 50% chance to spawn partially used.
            if item.get("consumable") and "uses_left" in item:
                try:
                    max_uses = int(item.get("uses_left", 0))
                except(TypeError, ValueError):
                    max_uses = 0
                if max_uses >1 and random.random()<0.5:
                    item["uses_left"] = random.randint(1, max_uses)

            # Randomize bulk blackpowder amount on loot; flasks remain separate.
            if str(item.get("type", "") or "").strip().lower() == "gunpowder":
                try:
                    full_grains = int(item.get("grains_left", 0) or 0)
                except(Exception, ValueError, TypeError):
                    full_grains = 0
                if full_grains > 0:
                    looted_grains = random.randint(max(1, int(full_grains * 0.2)), full_grains)
                    item["grains_left"] = looted_grains
                    _rescale_blackpowder_weight(item, full_grains_hint = full_grains, full_weight_hint = item.get("weight"))

            # Looted standalone weapon parts can define durability at loot-time.
            if not item.get("firearm"):
                dur_val = item.get("durability")
                dur_txt = str(dur_val).strip().lower() if dur_val is not None else ""
                if dur_txt == "set_by_looting":
                    cur_dur = item.get("current_durability")
                    try:
                        has_numeric_cur = cur_dur is not None and not math.isnan(float(cur_dur))
                    except(Exception, ValueError, TypeError):
                        has_numeric_cur = False
                    if not has_numeric_cur:
                        item["current_durability"] = round(
                            random.uniform(PART_DURABILITY_MAX * 0.15, PART_DURABILITY_MAX),
                            2,
                        )

            # Looted standalone ammunition needs a concrete variant selected
            # (weighted by variant rarity) so it doesn't carry the raw variant
            # list into inventory with no variant chosen. Magazines/firearms are
            # excluded; their rounds are filled separately below.
            if (isinstance(item.get("variants"), list) and item.get("variants")
                    and not item.get("firearm") and not item.get("magazinesystem")
                    and not item.get("variant")):
                ammo_variants = [v for v in item.get("variants", []) if isinstance(v, dict)]
                if ammo_variants:
                    rarity_weights = (table_data or {}).get("rarity_weights", {})
                    variant_weights = []
                    for var in ammo_variants:
                        v_rarity = var.get("rarity") or item.get("rarity") or "Common"
                        try:
                            w = float(rarity_weights.get(v_rarity, 1)) or 1.0
                        except(TypeError, ValueError):
                            w = 1.0
                        variant_weights.append(max(0.0001, w))
                    chosen_variant = random.choices(ammo_variants, weights = variant_weights, k = 1)[0]
                    cal = item.get("caliber")
                    if isinstance(cal, (list, tuple)):
                        cal_str = ", ".join(str(c).strip() for c in cal if str(c).strip())
                    else:
                        cal_str = str(cal).strip() if cal else ""
                    vname = str(chosen_variant.get("name") or chosen_variant.get("type") or "FMJ")
                    item["variant"] = vname
                    if cal_str:
                        item["name"] = f"{vname} ({cal_str})"
                    _apply_ammo_variant_data(item, item, chosen_variant)
                    item.pop("variants", None)

            if table_data and item.get("capacity")and item.get("magazinesystem")and not item.get("firearm"):

                if not item.get("rounds"):
                    item["rounds"]=[]
                if len(item.get("rounds", []))==0:
                    caliber = item.get("caliber")
                    if isinstance(caliber, str):
                        caliber =[caliber]

                    capacity = item.get("capacity", 30)

                    rounds_to_load = random.randint(max(1, capacity //4), capacity)

                    ammo_table = table_data.get("tables", {}).get("ammunition", [])
                    ammo_def = None
                    first_variant = None
                    for ammo in ammo_table:
                        ammo_caliber = ammo.get("caliber")
                        if isinstance(ammo_caliber, str):
                            ammo_caliber =[ammo_caliber]
                        if caliber and ammo_caliber and any(c in ammo_caliber for c in caliber):
                            ammo_def = ammo
                            variants = ammo.get("variants", [])
                            if variants:
                                first_variant = variants[0]
                            break

                    if ammo_def and first_variant:
                        for _ in range(rounds_to_load):
                            round_data = {
                            "name":ammo_def.get("name"),
                            "caliber":caliber[0]if caliber else ammo_def.get("caliber"),
                            "variant":first_variant.get("name"),
                            "type":first_variant.get("type"),
                            "pen":first_variant.get("pen"),
                            "modifiers":first_variant.get("modifiers"),
                            "tip":first_variant.get("tip")
                            }
                            item["rounds"].append(round_data)
                        logging.debug(f"Loaded magazine {item.get('name', 'Unknown')} with {rounds_to_load}/{capacity} rounds")

            if table_data and item.get("firearm"):
                self._apply_random_firearm_attachments(item, table_data, chance = 0.25)

            if table_data and item.get("firearm")and item.get("magazinesystem")and not item.get("loaded"):

                if random.random()<0.4:
                    mag_system = item.get("magazinesystem")
                    caliber = self._get_effective_firearm_calibers_for_loot(item)

                    magazines_table = table_data.get("tables", {}).get("magazines", [])
                    compatible_mags =[]
                    for mag in magazines_table:
                        if mag.get("magazinesystem")==mag_system:
                            mag_caliber = mag.get("caliber")
                            if isinstance(mag_caliber, str):
                                mag_caliber =[mag_caliber]
                            if caliber and mag_caliber and any(c in mag_caliber for c in caliber):
                                compatible_mags.append(mag)

                    if compatible_mags:
                        mag_template = random.choice(compatible_mags)
                        mag_copy = json.loads(json.dumps(mag_template))
                        mag_copy["table_category"]= "magazines"
                        mag_copy["rounds"]=[]

                        capacity = mag_copy.get("capacity", 30)

                        rounds_to_load = random.randint(max(1, capacity //4), capacity)

                        ammo_table = table_data.get("tables", {}).get("ammunition", [])
                        ammo_def = None
                        first_variant = None
                        for ammo in ammo_table:
                            ammo_caliber = ammo.get("caliber")
                            if isinstance(ammo_caliber, str):
                                ammo_caliber =[ammo_caliber]
                            if caliber and ammo_caliber and any(c in ammo_caliber for c in caliber):
                                ammo_def = ammo
                                variants = ammo.get("variants", [])
                                if variants:
                                    first_variant = variants[0]
                                break

                        if ammo_def and first_variant:
                            for _ in range(rounds_to_load):
                                round_data = {
                                "name":ammo_def.get("name"),
                                "caliber":caliber[0]if caliber else ammo_def.get("caliber"),
                                "variant":first_variant.get("name"),
                                "type":first_variant.get("type"),
                                "pen":first_variant.get("pen"),
                                "modifiers":first_variant.get("modifiers"),
                                "tip":first_variant.get("tip")
                                }
                                mag_copy["rounds"].append(round_data)

                        item["loaded"]= mag_copy
                        logging.debug(f"Loaded firearm {item.get('name', 'Unknown')} with {mag_copy.get('name')}({rounds_to_load}/{capacity} rounds)")

            if item.get("firearm") and item.get("parts"):
                if "rounds_fired" not in item:
                    # Curve: bias toward moderate use, but with a real chance of
                    # absurdly high round counts (higher ceiling than shops).
                    _loot_roll = random.random()
                    if _loot_roll < 0.55:
                        item["rounds_fired"] = int(500 + (random.random() ** 1.4) * 9500)
                    elif _loot_roll < 0.85:
                        item["rounds_fired"] = int(10000 + (random.random() ** 1.1) * 40000)
                    elif _loot_roll < 0.97:
                        item["rounds_fired"] = int(50000 + (random.random() ** 0.9) * 100000)
                    else:
                        item["rounds_fired"] = int(150000 + random.random() * 350000)

                _sync_firearm_cleanliness_from_rounds_fired(item)

                # Deep-copy parts so shared table dicts are not mutated between
                # multiple items of the same type looted in one session.
                if isinstance(item.get("parts"), list):
                    item["parts"] = json.loads(json.dumps(item["parts"]))

                _randomize_part_durability(item)

                # Broken-part replacement: heavily-used guns may have parts that
                # have completely worn out and been swapped with mismatched spares.
                _rf = int(item.get("rounds_fired", 0) or 0)
                if _rf >= 50000 and table_data:
                    if _rf < 100000:
                        _break_chance = 0.04
                    elif _rf < 200000:
                        _break_chance = 0.12
                    else:
                        _break_chance = 0.28

                    # Build a flat list of candidate replacement parts from all tables.
                    _replacement_pool = {}  # slot/type key -> list of candidate dicts
                    for _tbl_list in table_data.get("tables", {}).values():
                        if not isinstance(_tbl_list, list):
                            continue
                        for _cand in _tbl_list:
                            if not isinstance(_cand, dict) or _cand.get("firearm"):
                                continue
                            _cand_slot = str(_cand.get("slot") or "").strip().lower()
                            _cand_type = str(_cand.get("type") or "").strip().lower()
                            for _key in (_cand_slot, _cand_type):
                                if _key:
                                    _replacement_pool.setdefault(_key, []).append(_cand)

                    for _p in item["parts"]:
                        if not isinstance(_p, dict):
                            continue
                        if random.random() >= _break_chance:
                            continue
                        # Mark broken.
                        _p["current_durability"] = 0.0
                        # Find a random replacement matching this slot or type.
                        _p_slot = str(_p.get("slot") or "").strip().lower()
                        _p_type = str(_p.get("type") or "").strip().lower()
                        _candidates = _replacement_pool.get(_p_slot) or _replacement_pool.get(_p_type)
                        if _candidates:
                            _replacement = json.loads(json.dumps(random.choice(_candidates)))
                            _p["current"] = _replacement
                            # Give the replacement a random low-to-medium durability.
                            _p["current_durability"] = random.uniform(
                                PART_DURABILITY_MAX * 0.08, PART_DURABILITY_MAX * 0.42
                            )

            if item.get("spring_durability") == "set_by_looting":
                item["spring_durability"] = random.uniform(100, PART_DURABILITY_MAX)
            if item.get("reliability") is None and item.get("magazinesystem") and not item.get("firearm"):
                item["reliability"] = random.randint(70, 100)

        return items

    def _get_loot_crate_contents_preview(self, crate, table_data):

        info_lines =[]
        try:

            locked_status = "Locked"if crate.get("locked", False)else "Unlocked"
            pulls = crate.get("pulls", 3)
            if isinstance(pulls, dict):
                pulls_text = f"{pulls.get('min')}-{pulls.get('max')}"
            else:
                pulls_text = str(pulls)
            info_lines.append(f"{locked_status} | Pulls: {pulls_text}")

            num_entries = len(crate.get("loot_table", []))
            info_lines.append(f"Loot entries: {num_entries}")
        except Exception as e:
            logging.error(f"Failed to generate loot preview: {e}")

        if info_lines:
            return "\n".join(info_lines)
        return ""

    def _open_loot_selection_menu(self, crate, available_items, save_data, save_path, crate_file_path, table_data):

        self._clear_window()

        self.root.grid_rowconfigure(0, weight = 1)
        self.root.grid_columnconfigure(0, weight = 1)

        main_frame = customtkinter.CTkFrame(self.root)
        main_frame.grid(row = 0, column = 0, sticky = "nsew")

        title_label = customtkinter.CTkLabel(
        main_frame,
        text = f"Loot: {crate.get('name', 'Unknown Crate')}",
        font = customtkinter.CTkFont(size = 20, weight = "bold")
        )
        title_label.pack(pady = 20)

        def get_loot_containers():
            containers =[]
            equipment = save_data.get("equipment", {})

            containers.append({"name":"Hands", "location":"hands"})

            for slot, item in equipment.items():

                if item and isinstance(item, dict):
                    if "capacity"in item and "items"in item:
                        containers.append({
                        "name":f"{item.get('name', 'Container')}({slot})",
                        "location":f"equipment.{slot}"
                        })

                    if item.get("subslots"):
                        for subslot_idx, subslot_data in enumerate(item["subslots"]):
                            subslot_item = subslot_data.get("current")
                            if subslot_item and isinstance(subslot_item, dict):
                                if "capacity"in subslot_item and "items"in subslot_item:
                                    subslot_name = subslot_data.get("name", f"Subslot {subslot_idx}")
                                    containers.append({
                                    "name":f"{subslot_item.get('name', 'Container')}({slot} → {subslot_name})",
                                    "location":f"equipment.{slot}.subslot.{subslot_idx}"
                                    })

                elif isinstance(item, list):
                    for idx, subitem in enumerate(item):
                        try:
                            if subitem and isinstance(subitem, dict)and "capacity"in subitem and "items"in subitem:
                                containers.append({
                                "name":f"{subitem.get('name', 'Container')}({slot}#{idx})",
                                "location":f"equipment.{slot}.list.{idx}"
                                })

                            if subitem and isinstance(subitem, dict)and "subslots"in subitem:
                                for subslot_idx, subslot_data in enumerate(subitem.get("subslots", [])):
                                    subslot_item = subslot_data.get("current")
                                    if subslot_item and isinstance(subslot_item, dict):
                                        if "capacity"in subslot_item and "items"in subslot_item:
                                            subslot_name = subslot_data.get("name", f"Subslot {subslot_idx}")
                                            containers.append({
                                            "name":f"{subslot_item.get('name', 'Container')}({slot}#{idx} → {subslot_name})",
                                            "location":f"equipment.{slot}.list.{idx}.subslot.{subslot_idx}"
                                            })
                        except Exception:
                            logging.exception("Suppressed exception")

            return containers

        loot_containers = get_loot_containers()
        container_names =[c["name"]for c in loot_containers]

        def get_container_items_local(location):
            if location =="hands":
                return save_data["hands"].get("items", [])
            elif location.startswith("equipment."):
                parts = location.split(".")
                slot = parts[1]
                item = save_data["equipment"].get(slot)
                if item is None:
                    return[]
                if len(parts)>2 and parts[2]=="subslot":
                    subslot_idx = int(parts[3])
                    if isinstance(item, dict)and "subslots"in item and subslot_idx <len(item["subslots"]):
                        subslot_item = item["subslots"][subslot_idx].get("current")
                        if subslot_item and isinstance(subslot_item, dict):
                            return subslot_item.get("items", [])
                if len(parts)>2 and parts[2]=="list":
                    list_idx = int(parts[3])
                    if isinstance(item, list)and 0 <=list_idx <len(item):
                        subitem = item[list_idx]
                        if len(parts)>4 and parts[4]=="subslot":
                            subslot_idx = int(parts[5])
                            if "subslots"in subitem and subslot_idx <len(subitem["subslots"]):
                                subslot_item = subitem["subslots"][subslot_idx].get("current")
                                if subslot_item and isinstance(subslot_item, dict):
                                    return subslot_item.get("items", [])
                        return subitem.get("items", [])if isinstance(subitem, dict)else[]
                if isinstance(item, dict):
                    return item.get("items", [])
            return[]

        def set_container_items_local(location, items):
            if location =="hands":
                save_data["hands"]["items"]= items
            elif location.startswith("equipment."):
                parts = location.split(".")
                slot = parts[1]
                if slot in save_data["equipment"]and save_data["equipment"][slot]:
                    item = save_data["equipment"][slot]
                    if len(parts)>2 and parts[2]=="subslot":
                        subslot_idx = int(parts[3])
                        if isinstance(item, dict)and "subslots"in item and subslot_idx <len(item["subslots"]):
                            subslot_item = item["subslots"][subslot_idx].get("current")
                            if subslot_item and isinstance(subslot_item, dict):
                                subslot_item["items"]= items
                    elif len(parts)>2 and parts[2]=="list":
                        list_idx = int(parts[3])
                        if isinstance(item, list)and 0 <=list_idx <len(item):
                            subitem = item[list_idx]
                            if len(parts)>4 and parts[4]=="subslot":
                                subslot_idx = int(parts[5])
                                if "subslots"in subitem and subslot_idx <len(subitem["subslots"]):
                                    subslot_item = subitem["subslots"][subslot_idx].get("current")
                                    if subslot_item and isinstance(subslot_item, dict):
                                        subslot_item["items"]= items
                            else:
                                if isinstance(subitem, dict):
                                    subitem["items"]= items
                    else:
                        if isinstance(item, dict):
                            item["items"]= items

        def get_container_capacity_local(location):
            if location =="hands":
                base_capacity = save_data.get("hands", {}).get("capacity", 50)
                strength = save_data.get("stats", {}).get("Strength", 0)

                return base_capacity *(1 +strength *0.1)
            if location.startswith("equipment."):
                parts = location.split(".")
                slot = parts[1]
                equip = save_data.get("equipment", {}).get(slot)
                if equip:
                    if len(parts)>2 and parts[2]=="subslot":
                        subslot_idx = int(parts[3])
                        if isinstance(equip, dict)and "subslots"in equip and subslot_idx <len(equip["subslots"]):
                            subslot_item = equip["subslots"][subslot_idx].get("current")
                            if subslot_item and isinstance(subslot_item, dict):
                                return subslot_item.get("capacity")
                            return None
                    if len(parts)>2 and parts[2]=="list":
                        list_idx = int(parts[3])
                        if isinstance(equip, list)and 0 <=list_idx <len(equip):
                            subitem = equip[list_idx]
                            if len(parts)>4 and parts[4]=="subslot":
                                subslot_idx = int(parts[5])
                                if "subslots"in subitem and subslot_idx <len(subitem["subslots"]):
                                    subslot_item = subitem["subslots"][subslot_idx].get("current")
                                    if subslot_item and isinstance(subslot_item, dict):
                                        return subslot_item.get("capacity")
                                return None
                            return subitem.get("capacity")if isinstance(subitem, dict)else None
                    return equip.get("capacity")if isinstance(equip, dict)else None
            return None

        container_frame = customtkinter.CTkFrame(main_frame, fg_color = "transparent")
        container_frame.pack(fill = "x", padx = 20, pady =(0, 10))

        customtkinter.CTkLabel(
        container_frame,
        text = "Put items into:",
        font = customtkinter.CTkFont(size = 12)
        ).pack(side = "left", padx =(0, 10))

        container_selector = customtkinter.CTkOptionMenu(
        container_frame,
        values = container_names if container_names else["Hands"],
        width = 350,
        font = customtkinter.CTkFont(size = 12)
        )
        container_selector.pack(side = "left")
        container_selector.set(container_names[0]if container_names else "Hands")

        scroll_frame = customtkinter.CTkScrollableFrame(main_frame)
        scroll_frame.pack(fill = "both", expand = True, padx = 20, pady = 20)

        if global_variables.get("devmode", {}).get("value", False)and available_items:

            all_debug =[]
            for item in available_items:
                if item.get("_debug_info"):
                    all_debug.append(item.get("_debug_info"))
                    all_debug.append("")

            if all_debug:
                debug_frame = customtkinter.CTkFrame(scroll_frame, fg_color = "#1a1a2e")
                debug_frame.pack(fill = "x", pady =(0, 15), padx = 5)

                customtkinter.CTkLabel(
                debug_frame,
                text = "🔧 LOOT RESOLUTION DEBUG",
                font = customtkinter.CTkFont(size = 12, weight = "bold"),
                text_color = "#00ff88"
                ).pack(anchor = "w", padx = 10, pady =(10, 5))

                debug_text = customtkinter.CTkTextbox(
                debug_frame,
                height = 200,
                font = customtkinter.CTkFont(family = "Consolas", size = 10),
                fg_color = "#0d0d1a",
                text_color = "#88ff88"
                )
                debug_text.pack(fill = "x", padx = 10, pady =(0, 10))
                debug_text.insert("1.0", "\n".join(all_debug))
                debug_text.configure(state = "disabled")

        selected_items_checkboxes = {}

        def update_weight_display():

            selected_weight = 0.0
            for idx, checkbox in selected_items_checkboxes.items():
                if checkbox.get():
                    item = available_items[idx]
                    qty = item.get("quantity", 1)
                    weight = item.get("weight", 0)*qty
                    selected_weight +=weight

            current_encumbrance = self._calculate_encumbrance_status(save_data)

            new_encumbrance = current_encumbrance["encumbrance"]+selected_weight
            new_total_weight = current_encumbrance["total_weight"]+selected_weight

            threshold = current_encumbrance.get("threshold", save_data.get("encumbered_threshold", 50))

            weight_text = f"Selected Weight: {self._format_weight(selected_weight)}\n"
            weight_text +=f"New Total: {self._format_weight(new_total_weight)}\n"
            weight_text +=f"Encumbrance: {self._format_weight(new_encumbrance)} / {self._format_weight(threshold)}"

            if new_encumbrance >threshold:
                weight_text +=" ⚠️ ENCUMBERED"
                weight_label.configure(text_color = "red")
            else:
                weight_label.configure(text_color = "white")

            weight_label.configure(text = weight_text)

        # ── firearm inspect popup ──────────────────────────────────────────
        def _open_firearm_inspect(gun):
            import copy as _ic
            import copy as _ic_deep

            popup = customtkinter.CTkToplevel(self.root)
            popup.title(f"Inspect: {gun.get('name', 'Firearm')}")
            popup.transient(self.root)
            popup.grab_set()
            self._center_popup_on_window(popup, 500, 540)

            # --- shared durability helper (mirrors _view_parts / manage_attachments) ---
            def _dur_text(cur_dur, max_dur_field):
                if cur_dur is None:
                    return "N/A", "#888888"
                try:
                    val = float(cur_dur)
                except (TypeError, ValueError):
                    return "Unknown", "#888888"
                pct = max(0.0, min(100.0, val / PART_DURABILITY_MAX * 100))
                if val <= 0:
                    return "Worn Out", "#ff4444"
                elif pct < 25:
                    return "Poor", "#ff6644"
                elif pct < 50:
                    return "Fair", "#ffaa44"
                elif pct < 75:
                    return "Good", "#aacc44"
                else:
                    return "Excellent", "#44cc44"

            def _resolve_cur(p):
                """Return the resolved current-part dict from a part slot entry."""
                cur = p.get("current")
                if cur is None:
                    return None
                if isinstance(cur, dict) and "name" in cur:
                    return cur
                target_id = None
                if isinstance(cur, int):
                    target_id = cur
                elif isinstance(cur, dict) and "id" in cur:
                    target_id = cur.get("id")
                if target_id is None:
                    return cur if isinstance(cur, dict) else None
                if isinstance(table_data, dict):
                    for _tbl in table_data.get("tables", {}).values():
                        if not isinstance(_tbl, list):
                            continue
                        for _it in _tbl:
                            if isinstance(_it, dict) and _it.get("id") == target_id:
                                resolved = _ic_deep.deepcopy(_it)
                                if isinstance(cur, dict):
                                    for k, v in cur.items():
                                        if k != "id":
                                            resolved[k] = v
                                p["current"] = resolved
                                return resolved
                return cur if isinstance(cur, dict) else None

            # ── tab bar ────────────────────────────────────────────────────────
            tab_view = customtkinter.CTkTabview(popup, width = 480, height = 480)
            tab_view.pack(fill = "both", expand = True, padx = 8, pady = 8)

            tab_parts   = tab_view.add("Parts")
            tab_mag     = tab_view.add("Magazine")
            tab_attach  = tab_view.add("Attachments")

            # ── PARTS tab ─────────────────────────────────────────────────────
            parts = gun.get("parts") or []
            parts_scroll = customtkinter.CTkScrollableFrame(tab_parts, fg_color = "transparent")
            parts_scroll.pack(fill = "both", expand = True, padx = 4, pady = 4)

            if not parts:
                customtkinter.CTkLabel(parts_scroll, text = "No part data.",
                                       text_color = "#888888").pack(pady = 20)
            else:
                rf = int(gun.get("rounds_fired", 0) or 0)
                rounds_label = customtkinter.CTkLabel(
                    parts_scroll,
                    text = f"Rounds fired: {rf:,}",
                    font = customtkinter.CTkFont(size = 11),
                    text_color = "#aaaaaa"
                )
                rounds_label.pack(anchor = "w", padx = 8, pady = (4, 8))

                for p in parts:
                    if not isinstance(p, dict):
                        continue
                    resolved = _resolve_cur(p)
                    part_name = (resolved.get("name") if resolved else None) or p.get("name") or p.get("type", "Unknown")
                    slot_label = (p.get("type") or "").replace("_", " ").title() or part_name

                    row = customtkinter.CTkFrame(parts_scroll)
                    row.pack(fill = "x", padx = 4, pady = 3)
                    row.grid_columnconfigure(1, weight = 1)

                    customtkinter.CTkLabel(
                        row, text = slot_label,
                        font = customtkinter.CTkFont(size = 11, weight = "bold"),
                        width = 140, anchor = "w"
                    ).grid(row = 0, column = 0, padx = (8, 4), pady = 4, sticky = "w")

                    customtkinter.CTkLabel(
                        row, text = part_name,
                        font = customtkinter.CTkFont(size = 11),
                        anchor = "w"
                    ).grid(row = 0, column = 1, padx = 4, pady = 4, sticky = "w")

                    cur_dur = p.get("current_durability")
                    if cur_dur is None and resolved:
                        cur_dur = resolved.get("current_durability")
                    dur_text, dur_col = _dur_text(cur_dur, p.get("durability"))
                    customtkinter.CTkLabel(
                        row, text = dur_text,
                        font = customtkinter.CTkFont(size = 10),
                        text_color = dur_col, width = 90, anchor = "e"
                    ).grid(row = 0, column = 2, padx = (4, 8), pady = 4, sticky = "e")

            # ── MAGAZINE tab ──────────────────────────────────────────────────
            import tkinter as _tk_insp
            import threading as _thr_insp

            loaded = gun.get("loaded")
            _mag_state = {'removed': False, 'animating': False, 'stoggle': 0}

            _mag_outer = customtkinter.CTkFrame(tab_mag, fg_color = "transparent")
            _mag_outer.pack(fill = "both", expand = True)

            def _play_mag_sound_bg(action):
                def _do():
                    try:
                        self._play_weapon_action_sound(gun, action)
                    except Exception:
                        logging.exception("Suppressed exception")
                _thr_insp.Thread(target = _do, daemon = True).start()

            def _build_mag_view():
                for w in _mag_outer.winfo_children():
                    w.destroy()

                if not loaded:
                    customtkinter.CTkLabel(_mag_outer, text = "No magazine loaded.",
                                           text_color = "#888888").pack(pady = 20)
                    return

                if not _mag_state['removed']:
                    # ── sealed state ───────────────────────────────────────
                    cap_val = loaded.get("capacity", "?")
                    n_val   = len(loaded.get("rounds", []))
                    customtkinter.CTkLabel(
                        _mag_outer,
                        text = f"Loaded: {loaded.get('name', 'Magazine')}",
                        font = customtkinter.CTkFont(size = 13, weight = "bold")
                    ).pack(anchor = "w", padx = 10, pady = (10, 2))
                    customtkinter.CTkLabel(
                        _mag_outer,
                        text = f"Rounds: {n_val} / {cap_val}",
                        font = customtkinter.CTkFont(size = 11),
                        text_color = "#aaaaaa"
                    ).pack(anchor = "w", padx = 10, pady = 2)

                    def _remove_mag():
                        _mag_state['removed'] = True
                        _play_mag_sound_bg("magout")
                        popup.after(250, _build_mag_view)

                    customtkinter.CTkButton(
                        _mag_outer, text = "Remove Magazine to Inspect",
                        command = _remove_mag, width = 220,
                        fg_color = "#553322", hover_color = "#774433"
                    ).pack(pady = (10, 4), padx = 10, anchor = "w")
                    customtkinter.CTkLabel(
                        _mag_outer,
                        text = "Remove the magazine to view and unload its rounds.",
                        font = customtkinter.CTkFont(size = 10),
                        text_color = "#666666"
                    ).pack(anchor = "w", padx = 10)

                else:
                    # ── removed state: canvas mag viewer ───────────────────
                    mag = loaded
                    cap = int(mag.get("capacity", 0) or 0) or 30
                    existing = mag.setdefault("rounds", [])  # live reference

                    # --- tip-colour lookup (same as unload editor) ---
                    vtips_ins = {}
                    try:
                        _ammo_tbl = self._get_ammo_table_data()
                        mag_cal = mag.get("caliber")
                        mcal_str = mag_cal if isinstance(mag_cal, str) else (
                            mag_cal[0] if isinstance(mag_cal, list) and mag_cal else None)
                        for _atbl in _ammo_tbl:
                            _ac = _atbl.get("caliber")
                            _match = (_ac == mcal_str) if isinstance(_ac, str) else (
                                mcal_str in _ac if isinstance(_ac, list) and mcal_str else False)
                            if _match:
                                for _av in _atbl.get("variants", []):
                                    _atn = _av.get("name"); _att = _av.get("tip")
                                    if _atn and _att and isinstance(_att, str) and _att.startswith("#"):
                                        vtips_ins[_atn] = _att
                                break
                    except Exception:
                        logging.exception("Suppressed exception")

                    vset = {(r.get("variant") or r.get("name") or "Unknown")
                            for r in existing if isinstance(r, dict)}
                    cpal = ["#c4a032", "#b87333", "#a0a0a0", "#d4af37",
                            "#8b4513", "#cd7f32", "#e8c872", "#a08060"]
                    vcols_ins = {v: cpal[i % len(cpal)] for i, v in enumerate(sorted(vset))}

                    def _utip(vn):
                        return vtips_ins.get(vn, "#e0c060")

                    def _utip_ol(vn):
                        tc = vtips_ins.get(vn)
                        if not tc:
                            return "#aa8820"
                        try:
                            r2 = int(tc[1:3], 16); g2 = int(tc[3:5], 16); b2 = int(tc[5:7], 16)
                            return f"#{max(0, r2-40):02x}{max(0, g2-40):02x}{max(0, b2-40):02x}"
                        except Exception:
                            return "#aa8820"

                    def _utip_r(r):
                        return _utip(r.get("variant") or r.get("name") or "Unknown") if isinstance(r, dict) else "#e0c060"

                    def _utip_ol_r(r):
                        return _utip_ol(r.get("variant") or r.get("name") or "Unknown") if isinstance(r, dict) else "#aa8820"

                    SLOT_H = 28; SLOT_W = 260; ox_m = 20; SPRING_H = 14
                    canvas_h = 30 + cap * SLOT_H + SPRING_H + 8
                    canvas_w = SLOT_W + 44

                    # header row: name + round count label + re-insert button
                    hdr = customtkinter.CTkFrame(_mag_outer, fg_color = "transparent")
                    hdr.pack(fill = "x", padx = 6, pady = (6, 2))
                    customtkinter.CTkLabel(
                        hdr, text = mag.get("name", "Magazine"),
                        font = customtkinter.CTkFont(size = 12, weight = "bold")
                    ).pack(side = "left", padx = 6)
                    _cnt_lbl = customtkinter.CTkLabel(
                        hdr,
                        text = f"{len(existing)}/{cap} rounds",
                        font = customtkinter.CTkFont(size = 11),
                        text_color = "#aaaaaa"
                    )
                    _cnt_lbl.pack(side = "left", padx = 6)

                    def _reinstate():
                        _mag_state['removed'] = False
                        _mag_state['animating'] = False
                        _play_mag_sound_bg("magin")
                        popup.after(250, _build_mag_view)

                    customtkinter.CTkButton(
                        hdr, text = "Re-insert Magazine",
                        command = _reinstate, width = 165, height = 26,
                        font = customtkinter.CTkFont(size = 11),
                        fg_color = "#225522", hover_color = "#337733"
                    ).pack(side = "right", padx = 6)

                    # canvas container
                    canvas_container = _tk_insp.Frame(_mag_outer, bg = "#1a1a1a")
                    canvas_container.pack(fill = "both", expand = True, padx = 6, pady = 4)

                    effective_h = min(canvas_h, 360)
                    insp_canvas = _tk_insp.Canvas(
                        canvas_container, width = canvas_w, height = effective_h,
                        bg = "#1a1a1a", highlightthickness = 1, highlightbackground = "#555555"
                    )
                    if canvas_h > 360:
                        _sc = _tk_insp.Scrollbar(canvas_container, orient = "vertical",
                                                  command = insp_canvas.yview)
                        _sc.pack(side = "right", fill = "y")
                        insp_canvas.configure(yscrollcommand = _sc.set,
                                               scrollregion = (0, 0, canvas_w, canvas_h))
                    insp_canvas.pack(side = "left", fill = "both", expand = True)

                    MAG_TOP = 30

                    def _draw_mag_canvas():
                        insp_canvas.delete("mag")
                        oy = MAG_TOP
                        insp_canvas.create_text(
                            canvas_w // 2, 12,
                            text = "\u2191 CLICK ROUND TO EJECT \u2191",
                            fill = "#888888", font = ("Consolas", 9), tags = "mag"
                        )
                        insp_canvas.create_rectangle(
                            ox_m, oy, ox_m + SLOT_W, oy + cap * SLOT_H,
                            outline = "#888888", width = 2, tags = "mag"
                        )
                        insp_canvas.create_line(ox_m, oy, ox_m - 15, oy - 8,
                                                fill = "#888888", width = 2, tags = "mag")
                        insp_canvas.create_line(ox_m + SLOT_W, oy, ox_m + SLOT_W + 15, oy - 8,
                                                fill = "#888888", width = 2, tags = "mag")
                        for i in range(cap):
                            sy = oy + i * SLOT_H
                            if i > 0:
                                insp_canvas.create_line(ox_m, sy, ox_m + SLOT_W, sy,
                                                        fill = "#444444", dash = (2, 2), tags = "mag")
                            if i < len(existing):
                                r = existing[i]
                                vn = (r.get("variant") or r.get("name") or "Unknown") if isinstance(r, dict) else "Unknown"
                                c = vcols_ins.get(vn, "#c4a032")
                                insp_canvas.create_rectangle(
                                    ox_m + 2, sy + 2, ox_m + SLOT_W - 2, sy + SLOT_H - 2,
                                    fill = c, outline = "#222222", tags = "mag"
                                )
                                insp_canvas.create_oval(
                                    ox_m + 4, sy + 4, ox_m + 22, sy + SLOT_H - 4,
                                    fill = _utip_r(r), outline = _utip_ol_r(r), tags = "mag"
                                )
                                insp_canvas.create_text(
                                    ox_m + SLOT_W // 2 + 10, sy + SLOT_H // 2,
                                    text = vn, fill = "#1a1a1a",
                                    font = ("Consolas", 9, "bold"), tags = "mag"
                                )
                            else:
                                insp_canvas.create_text(
                                    ox_m + SLOT_W // 2, sy + SLOT_H // 2,
                                    text = "[empty]", fill = "#444444",
                                    font = ("Consolas", 9), tags = "mag"
                                )
                        by = oy + cap * SLOT_H
                        insp_canvas.create_rectangle(
                            ox_m, by, ox_m + SLOT_W, by + SPRING_H,
                            fill = "#555555", outline = "#666666", tags = "mag"
                        )
                        insp_canvas.create_text(
                            ox_m + SLOT_W // 2, by + SPRING_H // 2,
                            text = "\u25b2 SPRING \u25b2", fill = "#888888",
                            font = ("Consolas", 8), tags = "mag"
                        )

                    def _play_eject_sound():
                        try:
                            sn = f"bulletinsert{_mag_state['stoggle']}"
                            _mag_state['stoggle'] = 1 - _mag_state['stoggle']
                            sound_path = os.path.join("sounds", "firearms", "universal", f"{sn}.ogg")
                            if os.path.exists(sound_path):
                                snd = pygame.mixer.Sound(sound_path)
                                ch = pygame.mixer.find_channel()
                                if ch:
                                    ch.play(snd)
                        except Exception:
                            logging.exception("Suppressed exception")

                    def _eject_round(idx):
                        if idx < 0 or idx >= len(existing) or _mag_state['animating']:
                            return
                        removed = existing.pop(idx)
                        try:
                            save_data.setdefault('hands', {}).setdefault('items', [])
                            self._add_rounds_to_container(save_data['hands']['items'], [removed])
                        except Exception:
                            logging.exception("Suppressed exception")
                        _play_eject_sound()
                        _draw_mag_canvas()
                        _cnt_lbl.configure(text = f"{len(existing)}/{cap} rounds")

                    def _hit_slot(x, y):
                        oy = MAG_TOP
                        if x < ox_m or x > ox_m + SLOT_W:
                            return None
                        for i in range(len(existing)):
                            sy = oy + i * SLOT_H
                            if sy <= y <= sy + SLOT_H:
                                return i
                        return None

                    def _animate_eject(idx):
                        if idx < 0 or idx >= len(existing):
                            return
                        _mag_state['animating'] = True
                        oy = MAG_TOP
                        r = existing[idx]
                        vn = (r.get("variant") or r.get("name") or "Unknown") if isinstance(r, dict) else "Unknown"
                        c = vcols_ins.get(vn, "#c4a032")
                        sy = oy + idx * SLOT_H
                        _pri = insp_canvas.create_rectangle(
                            ox_m + 2, sy + 2, ox_m + SLOT_W - 2, sy + SLOT_H - 2,
                            fill = c, outline = "#ffffff", width = 2, tags = "popanim"
                        )
                        _poi = insp_canvas.create_oval(
                            ox_m + 4, sy + 4, ox_m + 22, sy + SLOT_H - 4,
                            fill = _utip_r(r), outline = _utip_ol_r(r), tags = "popanim"
                        )
                        _pti = insp_canvas.create_text(
                            ox_m + SLOT_W // 2 + 10, sy + SLOT_H // 2,
                            text = vn, fill = "#1a1a1a",
                            font = ("Consolas", 9, "bold"), tags = "popanim"
                        )
                        target_y = oy - SLOT_H - 10
                        steps = 8
                        def _step(s):
                            if s >= steps:
                                insp_canvas.delete("popanim")
                                _mag_state['animating'] = False
                                _eject_round(idx)
                                return
                            frac = (s + 1) / steps
                            ny = sy + (target_y - sy) * frac * frac
                            insp_canvas.coords(_pri, ox_m + 2, ny + 2, ox_m + SLOT_W - 2, ny + SLOT_H - 2)
                            insp_canvas.coords(_poi, ox_m + 4, ny + 4, ox_m + 22, ny + SLOT_H - 4)
                            insp_canvas.coords(_pti, ox_m + SLOT_W // 2 + 10, ny + SLOT_H // 2)
                            popup.after(20, lambda: _step(s + 1))
                        _step(0)

                    def _on_canvas_click(event):
                        if _mag_state['animating']:
                            return
                        idx = _hit_slot(event.x, event.y)
                        if idx is not None:
                            _animate_eject(idx)

                    insp_canvas.bind("<Button-1>", _on_canvas_click)
                    _draw_mag_canvas()

            _build_mag_view()

            # ── ATTACHMENTS tab ───────────────────────────────────────────────
            attach_frame = customtkinter.CTkScrollableFrame(tab_attach, fg_color = "transparent")
            attach_frame.pack(fill = "both", expand = True, padx = 4, pady = 4)

            accessories = gun.get("accessories") or []
            if not accessories:
                customtkinter.CTkLabel(attach_frame, text = "No attachment slots.",
                                       text_color = "#888888").pack(pady = 20)
            else:
                for acc in accessories:
                    if not isinstance(acc, dict):
                        continue
                    slot_name = (acc.get("name") or acc.get("slot") or "Slot").replace("_", " ").title()
                    cur_attach = acc.get("current")
                    if isinstance(cur_attach, dict) and "id" in cur_attach and "name" not in cur_attach:
                        cur_attach = _resolve_cur({"current": cur_attach}) or cur_attach

                    row = customtkinter.CTkFrame(attach_frame)
                    row.pack(fill = "x", padx = 4, pady = 3)
                    row.grid_columnconfigure(1, weight = 1)

                    customtkinter.CTkLabel(
                        row, text = slot_name,
                        font = customtkinter.CTkFont(size = 11, weight = "bold"),
                        width = 150, anchor = "w"
                    ).grid(row = 0, column = 0, padx = (8, 4), pady = 4, sticky = "w")

                    if cur_attach and isinstance(cur_attach, dict):
                        attach_name = cur_attach.get("name", "Unknown Attachment")
                        attach_desc = cur_attach.get("description", "")
                        customtkinter.CTkLabel(
                            row, text = attach_name,
                            font = customtkinter.CTkFont(size = 11),
                            anchor = "w"
                        ).grid(row = 0, column = 1, padx = 4, pady = 4, sticky = "w")
                        if attach_desc:
                            customtkinter.CTkLabel(
                                row, text = attach_desc,
                                font = customtkinter.CTkFont(size = 9),
                                text_color = "#888888",
                                wraplength = 260, anchor = "w"
                            ).grid(row = 1, column = 1, padx = (4, 8), sticky = "w")
                    else:
                        customtkinter.CTkLabel(
                            row, text = "Empty",
                            font = customtkinter.CTkFont(size = 11),
                            text_color = "#555555", anchor = "w"
                        ).grid(row = 0, column = 1, padx = 4, pady = 4, sticky = "w")

            customtkinter.CTkButton(
                popup, text = "Close", command = popup.destroy, width = 100
            ).pack(pady = (0, 8))

        # ── item rows ──────────────────────────────────────────────────────────
        for i, item in enumerate(available_items):
            item_frame = customtkinter.CTkFrame(scroll_frame)
            item_frame.pack(fill = "x", pady = 10, padx = 10)
            item_frame.grid_columnconfigure(1, weight = 1)

            checkbox = customtkinter.CTkCheckBox(
            item_frame,
            text = "",
            command = update_weight_display
            )
            checkbox.grid(row = 0, column = 0, sticky = "w", padx =(0, 10))
            checkbox.select()
            selected_items_checkboxes[i]= checkbox

            item_info_text = f"{self._format_item_name(item)} - {self._format_weight(item.get('weight', 0))}"
            if item.get("quantity", 1)>1:
                item_info_text +=f" x{item.get('quantity')}"
            if item.get("value"):
                item_info_text +=f"[{format_price(item.get('value'))}]"

            item_label = customtkinter.CTkLabel(
            item_frame,
            text = item_info_text,
            font = customtkinter.CTkFont(size = 12),
            anchor = "w"
            )
            item_label.grid(row = 0, column = 1, sticky = "ew", padx = 10)

            if item.get("firearm"):
                _inspect_item = item
                customtkinter.CTkButton(
                    item_frame,
                    text = "Inspect",
                    width = 72,
                    height = 26,
                    font = customtkinter.CTkFont(size = 11),
                    fg_color = "#2a3a4a",
                    hover_color = "#3a5a6a",
                    command = lambda g = _inspect_item: _open_firearm_inspect(g)
                ).grid(row = 0, column = 2, padx = (4, 6), sticky = "e")

            if item.get("description"):
                desc_label = customtkinter.CTkLabel(
                item_frame,
                text = item.get("description"),
                font = customtkinter.CTkFont(size = 10),
                text_color = "gray",
                wraplength = 600,
                justify = "left",
                anchor = "w"
                )
                desc_label.grid(row = 1, column = 0, columnspan = 3, sticky = "ew", padx = 10, pady =(5, 0))

        weight_frame = customtkinter.CTkFrame(main_frame)
        weight_frame.pack(fill = "x", padx = 20, pady = 10)

        weight_label = customtkinter.CTkLabel(
        weight_frame,
        text = "",
        font = customtkinter.CTkFont(size = 12),
        justify = "left",
        anchor = "w"
        )
        weight_label.pack(fill = "x", padx = 10, pady = 10)

        button_frame = customtkinter.CTkFrame(main_frame, fg_color = "transparent")
        button_frame.pack(fill = "x", padx = 20, pady = 20)
        button_frame.grid_columnconfigure((0, 1), weight = 1)

        def take_selected():

            try:

                selected_container_name = container_selector.get()
                selected_container = next((c for c in loot_containers if c["name"]==selected_container_name), None)

                if not selected_container:

                    selected_container = {"name":"Hands", "location":"hands"}

                target_location = selected_container["location"]

                items_to_take =[]
                remaining_items =[]

                for idx, checkbox in selected_items_checkboxes.items():
                    if checkbox.get():
                        items_to_take.append(available_items[idx])
                    else:
                        remaining_items.append(available_items[idx])

                if not items_to_take:
                    self._popup_show_info("Info", "No items selected.", sound = "popup")
                    return

                capacity = get_container_capacity_local(target_location)
                if capacity is not None:
                    current_items = get_container_items_local(target_location)
                    current_weight = sum(
                    it.get("weight", 0)*it.get("quantity", 1)
                    for it in current_items if isinstance(it, dict)
                    )
                    items_weight = sum(
                    it.get("weight", 0)*it.get("quantity", 1)
                    for it in items_to_take if isinstance(it, dict)
                    )
                    if current_weight +items_weight >capacity:
                        self._popup_show_info(
                        "Capacity Exceeded",
                        f"Selected items({self._format_weight(items_weight)}) would exceed container capacity.\n"
                        f"Current: {self._format_weight(current_weight)} / {self._format_weight(capacity)}",
                        sound = "error"
                        )
                        return

                current_items = get_container_items_local(target_location)
                current_items.extend(items_to_take)
                set_container_items_local(target_location, current_items)

                try:
                    self._write_save_to_path(save_path, save_data)
                except Exception as e:
                    logging.error(f"Failed to write updated save: {e}")

                if crate_file_path and os.path.exists(crate_file_path):
                    if remaining_items:

                        updated_crate = crate.copy()
                        updated_crate["generated_items"]= remaining_items
                        updated_crate.pop("loot_table", None)

                        _signed_json_write(crate_file_path, updated_crate, portable = True)
                        logging.info(f"Updated crate file with {len(remaining_items)} remaining items: {crate_file_path}")
                    else:

                        os.remove(crate_file_path)
                        logging.info(f"Deleted empty loot crate file: {crate_file_path}")

                item_summary = ", ".join([f"{self._format_item_name(item)}"for item in items_to_take])
                logging.info(f"Looted crate '{crate.get('name')}' into {selected_container_name}: {item_summary}")
                self._popup_show_info("Success", f"Took {len(items_to_take)} item(s) into {selected_container_name}:\n{item_summary}", sound = "success")
                self._open_loot_tool()
            except Exception as e:
                logging.error(f"Failed to take items: {e}")
                self._popup_show_info("Error", f"Failed to take items: {e}", sound = "error")

        def take_none():

            self._open_loot_tool()

        take_button = self._create_sound_button(
        button_frame,
        "Take Selected Items",
        take_selected,
        width = 250,
        height = 50,
        font = customtkinter.CTkFont(size = 14)
        )
        take_button.grid(row = 0, column = 0, padx =(0, 10))

        cancel_button = self._create_sound_button(
        button_frame,
        "Leave Crate",
        take_none,
        width = 250,
        height = 50,
        font = customtkinter.CTkFont(size = 14)
        )
        cancel_button.grid(row = 0, column = 1, padx =(10, 0))

        update_weight_display()

    def _resolve_table_id_references(self, table_data):
        import copy as _copy
        if not isinstance(table_data, dict):
            return table_data
        tables = table_data.get('tables', {})
        if not isinstance(tables, dict):
            return table_data

        id_to_item = {}
        for subtable_items in tables.values():
            if not isinstance(subtable_items, list):
                continue
            for it in subtable_items:
                if isinstance(it, dict)and 'id'in it:
                    id_to_item[it['id']]= it

        def _resolve_current(obj):
            if not isinstance(obj, dict):
                return
            for acc in(obj.get('accessories')or[]):
                try:
                    cur = acc.get('current')
                    if cur is None:
                        continue
                    target_id = None
                    sub_attachment = None
                    overrides = {}
                    if isinstance(cur, int):
                        target_id = cur
                    elif isinstance(cur, dict)and 'id'in cur:
                        target_id = cur.get('id')
                        sub_attachment = cur.get('sub_attachment')
                        for k, v in cur.items():
                            if k not in('id', 'sub_attachment'):
                                overrides[k]= v
                    if target_id is None:
                        if isinstance(cur, dict):
                            _resolve_current(cur)
                        continue
                    target = id_to_item.get(target_id)
                    if not target:
                        continue
                    new_installed = _copy.deepcopy(target)
                    for k, v in overrides.items():
                        try:
                            new_installed[k]= v
                        except Exception:
                            logging.exception("Suppressed exception")
                    acc['current']= new_installed
                    if sub_attachment:
                        sub_target = id_to_item.get(sub_attachment)
                        if sub_target and isinstance(new_installed.get('subslots'), list):
                            placed = False
                            for ss in new_installed['subslots']:
                                try:
                                    if ss.get('slot')==sub_target.get('slot')or ss.get('current')is None:
                                        ss['current']= _copy.deepcopy(sub_target)
                                        placed = True
                                        break
                                except Exception:
                                    logging.exception("Suppressed exception")
                            if not placed:
                                try:
                                    new_installed['subslots'][0]['current']= _copy.deepcopy(sub_target)
                                except Exception:
                                    logging.exception("Suppressed exception")
                    try:
                        _resolve_current(new_installed)
                    except Exception:
                        logging.exception("Suppressed exception")
                except Exception:
                    logging.exception("Suppressed exception")
            for s in(obj.get('subslots')or[]):
                try:
                    cur = s.get('current')
                    if cur is None:
                        continue
                    if isinstance(cur, int)or(isinstance(cur, dict)and 'id'in cur):
                        tmp = {'accessories':[{'current':cur}]}
                        _resolve_current(tmp)
                        try:
                            s['current']= tmp['accessories'][0].get('current')
                        except Exception:
                            logging.exception("Suppressed exception")
                    elif isinstance(cur, dict):
                        _resolve_current(cur)
                except Exception:
                    logging.exception("Suppressed exception")
            for p in(obj.get('parts')or[]):
                try:
                    if not isinstance(p, dict):
                        continue
                    cur = p.get('current')
                    if cur is None:
                        continue
                    target_id = None
                    overrides = {}
                    if isinstance(cur, int):
                        target_id = cur
                    elif isinstance(cur, dict)and 'id'in cur and 'name'not in cur:
                        target_id = cur.get('id')
                        for k, v in cur.items():
                            if k != 'id':
                                overrides[k]= v
                    if target_id is None:
                        continue
                    target = id_to_item.get(target_id)
                    if not target:
                        continue
                    new_part = _copy.deepcopy(target)
                    for k, v in overrides.items():
                        try:
                            new_part[k]= v
                        except Exception:
                            logging.exception("Suppressed exception")
                    p['current']= new_part
                except Exception:
                    logging.exception("Suppressed exception")

        for subtable_items in tables.values():
            if not isinstance(subtable_items, list):
                continue
            for item in subtable_items:
                try:
                    _resolve_current(item)
                except Exception:
                    logging.exception("Suppressed exception")

        return table_data

    def _open_enemy_loot_tool(self):

        logging.info("Individual Enemy Loot tool called")

        try:
            tbl_path = get_current_table_path()
            if not tbl_path or not os.path.exists(tbl_path):
                self._popup_show_info("Error", "No table file found.", sound = "error")
                return
            with open(tbl_path, 'r', encoding = 'utf-8-sig')as f:
                table_data = json.load(f)
        except Exception as e:
            logging.error(f"Failed to load table: {e}")
            self._popup_show_info("Error", f"Failed to load table: {e}", sound = "error")
            return

        dm_settings_path = os.path.join(saves_folder or "saves", "dm_settings.sldsv")
        enabled_enemies = {}

        if os.path.exists(dm_settings_path):
            try:
                dm_settings_loaded, _, dm_status = _signed_json_read(dm_settings_path, allow_unsigned = True)
                if isinstance(dm_settings_loaded, dict):
                    enabled_enemies = dm_settings_loaded.get("enabled_enemies", {})
            except Exception as e:
                logging.warning(f"Failed to load DM settings: {e}")

        enemy_list = table_data.get("tables", {}).get("enemy_drops", [])

        available_enemies =[
        enemy for enemy in enemy_list
        if enabled_enemies.get(enemy.get("name"), True)
        ]

        if not available_enemies:
            self._popup_show_info("Error", "No enabled enemies in table.", sound = "error")
            return

        self._clear_window()
        self._play_ui_sound("whoosh1")

        main_frame = customtkinter.CTkScrollableFrame(self.root, fg_color = "transparent")
        main_frame.pack(fill = "both", expand = True, padx = 20, pady = 20)

        title_label = customtkinter.CTkLabel(
        main_frame,
        text = "Individual Enemy Loot",
        font = customtkinter.CTkFont(size = 24, weight = "bold")
        )
        title_label.pack(pady = 20)

        customtkinter.CTkLabel(
        main_frame,
        text = "Select an enemy to generate loot:",
        font = customtkinter.CTkFont(size = 14)
        ).pack(pady = 10)

        for enemy in available_enemies:
            enemy_frame = customtkinter.CTkFrame(main_frame)
            enemy_frame.pack(fill = "x", pady = 5, padx = 20)

            enemy_info = f"{enemy.get('name', 'Unknown')} - {enemy.get('difficulty', 'Unknown')} Difficulty"

            customtkinter.CTkLabel(
            enemy_frame,
            text = enemy_info,
            font = customtkinter.CTkFont(size = 12)
            ).pack(side = "left", padx = 10, pady = 10)

            def generate_loot(e = enemy):
                self._show_enemy_loot_result(e, table_data)

            self._create_sound_button(
            enemy_frame,
            text = "Generate Loot",
            command = generate_loot,
            width = 150
            ).pack(side = "right", padx = 10, pady = 5)

        back_button = self._create_sound_button(
        main_frame,
        text = "Back to DM Tools",
        command = lambda:[self._clear_window(), self._open_dm_tools()],
        width = 300,
        height = 50,
        font = customtkinter.CTkFont(size = 16)
        )
        back_button.pack(pady = 20)

    def _show_enemy_loot_result(self, enemy, table_data):

        loot = self._generate_enemy_loot(enemy, table_data)

        dialog = customtkinter.CTkToplevel(self.root)
        dialog.title(f"Loot: {enemy.get('name', 'Unknown')}")
        dialog.transient(self.root)

        if global_variables.get("devmode", {}).get("value", False):
            self._center_popup_on_window(dialog, 700, 700)
        else:
            self._center_popup_on_window(dialog, 500, 600)
        dialog.grab_set()

        customtkinter.CTkLabel(
        dialog,
        text = f"Generated Loot for {enemy.get('name', 'Unknown')}",
        font = customtkinter.CTkFont(size = 16, weight = "bold")
        ).pack(pady = 10)

        scroll_frame = customtkinter.CTkScrollableFrame(dialog)
        scroll_frame.pack(fill = "both", expand = True, padx = 20, pady = 10)

        if global_variables.get("devmode", {}).get("value", False)and loot:
            debug_summary = loot[0].get("_loot_debug_summary", "")
            if debug_summary:
                debug_frame = customtkinter.CTkFrame(scroll_frame, fg_color = "#1a1a2e")
                debug_frame.pack(fill = "x", pady =(0, 15), padx = 5)

                customtkinter.CTkLabel(
                debug_frame,
                text = "🔧 DEBUG INFO",
                font = customtkinter.CTkFont(size = 12, weight = "bold"),
                text_color = "#00ff88"
                ).pack(anchor = "w", padx = 10, pady =(10, 5))

                debug_text = customtkinter.CTkTextbox(
                debug_frame,
                height = 250,
                font = customtkinter.CTkFont(family = "Consolas", size = 10),
                fg_color = "#0d0d1a",
                text_color = "#88ff88"
                )
                debug_text.pack(fill = "x", padx = 10, pady =(0, 10))
                debug_text.insert("1.0", debug_summary)
                debug_text.configure(state = "disabled")

        if not loot:
            customtkinter.CTkLabel(
            scroll_frame,
            text = "No loot generated",
            font = customtkinter.CTkFont(size = 12)
            ).pack(pady = 20)

            if global_variables.get("devmode", {}).get("value", False):
                customtkinter.CTkLabel(
                scroll_frame,
                text = "(Check logs for debug details)",
                font = customtkinter.CTkFont(size = 10),
                text_color = "gray"
                ).pack()
        else:
            customtkinter.CTkLabel(
            scroll_frame,
            text = "Generated Items:",
            font = customtkinter.CTkFont(size = 14, weight = "bold")
            ).pack(anchor = "w", padx = 10, pady =(10, 5))

            for item in loot:
                item_text = item.get('name', 'Unknown Item')
                if item.get("quantity", 1)>1:
                    item_text +=f" x{item['quantity']}"

                rarity = item.get('rarity', 'Common')
                rarity_colors = {
                'Common':'white',
                'Uncommon':'#00ff00',
                'Rare':'#0088ff',
                'Epic':'#aa00ff',
                'Legendary':'#ffaa00',
                'Special':'#ff0088'
                }
                text_color = rarity_colors.get(rarity, 'white')

                customtkinter.CTkLabel(
                scroll_frame,
                text = f"• {item_text}[{rarity}]",
                font = customtkinter.CTkFont(size = 12),
                text_color = text_color
                ).pack(anchor = "w", padx = 10, pady = 2)

        def save_loot():
            self._save_enemy_loot_transfer(enemy.get("name"), loot)
            dialog.destroy()

        self._create_sound_button(
        dialog,
        text = "Save as Enemy Loot Transfer",
        command = save_loot,
        width = 250
        ).pack(pady = 10)

        self._create_sound_button(
        dialog,
        text = "Close",
        command = dialog.destroy,
        fg_color = "#8B0000",
        width = 250
        ).pack(pady = 10)

    def _generate_enemy_loot(self, enemy, table_data):

        loot =[]
        debug_lines =[]

        if global_variables.get("devmode", {}).get("value", False):
            debug_lines.append(f"═══ ENEMY LOOT GENERATION DEBUG ═══")
            debug_lines.append(f"Enemy: {enemy.get('name', 'Unknown')}")
            debug_lines.append(f"Difficulty: {enemy.get('difficulty', 'Unknown')}")
            debug_lines.append(f"Total loot entries: {len(enemy.get('items', []))}")
            debug_lines.append("")

        rarity_weights = table_data.get("rarity_weights", {})

        for idx, loot_entry in enumerate(enemy.get("items", [])):

            entry_debug =[]
            if global_variables.get("devmode", {}).get("value", False):
                entry_debug.append(f"--- Entry #{idx +1} ---")
                entry_debug.append(f" Type: {loot_entry.get('type', 'Unknown')}")
                if loot_entry.get('type')=='table':
                    entry_debug.append(f" Table: {loot_entry.get('table', 'Unknown')}")
                elif loot_entry.get('type')=='id':
                    entry_debug.append(f" Item ID: {loot_entry.get('id', 'Unknown')}")
                entry_debug.append(f" Rarity filter: {loot_entry.get('rarity', 'Any')}")
                entry_debug.append(f" Guaranteed: {loot_entry.get('guaranteed', False)}")

            if loot_entry.get("guaranteed"):
                should_drop = True
                if global_variables.get("devmode", {}).get("value", False):
                    entry_debug.append(f" Drop result: ✓ GUARANTEED")
            else:

                rarity = loot_entry.get("rarity", "Common")
                drop_chance = rarity_weights.get(rarity, 50)/100.0
                roll = random.random()
                should_drop = roll <drop_chance

                if global_variables.get("devmode", {}).get("value", False):
                    entry_debug.append(f" Drop chance for '{rarity}': {drop_chance *100:.1f}%")
                    entry_debug.append(f" Roll: {roll *100:.2f}%")
                    entry_debug.append(f" Drop result: {'✓ SUCCESS'if should_drop else '✗ FAILED'}")

            if should_drop:
                item = self._resolve_loot_entry(loot_entry, table_data)
                if item:

                    if isinstance(item, list):
                        for it in item:
                            if global_variables.get("devmode", {}).get("value", False):
                                entry_debug.append(f" → Resolved: {it.get('name', 'Unknown')}({it.get('rarity', 'Unknown')})")

                                if it.get("_debug_info"):
                                    entry_debug.append(f"[Resolution details]\n{it.get('_debug_info')}")
                        loot.extend(item)
                    else:
                        if global_variables.get("devmode", {}).get("value", False):
                            entry_debug.append(f" → Resolved: {self._format_item_name(item)}({item.get('rarity', 'Unknown')})")
                        loot.append(item)

            if global_variables.get("devmode", {}).get("value", False):
                debug_lines.extend(entry_debug)
                debug_lines.append("")

        special_chance = rarity_weights.get("Special Chance", 0)
        special_roll = random.random()*100

        if global_variables.get("devmode", {}).get("value", False):
            debug_lines.append(f"--- Special Item Roll ---")
            debug_lines.append(f" Special chance: {special_chance}%")
            debug_lines.append(f" Roll: {special_roll:.2f}")

        if special_roll <special_chance:
            special_table = table_data.get("tables", {}).get("special_items", [])
            if special_table:
                selected_special = random.choice(special_table)
                special_copy = selected_special.copy()
                special_copy["table_category"]= "special_items"
                loot.append(special_copy)

                if global_variables.get("devmode", {}).get("value", False):
                    debug_lines.append(f" ★ SPECIAL ITEM TRIGGERED! Selected: {selected_special.get('name', 'Unknown')}")
            else:
                if global_variables.get("devmode", {}).get("value", False):
                    debug_lines.append(f" Special roll succeeded but no special_items table found")
        else:
            if global_variables.get("devmode", {}).get("value", False):
                debug_lines.append(f" No special item(needed < {special_chance})")

        if global_variables.get("devmode", {}).get("value", False):
            debug_lines.append("")
            debug_lines.append(f"═══ FINAL RESULT: {len(loot)} item(s) ═══")
            for it in loot:
                debug_lines.append(f" • {it.get('name', 'Unknown')}({it.get('rarity', 'Unknown')})")

            logging.debug("\n".join(debug_lines))

            if loot:
                loot[0]["_loot_debug_summary"]= "\n".join(debug_lines)

        return loot

    def _generate_lootcrate_contents(self, lootcrate_def, table_data):

        try:
            loot =[]
            pulls_config = lootcrate_def.get("pulls", {"min":1, "max":3})
            num_pulls = random.randint(pulls_config.get("min", 1), pulls_config.get("max", 3))

            loot_table = lootcrate_def.get("loot_table", [])
            if not loot_table:
                return loot

            for _ in range(num_pulls):

                loot_entry = random.choice(loot_table)

                item = self._resolve_loot_entry(loot_entry, table_data)
                if item:
                    if isinstance(item, list):
                        loot.extend(item)
                    else:
                        loot.append(item)

            return loot

        except Exception as e:
            logging.error(f"Failed to generate lootcrate contents: {e}")
            return[]

    def _open_create_lootcrate_tool(self):
        logging.info("Create Loot Crate tool called")
        self._clear_window()

        self.root.grid_rowconfigure(0, weight = 1)
        self.root.grid_columnconfigure(0, weight = 1)

        main_frame = customtkinter.CTkFrame(self.root)
        main_frame.grid(row = 0, column = 0, sticky = "nsew")

        title_label = customtkinter.CTkLabel(main_frame, text = "Create Lootcrate", font = customtkinter.CTkFont(size = 24, weight = "bold"))
        title_label.pack(pady = 20)

        create_scratch_btn = self._create_sound_button(main_frame, "Create from Scratch", self._open_create_lootcrate_from_scratch, width = 800, height = 60, font = customtkinter.CTkFont(size = 16))
        create_scratch_btn.pack(pady = 10, padx = 20)

        create_preset_btn = self._create_sound_button(main_frame, "Create from Preset", self._open_create_lootcrate_from_preset, width = 800, height = 60, font = customtkinter.CTkFont(size = 16))
        create_preset_btn.pack(pady = 10, padx = 20)

        back_button = self._create_sound_button(main_frame, "Back to DM Tools", lambda:[self._clear_window(), self._open_dm_tools()], width = 500, height = 50, font = customtkinter.CTkFont(size = 16))
        back_button.pack(pady = 20)

    def _open_create_lootcrate_from_preset(self):
        logging.info("Create Loot Crate from Preset called")
        self._clear_window()

        self.root.grid_rowconfigure(0, weight = 1)
        self.root.grid_columnconfigure(0, weight = 1)

        main_frame = customtkinter.CTkScrollableFrame(self.root)
        main_frame.grid(row = 0, column = 0, sticky = "nsew")

        title_label = customtkinter.CTkLabel(main_frame, text = "Create Lootcrate from Preset", font = customtkinter.CTkFont(size = 24, weight = "bold"))
        title_label.pack(pady = 20)

        try:
            tbl_path = get_current_table_path()
            if not tbl_path or not os.path.exists(tbl_path):
                self._popup_show_info("Error", "No table files found.", sound = "error")
                return
            with open(tbl_path, 'r', encoding = 'utf-8-sig')as f:
                table_data = json.load(f)
        except Exception as e:
            logging.error(f"Failed to load tables for loot crate creator: {e}")
            self._popup_show_info("Error", f"Failed to load tables: {e}", sound = "error")
            return

        def generate_crate_from_preset(crate):

            try:
                crate_copy = json.loads(json.dumps(crate))
                crate_copy.pop("_source_file", None)
                crate_copy.pop("_file_path", None)
                crate_copy["generated_at"]= datetime.now().isoformat()
                os.makedirs("lootcrates", exist_ok = True)
                filename = os.path.join(
                "lootcrates",
                f"lootcrate_{datetime.now().strftime('%Y%m%d_%H%M%S')}{global_variables['lootcrate_extension']}"
                )
                encoded_data = json.dumps(crate_copy, ensure_ascii = False)
                _signed_json_write(filename, crate_copy, portable = True)
                self._popup_show_info("Success", f"Generated loot crate '{crate.get('name', 'Loot Crate')}'.", sound = "success")
                logging.info(f"Generated loot crate file: {filename}")
            except Exception as e:
                logging.error(f"Failed to generate loot crate: {e}")
                self._popup_show_info("Error", f"Failed to generate loot crate: {e}", sound = "error")

        def render_preset(crate, parent_frame):

            row = customtkinter.CTkFrame(parent_frame)
            row.pack(fill = "x", padx = 5, pady = 4)
            row.grid_columnconfigure(0, weight = 1)

            name = crate.get("name", "Loot Crate")
            desc = crate.get("description", "")

            title = customtkinter.CTkLabel(row, text = name, font = customtkinter.CTkFont(size = 14, weight = "bold"), anchor = "w")
            title.grid(row = 0, column = 0, sticky = "w", padx = 4, pady =(2, 0))

            if desc:
                desc_label = customtkinter.CTkLabel(row, text = desc, font = customtkinter.CTkFont(size = 11), text_color = "gray", justify = "left", anchor = "w", wraplength = 600)
                desc_label.grid(row = 1, column = 0, sticky = "w", padx = 4, pady =(0, 2))

            preview = self._get_loot_crate_contents_preview(crate, table_data)
            if preview:
                preview_label = customtkinter.CTkLabel(row, text = preview, font = customtkinter.CTkFont(size = 10), text_color = "orange", justify = "left", anchor = "w", wraplength = 600)
                preview_label.grid(row = 2, column = 0, sticky = "w", padx = 4, pady =(0, 4))

            create_btn = self._create_sound_button(row, "Create", lambda c = crate:generate_crate_from_preset(c), width = 130, height = 35, font = customtkinter.CTkFont(size = 12))
            create_btn.grid(row = 0, column = 1, rowspan = 3, sticky = "e", padx = 10, pady = 6)

        presets_from_table = table_data.get("tables", {}).get("lootcrates", [])

        os.makedirs(os.path.join("lootcrates", "presets"), exist_ok = True)
        preset_files = glob.glob(os.path.join("lootcrates", "presets", f"*{global_variables['lootcrate_extension']}"))
        presets_from_folder =[]
        for pf in preset_files:
            try:
                pdata, _, p_status = _signed_json_read(pf, allow_unsigned = False, portable = True)
                if p_status == "tampered":
                    logging.warning(f"Preset file '{pf}' has been tampered with \u2014 signature verification failed. Skipping.")
                    continue
                elif p_status in ("unsigned", "incompatible_format"):
                    logging.warning(f"Preset file '{pf}' is unsigned or incompatible. Download and run convert_legacy_saves.py from github and run with --resign flag to convert.")
                    continue
                elif pdata is None:
                    logging.warning(f"Preset file '{pf}' could not be loaded. Skipping.")
                    continue
                pdata["_source_file"]= pf
                presets_from_folder.append(pdata)
            except Exception as e:
                logging.warning(f"Failed to load preset file {pf}: {e}")

        all_presets = presets_from_table +presets_from_folder
        if all_presets:
            for crate in all_presets:
                render_preset(crate, main_frame)
        else:
            no_presets_label = customtkinter.CTkLabel(main_frame, text = "No presets available.", font = customtkinter.CTkFont(size = 14), text_color = "gray")
            no_presets_label.pack(pady = 20)

        back_button = self._create_sound_button(main_frame, "Back", self._open_create_lootcrate_tool, width = 500, height = 50, font = customtkinter.CTkFont(size = 16))
        back_button.pack(pady = 20)

    def _open_create_lootcrate_from_scratch(self):
        logging.info("Create Loot Crate from Scratch called")
        self._clear_window()

        try:
            tbl_path = get_current_table_path()
            if not tbl_path or not os.path.exists(tbl_path):
                self._popup_show_info("Error", "No table files found.", sound = "error")
                return
            with open(tbl_path, 'r', encoding = 'utf-8-sig')as f:
                table_data = json.load(f)
        except Exception as e:
            logging.error(f"Failed to load tables for loot crate creator: {e}")
            self._popup_show_info("Error", f"Failed to load tables: {e}", sound = "error")
            return

        excluded_tables = {"lootcrates", "special_items", "enemy_drops"}
        all_items =[]
        for table_name, items in table_data.get("tables", {}).items():
            if table_name in excluded_tables:
                continue
            if not isinstance(items, list):
                continue
            for item in items:
                if not isinstance(item, dict)or item.get("id")is None:
                    continue
                item_copy = item.copy()
                item_copy["table_category"]= table_name
                all_items.append(item_copy)

        all_items.sort(key = lambda x:x.get("id", 999999))

        self.root.grid_rowconfigure(0, weight = 1)
        self.root.grid_columnconfigure(0, weight = 1)

        main_frame = customtkinter.CTkFrame(self.root)
        main_frame.grid(row = 0, column = 0, sticky = "nsew", padx = 10, pady = 10)
        main_frame.grid_rowconfigure(2, weight = 1)
        main_frame.grid_columnconfigure(0, weight = 1)
        main_frame.grid_columnconfigure(1, weight = 0)

        title_label = customtkinter.CTkLabel(main_frame, text = "Create Lootcrate from Scratch", font = customtkinter.CTkFont(size = 24, weight = "bold"))
        title_label.grid(row = 0, column = 0, columnspan = 2, pady =(0, 10))

        meta_frame = customtkinter.CTkFrame(main_frame)
        meta_frame.grid(row = 1, column = 0, columnspan = 2, sticky = "ew", padx = 10, pady = 10)
        meta_frame.grid_columnconfigure(1, weight = 1)
        meta_frame.grid_columnconfigure(3, weight = 1)

        name_label = customtkinter.CTkLabel(meta_frame, text = "Name:")
        name_label.grid(row = 0, column = 0, padx = 5, pady = 5, sticky = "w")
        name_entry = customtkinter.CTkEntry(meta_frame, placeholder_text = "Loot Crate Name", width = 200)
        name_entry.grid(row = 0, column = 1, padx = 5, pady = 5, sticky = "w")

        desc_label = customtkinter.CTkLabel(meta_frame, text = "Description:")
        desc_label.grid(row = 0, column = 2, padx =(20, 5), pady = 5, sticky = "w")
        desc_entry = customtkinter.CTkEntry(meta_frame, placeholder_text = "Optional description", width = 300)
        desc_entry.grid(row = 0, column = 3, padx = 5, pady = 5, sticky = "ew")

        locked_var = customtkinter.BooleanVar(value = False)
        locked_check = customtkinter.CTkCheckBox(meta_frame, text = "Locked(requires lockpicking)", variable = locked_var)
        locked_check.grid(row = 1, column = 0, columnspan = 2, padx = 5, pady = 5, sticky = "w")

        pulls_label = customtkinter.CTkLabel(meta_frame, text = "Pulls:")
        pulls_label.grid(row = 1, column = 2, padx =(20, 5), pady = 5, sticky = "w")

        pulls_frame = customtkinter.CTkFrame(meta_frame, fg_color = "transparent")
        pulls_frame.grid(row = 1, column = 3, padx = 5, pady = 5, sticky = "w")

        pulls_min_entry = customtkinter.CTkEntry(pulls_frame, placeholder_text = "Min", width = 60)
        pulls_min_entry.pack(side = "left", padx = 2)
        pulls_min_entry.insert(0, "3")

        pulls_dash = customtkinter.CTkLabel(pulls_frame, text = "-")
        pulls_dash.pack(side = "left", padx = 2)

        pulls_max_entry = customtkinter.CTkEntry(pulls_frame, placeholder_text = "Max", width = 60)
        pulls_max_entry.pack(side = "left", padx = 2)
        pulls_max_entry.insert(0, "3")

        pulls_hint = customtkinter.CTkLabel(pulls_frame, text = "(same for fixed)", font = customtkinter.CTkFont(size = 10), text_color = "gray")
        pulls_hint.pack(side = "left", padx = 5)

        content_frame = customtkinter.CTkFrame(main_frame, fg_color = "transparent")
        content_frame.grid(row = 2, column = 0, columnspan = 2, sticky = "nsew", pady = 10)
        content_frame.grid_rowconfigure(0, weight = 1)
        content_frame.grid_columnconfigure(0, weight = 1)
        content_frame.grid_columnconfigure(1, weight = 0)

        left_frame = customtkinter.CTkFrame(content_frame)
        left_frame.grid(row = 0, column = 0, sticky = "nsew", padx =(0, 5))
        left_frame.grid_rowconfigure(2, weight = 1)
        left_frame.grid_columnconfigure(0, weight = 1)

        search_frame = customtkinter.CTkFrame(left_frame, fg_color = "transparent")
        search_frame.grid(row = 0, column = 0, sticky = "ew", padx = 10, pady = 5)
        search_frame.grid_columnconfigure(1, weight = 1)

        search_label = customtkinter.CTkLabel(search_frame, text = "Search(ID or Name):", font = customtkinter.CTkFont(size = 12))
        search_label.grid(row = 0, column = 0, padx =(0, 10), sticky = "w")

        search_entry = customtkinter.CTkEntry(search_frame, placeholder_text = "Enter item ID or name...", width = 250)
        search_entry.grid(row = 0, column = 1, sticky = "ew", padx =(0, 10))

        ITEMS_PER_PAGE = 20
        current_page =[0]
        current_filtered =[all_items]
        search_timer =[None]

        info_label = customtkinter.CTkLabel(search_frame, text = f"Page 1 | {len(all_items)} items", font = customtkinter.CTkFont(size = 10), text_color = "gray")
        info_label.grid(row = 0, column = 2, padx = 5)

        table_filter_frame = customtkinter.CTkFrame(left_frame, fg_color = "transparent")
        table_filter_frame.grid(row = 1, column = 0, sticky = "ew", padx = 10, pady = 5)

        table_filter_label = customtkinter.CTkLabel(table_filter_frame, text = "Filter by table:", font = customtkinter.CTkFont(size = 11))
        table_filter_label.pack(side = "left", padx =(0, 5))

        table_names =["All"]+[t for t in table_data.get("tables", {}).keys()if t not in excluded_tables]
        table_filter_var = customtkinter.StringVar(value = "All")
        table_filter_menu = customtkinter.CTkOptionMenu(table_filter_frame, variable = table_filter_var, values = table_names, width = 150)
        table_filter_menu.pack(side = "left", padx = 5)

        scroll_frame = customtkinter.CTkScrollableFrame(left_frame, width = 550, height = 300)
        scroll_frame.grid(row = 2, column = 0, sticky = "nsew", padx = 5, pady = 5)
        scroll_frame.grid_columnconfigure(0, weight = 1)

        pagination_frame = customtkinter.CTkFrame(left_frame, fg_color = "transparent")
        pagination_frame.grid(row = 3, column = 0, pady = 5)

        right_frame = customtkinter.CTkFrame(content_frame)
        right_frame.grid(row = 0, column = 1, sticky = "nsew", padx =(5, 0))
        right_frame.grid_rowconfigure(1, weight = 1)

        loot_label = customtkinter.CTkLabel(right_frame, text = "Loot Table Entries", font = customtkinter.CTkFont(size = 14, weight = "bold"))
        loot_label.pack(pady = 10)

        loot_count_label = customtkinter.CTkLabel(right_frame, text = "0 entries", font = customtkinter.CTkFont(size = 11), text_color = "gray")
        loot_count_label.pack(pady = 2)

        loot_scroll = customtkinter.CTkScrollableFrame(right_frame, width = 320, height = 280)
        loot_scroll.pack(fill = "both", expand = True, padx = 5, pady = 5)

        loot_entries =[]

        def update_loot_display():
            for widget in loot_scroll.winfo_children():
                widget.destroy()

            loot_count_label.configure(text = f"{len(loot_entries)} entries")

            for idx, entry in enumerate(loot_entries):
                entry_frame = customtkinter.CTkFrame(loot_scroll)
                entry_frame.pack(fill = "x", pady = 2, padx = 2)

                entry_type = entry.get("type")
                if entry_type =="id":
                    item_id = entry.get("id")
                    item_name = entry.get("_display_name", f"ID: {item_id}")
                    rarity = entry.get("rarity", "")
                    rarity_text = f"({rarity})"if rarity else ""
                    text = f"📦 {item_name}{rarity_text}"
                elif entry_type =="table":
                    table_name = entry.get("table", "Unknown")
                    rarity = entry.get("rarity", "Any")
                    text = f"🎲 Random from '{table_name}'({rarity})"
                else:
                    text = f"? Unknown entry type"

                entry_label = customtkinter.CTkLabel(
                entry_frame,
                text = text,
                font = customtkinter.CTkFont(size = 11),
                anchor = "w",
                wraplength = 250
                )
                entry_label.pack(side = "left", fill = "x", expand = True, padx = 5, pady = 4)

                remove_btn = customtkinter.CTkButton(
                entry_frame,
                text = "X",
                width = 25,
                height = 25,
                font = customtkinter.CTkFont(size = 10),
                fg_color = "darkred",
                hover_color = "red",
                command = lambda i = idx:remove_entry(i)
                )
                remove_btn.pack(side = "right", padx = 2, pady = 2)

        def remove_entry(index):
            if 0 <=index <len(loot_entries):
                loot_entries.pop(index)
                update_loot_display()

        def show_add_item_popup(item):
            self._play_ui_sound("popup")
            popup = customtkinter.CTkToplevel(self.root)
            popup.title("Add Item to Loot Table")
            popup.transient(self.root)
            popup.grab_set()

            item_name = self._format_item_name(item)
            item_rarity = item.get("rarity", "Common")

            title_label = customtkinter.CTkLabel(popup, text = f"Add: {item_name}", font = customtkinter.CTkFont(size = 14, weight = "bold"))
            title_label.pack(pady =(15, 5))

            info_label = customtkinter.CTkLabel(popup, text = f"Item's inherent rarity: {item_rarity}", font = customtkinter.CTkFont(size = 11), text_color = "gray")
            info_label.pack(pady =(0, 10))

            rarity_weights = table_data.get("rarity_weights", {})
            non_rarity_keys = {"Luck Effect", "Special Chance"}
            rarity_options =[k for k in rarity_weights.keys()if k not in non_rarity_keys]
            default_loot_rarity = "Common"if "Common"in rarity_options else (rarity_options[0]if rarity_options else "Common")

            total_weight = sum(rarity_weights.get(r, 1)for r in rarity_options)

            rarity_frame = customtkinter.CTkFrame(popup)
            rarity_frame.pack(fill = "x", padx = 20, pady = 10)

            rarity_label = customtkinter.CTkLabel(rarity_frame, text = "Select pull rarity(affects drop chance):", font = customtkinter.CTkFont(size = 12))
            rarity_label.pack(anchor = "w", padx = 10, pady = 5)

            selected_rarity = customtkinter.StringVar(value = default_loot_rarity)

            for rarity in rarity_options:
                weight = rarity_weights.get(rarity, 1)
                percentage =(weight /total_weight *100)if total_weight >0 else 0

                radio_frame = customtkinter.CTkFrame(rarity_frame, fg_color = "transparent")
                radio_frame.pack(fill = "x", padx = 10, pady = 2)

                radio = customtkinter.CTkRadioButton(
                radio_frame,
                text = f"{rarity}",
                variable = selected_rarity,
                value = rarity,
                font = customtkinter.CTkFont(size = 12)
                )
                radio.pack(side = "left")

                pct_label = customtkinter.CTkLabel(
                radio_frame,
                text = f"({percentage:.1f}% chance)",
                font = customtkinter.CTkFont(size = 10),
                text_color = "orange"if rarity ==default_loot_rarity else "gray"
                )
                pct_label.pack(side = "left", padx = 10)

                if rarity ==default_loot_rarity:
                    default_label = customtkinter.CTkLabel(
                    radio_frame,
                    text = "← default looting rarity",
                    font = customtkinter.CTkFont(size = 10),
                    text_color = "green"
                    )
                    default_label.pack(side = "left")
                elif rarity ==item_rarity:
                    inherent_label = customtkinter.CTkLabel(
                    radio_frame,
                    text = "← item rarity",
                    font = customtkinter.CTkFont(size = 10),
                    text_color = "gray"
                    )
                    inherent_label.pack(side = "left")

            hint_label = customtkinter.CTkLabel(popup, text = "Higher rarity = lower weight = rarer drop", font = customtkinter.CTkFont(size = 10), text_color = "gray")
            hint_label.pack(pady = 5)

            button_frame = customtkinter.CTkFrame(popup, fg_color = "transparent")
            button_frame.pack(pady = 15)

            def confirm_add():
                self._play_ui_sound("click")
                entry = {
                "type":"id",
                "id":item.get("id"),
                "rarity":selected_rarity.get(),
                "_display_name":item.get("name", "Unknown")
                }
                loot_entries.append(entry)
                update_loot_display()
                popup.destroy()

            def cancel_add():
                self._play_ui_sound("click")
                popup.destroy()

            add_btn = customtkinter.CTkButton(button_frame, text = "Add Item", command = confirm_add, width = 120, height = 35)
            add_btn.pack(side = "left", padx = 10)

            cancel_btn = customtkinter.CTkButton(button_frame, text = "Cancel", command = cancel_add, width = 120, height = 35)
            cancel_btn.pack(side = "left", padx = 10)

            popup.update_idletasks()
            width = max(420, popup.winfo_reqwidth()+40)
            height = popup.winfo_reqheight()+20
            self._center_popup_on_window(popup, width, height)
            popup.deiconify()
            popup.lift()

        def add_item_entry(item):
            show_add_item_popup(item)

        def add_table_entry(table_name, rarity = "Common"):
            entry = {
            "type":"table",
            "table":table_name,
            "rarity":rarity
            }
            loot_entries.append(entry)
            update_loot_display()

        table_entry_frame = customtkinter.CTkFrame(right_frame)
        table_entry_frame.pack(fill = "x", padx = 5, pady = 5)

        table_entry_label = customtkinter.CTkLabel(table_entry_frame, text = "Add random table entry:", font = customtkinter.CTkFont(size = 11))
        table_entry_label.pack(anchor = "w", padx = 5, pady = 2)

        table_select_frame = customtkinter.CTkFrame(table_entry_frame, fg_color = "transparent")
        table_select_frame.pack(fill = "x", padx = 5, pady = 2)

        avail_tables =[t for t in table_data.get("tables", {}).keys()if t not in excluded_tables]
        table_select_var = customtkinter.StringVar(value = avail_tables[0]if avail_tables else "")
        table_select_menu = customtkinter.CTkOptionMenu(table_select_frame, variable = table_select_var, values = avail_tables, width = 140)
        table_select_menu.pack(side = "left", padx = 2)

        rarity_weights = table_data.get("rarity_weights", {})
        non_rarity_keys = {"Luck Effect", "Special Chance"}
        rarity_options =[k for k in rarity_weights.keys()if k not in non_rarity_keys]
        rarity_select_var = customtkinter.StringVar(value = rarity_options[0]if rarity_options else "Common")
        rarity_select_menu = customtkinter.CTkOptionMenu(table_select_frame, variable = rarity_select_var, values = rarity_options if rarity_options else["Common"], width = 100)
        rarity_select_menu.pack(side = "left", padx = 2)

        add_table_btn = customtkinter.CTkButton(
        table_select_frame,
        text = "+",
        width = 30,
        height = 28,
        command = lambda:add_table_entry(table_select_var.get(), rarity_select_var.get())
        )
        add_table_btn.pack(side = "left", padx = 2)

        clear_btn = customtkinter.CTkButton(
        right_frame,
        text = "Clear All Entries",
        width = 150,
        height = 30,
        fg_color = "darkred",
        hover_color = "red",
        command = lambda:[loot_entries.clear(), update_loot_display()]
        )
        clear_btn.pack(pady = 5)

        def create_item_widget(item):
            item_frame = customtkinter.CTkFrame(scroll_frame)
            item_frame.pack(fill = "x", pady = 2, padx = 3)
            item_frame.grid_columnconfigure(1, weight = 1)

            id_label = customtkinter.CTkLabel(
            item_frame,
            text = f"ID: {item.get('id', 'N/A')}",
            font = customtkinter.CTkFont(size = 11, weight = "bold"),
            width = 70,
            fg_color =("gray75", "gray25"),
            corner_radius = 4
            )
            id_label.grid(row = 0, column = 0, padx = 5, pady = 5, sticky = "w")

            details_frame = customtkinter.CTkFrame(item_frame, fg_color = "transparent")
            details_frame.grid(row = 0, column = 1, sticky = "ew", padx = 5, pady = 5)

            name_label = customtkinter.CTkLabel(
            details_frame,
            text = item.get("name", "Unknown"),
            font = customtkinter.CTkFont(size = 12, weight = "bold"),
            anchor = "w"
            )
            name_label.pack(anchor = "w")

            category_label = customtkinter.CTkLabel(
            details_frame,
            text = f"{item.get('table_category', 'N/A')} | {item.get('rarity', 'N/A')} | {format_price(item.get('value', 0))}",
            font = customtkinter.CTkFont(size = 9),
            text_color = "gray",
            anchor = "w"
            )
            category_label.pack(anchor = "w")

            add_button = self._create_sound_button(
            item_frame,
            "Add",
            lambda it = item:add_item_entry(it),
            width = 60,
            height = 28,
            font = customtkinter.CTkFont(size = 10)
            )
            add_button.grid(row = 0, column = 2, padx = 5, pady = 5)

        def display_page(page_num):
            items = current_filtered[0]
            total_pages = max(1, (len(items)+ITEMS_PER_PAGE -1)//ITEMS_PER_PAGE)

            page_num = max(0, min(page_num, total_pages -1))
            current_page[0]= page_num

            for widget in scroll_frame.winfo_children():
                widget.destroy()

            if not items:
                no_results = customtkinter.CTkLabel(scroll_frame, text = "No items found.", font = customtkinter.CTkFont(size = 12), text_color = "gray")
                no_results.pack(pady = 20)
                info_label.configure(text = "No items found")
                update_pagination_controls(0, 0)
                return

            start_idx = page_num *ITEMS_PER_PAGE
            end_idx = min(start_idx +ITEMS_PER_PAGE, len(items))

            for i in range(start_idx, end_idx):
                create_item_widget(items[i])

            info_label.configure(text = f"Page {page_num +1}/{total_pages} | {len(items)} items")
            update_pagination_controls(page_num, total_pages)

            try:
                scroll_frame._parent_canvas.yview_moveto(0)
            except Exception:
                logging.exception("Suppressed exception")

        def update_pagination_controls(current, total):
            for widget in pagination_frame.winfo_children():
                widget.destroy()

            if total <=1:
                return

            first_btn = customtkinter.CTkButton(
            pagination_frame, text = "<<", width = 35, height = 28,
            command = lambda:display_page(0),
            state = "normal"if current >0 else "disabled"
            )
            first_btn.pack(side = "left", padx = 1)

            prev_btn = customtkinter.CTkButton(
            pagination_frame, text = "<", width = 35, height = 28,
            command = lambda:display_page(current -1),
            state = "normal"if current >0 else "disabled"
            )
            prev_btn.pack(side = "left", padx = 1)

            start_page = max(0, current -2)
            end_page = min(total, start_page +5)
            if end_page -start_page <5:
                start_page = max(0, end_page -5)

            for p in range(start_page, end_page):
                btn = customtkinter.CTkButton(
                pagination_frame,
                text = str(p +1),
                width = 30,
                height = 28,
                fg_color =("gray75", "gray25")if p ==current else None,
                command = lambda page = p:display_page(page)
                )
                btn.pack(side = "left", padx = 1)

            next_btn = customtkinter.CTkButton(
            pagination_frame, text = ">", width = 35, height = 28,
            command = lambda:display_page(current +1),
            state = "normal"if current <total -1 else "disabled"
            )
            next_btn.pack(side = "left", padx = 1)

            last_btn = customtkinter.CTkButton(
            pagination_frame, text = ">>", width = 35, height = 28,
            command = lambda:display_page(total -1),
            state = "normal"if current <total -1 else "disabled"
            )
            last_btn.pack(side = "left", padx = 1)

        def filter_items(*args):
            search_term = search_entry.get().lower().strip()
            table_filter = table_filter_var.get()

            filtered = all_items

            if table_filter !="All":
                filtered =[item for item in filtered if item.get("table_category")==table_filter]

            if search_term:
                filtered =[
                item for item in filtered
                if search_term in str(item.get("id", ""))or search_term in item.get("name", "").lower()
                ]

            current_filtered[0]= filtered
            current_page[0]= 0
            display_page(0)

        def on_search_change(*args):
            if search_timer[0]is not None:
                try:
                    self.root.after_cancel(search_timer[0])
                except Exception:
                    logging.exception("Suppressed exception")
            search_timer[0]= self.root.after(200, filter_items)# type: ignore

        search_entry.bind("<KeyRelease>", on_search_change)
        table_filter_var.trace_add("write", lambda *a:filter_items())

        display_page(0)

        def save_lootcrate(as_preset = False):
            try:
                crate_name = name_entry.get().strip()
                if not crate_name:
                    self._popup_show_info("Error", "Please enter a crate name.", sound = "error")
                    return

                if not loot_entries:
                    self._popup_show_info("Error", "Please add at least one loot entry.", sound = "error")
                    return

                crate_desc = desc_entry.get().strip()
                locked = locked_var.get()

                try:
                    pulls_min = int(pulls_min_entry.get()or 3)
                    pulls_max = int(pulls_max_entry.get()or 3)
                except ValueError:
                    self._popup_show_info("Error", "Pulls must be numbers.", sound = "error")
                    return

                if pulls_min ==pulls_max:
                    pulls = pulls_min
                else:
                    pulls = {"min":min(pulls_min, pulls_max), "max":max(pulls_min, pulls_max)}

                clean_loot_entries =[]
                for entry in loot_entries:
                    clean_entry = {k:v for k, v in entry.items()if not k.startswith("_")}
                    clean_loot_entries.append(clean_entry)

                crate_data = {
                "name":crate_name,
                "description":crate_desc,
                "locked":locked,
                "pulls":pulls,
                "loot_table":clean_loot_entries,
                "created_at":datetime.now().isoformat(),
                "dm_created":True
                }

                if as_preset:
                    os.makedirs(os.path.join("lootcrates", "presets"), exist_ok = True)
                    safe_name = "".join(c if c.isalnum()or c in " _-"else "_"for c in crate_name).strip()
                    filename = os.path.join(
                    "lootcrates", "presets",
                    f"{safe_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}{global_variables['lootcrate_extension']}"
                    )
                else:
                    os.makedirs("lootcrates", exist_ok = True)
                    filename = os.path.join(
                    "lootcrates",
                    f"lootcrate_{datetime.now().strftime('%Y%m%d_%H%M%S')}{global_variables['lootcrate_extension']}"
                    )

                encoded_data = json.dumps(crate_data, ensure_ascii = False)
                _signed_json_write(filename, crate_data, portable = True)

                if as_preset:
                    self._popup_show_info("Success", f"Saved preset '{crate_name}' to presets folder.\nIt will now appear in 'Create from Preset'.", sound = "success")
                    logging.info(f"Saved preset loot crate to {filename}")
                else:
                    self._popup_show_info("Success", f"Generated loot crate '{crate_name}'.", sound = "success")
                    logging.info(f"Generated loot crate file: {filename}")

            except Exception as e:
                logging.error(f"Failed to save loot crate: {e}")
                self._popup_show_info("Error", f"Failed to save loot crate: {e}", sound = "error")

        button_frame = customtkinter.CTkFrame(main_frame, fg_color = "transparent")
        button_frame.grid(row = 3, column = 0, columnspan = 2, pady = 10)

        save_crate_btn = self._create_sound_button(
        button_frame,
        "Save Lootcrate",
        lambda:save_lootcrate(as_preset = False),
        width = 180,
        height = 40,
        font = customtkinter.CTkFont(size = 14)
        )
        save_crate_btn.pack(side = "left", padx = 10)

        save_preset_btn = self._create_sound_button(
        button_frame,
        "Save as Preset",
        lambda:save_lootcrate(as_preset = True),
        width = 180,
        height = 40,
        font = customtkinter.CTkFont(size = 14)
        )
        save_preset_btn.pack(side = "left", padx = 10)

        back_btn = self._create_sound_button(
        button_frame,
        "Back",
        self._open_create_lootcrate_tool,
        width = 120,
        height = 40,
        font = customtkinter.CTkFont(size = 14)
        )
        back_btn.pack(side = "left", padx = 10)
