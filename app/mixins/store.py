"""StoreMixin — App methods for the "store" feature area."""
from app.foundation import *
import logging


class StoreMixin:

    def _open_business_tool(self):
        logging.info("Business tool opened")
        self._clear_window()

        self.root.grid_rowconfigure(0, weight = 1)
        self.root.grid_columnconfigure(0, weight = 1)

        main_frame = customtkinter.CTkFrame(self.root)
        main_frame.grid(row = 0, column = 0, sticky = "nsew")

        title_label = customtkinter.CTkLabel(main_frame, text = "Businesses", font = customtkinter.CTkFont(size = 24, weight = "bold"))
        title_label.pack(pady = 20)

        try:
            current_tbl = global_variables.get('current_table')
            if current_tbl:
                tbl_path = os.path.join("tables", current_tbl)
            else:
                table_files = sorted(glob.glob(os.path.join("tables", "*.sldtbl")))
                if not table_files:
                    self._popup_show_info("Error", "No table files found.", sound = "error")
                    return
                tbl_path = table_files[0]

            if not os.path.exists(tbl_path):
                self._popup_show_info("Error", "Table file not found.", sound = "error")
                return

            with open(tbl_path, 'r', encoding = 'utf-8-sig')as f:
                table_data = json.load(f)

            try:
                self._resolve_table_id_references(table_data)
            except Exception:
                logging.exception("Failed to resolve table ID references for business tool")

            stores = table_data.get("tables", {}).get("stores", [])

            stores =[s for s in stores if s.get("display_in_program", True)]

            if not stores:
                error_label = customtkinter.CTkLabel(main_frame, text = "No businesses available in current table.", font = customtkinter.CTkFont(size = 14), text_color = "orange")
                error_label.pack(pady = 20)
                back_button = self._create_sound_button(main_frame, "Back to Main Menu", lambda:[self._clear_window(), self._build_main_menu()], width = 500, height = 50, font = customtkinter.CTkFont(size = 16))
                back_button.pack(pady = 20)
                return

            scroll_frame = customtkinter.CTkScrollableFrame(main_frame)
            scroll_frame.pack(fill = "both", expand = True, padx = 20, pady = 20)

            armories =[s for s in stores if s.get("type")=="armory"]
            regular_stores =[s for s in stores if s.get("type")=="store"]
            casinos =[s for s in stores if s.get("type")=="casino"]
            ammo_suppliers =[s for s in stores if s.get("type")=="ammo_supplier"]
            gunsmiths =[s for s in stores if s.get("type")=="gunsmith"]

            # Deliver any due orders before showing the UI
            try:
                self._check_and_deliver_orders()
            except Exception:
                logging.exception("Failed to run order delivery check")

            if armories:
                armory_section = customtkinter.CTkLabel(scroll_frame, text = "Armories", font = customtkinter.CTkFont(size = 18, weight = "bold"))
                armory_section.pack(pady =(10, 10), anchor = "w", padx = 10)

                for store in armories:
                    store_frame = customtkinter.CTkFrame(scroll_frame)
                    store_frame.pack(fill = "x", pady = 10, padx = 10)

                    name_label = customtkinter.CTkLabel(store_frame, text = store.get("name", "Unknown Armory"), font = customtkinter.CTkFont(size = 14, weight = "bold"))
                    name_label.pack(anchor = "w", padx = 10, pady =(10, 5))

                    shopkeeper = store.get("shopkeeper", "Unknown")
                    shopkeeper_label = customtkinter.CTkLabel(store_frame, text = f"Quartermaster: {shopkeeper}", font = customtkinter.CTkFont(size = 11), text_color = "gray")
                    shopkeeper_label.pack(anchor = "w", padx = 10)

                    points = store.get("armory_points", "disabled")
                    if points !="disabled":
                        points_label = customtkinter.CTkLabel(store_frame, text = f"Points: {points}(resets at 7 PM CST)", font = customtkinter.CTkFont(size = 11), text_color = "orange")
                        points_label.pack(anchor = "w", padx = 10)
                    else:
                        points_label = customtkinter.CTkLabel(store_frame, text = "Unlimited requisitions", font = customtkinter.CTkFont(size = 11), text_color = "green")
                        points_label.pack(anchor = "w", padx = 10)

                    enter_button = self._create_sound_button(store_frame, "Enter Armory", lambda s = store:self._open_armory_interface(s, table_data), width = 200, height = 40, font = customtkinter.CTkFont(size = 12))
                    enter_button.pack(pady = 10, padx = 10)

            if regular_stores:
                store_section = customtkinter.CTkLabel(scroll_frame, text = "Stores", font = customtkinter.CTkFont(size = 18, weight = "bold"))
                store_section.pack(pady =(20, 10), anchor = "w", padx = 10)

                for store in regular_stores:
                    store_frame = customtkinter.CTkFrame(scroll_frame)
                    store_frame.pack(fill = "x", pady = 10, padx = 10)

                    name_label = customtkinter.CTkLabel(store_frame, text = store.get("name", "Unknown Store"), font = customtkinter.CTkFont(size = 14, weight = "bold"))
                    name_label.pack(anchor = "w", padx = 10, pady =(10, 5))

                    shopkeeper = store.get("shopkeeper", "Unknown")
                    shopkeeper_label = customtkinter.CTkLabel(store_frame, text = f"Shopkeeper: {shopkeeper}", font = customtkinter.CTkFont(size = 11), text_color = "gray")
                    shopkeeper_label.pack(anchor = "w", padx = 10)

                    prices = store.get("prices", {})
                    buy_mult = prices.get("buy", 1.0)
                    sell_mult = prices.get("sell", 1.0)
                    prices_label = customtkinter.CTkLabel(store_frame, text = f"Buy: {buy_mult}x value | Sell: {sell_mult}x value", font = customtkinter.CTkFont(size = 11), text_color = "orange")
                    prices_label.pack(anchor = "w", padx = 10)

                    if store.get("accepts_trades"):
                        trades_label = customtkinter.CTkLabel(store_frame, text = "Accepts trades", font = customtkinter.CTkFont(size = 11), text_color = "green")
                        trades_label.pack(anchor = "w", padx = 10)

                    enter_button = self._create_sound_button(store_frame, "Enter Store", lambda s = store:self._open_store_interface(s, table_data), width = 200, height = 40, font = customtkinter.CTkFont(size = 12))
                    enter_button.pack(pady = 10, padx = 10)

            if casinos:
                casino_section = customtkinter.CTkLabel(scroll_frame, text = "Casinos", font = customtkinter.CTkFont(size = 18, weight = "bold"))
                casino_section.pack(pady =(20, 10), anchor = "w", padx = 10)

                for store in casinos:
                    store_frame = customtkinter.CTkFrame(scroll_frame)
                    store_frame.pack(fill = "x", pady = 10, padx = 10)

                    name_label = customtkinter.CTkLabel(store_frame, text = store.get("name", "Unknown Casino"), font = customtkinter.CTkFont(size = 14, weight = "bold"))
                    name_label.pack(anchor = "w", padx = 10, pady =(10, 5))

                    shopkeeper = store.get("shopkeeper", "Unknown")
                    shopkeeper_label = customtkinter.CTkLabel(store_frame, text = f"Proprietor: {shopkeeper}", font = customtkinter.CTkFont(size = 11), text_color = "gray")
                    shopkeeper_label.pack(anchor = "w", padx = 10)

                    min_bet = store.get("min_bet", 10)
                    max_bet = store.get("max_bet", 1000)
                    bet_label = customtkinter.CTkLabel(store_frame, text = f"Bets: {format_price(min_bet)} - {format_price(max_bet)}", font = customtkinter.CTkFont(size = 11), text_color = "gold")
                    bet_label.pack(anchor = "w", padx = 10)

                    enter_button = self._create_sound_button(store_frame, "Enter Casino", lambda s = store:self._open_casino_interface(s, table_data), width = 200, height = 40, font = customtkinter.CTkFont(size = 12))
                    enter_button.pack(pady = 10, padx = 10)

            if ammo_suppliers:
                ammo_sup_section = customtkinter.CTkLabel(scroll_frame, text = "Ammo Suppliers", font = customtkinter.CTkFont(size = 18, weight = "bold"))
                ammo_sup_section.pack(pady =(20, 10), anchor = "w", padx = 10)

                for store in ammo_suppliers:
                    store_frame = customtkinter.CTkFrame(scroll_frame)
                    store_frame.pack(fill = "x", pady = 10, padx = 10)

                    name_label = customtkinter.CTkLabel(store_frame, text = store.get("name", "Unknown Ammo Supplier"), font = customtkinter.CTkFont(size = 14, weight = "bold"))
                    name_label.pack(anchor = "w", padx = 10, pady =(10, 5))

                    supplier_label = customtkinter.CTkLabel(store_frame, text = f"Supplier: {store.get('shopkeeper', 'Unknown')}", font = customtkinter.CTkFont(size = 11), text_color = "gray")
                    supplier_label.pack(anchor = "w", padx = 10)

                    if store.get("free_ammo"):
                        pricing_label = customtkinter.CTkLabel(store_frame, text = "Ammo is free", font = customtkinter.CTkFont(size = 11), text_color = "#44cc44")
                    else:
                        prices_cfg = store.get("prices", {})
                        sell_m = prices_cfg.get("sell", 1.0)
                        pricing_label = customtkinter.CTkLabel(store_frame, text = f"Sells at {sell_m}x value", font = customtkinter.CTkFont(size = 11), text_color = "orange")
                    pricing_label.pack(anchor = "w", padx = 10)

                    enter_button = self._create_sound_button(store_frame, "Enter", lambda s = store:self._open_ammo_supplier_interface(s, table_data), width = 200, height = 40, font = customtkinter.CTkFont(size = 12))
                    enter_button.pack(pady = 10, padx = 10)

            if gunsmiths:
                gunsmith_section = customtkinter.CTkLabel(scroll_frame, text = "Gunsmiths", font = customtkinter.CTkFont(size = 18, weight = "bold"))
                gunsmith_section.pack(pady =(20, 10), anchor = "w", padx = 10)

                for store in gunsmiths:
                    store_frame = customtkinter.CTkFrame(scroll_frame)
                    store_frame.pack(fill = "x", pady = 10, padx = 10)

                    name_label = customtkinter.CTkLabel(store_frame, text = store.get("name", "Unknown Gunsmith"), font = customtkinter.CTkFont(size = 14, weight = "bold"))
                    name_label.pack(anchor = "w", padx = 10, pady =(10, 5))

                    smith_label = customtkinter.CTkLabel(store_frame, text = f"Gunsmith: {store.get('shopkeeper', 'Unknown')}", font = customtkinter.CTkFont(size = 11), text_color = "gray")
                    smith_label.pack(anchor = "w", padx = 10)

                    costs = store.get("service_cost", {}) if isinstance(store.get("service_cost", {}), dict) else {}
                    part_cost = int(costs.get("part_repair", 100) or 100)
                    whole_cost = int(costs.get("whole_gun_repair", 350) or 350)
                    pricing_label = customtkinter.CTkLabel(
                        store_frame,
                        text = f"Part repair: {format_price(part_cost)} | Whole gun repair: {format_price(whole_cost)}",
                        font = customtkinter.CTkFont(size = 11),
                        text_color = "orange"
                    )
                    pricing_label.pack(anchor = "w", padx = 10)

                    enter_button = self._create_sound_button(
                        store_frame,
                        "Enter Gunsmith",
                        lambda s = store:self._open_gunsmith_interface(s),
                        width = 200,
                        height = 40,
                        font = customtkinter.CTkFont(size = 12)
                    )
                    enter_button.pack(pady = 10, padx = 10)

            market_button = self._create_sound_button(main_frame, "Market Overview", self._open_market_graph, width = 500, height = 40, font = customtkinter.CTkFont(size = 13))
            market_button.pack(pady = (10, 4))

            pending_orders_count = len([o for o in persistentdata.get("pending_orders", []) if o.get("character_save") == (self.currentsave or "")])
            orders_btn_text = f"Pending Orders ({pending_orders_count})" if pending_orders_count else "Pending Orders"
            orders_button = self._create_sound_button(main_frame, orders_btn_text, self._open_orders_popup, width = 500, height = 40, font = customtkinter.CTkFont(size = 13))
            orders_button.pack(pady = (4, 4))

            back_button = self._create_sound_button(main_frame, "Back to Main Menu", lambda:[self._clear_window(), self._build_main_menu()], width = 500, height = 50, font = customtkinter.CTkFont(size = 16))
            back_button.pack(pady = (4, 20))

        except Exception as e:
            logging.error(f"Failed to open business tool: {e}")
            self._popup_show_info("Error", f"Failed to load businesses: {e}", sound = "error")

    def _open_gunsmith_interface(self, store):
        logging.info("Gunsmith interface opened: %s", store.get("name", "Unknown"))
        music_channel = None
        if store.get("music") and store.get("playlist"):
            music_channel = self._start_business_music(store.get("playlist"), first_play = True)

        marquee_job:list[object] = [None]

        def stop_ui_music():
            try:
                if marquee_job[0]:
                    try:
                        self.root.after_cancel(marquee_job[0])# type: ignore[arg-type]
                    except Exception:
                        logging.exception("Suppressed exception")
                    marquee_job[0] = None
            except Exception:
                logging.exception("Suppressed exception")
            try:
                self._stop_business_music(music_channel)
            except Exception:
                logging.exception("Suppressed exception")

        def _leave_gunsmith():
            stop_ui_music()
            self._clear_window()
            self._open_business_tool()

        self._clear_window()

        if self.currentsave is None:
            self._popup_show_info("Error", "No character loaded.", sound = "error")
            stop_ui_music()
            self._build_main_menu()
            return

        save_data = self._load_file((self.currentsave or "") + ".sldsv")
        if save_data is None:
            self._popup_show_info("Error", "Failed to load character data.", sound = "error")
            _leave_gunsmith()
            return

        costs = store.get("service_cost", {}) if isinstance(store.get("service_cost", {}), dict) else {}
        part_repair_cost = int(costs.get("part_repair", 100) or 100)
        whole_repair_cost = int(costs.get("whole_gun_repair", 350) or 350)

        self.root.grid_rowconfigure(0, weight = 1)
        self.root.grid_columnconfigure(0, weight = 1)

        main_frame = customtkinter.CTkFrame(self.root)
        main_frame.grid(row = 0, column = 0, sticky = "nsew")
        main_frame.grid_columnconfigure(0, weight = 1)
        main_frame.grid_rowconfigure(1, weight = 1)

        header_frame = customtkinter.CTkFrame(main_frame, fg_color = "transparent")
        header_frame.grid(row = 0, column = 0, sticky = "ew", padx = 20, pady = 10)

        title_label = customtkinter.CTkLabel(header_frame, text = store.get("name", "Gunsmith"), font = customtkinter.CTkFont(size = 24, weight = "bold"))
        title_label.pack(pady =(10, 5))

        smith_name = store.get("shopkeeper", "Unknown")
        smith_label = customtkinter.CTkLabel(header_frame, text = f"Gunsmith: {smith_name}", font = customtkinter.CTkFont(size = 14), text_color = "gray")
        smith_label.pack()

        service_label = customtkinter.CTkLabel(
            header_frame,
            text = f"Part repair: {format_price(part_repair_cost)} | Whole gun repair: {format_price(whole_repair_cost)}",
            font = customtkinter.CTkFont(size = 12),
            text_color = "orange"
        )
        service_label.pack(pady =(4, 2))

        money_label = customtkinter.CTkLabel(header_frame, text = "", font = customtkinter.CTkFont(size = 16, weight = "bold"), text_color = "green")
        money_label.pack(pady = (2, 6))

        if music_channel and music_channel.get("track"):
            try:
                def _get_track_info(track_path):
                    artist = None
                    title = None
                    length = None
                    try:
                        try:
                            sound = pygame.mixer.Sound(track_path)
                            length = float(sound.get_length())
                        except Exception:
                            length = None
                        try:
                            from mutagen._file import File as MutagenFile
                            mf = MutagenFile(track_path)
                            if mf is not None:
                                tags = getattr(mf, "tags", {}) or {}
                                def _get_tag(keys):
                                    for k in keys:
                                        v = tags.get(k)
                                        if v:
                                            try:
                                                if isinstance(v, (list, tuple)):
                                                    return str(v[0])
                                                return str(v)
                                            except Exception:
                                                return str(v)
                                    return None
                                artist = _get_tag(["artist", "ARTIST", "TPE1", "IART"])
                                title = _get_tag(["title", "TITLE", "TIT2", "INAM"])
                        except Exception:
                            logging.exception("Suppressed exception")
                    except Exception:
                        logging.exception("Suppressed exception")
                    if not title:
                        try:
                            title = os.path.basename(track_path or "")
                        except Exception:
                            title = "Unknown"
                    return {"artist": artist, "title": title, "length": length}

                marquee_frame = customtkinter.CTkFrame(header_frame, fg_color = "black")
                marquee_frame.pack(pady = (6, 0))
                try:
                    marquee_frame.configure(width = 500)
                    marquee_frame.pack_propagate(False)
                except Exception:
                    logging.exception("Suppressed exception")

                label_font = customtkinter.CTkFont(size = 12)
                try:
                    import ctypes
                    import tkinter.font as tkfont
                    fp = os.path.join(os.path.dirname(__file__), "fonts", "Tims_8x5_LCD_Matrix.ttf")
                    if os.path.exists(fp) and hasattr(ctypes, "windll"):
                        try:
                            FR_PRIVATE = 0x10
                            ctypes.windll.gdi32.AddFontResourceExW(fp, FR_PRIVATE, 0)
                        except Exception:
                            logging.exception("Suppressed exception")
                        try:
                            self.root.update_idletasks()
                            for family_name in list(tkfont.families()):
                                if any(x in family_name.lower() for x in ("tims", "8x5", "lcd")):
                                    label_font = customtkinter.CTkFont(size = 12, family = family_name)
                                    break
                        except Exception:
                            logging.exception("Suppressed exception")
                except Exception:
                    logging.exception("Suppressed exception")

                marquee_label = customtkinter.CTkLabel(
                    marquee_frame,
                    text = "",
                    anchor = "w",
                    font = label_font,
                    width = 480,
                    height = 26,
                    text_color = "#7CFC00",
                )
                marquee_label.pack(anchor = "center", padx = 4)

                try:
                    self.root.update_idletasks()
                    label_h = marquee_label.winfo_reqheight() or marquee_label.winfo_height()
                    if label_h:
                        marquee_frame.configure(height = label_h)
                except Exception:
                    logging.exception("Suppressed exception")

                pos = [0]
                prev_track = [music_channel.get("track") if music_channel else None]

                def _fmt_time(seconds):
                    try:
                        seconds = max(0, int(seconds))
                        return f"{seconds // 60}:{seconds % 60:02d}"
                    except Exception:
                        return "0:00"

                def _update_marquee():
                    try:
                        current = getattr(self, "_current_business_music", music_channel) or music_channel
                        track_path = (current or {}).get("track")
                        if track_path != prev_track[0]:
                            prev_track[0] = track_path
                            pos[0] = 0

                        meta_info = (current or {}).get("_meta")
                        if not meta_info:
                            try:
                                if current and not current.get("_meta_loading"):
                                    current["_meta_loading"] = True
                                    def _bg_load():
                                        try:
                                            info = _get_track_info((current or {}).get("track"))
                                            def _apply():
                                                try:
                                                    target = getattr(self, "_current_business_music", None) or current
                                                    if target is not None:
                                                        target.update({"_meta": info})
                                                except Exception:
                                                    logging.exception("Suppressed exception")
                                            self.root.after(0, _apply)
                                        except Exception:
                                            logging.exception("Suppressed exception")
                                        finally:
                                            try:
                                                current.pop("_meta_loading", None)
                                            except Exception:
                                                logging.exception("Suppressed exception")
                                    import threading
                                    threading.Thread(target = _bg_load, daemon = True).start()
                            except Exception:
                                logging.exception("Suppressed exception")

                        meta_info = (current or {}).get("_meta") or {}
                        base_artist = meta_info.get("artist") or ""
                        base_title = meta_info.get("title") or os.path.basename(track_path or "")
                        total = meta_info.get("length") or 0.0

                        started = (current or {}).get("started_at") or time.time()
                        start_offset = (current or {}).get("start_pos") or 0.0
                        elapsed = (time.time() - started) + float(start_offset)

                        meta = f"{base_artist} | {base_title} | {_fmt_time(elapsed)}/{_fmt_time(total)}" if (base_artist or base_title) else os.path.basename(track_path or "")

                        try:
                            self.root.update_idletasks()
                            label_px = marquee_label.winfo_width() or int(marquee_label.cget("width") or 480)
                        except Exception:
                            label_px = int(marquee_label.cget("width") or 480)

                        visible_chars = max(8, int(label_px / 8))
                        scrollfull = " " + meta + " "
                        if len(scrollfull) < visible_chars:
                            scrollfull = scrollfull + (" " * (visible_chars - len(scrollfull) + 2))

                        doubled = scrollfull * 3
                        marquee_label.configure(text = doubled[pos[0]:pos[0] + visible_chars])
                        pos[0] = (pos[0] + 1) % max(1, len(scrollfull))
                        marquee_job[0] = self.root.after(140, _update_marquee)
                    except Exception:
                        try:
                            marquee_label.configure(text = os.path.basename((getattr(self, "_current_business_music", music_channel) or {}).get("track") or ""))
                        except Exception:
                            logging.exception("Suppressed exception")

                _update_marquee()
            except Exception:
                logging.exception("Suppressed exception")

        content_scroll = customtkinter.CTkScrollableFrame(main_frame)
        content_scroll.grid(row = 1, column = 0, sticky = "nsew", padx = 20, pady = (0, 10))

        firearm_rows = []

        def _collect_firearms(node, path_label):
            if isinstance(node, dict):
                if node.get("firearm"):
                    firearm_rows.append((path_label, node))

                for k, v in node.items():
                    if k == "current" and isinstance(v, dict):
                        continue
                    next_path = f"{path_label}.{k}" if path_label else str(k)
                    _collect_firearms(v, next_path)
            elif isinstance(node, list):
                for i, v in enumerate(node):
                    _collect_firearms(v, f"{path_label}[{i}]")

        _collect_firearms(save_data.get("hands", {}), "hands")
        _collect_firearms(save_data.get("equipment", {}), "equipment")
        _collect_firearms(save_data.get("storage", []), "storage")

        dedup = {}
        for p, itm in firearm_rows:
            dedup[id(itm)] = (p, itm)
        firearm_rows = list(dedup.values())

        if not firearm_rows:
            empty = customtkinter.CTkLabel(content_scroll, text = "No firearms found in equipment, hands, or storage.", text_color = "orange", font = customtkinter.CTkFont(size = 13))
            empty.pack(pady = 20, padx = 10, anchor = "w")

            button_row = customtkinter.CTkFrame(main_frame, fg_color = "transparent")
            button_row.grid(row = 2, column = 0, sticky = "ew", padx = 20, pady = (0, 20))
            self._create_sound_button(button_row, "Back to Businesses", _leave_gunsmith, width = 220, height = 44, font = customtkinter.CTkFont(size = 14)).pack(side = "left")
            return

        firearm_options = []
        firearm_map = {}
        for idx, (path_label, itm) in enumerate(firearm_rows, start = 1):
            gun_name = itm.get("name", f"Firearm {idx}")
            label = f"{gun_name} [{path_label}]"
            firearm_options.append(label)
            firearm_map[label] = itm

        select_frame = customtkinter.CTkFrame(content_scroll)
        select_frame.pack(fill = "x", pady = 8, padx = 10)
        customtkinter.CTkLabel(select_frame, text = "Select Firearm", font = customtkinter.CTkFont(size = 13, weight = "bold")).pack(anchor = "w", padx = 10, pady = (10, 6))

        selected_firearm_var = customtkinter.StringVar(value = firearm_options[0])
        firearm_menu = customtkinter.CTkOptionMenu(select_frame, values = firearm_options, variable = selected_firearm_var)
        firearm_menu.pack(fill = "x", padx = 10, pady = (0, 10))

        service_frame = customtkinter.CTkFrame(content_scroll)
        service_frame.pack(fill = "x", pady = 8, padx = 10)
        customtkinter.CTkLabel(service_frame, text = "Service Type", font = customtkinter.CTkFont(size = 13, weight = "bold")).pack(anchor = "w", padx = 10, pady = (10, 6))

        service_mode_var = customtkinter.StringVar(value = "part")
        customtkinter.CTkRadioButton(service_frame, text = f"Repair individual part ({format_price(part_repair_cost)})", variable = service_mode_var, value = "part").pack(anchor = "w", padx = 10, pady = 2)
        customtkinter.CTkRadioButton(service_frame, text = f"Repair whole gun ({format_price(whole_repair_cost)})", variable = service_mode_var, value = "whole").pack(anchor = "w", padx = 10, pady = (2, 10))

        part_frame = customtkinter.CTkFrame(content_scroll)
        part_frame.pack(fill = "x", pady = 8, padx = 10)
        customtkinter.CTkLabel(part_frame, text = "Part Selection (individual repair)", font = customtkinter.CTkFont(size = 13, weight = "bold")).pack(anchor = "w", padx = 10, pady = (10, 6))

        part_option_var = customtkinter.StringVar(value = "")
        part_menu = customtkinter.CTkOptionMenu(part_frame, values = ["No repairable parts"], variable = part_option_var)
        part_menu.pack(fill = "x", padx = 10, pady = (0, 10))

        part_map = {}

        def _refresh_money_label():
            money_label.configure(text = f"Your Money: {format_price(save_data.get('money', 0))}")

        _refresh_money_label()

        def _get_repair_parts(item):
            rows = []
            parts = item.get("parts", [])
            if not isinstance(parts, list):
                return rows
            for idx, p in enumerate(parts):
                if not isinstance(p, dict):
                    continue
                cur = p.get("current") if isinstance(p.get("current"), dict) else p
                if not isinstance(cur, dict):
                    continue

                cur_d = cur.get("current_durability")
                max_d = cur.get("durability")
                if max_d is None:
                    max_d = p.get("durability")
                if max_d is None:
                    max_d = PART_DURABILITY_MAX

                name = cur.get("name") or p.get("name") or f"Part {idx + 1}"
                try:
                    cur_val = float(cur_d) if cur_d is not None else float(max_d)
                except Exception:
                    cur_val = float(max_d)
                try:
                    max_val = float(max_d)
                except Exception:
                    max_val = float(PART_DURABILITY_MAX)

                disp = f"{name} ({int(round(cur_val))}/{int(round(max_val))})"
                rows.append((disp, p))
            return rows

        def _refresh_parts_menu(*_):
            selected = firearm_map.get(selected_firearm_var.get())
            part_map.clear()
            if not isinstance(selected, dict):
                part_menu.configure(values = ["No repairable parts"])
                part_option_var.set("No repairable parts")
                return

            rows = _get_repair_parts(selected)
            if not rows:
                part_menu.configure(values = ["No repairable parts"])
                part_option_var.set("No repairable parts")
                return

            vals = [d for d, _ in rows]
            for d, p in rows:
                part_map[d] = p
            part_menu.configure(values = vals)
            part_option_var.set(vals[0])

        firearm_menu.configure(command = lambda _v: _refresh_parts_menu())
        _refresh_parts_menu()

        def _repair_selected_part(part_entry):
            if not isinstance(part_entry, dict):
                return False
            cur = part_entry.get("current") if isinstance(part_entry.get("current"), dict) else part_entry
            if not isinstance(cur, dict):
                return False
            max_d = cur.get("durability")
            if max_d is None:
                max_d = part_entry.get("durability")
            if max_d is None:
                max_d = PART_DURABILITY_MAX
            try:
                max_val = float(max_d)
            except Exception:
                max_val = float(PART_DURABILITY_MAX)
            cur["current_durability"] = max_val
            if part_entry is not cur and isinstance(part_entry, dict):
                part_entry["current_durability"] = max_val
            return True

        def _perform_service():
            selected_firearm = firearm_map.get(selected_firearm_var.get())
            if not isinstance(selected_firearm, dict):
                self._popup_show_info("Error", "Select a valid firearm.", sound = "error")
                return

            mode = service_mode_var.get()
            cost = part_repair_cost if mode == "part" else whole_repair_cost
            cur_money = float(save_data.get("money", 0) or 0)
            if cur_money < cost:
                self._popup_show_info("Insufficient Funds", f"You need {format_price(cost)} for this service.", sound = "error")
                return

            changed = False
            if mode == "part":
                part_entry = part_map.get(part_option_var.get())
                if not part_entry:
                    self._popup_show_info("Error", "No repairable part selected.", sound = "error")
                    return
                changed = _repair_selected_part(part_entry)
                action_text = "Part repaired"
            else:
                _repair_item_parts_durability_recursive(selected_firearm, fallback_value = PART_DURABILITY_MAX)
                changed = True
                action_text = "Whole firearm repaired"

            if not changed:
                self._popup_show_info("Error", "Failed to apply repair.", sound = "error")
                return

            save_data["money"] = cur_money - cost
            self._save_file(save_data)
            _refresh_money_label()
            _refresh_parts_menu()
            self._popup_show_info("Gunsmith", f"{action_text} for {format_price(cost)}.", sound = "success")

        action_frame = customtkinter.CTkFrame(main_frame, fg_color = "transparent")
        action_frame.grid(row = 2, column = 0, sticky = "ew", padx = 20, pady = (0, 20))
        self._create_sound_button(action_frame, "Apply Service", _perform_service, width = 220, height = 44, font = customtkinter.CTkFont(size = 14)).pack(side = "left", padx = (0, 10))
        self._create_sound_button(action_frame, "Back to Businesses", _leave_gunsmith, width = 220, height = 44, font = customtkinter.CTkFont(size = 14)).pack(side = "left")

    def _open_market_graph(self):
        """Open a popup showing a line graph of market demand for the past 30 days."""
        import tkinter as tk

        HISTORY_DAYS = 30
        SEGMENT_COLORS = {
            "firearms":    "#FF6B6B",
            "ammunition":  "#FFD700",
            "attachments": "#98FB98",
            "magazines":   "#87CEEB",
            "melee":       "#FF8C00",
            "throwables":  "#DA70D6",
            "consumables": "#00CED1",
            "equipment":   "#9370DB",
        }

        # Build historical data
        today_key = _get_market_day_key()
        full_walk = _compute_market_walk(today_key)
        history = full_walk[-HISTORY_DAYS:]  # last N days

        popup = customtkinter.CTkToplevel(self.root)
        popup.title("Market Overview")
        popup.transient(self.root)
        popup.grab_set()
        popup.withdraw()

        popup.grid_rowconfigure(1, weight=1)
        popup.grid_columnconfigure(0, weight=1)

        # Header
        hdr = customtkinter.CTkFrame(popup, fg_color="transparent")
        hdr.grid(row=0, column=0, sticky="ew", padx=16, pady=(12, 4))
        customtkinter.CTkLabel(hdr, text="Market Demand — 30-Day History",
                               font=customtkinter.CTkFont(size=18, weight="bold")).pack(side="left")

        # Compute next update time
        now = datetime.now()
        if now.hour < 12:
            next_update = now.replace(hour=12, minute=0, second=0, microsecond=0)
        else:
            next_update = (now + timedelta(days=1)).replace(hour=12, minute=0, second=0, microsecond=0)
        delta = next_update - now
        hours, rem = divmod(int(delta.total_seconds()), 3600)
        mins = rem // 60
        customtkinter.CTkLabel(hdr, text=f"  Next update in {hours}h {mins}m",
                               font=customtkinter.CTkFont(size=11), text_color="gray").pack(side="left", padx=8)

        # Canvas container
        graph_frame = customtkinter.CTkFrame(popup)
        graph_frame.grid(row=1, column=0, sticky="nsew", padx=16, pady=4)

        CANVAS_W = 920
        CANVAS_H = 400
        PAD_L = 58
        PAD_R = 20
        PAD_T = 28
        PAD_B = 48
        PLOT_W = CANVAS_W - PAD_L - PAD_R
        PLOT_H = CANVAS_H - PAD_T - PAD_B
        Y_MIN = 0.65
        Y_MAX = 1.40

        canvas = tk.Canvas(graph_frame, width=CANVAS_W, height=CANVAS_H,
                           bg="#1a1a2e", highlightthickness=0)
        canvas.pack(padx=4, pady=4)

        def y_to_px(val):
            frac = (val - Y_MIN) / (Y_MAX - Y_MIN)
            return PAD_T + PLOT_H * (1.0 - frac)

        def x_to_px(idx):
            n = len(history)
            if n <= 1:
                return PAD_L + PLOT_W / 2
            return PAD_L + (idx / (n - 1)) * PLOT_W

        # Grid lines at 10 % intervals
        grid_vals = [i / 100 for i in range(60, 160, 10)]
        for gv in grid_vals:
            gy = y_to_px(gv)
            canvas.create_line(PAD_L, gy, PAD_L + PLOT_W, gy,
                               fill="#2a2a4a", width=1)
            pct = int(round((gv - 1.0) * 100))
            label_txt = f"{'+' if pct >= 0 else ''}{pct}%"
            canvas.create_text(PAD_L - 6, gy, text=label_txt,
                               fill="#888899", font=("Courier", 8), anchor="e")

        # Baseline at 0 %
        baseline_y = y_to_px(1.0)
        canvas.create_line(PAD_L, baseline_y, PAD_L + PLOT_W, baseline_y,
                           fill="#555577", width=1, dash=(4, 3))

        # Highlight today's column
        today_x = x_to_px(len(history) - 1)
        canvas.create_rectangle(today_x - 8, PAD_T,
                                 today_x + 8, PAD_T + PLOT_H,
                                 fill="#2a2a1a", outline="")
        canvas.create_line(today_x, PAD_T, today_x, PAD_T + PLOT_H,
                           fill="#ffff55", width=1, dash=(3, 3))
        canvas.create_text(today_x, PAD_T - 10, text="Today",
                           fill="#ffff55", font=("Courier", 7))

        # X-axis date labels (every 5 days)
        for i, (dk, _) in enumerate(history):
            if i % 5 == 0 or i == len(history) - 1:
                lx = x_to_px(i)
                canvas.create_text(lx, PAD_T + PLOT_H + 12,
                                   text=dk[5:],  # MM-DD
                                   fill="#666688", font=("Courier", 7), anchor="n")

        # Draw segment lines + dots at today
        visible_segs = list(_MARKET_SEGMENTS)
        for seg in visible_segs:
            color = SEGMENT_COLORS.get(seg, "#ffffff")
            points = []
            for i, (dk, demand) in enumerate(history):
                mult = demand.get(seg, 1.0)
                points.append((x_to_px(i), y_to_px(mult)))

            # Line
            for j in range(len(points) - 1):
                canvas.create_line(points[j][0], points[j][1],
                                   points[j+1][0], points[j+1][1],
                                   fill=color, width=2, smooth=True)

            # Today dot
            tx, ty = points[-1]
            canvas.create_oval(tx - 4, ty - 4, tx + 4, ty + 4,
                               fill=color, outline="#ffffff", width=1)

        # Axes borders
        canvas.create_rectangle(PAD_L, PAD_T,
                                 PAD_L + PLOT_W, PAD_T + PLOT_H,
                                 outline="#444466", width=1)

        # Legend (two rows of 4)
        legend_frame = customtkinter.CTkFrame(popup, fg_color="transparent")
        legend_frame.grid(row=2, column=0, sticky="ew", padx=16, pady=(0, 4))
        for col_idx, seg in enumerate(_MARKET_SEGMENTS):
            color = SEGMENT_COLORS.get(seg, "#ffffff")
            demand_today = history[-1][1]
            mult = demand_today.get(seg, 1.0)
            pct = round((mult - 1.0) * 100)
            sign = "+" if pct >= 0 else ""
            arrow = "▲" if pct >= 0 else "▼"
            label_txt = f"{_MARKET_SEGMENT_DISPLAY[seg]}  {arrow}{sign}{pct}%"
            lbl = customtkinter.CTkLabel(legend_frame, text=label_txt,
                                         font=customtkinter.CTkFont(size=11),
                                         text_color=color)
            lbl.grid(row=col_idx // 4, column=col_idx % 4, padx=12, pady=2, sticky="w")

        # Close button
        btn_frame = customtkinter.CTkFrame(popup, fg_color="transparent")
        btn_frame.grid(row=3, column=0, pady=(4, 14))
        self._create_sound_button(btn_frame, "Close", popup.destroy,
                                   width=120, height=35).pack()

        popup.update_idletasks()
        w, h = popup.winfo_reqwidth(), popup.winfo_reqheight()
        sw, sh = popup.winfo_screenwidth(), popup.winfo_screenheight()
        popup.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")
        popup.deiconify()
        popup.lift()

    def _get_armory_points_status(self, store_name):

        import pytz
        from datetime import datetime, timedelta

        try:
            cst = pytz.timezone('US/Central')
            now_cst = datetime.now(cst)

            reset_time_today = now_cst.replace(hour = 19, minute = 0, second = 0, microsecond = 0)

            if now_cst >=reset_time_today:
                last_reset = reset_time_today
            else:
                last_reset = reset_time_today -timedelta(days = 1)

            armory_key = f"armory_points_{store_name}"
            last_reset_key = f"armory_reset_{store_name}"

            stored_reset = persistentdata.get(last_reset_key)
            if stored_reset:
                try:
                    stored_reset_dt = datetime.fromisoformat(stored_reset)
                    if stored_reset_dt.tzinfo is None:
                        stored_reset_dt = cst.localize(stored_reset_dt)
                except Exception:
                    stored_reset_dt = None
            else:
                stored_reset_dt = None

            if stored_reset_dt is None or stored_reset_dt <last_reset:
                persistentdata[last_reset_key]= last_reset.isoformat()
                persistentdata[armory_key]= None
                self._save_persistent_data()
                return None

            return persistentdata.get(armory_key)

        except Exception as e:
            logging.warning(f"Failed to check armory points reset: {e}")
            return persistentdata.get(f"armory_points_{store_name}")

    def _set_armory_points_used(self, store_name, points_used):

        armory_key = f"armory_points_{store_name}"
        persistentdata[armory_key]= points_used
        self._save_persistent_data()

    def _get_business_music_track_length(self, track_path):
        try:
            cache = getattr(self, "_business_music_track_length_cache", {})
            if track_path in cache:
                return cache.get(track_path)or 60.0
        except Exception:
            cache = {}

        track_length = 60.0
        try:
            sound = pygame.mixer.Sound(track_path)
            track_length = max(1.0, float(sound.get_length()or 0.0))
        except Exception:
            track_length = 60.0

        try:
            cache[track_path]= track_length
            self._business_music_track_length_cache = cache
        except Exception:
            logging.exception("Suppressed exception")
        return track_length

    def _pick_business_music_track_and_position(self, playlists, all_tracks, first_play = False):
        tracks = sorted(all_tracks or [], key = lambda t:(os.path.basename(t).lower(), t.lower()))
        if not tracks:
            return None, 0.0

        force_track_raw = str(appearance_settings.get("business_music_sync_force_track", "")or "").strip()
        force_position_raw = appearance_settings.get("business_music_sync_force_position", -1.0)

        forced_track = None
        if force_track_raw:
            try:
                forced_index = int(force_track_raw)
                if 0 <=forced_index <len(tracks):
                    forced_track = tracks[forced_index]
            except Exception:
                forced_index = None
            if forced_track is None:
                needle = force_track_raw.lower()
                for candidate in tracks:
                    if os.path.basename(candidate).lower()==needle:
                        forced_track = candidate
                        break

        if forced_track:
            forced_pos = 0.0
            try:
                forced_pos = float(force_position_raw)
            except Exception:
                forced_pos = 0.0
            track_len = self._get_business_music_track_length(forced_track)
            forced_pos = max(0.0, min(max(0.0, track_len -0.05), forced_pos))
            return forced_track, forced_pos

        sync_mode = str(appearance_settings.get("business_music_sync_mode", "random")or "random").strip().lower()
        if sync_mode in("seed", "seeded", "deterministic", "sync"):
            seed_text = str(appearance_settings.get("business_music_sync_seed", "doom-tools-shared")or "doom-tools-shared")
            playlist_key = "|".join(sorted(str(p)for p in(playlists or [])))
            seed_payload = f"business_music_sync_v2|{seed_text}|{playlist_key}"

            # Build a deterministic randomized playlist order shared by all clients.
            order_seed = int(_hashlib.sha256((seed_payload +"|order").encode("utf-8")).hexdigest(), 16) & 0xFFFFFFFF
            order_rng = random.Random(order_seed)
            seeded_tracks = list(tracks)
            order_rng.shuffle(seeded_tracks)

            lengths_sec = []
            for tp in seeded_tracks:
                try:
                    sec_len = int(round(float(self._get_business_music_track_length(tp))))
                except Exception:
                    sec_len = 60
                lengths_sec.append(max(1, sec_len))

            total_cycle_seconds = int(sum(lengths_sec))
            if total_cycle_seconds <=0:
                lengths_sec =[60 for _ in seeded_tracks]
                total_cycle_seconds = int(sum(lengths_sec))

            offset_seed = int(_hashlib.sha256((seed_payload +"|offset").encode("utf-8")).hexdigest(), 16)
            seed_offset_seconds = int(offset_seed % max(1, total_cycle_seconds))

            # Rolling global second tick keeps all clients on the same song/timepoint.
            tick_seconds = int(time.time())
            phase_seconds = int((tick_seconds +seed_offset_seconds) % max(1, total_cycle_seconds))

            cursor_seconds = 0
            for idx, seg_len_seconds in enumerate(lengths_sec):
                next_cursor = cursor_seconds +seg_len_seconds
                if phase_seconds <next_cursor or idx ==len(lengths_sec)-1:
                    start_pos = float(max(0, min(max(0, seg_len_seconds -1), phase_seconds -cursor_seconds)))
                    return seeded_tracks[idx], start_pos
                cursor_seconds = next_cursor

        prev = getattr(self, "_last_business_music_track", None)
        if len(tracks)>1 and prev in tracks:
            choices =[t for t in tracks if t !=prev]
            track = random.choice(choices)if choices else random.choice(tracks)
        else:
            track = random.choice(tracks)

        random_start = 0.0
        if first_play:
            try:
                track_length = self._get_business_music_track_length(track)
                ext = os.path.splitext(track)[1].lower()
                if ext in (".ogg", ".mp3"):
                    random_start = random.uniform(0, max(0.0, track_length -10.0))
            except Exception:
                random_start = 0.0

        return track, random_start

    def _start_business_music(self, playlists, first_play:bool = False):

        try:
            if not playlists:
                return None

            if isinstance(playlists, str):
                playlists = [playlists]
            elif not isinstance(playlists, (list, tuple, set)):
                return None

            if appearance_settings.get("mute_business_music", False):
                logging.debug("Business music is muted by settings; skipping playback start")
                return None

            all_tracks =[]
            for playlist in playlists:
                music_folder = os.path.join("sounds", "music", playlist)
                if os.path.exists(music_folder):
                    tracks = []
                    for ext in ("ogg", "wav", "mp3"):
                        tracks.extend(glob.glob(os.path.join(music_folder, f"track*.{ext}")))

                    tracks =[t for t in tracks if os.path.getsize(t)>0]
                    all_tracks.extend(tracks)

            failed_tracks = getattr(self, "_failed_music_tracks", set())

            all_tracks =[t for t in all_tracks if t not in failed_tracks]

            if all_tracks:
                track, random_start = self._pick_business_music_track_and_position(playlists, all_tracks, first_play = first_play)
                if not track:
                    return None

                try:
                    pygame.mixer.music.load(track)
                except Exception as load_err:
                    logging.warning(f"Cannot load track {os.path.basename(track)}: {load_err}")
                    failed_tracks.add(track)
                    self._failed_music_tracks = failed_tracks

                    return self._start_business_music(playlists, first_play)

                try:
                    self._last_business_music_track = track
                except Exception:
                    logging.exception("Suppressed exception")

                try:
                    track_length = self._get_business_music_track_length(track)
                except Exception:
                    track_length = 60.0

                try:
                    random_start = max(0.0, min(max(0.0, track_length -0.05), float(random_start)))
                except Exception:
                    random_start = 0.0

                try:
                    music_vol = float(appearance_settings.get("music_volume", appearance_settings.get("sound_volume", 100))) / 100.0
                except Exception:
                    music_vol = 1.0
                music_vol = max(0.0, min(1.0, music_vol))
                pygame.mixer.music.set_volume(music_vol)

                try:
                    if random_start > 0:
                        pygame.mixer.music.play(loops = 0, start = random_start)
                    else:
                        pygame.mixer.music.play(loops = 0)
                except Exception:
                    # Fallback for formats/backends that don't support start position.
                    pygame.mixer.music.play(loops = 0)

                sync_mode = str(appearance_settings.get("business_music_sync_mode", "random")or "random").strip().lower()
                logging.info(f"Started business music: {os.path.basename(track)} at {random_start:.1f}s(mode={sync_mode})")
                music_info = {
                    "track":track,
                    "playlist":playlists,
                    "start_pos":random_start,
                    "started_at":time.time(),
                    "sync_mode":sync_mode,
                    "sync_seed":appearance_settings.get("business_music_sync_seed", "doom-tools-shared")
                }

                try:
                    self._current_business_music = music_info
                except Exception:
                    logging.exception("Suppressed exception")
                try:
                    logging.debug(f"_start_business_music set _current_business_music -> {os.path.basename(track)} start={random_start:.1f}")
                except Exception:
                    logging.exception("Suppressed exception")

                try:
                    existing = getattr(self, "_music_poll_job", None)
                    if existing:
                        try:
                            self.root.after_cancel(existing)
                        except Exception:
                            logging.exception("Suppressed exception")
                        self._music_poll_job = None
                except Exception:
                    logging.exception("Suppressed exception")

                def _poll_music():
                    try:
                        if not pygame.mixer.music.get_busy():

                            try:

                                logging.debug("business music finished, starting next track")
                                self._start_business_music(playlists, first_play = False)
                            except Exception:
                                logging.exception("Suppressed exception")
                        else:

                            self._music_poll_job = self.root.after(1000, _poll_music)
                    except Exception:
                        logging.exception("Suppressed exception")

                try:
                    self._music_poll_job = self.root.after(1000, _poll_music)
                except Exception:
                    self._music_poll_job = None

                return music_info
        except Exception as e:
            logging.warning(f"Failed to start business music: {e}")
        return None

    def _apply_business_music_volume(self):
        try:
            if appearance_settings.get("mute_business_music", False):
                pygame.mixer.music.set_volume(0.0)
                return
            vol = float(appearance_settings.get("music_volume", appearance_settings.get("sound_volume", 100))) / 100.0
            vol = max(0.0, min(1.0, vol))
            pygame.mixer.music.set_volume(vol)
        except Exception:
            logging.exception("Suppressed exception")

    def _stop_business_music(self, music_info):

        try:

            try:
                job = getattr(self, "_music_poll_job", None)
                if job:
                    try:
                        self.root.after_cancel(job)
                    except Exception:
                        logging.exception("Suppressed exception")
                    self._music_poll_job = None
            except Exception:
                logging.exception("Suppressed exception")

            pygame.mixer.music.stop()
            try:
                pygame.mixer.music.unload()
            except Exception:
                logging.exception("Suppressed exception")
            try:

                if hasattr(self, "_current_business_music"):
                    self._current_business_music = None
            except Exception:
                logging.exception("Suppressed exception")
        except Exception:
            logging.exception("Suppressed exception")

    def _open_armory_interface(self, store, table_data):

        logging.info(f"Opening armory: {store.get('name')}")

        music_channel = None
        if store.get("music")and store.get("playlist"):
            music_channel = self._start_business_music(store.get("playlist"), first_play = True)

        self._clear_window()

        self.root.grid_rowconfigure(0, weight = 1)
        self.root.grid_columnconfigure(0, weight = 1)

        main_frame = customtkinter.CTkFrame(self.root)
        main_frame.grid(row = 0, column = 0, sticky = "nsew")
        main_frame.grid_columnconfigure(0, weight = 1)
        main_frame.grid_rowconfigure(1, weight = 1)

        header_frame = customtkinter.CTkFrame(main_frame, fg_color = "transparent")
        header_frame.grid(row = 0, column = 0, sticky = "ew", padx = 20, pady = 10)

        title_label = customtkinter.CTkLabel(header_frame, text = store.get("name", "Armory"), font = customtkinter.CTkFont(size = 24, weight = "bold"))
        title_label.pack(pady =(10, 5))

        shopkeeper_label = customtkinter.CTkLabel(header_frame, text = f"Quartermaster: {store.get('shopkeeper', 'Unknown')}", font = customtkinter.CTkFont(size = 14), text_color = "gray")
        shopkeeper_label.pack()

        max_points = store.get("armory_points", "disabled")
        points_used = self._get_armory_points_status(store.get("name", "Unknown"))or 0

        if max_points !="disabled":
            overflow_key = f"armory_overflow_{store.get('name', 'Unknown')}"
            overflow_amt = persistentdata.get(overflow_key, 0)or 0
            remaining_points = max_points +overflow_amt -points_used
            points_label = customtkinter.CTkLabel(header_frame, text = f"Requisition Points: {remaining_points}/{max_points}(+{overflow_amt} overflow)(resets 7 PM CST)", font = customtkinter.CTkFont(size = 14), text_color = "orange")
            points_label.pack(pady = 5)
        else:
            remaining_points = float('inf')
            points_label = customtkinter.CTkLabel(header_frame, text = "Unlimited Requisitions", font = customtkinter.CTkFont(size = 14), text_color = "green")
            points_label.pack(pady = 5)

        try:
            search_frame = customtkinter.CTkFrame(header_frame, fg_color = "transparent")
            search_frame.pack(pady =(6, 2))
            search_entry = customtkinter.CTkEntry(search_frame, placeholder_text = "Search armory items...", width = 360)
            search_entry.pack(side = "left", padx =(0, 6))
            def _perform_armory_search(event = None):
                try:
                    q =(search_entry.get()or "").strip().lower()
                    if not q:

                        try:
                            if selected_category and selected_category[0]:
                                show_category_items(selected_category[0])
                                return
                        except Exception:
                            logging.exception("Suppressed exception")
                        return

                    matches =[]
                    try:
                        for cat, items in list(categories.items()):
                            for it in items:
                                try:
                                    name =(self._format_item_name(it)or "").lower()
                                except Exception:
                                    name =(it.get('name')or '').lower()
                                desc =(it.get('description')or '').lower()
                                if q in name or q in desc:
                                    matches.append(it)

                        categories["Search Results"]= matches
                        show_category_items("Search Results")
                        try:

                            search_entry.configure(text_color = "#7CFC00")
                            self.root.after(800, lambda:search_entry.configure(text_color = "#000000"))
                        except Exception:
                            logging.exception("Suppressed exception")
                    except Exception:
                        logging.exception("Suppressed exception")
                except Exception:
                    logging.exception("Suppressed exception")

            search_btn = self._create_sound_button(search_frame, "Search", _perform_armory_search, width = 80, height = 28, font = customtkinter.CTkFont(size = 11))
            search_btn.pack(side = "left")
            def _clear_search():
                try:
                    search_entry.delete(0, 'end')
                    try:
                        categories.pop("Search Results", None)
                    except Exception:
                        logging.exception("Suppressed exception")
                    try:
                        if selected_category and selected_category[0]:
                            show_category_items(selected_category[0])
                    except Exception:
                        logging.exception("Suppressed exception")
                except Exception:
                    logging.exception("Suppressed exception")
            clear_btn = self._create_sound_button(search_frame, "Clear", _clear_search, width = 60, height = 28, font = customtkinter.CTkFont(size = 11))
            clear_btn.pack(side = "left", padx =(6, 0))
            try:
                search_entry.bind("<Return>", _perform_armory_search)
            except Exception:
                logging.exception("Suppressed exception")
        except Exception:
            logging.exception("Suppressed exception")

        marquee_label = None
        marquee_job:list[object]=[None]

        def _get_track_info(track_path):
            artist = None
            title = None
            length = None
            try:
                logging.debug(f"_get_track_info called for: {os.path.basename(track_path or '')}")
            except Exception:
                logging.exception("Suppressed exception")
            try:

                try:
                    sound = pygame.mixer.Sound(track_path)
                    length = float(sound.get_length())
                except Exception:
                    length = None

                try:
                    from mutagen._file import File as MutagenFile
                    mf = MutagenFile(track_path)
                    if mf is not None:
                        tags = getattr(mf, 'tags', {})or {}

                        def _get_tag(keys):
                            for k in keys:
                                v = tags.get(k)
                                if v:
                                    try:
                                        if isinstance(v, (list, tuple)):
                                            return str(v[0])
                                        return str(v)
                                    except Exception:
                                        return str(v)
                            return None
                        artist = _get_tag(["artist", "ARTIST", "TPE1", "IART"])
                        title = _get_tag(["title", "TITLE", "TIT2", "INAM"])
                except Exception:
                    logging.exception("Suppressed exception")

            except Exception:
                logging.exception("Suppressed exception")

            if not title:
                try:
                    title = os.path.basename(track_path or "")
                except Exception:
                    title = "Unknown"

            return {"artist":artist, "title":title, "length":length}

        def stop_ui_music():
            try:
                if marquee_job[0]:
                    try:
                        self.root.after_cancel(marquee_job[0])# type: ignore[arg-type]
                    except Exception:
                        logging.exception("Suppressed exception")
                    marquee_job[0]= None
            except Exception:
                logging.exception("Suppressed exception")
            try:
                self._stop_business_music(music_channel)
            except Exception:
                logging.exception("Suppressed exception")

        if music_channel and music_channel.get("track"):
            try:
                track_path = music_channel.get("track")
                info = _get_track_info(track_path)
                base_artist = info.get("artist")or ""
                base_title = info.get("title")or os.path.basename(track_path or "")
                track_len = info.get("length")or 0.0

                marquee_frame = customtkinter.CTkFrame(header_frame, fg_color = "black")

                marquee_frame.pack(pady =(6, 0))
                try:
                    marquee_frame.configure(width = 500)

                    try:
                        marquee_frame.pack_propagate(False)
                    except Exception:
                        logging.exception("Suppressed exception")
                except Exception:
                    logging.exception("Suppressed exception")
                try:

                    label_font = None
                    try:
                        import ctypes
                        import tkinter.font as tkfont
                        fp = os.path.join(os.path.dirname(__file__), "fonts", "Tims_8x5_LCD_Matrix.ttf")
                        if os.path.exists(fp)and hasattr(ctypes, 'windll'):
                            try:
                                FR_PRIVATE = 0x10
                                ctypes.windll.gdi32.AddFontResourceExW(fp, FR_PRIVATE, 0)
                            except Exception:
                                logging.exception("Suppressed exception")

                            try:
                                self.root.update_idletasks()
                                fams = list(tkfont.families())
                                for f in fams:
                                    if any(x in f.lower()for x in("tims", "8x5", "lcd")):
                                        label_font = customtkinter.CTkFont(size = 12, family = f)
                                        break
                            except Exception:
                                logging.exception("Suppressed exception")
                    except Exception:
                        logging.exception("Suppressed exception")
                    if not label_font:
                        label_font = customtkinter.CTkFont(size = 12)
                except Exception:
                    label_font = customtkinter.CTkFont(size = 12)
                marquee_label = customtkinter.CTkLabel(marquee_frame, text = "", anchor = "w", font = label_font, width = 480, height = 26, text_color = "#7CFC00")
                marquee_label.pack(anchor = "center", padx = 4)
                try:
                    marquee_debug_label = customtkinter.CTkLabel(marquee_frame, text = "", anchor = "w", font = customtkinter.CTkFont(size = 9), text_color = "white")
                    marquee_debug_label.pack(anchor = "center", padx = 4, pady =(2, 0))
                except Exception:
                    marquee_debug_label = None
                try:
                    self.root.update_idletasks()
                    lh = marquee_label.winfo_reqheight()or marquee_label.winfo_height()
                    if lh:
                        try:
                            marquee_frame.configure(height = lh)
                        except Exception:
                            logging.exception("Suppressed exception")
                except Exception:
                    logging.exception("Suppressed exception")

                pos =[0]
                prev_track =[music_channel.get('track')if(music_channel and music_channel.get('track'))else None]

                def _fmt_time(s):
                    try:
                        s = max(0, int(s))
                        return f"{s //60}:{s %60:02d}"
                    except Exception:
                        return "0:00"

                def _update_marquee():
                    try:

                        current = getattr(self, "_current_business_music", music_channel)
                        meta_info = None
                        if current:
                            meta_info = current.get("_meta")

                        try:
                            track_path =(current or {}).get('track')
                            if track_path !=prev_track[0]:
                                prev_track[0]= track_path
                                pos[0]= 0
                        except Exception:
                            track_path =(current or {}).get('track')
                        try:
                            logging.debug(f"store marquee update: track={os.path.basename((current or {}).get('track')or '')} meta={bool(meta_info)} pos={pos[0]} ids: current={id(current)} music_channel={id(music_channel)} self_cur={id(getattr(self, '_current_business_music', None))}")
                        except Exception:
                            logging.exception("Suppressed exception")
                        try:
                            if marquee_debug_label is not None:
                                dbg = f"meta={bool(meta_info)} id={id(current)}"
                                try:

                                    tt =(meta_info or {}).get('title')if meta_info else((current or {}).get('track')or '')
                                    if tt:
                                        dbg +=f" title={tt[:30]}"
                                except Exception:
                                    logging.exception("Suppressed exception")
                                marquee_debug_label.configure(text = dbg)
                        except Exception:
                            logging.exception("Suppressed exception")

                        if meta_info:
                            base_artist = meta_info.get("artist")or ""
                            base_title = meta_info.get("title")or os.path.basename(track_path or "")
                            total = meta_info.get("length")or 0.0
                        else:
                            base_artist = ""
                            base_title = os.path.basename(track_path or "")
                            total = 0.0

                            try:
                                if not current.get("_meta_loading"):
                                    current["_meta_loading"]= True
                                    def _bg_load():
                                        try:
                                            info = _get_track_info(track_path)
                                            def _apply():
                                                try:
                                                    try:
                                                        logging.debug(f"applying _meta(bg_load current): {os.path.basename((current or {}).get('track')or '')} -> title={info.get('title')} artist={info.get('artist')}")
                                                    except Exception:
                                                        logging.exception("Suppressed exception")
                                                    try:
                                                        target = getattr(self, "_current_business_music", None)
                                                        if target is None:
                                                            target = current
                                                        if target is not None:
                                                                target.update({"_meta":info})
                                                                try:
                                                                    logging.debug(f"triggering marquee refresh after applying meta for {os.path.basename((target or {}).get('track')or '')}(current)")
                                                                except Exception:
                                                                    logging.exception("Suppressed exception")
                                                                try:

                                                                    self.root.after(0, _update_marquee)
                                                                except Exception:
                                                                    logging.exception("Suppressed exception")
                                                    except Exception:
                                                        try:
                                                            logging.exception("failed to apply _meta in bg_load(current) for store marquee")
                                                        except Exception:
                                                            logging.exception("Suppressed exception")
                                                except Exception:
                                                    try:
                                                        logging.exception("unexpected error in _apply for bg_load(current)")
                                                    except Exception:
                                                        logging.exception("Suppressed exception")
                                            try:
                                                logging.debug(f"scheduling _apply(current) via root.after for track {os.path.basename((getattr(self, '_current_business_music', current)or {}).get('track')or '')}")
                                            except Exception:
                                                logging.exception("Suppressed exception")
                                            self.root.after(0, _apply)
                                        except Exception:
                                            logging.exception("Suppressed exception")
                                        finally:
                                            try:
                                                current.pop("_meta_loading", None)
                                            except Exception:
                                                logging.exception("Suppressed exception")
                                    import threading
                                    try:
                                        logging.debug("starting background _bg_load thread for store marquee(in _update_marquee)")
                                    except Exception:
                                        logging.exception("Suppressed exception")
                                    threading.Thread(target = _bg_load, daemon = True).start()
                            except Exception:
                                logging.exception("Suppressed exception")

                        started = current.get("started_at")or time.time()
                        start_offset = current.get("start_pos")or 0.0
                        elapsed =(time.time()-started)+float(start_offset)

                        elapsed_display = _fmt_time(elapsed)
                        total_fmt = _fmt_time(total)

                        meta = f"{base_artist} | {base_title} | {elapsed_display}/{total_fmt}"if(base_artist or base_title)else os.path.basename((music_channel or {}).get("track")or "")

                        try:
                            self.root.update_idletasks()
                            label_px = marquee_label.winfo_width()or int(marquee_label.cget("width")or 480)
                        except Exception:
                            label_px = int(marquee_label.cget("width")or 480)

                        avg_char_px = 8
                        visible_chars = max(8, int(label_px /max(1, avg_char_px)))

                        scrollfull = " "+meta +" "
                        if len(scrollfull)<visible_chars:
                            scrollfull = scrollfull +(" "*(visible_chars -len(scrollfull)+2))

                        doubled =(scrollfull *3)
                        display = doubled[pos[0]:pos[0]+visible_chars]
                        marquee_label.configure(text = display)
                        pos[0]=(pos[0]+1)%max(1, len(scrollfull))
                        try:

                            len_scroll = max(1, len(scrollfull))
                            delay_ms = int(min(500, max(60, 80 +(len_scroll *4))))
                        except Exception:
                            delay_ms = 220
                        marquee_job[0]= self.root.after(delay_ms, _update_marquee)
                    except Exception:
                        try:
                            marquee_label.configure(text = os.path.basename((getattr(self, "_current_business_music", music_channel)or {}).get("track")or ""))
                        except Exception:
                            logging.exception("Suppressed exception")

                try:
                    import threading
                    def _load_meta():
                        try:
                            cur = getattr(self, "_current_business_music", music_channel)
                            if not cur:
                                return
                            info = _get_track_info(cur.get("track"))
                            def _apply():
                                try:

                                    cur.update({"_meta":info})
                                except Exception:
                                    logging.exception("Suppressed exception")
                            self.root.after(0, _apply)
                        except Exception:
                            logging.exception("Suppressed exception")
                    try:
                        import threading
                        try:
                            logging.debug("starting initial background _load_meta thread for store marquee")
                        except Exception:
                            logging.exception("Suppressed exception")
                        threading.Thread(target = _load_meta, daemon = True).start()
                    except Exception:
                        logging.exception("Suppressed exception")
                except Exception:
                    logging.exception("Suppressed exception")

                _update_marquee()
            except Exception:
                logging.exception("Suppressed exception")

        save_path = os.path.join(saves_folder or "", (self.currentsave or "")+".sldsv")
        save_data = self._load_file((self.currentsave or "")+".sldsv")
        if save_data is None:
            self._popup_show_info("Error", "Failed to load character data.", sound = "error")
            try:
                self._stop_business_music(music_channel)
            except Exception:
                logging.exception("Suppressed exception")
            return

        equipped_weapons = self._get_equipped_weapons(save_data, table_data)
        equipped_calibers = set()
        equipped_magazine_systems = set()

        def _normalize_mag_system_values(raw_value):
            if raw_value is None:
                return []
            if isinstance(raw_value, str):
                return [raw_value]
            if isinstance(raw_value, (list, tuple, set)):
                vals = []
                for v in raw_value:
                    if v is None:
                        continue
                    vals.append(str(v))
                return vals
            return [str(raw_value)]

        def _mag_system_matches(raw_value):
            return any(ms in equipped_magazine_systems for ms in _normalize_mag_system_values(raw_value))

        for wpn in equipped_weapons:
            item = wpn.get("item", {})
            calibers = item.get("caliber", [])
            if isinstance(calibers, str):
                calibers =[calibers]
            for cal in calibers:
                equipped_calibers.add(cal)

            mag_system = item.get("magazinesystem")
            for ms in _normalize_mag_system_values(mag_system):
                if ms:
                    equipped_magazine_systems.add(ms)

        equipped_attachment_slots = set()
        for wpn in equipped_weapons:
            for acc in(wpn.get('accessories')or[]):
                try:
                    slot = acc.get('slot')
                    if slot:
                        equipped_attachment_slots.add(slot)
                except Exception:
                    logging.exception("Suppressed exception")

        armory_items =[]
        tables = table_data.get("tables", {})
        for table_name, items in tables.items():
            if isinstance(items, list):
                for item in items:
                    if isinstance(item, dict)and item.get("in_armory"):
                        item_copy = item.copy()
                        item_copy["_table_category"]= table_name
                        armory_items.append(item_copy)

        categories = {}
        for item in armory_items:
            cat = item.get("armory_category", "Uncategorized")
            if cat not in categories:
                categories[cat]=[]
            categories[cat].append(item)

        content_frame = customtkinter.CTkFrame(main_frame)
        content_frame.grid(row = 1, column = 0, sticky = "nsew", padx = 20, pady = 10)

        content_frame.grid_columnconfigure(0, weight = 0)
        content_frame.grid_columnconfigure(1, weight = 0)
        content_frame.grid_columnconfigure(2, weight = 1)
        content_frame.grid_rowconfigure(0, weight = 1)

        category_frame = customtkinter.CTkScrollableFrame(content_frame, width = 200)
        category_frame.grid(row = 0, column = 0, sticky = "ns", padx =(0, 10))

        items_frame = customtkinter.CTkFrame(content_frame)
        items_frame.grid(row = 0, column = 2, sticky = "nsew")

        cart =[]
        cart_points =[0]
        lead_free_only =[False]

        subcat_scroll = None

        items_scroll = None
        lead_free_checkbox =[None]

        def update_cart_display():
            if max_points !="disabled":
                overflow_key = f"armory_overflow_{store.get('name', 'Unknown')}"
                overflow_amt = persistentdata.get(overflow_key, 0)or 0
                current_remaining = max_points +overflow_amt -points_used -cart_points[0]
                points_label.configure(text = f"Requisition Points: {current_remaining}/{max_points}(+{overflow_amt} overflow)(Cart: {cart_points[0]} pts)")
            else:
                points_label.configure(text = f"Unlimited Requisitions(Cart: {len(cart)} items)")

        def show_category_items(category_name):
            nonlocal subcat_scroll, items_scroll

            try:
                if subcat_scroll is not None:
                    try:
                        subcat_scroll.grid_forget()
                    except Exception:
                        logging.exception("Suppressed exception")
                    try:
                        subcat_scroll.destroy()
                    except Exception:
                        logging.exception("Suppressed exception")
                    subcat_scroll = None
            except Exception:
                logging.exception("Suppressed exception")
            try:
                if items_scroll is not None:
                    try:
                        items_scroll.pack_forget()
                    except Exception:
                        logging.exception("Suppressed exception")
                    try:
                        items_scroll.destroy()
                    except Exception:
                        logging.exception("Suppressed exception")
                    items_scroll = None
            except Exception:
                logging.exception("Suppressed exception")
            try:

                for widget in items_frame.winfo_children():
                    try:
                        widget.destroy()
                    except Exception:
                        try:
                            widget.grid_forget()
                        except Exception:
                            logging.exception("Suppressed exception")
            except Exception:
                logging.exception("Suppressed exception")

            try:
                selected_category[0]= category_name
                for name, btn in category_buttons.items():
                    try:
                        if name ==category_name:
                            btn.configure(border_color = "white", border_width = 2)
                        else:
                            btn.configure(border_width = 0)
                    except Exception:
                        logging.exception("Suppressed exception")
            except Exception:
                logging.exception("Suppressed exception")

            cat_items = categories.get(category_name, [])

            subcats = {}
            for it in cat_items:
                sub = it.get("armory_subcategory")or it.get("subtype")or "General"
                subcats.setdefault(sub, []).append(it)

            if len(subcats)<=1:
                if subcat_scroll is not None:
                    try:
                        subcat_scroll.grid_forget()
                    except Exception:
                        logging.exception("Suppressed exception")
                    try:
                        subcat_scroll.destroy()
                    except Exception:
                        logging.exception("Suppressed exception")
                    subcat_scroll = None

                try:

                    if items_scroll is not None:
                        try:
                            items_scroll.pack_forget()
                        except Exception:
                            logging.exception("Suppressed exception")
                        try:
                            items_scroll.destroy()
                        except Exception:
                            logging.exception("Suppressed exception")
                        items_scroll = None
                    items_frame.grid(row = 0, column = 1, sticky = "nsew")
                    content_frame.grid_columnconfigure(1, weight = 1)
                    content_frame.grid_columnconfigure(2, weight = 0)
                except Exception:
                    logging.exception("Suppressed exception")

            subcat_buttons_frame = None
            selected_subcat =[None]

            def render_item_list(items_list, parent = None):
                if parent is None:
                    parent = items_scroll if items_scroll is not None else items_frame
                for item in items_list:
                    is_ammo = item.get("_table_category")=="ammunition"
                    variants = item.get("variants", [])if is_ammo else[]

                    if is_ammo and lead_free_only[0]:
                        has_lead_free = any(v.get("lead_free", False)for v in variants)
                        if not has_lead_free:
                            continue

                    item_frame = customtkinter.CTkFrame(parent)
                    item_frame.pack(fill = "x", pady = 5, padx = 10)

                    is_highlighted = False
                    calibers = item.get("caliber", [])
                    if isinstance(calibers, str):
                        calibers =[calibers]

                    if item.get("_table_category")=="ammunition":
                        for cal in calibers:
                            if cal in equipped_calibers:
                                is_highlighted = True
                                break

                    if item.get("_table_category")=="magazines":
                        mag_system = item.get("magazinesystem")
                        if _mag_system_matches(mag_system):
                            for cal in calibers:
                                if cal in equipped_calibers:
                                    is_highlighted = True
                                    break

                    if not is_highlighted:
                        try:
                            is_attachment = bool(item.get('attachment')or item.get('accessory')or(item.get('_table_category')in('attachments', 'accessories')))
                            if is_attachment:
                                item_slots = item.get('slot')or item.get('attach_to')or item.get('accessory_slot')or item.get('parent_accessory_slot')or[]
                                if isinstance(item_slots, str):
                                    item_slots =[item_slots]
                                for s in item_slots:
                                    if s and s in equipped_attachment_slots:
                                        is_highlighted = True
                                        break
                        except Exception:
                            logging.exception("Suppressed exception")

                    if is_highlighted:
                        item_frame.configure(fg_color = "#2a4a2a")

                    name_text = self._format_item_name(item)
                    if is_highlighted:
                        name_text = "⭐ "+name_text

                    name_label = customtkinter.CTkLabel(item_frame, text = name_text, font = customtkinter.CTkFont(size = 13, weight = "bold"), anchor = "w")
                    name_label.pack(anchor = "w", padx = 10, pady =(8, 2))

                    if item.get("description"):
                        desc_label = customtkinter.CTkLabel(item_frame, text = item.get("description"), font = customtkinter.CTkFont(size = 10), text_color = "gray", wraplength = 500, justify = "left", anchor = "w")
                        desc_label.pack(anchor = "w", padx = 10, pady =(0, 5))

                    info_parts =[]
                    if item.get("weight"):
                        info_parts.append(f"Weight: {self._format_weight(item.get('weight'))}")
                    if item.get("caliber"):
                        cal = item.get("caliber")
                        if isinstance(cal, list):
                            cal = ", ".join(cal)
                        info_parts.append(f"Caliber: {cal}")
                    if item.get("rarity"):
                        info_parts.append(f"Rarity: {item.get('rarity')}")
                    if item.get("type"):
                        info_parts.append(f"Type: {item.get('type')}")
                    if item.get("pen"):
                        info_parts.append(f"Pen: {item.get('pen')}")
                    if item.get("ammo_labels") and isinstance(item.get("ammo_labels"), list):
                        info_parts.append(" / ".join(str(x) for x in item.get("ammo_labels") if x))

                    if info_parts:
                        info_label = customtkinter.CTkLabel(item_frame, text = " | ".join(info_parts), font = customtkinter.CTkFont(size = 10), text_color = "orange")
                        info_label.pack(anchor = "w", padx = 10, pady =(0, 5))

                    if is_ammo and variants:
                        variant_info_parts =[]
                        for v in variants:
                            pen = v.get("pen", "?")
                            ammo_type = v.get("type", "?")
                            lf = v.get("lead_free", False)
                            lf_indicator = " 🌿"if lf else ""
                            if lead_free_only[0]and not lf:
                                continue
                            labels = _get_ammo_variant_labels(v)
                            label_suffix = f" [{' / '.join(labels)}]" if labels else ""
                            variant_info_parts.append(f"{v.get('name', 'Unknown')}(Type: {ammo_type} | Pen: {pen}{lf_indicator}){label_suffix}")
                        if variant_info_parts:
                            variants_text = "Variants: "+", ".join(variant_info_parts)
                            variants_label = customtkinter.CTkLabel(item_frame, text = variants_text, font = customtkinter.CTkFont(size = 9), text_color = "#88aaff", wraplength = 500, justify = "left", anchor = "w")
                            variants_label.pack(anchor = "w", padx = 10, pady =(0, 5))

                    def add_to_cart(it = item):
                        if max_points !="disabled":
                            current_remaining = max_points -points_used -cart_points[0]
                            if current_remaining <1:
                                self._popup_show_info("No Points", "You don't have enough requisition points.", sound = "error")
                                return

                        table_category = it.get("_table_category")or it.get("table_category")

                        if table_category =="magazines":
                            mag_copy = it.copy()
                            mag_copy.pop("_table_category", None)
                            mag_copy.setdefault("rounds", [])

                            try:
                                load_var = customtkinter.BooleanVar(value = True)
                                dlg = customtkinter.CTkToplevel(self.root)
                                dlg.title('Load Magazine?')
                                dlg.transient(self.root)
                                chk = customtkinter.CTkCheckBox(dlg, text = 'Load magazine with ammunition', variable = load_var)
                                chk.pack(padx = 12, pady = 8)
                            except Exception:
                                load_var = None

                            def _open_shop_magazine_editor():
                                import tkinter as _tk_shop
                                try:
                                    ammo_table = tables.get('ammunition', [])
                                    mag_cal = mag_copy.get('caliber')
                                    if isinstance(mag_cal, str):
                                        mag_cal = [mag_cal]

                                    variant_map = {}
                                    for ammo_def in ammo_table:
                                        ammo_cal = ammo_def.get('caliber')
                                        if isinstance(ammo_cal, str):
                                            ammo_cal = [ammo_cal]
                                        if mag_cal and ammo_cal and any(c in ammo_cal for c in mag_cal):
                                            for var in ammo_def.get('variants', []):
                                                vn = var.get('name')
                                                if vn:
                                                    variant_map[vn] = (ammo_def, var)

                                    if not variant_map:
                                        self._popup_show_info('No Compatible Ammo', 'No compatible ammunition variants found for this magazine.', sound = 'error')
                                        return

                                    editor = customtkinter.CTkToplevel(self.root)
                                    editor.title('Magazine Loader')
                                    editor.transient(self.root)
                                    cap = int(mag_copy.get('capacity', 30) or 30)
                                    existing = list(mag_copy.get('rounds', []) or [])

                                    vlist = sorted(variant_map.keys())
                                    cpal = ['#c4a032', '#b87333', '#a0a0a0', '#d4af37', '#8b4513', '#cd7f32', '#e8c872', '#a08060']
                                    vcols = {v: cpal[i % len(cpal)] for i, v in enumerate(vlist)}

                                    vtips = {}
                                    variant_to_caliber = {}
                                    for vn, (ad, vr) in variant_map.items():
                                        t = vr.get('tip')
                                        if t and isinstance(t, str) and t.startswith('#'):
                                            vtips[vn] = t
                                        ac = ad.get('caliber')
                                        variant_to_caliber[vn] = (ac[0] if isinstance(ac, list) and ac else ac) or 'Unknown'
                                    _cg_raw = {}
                                    for vn in vlist:
                                        _cg_raw.setdefault(variant_to_caliber.get(vn, 'Unknown'), []).append(vn)
                                    caliber_order = sorted(_cg_raw.keys())
                                    caliber_groups = {k: sorted(v) for k, v in _cg_raw.items()}

                                    def _tip_for(vn):
                                        return vtips.get(vn, '#e0c060')

                                    def _tip_ol_for(vn):
                                        tc = vtips.get(vn)
                                        if not tc:
                                            return '#aa8820'
                                        try:
                                            r_v = int(tc[1:3], 16); g_v = int(tc[3:5], 16); b_v = int(tc[5:7], 16)
                                            return f'#{max(0, r_v - 40):02x}{max(0, g_v - 40):02x}{max(0, b_v - 40):02x}'
                                        except Exception:
                                            return '#aa8820'

                                    def _tip_for_round(r):
                                        if isinstance(r, dict):
                                            vn = r.get('variant') or r.get('name') or 'Unknown'
                                            return _tip_for(vn)
                                        return '#e0c060'

                                    def _tip_ol_for_round(r):
                                        if isinstance(r, dict):
                                            vn = r.get('variant') or r.get('name') or 'Unknown'
                                            return _tip_ol_for(vn)
                                        return '#aa8820'

                                    SLOT_H = 28; SLOT_W = 260; ox_mag = 20
                                    CHIP_W, CHIP_H, CHIP_PAD = 130, 28, 6
                                    CAL_HEADER_H = 18
                                    CAL_GROUP_PAD = 8
                                    _cols = max(1, (SLOT_W + 40) // (CHIP_W + CHIP_PAD))
                                    _sel_h_acc = 22
                                    for _cg in caliber_order:
                                        _cg_rows = max(1, (len(caliber_groups[_cg]) + _cols - 1) // _cols)
                                        _sel_h_acc += CAL_HEADER_H + _cg_rows * (CHIP_H + CHIP_PAD) + CAL_GROUP_PAD
                                    SEL_H = _sel_h_acc + 4
                                    HINT_H = 22
                                    MAG_TOP = SEL_H + HINT_H
                                    SPRING_H = 14
                                    canvas_h = MAG_TOP + cap * SLOT_H + SPRING_H + 8
                                    canvas_w = SLOT_W + 40

                                    main_frame = customtkinter.CTkFrame(editor)
                                    main_frame.grid(row = 0, column = 0, sticky = 'nsew', padx = 8, pady = 8)

                                    effective_h = min(canvas_h, 650)
                                    mag_canvas = _tk_shop.Canvas(main_frame, width = canvas_w, height = effective_h, bg = '#1a1a1a', highlightthickness = 1, highlightbackground = '#555555')
                                    if canvas_h > 650:
                                        _mc_scroll = _tk_shop.Scrollbar(main_frame, orient = 'vertical', command = mag_canvas.yview)
                                        _mc_scroll.pack(side = 'right', fill = 'y')
                                        mag_canvas.configure(yscrollcommand = _mc_scroll.set, scrollregion = (0, 0, canvas_w, canvas_h))
                                    mag_canvas.pack(side = 'left', fill = 'both', expand = True)

                                    side = customtkinter.CTkFrame(editor, fg_color = 'transparent', width = 180)
                                    side.grid(row = 0, column = 1, sticky = 'ns', padx = 8, pady = 8)

                                    ls = {'dragging': False, 'drag_vn': None, 'di': None, 'dt': None, 'do': None,
                                          'added': 0, 'stoggle': 0, 'animating': False}
                                    chip_hitboxes = {}

                                    def _draw_chips():
                                        mag_canvas.delete('chips')
                                        chip_hitboxes.clear()
                                        mag_canvas.create_text(canvas_w // 2, 10, text = 'AVAILABLE ROUNDS', fill = '#888888', font = ('Consolas', 9, 'bold'), tags = 'chips')
                                        if not vlist:
                                            mag_canvas.create_text(canvas_w // 2, SEL_H // 2 + 10, text = 'No rounds available', fill = '#555555', font = ('Consolas', 9), tags = 'chips')
                                            return
                                        cur_y = 22
                                        for cal in caliber_order:
                                            cal_vns = caliber_groups[cal]
                                            mag_canvas.create_text(6, cur_y + CAL_HEADER_H // 2, text = cal, fill = '#99aacc', font = ('Consolas', 9, 'bold'), anchor = 'w', tags = 'chips')
                                            cur_y += CAL_HEADER_H
                                            start_x = (canvas_w - min(len(cal_vns), _cols) * (CHIP_W + CHIP_PAD) + CHIP_PAD) // 2
                                            for idx, vn in enumerate(cal_vns):
                                                row_i = idx // _cols; col_i = idx % _cols
                                                x1 = start_x + col_i * (CHIP_W + CHIP_PAD)
                                                y1 = cur_y + row_i * (CHIP_H + CHIP_PAD)
                                                x2 = x1 + CHIP_W; y2 = y1 + CHIP_H
                                                chip_hitboxes[vn] = (x1, y1, x2, y2)
                                                c = vcols.get(vn, '#c4a032')
                                                mag_canvas.create_rectangle(x1, y1, x2, y2, fill = c, outline = '#dddddd', width = 1, tags = 'chips')
                                                mag_canvas.create_oval(x1 + 3, y1 + 3, x1 + 19, y2 - 3, fill = _tip_for(vn), outline = _tip_ol_for(vn), tags = 'chips')
                                                disp = vn if len(vn) <= 11 else vn[:10] + '\u2026'
                                                mag_canvas.create_text((x1 + x2) // 2 + 8, (y1 + y2) // 2, text = f'{disp} x\u221e', fill = '#1a1a1a', font = ('Consolas', 8, 'bold'), tags = 'chips')
                                            rows_for_cal = max(1, (len(cal_vns) + _cols - 1) // _cols)
                                            cur_y += rows_for_cal * (CHIP_H + CHIP_PAD) + CAL_GROUP_PAD

                                    def _draw_mag_body():
                                        mag_canvas.delete('mag')
                                        oy = MAG_TOP
                                        mag_canvas.create_text(canvas_w // 2, MAG_TOP - 10, text = '\u2193 DROP INTO MAGAZINE \u2193', fill = '#555555', font = ('Consolas', 9), tags = 'mag')
                                        mag_canvas.create_rectangle(ox_mag, oy, ox_mag + SLOT_W, oy + cap * SLOT_H, outline = '#888888', width = 2, tags = 'mag')
                                        mag_canvas.create_line(ox_mag, oy, ox_mag - 15, oy - 8, fill = '#888888', width = 2, tags = 'mag')
                                        mag_canvas.create_line(ox_mag + SLOT_W, oy, ox_mag + SLOT_W + 15, oy - 8, fill = '#888888', width = 2, tags = 'mag')
                                        for i in range(cap):
                                            sy = oy + i * SLOT_H
                                            if i > 0:
                                                mag_canvas.create_line(ox_mag, sy, ox_mag + SLOT_W, sy, fill = '#444444', dash = (2, 2), tags = 'mag')
                                            if i < len(existing):
                                                r = existing[i]
                                                vn = r.get('variant') if isinstance(r, dict) else str(r) if r else 'Unknown'
                                                c = vcols.get(vn, '#c4a032')
                                                mag_canvas.create_rectangle(ox_mag + 2, sy + 2, ox_mag + SLOT_W - 2, sy + SLOT_H - 2, fill = c, outline = '#222222', tags = 'mag')
                                                mag_canvas.create_oval(ox_mag + 4, sy + 4, ox_mag + 22, sy + SLOT_H - 4, fill = _tip_for_round(r), outline = _tip_ol_for_round(r), tags = 'mag')
                                                mag_canvas.create_text(ox_mag + SLOT_W // 2 + 10, sy + SLOT_H // 2, text = vn, fill = '#1a1a1a', font = ('Consolas', 9, 'bold'), tags = 'mag') # type: ignore
                                            else:
                                                mag_canvas.create_text(ox_mag + SLOT_W // 2, sy + SLOT_H // 2, text = '[empty]', fill = '#444444', font = ('Consolas', 9), tags = 'mag')
                                        by = oy + cap * SLOT_H
                                        mag_canvas.create_rectangle(ox_mag, by, ox_mag + SLOT_W, by + SPRING_H, fill = '#555555', outline = '#666666', tags = 'mag')
                                        mag_canvas.create_text(ox_mag + SLOT_W // 2, by + SPRING_H // 2, text = '\u25b2 SPRING \u25b2', fill = '#888888', font = ('Consolas', 8), tags = 'mag')

                                    def _draw_all():
                                        _draw_chips()
                                        _draw_mag_body()

                                    def _make_round(vname):
                                        pair = variant_map.get(vname)
                                        if not pair:
                                            return {'name': vname, 'caliber': mag_cal[0] if mag_cal else None, 'variant': vname}
                                        ammo_def, var = pair
                                        cal_val = mag_cal[0] if mag_cal and isinstance(mag_cal, (list, tuple)) else (mag_cal if mag_cal else ammo_def.get('caliber'))
                                        rd = {'name': ammo_def.get('name'), 'caliber': cal_val, 'variant': var.get('name'),
                                              'type': var.get('type'), 'pen': var.get('pen'), 'modifiers': var.get('modifiers'), 'tip': var.get('tip')}
                                        _apply_ammo_variant_data(rd, ammo_def, var)
                                        return rd

                                    def _play_insert():
                                        try:
                                            sn = f"bulletinsert{ls['stoggle']}"
                                            ls['stoggle'] = 1 - ls['stoggle']
                                            sound_path = os.path.join('sounds', 'firearms', 'universal', f'{sn}.ogg')
                                            if os.path.exists(sound_path):
                                                sound = pygame.mixer.Sound(sound_path)
                                                ch = pygame.mixer.find_channel()
                                                if ch:
                                                    ch.play(sound)
                                        except Exception:
                                            logging.exception("Suppressed exception")

                                    def _do_insert_data(vname):
                                        if len(existing) >= cap:
                                            return False
                                        r = _make_round(vname)
                                        existing.insert(0, r)
                                        ls['added'] += 1
                                        _play_insert()
                                        return True

                                    def _hit_chip(x, y):
                                        for vn, (x1, y1, x2, y2) in chip_hitboxes.items():
                                            if x1 <= x <= x2 and y1 <= y <= y2:
                                                return vn
                                        return None

                                    def _on_press(event):
                                        if ls['animating'] or len(existing) >= cap:
                                            return
                                        vn = _hit_chip(event.x, event.y)
                                        if not vn:
                                            return
                                        ls['dragging'] = True
                                        ls['drag_vn'] = vn
                                        c = vcols.get(vn, '#c4a032')
                                        ls['di'] = mag_canvas.create_rectangle(ox_mag + 2, event.y - SLOT_H // 2, ox_mag + SLOT_W - 2, event.y + SLOT_H // 2, fill = c, outline = '#ffffff', width = 2, tags = 'drag')
                                        ls['do'] = mag_canvas.create_oval(ox_mag + 4, event.y - SLOT_H // 2 + 2, ox_mag + 22, event.y + SLOT_H // 2 - 2, fill = _tip_for(vn), outline = _tip_ol_for(vn), tags = 'drag')
                                        ls['dt'] = mag_canvas.create_text(ox_mag + SLOT_W // 2 + 10, event.y, text = vn, fill = '#1a1a1a', font = ('Consolas', 10, 'bold'), tags = 'drag')

                                    def _on_move(event):
                                        if not ls['dragging']:
                                            return
                                        y = event.y
                                        if ls['di'] and ls['dt'] and ls['do']:
                                            mag_canvas.coords(ls['di'], ox_mag + 2, y - SLOT_H // 2, ox_mag + SLOT_W - 2, y + SLOT_H // 2)
                                            mag_canvas.coords(ls['do'], ox_mag + 4, y - SLOT_H // 2 + 2, ox_mag + 22, y + SLOT_H // 2 - 2)
                                            mag_canvas.coords(ls['dt'], ox_mag + SLOT_W // 2 + 10, y)

                                    def _on_release(event):
                                        if not ls['dragging']:
                                            return
                                        ls['dragging'] = False
                                        mag_canvas.delete('drag')
                                        ls['di'] = ls['dt'] = ls['do'] = None
                                        if len(existing) >= cap or ls['animating']:
                                            return
                                        vn = ls['drag_vn']
                                        if not vn:
                                            return
                                        if event.y >= MAG_TOP - 15:
                                            _animate_push_insert(vn)

                                    def _animate_push_insert(vname):
                                        ls['animating'] = True
                                        oy = MAG_TOP
                                        n_ex = len(existing)
                                        c_new = vcols.get(vname, '#c4a032')
                                        mag_canvas.delete('mag')
                                        mag_canvas.create_text(canvas_w // 2, MAG_TOP - 10, text = '\u2193 DROP INTO MAGAZINE \u2193', fill = '#555555', font = ('Consolas', 9), tags = 'magshell')
                                        mag_canvas.create_rectangle(ox_mag, oy, ox_mag + SLOT_W, oy + cap * SLOT_H, outline = '#888888', width = 2, tags = 'magshell')
                                        mag_canvas.create_line(ox_mag, oy, ox_mag - 15, oy - 8, fill = '#888888', width = 2, tags = 'magshell')
                                        mag_canvas.create_line(ox_mag + SLOT_W, oy, ox_mag + SLOT_W + 15, oy - 8, fill = '#888888', width = 2, tags = 'magshell')
                                        for si in range(1, cap):
                                            _sy = oy + si * SLOT_H
                                            mag_canvas.create_line(ox_mag, _sy, ox_mag + SLOT_W, _sy, fill = '#444444', dash = (2, 2), tags = 'magshell')
                                        _by = oy + cap * SLOT_H
                                        mag_canvas.create_rectangle(ox_mag, _by, ox_mag + SLOT_W, _by + SPRING_H, fill = '#555555', outline = '#666666', tags = 'magshell')
                                        mag_canvas.create_text(ox_mag + SLOT_W // 2, _by + SPRING_H // 2, text = '\u25b2 SPRING \u25b2', fill = '#888888', font = ('Consolas', 8), tags = 'magshell')
                                        for ei in range(n_ex, cap):
                                            _esy = oy + ei * SLOT_H
                                            mag_canvas.create_text(ox_mag + SLOT_W // 2, _esy + SLOT_H // 2, text = '[empty]', fill = '#444444', font = ('Consolas', 9), tags = 'magshell')
                                        anim_ids = []
                                        for i in range(n_ex):
                                            r = existing[i]
                                            vn_e = r.get('variant') if isinstance(r, dict) else str(r) if r else 'Unknown'
                                            c_e = vcols.get(vn_e, '#c4a032')
                                            sy = oy + i * SLOT_H
                                            _ri = mag_canvas.create_rectangle(ox_mag + 2, sy + 2, ox_mag + SLOT_W - 2, sy + SLOT_H - 2, fill = c_e, outline = '#222222', tags = 'pushanim')
                                            _oi = mag_canvas.create_oval(ox_mag + 4, sy + 4, ox_mag + 22, sy + SLOT_H - 4, fill = _tip_for_round(r), outline = _tip_ol_for_round(r), tags = 'pushanim')
                                            _ti = mag_canvas.create_text(ox_mag + SLOT_W // 2 + 10, sy + SLOT_H // 2, text = vn_e, fill = '#1a1a1a', font = ('Consolas', 9, 'bold'), tags = 'pushanim') # type: ignore
                                            anim_ids.append((_ri, _oi, _ti, float(sy)))
                                        new_start_y = float(oy - SLOT_H - 4)
                                        new_target_y = float(oy)
                                        _nr = mag_canvas.create_rectangle(ox_mag + 2, new_start_y + 2, ox_mag + SLOT_W - 2, new_start_y + SLOT_H - 2, fill = c_new, outline = '#ffffff', width = 2, tags = 'pushanim')
                                        _no = mag_canvas.create_oval(ox_mag + 4, new_start_y + 4, ox_mag + 22, new_start_y + SLOT_H - 4, fill = _tip_for(vname), outline = _tip_ol_for(vname), tags = 'pushanim')
                                        _nt = mag_canvas.create_text(ox_mag + SLOT_W // 2 + 10, new_start_y + SLOT_H // 2, text = vname, fill = '#1a1a1a', font = ('Consolas', 10, 'bold'), tags = 'pushanim')
                                        total_steps = 10
                                        push_per_step = float(SLOT_H) / total_steps
                                        new_per_step = (new_target_y - new_start_y) / total_steps
                                        def _push_step(step):
                                            if step >= total_steps:
                                                mag_canvas.delete('pushanim')
                                                mag_canvas.delete('magshell')
                                                _do_insert_data(vname)
                                                _draw_all()
                                                _update_side()
                                                ls['animating'] = False
                                                return
                                            frac = step + 1
                                            for _ri, _oi, _ti, base_y in anim_ids:
                                                cy = base_y + frac * push_per_step
                                                mag_canvas.coords(_ri, ox_mag + 2, cy + 2, ox_mag + SLOT_W - 2, cy + SLOT_H - 2)
                                                mag_canvas.coords(_oi, ox_mag + 4, cy + 4, ox_mag + 22, cy + SLOT_H - 4)
                                                mag_canvas.coords(_ti, ox_mag + SLOT_W // 2 + 10, cy + SLOT_H // 2)
                                            cn = new_start_y + frac * new_per_step
                                            mag_canvas.coords(_nr, ox_mag + 2, cn + 2, ox_mag + SLOT_W - 2, cn + SLOT_H - 2)
                                            mag_canvas.coords(_no, ox_mag + 4, cn + 4, ox_mag + 22, cn + SLOT_H - 4)
                                            mag_canvas.coords(_nt, ox_mag + SLOT_W // 2 + 10, cn + SLOT_H // 2)
                                            editor.after(25, lambda: _push_step(step + 1))
                                        _push_step(0)

                                    mag_canvas.bind('<Button-1>', _on_press)
                                    mag_canvas.bind('<B1-Motion>', _on_move)
                                    mag_canvas.bind('<ButtonRelease-1>', _on_release)

                                    _cap_lbl = customtkinter.CTkLabel(side, text = f'{len(existing)}/{cap} rounds loaded', font = customtkinter.CTkFont(size = 13, weight = 'bold'))
                                    _cap_lbl.pack(pady = (10, 6))
                                    customtkinter.CTkLabel(side, text = 'Click & drag a round\nfrom the top area down\ninto the magazine', font = customtkinter.CTkFont(size = 10), text_color = '#888888', wraplength = 170).pack(pady = 6)

                                    def _update_side():
                                        _cap_lbl.configure(text = f'{len(existing)}/{cap} rounds loaded')

                                    _shop_reloader = {'hooked': False, 'ch': None, 'btn': None, 'unhook_btn': None}

                                    def _stop_shop_reloader():
                                        if _shop_reloader['ch']:
                                            try:
                                                _shop_reloader['ch'].stop()
                                            except Exception:
                                                logging.exception("Suppressed exception")
                                            _shop_reloader['ch'] = None

                                    def _start_shop_reloader_loop():
                                        try:
                                            rpath = os.path.join('sounds', 'firearms', 'universal', 'reloaderloop.ogg')
                                            if os.path.exists(rpath):
                                                snd = pygame.mixer.Sound(rpath)
                                                ch = pygame.mixer.find_channel()
                                                if ch:
                                                    ch.play(snd, loops = -1)
                                                    _shop_reloader['ch'] = ch
                                        except Exception:
                                            logging.exception("Suppressed exception")

                                    def _play_shop_reloader_insert():
                                        dur = 200
                                        try:
                                            rpath = os.path.join('sounds', 'firearms', 'universal', 'reloaderroundinsert.ogg')
                                            if os.path.exists(rpath):
                                                snd = pygame.mixer.Sound(rpath)
                                                dur = max(int(snd.get_length() * 1000), 100)
                                                ch = pygame.mixer.find_channel()
                                                if ch:
                                                    ch.play(snd)
                                        except Exception:
                                            logging.exception("Suppressed exception")
                                        return dur

                                    def _shop_reloader_auto_fill(vname):
                                        if ls['animating'] or len(existing) >= cap:
                                            return
                                        ls['animating'] = True
                                        _shop_reloader['hooked'] = True
                                        if _shop_reloader.get('btn'):
                                            try:
                                                _shop_reloader['btn'].configure(state = 'disabled')
                                            except Exception:
                                                logging.exception("Suppressed exception")
                                        insert_dur = _play_shop_reloader_insert()
                                        def _start_loop_and_fill():
                                            _start_shop_reloader_loop()
                                            _shop_reloader_fill_step(vname)
                                        editor.after(max(insert_dur, 100), _start_loop_and_fill)

                                    def _shop_reloader_fill_step(vname):
                                        if len(existing) >= cap:
                                            _stop_shop_reloader()
                                            ls['animating'] = False
                                            _draw_all()
                                            _update_side()
                                            if _shop_reloader.get('unhook_btn'):
                                                try:
                                                    _shop_reloader['unhook_btn'].configure(state = 'normal')
                                                except Exception:
                                                    logging.exception("Suppressed exception")
                                            return
                                        r = _make_round(vname)
                                        existing.insert(0, r)
                                        ls['added'] += 1
                                        _play_insert()
                                        _draw_all()
                                        _update_side()
                                        editor.after(100, lambda: _shop_reloader_fill_step(vname))

                                    def _unhook_shop_reloader():
                                        _stop_shop_reloader()
                                        _shop_reloader['hooked'] = False
                                        ls['animating'] = False
                                        if _shop_reloader.get('btn'):
                                            try:
                                                _shop_reloader['btn'].configure(state = 'normal')
                                            except Exception:
                                                logging.exception("Suppressed exception")
                                        if _shop_reloader.get('unhook_btn'):
                                            try:
                                                _shop_reloader['unhook_btn'].configure(state = 'disabled')
                                            except Exception:
                                                logging.exception("Suppressed exception")
                                        _play_shop_reloader_insert()

                                    def _use_shop_reloader():
                                        if ls['animating'] or _shop_reloader['hooked']:
                                            return
                                        if len(vlist) == 0:
                                            return
                                        if len(vlist) == 1:
                                            _shop_reloader_auto_fill(vlist[0])
                                            return
                                        _avail_cal_groups = {}
                                        for vn in vlist:
                                            cal = variant_to_caliber.get(vn, 'Unknown')
                                            _avail_cal_groups.setdefault(cal, []).append(vn)
                                        _calibers = sorted(_avail_cal_groups.keys())
                                        def _open_variant_picker(cal_vns):
                                            sel_popup = customtkinter.CTkToplevel(editor)
                                            sel_popup.title('Select Round Type')
                                            sel_popup.transient(editor)
                                            sel_popup.grab_set()
                                            customtkinter.CTkLabel(sel_popup, text = 'Select variant for reloader:', font = customtkinter.CTkFont(size = 12)).pack(pady = 8)
                                            sel_var = customtkinter.StringVar(value = cal_vns[0])
                                            sf = customtkinter.CTkScrollableFrame(sel_popup, height = min(240, len(cal_vns) * 36 + 10), width = 260)
                                            sf.pack(fill = 'x', padx = 8, pady = 4)
                                            for vn in cal_vns:
                                                customtkinter.CTkRadioButton(sf, text = f'{vn} (x\u221e)', variable = sel_var, value = vn).pack(anchor = 'w', padx = 8, pady = 2)
                                            def _go():
                                                v = sel_var.get()
                                                sel_popup.destroy()
                                                _shop_reloader_auto_fill(v)
                                            customtkinter.CTkButton(sel_popup, text = 'Hook Up & Load', command = _go, width = 160).pack(pady = 8)
                                            customtkinter.CTkButton(sel_popup, text = 'Cancel', command = sel_popup.destroy, width = 120, fg_color = '#444444').pack(pady = 4)
                                            sel_popup.update_idletasks()
                                            _sw2 = sel_popup.winfo_screenwidth(); _sh2 = sel_popup.winfo_screenheight()
                                            _pw = sel_popup.winfo_reqwidth(); _ph = sel_popup.winfo_reqheight()
                                            sel_popup.geometry(f'+{_sw2 // 2 - _pw // 2}+{max(0, _sh2 // 2 - _ph // 2)}')
                                            sel_popup.lift()
                                            self._safe_focus(sel_popup)
                                        if len(_calibers) == 1:
                                            _open_variant_picker(vlist)
                                            return
                                        cal_popup = customtkinter.CTkToplevel(editor)
                                        cal_popup.title('Select Caliber')
                                        cal_popup.transient(editor)
                                        cal_popup.grab_set()
                                        customtkinter.CTkLabel(cal_popup, text = 'Select caliber to load:', font = customtkinter.CTkFont(size = 12)).pack(pady = 8)
                                        for cal in _calibers:
                                            cal_vns = list(_avail_cal_groups[cal])
                                            def _pick(cv = cal_vns):
                                                cal_popup.destroy()
                                                _open_variant_picker(cv)
                                            customtkinter.CTkButton(cal_popup, text = cal, command = _pick, width = 220, height = 32).pack(padx = 16, pady = 4)
                                        customtkinter.CTkButton(cal_popup, text = 'Cancel', command = cal_popup.destroy, width = 120, fg_color = '#444444').pack(pady = 8)
                                        cal_popup.update_idletasks()
                                        _sw3 = cal_popup.winfo_screenwidth(); _sh3 = cal_popup.winfo_screenheight()
                                        _cw = cal_popup.winfo_reqwidth(); _ch2 = cal_popup.winfo_reqheight()
                                        cal_popup.geometry(f'+{_sw3 // 2 - _cw // 2}+{max(0, _sh3 // 2 - _ch2 // 2)}')
                                        cal_popup.lift()
                                        self._safe_focus(cal_popup)

                                    _shop_reloader['btn'] = customtkinter.CTkButton(side, text = '\u2699 Use Reloader', command = _use_shop_reloader, width = 160, height = 30, font = customtkinter.CTkFont(size = 11), fg_color = '#2a6a2a', hover_color = '#3a7a3a')
                                    _shop_reloader['btn'].pack(pady = 4)
                                    _shop_reloader['unhook_btn'] = customtkinter.CTkButton(side, text = '\u2716 Unhook Reloader', command = _unhook_shop_reloader, width = 160, height = 30, font = customtkinter.CTkFont(size = 11), fg_color = '#6a2a2a', hover_color = '#7a3a3a', state = 'disabled')
                                    _shop_reloader['unhook_btn'].pack(pady = 4)

                                    def _apply():
                                        if _shop_reloader.get('hooked'):
                                            self._popup_show_info('Reloader', 'Please unhook the reloader first!')
                                            return
                                        _stop_shop_reloader()
                                        mag_copy['rounds'] = existing[:cap]
                                        editor.destroy()
                                        cart.append(mag_copy)
                                        cart_points[0] += 1
                                        update_cart_display()
                                        self._play_ui_sound('click')
                                        logging.info(f"Added magazine to cart: {mag_copy.get('name')}")
                                        dlg.destroy()

                                    editor.protocol('WM_DELETE_WINDOW', lambda: (self._popup_show_info('Reloader', 'Please unhook the reloader first!') if _shop_reloader.get('hooked') else editor.destroy()))
                                    customtkinter.CTkButton(side, text = 'Apply', command = _apply, width = 160, height = 35, font = customtkinter.CTkFont(size = 12)).pack(pady = 10)
                                    customtkinter.CTkButton(side, text = 'Cancel', command = lambda: (self._popup_show_info('Reloader', 'Please unhook the reloader first!') if _shop_reloader.get('hooked') else editor.destroy()), width = 160, height = 30, fg_color = '#444444').pack(pady = 4)

                                    _draw_all()
                                    editor.update_idletasks()
                                    ew = max(editor.winfo_reqwidth(), 520)
                                    eh = max(editor.winfo_reqheight(), 420)
                                    _sw_s = editor.winfo_screenwidth(); _sh_s = editor.winfo_screenheight()
                                    x = (_sw_s // 2) - (ew // 2); y = (_sh_s // 2) - (eh // 2)
                                    editor.geometry(f'{ew}x{eh}+{x}+{y}')
                                    editor.grab_set()
                                    editor.lift()
                                    self._safe_focus(editor)
                                except Exception:
                                    logging.exception('Failed to open shop magazine editor')

                            btn_frame = customtkinter.CTkFrame(dlg, fg_color = 'transparent')
                            btn_frame.pack(fill = 'x', padx = 8, pady = 8)

                            def _add_plain():
                                cart.append(mag_copy)
                                cart_points[0]+=1
                                update_cart_display()
                                self._play_ui_sound('click')
                                logging.info(f"Added magazine to cart: {mag_copy.get('name')}")
                                dlg.destroy()
                                return

                            open_editor_btn = customtkinter.CTkButton(btn_frame, text = 'Open Editor', command = _open_shop_magazine_editor, width = 140)
                            open_editor_btn.pack(side = 'left', padx = 6)
                            add_plain_btn = customtkinter.CTkButton(btn_frame, text = 'Add(Empty)', command = _add_plain, width = 140)
                            add_plain_btn.pack(side = 'left', padx = 6)
                            cancel_btn = customtkinter.CTkButton(btn_frame, text = 'Cancel', command = dlg.destroy, width = 120, fg_color = '#444444')
                            cancel_btn.pack(side = 'left', padx = 6)

                            dlg.grab_set()
                            dlg.lift()
                            self._safe_focus(dlg)
                            return

                        if table_category =="ammunition":
                            ammo_def = it
                            variants = ammo_def.get("variants", [])
                            sel_var = None
                            if variants:
                                if lead_free_only[0]:
                                    variants =[v for v in variants if v.get("lead_free", False)]
                                if not variants:
                                    self._popup_show_info("No Lead-Free Variants", "No lead-free variants available for this ammunition.", sound = "error")
                                    return
                                opts =[]
                                for v in variants:
                                    pen = v.get("pen", "?")
                                    ammo_type = v.get("type", "?")
                                    lf = v.get("lead_free", False)
                                    lf_indicator = " 🌿"if lf else ""
                                    labels = _get_ammo_variant_labels(v)
                                    label_suffix = f" [{' / '.join(labels)}]" if labels else ""
                                    opts.append(f"{v.get('name')}(Type: {ammo_type} | Pen: {pen}{lf_indicator}){label_suffix}")
                                sel_var = self._popup_select_option("Ammo Variant", "Choose ammo variant:", opts)
                                if sel_var is None:
                                    return
                                sel_name = sel_var.split("(Type:")[0].strip()
                                chosen = next((v for v in variants if v.get("name")==sel_name), None)
                            else:
                                chosen = None

                            qty = self._popup_ask_integer("Quantity", "How many rounds to requisition?", initial_value = 10, min_value = 1, max_value = 999)
                            if qty is None:
                                return

                            raw_cal = ammo_def.get("caliber")
                            if isinstance(raw_cal, (list, tuple))and raw_cal:
                                cal_val = raw_cal[0]
                            else:
                                cal_val = raw_cal

                            unit_weight = None
                            if ammo_def.get("weight")is not None:
                                try:
                                    unit_weight = float(ammo_def.get("weight"))
                                except Exception:
                                    unit_weight = None

                            stack_item = {
                            "name":ammo_def.get("name", "Ammunition"),
                            "caliber":cal_val,
                            "variant":chosen.get("name")if chosen else None,
                            "quantity":int(qty)
                            }
                            if unit_weight is not None:
                                stack_item["weight"]= unit_weight

                            if chosen:
                                _apply_ammo_variant_data(stack_item, ammo_def, chosen)
                            else:
                                for k in["type", "pen", "modifiers", "tip", "rarity"]:
                                    if k in ammo_def:
                                        stack_item[k]= ammo_def.get(k)

                            cart.append(stack_item)
                            cart_points[0]+=1
                            update_cart_display()
                            self._play_ui_sound("click")
                            logging.info(f"Added ammo to cart: {stack_item.get('name')} x{stack_item.get('quantity')}")
                            return

                        cart.append(it.copy())
                        cart_points[0]+=1
                        update_cart_display()
                        self._play_ui_sound("click")
                        logging.info(f"Added to cart: {it.get('name')}")

                    add_btn = self._create_sound_button(item_frame, "Requisition(+1 pt)", add_to_cart, width = 150, height = 30, font = customtkinter.CTkFont(size = 11))
                    add_btn.pack(anchor = "e", padx = 10, pady = 8)

            if len(subcats)>1:

                try:
                    items_frame.grid_rowconfigure(0, weight = 1)
                    items_frame.grid_columnconfigure(0, weight = 1)
                except Exception:
                    logging.exception("Suppressed exception")

                subcat_scroll = customtkinter.CTkScrollableFrame(content_frame, width = 180)
                subcat_scroll.grid(row = 0, column = 1, sticky = "ns", padx =(10, 6), pady =(0, 6))

                try:
                    items_frame.grid(row = 0, column = 2, sticky = "nsew")
                    content_frame.grid_columnconfigure(1, weight = 0)
                    content_frame.grid_columnconfigure(2, weight = 1)
                except Exception:
                    logging.exception("Suppressed exception")

                content_right = customtkinter.CTkFrame(items_frame)
                content_right.grid(row = 0, column = 0, sticky = "nsew")

                try:
                    items_scroll = customtkinter.CTkScrollableFrame(content_right)
                    items_scroll.pack(fill = "both", expand = True, padx = 0, pady = 0)
                except Exception:
                    items_scroll = None

                subcat_buttons = {}

                def _render_subcat_items(name, sub_items, target_frame, scroll_holder):
                    for _w in target_frame.winfo_children():
                        try:
                            _w.destroy()
                        except Exception:
                            logging.exception("Suppressed exception")

                    sub2cats = {}
                    for it2 in sub_items:
                        s2 = it2.get("armory_subcategory2") or "General"
                        sub2cats.setdefault(s2, []).append(it2)

                    if len(sub2cats) <= 1:
                        try:
                            _single_scroll = customtkinter.CTkScrollableFrame(target_frame)
                            _single_scroll.pack(fill = "both", expand = True)
                        except Exception:
                            _single_scroll = target_frame

                        sub_title = customtkinter.CTkLabel(_single_scroll, text = name, font = customtkinter.CTkFont(size = 16, weight = "bold"))
                        sub_title.pack(pady =(6, 12), anchor = "w", padx = 10)
                        render_item_list(sub_items, parent = _single_scroll)
                    else:
                        sub2_layout = customtkinter.CTkFrame(target_frame, fg_color = "transparent")
                        sub2_layout.pack(fill = "both", expand = True)

                        sub2_layout.grid_rowconfigure(0, weight = 1)
                        sub2_layout.grid_columnconfigure(0, weight = 0)
                        sub2_layout.grid_columnconfigure(1, weight = 1)

                        sub2_scroll = customtkinter.CTkScrollableFrame(sub2_layout, width = 150)
                        sub2_scroll.grid(row = 0, column = 0, sticky = "ns", padx =(0, 6))

                        sub2_right = customtkinter.CTkFrame(sub2_layout)
                        sub2_right.grid(row = 0, column = 1, sticky = "nsew")

                        try:
                            sub2_items_scroll = customtkinter.CTkScrollableFrame(sub2_right)
                            sub2_items_scroll.pack(fill = "both", expand = True, padx = 0, pady = 0)
                        except Exception:
                            sub2_items_scroll = None

                        sub2_buttons = {}
                        selected_sub2 = [None]

                        def make_sub2_btn(s2name):
                            def on_click():
                                for w2 in sub2_right.winfo_children():
                                    w2.destroy()
                                try:
                                    s2_scroll = customtkinter.CTkScrollableFrame(sub2_right)
                                    s2_scroll.pack(fill = "both", expand = True, padx = 0, pady = 0)
                                except Exception:
                                    s2_scroll = None
                                s2_title = customtkinter.CTkLabel(sub2_right, text = s2name, font = customtkinter.CTkFont(size = 16, weight = "bold"))
                                s2_title.pack(pady =(6, 12), anchor = "w", padx = 10)
                                render_item_list(sub2cats.get(s2name, []), parent = s2_scroll if s2_scroll is not None else sub2_right)
                                selected_sub2[0] = s2name
                                for nm2, b2 in sub2_buttons.items():
                                    try:
                                        if nm2 == s2name:
                                            b2.configure(border_color = "white", border_width = 2)
                                        else:
                                            b2.configure(border_width = 0)
                                    except Exception:
                                        logging.exception("Suppressed exception")
                            return on_click

                        for s2name in sorted(sub2cats.keys()):
                            has_highlighted2 = False
                            for it2 in sub2cats.get(s2name, []):
                                calibers2 = it2.get("caliber", [])
                                if isinstance(calibers2, str):
                                    calibers2 = [calibers2]
                                if it2.get("_table_category") == "ammunition":
                                    for cal2 in calibers2:
                                        if cal2 in equipped_calibers:
                                            has_highlighted2 = True
                                            break
                                if has_highlighted2:
                                    break
                                if it2.get("_table_category") == "magazines":
                                    mag_sys2 = it2.get("magazinesystem")
                                    if _mag_system_matches(mag_sys2):
                                        for cal2 in calibers2:
                                            if cal2 in equipped_calibers:
                                                has_highlighted2 = True
                                                break
                                if has_highlighted2:
                                    break
                            btn_text2 = s2name if not has_highlighted2 else ("⭐ " + s2name)
                            btn_kwargs2 = {"width": 130, "height": 30, "font": customtkinter.CTkFont(size = 10)}
                            if has_highlighted2:
                                btn_kwargs2["fg_color"] = "#2a8a2a"
                            btn2 = self._create_sound_button(sub2_scroll, btn_text2, make_sub2_btn(s2name), **btn_kwargs2)
                            btn2.pack(fill = "x", pady = 3, padx = 6)
                            sub2_buttons[s2name] = btn2

                        first2 = sorted(sub2cats.keys())[0]
                        s2_title = customtkinter.CTkLabel(sub2_right, text = first2, font = customtkinter.CTkFont(size = 16, weight = "bold"))
                        s2_title.pack(pady =(6, 12), anchor = "w", padx = 10)
                        render_item_list(sub2cats.get(first2, []), parent = sub2_items_scroll if sub2_items_scroll is not None else sub2_right)
                        selected_sub2[0] = first2
                        for nm2, b2 in sub2_buttons.items():
                            try:
                                if nm2 == first2:
                                    b2.configure(border_color = "white", border_width = 2)
                                else:
                                    b2.configure(border_width = 0)
                            except Exception:
                                logging.exception("Suppressed exception")

                def make_subcat_btn(name):
                    def on_click():
                        nonlocal items_scroll

                        for w in content_right.winfo_children():
                            w.destroy()

                        try:
                            items_scroll = customtkinter.CTkScrollableFrame(content_right)
                            items_scroll.pack(fill = "both", expand = True, padx = 0, pady = 0)
                        except Exception:
                            items_scroll = None
                        _render_subcat_items(name, subcats.get(name, []), content_right, items_scroll)
                        selected_subcat[0]= name

                        for nm, b in subcat_buttons.items():
                            try:
                                if nm ==name:
                                    b.configure(border_color = "white", border_width = 2)
                                else:
                                    b.configure(border_width = 0)
                            except Exception:
                                logging.exception("Suppressed exception")
                    return on_click

                for sname in sorted(subcats.keys()):

                    has_highlighted = False
                    for it in subcats.get(sname, []):
                        calibers = it.get("caliber", [])
                        if isinstance(calibers, str):
                            calibers =[calibers]
                        if it.get("_table_category")=="ammunition":
                            for cal in calibers:
                                if cal in equipped_calibers:
                                    has_highlighted = True
                                    break
                        if has_highlighted:
                            break
                        if it.get("_table_category")=="magazines":
                            mag_system = it.get("magazinesystem")
                            if _mag_system_matches(mag_system):
                                for cal in calibers:
                                    if cal in equipped_calibers:
                                        has_highlighted = True
                                        break
                        if has_highlighted:
                            break
                    btn_text = sname if not has_highlighted else("⭐ "+sname)
                    btn_kwargs = {"width":160, "height":30, "font":customtkinter.CTkFont(size = 10)}
                    if has_highlighted:
                        btn_kwargs["fg_color"]= "#2a8a2a"
                    btn = self._create_sound_button(subcat_scroll, btn_text, make_subcat_btn(sname), **btn_kwargs)
                    btn.pack(fill = "x", pady = 3, padx = 6)
                    subcat_buttons[sname]= btn

                first = sorted(subcats.keys())[0]
                _render_subcat_items(first, subcats.get(first, []), content_right, items_scroll)
                selected_subcat[0]= first

                for nm, b in subcat_buttons.items():
                    try:
                        if nm ==first:
                            b.configure(border_color = "white", border_width = 2)
                        else:
                            b.configure(border_width = 0)
                    except Exception:
                        logging.exception("Suppressed exception")

                try:
                    if subcat_scroll is not None and len(subcat_scroll.winfo_children())==0:
                        subcat_scroll.destroy()
                        subcat_scroll = None
                        items_frame.grid(row = 0, column = 1, sticky = "nsew")
                        content_frame.grid_columnconfigure(1, weight = 1)
                        content_frame.grid_columnconfigure(2, weight = 0)
                except Exception:
                    logging.exception("Suppressed exception")
            else:

                try:
                    items_scroll = customtkinter.CTkScrollableFrame(items_frame)
                    items_scroll.pack(fill = "both", expand = True, padx = 0, pady = 0)
                except Exception:
                    items_scroll = None

                is_ammo_category = "ammunition"in category_name.lower()or "ammo"in category_name.lower()

                if items_scroll is not None:
                    header_frame_cat = customtkinter.CTkFrame(items_scroll, fg_color = "transparent")
                    header_frame_cat.pack(fill = "x", pady =(10, 6), padx = 10)

                    cat_title = customtkinter.CTkLabel(header_frame_cat, text = category_name, font = customtkinter.CTkFont(size = 18, weight = "bold"))
                    cat_title.pack(side = "left")

                    if is_ammo_category:
                        def toggle_lead_free():
                            lead_free_only[0]= not lead_free_only[0]
                            show_category_items(category_name)

                        lf_check_var = customtkinter.BooleanVar(value = lead_free_only[0])
                        lf_checkbox = customtkinter.CTkCheckBox(
                        header_frame_cat,
                        text = "Lead-Free Only 🌿",
                        variable = lf_check_var,
                        command = toggle_lead_free,
                        font = customtkinter.CTkFont(size = 11),
                        text_color = "#7CFC00"
                        )
                        lf_checkbox.pack(side = "right", padx = 10)
                        lead_free_checkbox[0]= lf_checkbox # type: ignore

                    render_item_list(cat_items, parent = items_scroll)
                else:
                    cat_title = customtkinter.CTkLabel(items_frame, text = category_name, font = customtkinter.CTkFont(size = 18, weight = "bold"))
                    cat_title.pack(pady =(10, 6), anchor = "w", padx = 10)
                    render_item_list(cat_items, parent = items_frame)

        sorted_categories = sorted(categories.keys())

        ammo_mags_first =[]
        others =[]
        for cat in sorted_categories:
            if cat.lower()in["ammunition", "magazines", "ammo"]:
                ammo_mags_first.append(cat)
            else:
                others.append(cat)
        sorted_categories = ammo_mags_first +others

        category_buttons = {}
        selected_category =[None]
        for cat_name in sorted_categories:
            has_highlighted = False
            for item in categories.get(cat_name, []):
                calibers = item.get("caliber", [])
                if isinstance(calibers, str):
                    calibers =[calibers]
                for cal in calibers:
                    if cal in equipped_calibers:
                        has_highlighted = True
                        break
                if has_highlighted:
                    break

            btn_text = cat_name
            if has_highlighted:
                btn_text = "⭐ "+cat_name

            cat_kwargs = {"width":180, "height":35, "font":customtkinter.CTkFont(size = 11)}
            if has_highlighted:
                cat_kwargs["fg_color"]= "#2a8a2a"
            cat_btn = self._create_sound_button(category_frame, btn_text, lambda c = cat_name:show_category_items(c), **cat_kwargs)
            cat_btn.pack(pady = 3, padx = 5)
            category_buttons[cat_name]= cat_btn

        if sorted_categories:

            selected_category[0]= sorted_categories[0]

            for name, btn in category_buttons.items():
                try:
                    if name ==selected_category[0]:
                        btn.configure(border_color = "white", border_width = 2)
                    else:
                        btn.configure(border_width = 0)
                except Exception:
                    logging.exception("Suppressed exception")
            show_category_items(sorted_categories[0])

        button_frame = customtkinter.CTkFrame(main_frame, fg_color = "transparent")
        button_frame.grid(row = 2, column = 0, sticky = "ew", padx = 20, pady = 10)

        def view_cart():
            if not cart:
                self._popup_show_info("Empty Cart", "Your requisition cart is empty.", sound = "popup")
                return

            cart_popup = customtkinter.CTkToplevel(self.root)
            cart_popup.title("Requisition Cart")
            cart_popup.geometry("600x500")
            cart_popup.transient(self.root)

            cart_scroll = customtkinter.CTkScrollableFrame(cart_popup)
            cart_scroll.pack(fill = "both", expand = True, padx = 10, pady = 10)

            for idx, item in enumerate(cart):
                item_frame = customtkinter.CTkFrame(cart_scroll)
                item_frame.pack(fill = "x", pady = 3)

                customtkinter.CTkLabel(item_frame, text = f"{self._format_item_name(item)}(1 pt)", font = customtkinter.CTkFont(size = 12)).pack(side = "left", padx = 10, pady = 5)

                def remove_item(i = idx):
                    cart.pop(i)
                    cart_points[0]-=1
                    update_cart_display()
                    cart_popup.destroy()
                    view_cart()

                remove_btn = customtkinter.CTkButton(item_frame, text = "Remove", command = remove_item, width = 80, height = 25)
                remove_btn.pack(side = "right", padx = 10, pady = 5)

            total_label = customtkinter.CTkLabel(cart_popup, text = f"Total: {cart_points[0]} points", font = customtkinter.CTkFont(size = 14, weight = "bold"))
            total_label.pack(pady = 10)

            def clear_cart():
                cart.clear()
                cart_points[0]= 0
                update_cart_display()
                cart_popup.destroy()

            clear_btn = customtkinter.CTkButton(cart_popup, text = "Clear Cart", command = clear_cart, width = 150)
            clear_btn.pack(pady = 5)

            close_btn = customtkinter.CTkButton(cart_popup, text = "Close", command = cart_popup.destroy, width = 150)
            close_btn.pack(pady = 5)

            try:
                cart_popup.update_idletasks()
                cart_popup.deiconify()
                cart_popup.lift()
                cart_popup.grab_set()
                self._safe_focus(cart_popup)
            except Exception:
                try:
                    cart_popup.grab_set()
                except Exception:
                    logging.exception("Suppressed exception")

        def checkout():
            if not cart:
                self._popup_show_info("Empty Cart", "Your requisition cart is empty.", sound = "popup")
                return

            if max_points !="disabled":
                current_remaining = max_points -points_used -cart_points[0]
                if current_remaining <0:
                    self._popup_show_info("Insufficient Points", "You don't have enough requisition points.", sound = "error")
                    return

            try:
                hands_items = save_data.get("hands", {}).get("items", [])

                for item in cart:
                    item_copy = item.copy()
                    item_copy.pop("_table_category", None)
                    item_copy = add_subslots_to_item(item_copy)
                    if item_copy.get("firearm"):
                        _set_armory_used_good_weapon_condition(item_copy)
                    else:
                        _set_full_part_durability(item_copy)

                    try:
                        item_copy["_from_armory"]= store.get("name", "Unknown")
                    except Exception:
                        logging.exception("Suppressed exception")
                    self._add_item_to_container(hands_items, item_copy)

                save_data["hands"]["items"]= hands_items
                self._write_save_to_path(save_path, save_data)

                if max_points !="disabled":
                    new_points_used = points_used +cart_points[0]
                    self._set_armory_points_used(store.get("name", "Unknown"), new_points_used)

                item_names =[it.get("name", "Unknown")for it in cart]
                logging.info(f"Requisitioned items: {item_names}")
                self._popup_show_info("Requisition Complete", f"Requisitioned {len(cart)} item(s):\n"+"\n".join(item_names[:10])+("..."if len(item_names)>10 else ""), sound = "success")

                cart.clear()
                cart_points[0]= 0
                stop_ui_music()
                self._open_business_tool()

            except Exception as e:
                logging.error(f"Failed to checkout: {e}")
                self._popup_show_info("Error", f"Failed to requisition items: {e}", sound = "error")

        def leave_armory():
            def _do_leave(confirmed:bool = True):
                if not confirmed:
                    return
                try:
                    stop_ui_music()
                except Exception:
                    try:
                        self._stop_business_music(music_channel)
                    except Exception:
                        logging.exception("Suppressed exception")
                self._open_business_tool()

            try:
                if cart and len(cart)>0:
                    msg = f"You have {len(cart)} item(s) in your cart.Leaving will discard them.Leave anyway?"
                    self._popup_confirm("Leave Armory", msg, _do_leave)
                    return
            except Exception:
                logging.exception("Suppressed exception")

            _do_leave()

        cart_btn = self._create_sound_button(button_frame, f"View Cart({len(cart)})", view_cart, width = 200, height = 40, font = customtkinter.CTkFont(size = 14))
        cart_btn.pack(side = "left", padx = 10)

        checkout_btn = self._create_sound_button(button_frame, "Confirm Requisition", checkout, width = 200, height = 40, font = customtkinter.CTkFont(size = 14))
        checkout_btn.pack(side = "left", padx = 10)

        def return_armory_items():
            nonlocal points_used
            store_name = store.get("name", "Unknown")
            all_items = self._get_all_player_items_from_save(save_data)
            matches = [d for d in all_items if d.get("item", {}).get("_from_armory") == store_name]
            if not matches:
                self._popup_show_info("No Items", "No items from this armory were found on the character.", sound = "popup")
                return

            ret_popup = customtkinter.CTkToplevel(self.root)
            ret_popup.title("Return Armory Items")
            ret_popup.transient(self.root)

            customtkinter.CTkLabel(ret_popup, text = f"Select items to return to {store_name}:", font = customtkinter.CTkFont(size = 13, weight = 'bold')).pack(pady = (10, 5), padx = 10)

            scroll_frame = customtkinter.CTkScrollableFrame(ret_popup, fg_color = "transparent", width = 380, height = 300)
            scroll_frame.pack(fill = "both", expand = True, padx = 10, pady = 5)

            check_vars = []
            for i, m in enumerate(matches):
                item = m.get("item", {})
                name = item.get("name", "Unknown")
                loc = m.get("location", "unknown")
                loc_label = loc.replace("_", " ").title() if loc else "Unknown"
                var = customtkinter.BooleanVar(value = False)
                check_vars.append(var)
                customtkinter.CTkCheckBox(scroll_frame, text = f"{name}  ({loc_label})", variable = var, font = customtkinter.CTkFont(size = 11)).pack(anchor = "w", pady = 2, padx = 5)

            btn_row = customtkinter.CTkFrame(ret_popup, fg_color = "transparent")
            btn_row.pack(fill = "x", padx = 10, pady = (5, 2))

            def _select_all():
                for v in check_vars:
                    v.set(True)

            def _select_none():
                for v in check_vars:
                    v.set(False)

            customtkinter.CTkButton(btn_row, text = "Select All", command = _select_all, width = 100, height = 28, font = customtkinter.CTkFont(size = 11)).pack(side = "left", padx = 4)
            customtkinter.CTkButton(btn_row, text = "Select None", command = _select_none, width = 100, height = 28, font = customtkinter.CTkFont(size = 11), fg_color = "#444444").pack(side = "left", padx = 4)

            def do_return():
                selected = [matches[i] for i, v in enumerate(check_vars) if v.get()]
                if not selected:
                    self._popup_show_info("No Selection", "No items selected to return.")
                    return
                try:
                    locations_to_remove = {}
                    for m in selected:
                        loc = m.get("location")
                        idx = m.get("index")
                        locations_to_remove.setdefault(loc, []).append(idx)

                    for loc in locations_to_remove:
                        locations_to_remove[loc] = sorted(locations_to_remove[loc], reverse = True)

                    for loc, indices in locations_to_remove.items():
                        for idx in indices:
                            self._remove_item_from_save_location(save_data, loc, idx)

                    self._write_save_to_path(save_path, save_data)

                    refund_count = len(selected)
                    if max_points != "disabled":
                        cur_used = self._get_armory_points_status(store_name) or 0
                        new_used = max(cur_used - refund_count, 0)
                        extra = max(refund_count - cur_used, 0)
                        if extra > 0:
                            overflow_key = f"armory_overflow_{store_name}"
                            persistentdata[overflow_key] = (persistentdata.get(overflow_key, 0) or 0) + extra
                        self._set_armory_points_used(store_name, new_used)
                        points_used = new_used

                    ret_popup.destroy()
                    self._popup_show_info("Return Complete", f"Returned {len(selected)} item(s) to {store_name}. Refunded {refund_count} point(s).", sound = "success")
                    stop_ui_music()
                    self._open_business_tool()
                except Exception as e:
                    logging.error(f"Failed to return armory items: {e}")
                    self._popup_show_info("Error", f"Failed to return items: {e}", sound = "error")

            action_row = customtkinter.CTkFrame(ret_popup, fg_color = "transparent")
            action_row.pack(fill = "x", padx = 10, pady = 10)

            customtkinter.CTkButton(action_row, text = "Return Selected", command = do_return, width = 160, height = 35, font = customtkinter.CTkFont(size = 13)).pack(side = "left", padx = 5)
            customtkinter.CTkButton(action_row, text = "Cancel", command = ret_popup.destroy, width = 120, height = 35, font = customtkinter.CTkFont(size = 13), fg_color = "#444444").pack(side = "left", padx = 5)

            ret_popup.update_idletasks()
            pw = max(ret_popup.winfo_reqwidth(), 440)
            ph = max(ret_popup.winfo_reqheight(), 350)
            sx = ret_popup.winfo_screenwidth(); sy = ret_popup.winfo_screenheight()
            ret_popup.geometry(f"{pw}x{ph}+{sx // 2 - pw // 2}+{sy // 2 - ph // 2}")
            ret_popup.grab_set()
            ret_popup.lift()
            self._safe_focus(ret_popup)

        return_btn = self._create_sound_button(button_frame, "Return Armory Items", return_armory_items, width = 200, height = 40, font = customtkinter.CTkFont(size = 14))
        return_btn.pack(side = "left", padx = 10)

        back_btn = self._create_sound_button(button_frame, "Leave Armory", leave_armory, width = 200, height = 40, font = customtkinter.CTkFont(size = 14))
        back_btn.pack(side = "right", padx = 10)

    def _open_crafting_menu(self, store, table_data):
        self._popup_show_info("Crafting Menu", "Crafting system is not implemented yet.", sound = "popup")

    def _start_shop_firearm_test(self, firearm_item, table_data, on_test_purchase = None, buy_price = 0.0, on_test_started = None):
        if not isinstance(firearm_item, dict) or not firearm_item.get("firearm"):
            self._popup_show_info("Test Firearm", "Only firearms can be tested.", sound = "error")
            return
        if _is_new_historical_firearm(firearm_item):
            self._popup_show_info("Test Firearm", "Brand-new historical firearms cannot be test-fired.", sound = "error")
            return
        if firearm_item.get("_test_used"):
            self._popup_show_info("Test Firearm", "This firearm has already been test-fired.", sound = "error")
            return
        try:
            _rf_val = firearm_item.get("rounds_fired")
            _is_new_gun = (_rf_val is None or int(_rf_val or 0) == 0)
        except Exception:
            _is_new_gun = True
        try:
            _bp = float(buy_price or 0)
        except Exception:
            _bp = 0.0
        test_cost = max(25.0, round(_bp * 0.04, 2)) if (_is_new_gun and _bp > 0) else 10.0
        if self.currentsave is None:
            self._popup_show_info("Test Firearm", "No character loaded.", sound = "error")
            return

        save_filename = (self.currentsave or "") + ".sldsv"
        save_data_local = self._load_file(save_filename)
        if not isinstance(save_data_local, dict):
            self._popup_show_info("Test Firearm", "Failed to load your character save.", sound = "error")
            return

        try:
            current_money = float(save_data_local.get("money", 0) or 0)
        except Exception:
            current_money = 0.0
        if current_money < test_cost:
            self._popup_show_info(
                "Not Enough Money",
                f"Testing costs {format_price(test_cost)} and you only have {format_price(current_money)}.",
                sound = "error"
            )
            return

        save_data_local["money"] = round(current_money - test_cost, 2)
        save_path = os.path.join(saves_folder or "", save_filename)
        self._write_save_to_path(save_path, save_data_local)
        globals()["save_data"] = save_data_local
        self._current_save_data = save_data_local

        firearm_item["_test_used"] = True
        if callable(on_test_started):
            try:
                on_test_started()
            except Exception:
                logging.exception("Suppressed exception")
        if callable(on_test_purchase):
            try:
                on_test_purchase(save_data_local["money"])
            except Exception:
                logging.exception("Suppressed exception")

        self._open_firearm_test_mode(firearm_item, table_data, test_cost = test_cost)

    def _open_firearm_test_mode(self, firearm_item, table_data, test_cost = 10.0):
        if not isinstance(firearm_item, dict):
            self._popup_show_info("Test Firearm", "Invalid firearm data.", sound = "error")
            return

        def _to_lower_set(value):
            if isinstance(value, (list, tuple, set)):
                return {str(v).strip().lower() for v in value if str(v).strip()}
            if value is None:
                return set()
            text = str(value).strip().lower()
            return {text} if text else set()

        def _is_civilian_text(text):
            t = str(text or "").lower()
            positive = ("remington", "umc", "jhp", "jsp", "soft point", "hollow point", ".223", ".308", "winchester", "civilian")
            negative = ("nato", "mil", "m855", "m193", "ss109", "tracer", "armor piercing", "ap")
            score = 0
            for tok in positive:
                if tok in t:
                    score += 3
            for tok in negative:
                if tok in t:
                    score -= 4
            return score

        def _select_preferred_round(weapon_obj, tbl_data):
            ammo_table = (tbl_data or {}).get("tables", {}).get("ammunition", []) or []
            weapon_calibers = _to_lower_set(weapon_obj.get("caliber"))
            alt_map = {
                "5.56x45mm nato": [".223 remington", ".223", "223 remington"],
                "5.56 nato": [".223 remington", ".223", "223 remington"],
                "7.62x51mm nato": [".308 winchester", ".308", "308 winchester"],
                "7.62 nato": [".308 winchester", ".308", "308 winchester"],
            }

            alt_targets = set()
            for wc in weapon_calibers:
                for alt in alt_map.get(wc, []):
                    alt_targets.add(alt.lower())

            best_entry = None
            best_score = -10**9
            for ammo in ammo_table:
                if not isinstance(ammo, dict):
                    continue
                cal = str(ammo.get("caliber", "") or "").strip().lower()
                if not cal:
                    continue
                score = 0
                if cal in weapon_calibers:
                    score += 100
                if cal in alt_targets or any(alt in cal for alt in alt_targets):
                    score += 95
                score += _is_civilian_text(cal)
                score += _is_civilian_text(ammo.get("name", ""))
                if score > best_score:
                    best_score = score
                    best_entry = ammo

            if not isinstance(best_entry, dict):
                fallback_cal = None
                raw_cal = weapon_obj.get("caliber")
                if isinstance(raw_cal, list) and raw_cal:
                    fallback_cal = str(raw_cal[0])
                elif raw_cal is not None:
                    fallback_cal = str(raw_cal)
                if not fallback_cal:
                    fallback_cal = "Unknown"
                return {
                    "name": f"{fallback_cal} | Training",
                    "caliber": fallback_cal,
                    "variant": "Training"
                }

            chosen_cal = str(best_entry.get("caliber", "Unknown"))
            variants = best_entry.get("variants") or []
            chosen_variant = None
            chosen_variant_name = "Ball"
            best_variant_score = -10**9
            for var in variants:
                if isinstance(var, dict):
                    vname = str(var.get("name") or var.get("variant") or var.get("variant_name") or "")
                    score = _is_civilian_text(vname)
                    if score > best_variant_score:
                        best_variant_score = score
                        chosen_variant = var
                        chosen_variant_name = vname or chosen_variant_name
                elif isinstance(var, str):
                    score = _is_civilian_text(var)
                    if score > best_variant_score:
                        best_variant_score = score
                        chosen_variant = var
                        chosen_variant_name = var

            round_obj = {
                "name": f"{chosen_cal} | {chosen_variant_name}",
                "caliber": chosen_cal,
                "variant": chosen_variant_name
            }
            if isinstance(chosen_variant, dict):
                for key in ("pen", "type", "ammo_labels", "modifiers"):
                    if key in chosen_variant:
                        round_obj[key] = chosen_variant.get(key)
            return round_obj

        weapon = json.loads(json.dumps(firearm_item))
        preferred_round = _select_preferred_round(weapon, table_data)

        mag_type = str(weapon.get("magazinetype", "") or "").lower()
        platform = str(weapon.get("platform", "") or "").lower()
        is_internal = any(k in mag_type for k in ("internal", "tube", "cylinder", "break", "en bloc", "belt")) or "revolver" in platform

        def _make_round_list(count):
            return [json.loads(json.dumps(preferred_round)) for _ in range(max(0, int(count)))]

        def _find_mag_template(weapon_obj, tbl_data):
            mags = (tbl_data or {}).get("tables", {}).get("magazines", []) or []
            target_systems = _to_lower_set(weapon_obj.get("magazinesystem"))
            target_calibers = _to_lower_set(weapon_obj.get("caliber"))
            for mag in mags:
                if not isinstance(mag, dict):
                    continue
                mag_systems = _to_lower_set(mag.get("magazinesystem"))
                if target_systems and not mag_systems.intersection(target_systems):
                    continue
                mag_calibers = _to_lower_set(mag.get("caliber"))
                if target_calibers and mag_calibers and not mag_calibers.intersection(target_calibers):
                    continue
                return mag
            return None

        mag_template = _find_mag_template(weapon, table_data)
        capacity = 30
        try:
            if isinstance(mag_template, dict):
                capacity = int(mag_template.get("capacity", capacity) or capacity)
            elif weapon.get("capacity") is not None:
                capacity = int(weapon.get("capacity") or capacity)
        except Exception:
            capacity = 30
        capacity = max(1, capacity)

        test_state = {
            "spare_mags": [],
            "internal_reserve": 0
        }

        if is_internal:
            weapon["loaded"] = None
            weapon["rounds"] = _make_round_list(capacity)
            weapon["chambered"] = weapon["rounds"].pop(0) if weapon.get("rounds") else None
            test_state["internal_reserve"] = capacity * 2
        else:
            mags = []
            for _ in range(3):
                if isinstance(mag_template, dict):
                    mag_obj = json.loads(json.dumps(mag_template))
                else:
                    mag_obj = {
                        "name": f"Test Magazine ({capacity}rnd)",
                        "capacity": capacity,
                        "magazinesystem": weapon.get("magazinesystem"),
                        "magazinetype": weapon.get("magazinetype", "Detachable box")
                    }
                mag_obj["rounds"] = _make_round_list(capacity)
                mags.append(mag_obj)
            weapon["loaded"] = mags[0]
            weapon["rounds"] = []
            weapon["chambered"] = weapon["loaded"]["rounds"].pop(0) if weapon.get("loaded", {}).get("rounds") else None
            test_state["spare_mags"] = mags[1:]

        combat_state = {
            "barrel_temperatures": {},
            "barrel_cleanliness": {},
            "ambient_temperature": 70,
            "weapon_last_used": {},
            "weather": {"weather": "clear", "wind_severity": 0, "temperature_f": 70}
        }

        popup = customtkinter.CTkToplevel(self.root)
        popup.title(f"Test Firearm: {self._format_item_name(firearm_item)}")
        popup.transient(self.root)
        popup.grab_set()
        popup.withdraw()
        self._center_popup_on_window(popup, 760, 440)

        frame = customtkinter.CTkFrame(popup, fg_color = "transparent")
        frame.pack(fill = "both", expand = True, padx = 20, pady = 16)

        customtkinter.CTkLabel(
            frame,
            text = f"Firearm Test Mode: {self._format_item_name(firearm_item)}",
            font = customtkinter.CTkFont(size = 18, weight = "bold"),
            wraplength = 700,
            justify = "center"
        ).pack(pady = (0, 8))

        customtkinter.CTkLabel(
            frame,
            text = f"Test fee paid: {format_price(test_cost)} | Clipboard output disabled | Attachment/part edits disabled",
            font = customtkinter.CTkFont(size = 12),
            text_color = "#aaaaaa",
            wraplength = 700,
            justify = "center"
        ).pack(pady = (0, 10))

        status_label = customtkinter.CTkLabel(frame, text = "", font = customtkinter.CTkFont(size = 12), justify = "left", anchor = "w")
        status_label.pack(fill = "x", pady = (0, 8))

        result_label = customtkinter.CTkLabel(frame, text = "Ready.", font = customtkinter.CTkFont(size = 12), justify = "left", anchor = "w", wraplength = 700)
        result_label.pack(fill = "x", pady = (0, 12))

        def _get_firearm_rounds_fired(obj):
            try:
                return int(obj.get("rounds_fired", 0) or 0)
            except Exception:
                return 0

        def _update_status():
            rf = _get_firearm_rounds_fired(firearm_item)
            if is_internal:
                in_weapon = len(weapon.get("rounds", []) or []) + (1 if weapon.get("chambered") else 0)
                reserve = int(test_state.get("internal_reserve", 0) or 0)
                text = f"Rounds in weapon: {in_weapon} | Reserve rounds: {reserve} | Firearm rounds fired: {rf:,}"
            else:
                loaded = weapon.get("loaded") if isinstance(weapon.get("loaded"), dict) else {}
                in_mag = len((loaded or {}).get("rounds", []) or [])
                chambered = 1 if weapon.get("chambered") else 0
                reserve_mags = len(test_state.get("spare_mags", []) or [])
                text = f"Loaded mag: {in_mag} + {chambered} chambered | Spare mags: {reserve_mags} | Firearm rounds fired: {rf:,}"
            status_label.configure(text = text)

        def _apply_fired_rounds_to_shop_item(message):
            try:
                m = re.search(r"Fired\s+(\d+)\s+round", str(message or ""), re.IGNORECASE)
                fired_count = int(m.group(1)) if m else 0
            except Exception:
                fired_count = 0
            if fired_count <= 0:
                return
            current_rf = _get_firearm_rounds_fired(firearm_item)
            firearm_item["rounds_fired"] = current_rf + fired_count
            weapon["rounds_fired"] = firearm_item.get("rounds_fired", current_rf + fired_count)

        _fire_btns = []

        def _fire(rounds_to_fire):
            if getattr(popup, "_firing", False):
                return
            popup._firing = True
            for _b in _fire_btns:
                try:
                    _b.configure(state = "disabled")
                except Exception:
                    logging.exception("Suppressed exception")
            result_label.configure(text = "Firing...")
            prev_clipboard_state = bool(getattr(self, "_suppress_clipboard_copy", False))
            self._suppress_clipboard_copy = True
            def _do_fire():
                try:
                    result = self._fire_weapon(weapon, combat_state, rounds_to_fire = rounds_to_fire, fire_mode = None, save_data = None)
                except Exception:
                    result = "Firing failed due to an internal error."
                finally:
                    self._suppress_clipboard_copy = prev_clipboard_state
                def _after():
                    _apply_fired_rounds_to_shop_item(result)
                    result_label.configure(text = str(result))
                    _update_status()
                    for _b in _fire_btns:
                        try:
                            _b.configure(state = "normal")
                        except Exception:
                            logging.exception("Suppressed exception")
                    popup._firing = False
                try:
                    popup.after(0, _after)
                except Exception:
                    logging.exception("Suppressed exception")
            import threading as _test_threading
            _test_threading.Thread(target = _do_fire, daemon = True).start()

        def _reload_test_weapon():
            if is_internal:
                cur_rounds = weapon.get("rounds", []) or []
                current_count = len(cur_rounds)
                needed = max(0, capacity - current_count)
                reserve = int(test_state.get("internal_reserve", 0) or 0)
                to_load = min(needed, reserve)
                if to_load <= 0:
                    result_label.configure(text = "No reserve rounds left to reload.")
                    return
                cur_rounds.extend(_make_round_list(to_load))
                weapon["rounds"] = cur_rounds
                test_state["internal_reserve"] = reserve - to_load
                result_label.configure(text = f"Reloaded internal magazine with {to_load} round(s).")
                _update_status()
                return

            spares = test_state.get("spare_mags", []) or []
            if not spares:
                result_label.configure(text = "No spare magazines left.")
                return
            weapon["loaded"] = spares.pop(0)
            if not weapon.get("chambered") and isinstance(weapon.get("loaded"), dict):
                rounds = weapon["loaded"].get("rounds", []) or []
                if rounds:
                    weapon["chambered"] = rounds.pop(0)
                    weapon["loaded"]["rounds"] = rounds
            test_state["spare_mags"] = spares
            result_label.configure(text = "Reloaded next test magazine.")
            _update_status()

        button_row = customtkinter.CTkFrame(frame, fg_color = "transparent")
        button_row.pack(fill = "x", pady = (4, 0))

        _f1_btn = self._create_sound_button(button_row, "Fire 1", lambda: _fire(1), width = 120, height = 36)
        _f1_btn.pack(side = "left", padx = (0, 8))
        _fire_btns.append(_f1_btn)
        _f3_btn = self._create_sound_button(button_row, "Fire 3", lambda: _fire(3), width = 120, height = 36)
        _f3_btn.pack(side = "left", padx = (0, 8))
        _fire_btns.append(_f3_btn)
        self._create_sound_button(button_row, "Reload", _reload_test_weapon, width = 120, height = 36).pack(side = "left", padx = (0, 8))
        self._create_sound_button(button_row, "Close", popup.destroy, width = 120, height = 36).pack(side = "right")

        _update_status()
        popup.deiconify()

    def _open_store_interface(self, store, table_data):

        logging.info(f"Opening store: {store.get('name')}")

        music_channel = None
        if store.get("music")and store.get("playlist"):
            music_channel = self._start_business_music(store.get("playlist"), first_play = True)

        self._clear_window()

        self.root.grid_rowconfigure(0, weight = 1)
        self.root.grid_columnconfigure(0, weight = 1)

        main_frame = customtkinter.CTkFrame(self.root)
        main_frame.grid(row = 0, column = 0, sticky = "nsew")
        main_frame.grid_columnconfigure(0, weight = 1)
        main_frame.grid_rowconfigure(1, weight = 1)

        header_frame = customtkinter.CTkFrame(main_frame, fg_color = "transparent")
        header_frame.grid(row = 0, column = 0, sticky = "ew", padx = 20, pady = 10)

        title_label = customtkinter.CTkLabel(header_frame, text = store.get("name", "Store"), font = customtkinter.CTkFont(size = 24, weight = "bold"))
        title_label.pack(pady =(10, 5))

        shopkeeper_label = customtkinter.CTkLabel(header_frame, text = f"Shopkeeper: {store.get('shopkeeper', 'Unknown')}", font = customtkinter.CTkFont(size = 14), text_color = "gray")
        shopkeeper_label.pack()

        save_path = os.path.join(saves_folder or "", (self.currentsave or "")+".sldsv")
        save_data = self._load_file((self.currentsave or "")+".sldsv")
        if save_data is None:
            self._popup_show_info("Error", "Failed to load character data.", sound = "error")
            try:
                self._stop_business_music(music_channel)
            except Exception:
                logging.exception("Suppressed exception")
            return

        equipped_weapons = self._get_equipped_weapons(save_data, table_data)
        equipped_calibers = set()
        equipped_magazine_systems = set()
        equipped_attachment_slots = set()

        for wpn in equipped_weapons:
            item = wpn.get("item", {})
            calibers = item.get("caliber", [])
            if isinstance(calibers, str):
                calibers = [calibers]
            for cal in calibers:
                if cal:
                    equipped_calibers.add(cal)

            mag_system = item.get("magazinesystem")
            if isinstance(mag_system, str):
                if mag_system:
                    equipped_magazine_systems.add(mag_system)
            elif isinstance(mag_system, list):
                for ms in mag_system:
                    if isinstance(ms, str) and ms:
                        equipped_magazine_systems.add(ms)

        for wpn in equipped_weapons:
            for acc in (wpn.get("accessories") or []):
                if isinstance(acc, dict):
                    slot_name = acc.get("slot")
                    if slot_name:
                        equipped_attachment_slots.add(slot_name)

        def _is_shop_item_relevant(item):
            if not isinstance(item, dict):
                return False

            calibers = item.get("caliber", [])
            if isinstance(calibers, str):
                calibers = [calibers]

            if item.get("_table_category") == "ammunition":
                for cal in calibers:
                    if cal in equipped_calibers:
                        return True

            if item.get("_table_category") == "magazines":
                mag_system = item.get("magazinesystem")
                item_mag_systems = []
                if isinstance(mag_system, str):
                    item_mag_systems = [mag_system]
                elif isinstance(mag_system, list):
                    item_mag_systems = [ms for ms in mag_system if isinstance(ms, str) and ms]

                if any(ms in equipped_magazine_systems for ms in item_mag_systems):
                    for cal in calibers:
                        if cal in equipped_calibers:
                            return True

            is_attachment = bool(item.get("attachment") or item.get("accessory") or (item.get("_table_category") in ("attachments", "accessories")))
            if is_attachment:
                item_slots = item.get("slot") or item.get("attach_to") or item.get("accessory_slot") or item.get("parent_accessory_slot") or []
                if isinstance(item_slots, str):
                    item_slots = [item_slots]
                for slot_name in item_slots:
                    if slot_name and slot_name in equipped_attachment_slots:
                        return True

            return False

        player_money =[save_data.get("money", 0)]

        money_label = customtkinter.CTkLabel(header_frame, text = f"Your Money: {format_price(player_money[0])}", font = customtkinter.CTkFont(size = 16, weight = "bold"), text_color = "green")
        money_label.pack(pady = 5)

        prices = store.get("prices", {"buy":1.0, "sell":1.0})
        buy_mult = prices.get("buy", 1.0)
        sell_mult = prices.get("sell", 1.0)

        market_demand = _get_market_demand()
        market_ticker = _format_market_ticker(market_demand)

        prices_label = customtkinter.CTkLabel(header_frame, text = f"Shop buys at {buy_mult}x | Shop sells at {sell_mult}x value", font = customtkinter.CTkFont(size = 12), text_color = "orange")
        prices_label.pack()

        market_label = customtkinter.CTkLabel(header_frame, text = f"Market:  {market_ticker}", font = customtkinter.CTkFont(size = 10), text_color = "lightblue", wraplength = 900, justify = "center")
        market_label.pack(pady = (0, 4))

        marquee_label = None
        marquee_job:list[object]=[None]

        def _get_track_info(track_path):
            artist = None
            title = None
            length = None
            try:
                try:
                    sound = pygame.mixer.Sound(track_path)
                    length = float(sound.get_length())
                except Exception:
                    length = None
                try:
                    from mutagen._file import File as MutagenFile
                    mf = MutagenFile(track_path)
                    if mf is not None:
                        tags = getattr(mf, 'tags', {})or {}
                        def _get_tag(keys):
                            for k in keys:
                                v = tags.get(k)
                                if v:
                                    try:
                                        if isinstance(v, (list, tuple)):
                                            return str(v[0])
                                        return str(v)
                                    except Exception:
                                        return str(v)
                            return None
                        artist = _get_tag(["artist", "ARTIST", "TPE1", "IART"])
                        title = _get_tag(["title", "TITLE", "TIT2", "INAM"])
                except Exception:
                    logging.exception("Suppressed exception")
            except Exception:
                logging.exception("Suppressed exception")
            if not title:
                try:
                    title = os.path.basename(track_path or "")
                except Exception:
                    title = "Unknown"
            try:
                logging.debug(f"_get_track_info result: title={title} artist={artist} length={length}")
            except Exception:
                logging.exception("Suppressed exception")
            return {"artist":artist, "title":title, "length":length}

        def stop_ui_music():
            try:
                if marquee_job[0]:
                    try:
                        self.root.after_cancel(marquee_job[0])# type: ignore[arg-type]
                    except Exception:
                        logging.exception("Suppressed exception")
                    marquee_job[0]= None
            except Exception:
                logging.exception("Suppressed exception")
            try:
                self._stop_business_music(music_channel)
            except Exception:
                logging.exception("Suppressed exception")

        if music_channel and music_channel.get("track"):
            try:
                track_path = music_channel.get("track")
                info = _get_track_info(track_path)
                base_artist = info.get("artist")or ""
                base_title = info.get("title")or os.path.basename(track_path or "")
                track_len = info.get("length")or 0.0

                marquee_frame = customtkinter.CTkFrame(header_frame, fg_color = "black")

                marquee_frame.pack(pady =(6, 0))
                try:
                    marquee_frame.configure(width = 500)

                    try:
                        marquee_frame.pack_propagate(False)
                    except Exception:
                        logging.exception("Suppressed exception")
                except Exception:
                    logging.exception("Suppressed exception")
                try:

                    label_font = None
                    try:
                        import ctypes
                        import tkinter.font as tkfont
                        fp = os.path.join(os.path.dirname(__file__), "fonts", "Tims_8x5_LCD_Matrix.ttf")
                        if os.path.exists(fp)and hasattr(ctypes, 'windll'):
                            try:
                                FR_PRIVATE = 0x10
                                ctypes.windll.gdi32.AddFontResourceExW(fp, FR_PRIVATE, 0)
                            except Exception:
                                logging.exception("Suppressed exception")

                            try:
                                self.root.update_idletasks()
                                fams = list(tkfont.families())
                                for f in fams:
                                    if any(x in f.lower()for x in("tims", "8x5", "lcd")):
                                        label_font = customtkinter.CTkFont(size = 12, family = f)
                                        break
                            except Exception:
                                logging.exception("Suppressed exception")
                    except Exception:
                        logging.exception("Suppressed exception")
                    if not label_font:
                        label_font = customtkinter.CTkFont(size = 12)
                except Exception:
                    label_font = customtkinter.CTkFont(size = 12)
                marquee_label = customtkinter.CTkLabel(marquee_frame, text = "", anchor = "w", font = label_font, width = 480, height = 26, text_color = "#7CFC00")
                marquee_label.pack(anchor = "center", padx = 4)
                try:
                    marquee_debug_label = customtkinter.CTkLabel(marquee_frame, text = "", anchor = "w", font = customtkinter.CTkFont(size = 9), text_color = "white")
                    marquee_debug_label.pack(anchor = "center", padx = 4, pady =(2, 0))
                except Exception:
                    marquee_debug_label = None
                try:
                    self.root.update_idletasks()
                    lh = marquee_label.winfo_reqheight()or marquee_label.winfo_height()
                    if lh:
                        try:
                            marquee_frame.configure(height = lh)
                        except Exception:
                            logging.exception("Suppressed exception")
                except Exception:
                    logging.exception("Suppressed exception")

                pos =[0]

                def _fmt_time(s):
                    try:
                        s = max(0, int(s))
                        return f"{s //60}:{s %60:02d}"
                    except Exception:
                        return "0:00"

                def _update_marquee():
                    try:

                        current = getattr(self, "_current_business_music", music_channel)
                        meta_info = None
                        if current:
                            meta_info = current.get("_meta")

                        try:
                            track_path =(current or {}).get('track')
                            if track_path !=prev_track[0]:
                                prev_track[0]= track_path
                                pos[0]= 0
                        except Exception:
                            track_path =(current or {}).get('track')
                        try:
                            logging.debug(f"store marquee update: track={os.path.basename((current or {}).get('track')or '')} meta={bool(meta_info)} pos={pos[0]} ids: current={id(current)} music_channel={id(music_channel)} self_cur={id(getattr(self, '_current_business_music', None))}")
                        except Exception:
                            logging.exception("Suppressed exception")
                        try:
                            if marquee_debug_label is not None:
                                dbg = f"meta={bool(meta_info)} id={id(current)}"
                                try:

                                    tt =(meta_info or {}).get('title')if meta_info else((current or {}).get('track')or '')
                                    if tt:
                                        dbg +=f" title={tt[:30]}"
                                except Exception:
                                    logging.exception("Suppressed exception")
                                marquee_debug_label.configure(text = dbg)
                        except Exception:
                            logging.exception("Suppressed exception")

                        if meta_info:
                            base_artist = meta_info.get("artist")or ""
                            base_title = meta_info.get("title")or os.path.basename(track_path or "")
                            total = meta_info.get("length")or 0.0
                        else:

                            base_artist = ""
                            base_title = os.path.basename(track_path or "")
                            total = 0.0
                            try:
                                if current and not current.get("_meta_loading"):
                                    current["_meta_loading"]= True
                                    def _bg_load():
                                        try:
                                            info = _get_track_info((current or {}).get("track"))
                                            def _apply():
                                                try:
                                                    try:
                                                        logging.debug(f"applying _meta(bg_load current): {os.path.basename((current or {}).get('track')or '')} -> title={info.get('title')} artist={info.get('artist')}")
                                                    except Exception:
                                                        logging.exception("Suppressed exception")
                                                    try:
                                                        target = getattr(self, "_current_business_music", None)
                                                        if target is None:
                                                            target = current
                                                        if target is not None:
                                                                target.update({"_meta":info})
                                                                try:
                                                                    logging.debug(f"triggering marquee refresh after applying meta for {os.path.basename((target or {}).get('track')or '')}(current)")
                                                                except Exception:
                                                                    logging.exception("Suppressed exception")
                                                                try:
                                                                    self.root.after(0, _update_marquee)
                                                                except Exception:
                                                                    logging.exception("Suppressed exception")
                                                    except Exception:
                                                        try:
                                                            logging.exception("failed to apply _meta in bg_load(current) for store marquee")
                                                        except Exception:
                                                            logging.exception("Suppressed exception")
                                                except Exception:
                                                    try:
                                                        logging.exception("unexpected error in _apply for bg_load(current)")
                                                    except Exception:
                                                        logging.exception("Suppressed exception")
                                            try:
                                                logging.debug(f"scheduling _apply(current) via root.after for track {os.path.basename((getattr(self, '_current_business_music', current)or {}).get('track')or '')}")
                                            except Exception:
                                                logging.exception("Suppressed exception")
                                            self.root.after(0, _apply)
                                        except Exception:
                                            logging.exception("Suppressed exception")
                                        finally:
                                            try:
                                                current.pop("_meta_loading", None)
                                            except Exception:
                                                logging.exception("Suppressed exception")
                                    import threading
                                    threading.Thread(target = _bg_load, daemon = True).start()
                            except Exception:
                                logging.exception("Suppressed exception")

                        started =(current or {}).get("started_at")or time.time()
                        start_offset =(current or {}).get("start_pos")or 0.0
                        elapsed =(time.time()-started)+float(start_offset)

                        elapsed_display = _fmt_time(elapsed)
                        total_fmt = _fmt_time(total)

                        meta = f"{base_artist} | {base_title} | {elapsed_display}/{total_fmt}"if(base_artist or base_title)else os.path.basename((music_channel or {}).get("track")or "")

                        try:
                            self.root.update_idletasks()
                            label_px = marquee_label.winfo_width()or int(marquee_label.cget("width")or 480)
                        except Exception:
                            label_px = int(marquee_label.cget("width")or 480)

                        avg_char_px = 8
                        visible_chars = max(8, int(label_px /max(1, avg_char_px)))

                        scrollfull = " "+meta +" "
                        if len(scrollfull)<visible_chars:
                            scrollfull = scrollfull +(" "*(visible_chars -len(scrollfull)+2))

                        doubled =(scrollfull *3)
                        display = doubled[pos[0]:pos[0]+visible_chars]
                        marquee_label.configure(text = display)
                        pos[0]=(pos[0]+1)%max(1, len(scrollfull))
                        try:
                            len_scroll = max(1, len(scrollfull))
                            delay_ms = int(min(500, max(60, 70 +(len_scroll *3))))
                        except Exception:
                            delay_ms = 120
                        marquee_job[0]= self.root.after(delay_ms, _update_marquee)
                    except Exception:
                        try:
                            marquee_label.configure(text = os.path.basename((getattr(self, "_current_business_music", music_channel)or {}).get("track")or ""))
                        except Exception:
                            logging.exception("Suppressed exception")

                try:
                    import threading
                    try:
                        logging.debug("starting initial background _load_meta thread for store marquee")
                    except Exception:
                        logging.exception("Suppressed exception")
                    def _load_meta():
                        try:
                            cur = getattr(self, "_current_business_music", music_channel)
                            if not cur:
                                return
                            info = _get_track_info(cur.get("track"))
                            try:
                                logging.debug(f"_load_meta fetched info: title={info.get('title')} artist={info.get('artist')}")
                            except Exception:
                                logging.exception("Suppressed exception")
                            def _apply():
                                try:
                                    try:
                                        logging.debug(f"applying initial _meta(from _load_meta): {os.path.basename((cur or {}).get('track')or '')} -> title={info.get('title')} artist={info.get('artist')}")
                                    except Exception:
                                        logging.exception("Suppressed exception")
                                    try:

                                        target = getattr(self, "_current_business_music", None)
                                        if target is None:
                                            target = cur
                                        if target is not None:
                                            target.update({"_meta":info})
                                            try:
                                                logging.debug(f"triggering marquee refresh after initial apply for {os.path.basename((target or {}).get('track')or '')}")
                                            except Exception:
                                                logging.exception("Suppressed exception")
                                            try:
                                                self.root.after(0, _update_marquee)
                                            except Exception:
                                                logging.exception("Suppressed exception")
                                    except Exception:
                                        try:
                                            logging.exception("failed to apply initial _meta in _load_meta for store marquee")
                                        except Exception:
                                            logging.exception("Suppressed exception")
                                except Exception:
                                    try:
                                        logging.exception("unexpected error in initial _apply for store marquee")
                                    except Exception:
                                        logging.exception("Suppressed exception")
                            try:
                                logging.debug(f"scheduling initial _apply via root.after for store marquee: {os.path.basename((cur or {}).get('track')or '')}")
                            except Exception:
                                logging.exception("Suppressed exception")
                            try:
                                self.root.after(0, _apply)
                            except Exception:
                                logging.exception("Suppressed exception")
                        except Exception:
                            logging.exception("Suppressed exception")
                    threading.Thread(target = _load_meta, daemon = True).start()
                except Exception:
                    logging.exception("Suppressed exception")

                _update_marquee()
            except Exception:
                logging.exception("Suppressed exception")

        def get_all_player_items():

            all_items =[]

            hands_items = save_data.get("hands", {}).get("items", [])
            for idx, item in enumerate(hands_items):
                if isinstance(item, dict):
                    all_items.append({"item":item, "location":"hands", "index":idx})

            equipment = save_data.get("equipment", {})
            for slot_name, slot_item in equipment.items():
                if slot_item and isinstance(slot_item, dict):
                    if "items"in slot_item and "capacity"in slot_item:
                        for idx, item in enumerate(slot_item.get("items", [])):
                            if isinstance(item, dict):
                                all_items.append({"item":item, "location":f"equipment.{slot_name}", "index":idx})

                    if "subslots"in slot_item:
                        for subslot_idx, subslot_data in enumerate(slot_item.get("subslots", [])):
                            subslot_item = subslot_data.get("current")
                            if subslot_item and isinstance(subslot_item, dict)and "items"in subslot_item:
                                for idx, item in enumerate(subslot_item.get("items", [])):
                                    if isinstance(item, dict):
                                        all_items.append({"item":item, "location":f"equipment.{slot_name}.subslot.{subslot_idx}", "index":idx})

                elif isinstance(slot_item, list):
                    for list_idx, list_item in enumerate(slot_item):
                        if list_item and isinstance(list_item, dict):
                            if "items"in list_item and "capacity"in list_item:
                                for idx, item in enumerate(list_item.get("items", [])):
                                    if isinstance(item, dict):
                                        all_items.append({"item":item, "location":f"equipment.{slot_name}.list.{list_idx}", "index":idx})

                            if "subslots"in list_item:
                                for subslot_idx, subslot_data in enumerate(list_item.get("subslots", [])):
                                    subslot_item = subslot_data.get("current")
                                    if subslot_item and isinstance(subslot_item, dict)and "items"in subslot_item:
                                        for idx, item in enumerate(subslot_item.get("items", [])):
                                            if isinstance(item, dict):
                                                all_items.append({"item":item, "location":f"equipment.{slot_name}.list.{list_idx}.subslot.{subslot_idx}", "index":idx})

            return all_items

        def remove_item_from_location(location, index):

            if location =="hands":
                items = save_data.get("hands", {}).get("items", [])
                if 0 <=index <len(items):
                    items.pop(index)
            elif location.startswith("equipment."):
                parts = location.split(".")
                slot = parts[1]
                slot_item = save_data.get("equipment", {}).get(slot)

                if len(parts)==2:
                    if slot_item and isinstance(slot_item, dict)and "items"in slot_item:
                        items = slot_item.get("items", [])
                        if 0 <=index <len(items):
                            items.pop(index)
                elif len(parts)>=4 and parts[2]=="subslot":
                    subslot_idx = int(parts[3])
                    if slot_item and isinstance(slot_item, dict)and "subslots"in slot_item:
                        subslot_item = slot_item["subslots"][subslot_idx].get("current")
                        if subslot_item and "items"in subslot_item:
                            items = subslot_item.get("items", [])
                            if 0 <=index <len(items):
                                items.pop(index)
                elif len(parts)>=4 and parts[2]=="list":
                    list_idx = int(parts[3])
                    if isinstance(slot_item, list)and 0 <=list_idx <len(slot_item):
                        list_item = slot_item[list_idx]
                        if len(parts)==4:
                            if list_item and isinstance(list_item, dict)and "items"in list_item:
                                items = list_item.get("items", [])
                                if 0 <=index <len(items):
                                    items.pop(index)
                        elif len(parts)>=6 and parts[4]=="subslot":
                            subslot_idx = int(parts[5])
                            if list_item and isinstance(list_item, dict)and "subslots"in list_item:
                                subslot_item = list_item["subslots"][subslot_idx].get("current")
                                if subslot_item and "items"in subslot_item:
                                    items = subslot_item.get("items", [])
                                    if 0 <=index <len(items):
                                        items.pop(index)

        store_inventory =[]
        store_inv_config = store.get("inventory", [])
        used_firearm_chance = store.get("used_firearm_chance", 40.0)
        try:
            used_firearm_chance = float(used_firearm_chance)
        except (TypeError, ValueError):
            used_firearm_chance = 40.0
        used_firearm_chance = max(0.0, min(100.0, used_firearm_chance)) / 100.0
        tables = table_data.get("tables", {})

        def _expand_ammo_variants_for_store(items):
            expanded = []
            for base_item in items:
                if not isinstance(base_item, dict):
                    continue
                is_ammo = str(base_item.get("_table_category", "")).lower() == "ammunition"
                variants = base_item.get("variants", []) if is_ammo else []
                caliber = base_item.get("caliber")

                if is_ammo and isinstance(variants, list) and variants:
                    if isinstance(caliber, list):
                        caliber_name = ", ".join(str(c) for c in caliber)
                    else:
                        caliber_name = str(caliber or base_item.get("name", "Ammunition"))

                    for var in variants:
                        if not isinstance(var, dict):
                            continue
                        var_name = str(var.get("name") or var.get("type") or "FMJ")
                        item_copy = base_item.copy()
                        item_copy["name"] = f"{var_name} ({caliber_name})"
                        item_copy["variant"] = var_name
                        item_copy["caliber"] = caliber_name
                        _apply_ammo_variant_data(item_copy, base_item, var)

                        labels = item_copy.get("ammo_labels", [])
                        if labels:
                            item_copy["name"] = f"{item_copy['name']} [{' / '.join(labels)}]"

                        item_copy.pop("variants", None)
                        expanded.append(item_copy)
                else:
                    expanded.append(base_item)

            return expanded

        def _get_store_buy_price(item_obj):
            base_value = self._compute_item_value_with_installed_components(item_obj)
            effective_value = _get_depreciated_item_value(base_value, item_obj)

            raw_price = effective_value * sell_mult * _get_item_market_multiplier(item_obj, market_demand)
            buy_price_value = round(raw_price, 2)

            # Prevent tiny positive ammunition prices from rounding down to zero.
            if str(item_obj.get("_table_category", "")).lower() == "ammunition" and raw_price > 0 and buy_price_value < 0.01:
                return 0.01
            if item_obj.get("firearm") and float(item_obj.get("rounds_fired", 0) or 0) > 0:
                return max(100.0, max(0.0, buy_price_value))
            return max(0.0, buy_price_value)

        for inv_entry in store_inv_config:
            if inv_entry.get("type")=="table":
                table_name = inv_entry.get("table")
                table_items = tables.get(table_name, [])
                for item in table_items:
                    if isinstance(item, dict):
                        item_copy = item.copy()
                        item_copy["_table_category"]= table_name
                        store_inventory.append(item_copy)
            elif inv_entry.get("type")=="id":
                item_id = inv_entry.get("id")
                for table_name, table_items in tables.items():
                    if isinstance(table_items, list):
                        for item in table_items:
                            if isinstance(item, dict)and item.get("id")==item_id:
                                item_copy = item.copy()
                                item_copy["_table_category"]= table_name
                                store_inventory.append(item_copy)
                                break

        store_inventory = _expand_ammo_variants_for_store(store_inventory)

        stock_count_by_key = {}

        def _hashable_key_value(value):
            if isinstance(value, dict):
                try:
                    return tuple(sorted((str(k), _hashable_key_value(v)) for k, v in value.items()))
                except Exception:
                    return str(value)
            if isinstance(value, (list, tuple, set)):
                try:
                    return tuple(_hashable_key_value(v) for v in value)
                except Exception:
                    return str(value)
            return value

        def _shop_stock_key(item_obj):
            return (
                _hashable_key_value(item_obj.get("id")),
                _hashable_key_value(item_obj.get("name")),
                _hashable_key_value(item_obj.get("caliber")),
                _hashable_key_value(item_obj.get("variant")),
                _hashable_key_value(item_obj.get("_table_category")),
            )

        for inv_item in store_inventory:
            if not isinstance(inv_item, dict):
                continue
            _k = _shop_stock_key(inv_item)
            stock_count_by_key[_k] = stock_count_by_key.get(_k, 0) + 1

        for inv_item in store_inventory:
            if not isinstance(inv_item, dict):
                continue
            inv_item["_shop_available_qty"] = stock_count_by_key.get(_shop_stock_key(inv_item), 1)

        for item_idx, inv_item in enumerate(store_inventory):
            if not isinstance(inv_item, dict) or not inv_item.get("firearm"):
                continue
            if inv_item.get("rounds_fired") is not None:
                _sync_firearm_cleanliness_from_rounds_fired(inv_item)
                continue
            seeded_rf = _get_seeded_store_firearm_rounds_fired(inv_item, store.get("name", ""), item_idx, used_firearm_chance)
            if seeded_rf is not None:
                inv_item["rounds_fired"] = seeded_rf
                _sync_firearm_cleanliness_from_rounds_fired(inv_item)

        inv_qty = store.get("inventory_quantity", "disabled")
        if inv_qty !="disabled"and isinstance(inv_qty, dict):
            min_qty = inv_qty.get("min", 20)
            max_qty = inv_qty.get("max", 40)
            stock_rng = random.Random(_get_market_seed_for_store(store.get("name", "")))
            target_qty = stock_rng.randint(min_qty, max_qty)
            if len(store_inventory)>target_qty:
                store_inventory = stock_rng.sample(store_inventory, target_qty)

        tab_view = customtkinter.CTkTabview(main_frame)
        tab_view.grid(row = 1, column = 0, sticky = "nsew", padx = 20, pady = 10)

        buy_tab = tab_view.add("Buy")
        sell_tab = tab_view.add("Sell")
        if store.get("accepts_trades"):
            trade_tab = tab_view.add("Trade")

        buy_cart =[]
        buy_total =[0.0]

        def update_buy_display():
            money_label.configure(text = f"Your Money: {format_price(player_money[0])} | Cart Total: {format_price(buy_total[0])}")

        def on_test_firearm_purchase(new_money):
            try:
                player_money[0] = float(new_money)
            except Exception:
                player_money[0] = new_money
            update_buy_display()

        def _is_store_item_stackable(item_obj):
            if not isinstance(item_obj, dict):
                return False
            if str(item_obj.get("_table_category", "")).lower() == "ammunition":
                return True
            if item_obj.get("can_stack") is False:
                return False
            non_stackable_keys = ["magazinesystem", "capacity", "firearm", "attachment", "subslots", "loaded", "chambered"]
            return not any(k in item_obj for k in non_stackable_keys)

        def _cart_stack_key(item_obj):
            return (
                item_obj.get("name"),
                item_obj.get("id"),
                item_obj.get("caliber"),
                item_obj.get("variant"),
                item_obj.get("_table_category"),
            )

        def _buy_cart_units():
            total_units = 0
            for entry in buy_cart:
                try:
                    total_units += max(1, int(entry.get("quantity", 1)))
                except Exception:
                    total_units += 1
            return total_units

        def _add_item_to_buy_cart(item_obj, unit_price, quantity = 1):
            try:
                qty = max(1, int(quantity))
            except Exception:
                qty = 1

            stackable = _is_store_item_stackable(item_obj)
            line_total = float(unit_price) * qty

            if player_money[0] - buy_total[0] < line_total:
                self._popup_show_info(
                    "Not Enough Money",
                    f"You need {format_price(line_total)} but only have {format_price(player_money[0] - buy_total[0])} remaining.",
                    sound = "error",
                )
                return False

            if stackable:
                key = _cart_stack_key(item_obj)
                for entry in buy_cart:
                    if entry.get("stackable") and entry.get("_cart_key") == key:
                        entry_qty = max(1, int(entry.get("quantity", 1)))
                        entry["quantity"] = entry_qty + qty
                        entry["line_total"] = float(entry.get("line_total", 0.0)) + line_total
                        buy_total[0] += line_total
                        update_buy_display()
                        self._play_ui_sound("click")
                        return True

            buy_cart.append({
                "item": item_obj.copy(),
                "price": float(unit_price),
                "quantity": qty,
                "line_total": line_total,
                "stackable": stackable,
                "_cart_key": _cart_stack_key(item_obj),
                "_original_item": item_obj if isinstance(item_obj, dict) and item_obj.get("firearm") else None,
            })
            buy_total[0] += line_total
            update_buy_display()
            self._play_ui_sound("click")
            return True

        def _remove_buy_cart_index(idx):
            if idx < 0 or idx >= len(buy_cart):
                return
            try:
                removed = buy_cart.pop(idx)
            except Exception:
                return
            try:
                buy_total[0] -= float(removed.get("line_total", removed.get("price", 0.0)))
            except Exception:
                logging.exception("Suppressed exception")
            buy_total[0] = max(0.0, buy_total[0])
            update_buy_display()

        def _open_buy_cart_popup():
            if not buy_cart:
                self._popup_show_info("Empty Cart", "Your buy cart is empty.", sound = "popup")
                return

            popup = customtkinter.CTkToplevel(self.root)
            popup.title("Buy Cart")
            popup.geometry("620x460")
            popup.transient(self.root)

            header = customtkinter.CTkLabel(
                popup,
                text = f"Cart Items: {_buy_cart_units()} | Total: {format_price(buy_total[0])}",
                font = customtkinter.CTkFont(size = 14, weight = "bold"),
            )
            header.pack(pady = (10, 6))

            scroll = customtkinter.CTkScrollableFrame(popup)
            scroll.pack(fill = "both", expand = True, padx = 10, pady = 6)

            def _refresh():
                for w in scroll.winfo_children():
                    try:
                        w.destroy()
                    except Exception:
                        logging.exception("Suppressed exception")

                for idx, entry in enumerate(buy_cart):
                    item = entry.get("item", {})
                    qty = max(1, int(entry.get("quantity", 1)))
                    unit_price = float(entry.get("price", 0.0))
                    line_total = float(entry.get("line_total", unit_price * qty))

                    row = customtkinter.CTkFrame(scroll)
                    row.pack(fill = "x", padx = 6, pady = 4)

                    title = f"{self._format_item_name(item)} x{qty}"
                    customtkinter.CTkLabel(row, text = title, anchor = "w", font = customtkinter.CTkFont(size = 12, weight = "bold")).pack(side = "left", padx = 8, pady = 6)
                    customtkinter.CTkLabel(row, text = f"{format_price(unit_price)} ea | {format_price(line_total)} total", anchor = "e").pack(side = "left", padx = 8)

                    rm_btn = self._create_sound_button(
                        row,
                        "Remove",
                        lambda i = idx: (_remove_buy_cart_index(i), _refresh()),
                        width = 90,
                        height = 28,
                        fg_color = "#8B0000",
                    )
                    rm_btn.pack(side = "right", padx = 8)

                header.configure(text = f"Cart Items: {_buy_cart_units()} | Total: {format_price(buy_total[0])}")

            footer = customtkinter.CTkFrame(popup, fg_color = "transparent")
            footer.pack(fill = "x", padx = 10, pady = (6, 10))
            self._create_sound_button(footer, "Clear Cart", lambda: (buy_cart.clear(), buy_total.__setitem__(0, 0.0), update_buy_display(), _refresh()), width = 120, height = 30, fg_color = "#8B0000").pack(side = "left")
            self._create_sound_button(footer, "Close", popup.destroy, width = 120, height = 30).pack(side = "right")

            _refresh()

        shop_categories = {}
        for item in store_inventory:
            cat = item.get("shop_category") or item.get("armory_category") or item.get("_table_category") or "Uncategorized"
            shop_categories.setdefault(cat, []).append(item)

        # Show category navigation when there are multiple main categories,
        # or when a single main category still branches into subcategories.
        show_shop_category_menu = len(shop_categories) > 1
        if not show_shop_category_menu and shop_categories:
            for _cat_items in shop_categories.values():
                _subcats = set()
                for _it in _cat_items:
                    _sub = _it.get("shop_subcategory") or _it.get("armory_subcategory") or _it.get("subtype") or "General"
                    _subcats.add(str(_sub))
                if len(_subcats) > 1:
                    show_shop_category_menu = True
                    break

        if not show_shop_category_menu:

            buy_scroll = customtkinter.CTkScrollableFrame(buy_tab)
            buy_scroll.pack(fill = "both", expand = True)

            for item in store_inventory:
                item_frame = customtkinter.CTkFrame(buy_scroll)
                item_frame.pack(fill = "x", pady = 5, padx = 10)

                if _is_shop_item_relevant(item):
                    item_frame.configure(fg_color = "#2a4a2a")

                buy_price = _get_store_buy_price(item)

                item_name_text = self._format_item_name(item)
                if _is_shop_item_relevant(item):
                    item_name_text = "⭐ " + item_name_text
                name_label = customtkinter.CTkLabel(item_frame, text = f"{item_name_text} - {format_price(buy_price)}", font = customtkinter.CTkFont(size = 13, weight = "bold"), anchor = "w")
                name_label.pack(anchor = "w", padx = 10, pady =(8, 2))

                if item.get("description"):
                    desc_label = customtkinter.CTkLabel(item_frame, text = item.get("description")[:100]+"..."if len(item.get("description", ""))>100 else item.get("description", ""), font = customtkinter.CTkFont(size = 10), text_color = "gray", wraplength = 400, justify = "left", anchor = "w")
                    desc_label.pack(anchor = "w", padx = 10, pady =(0, 5))

                info_parts = []
                if item.get("weight"):
                    info_parts.append(f"Weight: {self._format_weight(item.get('weight'))}")
                if item.get("caliber"):
                    cal = item.get("caliber")
                    if isinstance(cal, list):
                        cal = ", ".join(str(c) for c in cal)
                    info_parts.append(f"Caliber: {cal}")
                if item.get("rarity"):
                    info_parts.append(f"Rarity: {item.get('rarity')}")
                if item.get("type"):
                    info_parts.append(f"Type: {item.get('type')}")
                if item.get("pen"):
                    info_parts.append(f"Pen: {item.get('pen')}")
                if item.get("ammo_labels") and isinstance(item.get("ammo_labels"), list):
                    info_parts.append(" / ".join(str(x) for x in item.get("ammo_labels") if x))
                if _is_new_historical_firearm(item):
                    info_parts.append("Historical Premium x25")
                info_parts.append(f"Available: {int(item.get('_shop_available_qty', 1) or 1)}")

                if info_parts:
                    info_label = customtkinter.CTkLabel(item_frame, text = " | ".join(info_parts), font = customtkinter.CTkFont(size = 10), text_color = "orange")
                    info_label.pack(anchor = "w", padx = 10, pady =(0, 5))

                qty_var = customtkinter.StringVar(value = "1")

                def add_to_buy_cart(it = item, price = buy_price, qv = qty_var):
                    try:
                        qty = max(1, int((qv.get() or "1").strip()))
                    except Exception:
                        qty = 1
                    _add_item_to_buy_cart(it, price, qty)

                btn_row = customtkinter.CTkFrame(item_frame, fg_color = "transparent")
                btn_row.pack(anchor = "e", padx = 10, pady = 8)
                inspect_btn = self._create_sound_button(btn_row, "Inspect", lambda it = item, pr = buy_price: self._open_shop_item_inspect(it, pr, table_data, store, on_test_firearm_purchase), width = 80, height = 30, font = customtkinter.CTkFont(size = 11))
                inspect_btn.pack(side = "left", padx = (0, 6))
                customtkinter.CTkLabel(btn_row, text = "Qty:", font = customtkinter.CTkFont(size = 11)).pack(side = "left", padx = (0, 4))
                customtkinter.CTkEntry(btn_row, textvariable = qty_var, width = 52).pack(side = "left", padx = (0, 6))
                add_btn = self._create_sound_button(btn_row, f"Buy({format_price(buy_price)})", add_to_buy_cart, width = 120, height = 30, font = customtkinter.CTkFont(size = 11))
                add_btn.pack(side = "left")

        else:

            buy_content = customtkinter.CTkFrame(buy_tab)
            buy_content.pack(fill = "both", expand = True)

            buy_content.grid_columnconfigure(0, weight = 0)
            buy_content.grid_columnconfigure(1, weight = 1)
            buy_content.grid_rowconfigure(0, weight = 1)

            shop_cat_frame = customtkinter.CTkScrollableFrame(buy_content, width = 200)
            shop_cat_frame.grid(row = 0, column = 0, sticky = "ns", padx =(0, 10))

            shop_items_frame = customtkinter.CTkFrame(buy_content)
            shop_items_frame.grid(row = 0, column = 1, sticky = "nsew")

            shop_items_scroll = [None]
            shop_cat_buttons = {}
            shop_selected_cat = [None]

            def render_shop_item_list(items_list, parent):
                for item in items_list:
                    item_frame = customtkinter.CTkFrame(parent)
                    item_frame.pack(fill = "x", pady = 5, padx = 10)

                    if _is_shop_item_relevant(item):
                        item_frame.configure(fg_color = "#2a4a2a")

                    buy_price = _get_store_buy_price(item)

                    item_name_text = self._format_item_name(item)
                    if _is_shop_item_relevant(item):
                        item_name_text = "⭐ " + item_name_text
                    name_label = customtkinter.CTkLabel(item_frame, text = f"{item_name_text} - {format_price(buy_price)}", font = customtkinter.CTkFont(size = 13, weight = "bold"), anchor = "w")
                    name_label.pack(anchor = "w", padx = 10, pady =(8, 2))

                    if item.get("description"):
                        desc_label = customtkinter.CTkLabel(item_frame, text = item.get("description")[:100] + "..." if len(item.get("description", "")) > 100 else item.get("description", ""), font = customtkinter.CTkFont(size = 10), text_color = "gray", wraplength = 400, justify = "left", anchor = "w")
                        desc_label.pack(anchor = "w", padx = 10, pady =(0, 5))

                    info_parts = []
                    if item.get("weight"):
                        info_parts.append(f"Weight: {self._format_weight(item.get('weight'))}")
                    if item.get("caliber"):
                        cal = item.get("caliber")
                        if isinstance(cal, list):
                            cal = ", ".join(str(c) for c in cal)
                        info_parts.append(f"Caliber: {cal}")
                    if item.get("rarity"):
                        info_parts.append(f"Rarity: {item.get('rarity')}")
                    if item.get("type"):
                        info_parts.append(f"Type: {item.get('type')}")
                    if item.get("pen"):
                        info_parts.append(f"Pen: {item.get('pen')}")
                    if item.get("ammo_labels") and isinstance(item.get("ammo_labels"), list):
                        info_parts.append(" / ".join(str(x) for x in item.get("ammo_labels") if x))
                    if _is_new_historical_firearm(item):
                        info_parts.append("Historical Premium x25")
                    info_parts.append(f"Available: {int(item.get('_shop_available_qty', 1) or 1)}")

                    if info_parts:
                        info_label = customtkinter.CTkLabel(item_frame, text = " | ".join(info_parts), font = customtkinter.CTkFont(size = 10), text_color = "orange")
                        info_label.pack(anchor = "w", padx = 10, pady =(0, 5))

                    qty_var = customtkinter.StringVar(value = "1")

                    def add_to_buy_cart(it = item, price = buy_price, qv = qty_var):
                        try:
                            qty = max(1, int((qv.get() or "1").strip()))
                        except Exception:
                            qty = 1
                        _add_item_to_buy_cart(it, price, qty)

                    btn_row = customtkinter.CTkFrame(item_frame, fg_color = "transparent")
                    btn_row.pack(anchor = "e", padx = 10, pady = 8)
                    inspect_btn = self._create_sound_button(btn_row, "Inspect", lambda it = item, pr = buy_price: self._open_shop_item_inspect(it, pr, table_data, store, on_test_firearm_purchase), width = 80, height = 30, font = customtkinter.CTkFont(size = 11))
                    inspect_btn.pack(side = "left", padx = (0, 6))
                    customtkinter.CTkLabel(btn_row, text = "Qty:", font = customtkinter.CTkFont(size = 11)).pack(side = "left", padx = (0, 4))
                    customtkinter.CTkEntry(btn_row, textvariable = qty_var, width = 52).pack(side = "left", padx = (0, 6))
                    add_btn = self._create_sound_button(btn_row, f"Buy({format_price(buy_price)})", add_to_buy_cart, width = 120, height = 30, font = customtkinter.CTkFont(size = 11))
                    add_btn.pack(side = "left")

            def show_shop_category(category_name):
                try:
                    if shop_items_scroll[0] is not None:
                        try:
                            shop_items_scroll[0].pack_forget()
                        except Exception:
                            logging.exception("Suppressed exception")
                        try:
                            shop_items_scroll[0].destroy()
                        except Exception:
                            logging.exception("Suppressed exception")
                        shop_items_scroll[0] = None
                except Exception:
                    logging.exception("Suppressed exception")
                try:
                    for widget in shop_items_frame.winfo_children():
                        try:
                            widget.destroy()
                        except Exception:
                            logging.exception("Suppressed exception")
                except Exception:
                    logging.exception("Suppressed exception")

                try:
                    shop_selected_cat[0] = category_name
                    for name, btn in shop_cat_buttons.items():
                        try:
                            if name == category_name:
                                btn.configure(border_color = "white", border_width = 2)
                            else:
                                btn.configure(border_width = 0)
                        except Exception:
                            logging.exception("Suppressed exception")
                except Exception:
                    logging.exception("Suppressed exception")

                cat_items = shop_categories.get(category_name, [])

                subcats = {}
                for it in cat_items:
                    sub = it.get("shop_subcategory") or it.get("armory_subcategory") or it.get("subtype") or "General"
                    subcats.setdefault(sub, []).append(it)

                if len(subcats) <= 1:
                    try:
                        shop_items_scroll[0] = customtkinter.CTkScrollableFrame(shop_items_frame) # type: ignore
                        shop_items_scroll[0].pack(fill = "both", expand = True)
                    except Exception:
                        shop_items_scroll[0] = None

                    parent = shop_items_scroll[0] if shop_items_scroll[0] is not None else shop_items_frame

                    cat_title = customtkinter.CTkLabel(parent, text = category_name, font = customtkinter.CTkFont(size = 18, weight = "bold"))
                    cat_title.pack(pady =(10, 6), anchor = "w", padx = 10)

                    render_shop_item_list(cat_items, parent)
                else:
                    shop_items_frame.grid_rowconfigure(0, weight = 1)
                    shop_items_frame.grid_columnconfigure(0, weight = 0)
                    shop_items_frame.grid_columnconfigure(1, weight = 1)

                    subcat_scroll = customtkinter.CTkScrollableFrame(shop_items_frame, width = 160)
                    subcat_scroll.grid(row = 0, column = 0, sticky = "ns", padx =(0, 6))

                    content_right = customtkinter.CTkFrame(shop_items_frame)
                    content_right.grid(row = 0, column = 1, sticky = "nsew")

                    try:
                        shop_items_scroll[0] = customtkinter.CTkScrollableFrame(content_right) # type: ignore
                        shop_items_scroll[0].pack(fill = "both", expand = True)
                    except Exception:
                        shop_items_scroll[0] = None

                    subcat_buttons = {}
                    selected_subcat = [None]

                    def _render_shop_subcat_items(sname, sub_items, target_frame, scroll_holder):
                        for _w in target_frame.winfo_children():
                            try:
                                _w.destroy()
                            except Exception:
                                logging.exception("Suppressed exception")

                        sub2cats = {}
                        for it2 in sub_items:
                            s2 = it2.get("shop_subcategory2") or it2.get("armory_subcategory2") or "General"
                            sub2cats.setdefault(s2, []).append(it2)

                        if len(sub2cats) <= 1:
                            try:
                                _single_scroll = customtkinter.CTkScrollableFrame(target_frame)
                                _single_scroll.pack(fill = "both", expand = True)
                            except Exception:
                                _single_scroll = target_frame

                            sub_title = customtkinter.CTkLabel(_single_scroll, text = sname, font = customtkinter.CTkFont(size = 16, weight = "bold"))
                            sub_title.pack(pady =(6, 12), anchor = "w", padx = 10)
                            render_shop_item_list(sub_items, _single_scroll)
                        else:
                            sub2_layout = customtkinter.CTkFrame(target_frame, fg_color = "transparent")
                            sub2_layout.pack(fill = "both", expand = True)

                            sub2_layout.grid_rowconfigure(0, weight = 1)
                            sub2_layout.grid_columnconfigure(0, weight = 0)
                            sub2_layout.grid_columnconfigure(1, weight = 1)

                            sub2_scroll = customtkinter.CTkScrollableFrame(sub2_layout, width = 130)
                            sub2_scroll.grid(row = 0, column = 0, sticky = "ns", padx =(0, 6))

                            sub2_right = customtkinter.CTkFrame(sub2_layout)
                            sub2_right.grid(row = 0, column = 1, sticky = "nsew")

                            try:
                                sub2_items_scroll = customtkinter.CTkScrollableFrame(sub2_right)
                                sub2_items_scroll.pack(fill = "both", expand = True, padx = 0, pady = 0)
                            except Exception:
                                sub2_items_scroll = None

                            sub2_buttons = {}
                            selected_sub2 = [None]

                            def make_sub2_btn(s2name):
                                def on_click():
                                    for w2 in sub2_right.winfo_children():
                                        w2.destroy()
                                    try:
                                        s2_scroll = customtkinter.CTkScrollableFrame(sub2_right)
                                        s2_scroll.pack(fill = "both", expand = True, padx = 0, pady = 0)
                                    except Exception:
                                        s2_scroll = None
                                    s2_title = customtkinter.CTkLabel(sub2_right, text = s2name, font = customtkinter.CTkFont(size = 16, weight = "bold"))
                                    s2_title.pack(pady =(6, 12), anchor = "w", padx = 10)
                                    render_shop_item_list(sub2cats.get(s2name, []), s2_scroll if s2_scroll is not None else sub2_right)
                                    selected_sub2[0] = s2name
                                    for nm2, b2 in sub2_buttons.items():
                                        try:
                                            if nm2 == s2name:
                                                b2.configure(border_color = "white", border_width = 2)
                                            else:
                                                b2.configure(border_width = 0)
                                        except Exception:
                                            logging.exception("Suppressed exception")
                                return on_click

                            for s2name in sorted(sub2cats.keys()):
                                has_highlighted2 = any(_is_shop_item_relevant(it2) for it2 in sub2cats.get(s2name, []))
                                btn_text2 = s2name if not has_highlighted2 else ("⭐ " + s2name)
                                btn_kwargs2 = {"width":110, "height":30, "font":customtkinter.CTkFont(size = 10)}
                                if has_highlighted2:
                                    btn_kwargs2["fg_color"] = "#2a8a2a"
                                btn2 = self._create_sound_button(sub2_scroll, btn_text2, make_sub2_btn(s2name), **btn_kwargs2)
                                btn2.pack(fill = "x", pady = 3, padx = 6)
                                sub2_buttons[s2name] = btn2

                            first2 = sorted(sub2cats.keys())[0]
                            s2_title = customtkinter.CTkLabel(sub2_right, text = first2, font = customtkinter.CTkFont(size = 16, weight = "bold"))
                            s2_title.pack(pady =(6, 12), anchor = "w", padx = 10)
                            render_shop_item_list(sub2cats.get(first2, []), sub2_items_scroll if sub2_items_scroll is not None else sub2_right)
                            selected_sub2[0] = first2
                            for nm2, b2 in sub2_buttons.items():
                                try:
                                    if nm2 == first2:
                                        b2.configure(border_color = "white", border_width = 2)
                                    else:
                                        b2.configure(border_width = 0)
                                except Exception:
                                    logging.exception("Suppressed exception")

                    def make_subcat_btn(sname):
                        def on_click():
                            shop_items_scroll[0] = None
                            _render_shop_subcat_items(sname, subcats.get(sname, []), content_right, shop_items_scroll[0])
                            selected_subcat[0] = sname
                            for nm, b in subcat_buttons.items():
                                try:
                                    if nm == sname:
                                        b.configure(border_color = "white", border_width = 2)
                                    else:
                                        b.configure(border_width = 0)
                                except Exception:
                                    logging.exception("Suppressed exception")
                        return on_click

                    for sname in sorted(subcats.keys()):
                        has_highlighted = any(_is_shop_item_relevant(it) for it in subcats.get(sname, []))
                        btn_text = sname if not has_highlighted else ("⭐ " + sname)
                        btn_kwargs = {"width":140, "height":30, "font":customtkinter.CTkFont(size = 10)}
                        if has_highlighted:
                            btn_kwargs["fg_color"] = "#2a8a2a"
                        btn = self._create_sound_button(subcat_scroll, btn_text, make_subcat_btn(sname), **btn_kwargs)
                        btn.pack(fill = "x", pady = 3, padx = 6)
                        subcat_buttons[sname] = btn

                    first_sub = sorted(subcats.keys())[0]
                    _render_shop_subcat_items(first_sub, subcats.get(first_sub, []), content_right, shop_items_scroll[0])
                    selected_subcat[0] = first_sub
                    for nm, b in subcat_buttons.items():
                        try:
                            if nm == first_sub:
                                b.configure(border_color = "white", border_width = 2)
                            else:
                                b.configure(border_width = 0)
                        except Exception:
                            logging.exception("Suppressed exception")

            sorted_shop_cats = sorted(shop_categories.keys())

            for cat_name in sorted_shop_cats:
                has_highlighted = any(_is_shop_item_relevant(it) for it in shop_categories.get(cat_name, []))
                btn_text = cat_name if not has_highlighted else ("⭐ " + cat_name)
                cat_kwargs = {"width":180, "height":35, "font":customtkinter.CTkFont(size = 11)}
                if has_highlighted:
                    cat_kwargs["fg_color"] = "#2a8a2a"
                cat_btn = self._create_sound_button(shop_cat_frame, btn_text, lambda c = cat_name: show_shop_category(c), **cat_kwargs)
                cat_btn.pack(pady = 3, padx = 5)
                shop_cat_buttons[cat_name] = cat_btn

            if sorted_shop_cats:
                shop_selected_cat[0] = sorted_shop_cats[0]
                for name, btn in shop_cat_buttons.items():
                    try:
                        if name == shop_selected_cat[0]:
                            btn.configure(border_color = "white", border_width = 2)
                        else:
                            btn.configure(border_width = 0)
                    except Exception:
                        logging.exception("Suppressed exception")
                show_shop_category(sorted_shop_cats[0])

        sell_scroll = customtkinter.CTkScrollableFrame(sell_tab)
        sell_scroll.pack(fill = "both", expand = True)

        sell_cart =[]
        sell_total =[0]

        def update_sell_display():
            money_label.configure(text = f"Your Money: {format_price(player_money[0])} | Sell Value: {format_price(sell_total[0])}")

        all_player_items = get_all_player_items()

        for item_data in all_player_items:
            item = item_data["item"]
            location = item_data["location"]
            item_idx = item_data["index"]

            if item.get("_from_armory"):
                continue

            item_frame = customtkinter.CTkFrame(sell_scroll)
            item_frame.pack(fill = "x", pady = 5, padx = 10)

            base_value = self._compute_item_value_with_installed_components(item)
            effective_value = _apply_sale_modifiers(base_value, item, table_data)
            sell_price = int(effective_value * buy_mult * _get_item_market_multiplier(item, market_demand))
            if item.get("firearm") and float(item.get("rounds_fired", 0) or 0) > 0:
                sell_price = max(100, sell_price)

            location_text = location.replace("equipment.", "").replace(".list.", " #").replace(".subslot.", " sub#")
            name_label = customtkinter.CTkLabel(item_frame, text = f"{self._format_item_name(item)} - {format_price(sell_price)}", font = customtkinter.CTkFont(size = 13, weight = "bold"), anchor = "w")
            name_label.pack(anchor = "w", padx = 10, pady =(8, 2))

            loc_label = customtkinter.CTkLabel(item_frame, text = f"Location: {location_text}", font = customtkinter.CTkFont(size = 10), text_color = "gray", anchor = "w")
            loc_label.pack(anchor = "w", padx = 10, pady =(0, 5))

            purchase_price = item.get("_purchase_price")
            if purchase_price is not None:
                profit = sell_price - purchase_price
                profit_str = (f"+{format_price(profit)}" if profit >= 0 else f"-{format_price(abs(profit))}")
                profit_color = "#44cc44" if profit >= 0 else "#ff6644"
                pp_label = customtkinter.CTkLabel(item_frame, text = f"Paid: {format_price(purchase_price)}  |  P&L: {profit_str}", font = customtkinter.CTkFont(size = 10), text_color = profit_color, anchor = "w")
                pp_label.pack(anchor = "w", padx = 10, pady =(0, 3))

            def add_to_sell_cart(loc = location, i = item_idx, it = item, price = sell_price):
                cart_key = f"{loc}:{i}"
                if cart_key in[f"{s['location']}:{s['index']}"for s in sell_cart]:
                    self._popup_show_info("Already Added", "This item is already in your sell cart.", sound = "popup")
                    return
                sell_cart.append({"location":loc, "index":i, "item":it, "price":price})
                sell_total[0]+=price
                update_sell_display()
                self._play_ui_sound("click")

            add_btn = self._create_sound_button(item_frame, f"Sell({format_price(sell_price)})", add_to_sell_cart, width = 120, height = 30, font = customtkinter.CTkFont(size = 11))
            add_btn.pack(anchor = "e", padx = 10, pady = 8)

        if store.get("accepts_trades"):
            trade_main_frame = customtkinter.CTkFrame(trade_tab)
            trade_main_frame.pack(fill = "both", expand = True)

            trade_main_frame.grid_columnconfigure(0, weight = 1)
            trade_main_frame.grid_columnconfigure(1, weight = 1)
            trade_main_frame.grid_rowconfigure(1, weight = 1)

            your_label = customtkinter.CTkLabel(trade_main_frame, text = "Your Items", font = customtkinter.CTkFont(size = 14, weight = "bold"))
            your_label.grid(row = 0, column = 0, pady =(10, 5))

            store_label = customtkinter.CTkLabel(trade_main_frame, text = "Store Items", font = customtkinter.CTkFont(size = 14, weight = "bold"))
            store_label.grid(row = 0, column = 1, pady =(10, 5))

            your_scroll = customtkinter.CTkScrollableFrame(trade_main_frame)
            your_scroll.grid(row = 1, column = 0, sticky = "nsew", padx = 5, pady = 5)

            store_scroll = customtkinter.CTkScrollableFrame(trade_main_frame)
            store_scroll.grid(row = 1, column = 1, sticky = "nsew", padx = 5, pady = 5)

            trade_offer = {"your_items":[], "store_items":[]}
            trade_values = {"your_total":0, "store_total":0}

            trade_status_label = customtkinter.CTkLabel(trade_main_frame, text = "Your offer: $0 | Store offer: $0", font = customtkinter.CTkFont(size = 12))
            trade_status_label.grid(row = 2, column = 0, columnspan = 2, pady = 10)

            def update_trade_display():
                trade_status_label.configure(text = f"Your offer: {format_price(trade_values['your_total'])} | Store offer: {format_price(trade_values['store_total'])}")

            for item_data in all_player_items:
                item = item_data["item"]
                location = item_data["location"]
                item_idx = item_data["index"]

                if item.get("_from_armory"):
                    continue

                item_frame = customtkinter.CTkFrame(your_scroll)
                item_frame.pack(fill = "x", pady = 3, padx = 5)

                trade_value = int(self._compute_item_value_with_installed_components(item) * buy_mult * _get_item_market_multiplier(item, market_demand))
                location_text = location.replace("equipment.", "").replace(".list.", " #").replace(".subslot.", " sub#")

                name_label = customtkinter.CTkLabel(item_frame, text = f"{self._format_item_name(item)}({format_price(trade_value)})", font = customtkinter.CTkFont(size = 11), anchor = "w")
                name_label.pack(anchor = "w", padx = 8, pady =(5, 0))

                loc_label = customtkinter.CTkLabel(item_frame, text = f"{location_text}", font = customtkinter.CTkFont(size = 9), text_color = "gray", anchor = "w")
                loc_label.pack(anchor = "w", padx = 8, pady =(0, 3))

                def toggle_your_item(loc = location, i = item_idx, it = item, val = trade_value, frame = item_frame):
                    cart_key = f"{loc}:{i}"
                    existing =[idx for idx, e in enumerate(trade_offer["your_items"])if f"{e['location']}:{e['index']}"==cart_key]
                    if existing:
                        trade_offer["your_items"].pop(existing[0])
                        trade_values["your_total"]-=val
                        frame.configure(fg_color =("gray86", "gray17"))
                    else:
                        trade_offer["your_items"].append({"location":loc, "index":i, "item":it, "value":val})
                        trade_values["your_total"]+=val
                        frame.configure(fg_color =("green", "darkgreen"))
                    update_trade_display()
                    self._play_ui_sound("click")

                item_frame.bind("<Button-1>", lambda e, f = toggle_your_item:f())
                name_label.bind("<Button-1>", lambda e, f = toggle_your_item:f())
                loc_label.bind("<Button-1>", lambda e, f = toggle_your_item:f())

            for item in store_inventory:
                item_frame = customtkinter.CTkFrame(store_scroll)
                item_frame.pack(fill = "x", pady = 3, padx = 5)

                trade_value = int(self._compute_item_value_with_installed_components(item) * sell_mult * _get_item_market_multiplier(item, market_demand))

                name_label = customtkinter.CTkLabel(item_frame, text = f"{self._format_item_name(item)}({format_price(trade_value)})", font = customtkinter.CTkFont(size = 11), anchor = "w")
                name_label.pack(anchor = "w", padx = 8, pady = 5)

                def toggle_store_item(it = item, val = trade_value, frame = item_frame):
                    item_id = it.get("id", id(it))
                    existing =[idx for idx, e in enumerate(trade_offer["store_items"])if e["item"].get("id", id(e["item"]))==item_id]
                    if existing:
                        trade_offer["store_items"].pop(existing[0])
                        trade_values["store_total"]-=val
                        frame.configure(fg_color =("gray86", "gray17"))
                    else:
                        trade_offer["store_items"].append({"item":it.copy(), "value":val})
                        trade_values["store_total"]+=val
                        frame.configure(fg_color =("green", "darkgreen"))
                    update_trade_display()
                    self._play_ui_sound("click")

                item_frame.bind("<Button-1>", lambda e, f = toggle_store_item:f())
                name_label.bind("<Button-1>", lambda e, f = toggle_store_item:f())

            def complete_trade():
                if not trade_offer["your_items"]and not trade_offer["store_items"]:
                    self._popup_show_info("Empty Trade", "Select items to trade.", sound = "popup")
                    return

                diff = trade_values["store_total"]-trade_values["your_total"]

                if diff >player_money[0]:
                    self._popup_show_info("Not Enough Money", f"This trade requires {format_price(diff)} extra but you only have {format_price(player_money[0])}.", sound = "error")
                    return

                try:
                    locations_to_remove = {}
                    for entry in trade_offer["your_items"]:
                        loc = entry["location"]
                        idx = entry["index"]
                        if loc not in locations_to_remove:
                            locations_to_remove[loc]=[]
                        locations_to_remove[loc].append(idx)

                    for loc in locations_to_remove:
                        locations_to_remove[loc]= sorted(locations_to_remove[loc], reverse = True)

                    for loc, indices in locations_to_remove.items():
                        for idx in indices:
                            remove_item_from_location(loc, idx)

                    hands_items = save_data.get("hands", {}).get("items", [])
                    for entry in trade_offer["store_items"]:
                        item_copy = entry["item"].copy()
                        item_copy.pop("_table_category", None)
                        item_copy = add_subslots_to_item(item_copy)
                        _repair_item_parts_durability_recursive(item_copy, 100.0)
                        self._add_item_to_container(hands_items, item_copy)

                    _repair_item_parts_durability_recursive(save_data, 100.0)
                    save_data["hands"]["items"]= hands_items
                    save_data["money"]= player_money[0]-diff
                    self._write_save_to_path(save_path, save_data)

                    your_names =[e["item"].get("name", "Unknown")for e in trade_offer["your_items"]]
                    store_names =[e["item"].get("name", "Unknown")for e in trade_offer["store_items"]]
                    logging.info(f"Trade completed: gave {your_names}, received {store_names}, paid {format_price(diff if diff >0 else 0)}")

                    msg = f"Traded {len(trade_offer['your_items'])} of your item(s) for {len(trade_offer['store_items'])} store item(s)."
                    if diff >0:
                        msg +=f" Paid {format_price(diff)} extra."
                    elif diff <0:
                        msg +=f" Received {format_price(-diff)}."
                    self._popup_show_info("Trade Complete", msg, sound = "success")

                    stop_ui_music()
                    self._open_business_tool()

                except Exception as e:
                    logging.error(f"Failed to complete trade: {e}")
                    self._popup_show_info("Error", f"Failed to complete trade: {e}", sound = "error")

            trade_btn = self._create_sound_button(trade_main_frame, "Complete Trade", complete_trade, width = 200, height = 35, font = customtkinter.CTkFont(size = 13))
            trade_btn.grid(row = 3, column = 0, columnspan = 2, pady = 10)

        button_frame = customtkinter.CTkFrame(main_frame, fg_color = "transparent")
        button_frame.grid(row = 2, column = 0, sticky = "ew", padx = 20, pady = 10)

        def complete_purchase():
            if not buy_cart:
                self._popup_show_info("Empty Cart", "Your buy cart is empty.", sound = "popup")
                return

            if buy_total[0]>player_money[0]:
                self._popup_show_info("Not Enough Money", f"You need {format_price(buy_total[0])} but only have {format_price(player_money[0])}.", sound = "error")
                return

            try:
                hands_items = save_data.get("hands", {}).get("items", [])

                hardcore = bool(table_data.get("additional_settings", {}).get("hardcore_mode", False))
                for cart_entry in buy_cart:
                    qty = max(1, int(cart_entry.get("quantity", 1)))
                    unit_price = float(cart_entry.get("price", 0.0))
                    is_stackable = bool(cart_entry.get("stackable", False))

                    _cart_orig = cart_entry.get("_original_item")
                    if is_stackable:
                        item_copy = cart_entry["item"].copy()
                        _src_table_cat = str(item_copy.get("_table_category") or item_copy.get("table_category") or "").strip().lower()
                        if _src_table_cat == "historical_firearms":
                            item_copy["_is_historical_firearm"] = True
                        item_copy.pop("_table_category", None)
                        item_copy["quantity"] = qty
                        item_copy["_purchase_price"] = unit_price
                        if isinstance(_cart_orig, dict) and _cart_orig.get("firearm") and "rounds_fired" in _cart_orig:
                            item_copy["rounds_fired"] = _cart_orig["rounds_fired"]
                        item_copy = add_subslots_to_item(item_copy)
                        self._apply_random_firearm_attachments(item_copy, table_data, chance = 0.25)
                        _repair_item_parts_durability_recursive(item_copy, 100.0)
                        if hardcore and item_copy.get("firearm") and "rounds_fired" not in item_copy:
                            item_copy["rounds_fired"] = random.randint(0, 2000)
                        self._add_item_to_container(hands_items, item_copy)
                    else:
                        for _ in range(qty):
                            item_copy = cart_entry["item"].copy()
                            _src_table_cat = str(item_copy.get("_table_category") or item_copy.get("table_category") or "").strip().lower()
                            if _src_table_cat == "historical_firearms":
                                item_copy["_is_historical_firearm"] = True
                            item_copy.pop("_table_category", None)
                            item_copy["_purchase_price"] = unit_price
                            if isinstance(_cart_orig, dict) and _cart_orig.get("firearm") and "rounds_fired" in _cart_orig:
                                item_copy["rounds_fired"] = _cart_orig["rounds_fired"]
                            item_copy = add_subslots_to_item(item_copy)
                            self._apply_random_firearm_attachments(item_copy, table_data, chance = 0.25)
                            _repair_item_parts_durability_recursive(item_copy, 100.0)
                            if hardcore and item_copy.get("firearm") and "rounds_fired" not in item_copy:
                                item_copy["rounds_fired"] = random.randint(0, 2000)
                            self._add_item_to_container(hands_items, item_copy)

                _repair_item_parts_durability_recursive(save_data, 100.0)
                save_data["hands"]["items"]= hands_items
                save_data["money"]= player_money[0]-buy_total[0]
                self._write_save_to_path(save_path, save_data)

                item_names = [f"{e['item'].get('name', 'Unknown')} x{max(1, int(e.get('quantity', 1)))}" for e in buy_cart]
                logging.info(f"Purchased items for {format_price(buy_total[0])}: {item_names}")
                self._popup_show_info("Purchase Complete", f"Purchased {_buy_cart_units()} item(s) for {format_price(buy_total[0])}.", sound = "success")

                buy_cart.clear()
                buy_total[0]= 0
                player_money[0]= save_data["money"]
                try:
                    stop_ui_music()
                except Exception:
                    try:
                        self._stop_business_music(music_channel)
                    except Exception:
                        logging.exception("Suppressed exception")
                self._open_business_tool()

            except Exception as e:
                logging.error(f"Failed to complete purchase: {e}")
                self._popup_show_info("Error", f"Failed to complete purchase: {e}", sound = "error")

        def complete_sale():
            if not sell_cart:
                self._popup_show_info("Empty Cart", "Your sell cart is empty.", sound = "popup")
                return

            try:
                locations_to_remove = {}
                for entry in sell_cart:
                    loc = entry["location"]
                    idx = entry["index"]
                    if loc not in locations_to_remove:
                        locations_to_remove[loc]=[]
                    locations_to_remove[loc].append(idx)

                for loc in locations_to_remove:
                    locations_to_remove[loc]= sorted(locations_to_remove[loc], reverse = True)

                for loc, indices in locations_to_remove.items():
                    for idx in indices:
                        remove_item_from_location(loc, idx)

                save_data["money"]= player_money[0]+sell_total[0]
                self._write_save_to_path(save_path, save_data)

                logging.info(f"Sold {len(sell_cart)} items for {format_price(sell_total[0])}")
                self._popup_show_info("Sale Complete", f"Sold {len(sell_cart)} item(s) for {format_price(sell_total[0])}.", sound = "success")

                sell_cart.clear()
                sell_total[0]= 0
                player_money[0]= save_data["money"]
                try:
                    stop_ui_music()
                except Exception:
                    try:
                        self._stop_business_music(music_channel)
                    except Exception:
                        logging.exception("Suppressed exception")
                self._open_business_tool()

            except Exception as e:
                logging.error(f"Failed to complete sale: {e}")
                self._popup_show_info("Error", f"Failed to complete sale: {e}", sound = "error")

        def leave_store():
            def _do_leave(confirmed:bool = True):
                if not confirmed:
                    return
                try:
                    stop_ui_music()
                except Exception:
                    try:
                        self._stop_business_music(music_channel)
                    except Exception:
                        logging.exception("Suppressed exception")
                self._open_business_tool()

            try:
                has_buy = bool(buy_cart)
                has_sell = bool(sell_cart)
                if has_buy or has_sell:
                    parts =[]
                    if has_buy:
                        parts.append(f"{_buy_cart_units()} item(s) in buy cart")
                    if has_sell:
                        parts.append(f"{len(sell_cart)} item(s) in sell cart")
                    details = " and ".join(parts)
                    msg = f"You have {details}.Leaving will discard these items.Leave anyway?"
                    self._popup_confirm("Leave Store", msg, _do_leave)
                    return
            except Exception:
                logging.exception("Suppressed exception")

            _do_leave()

        buy_btn = self._create_sound_button(button_frame, "Complete Purchase", complete_purchase, width = 200, height = 40, font = customtkinter.CTkFont(size = 14))
        buy_btn.pack(side = "left", padx = 10)

        cart_btn = self._create_sound_button(button_frame, "View Buy Cart", _open_buy_cart_popup, width = 180, height = 40, font = customtkinter.CTkFont(size = 14))
        cart_btn.pack(side = "left", padx = 10)

        sell_btn = self._create_sound_button(button_frame, "Complete Sale", complete_sale, width = 200, height = 40, font = customtkinter.CTkFont(size = 14))
        sell_btn.pack(side = "left", padx = 10)

        if store.get("can_order_ammo"):
            order_ammo_btn = self._create_sound_button(
                button_frame, "Order Ammo",
                lambda: self._open_order_ammo_dialog(store, table_data),
                width = 160, height = 40, font = customtkinter.CTkFont(size = 14)
            )
            order_ammo_btn.pack(side = "left", padx = 10)

        back_btn = self._create_sound_button(button_frame, "Leave Store", leave_store, width = 200, height = 40, font = customtkinter.CTkFont(size = 14))
        back_btn.pack(side = "right", padx = 10)

    # ── Order delivery helpers ──────────────────────────────────────────────

    def _check_and_deliver_orders(self):
        """Deliver any pending ammo orders whose delivery time has passed for the current character."""
        try:
            orders = persistentdata.get("pending_orders", [])
            if not orders:
                return
            now = datetime.now()
            save_char = self.currentsave or ""
            save_path = os.path.join(saves_folder or "", save_char + ".sldsv")
            if not save_char or not os.path.exists(save_path):
                return
            due = [o for o in orders if o.get("character_save") == save_char]
            due = [o for o in due if datetime.fromisoformat(o["deliver_at"]) <= now]
            if not due:
                return
            save_data = self._load_file(save_char + ".sldsv")
            if save_data is None:
                return
            hands_items = save_data.get("hands", {}).get("items", [])
            delivered_ids = []
            delivered_names = []
            for order in due:
                item_data = order.get("item_data")
                if not isinstance(item_data, dict):
                    delivered_ids.append(order["order_id"])
                    continue
                item_copy = item_data.copy()
                self._add_item_to_container(hands_items, item_copy)
                delivered_ids.append(order["order_id"])
                delivered_names.append(
                    f"{item_copy.get('name', 'Ammo')} x{item_copy.get('quantity', 1)}"
                )
            save_data["hands"]["items"] = hands_items
            self._write_save_to_path(save_path, save_data)
            persistentdata["pending_orders"] = [
                o for o in orders if o.get("order_id") not in delivered_ids
            ]
            self._save_persistent_data()
            if delivered_names:
                self._popup_show_info(
                    "Order Delivered",
                    "The following ammo orders arrived:\n" + "\n".join(f"  • {n}" for n in delivered_names),
                    sound = "success",
                )
        except Exception:
            logging.exception("Failed to check and deliver pending orders")

    def _open_orders_popup(self):
        """Show all pending ammo orders for the current character."""
        try:
            orders = persistentdata.get("pending_orders", [])
            char_orders = [o for o in orders if o.get("character_save") == (self.currentsave or "")]

            popup = customtkinter.CTkToplevel(self.root)
            popup.title("Pending Ammo Orders")
            popup.transient(self.root)
            popup.grab_set()
            popup.withdraw()

            popup.grid_rowconfigure(1, weight=1)
            popup.grid_columnconfigure(0, weight=1)

            hdr = customtkinter.CTkLabel(popup, text="Pending Ammo Orders",
                                         font=customtkinter.CTkFont(size=18, weight="bold"))
            hdr.grid(row=0, column=0, padx=16, pady=(12, 4), sticky="w")

            if not char_orders:
                customtkinter.CTkLabel(popup, text="No pending orders.",
                                       font=customtkinter.CTkFont(size=13), text_color="gray"
                                       ).grid(row=1, column=0, padx=16, pady=20)
            else:
                scroll = customtkinter.CTkScrollableFrame(popup, width=600, height=360)
                scroll.grid(row=1, column=0, sticky="nsew", padx=16, pady=4)

                now = datetime.now()
                for order in char_orders:
                    card = customtkinter.CTkFrame(scroll)
                    card.pack(fill="x", pady=6, padx=4)

                    item_name = order.get("item_data", {}).get("name", order.get("caliber", "?"))
                    qty = order.get("item_data", {}).get("quantity", 1)
                    store_name = order.get("store_name", "?")
                    cost = order.get("total_cost", 0.0)
                    deliver_at_str = order.get("deliver_at", "")
                    try:
                        deliver_dt = datetime.fromisoformat(deliver_at_str)
                        remaining = deliver_dt - now
                        if remaining.total_seconds() <= 0:
                            time_str = "Ready for pickup"
                            tc = "green"
                        else:
                            h, rem = divmod(int(remaining.total_seconds()), 3600)
                            m = rem // 60
                            time_str = f"Arrives in {h}h {m}m  ({deliver_dt.strftime('%b %d %I:%M %p')})"
                            tc = "orange"
                    except Exception:
                        time_str = deliver_at_str
                        tc = "gray"

                    customtkinter.CTkLabel(card, text=f"{item_name} x{qty}",
                                           font=customtkinter.CTkFont(size=13, weight="bold")
                                           ).pack(anchor="w", padx=10, pady=(6, 0))
                    customtkinter.CTkLabel(card, text=f"From: {store_name}   |   Paid: {format_price(cost)}",
                                           font=customtkinter.CTkFont(size=11), text_color="gray"
                                           ).pack(anchor="w", padx=10)
                    customtkinter.CTkLabel(card, text=time_str,
                                           font=customtkinter.CTkFont(size=11), text_color=tc
                                           ).pack(anchor="w", padx=10, pady=(0, 6))

            btn_row = customtkinter.CTkFrame(popup, fg_color="transparent")
            btn_row.grid(row=2, column=0, padx=16, pady=10, sticky="ew")

            devmode = global_variables.get("devmode", {}).get("value", False)
            if devmode and char_orders:
                def skip_wait():
                    try:
                        for order in persistentdata.get("pending_orders", []):
                            if order.get("character_save") == (self.currentsave or ""):
                                order["deliver_at"] = datetime.now().isoformat()
                        self._save_persistent_data()
                        popup.destroy()
                        self._check_and_deliver_orders()
                        self._open_orders_popup()
                    except Exception:
                        logging.exception("Failed to skip order wait")
                self._create_sound_button(btn_row, "[DEV] Deliver All Now", skip_wait,
                                          width=200, height=34, font=customtkinter.CTkFont(size=12),
                                          fg_color="#8B0000").pack(side="left", padx=(0, 10))

            customtkinter.CTkButton(btn_row, text="Close", command=popup.destroy, width=120).pack(side="left")

            popup.update_idletasks()
            popup.deiconify()
        except Exception:
            logging.exception("Failed to open orders popup")

    def _open_order_ammo_dialog(self, store, table_data):
        """Popup to order ammo from a trader that has can_order_ammo=true.

        Orders cost 10× the normal shop price and arrive at noon the next day.
        """
        try:
            tables = table_data.get("tables", {})
            all_ammo = tables.get("ammunition", [])
            prices = store.get("prices", {"buy": 1.0, "sell": 1.0})
            sell_mult = float(prices.get("sell", 1.0))
            market_demand = _get_market_demand()

            # Build sorted list of unique calibers from ammo table
            caliber_set = []
            seen_cal = set()
            for ammo_def in all_ammo:
                if not isinstance(ammo_def, dict):
                    continue
                cals = ammo_def.get("caliber", [])
                if isinstance(cals, str):
                    cals = [cals]
                for c in cals:
                    if c and c not in seen_cal:
                        seen_cal.add(c)
                        caliber_set.append(c)
            caliber_set.sort()

            if not caliber_set:
                self._popup_show_info("No Ammo", "No ammunition calibers found in table.", sound="popup")
                return

            save_data_local = self._load_file((self.currentsave or "") + ".sldsv")
            if save_data_local is None:
                self._popup_show_info("Error", "Failed to load character data.", sound="error")
                return

            player_money = [save_data_local.get("money", 0)]

            popup = customtkinter.CTkToplevel(self.root)
            popup.title(f"Order Ammo — {store.get('name', 'Trader')}")
            popup.transient(self.root)
            popup.grab_set()
            popup.withdraw()
            popup.geometry("480x540")

            popup.grid_columnconfigure(0, weight=1)
            popup.grid_rowconfigure(3, weight=1)

            # Header
            customtkinter.CTkLabel(popup, text=f"Order Ammo from {store.get('name', 'Trader')}",
                                   font=customtkinter.CTkFont(size=17, weight="bold")
                                   ).grid(row=0, column=0, padx=16, pady=(12, 2), sticky="w")
            customtkinter.CTkLabel(popup,
                                   text="Variant is randomized. Delivery: 12:00 PM next day. Cost: 10× shop price.",
                                   font=customtkinter.CTkFont(size=11), text_color="orange"
                                   ).grid(row=1, column=0, padx=16, pady=(0, 6), sticky="w")

            money_lbl = customtkinter.CTkLabel(popup,
                                               text=f"Your Money: {format_price(player_money[0])}",
                                               font=customtkinter.CTkFont(size=13, weight="bold"),
                                               text_color="green")
            money_lbl.grid(row=2, column=0, padx=16, pady=(0, 4), sticky="w")

            form_frame = customtkinter.CTkFrame(popup)
            form_frame.grid(row=3, column=0, sticky="nsew", padx=16, pady=4)
            form_frame.grid_columnconfigure(0, weight=1)
            form_frame.grid_rowconfigure(1, weight=1)

            # Caliber search + listbox
            customtkinter.CTkLabel(form_frame, text="Caliber:", font=customtkinter.CTkFont(size=13),
                                   anchor="w").grid(row=0, column=0, padx=10, pady=(8, 2), sticky="w")

            search_var = customtkinter.StringVar()
            search_entry = customtkinter.CTkEntry(form_frame, textvariable=search_var,
                                                  placeholder_text="Search calibers…", width=280)
            search_entry.grid(row=1, column=0, padx=10, pady=(0, 4), sticky="ew")

            import tkinter as _tk_ord
            cal_listbox_frame = customtkinter.CTkFrame(form_frame)
            cal_listbox_frame.grid(row=2, column=0, padx=10, pady=(0, 6), sticky="nsew")
            form_frame.grid_rowconfigure(2, weight=1)

            cal_listbox = _tk_ord.Listbox(cal_listbox_frame, selectmode="single",
                                           bg="#2b2b2b", fg="white", selectbackground="#1f538d",
                                           relief="flat", borderwidth=0,
                                           font=("Segoe UI", 11), activestyle="none",
                                           exportselection=False, height=8)
            cal_sb = _tk_ord.Scrollbar(cal_listbox_frame, orient="vertical",
                                        command=cal_listbox.yview)
            cal_listbox.configure(yscrollcommand=cal_sb.set)
            cal_listbox.pack(side="left", fill="both", expand=True)
            cal_sb.pack(side="right", fill="y")

            selected_caliber = [caliber_set[0] if caliber_set else ""]

            def _populate_list(filter_text=""):
                cal_listbox.delete(0, _tk_ord.END)
                ft = filter_text.strip().lower()
                for c in caliber_set:
                    if not ft or ft in c.lower():
                        cal_listbox.insert(_tk_ord.END, c)
                # Reselect previously chosen caliber if visible
                for i in range(cal_listbox.size()):
                    if cal_listbox.get(i) == selected_caliber[0]:
                        cal_listbox.selection_set(i)
                        cal_listbox.see(i)
                        break
                else:
                    if cal_listbox.size() > 0:
                        cal_listbox.selection_set(0)
                        selected_caliber[0] = cal_listbox.get(0)

            def _on_search(*_):
                _populate_list(search_var.get())
                _update_price_label()

            def _on_select(event=None):
                sel = cal_listbox.curselection()
                if sel:
                    selected_caliber[0] = cal_listbox.get(sel[0])
                _update_price_label()

            search_var.trace_add("write", _on_search)
            cal_listbox.bind("<<ListboxSelect>>", _on_select)
            _populate_list()

            # Quantity + price
            qty_row = customtkinter.CTkFrame(form_frame, fg_color="transparent")
            qty_row.grid(row=3, column=0, padx=10, pady=4, sticky="ew")
            customtkinter.CTkLabel(qty_row, text="Quantity:", font=customtkinter.CTkFont(size=13)
                                   ).pack(side="left")
            qty_var = customtkinter.StringVar(value="50")
            customtkinter.CTkEntry(qty_row, textvariable=qty_var, width=100
                                   ).pack(side="left", padx=8)

            price_lbl = customtkinter.CTkLabel(form_frame, text="Est. Cost: —",
                                               font=customtkinter.CTkFont(size=12), text_color="orange")
            price_lbl.grid(row=4, column=0, padx=10, pady=(2, 6), sticky="w")

            def _update_price_label(*_):
                try:
                    cal = selected_caliber[0]
                    qty = max(1, int(qty_var.get() or "1"))
                    unit_price = _estimate_ammo_unit_price(cal, all_ammo, sell_mult, market_demand)
                    total = round(unit_price * qty * 10.0, 2)
                    price_lbl.configure(text=f"Est. Cost: {format_price(total)}  ({format_price(unit_price * 10.0)}/ea × {qty})")
                except Exception:
                    price_lbl.configure(text="Est. Cost: —")

            qty_var.trace_add("write", _update_price_label)
            _update_price_label()

            def place_order():
                try:
                    cal = selected_caliber[0].strip()
                    if not cal:
                        self._popup_show_info("Error", "Select a caliber.", sound="popup")
                        return
                    try:
                        qty = max(1, int(qty_var.get() or "1"))
                    except ValueError:
                        self._popup_show_info("Error", "Enter a valid quantity.", sound="popup")
                        return

                    unit_price = _estimate_ammo_unit_price(cal, all_ammo, sell_mult, market_demand)
                    total_cost = round(unit_price * qty * 10.0, 2)

                    if total_cost > player_money[0]:
                        self._popup_show_info("Not Enough Money",
                                              f"You need {format_price(total_cost)} but have {format_price(player_money[0])}.",
                                              sound="error")
                        return

                    item_data = _resolve_ammo_order_item(cal, qty, table_data)
                    if item_data is None:
                        self._popup_show_info("Error", f"No ammo found for caliber '{cal}'.", sound="error")
                        return

                    now_dt = datetime.now()
                    tomorrow = now_dt + timedelta(days=1)
                    deliver_dt = tomorrow.replace(hour=12, minute=0, second=0, microsecond=0)
                    if now_dt.hour < 12 and now_dt.date() == datetime.now().date():
                        deliver_dt = now_dt.replace(hour=12, minute=0, second=0, microsecond=0)
                        if deliver_dt <= now_dt:
                            deliver_dt = tomorrow.replace(hour=12, minute=0, second=0, microsecond=0)

                    import uuid as _uuid
                    order = {
                        "order_id": str(_uuid.uuid4()),
                        "store_name": store.get("name", "Unknown"),
                        "caliber": cal,
                        "quantity": qty,
                        "total_cost": total_cost,
                        "ordered_at": now_dt.isoformat(),
                        "deliver_at": deliver_dt.isoformat(),
                        "character_save": self.currentsave or "",
                        "item_data": item_data,
                    }

                    if "pending_orders" not in persistentdata:
                        persistentdata["pending_orders"] = []
                    persistentdata["pending_orders"].append(order)

                    save_path_local = os.path.join(saves_folder or "", (self.currentsave or "") + ".sldsv")
                    save_data_upd = self._load_file((self.currentsave or "") + ".sldsv")
                    if save_data_upd is not None:
                        save_data_upd["money"] = player_money[0] - total_cost
                        self._write_save_to_path(save_path_local, save_data_upd)
                        player_money[0] = save_data_upd["money"]
                        money_lbl.configure(text=f"Your Money: {format_price(player_money[0])}")

                    self._save_persistent_data()
                    logging.info(f"Ammo order placed: {qty}× {cal} from {store.get('name')} — {format_price(total_cost)}")
                    self._popup_show_info("Order Placed",
                                          f"Ordered {qty}× {item_data.get('name', cal)}\nCost: {format_price(total_cost)}\nDelivery: {deliver_dt.strftime('%b %d at %I:%M %p')}",
                                          sound="success")
                    popup.destroy()
                except Exception:
                    logging.exception("Failed to place ammo order")
                    self._popup_show_info("Error", "Failed to place order.", sound="error")

            btn_row = customtkinter.CTkFrame(popup, fg_color="transparent")
            btn_row.grid(row=4, column=0, padx=16, pady=12, sticky="ew")
            self._create_sound_button(btn_row, "Place Order", place_order,
                                      width=160, height=36, font=customtkinter.CTkFont(size=13)
                                      ).pack(side="left", padx=(0, 10))
            customtkinter.CTkButton(btn_row, text="Cancel", command=popup.destroy, width=100).pack(side="left")

            popup.update_idletasks()
            popup.deiconify()
        except Exception:
            logging.exception("Failed to open order ammo dialog")

    def _open_ammo_supplier_interface(self, store, table_data):
        """Full UI for an ammo_supplier store type, styled like the regular store."""
        logging.info(f"Opening ammo supplier: {store.get('name')}")

        music_channel = None
        if store.get("music") and store.get("playlist"):
            music_channel = self._start_business_music(store.get("playlist"), first_play=True)

        self._clear_window()
        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(0, weight=1)

        main_frame = customtkinter.CTkFrame(self.root)
        main_frame.grid(row=0, column=0, sticky="nsew")
        main_frame.grid_columnconfigure(0, weight=1)
        main_frame.grid_rowconfigure(1, weight=1)

        free_ammo = bool(store.get("free_ammo", False))
        prices = store.get("prices", {"buy": 1.0, "sell": 1.0})
        sell_mult = float(prices.get("sell", 1.0))

        # ── Header ──────────────────────────────────────────────────────────
        header_frame = customtkinter.CTkFrame(main_frame, fg_color="transparent")
        header_frame.grid(row=0, column=0, sticky="ew", padx=20, pady=10)

        customtkinter.CTkLabel(header_frame, text=store.get("name", "Ammo Supplier"),
                               font=customtkinter.CTkFont(size=24, weight="bold")).pack(pady=(10, 5))
        customtkinter.CTkLabel(header_frame,
                               text=f"Supplier: {store.get('shopkeeper', 'Unknown')}",
                               font=customtkinter.CTkFont(size=14), text_color="gray").pack()

        save_path = os.path.join(saves_folder or "", (self.currentsave or "") + ".sldsv")
        save_data = self._load_file((self.currentsave or "") + ".sldsv")
        if save_data is None:
            self._popup_show_info("Error", "Failed to load character data.", sound="error")
            if music_channel:
                try:
                    self._stop_business_music(music_channel)
                except Exception:
                    logging.exception("Suppressed exception")
            return

        player_money = [save_data.get("money", 0)]

        if free_ammo:
            customtkinter.CTkLabel(header_frame, text="All ammo is FREE",
                                   font=customtkinter.CTkFont(size=13, weight="bold"),
                                   text_color="#44cc44").pack()
        else:
            customtkinter.CTkLabel(header_frame,
                                   text=f"Sells at {sell_mult}x value",
                                   font=customtkinter.CTkFont(size=12), text_color="orange").pack()

        money_label = customtkinter.CTkLabel(header_frame,
                                             text=f"Your Money: {format_price(player_money[0])}",
                                             font=customtkinter.CTkFont(size=16, weight="bold"),
                                             text_color="green")
        money_label.pack(pady=5)

        # ── Song display marquee ─────────────────────────────────────────────
        marquee_label = None
        marquee_job: list = [None]
        prev_track: list = [None]

        def _get_track_info(track_path):
            artist = None
            title = None
            length = None
            try:
                try:
                    sound = pygame.mixer.Sound(track_path)
                    length = float(sound.get_length())
                except Exception:
                    length = None
                try:
                    from mutagen._file import File as MutagenFile
                    mf = MutagenFile(track_path)
                    if mf is not None:
                        tags = getattr(mf, 'tags', {}) or {}
                        def _get_tag(keys):
                            for k in keys:
                                v = tags.get(k)
                                if v:
                                    try:
                                        if isinstance(v, (list, tuple)):
                                            return str(v[0])
                                        return str(v)
                                    except Exception:
                                        return str(v)
                            return None
                        artist = _get_tag(["artist", "ARTIST", "TPE1", "IART"])
                        title = _get_tag(["title", "TITLE", "TIT2", "INAM"])
                except Exception:
                    logging.exception("Suppressed exception")
            except Exception:
                logging.exception("Suppressed exception")
            if not title:
                try:
                    title = os.path.basename(track_path or "")
                except Exception:
                    title = "Unknown"
            return {"artist": artist, "title": title, "length": length}

        def stop_ui_music():
            try:
                if marquee_job[0]:
                    try:
                        self.root.after_cancel(marquee_job[0])  # type: ignore[arg-type]
                    except Exception:
                        logging.exception("Suppressed exception")
                    marquee_job[0] = None
            except Exception:
                logging.exception("Suppressed exception")
            try:
                self._stop_business_music(music_channel)
            except Exception:
                logging.exception("Suppressed exception")

        if music_channel and music_channel.get("track"):
            try:
                track_path = music_channel.get("track")
                info = _get_track_info(track_path)
                base_artist = info.get("artist") or ""
                base_title = info.get("title") or os.path.basename(track_path or "")
                track_len = info.get("length") or 0.0

                marquee_frame = customtkinter.CTkFrame(header_frame, fg_color="black",
                                                       width=500, height=30)
                marquee_frame.pack(pady=(6, 0))
                try:
                    marquee_frame.pack_propagate(False)
                except Exception:
                    logging.exception("Suppressed exception")

                label_font = None
                try:
                    import ctypes
                    import tkinter.font as tkfont
                    fp = os.path.join(os.path.dirname(__file__), "fonts", "Tims_8x5_LCD_Matrix.ttf")
                    if os.path.exists(fp) and hasattr(ctypes, 'windll'):
                        try:
                            FR_PRIVATE = 0x10
                            ctypes.windll.gdi32.AddFontResourceExW(fp, FR_PRIVATE, 0)
                        except Exception:
                            logging.exception("Suppressed exception")
                        try:
                            self.root.update_idletasks()
                            fams = list(tkfont.families())
                            for f in fams:
                                if any(x in f.lower() for x in ("tims", "8x5", "lcd")):
                                    label_font = customtkinter.CTkFont(size=12, family=f)
                                    break
                        except Exception:
                            logging.exception("Suppressed exception")
                except Exception:
                    logging.exception("Suppressed exception")
                if not label_font:
                    label_font = customtkinter.CTkFont(size=12)

                marquee_label = customtkinter.CTkLabel(
                    marquee_frame, text="", anchor="w", font=label_font,
                    width=480, height=26, text_color="#7CFC00")
                marquee_label.pack(anchor="center", padx=4)

                marquee_debug_label = None

                pos = [0]

                def _fmt_time(s):
                    try:
                        s = max(0, int(s))
                        return f"{s // 60}:{s % 60:02d}"
                    except Exception:
                        return "0:00"

                def _update_marquee():
                    try:
                        current = getattr(self, "_current_business_music", music_channel)
                        meta_info = None
                        if current:
                            meta_info = current.get("_meta")
                        try:
                            tp = (current or {}).get('track')
                            if tp != prev_track[0]:
                                prev_track[0] = tp
                                pos[0] = 0
                        except Exception:
                            logging.exception("Suppressed exception")
                        if meta_info:
                            base_artist = meta_info.get("artist") or ""
                            base_title = meta_info.get("title") or os.path.basename((current or {}).get('track') or "")
                            total = meta_info.get("length") or 0.0
                        else:
                            base_artist = ""
                            base_title = os.path.basename((current or {}).get('track') or "")
                            total = 0.0
                            try:
                                if current and not current.get("_meta_loading"):
                                    current["_meta_loading"] = True
                                    def _bg_load():
                                        try:
                                            info2 = _get_track_info((current or {}).get("track"))
                                            def _apply():
                                                try:
                                                    target = getattr(self, "_current_business_music", None) or current
                                                    if target is not None:
                                                        target.update({"_meta": info2})
                                                        try:
                                                            self.root.after(0, _update_marquee)
                                                        except Exception:
                                                            logging.exception("Suppressed exception")
                                                except Exception:
                                                    logging.exception("Suppressed exception")
                                            self.root.after(0, _apply)
                                        except Exception:
                                            logging.exception("Suppressed exception")
                                        finally:
                                            try:
                                                current.pop("_meta_loading", None)
                                            except Exception:
                                                logging.exception("Suppressed exception")
                                    import threading as _thr
                                    _thr.Thread(target=_bg_load, daemon=True).start()
                            except Exception:
                                logging.exception("Suppressed exception")

                        started = (current or {}).get("started_at") or time.time()
                        start_offset = (current or {}).get("start_pos") or 0.0
                        elapsed = (time.time() - started) + float(start_offset)
                        meta = (
                            f"{base_artist} | {base_title} | {_fmt_time(elapsed)}/{_fmt_time(total)}"
                            if (base_artist or base_title)
                            else os.path.basename((music_channel or {}).get("track") or "")
                        )
                        try:
                            self.root.update_idletasks()
                            label_px = marquee_label.winfo_width() or int(marquee_label.cget("width") or 480)
                        except Exception:
                            label_px = 480
                        visible_chars = max(8, int(label_px / max(1, 8)))
                        scrollfull = " " + meta + " "
                        if len(scrollfull) < visible_chars:
                            scrollfull += " " * (visible_chars - len(scrollfull) + 2)
                        doubled = scrollfull * 3
                        marquee_label.configure(text=doubled[pos[0]:pos[0] + visible_chars])
                        pos[0] = (pos[0] + 1) % max(1, len(scrollfull))
                        delay_ms = int(min(500, max(60, 70 + (len(scrollfull) * 3))))
                        marquee_job[0] = self.root.after(delay_ms, _update_marquee)
                    except Exception:
                        try:
                            marquee_label.configure(text=os.path.basename(
                                (getattr(self, "_current_business_music", music_channel) or {}).get("track") or ""))
                        except Exception:
                            logging.exception("Suppressed exception")

                try:
                    import threading as _thr2
                    def _load_meta():
                        try:
                            cur = getattr(self, "_current_business_music", music_channel)
                            if not cur:
                                return
                            info3 = _get_track_info(cur.get("track"))
                            def _apply2():
                                try:
                                    target = getattr(self, "_current_business_music", None) or cur
                                    if target is not None:
                                        target.update({"_meta": info3})
                                        try:
                                            self.root.after(0, _update_marquee)
                                        except Exception:
                                            logging.exception("Suppressed exception")
                                except Exception:
                                    logging.exception("Suppressed exception")
                            self.root.after(0, _apply2)
                        except Exception:
                            logging.exception("Suppressed exception")
                    _thr2.Thread(target=_load_meta, daemon=True).start()
                except Exception:
                    logging.exception("Suppressed exception")

                _update_marquee()
            except Exception:
                logging.exception("Suppressed exception")

        market_demand = _get_market_demand()

        # ── Equipped info ────────────────────────────────────────────────────
        equipped_weapons = self._get_equipped_weapons(save_data, table_data)
        equipped_calibers = set()
        equipped_magazine_systems = set()
        for wpn in equipped_weapons:
            item = wpn.get("item", {})
            cals = item.get("caliber", [])
            if isinstance(cals, str):
                cals = [cals]
            for c in cals:
                if c:
                    equipped_calibers.add(c)
            mag_sys = item.get("magazinesystem")
            if isinstance(mag_sys, str) and mag_sys:
                equipped_magazine_systems.add(mag_sys)
            elif isinstance(mag_sys, list):
                for ms in mag_sys:
                    if isinstance(ms, str) and ms:
                        equipped_magazine_systems.add(ms)

        tables = table_data.get("tables", {})
        all_ammo = tables.get("ammunition", [])
        all_mags = tables.get("magazines", [])
        rarity_weights = table_data.get("rarity_weights", {})

        # Generate stock
        stock = _generate_ammo_supplier_stock(store, tables, equipped_calibers,
                                              equipped_magazine_systems, all_ammo, all_mags,
                                              rarity_weights)

        # Tag each stock item with its available quantity
        _stock_key_counts: dict = {}
        def _stock_key(item_obj):
            cal = item_obj.get("caliber")
            if isinstance(cal, list):
                cal = tuple(cal)
            return (item_obj.get("name"), item_obj.get("id"),
                    cal, item_obj.get("variant"),
                    item_obj.get("_table_category"))
        for _si in stock:
            if not isinstance(_si, dict):
                continue
            _k = _stock_key(_si)
            # ammunition uses its own 'quantity' field; others default to 1
            _avail = int(_si.get("quantity", 1) or 1)
            _stock_key_counts[_k] = max(_stock_key_counts.get(_k, 0), _avail)
        for _si in stock:
            if isinstance(_si, dict):
                _si["_shop_available_qty"] = _stock_key_counts.get(_stock_key(_si), 1)

        def _get_item_price(item_obj):
            if free_ammo:
                return 0.0
            base_value = self._compute_item_value_with_installed_components(item_obj)
            raw = base_value * sell_mult * _get_item_market_multiplier(item_obj, market_demand)
            price = round(raw, 2)
            if str(item_obj.get("_table_category", "")).lower() == "ammunition" and raw > 0 and price < 0.01:
                return 0.01
            return max(0.0, price)

        # ── Cart helpers ────────────────────────────────────────────────────
        buy_cart = []
        buy_total = [0.0]

        def update_money_label():
            if free_ammo:
                money_label.configure(text=f"Your Money: {format_price(player_money[0])}")
            else:
                money_label.configure(
                    text=f"Your Money: {format_price(player_money[0])} | Cart Total: {format_price(buy_total[0])}"
                )

        def _is_stackable(item_obj):
            if str(item_obj.get("_table_category", "")).lower() == "ammunition":
                return True
            if item_obj.get("can_stack") is False:
                return False
            non_stack = ["magazinesystem", "capacity", "firearm", "attachment", "subslots", "loaded", "chambered"]
            return not any(k in item_obj for k in non_stack)

        def _cart_key(item_obj):
            return (item_obj.get("name"), item_obj.get("id"),
                    item_obj.get("caliber"), item_obj.get("variant"),
                    item_obj.get("_table_category"))

        def _buy_cart_units():
            return sum(max(1, int(e.get("quantity", 1))) for e in buy_cart)

        def _cart_qty_for_key(key):
            """How many units of this stock key are already in the cart."""
            total = 0
            for entry in buy_cart:
                if entry.get("_key") == key:
                    total += max(1, int(entry.get("quantity", 1)))
            return total

        def _add_to_cart(item_obj, unit_price, quantity=1):
            try:
                qty = max(1, int(quantity))
            except Exception:
                qty = 1

            avail = int(item_obj.get("_shop_available_qty", 1) or 1)
            already_in_cart = _cart_qty_for_key(_cart_key(item_obj))
            remaining = avail - already_in_cart
            if qty > remaining:
                if remaining <= 0:
                    self._popup_show_info("Out of Stock",
                                          f"No more '{item_obj.get('name', 'item')}' available.",
                                          sound="error")
                else:
                    self._popup_show_info("Not Enough Stock",
                                          f"Only {remaining} more available (already {already_in_cart} in cart, {avail} in stock).",
                                          sound="error")
                return False

            line_total = float(unit_price) * qty
            if not free_ammo and player_money[0] - buy_total[0] < line_total:
                self._popup_show_info("Not Enough Money",
                                      f"Need {format_price(line_total)}, have {format_price(player_money[0] - buy_total[0])} left.",
                                      sound="error")
                return False
            stackable = _is_stackable(item_obj)
            if stackable:
                key = _cart_key(item_obj)
                for entry in buy_cart:
                    if entry.get("stackable") and entry.get("_key") == key:
                        entry["quantity"] = max(1, int(entry.get("quantity", 1))) + qty
                        entry["line_total"] = float(entry.get("line_total", 0.0)) + line_total
                        buy_total[0] += line_total
                        update_money_label()
                        self._play_ui_sound("click")
                        return True
            buy_cart.append({
                "item": item_obj.copy(),
                "price": float(unit_price),
                "quantity": qty,
                "line_total": line_total,
                "stackable": stackable,
                "_key": _cart_key(item_obj),
            })
            buy_total[0] += line_total
            update_money_label()
            self._play_ui_sound("click")
            return True

        def _remove_cart_index(idx):
            if idx < 0 or idx >= len(buy_cart):
                return
            removed = buy_cart.pop(idx)
            buy_total[0] = max(0.0, buy_total[0] - float(removed.get("line_total", 0.0)))
            update_money_label()

        def _open_cart_popup():
            if not buy_cart:
                self._popup_show_info("Empty Cart", "Your cart is empty.", sound="popup")
                return
            cpop = customtkinter.CTkToplevel(self.root)
            cpop.title("Cart")
            cpop.geometry("600x420")
            cpop.transient(self.root)
            cart_hdr = customtkinter.CTkLabel(
                cpop,
                text=f"Cart Items: {_buy_cart_units()} | Total: {format_price(buy_total[0])}",
                font=customtkinter.CTkFont(size=14, weight="bold"),
            )
            cart_hdr.pack(pady=(10, 6))
            cscroll = customtkinter.CTkScrollableFrame(cpop)
            cscroll.pack(fill="both", expand=True, padx=10, pady=6)

            def _crefresh():
                for w in cscroll.winfo_children():
                    try:
                        w.destroy()
                    except Exception:
                        logging.exception("Suppressed exception")
                for idx, entry in enumerate(buy_cart):
                    item = entry.get("item", {})
                    qty = max(1, int(entry.get("quantity", 1)))
                    unit_price = float(entry.get("price", 0.0))
                    line_total = float(entry.get("line_total", unit_price * qty))
                    crow = customtkinter.CTkFrame(cscroll)
                    crow.pack(fill="x", padx=6, pady=4)
                    price_disp = "Free" if free_ammo else f"{format_price(unit_price)} ea | {format_price(line_total)} total"
                    customtkinter.CTkLabel(crow,
                                           text=f"{item.get('name', 'Unknown')} x{qty}",
                                           anchor="w",
                                           font=customtkinter.CTkFont(size=12, weight="bold")
                                           ).pack(side="left", padx=8, pady=6)
                    customtkinter.CTkLabel(crow, text=price_disp, anchor="e").pack(side="left", padx=8)
                    self._create_sound_button(
                        crow, "Remove",
                        lambda i=idx: (_remove_cart_index(i), _crefresh()),
                        width=90, height=28, fg_color="#8B0000"
                    ).pack(side="right", padx=8)
                cart_hdr.configure(
                    text=f"Cart Items: {_buy_cart_units()} | Total: {format_price(buy_total[0])}"
                )

            cfooter = customtkinter.CTkFrame(cpop, fg_color="transparent")
            cfooter.pack(fill="x", padx=10, pady=(6, 10))
            self._create_sound_button(
                cfooter, "Clear Cart",
                lambda: (buy_cart.clear(), buy_total.__setitem__(0, 0.0), update_money_label(), _crefresh()),
                width=120, height=30, fg_color="#8B0000"
            ).pack(side="left")
            self._create_sound_button(cfooter, "Close", cpop.destroy, width=120, height=30).pack(side="right")
            _crefresh()

        # ── Content frame (category nav left + items right) ─────────────────
        content_frame = customtkinter.CTkFrame(main_frame)
        content_frame.grid(row=1, column=0, sticky="nsew", padx=20, pady=10)
        content_frame.grid_columnconfigure(0, weight=0)
        content_frame.grid_columnconfigure(1, weight=1)
        content_frame.grid_rowconfigure(0, weight=1)

        # Build category groups from stock
        RARITY_COLOR = {
            "Common": "white", "Uncommon": "#aaffaa", "Rare": "#aaaaff",
            "Legendary": "#ffcc44", "Mythic": "#ff44ff",
        }
        ammo_items = [s for s in stock if str(s.get("_table_category", "")).lower() == "ammunition"]
        mag_items  = [s for s in stock if str(s.get("_table_category", "")).lower() == "magazines"]
        clip_items = [s for s in stock if str(s.get("_table_category", "")).lower() == "clips"]

        # Caliber set for order tab
        caliber_set = []
        seen_cal_s: set = set()
        for _a in all_ammo:
            if not isinstance(_a, dict):
                continue
            _cals = _a.get("caliber", [])
            if isinstance(_cals, str):
                _cals = [_cals]
            for _c in _cals:
                if _c and _c not in seen_cal_s:
                    seen_cal_s.add(_c)
                    caliber_set.append(_c)
        caliber_set.sort()

        categories = {"Ammunition": ammo_items}
        if mag_items:
            categories["Magazines (Pre-filled)"] = mag_items
        if clip_items:
            categories["Clips"] = clip_items
        categories["Order Caliber"] = []  # virtual tab handled separately

        # Left nav
        cat_nav = customtkinter.CTkScrollableFrame(content_frame, width=190)
        cat_nav.grid(row=0, column=0, sticky="ns", padx=(0, 10))

        # Right content area
        items_area = customtkinter.CTkFrame(content_frame)
        items_area.grid(row=0, column=1, sticky="nsew")
        items_area.grid_rowconfigure(0, weight=1)
        items_area.grid_columnconfigure(0, weight=1)

        items_scroll_holder = [None]  # holds current CTkScrollableFrame

        def _render_category(cat_name):
            # Destroy previous scroll frame
            if items_scroll_holder[0] is not None:
                try:
                    items_scroll_holder[0].destroy()
                except Exception:
                    logging.exception("Suppressed exception")
                items_scroll_holder[0] = None

            # ── Order Caliber pane ──────────────────────────────────────────
            if cat_name == "Order Caliber":
                pane = customtkinter.CTkScrollableFrame(items_area)
                pane.grid(row=0, column=0, sticky="nsew")
                pane.grid_columnconfigure(0, weight=1)
                items_scroll_holder[0] = pane

                customtkinter.CTkLabel(pane,
                                       text="Order a specific caliber",
                                       font=customtkinter.CTkFont(size=15, weight="bold")
                                       ).grid(row=0, column=0, padx=14, pady=(12, 2), sticky="w")
                customtkinter.CTkLabel(pane,
                                       text="Variant is randomized by rarity (may include military variants). Delivery: 12 PM next day.",
                                       font=customtkinter.CTkFont(size=11), text_color="gray",
                                       wraplength=460, justify="left"
                                       ).grid(row=1, column=0, padx=14, pady=(0, 8), sticky="w")

                oform = customtkinter.CTkFrame(pane)
                oform.grid(row=2, column=0, sticky="ew", padx=14, pady=4)
                oform.grid_columnconfigure(0, weight=1)
                oform.grid_rowconfigure(1, weight=1)

                customtkinter.CTkLabel(oform, text="Search caliber:",
                                       font=customtkinter.CTkFont(size=12), anchor="w"
                                       ).grid(row=0, column=0, padx=10, pady=(8, 2), sticky="w")

                o_search_var = customtkinter.StringVar()
                o_search = customtkinter.CTkEntry(oform, textvariable=o_search_var,
                                                  placeholder_text="e.g. 9x19mm…", width=260)
                o_search.grid(row=1, column=0, padx=10, pady=(0, 4), sticky="ew")

                import tkinter as _tk_sup
                lb_frame = customtkinter.CTkFrame(oform)
                lb_frame.grid(row=2, column=0, padx=10, pady=(0, 6), sticky="nsew")
                oform.grid_rowconfigure(2, weight=1)

                o_listbox = _tk_sup.Listbox(lb_frame, selectmode="single",
                                             bg="#2b2b2b", fg="white",
                                             selectbackground="#1f538d",
                                             relief="flat", borderwidth=0,
                                             font=("Segoe UI", 11), activestyle="none",
                                             exportselection=False, height=8)
                o_sb = _tk_sup.Scrollbar(lb_frame, orient="vertical", command=o_listbox.yview)
                o_listbox.configure(yscrollcommand=o_sb.set)
                o_listbox.pack(side="left", fill="both", expand=True)
                o_sb.pack(side="right", fill="y")

                o_selected_cal = [caliber_set[0] if caliber_set else ""]

                def _o_populate(ft=""):
                    o_listbox.delete(0, _tk_sup.END)
                    fl = ft.strip().lower()
                    for c in caliber_set:
                        if not fl or fl in c.lower():
                            o_listbox.insert(_tk_sup.END, c)
                    for i in range(o_listbox.size()):
                        if o_listbox.get(i) == o_selected_cal[0]:
                            o_listbox.selection_set(i)
                            o_listbox.see(i)
                            break
                    else:
                        if o_listbox.size() > 0:
                            o_listbox.selection_set(0)
                            o_selected_cal[0] = o_listbox.get(0)

                def _o_on_search(*_):
                    _o_populate(o_search_var.get())
                    _o_update_price()

                def _o_on_select(event=None):
                    sel = o_listbox.curselection()
                    if sel:
                        o_selected_cal[0] = o_listbox.get(sel[0])
                    _o_update_price()

                o_search_var.trace_add("write", _o_on_search)
                o_listbox.bind("<<ListboxSelect>>", _o_on_select)
                _o_populate()

                qty_row_o = customtkinter.CTkFrame(oform, fg_color="transparent")
                qty_row_o.grid(row=3, column=0, padx=10, pady=4, sticky="ew")
                customtkinter.CTkLabel(qty_row_o, text="Quantity:",
                                       font=customtkinter.CTkFont(size=13)).pack(side="left")
                o_qty_var = customtkinter.StringVar(value="50")
                customtkinter.CTkEntry(qty_row_o, textvariable=o_qty_var, width=100
                                       ).pack(side="left", padx=8)

                o_price_lbl = customtkinter.CTkLabel(oform,
                                                     text="Cost: Free" if free_ammo else "Cost: —",
                                                     font=customtkinter.CTkFont(size=12),
                                                     text_color="#44cc44" if free_ammo else "orange")
                o_price_lbl.grid(row=4, column=0, padx=10, pady=(2, 8), sticky="w")

                def _o_update_price(*_):
                    try:
                        cal = o_selected_cal[0]
                        qty = max(1, int(o_qty_var.get() or "1"))
                        if free_ammo:
                            o_price_lbl.configure(
                                text=f"Cost: Free  (qty: {qty})", text_color="#44cc44")
                        else:
                            up = _estimate_ammo_unit_price(cal, all_ammo, sell_mult, market_demand)
                            total = round(up * qty, 2)
                            o_price_lbl.configure(
                                text=f"Cost: {format_price(total)}  ({format_price(up)}/ea × {qty})",
                                text_color="orange")
                    except Exception:
                        logging.exception("Suppressed exception")

                o_qty_var.trace_add("write", _o_update_price)
                _o_update_price()

                def place_supplier_order():
                    try:
                        cal = o_selected_cal[0].strip()
                        if not cal:
                            self._popup_show_info("Error", "Select a caliber.", sound="popup")
                            return
                        try:
                            qty = max(1, int(o_qty_var.get() or "1"))
                        except ValueError:
                            self._popup_show_info("Error", "Enter a valid quantity.", sound="popup")
                            return

                        if free_ammo:
                            total_cost = 0.0
                        else:
                            up = _estimate_ammo_unit_price(cal, all_ammo, sell_mult, market_demand)
                            total_cost = round(up * qty, 2)
                            if total_cost > player_money[0]:
                                self._popup_show_info(
                                    "Not Enough Money",
                                    f"Need {format_price(total_cost)}, have {format_price(player_money[0])}.",
                                    sound="error")
                                return

                        item_data = _resolve_ammo_order_item(cal, qty, table_data)
                        if item_data is None:
                            self._popup_show_info("Error", f"No ammo found for '{cal}'.", sound="error")
                            return

                        now_dt = datetime.now()
                        tomorrow = now_dt + timedelta(days=1)
                        deliver_dt = tomorrow.replace(hour=12, minute=0, second=0, microsecond=0)
                        if now_dt.hour < 12:
                            same_day = now_dt.replace(hour=12, minute=0, second=0, microsecond=0)
                            if same_day > now_dt:
                                deliver_dt = same_day

                        import uuid as _uuid
                        order = {
                            "order_id": str(_uuid.uuid4()),
                            "store_name": store.get("name", "Ammo Supplier"),
                            "caliber": cal,
                            "quantity": qty,
                            "total_cost": total_cost,
                            "ordered_at": now_dt.isoformat(),
                            "deliver_at": deliver_dt.isoformat(),
                            "character_save": self.currentsave or "",
                            "item_data": item_data,
                        }

                        if "pending_orders" not in persistentdata:
                            persistentdata["pending_orders"] = []
                        persistentdata["pending_orders"].append(order)

                        if not free_ammo:
                            save_data_upd = self._load_file((self.currentsave or "") + ".sldsv")
                            if save_data_upd is not None:
                                save_data_upd["money"] = player_money[0] - total_cost
                                self._write_save_to_path(save_path, save_data_upd)
                                player_money[0] = save_data_upd["money"]
                                update_money_label()

                        self._save_persistent_data()
                        cost_str = "Free" if free_ammo else format_price(total_cost)
                        self._popup_show_info(
                            "Order Placed",
                            f"Ordered {qty}× {item_data.get('name', cal)}\nCost: {cost_str}\nDelivery: {deliver_dt.strftime('%b %d at %I:%M %p')}",
                            sound="success")
                    except Exception:
                        logging.exception("Failed to place supplier order")
                        self._popup_show_info("Error", "Failed to place order.", sound="error")

                self._create_sound_button(oform, "Place Order", place_supplier_order,
                                          width=160, height=36,
                                          font=customtkinter.CTkFont(size=13)
                                          ).grid(row=5, column=0, padx=10, pady=(4, 12), sticky="w")
                return

            # ── Regular stock pane ──────────────────────────────────────────
            items_list = categories.get(cat_name, [])
            pane = customtkinter.CTkScrollableFrame(items_area)
            pane.grid(row=0, column=0, sticky="nsew")
            items_scroll_holder[0] = pane

            if not items_list:
                customtkinter.CTkLabel(pane, text="No items in stock.",
                                       font=customtkinter.CTkFont(size=13),
                                       text_color="gray").pack(padx=20, pady=20)
                return

            for item in items_list:
                unit_price = _get_item_price(item)
                price_str = "Free" if free_ammo else format_price(unit_price)
                is_relevant = any(c in equipped_calibers for c in (
                    [item.get("caliber")] if isinstance(item.get("caliber"), str)
                    else (item.get("caliber") or [])
                ))
                item_frame = customtkinter.CTkFrame(pane)
                if is_relevant:
                    item_frame.configure(fg_color="#2a4a2a")
                item_frame.pack(fill="x", pady=5, padx=10)

                rarity_color = RARITY_COLOR.get(item.get("rarity", "Common"), "white")
                name_text = item.get("name", "Unknown")
                if is_relevant:
                    name_text = "⭐ " + name_text
                customtkinter.CTkLabel(item_frame,
                                       text=f"{name_text}  —  {price_str}",
                                       font=customtkinter.CTkFont(size=13, weight="bold"),
                                       text_color=rarity_color, anchor="w"
                                       ).pack(anchor="w", padx=10, pady=(8, 2))

                if item.get("description"):
                    desc = item["description"]
                    if len(desc) > 100:
                        desc = desc[:100] + "..."
                    customtkinter.CTkLabel(item_frame, text=desc,
                                           font=customtkinter.CTkFont(size=10), text_color="gray",
                                           wraplength=500, justify="left", anchor="w"
                                           ).pack(anchor="w", padx=10, pady=(0, 4))

                info_parts = []
                cal = item.get("caliber")
                if cal:
                    if isinstance(cal, list):
                        cal = ", ".join(str(c) for c in cal)
                    info_parts.append(f"Caliber: {cal}")
                if item.get("rarity"):
                    info_parts.append(f"Rarity: {item['rarity']}")
                if item.get("weight"):
                    info_parts.append(f"Weight: {self._format_weight(item['weight'])}")
                if item.get("pen"):
                    info_parts.append(f"Pen: {item['pen']}")
                labels = item.get("ammo_labels", [])
                if labels:
                    info_parts.append(" / ".join(str(x) for x in labels if x))
                if item.get("_guaranteed"):
                    info_parts.append("Guaranteed")
                if item.get("_prefilled"):
                    cap = item.get("capacity", 0)
                    info_parts.append(f"Pre-filled ({cap} rds)")
                avail_qty = int(item.get("_shop_available_qty", 1) or 1)
                info_parts.append(f"Available: {avail_qty}")

                if info_parts:
                    customtkinter.CTkLabel(item_frame,
                                           text=" | ".join(info_parts),
                                           font=customtkinter.CTkFont(size=10),
                                           text_color="orange", anchor="w"
                                           ).pack(anchor="w", padx=10, pady=(0, 4))

                btn_row_item = customtkinter.CTkFrame(item_frame, fg_color="transparent")
                btn_row_item.pack(anchor="w", padx=10, pady=(0, 8))

                qty_var = customtkinter.StringVar(value="1")
                customtkinter.CTkLabel(btn_row_item, text="Qty:",
                                       font=customtkinter.CTkFont(size=11)).pack(side="left", padx=(0, 4))
                customtkinter.CTkEntry(btn_row_item, textvariable=qty_var, width=52).pack(side="left", padx=(0, 6))

                def _do_add(it=item, up=unit_price, qv=qty_var):
                    try:
                        qty = max(1, int((qv.get() or "1").strip()))
                    except Exception:
                        qty = 1
                    _add_to_cart(it, up, qty)

                self._create_sound_button(
                    btn_row_item, f"Add to Cart ({format_price(unit_price)}/ea)",
                    _do_add,
                    width=180, height=30, font=customtkinter.CTkFont(size=12)
                ).pack(side="left")

        # Build category buttons
        sorted_cats = list(categories.keys())
        for cat_name in sorted_cats:
            count = len(categories[cat_name])
            btn_text = cat_name if cat_name == "Order Caliber" else f"{cat_name} ({count})"
            self._create_sound_button(
                cat_nav, btn_text,
                lambda c=cat_name: _render_category(c),
                width=175, height=38, font=customtkinter.CTkFont(size=12)
            ).pack(pady=4, padx=6)

        # Show first category by default
        _render_category(sorted_cats[0])

        # ── Bottom buttons ───────────────────────────────────────────────────
        btn_row = customtkinter.CTkFrame(main_frame, fg_color="transparent")
        btn_row.grid(row=2, column=0, sticky="ew", padx=20, pady=10)

        def _complete_purchase():
            if not buy_cart:
                self._popup_show_info("Empty Cart", "Your cart is empty.", sound="popup")
                return
            try:
                hands_items = save_data.get("hands", {}).get("items", [])
                for entry in buy_cart:
                    qty = max(1, int(entry.get("quantity", 1)))
                    unit_price = float(entry.get("price", 0.0))
                    item_copy = entry["item"].copy()
                    item_copy.pop("_table_category", None)
                    item_copy.pop("_guaranteed", None)
                    item_copy.pop("_prefilled", None)
                    item_copy["quantity"] = qty
                    item_copy["_purchase_price"] = unit_price
                    item_copy = add_subslots_to_item(item_copy)
                    _repair_item_parts_durability_recursive(item_copy, 100.0)
                    self._add_item_to_container(hands_items, item_copy)
                _repair_item_parts_durability_recursive(save_data, 100.0)
                save_data["hands"]["items"] = hands_items
                if not free_ammo:
                    save_data["money"] = player_money[0] - buy_total[0]
                    player_money[0] = save_data["money"]
                self._write_save_to_path(save_path, save_data)
                cost_str = "Free" if free_ammo else format_price(buy_total[0])
                total_units = _buy_cart_units()
                self._popup_show_info("Purchase Complete",
                                      f"Received {total_units} item(s).  Cost: {cost_str}.",
                                      sound="success")
                buy_cart.clear()
                buy_total[0] = 0.0
                update_money_label()
                stop_ui_music()
                self._open_business_tool()
            except Exception:
                logging.exception("Failed to complete ammo supplier purchase")
                self._popup_show_info("Error", "Failed to complete purchase.", sound="error")

        def _leave():
            if buy_cart:
                def _do_leave(confirmed=True):
                    if not confirmed:
                        return
                    stop_ui_music()
                    self._open_business_tool()
                n = _buy_cart_units()
                self._popup_confirm("Leave", f"You have {n} item(s) in cart. Leave anyway?", _do_leave)
                return
            stop_ui_music()
            self._open_business_tool()

        self._create_sound_button(btn_row, "Complete Purchase", _complete_purchase,
                                  width=200, height=40, font=customtkinter.CTkFont(size=14)
                                  ).pack(side="left", padx=10)
        self._create_sound_button(btn_row, "View Cart", _open_cart_popup,
                                  width=160, height=40, font=customtkinter.CTkFont(size=14)
                                  ).pack(side="left", padx=10)
        self._create_sound_button(btn_row, "Leave", _leave,
                                  width=140, height=40, font=customtkinter.CTkFont(size=14)
                                  ).pack(side="right", padx=10)
