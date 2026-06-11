"""CharactersMixin — App methods for the "characters" feature area."""
from app.foundation import *


class CharactersMixin:
    def _open_character_management(self):
        logging.info("Character Management definition called")
        create_new_character_button = self._create_sound_button(self.root, "Create New Character", lambda:[self._clear_window(), self._create_new_character()], width = 500, height = 50, font = customtkinter.CTkFont(size = 16))
        create_new_character_button.pack(pady = 20)
        load_existing_character_button = self._create_sound_button(
        self.root,
        "Load Existing Character",
        lambda:[self._clear_window(), self._load_existing_character()],
        width = 500,
        height = 50,
        font = customtkinter.CTkFont(size = 16),
        state = "disabled"if not os.listdir(saves_folder)or all(
        f in["persistent_data.sldsv", "settings.sldsv", "appearance_settings.sldsv", "dm_settings.sldsv"]or f.endswith(".sldsv.sldsv")or f =="backups"
        for f in os.listdir(saves_folder)
        )else "normal"
        )
        load_existing_character_button.pack(pady = 20)

        view_stats_button = self._create_sound_button(
        self.root,
        "View Loaded Character Stats",
        self._view_character_stats,
        width = 500,
        height = 50,
        font = customtkinter.CTkFont(size = 16),
        state = "disabled"if self.currentsave is None else "normal"
        )
        view_stats_button.pack(pady = 20)

        modify_stats_button = self._create_sound_button(
        self.root,
        "Modify Character Stats",
        lambda:[self._clear_window(), self._modify_character_stats()],
        width = 500,
        height = 50,
        font = customtkinter.CTkFont(size = 16),
        state = "disabled"if self.currentsave is None else "normal"
        )
        modify_stats_button.pack(pady = 20)

        return_button = self._create_sound_button(self.root, "Return to Inventory Manager", lambda:[self._clear_window(), self._open_inventory_manager_tool()], width = 500, height = 50, font = customtkinter.CTkFont(size = 16))
        return_button.pack(pady = 20)

    def _view_character_stats(self):
        logging.info("View Character Stats called")

        if self.currentsave is None:
            self._popup_show_info("Error", "No character loaded.", sound = "error")
            return

        save_filename =(self.currentsave or "")+".sldsv"
        save_data = self._load_file(save_filename)

        if save_data is None:
            self._popup_show_info("Error", "Failed to load character data.", sound = "error")
            return

        encumbrance_info = self._calculate_encumbrance_status(save_data)

        self._clear_window()

        self.root.grid_rowconfigure(0, weight = 1)
        self.root.grid_columnconfigure(0, weight = 1)

        main_frame = customtkinter.CTkFrame(self.root)
        main_frame.grid(row = 0, column = 0, sticky = "nsew", padx = 20, pady = 20)
        main_frame.grid_rowconfigure(1, weight = 1)
        main_frame.grid_columnconfigure(0, weight = 1)

        title = customtkinter.CTkLabel(main_frame, text = f"Character: {save_data.get('charactername', 'Unknown')}", font = customtkinter.CTkFont(size = 24, weight = "bold"))
        title.grid(row = 0, column = 0, pady =(0, 20))

        scroll = customtkinter.CTkScrollableFrame(main_frame, width = 800, height = 500)
        scroll.grid(row = 1, column = 0, sticky = "nsew", padx = 10, pady = 10)
        scroll.grid_columnconfigure(0, weight = 1)

        stats_label = customtkinter.CTkLabel(scroll, text = "Base Stats", font = customtkinter.CTkFont(size = 16, weight = "bold"))
        stats_label.pack(pady =(10, 15), anchor = "w", padx = 20)

        stats = save_data.get("stats", {})
        for stat_name, stat_value in stats.items():

            display_value = stat_value
            agility_penalty_text = ""

            if stat_name =="Agility"and encumbrance_info["encumbrance_level"]>0:
                display_value = stat_value -encumbrance_info["encumbrance_level"]
                agility_penalty_text = f"(Base: {stat_value}, Penalty: -{encumbrance_info['encumbrance_level']})"

            stat_frame = customtkinter.CTkFrame(scroll, fg_color = "transparent")
            stat_frame.pack(fill = "x", pady = 5, padx = 30)

            stat_label = customtkinter.CTkLabel(
            stat_frame,
            text = f"{stat_name}: {display_value:+d}{agility_penalty_text}",
            font = customtkinter.CTkFont(size = 12),
            anchor = "w"
            )
            stat_label.pack(fill = "x")

        enc_label = customtkinter.CTkLabel(scroll, text = "Encumbrance Status", font = customtkinter.CTkFont(size = 16, weight = "bold"))
        enc_label.pack(pady =(20, 15), anchor = "w", padx = 20)

        enc_items =[
        ("Total Weight", self._format_weight(encumbrance_info["total_weight"])),
        ("Encumbrance", self._format_weight(encumbrance_info['encumbrance'])),
        ("Encumbrance Threshold", self._format_weight(encumbrance_info['threshold'])),
        ("Encumbrance Level", f"{encumbrance_info['encumbrance_level']}"),
        ("Status", "Encumbered"if encumbrance_info["is_encumbered"]else "Not Encumbered")
        ]

        for label_text, value_text in enc_items:
            enc_frame = customtkinter.CTkFrame(scroll, fg_color = "transparent")
            enc_frame.pack(fill = "x", pady = 3, padx = 30)

            label = customtkinter.CTkLabel(
            enc_frame,
            text = f"{label_text}: {value_text}",
            font = customtkinter.CTkFont(size = 12),
            anchor = "w"
            )
            label.pack(fill = "x")

        tracked = save_data.get('tracked_stats', {})or {}
        try:
            if isinstance(tracked, dict):
                track_label = customtkinter.CTkLabel(scroll, text = "Tracked Activity", font = customtkinter.CTkFont(size = 16, weight = "bold"))
                track_label.pack(pady =(20, 15), anchor = "w", padx = 20)

                ta_items =[
                ("Rounds Fired(total)", tracked.get('rounds_fired_total', 0)),
                ("Magazines Reloaded(total)", tracked.get('mags_reloaded_total', 0)),
                ("Bullets Loaded(total)", tracked.get('bullets_loaded_total', 0)),
                ("D20 Rolls(total)", tracked.get('d20_rolls_total', 0)),
                ("D20 Ones(1)", tracked.get('d20_ones', 0)),
                ("D20 Twenties(20)", tracked.get('d20_twenties', 0))
                ]

                for label_text, value_text in ta_items:
                    tf = customtkinter.CTkFrame(scroll, fg_color = "transparent")
                    tf.pack(fill = "x", pady = 3, padx = 30)
                    lbl = customtkinter.CTkLabel(tf, text = f"{label_text}: {value_text}", font = customtkinter.CTkFont(size = 12), anchor = "w")
                    lbl.pack(fill = "x")

                bh = tracked.get('bullets_loaded_history', [])or[]
                if isinstance(bh, list)and bh:
                    hist_label = customtkinter.CTkLabel(scroll, text = "Recent Bullets Loaded", font = customtkinter.CTkFont(size = 14, weight = "bold"))
                    hist_label.pack(pady =(12, 6), anchor = "w", padx = 20)
                    for rec in bh[-5:]:
                        try:
                            wid = rec.get('weapon_id')
                            cnt = rec.get('count')
                            t = rec.get('time')
                            txt = f"{wid}: {cnt} @ {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(t))if t else 'unknown'}"
                        except Exception:
                            txt = str(rec)
                        rf = customtkinter.CTkFrame(scroll, fg_color = "transparent")
                        rf.pack(fill = "x", pady = 2, padx = 40)
                        rlbl = customtkinter.CTkLabel(rf, text = txt, font = customtkinter.CTkFont(size = 11), anchor = "w")
                        rlbl.pack(fill = "x")
        except Exception:
            logging.exception('Failed rendering tracked_stats in character view')

        try:
            active_effects = self._get_active_temporary_effects(save_data)
            if active_effects:
                fx_label = customtkinter.CTkLabel(scroll, text = "Temporary Effects", font = customtkinter.CTkFont(size = 16, weight = "bold"))
                fx_label.pack(pady =(20, 15), anchor = "w", padx = 20)
                for fx_text in self._get_temporary_effect_display_lines(save_data):
                    fx_frame = customtkinter.CTkFrame(scroll, fg_color = "transparent")
                    fx_frame.pack(fill = "x", pady = 3, padx = 30)
                    fx_lbl = customtkinter.CTkLabel(fx_frame, text = fx_text, font = customtkinter.CTkFont(size = 12), anchor = "w")
                    fx_lbl.pack(fill = "x")
        except Exception:
            logging.exception('Failed rendering temporary effects in character view')

        other_label = customtkinter.CTkLabel(scroll, text = "Other Info", font = customtkinter.CTkFont(size = 16, weight = "bold"))
        other_label.pack(pady =(20, 15), anchor = "w", padx = 20)

        other_items =[
        ("Money", f"{format_price(save_data.get('money', 0))}"),
        ("Equipment Slots", f"{len([s for s in save_data.get('equipment', {}).values()if s is not None])}/{len(save_data.get('equipment', {}))}"),
        ("Storage Items", f"{len(save_data.get('storage', []))}")
        ]

        for label_text, value_text in other_items:
            other_frame = customtkinter.CTkFrame(scroll, fg_color = "transparent")
            other_frame.pack(fill = "x", pady = 3, padx = 30)

            label = customtkinter.CTkLabel(
            other_frame,
            text = f"{label_text}: {value_text}",
            font = customtkinter.CTkFont(size = 12),
            anchor = "w"
            )
            label.pack(fill = "x")

        button_frame = customtkinter.CTkFrame(main_frame, fg_color = "transparent")
        button_frame.grid(row = 2, column = 0, pady = 10)
        button_frame.grid_columnconfigure((0, 1), weight = 1)

        def save_character():
            try:
                self._save_file(save_data)
                self._popup_show_info("Success", "Character saved successfully!", sound = "success")
            except Exception as e:
                logging.error(f"Failed to save character: {e}")
                self._popup_show_info("Error", f"Failed to save: {e}", sound = "error")

        save_button = self._create_sound_button(
        button_frame,
        "Save",
        save_character,
        width = 200,
        height = 40
        )
        save_button.grid(row = 0, column = 0, padx =(0, 10))

        back_button = self._create_sound_button(
        button_frame,
        "Back",
        lambda:[self._clear_window(), self._open_character_management()],
        width = 200,
        height = 40
        )
        back_button.grid(row = 0, column = 1, padx =(10, 0))

    def _modify_character_stats(self):
        logging.info("Modify Character Stats called")

        if self.currentsave is None:
            self._popup_show_info("Error", "No character loaded.", sound = "error")
            return

        save_filename =(self.currentsave or "")+".sldsv"
        save_data = self._load_file(save_filename)

        if save_data is None:
            self._popup_show_info("Error", "Failed to load character data.", sound = "error")
            return

        stat_clamp = 20
        slot_disable_points = 6
        try:
            tbl_path = get_current_table_path()
            if tbl_path and os.path.exists(tbl_path):
                with open(tbl_path, 'r', encoding = 'utf-8-sig')as f:
                    table_data = json.load(f)
                    stat_clamp = table_data.get("additional_settings", {}).get("stat_clamp", 20)
                    slot_disable_points = table_data.get("additional_settings", {}).get("slot_disable_points", 1)
        except Exception:
            pass

        self.root.grid_rowconfigure(0, weight = 1)
        self.root.grid_columnconfigure(0, weight = 1)

        scrollable_frame = customtkinter.CTkScrollableFrame(self.root, width = 650, height = 700)
        scrollable_frame.grid(row = 0, column = 0, sticky = "nsew", padx = 20, pady = 20)
        scrollable_frame.grid_columnconfigure(0, weight = 1)

        title = customtkinter.CTkLabel(scrollable_frame, text = "Modify Character Stats", font = customtkinter.CTkFont(size = 24, weight = "bold"))
        title.grid(row = 0, column = 0, pady =(0, 20))

        stats_frame = customtkinter.CTkFrame(scrollable_frame)
        stats_frame.grid(row = 1, column = 0, sticky = "ew", pady = 10, padx = 10)
        stats_frame.grid_columnconfigure((1, 2, 3), weight = 1)

        stat_names = list(emptysave["stats"].keys())
        stat_sliders = {}
        stat_value_labels = {}
        for i, stat in enumerate(stat_names):
            stat_label = customtkinter.CTkLabel(stats_frame, text = f"{stat}:", font = customtkinter.CTkFont(size = 12), width = 100)
            stat_label.grid(row = i +1, column = 0, sticky = "w", padx =(0, 10), pady = 8)
            value_label = customtkinter.CTkLabel(stats_frame, text = "0", font = customtkinter.CTkFont(size = 12, weight = "bold"), width = 30)
            value_label.grid(row = i +1, column = 1, sticky = "e", padx =(0, 10), pady = 8)
            stat_value_labels[stat]= value_label
            def make_slider_callback(stat_name, value_lbl):
                def on_slider_change(val):
                    value_lbl.configure(text = str(int(float(val))))
                return on_slider_change
            if stat =="Luck":
                stat_min, stat_max = -4, 4
                stat_steps = 8
            else:
                stat_min, stat_max = -20, stat_clamp
                stat_steps = 40 +stat_clamp
            slider = customtkinter.CTkSlider(
            stats_frame,
            from_ = stat_min,
            to = stat_max,
            number_of_steps = stat_steps,
            command = make_slider_callback(stat, value_label)
            )
            slider.set(int(save_data.get('stats', {}).get(stat, 0)))
            slider.grid(row = i +1, column = 2, sticky = "ew", padx = 10, pady = 8)
            stat_sliders[stat]= slider
            range_label = customtkinter.CTkLabel(stats_frame, text = f"[{stat_min}, +{stat_max}]", font = customtkinter.CTkFont(size = 10), text_color = "gray")
            range_label.grid(row = i +1, column = 3, sticky = "w", padx =(10, 0), pady = 8)

        equipment_frame = customtkinter.CTkFrame(scrollable_frame)
        equipment_frame.grid(row = 2, column = 0, sticky = "ew", pady = 10, padx = 10)
        equipment_frame.grid_columnconfigure((0, 1, 2), weight = 1)

        equipment_slots = list(emptysave["equipment"].keys())
        slot_checkboxes = {}
        for i, slot in enumerate(equipment_slots):
            row =(i //3)+1
            col = i %3
            checkbox = customtkinter.CTkCheckBox(
            equipment_frame,
            text = slot.title(),
            font = customtkinter.CTkFont(size = 11)
            )
            if slot in save_data.get('equipment', {}):
                checkbox.select()
            else:
                checkbox.deselect()
            checkbox.grid(row = row, column = col, sticky = "w", padx = 10, pady = 5)
            slot_checkboxes[slot]= checkbox

        sum_frame = customtkinter.CTkFrame(scrollable_frame)
        sum_frame.grid(row = 3, column = 0, sticky = "ew", pady = 15, padx = 10)
        sum_frame.grid_columnconfigure(1, weight = 1)
        sum_label = customtkinter.CTkLabel(sum_frame, text = "Total Points:", font = customtkinter.CTkFont(size = 12, weight = "bold"))
        sum_label.grid(row = 0, column = 0, sticky = "w", padx =(0, 10))
        sum_value_label = customtkinter.CTkLabel(sum_frame, text = "0", font = customtkinter.CTkFont(size = 12, weight = "bold"))
        sum_value_label.grid(row = 0, column = 1, sticky = "w")

        def update_sum(*args):
            stat_total = sum(int(float(stat_sliders[stat].get()))for stat in stat_names)
            disabled_slots = sum(1 for slot, checkbox in slot_checkboxes.items()if not checkbox.get())
            bonus_points = disabled_slots *slot_disable_points *-1
            total = stat_total +bonus_points

            sum_value_label.configure(text = f"{stat_total} + {bonus_points} = {total}")
            if total >0:
                sum_value_label.configure(text_color = "red")
                save_button.configure(state = "disabled")
            else:
                sum_value_label.configure(text_color = "white")
                save_button.configure(state = "normal")

        for stat in stat_names:
            stat_sliders[stat].configure(command = lambda val, s = stat:[
            stat_value_labels[s].configure(text = str(int(float(stat_sliders[s].get())))),
            update_sum()
            ])

        for slot in equipment_slots:
            slot_checkboxes[slot].configure(command = update_sum)

        button_frame = customtkinter.CTkFrame(scrollable_frame, fg_color = "transparent")
        button_frame.grid(row = 4, column = 0, sticky = "ew", pady =(20, 0), padx = 10)
        button_frame.grid_columnconfigure((0, 1), weight = 1)

        def perform_save_modifications():
            try:
                stat_total = sum(int(float(stat_sliders[stat].get()))for stat in stat_names)
                disabled_slots = sum(1 for slot, checkbox in slot_checkboxes.items()if not checkbox.get())
                bonus_points = disabled_slots *slot_disable_points *-1
                total = stat_total +bonus_points

                if total >0:
                    self._popup_show_info('Error', 'Point total must be zero or negative; adjust stats or slots.', sound = 'error')
                    return

                for stat in stat_names:
                    save_data.setdefault('stats', {})[stat]= int(float(stat_sliders[stat].get()))

                for slot, checkbox in slot_checkboxes.items():
                    if not checkbox.get():
                        if slot in save_data.get('equipment', {}):
                            del save_data['equipment'][slot]
                    else:
                        save_data.setdefault('equipment', {}).setdefault(slot, None)

                save_path = os.path.join(saves_folder or 'saves', (self.currentsave or '')+'.sldsv')
                self._write_save_to_path(save_path, save_data)
                self._popup_show_info('Success', 'Stats saved successfully!', sound = 'success')
                self._clear_window()
                self._open_character_management()
            except Exception as e:
                logging.exception('Failed saving modified stats')
                self._popup_show_info('Error', f'Failed to save: {e}', sound = 'error')

        save_button = self._create_sound_button(button_frame, 'Save', perform_save_modifications, width = 200, height = 50, font = customtkinter.CTkFont(size = 14))
        save_button.grid(row = 0, column = 0, padx =(0, 10))
        cancel_button = self._create_sound_button(button_frame, 'Cancel', lambda:self._popup_confirm(
        'Cancel Modifications',
        'Are you sure you want to cancel? Unsaved changes will be lost.',
        lambda:[self._clear_window(), self._open_character_management()]
        ), width = 200, height = 50, font = customtkinter.CTkFont(size = 14))
        cancel_button.grid(row = 0, column = 1, padx =(10, 0))
    def _create_new_character(self):
        import uuid
        import json
        stat_clamp = 20
        slot_disable_points = 6
        table_data = {}
        equipment_editor = False
        starting_budget = 0
        free_points = 0
        try:
            tbl_path = get_current_table_path()
            if tbl_path and os.path.exists(tbl_path):
                with open(tbl_path, 'r', encoding = 'utf-8-sig')as f:
                    table_data = json.load(f)
                    stat_clamp = table_data.get("additional_settings", {}).get("stat_clamp", 20)
                    slot_disable_points = table_data.get("additional_settings", {}).get("slot_disable_points", 1)
                    equipment_editor = bool(table_data.get("additional_settings", {}).get("equipment_editor", False))
                    starting_budget = int(table_data.get("additional_settings", {}).get("starting_budget", 0))
                    free_points = int(table_data.get("additional_settings", {}).get("free_points", 0))
                    logging.info(f"Loaded stat_clamp from table: {stat_clamp}")
                    logging.info(f"Loaded slot_disable_points from table: {slot_disable_points}")
                    logging.info(f"equipment_editor={equipment_editor}, starting_budget={starting_budget}")
                    logging.info(f"Loaded free_points from table: {free_points}")
        except Exception as e:
            logging.warning(f"Failed to load table settings, using default clamp: {e}")
        self.root.grid_rowconfigure(0, weight = 1)
        self.root.grid_columnconfigure(0, weight = 1)

        scrollable_frame = customtkinter.CTkScrollableFrame(self.root, width = 650, height = 700)
        scrollable_frame.grid(row = 0, column = 0, sticky = "nsew", padx = 20, pady = 20)
        scrollable_frame.grid_columnconfigure(0, weight = 1)

        title = customtkinter.CTkLabel(scrollable_frame, text = "Create New Character", font = customtkinter.CTkFont(size = 24, weight = "bold"))
        title.grid(row = 0, column = 0, pady =(0, 20))
        name_label = customtkinter.CTkLabel(scrollable_frame, text = "Character Name:", font = customtkinter.CTkFont(size = 14))
        name_label.grid(row = 1, column = 0, sticky = "w", pady = 5)
        name_entry = customtkinter.CTkEntry(scrollable_frame, placeholder_text = "Enter character name")
        name_entry.grid(row = 2, column = 0, sticky = "ew", pady =(0, 15), padx = 10)
        stats_frame = customtkinter.CTkFrame(scrollable_frame)
        stats_frame.grid(row = 3, column = 0, sticky = "ew", pady = 10, padx = 10)
        stats_frame.grid_columnconfigure((1, 2, 3), weight = 1)
        stats_label = customtkinter.CTkLabel(stats_frame, text = "Initial Stats(Sum must be ≤ 0)", font = customtkinter.CTkFont(size = 14, weight = "bold"))
        stats_label.grid(row = 0, column = 0, columnspan = 4, pady =(0, 15))
        stat_names = list(emptysave["stats"].keys())
        stat_sliders = {}
        stat_value_labels = {}
        stat_range_labels = {}
        for i, stat in enumerate(stat_names):
            stat_label = customtkinter.CTkLabel(stats_frame, text = f"{stat}:", font = customtkinter.CTkFont(size = 12), width = 100)
            stat_label.grid(row = i +1, column = 0, sticky = "w", padx =(0, 10), pady = 8)
            value_label = customtkinter.CTkLabel(stats_frame, text = "0", font = customtkinter.CTkFont(size = 12, weight = "bold"), width = 30)
            value_label.grid(row = i +1, column = 1, sticky = "e", padx =(0, 10), pady = 8)
            stat_value_labels[stat]= value_label
            def make_slider_callback(stat_name, value_lbl):
                def on_slider_change(val):
                    value_lbl.configure(text = str(int(float(val))))
                return on_slider_change
            if stat =="Luck":
                stat_min, stat_max = -4, 4
                stat_steps = 8
            else:
                stat_min, stat_max = -20, stat_clamp
                stat_steps = 40 +stat_clamp
            slider = customtkinter.CTkSlider(
            stats_frame,
            from_ = stat_min,
            to = stat_max,
            number_of_steps = stat_steps,
            command = make_slider_callback(stat, value_label)
            )
            slider.set(0)
            slider.grid(row = i +1, column = 2, sticky = "ew", padx = 10, pady = 8)
            stat_sliders[stat]= slider
            range_label = customtkinter.CTkLabel(stats_frame, text = f"[{stat_min}, +{stat_max}]", font = customtkinter.CTkFont(size = 10), text_color = "gray")
            range_label.grid(row = i +1, column = 3, sticky = "w", padx =(10, 0), pady = 8)
            stat_range_labels[stat]= range_label

        equipment_frame = customtkinter.CTkFrame(scrollable_frame)
        equipment_frame.grid(row = 4, column = 0, sticky = "ew", pady = 10, padx = 10)
        equipment_frame.grid_columnconfigure((0, 1, 2), weight = 1)

        equipment_label = customtkinter.CTkLabel(equipment_frame, text = f"Equipment Slots(Disable for -{slot_disable_points} point{'s'if slot_disable_points !=1 else ''} each)", font = customtkinter.CTkFont(size = 14, weight = "bold"))
        equipment_label.grid(row = 0, column = 0, columnspan = 3, pady =(0, 15))

        equipment_slots = list(emptysave["equipment"].keys())
        slot_checkboxes = {}

        for i, slot in enumerate(equipment_slots):
            row =(i //3)+1
            col = i %3

            checkbox = customtkinter.CTkCheckBox(
            equipment_frame,
            text = slot.title(),
            font = customtkinter.CTkFont(size = 11)
            )
            checkbox.select()
            checkbox.grid(row = row, column = col, sticky = "w", padx = 10, pady = 5)
            slot_checkboxes[slot]= checkbox

        disable_limits_var = customtkinter.BooleanVar(value = False)
        if global_variables.get("devmode", {}).get("value", False):
            def on_disable_limits_toggle():
                unlimited = disable_limits_var.get()
                for stat in stat_names:
                    slider = stat_sliders[stat]
                    if unlimited:
                        if stat =="Luck":
                            new_min, new_max, new_steps = -100, 100, 200
                        else:
                            new_min, new_max, new_steps = -100, 100, 200
                    else:
                        if stat =="Luck":
                            new_min, new_max, new_steps = -4, 4, 8
                        else:
                            new_min, new_max = -20, stat_clamp
                            new_steps = 40 +stat_clamp
                    current_val = int(float(slider.get()))
                    clamped_val = max(new_min, min(new_max, current_val))
                    slider.configure(from_ = new_min, to = new_max, number_of_steps = new_steps)
                    slider.set(clamped_val)
                    stat_value_labels[stat].configure(text = str(clamped_val))
                    stat_range_labels[stat].configure(text = f"[{new_min}, +{new_max}]")
                update_sum()

            limits_checkbox = customtkinter.CTkCheckBox(
            scrollable_frame,
            text = "Disable Limits(Dev)",
            variable = disable_limits_var,
            command = on_disable_limits_toggle,
            font = customtkinter.CTkFont(size = 12)
            )
            limits_checkbox.grid(row = 5, column = 0, sticky = "w", pady = 5, padx = 10)

        sum_frame = customtkinter.CTkFrame(scrollable_frame)
        sum_frame.grid(row = 6, column = 0, sticky = "ew", pady = 15, padx = 10)
        sum_frame.grid_columnconfigure(1, weight = 1)
        sum_label = customtkinter.CTkLabel(sum_frame, text = "Total Points:", font = customtkinter.CTkFont(size = 12, weight = "bold"))
        sum_label.grid(row = 0, column = 0, sticky = "w", padx =(0, 10))
        sum_value_label = customtkinter.CTkLabel(sum_frame, text = "0", font = customtkinter.CTkFont(size = 12, weight = "bold"))
        sum_value_label.grid(row = 0, column = 1, sticky = "w")

        def update_sum(*args):
            stat_total = sum(int(float(stat_sliders[stat].get())) for stat in stat_names)
            disabled_slots = sum(1 for slot, checkbox in slot_checkboxes.items() if not checkbox.get())
            bonus_points = disabled_slots * slot_disable_points * -1
            # Apply free_points logic: user can spend up to free_points for free
            effective_stat_total = stat_total
            if free_points > 0:
                effective_stat_total = max(0, stat_total - free_points)
            total = effective_stat_total + bonus_points

            # Show the calculation in the label
            if free_points > 0:
                sum_value_label.configure(text = f"{stat_total} (−{free_points} free) + {bonus_points} = {total}")
            else:
                sum_value_label.configure(text = f"{stat_total} + {bonus_points} = {total}")

            if disable_limits_var.get():
                sum_value_label.configure(text_color = "white")
                create_button.configure(state = "normal")
            elif total > 0:
                sum_value_label.configure(text_color = "red")
                create_button.configure(state = "disabled")
            else:
                sum_value_label.configure(text_color = "white")
                create_button.configure(state = "normal")

        for stat in stat_names:
            stat_sliders[stat].configure(command = lambda val, s = stat:[
            stat_value_labels[s].configure(text = str(int(float(stat_sliders[s].get())))),
            update_sum()
            ])

        for slot in equipment_slots:
            slot_checkboxes[slot].configure(command = update_sum)

        button_frame = customtkinter.CTkFrame(scrollable_frame, fg_color = "transparent")
        button_frame.grid(row = 7, column = 0, sticky = "ew", pady =(20, 0), padx = 10)
        button_frame.grid_columnconfigure((0, 1), weight = 1)

        def perform_character_creation():
            char_name = name_entry.get().strip()
            stat_total = sum(int(float(stat_sliders[stat].get()))for stat in stat_names)
            disabled_slots = sum(1 for slot, checkbox in slot_checkboxes.items()if not checkbox.get())
            bonus_points = disabled_slots *slot_disable_points *-1
            total = stat_total +bonus_points

            try:
                new_save = emptysave.copy()
                new_save["charactername"]= char_name
                for stat in stat_names:
                    new_save["stats"][stat]= int(float(stat_sliders[stat].get()))

                for slot, checkbox in slot_checkboxes.items():
                    if not checkbox.get():
                        del new_save["equipment"][slot]
                char_uuid = str(uuid.uuid4())
                save_basename = f"{char_name}_{char_uuid}"
                save_filename = os.path.join(saves_folder or "saves", save_basename +".sldsv")

                self._write_save_to_path(save_filename, new_save)
                persistentdata["save_uuids"][char_uuid]= char_name
                persistentdata["last_loaded_save"]= char_uuid

                try:
                    self.currentsave = save_basename
                except Exception:
                    pass
                self._save_persistent_data()
                logging.info(f"Character '{char_name}' created successfully with UUID: {char_uuid}")
                self._popup_show_info("Success", f"Character '{char_name}' created successfully!", sound = "success")
                self._clear_window()
                self._open_character_management()
            except Exception as e:
                logging.error(f"Failed to create character: {e}")
                self._popup_show_info("Error", f"Failed to create character: {e}", sound = "error")

        def create_character():
            char_name = name_entry.get().strip()
            if not char_name:
                self._popup_show_info("Error", "Please enter a character name.", sound = "error")
                return

            stat_total = sum(int(float(stat_sliders[stat].get())) for stat in stat_names)
            logging.debug(f"Stat total before free points: {stat_total}, free points: {free_points}")
            # Apply free_points logic: user can spend up to free_points for free
            effective_stat_total = stat_total
            if free_points > 0:
                effective_stat_total = max(0, stat_total - free_points)
            disabled_slots = sum(1 for slot, checkbox in slot_checkboxes.items() if not checkbox.get())
            bonus_points = disabled_slots * slot_disable_points * -1
            total = effective_stat_total + bonus_points

            def _do_proceed():
                if equipment_editor:
                    char_stats = {s: int(float(stat_sliders[s].get())) for s in stat_names}
                    disabled_slots_list = [sl for sl, cb in slot_checkboxes.items() if not cb.get()]
                    self._clear_window()
                    self._open_char_creation_equipment_page(
                        char_name = char_name,
                        char_stats = char_stats,
                        disabled_slots = disabled_slots_list,
                        table_data = table_data,
                        starting_budget = starting_budget,
                    )
                else:
                    perform_character_creation()

            if disable_limits_var.get():
                _do_proceed()
            elif total < 0:
                self._popup_confirm(
                    "Negative Balance Warning",
                    f"Your point balance is {total}(negative).This means you have unspent points.\n\nAre you sure you want to continue?",
                    lambda _=None: _do_proceed()
                )
            else:
                _do_proceed()

        def go_back():
            self._clear_window()
            self._open_character_management()

        create_button = self._create_sound_button(button_frame, "Next: Choose Equipment" if equipment_editor else "Create Character", create_character, width = 200, height = 50, font = customtkinter.CTkFont(size = 14))
        create_button.grid(row = 0, column = 0, padx =(0, 10))
        back_button = self._create_sound_button(
        button_frame,
        "Cancel",
        lambda:self._popup_confirm(
        "Cancel Character Creation",
        "Are you sure you want to cancel? Unsaved changes will be lost.",
        go_back
        ),
        width = 200,
        height = 50,
        font = customtkinter.CTkFont(size = 14)
        )
        back_button.grid(row = 0, column = 1, padx =(10, 0))
    def _open_char_creation_equipment_page(self, char_name, char_stats, disabled_slots, table_data, starting_budget):
        """Second page of character creation: allocate a budget and equip starting gear."""
        import copy as _copy
        import uuid as _uuid2

        # Build the initial in-memory save (not yet written to disk).
        new_save = _copy.deepcopy(emptysave)
        new_save["charactername"] = char_name
        for stat, val in char_stats.items():
            if stat in new_save["stats"]:
                new_save["stats"][stat] = val
        for slot in disabled_slots:
            new_save["equipment"].pop(slot, None)

        remaining_budget = [int(starting_budget)]

        self.root.grid_rowconfigure(0, weight = 1)
        self.root.grid_columnconfigure(0, weight = 1)

        # ── Root layout ──────────────────────────────────────────────────────
        root_frame = customtkinter.CTkFrame(self.root)
        root_frame.grid(row = 0, column = 0, sticky = "nsew", padx = 8, pady = 8)
        root_frame.grid_rowconfigure(1, weight = 1)
        root_frame.grid_columnconfigure((0, 1), weight = 1)

        # Header
        header_frame = customtkinter.CTkFrame(root_frame, fg_color = "transparent")
        header_frame.grid(row = 0, column = 0, columnspan = 2, sticky = "ew", pady = (0, 6))
        header_frame.grid_columnconfigure(1, weight = 1)

        customtkinter.CTkLabel(
            header_frame,
            text = f"Equipment Setup — {char_name}",
            font = customtkinter.CTkFont(size = 20, weight = "bold"),
        ).grid(row = 0, column = 0, padx = 10, sticky = "w")

        budget_label = customtkinter.CTkLabel(
            header_frame,
            text = f"Budget: {format_price(remaining_budget[0])}",
            font = customtkinter.CTkFont(size = 16, weight = "bold"),
            text_color = "#A8E6CF",
        )
        budget_label.grid(row = 0, column = 1, padx = 10, sticky = "e")

        def refresh_budget_label():
            budget_label.configure(
                text = f"Budget: {format_price(remaining_budget[0])}",
                text_color = "#A8E6CF" if remaining_budget[0] >= 0 else "#FF7070",
            )

        # ── Left panel: copied UI patterns (Item Equip + View Inventory) ────
        left_frame = customtkinter.CTkFrame(root_frame)
        left_frame.grid(row = 1, column = 0, sticky = "nsew", padx = (0, 4))
        left_frame.grid_rowconfigure(0, weight = 1)
        left_frame.grid_columnconfigure(0, weight = 1)

        left_tab = customtkinter.CTkTabview(left_frame)
        left_tab.grid(row = 0, column = 0, sticky = "nsew", padx = 4, pady = 4)
        left_tab.add("Equipment Slots")
        left_tab.add("Inventory")

        slots_tab = left_tab.tab("Equipment Slots")
        slots_tab.grid_rowconfigure(0, weight = 1)
        slots_tab.grid_columnconfigure(0, weight = 1)

        slots_frame = customtkinter.CTkFrame(slots_tab)
        slots_frame.grid(row = 0, column = 0, sticky = "nsew")
        slots_frame.grid_rowconfigure(1, weight = 1)
        slots_frame.grid_columnconfigure(0, weight = 1)

        customtkinter.CTkLabel(
            slots_frame,
            text = "Equipment Slots",
            font = customtkinter.CTkFont(size = 16, weight = "bold"),
        ).grid(row = 0, column = 0, pady = 10)

        slots_scroll = customtkinter.CTkScrollableFrame(slots_frame, height = 600)
        slots_scroll.grid(row = 1, column = 0, sticky = "nsew", padx = 10, pady = (0, 10))

        inv_tab = left_tab.tab("Inventory")
        inv_tab.grid_rowconfigure(0, weight = 1)
        inv_tab.grid_columnconfigure(0, weight = 1)

        inv_frame = customtkinter.CTkFrame(inv_tab)
        inv_frame.grid(row = 0, column = 0, sticky = "nsew")
        inv_frame.grid_rowconfigure(1, weight = 1)
        inv_frame.grid_columnconfigure(0, weight = 1)

        customtkinter.CTkLabel(
            inv_frame,
            text = "Inventory",
            font = customtkinter.CTkFont(size = 16, weight = "bold"),
        ).grid(row = 0, column = 0, pady = 10)

        inv_scroll = customtkinter.CTkScrollableFrame(inv_frame, height = 600)
        inv_scroll.grid(row = 1, column = 0, sticky = "nsew", padx = 10, pady = (0, 10))

        # ── Right panel: Item catalog ─────────────────────────────────────────
        right_frame = customtkinter.CTkFrame(root_frame)
        right_frame.grid(row = 1, column = 1, sticky = "nsew", padx = (4, 0))
        right_frame.grid_rowconfigure(2, weight = 1)
        right_frame.grid_columnconfigure(0, weight = 1)

        customtkinter.CTkLabel(
            right_frame,
            text = "Available Items",
            font = customtkinter.CTkFont(size = 16, weight = "bold"),
        ).grid(row = 0, column = 0, pady = (8, 4))

        search_frame = customtkinter.CTkFrame(right_frame, fg_color = "transparent")
        search_frame.grid(row = 1, column = 0, sticky = "ew", padx = 8, pady = 4)
        search_frame.grid_columnconfigure(0, weight = 1)

        search_entry = customtkinter.CTkEntry(search_frame, placeholder_text = "Search items by ID, name, or category…")
        search_entry.grid(row = 0, column = 0, sticky = "ew")

        catalog_scroll = customtkinter.CTkScrollableFrame(right_frame, height = 460)
        catalog_scroll.grid(row = 2, column = 0, sticky = "nsew", padx = 8, pady = (0, 4))

        pagination_frame = customtkinter.CTkFrame(right_frame, fg_color = "transparent")
        pagination_frame.grid(row = 3, column = 0, pady = 4)

        # ── Bottom buttons ────────────────────────────────────────────────────
        btn_frame = customtkinter.CTkFrame(root_frame, fg_color = "transparent")
        btn_frame.grid(row = 2, column = 0, columnspan = 2, pady = (6, 0))

        # ── Load catalog items ────────────────────────────────────────────────
        all_items = []
        if table_data:
            for tname, titems in table_data.get("tables", {}).items():
                if not isinstance(titems, list):
                    continue
                for item in titems:
                    if not isinstance(item, dict) or item.get("id") is None:
                        continue
                    ic = item.copy()
                    ic["table_category"] = tname
                    all_items.append(ic)
            all_items.sort(key = lambda x: x.get("id", 999999))

        all_ammo_defs = []
        if table_data:
            all_ammo_defs = table_data.get("tables", {}).get("ammunition", []) or []

        def _norm_lower_set(v):
            if isinstance(v, list):
                return {str(x).strip().lower() for x in v if str(x).strip()}
            if isinstance(v, tuple) or isinstance(v, set):
                return {str(x).strip().lower() for x in v if str(x).strip()}
            if isinstance(v, str):
                s = v.strip().lower()
                return {s} if s else set()
            return set()

        def _item_calibers(item_obj):
            vals = set()
            if not isinstance(item_obj, dict):
                return vals
            vals.update(_norm_lower_set(item_obj.get("caliber")))
            vals.update(_norm_lower_set(item_obj.get("musket_caliber")))
            return vals

        def _item_mag_systems(item_obj):
            vals = set()
            if not isinstance(item_obj, dict):
                return vals
            vals.update(_norm_lower_set(item_obj.get("magazinesystem")))
            vals.update(_norm_lower_set(item_obj.get("submagazinesystem")))
            return vals

        def _is_magazine_item(item_obj):
            return bool(isinstance(item_obj, dict) and item_obj.get("magazinesystem") and not item_obj.get("firearm"))

        def _resolve_conflict_slots(conflicts):
            out = []
            try:
                if isinstance(conflicts, dict):
                    slot_field = conflicts.get("slot")
                    if slot_field:
                        if isinstance(slot_field, (list, tuple)):
                            out = [str(c) for c in slot_field]
                        else:
                            out = [str(slot_field)]
                elif isinstance(conflicts, (list, tuple)):
                    out = [str(c) for c in conflicts]
                elif conflicts:
                    out = [str(conflicts)]
            except Exception:
                out = []
            return out

        def _slot_blocked_by_subslots(slot_name):
            try:
                slot_name_l = str(slot_name).lower() if slot_name is not None else ""
                equipment = new_save.get("equipment", {})
                for _, other_item in equipment.items():
                    if not other_item or not isinstance(other_item, dict):
                        continue

                    for subslot_data in other_item.get("subslots", []) or []:
                        try:
                            conflicts = subslot_data.get("conflicts_with")
                            cur = subslot_data.get("current")
                            if not cur:
                                continue
                            for conflict_slot in _resolve_conflict_slots(conflicts):
                                if str(conflict_slot).lower() == slot_name_l:
                                    return True
                        except Exception:
                            pass

                    for acc in other_item.get("accessories", []) or []:
                        try:
                            curacc = acc.get("current")
                            if not isinstance(curacc, dict):
                                continue
                            for subslot_data in curacc.get("subslots", []) or []:
                                try:
                                    conflicts = subslot_data.get("conflicts_with")
                                    cur = subslot_data.get("current")
                                    if not cur:
                                        continue
                                    for conflict_slot in _resolve_conflict_slots(conflicts):
                                        if str(conflict_slot).lower() == slot_name_l:
                                            return True
                                except Exception:
                                    pass
                        except Exception:
                            pass

                    try:
                        item_conflicts = other_item.get("conflicts_with")
                        if item_conflicts:
                            for conflict_slot in _resolve_conflict_slots(item_conflicts):
                                if str(conflict_slot).lower() == slot_name_l:
                                    return True
                    except Exception:
                        pass
                return False
            except Exception:
                return False

        def _get_equip_choices_for_item(item_obj):
            equipment = new_save.get("equipment", {})
            choices = []

            def add_choice(label, slot=None, parent_slot=None, subslot=None):
                choices.append({"label": label, "slot": slot, "parent_slot": parent_slot, "subslot": subslot})

            is_weapon = bool(item_obj.get("firearm") or item_obj.get("melee"))
            if is_weapon:
                weapon_subtype = item_obj.get("subtype", "unknown")
                weapon_melee_type = item_obj.get("type") if item_obj.get("melee") else None

                if weapon_subtype == "pistol" and "waistband" in equipment and equipment["waistband"] is None and not _slot_blocked_by_subslots("waistband"):
                    add_choice("Waistband", slot="waistband")

                def _check_holster_sling(equipped_item, parent_slot, label_prefix=None):
                    if not isinstance(equipped_item, dict) or not equipped_item.get("holster_sling", False):
                        return
                    compatible_types = equipped_item.get("weapon_types", []) or []
                    if weapon_subtype in compatible_types or weapon_melee_type in compatible_types:
                        for subslot_data in equipped_item.get("subslots", []) or []:
                            if subslot_data.get("slot") != "weapon_slot" or subslot_data.get("current") is not None:
                                continue
                            conflicts = subslot_data.get("conflicts_with")
                            blocked = False
                            if conflicts:
                                for conflict_slot in _resolve_conflict_slots(conflicts):
                                    if conflict_slot in equipment and equipment.get(conflict_slot) is not None:
                                        blocked = True
                                        break
                            if blocked:
                                continue
                            lbl = label_prefix or parent_slot.title()
                            label = f"{lbl} - {subslot_data.get('name', 'Weapon Slot')}"
                            add_choice(label, parent_slot=parent_slot, subslot=subslot_data)

                for parent_slot, equipped_item in equipment.items():
                    if isinstance(equipped_item, dict):
                        _check_holster_sling(equipped_item, parent_slot)
                        for ss in equipped_item.get("subslots", []) or []:
                            cur = ss.get("current")
                            if isinstance(cur, dict) and cur.get("holster_sling", False):
                                _check_holster_sling(cur, parent_slot, label_prefix=f"{parent_slot.title()} - {ss.get('name', 'Subslot')}")
            else:
                valid_slots = item_obj.get("slot", [])
                if not isinstance(valid_slots, list):
                    valid_slots = [valid_slots]

                for slot in valid_slots:
                    if slot in equipment and equipment.get(slot) is None and not _slot_blocked_by_subslots(slot):
                        add_choice(slot.title(), slot=slot)

                def _recurse_find_subslots(root_slot, container, label_prefix=None):
                    try:
                        if not container or not isinstance(container, dict):
                            return
                        for subslot_data in container.get("subslots", []) or []:
                            try:
                                subslot_type = subslot_data.get("slot", "")
                                lbl_suffix = subslot_data.get("name", subslot_type)
                                label = f"{root_slot.title()} - {lbl_suffix}" if not label_prefix else f"{label_prefix} -> {lbl_suffix}"
                                if subslot_type in valid_slots and subslot_data.get("current") is None:
                                    add_choice(label, parent_slot=root_slot, subslot=subslot_data)
                                cur = subslot_data.get("current")
                                if isinstance(cur, dict):
                                    _recurse_find_subslots(root_slot, cur, label_prefix=label)
                            except Exception:
                                pass
                    except Exception:
                        pass

                for parent_slot, equipped_item in equipment.items():
                    if isinstance(equipped_item, dict):
                        _recurse_find_subslots(parent_slot, equipped_item)

            # De-duplicate by label for cleaner UI
            seen = set()
            out = []
            for c in choices:
                key = c.get("label")
                if key in seen:
                    continue
                seen.add(key)
                out.append(c)
            return out

        def _select_equip_choice_popup(choices, on_apply):
            if not choices:
                return
            if len(choices) == 1:
                on_apply(choices[0])
                return

            popup = customtkinter.CTkToplevel(self.root)
            popup.title("Select Slot")
            popup.transient(self.root)
            self._center_popup_on_window(popup, 360, 200)

            customtkinter.CTkLabel(
                popup,
                text = "Choose where to equip:",
                font = customtkinter.CTkFont(size = 14, weight = "bold")
            ).pack(pady = (15, 10))

            labels = [c["label"] for c in choices]
            selection = customtkinter.StringVar(value = labels[0])
            customtkinter.CTkOptionMenu(popup, values = labels, variable = selection).pack(pady = 10, padx = 20, fill = "x")

            btn_frame = customtkinter.CTkFrame(popup, fg_color = "transparent")
            btn_frame.pack(pady = 15)

            def _confirm():
                label = selection.get()
                chosen = next((c for c in choices if c.get("label") == label), None)
                if chosen:
                    on_apply(chosen)
                popup.destroy()

            self._create_sound_button(btn_frame, "Equip", _confirm, width = 120, height = 35).pack(side = "left", padx = 10)
            self._create_sound_button(btn_frame, "Cancel", popup.destroy, width = 120, height = 35).pack(side = "left", padx = 10)

            popup.grab_set()
            popup.lift()
            try:
                self._safe_focus(popup)
            except Exception:
                pass

        def _ammo_unit_price(ammo_def):
            base = _cc_item_price(ammo_def)
            qty = ammo_def.get("quantity", 1)
            try:
                qty = int(qty)
            except (TypeError, ValueError):
                qty = 1
            if qty <= 0:
                qty = 1
            return round(float(base) / float(qty), 2)

        def _compatible_ammo_defs_for_mag(mag_item):
            mag_cals = _item_calibers(mag_item)
            if not all_ammo_defs:
                return []
            if not mag_cals:
                return [a for a in all_ammo_defs if isinstance(a, dict)]
            out = []
            for ammo_def in all_ammo_defs:
                if not isinstance(ammo_def, dict):
                    continue
                ammo_cals = _item_calibers(ammo_def)
                if ammo_cals and ammo_cals.intersection(mag_cals):
                    out.append(ammo_def)
            return out

        def _build_round_data(ammo_def, preferred_caliber=None):
            ammo_name = ammo_def.get("name") or "Ammo"
            cal_src = ammo_def.get("caliber")
            if isinstance(cal_src, list):
                cal_candidates = [str(c) for c in cal_src if str(c).strip()]
            elif isinstance(cal_src, str) and cal_src.strip():
                cal_candidates = [cal_src.strip()]
            else:
                cal_candidates = []

            caliber = preferred_caliber or (cal_candidates[0] if cal_candidates else None)
            var = None
            variants = ammo_def.get("variants", []) or []
            if variants and isinstance(variants[0], dict):
                var = variants[0]

            rd = {"name": ammo_name, "caliber": caliber}
            if isinstance(var, dict):
                if var.get("name") is not None:
                    rd["variant"] = var.get("name")
                if var.get("type") is not None:
                    rd["type"] = var.get("type")
                if var.get("pen") is not None:
                    rd["pen"] = var.get("pen")
                if var.get("modifiers") is not None:
                    rd["modifiers"] = var.get("modifiers")
                if var.get("tip") is not None:
                    rd["tip"] = var.get("tip")
            return rd

        def _prompt_magazine_fill(item_copy, on_done):
            capacity_raw = item_copy.get("capacity", 0)
            try:
                capacity = max(0, int(capacity_raw))
            except (TypeError, ValueError):
                capacity = 0

            if capacity <= 0:
                item_copy["rounds"] = []
                item_copy["_cc_price"] = _cc_item_price(item_copy)
                on_done(item_copy)
                return

            compatible_ammo = _compatible_ammo_defs_for_mag(item_copy)
            if not compatible_ammo:
                item_copy["rounds"] = []
                item_copy["_cc_price"] = _cc_item_price(item_copy)
                on_done(item_copy)
                return

            base_price_raw = _cc_item_price(item_copy, apply_firearm_modifiers = False)
            base_price = _cc_item_price(item_copy, apply_firearm_modifiers = True)
            mag_cals = _item_calibers(item_copy)

            popup = customtkinter.CTkToplevel(self.root)
            popup.title("Load Magazine")
            popup.transient(self.root)

            customtkinter.CTkLabel(
                popup,
                text = f"Load \"{item_copy.get('name', 'Magazine')}\"",
                font = customtkinter.CTkFont(size = 13, weight = "bold"),
            ).pack(padx = 12, pady = (12, 8), anchor = "w")

            load_var = customtkinter.BooleanVar(value = True)
            customtkinter.CTkCheckBox(
                popup,
                text = "Load magazine with ammunition",
                variable = load_var,
            ).pack(padx = 12, pady = (0, 8), anchor = "w")

            def _open_mag_loader_editor():
                import tkinter as _tk_shop

                variant_map = {}
                for ammo_def in compatible_ammo:
                    variants = ammo_def.get("variants", []) or []
                    if variants:
                        for var in variants:
                            if not isinstance(var, dict):
                                continue
                            vname = str(var.get("name") or var.get("type") or "FMJ")
                            key = f"{ammo_def.get('name', 'Ammo')} :: {vname}"
                            variant_map[key] = (ammo_def, var)
                    else:
                        key = f"{ammo_def.get('name', 'Ammo')} :: Standard"
                        variant_map[key] = (ammo_def, None)

                if not variant_map:
                    self._popup_show_info("No Compatible Ammo", "No compatible ammunition variants found for this magazine.", sound = "error")
                    return

                editor = customtkinter.CTkToplevel(self.root)
                editor.title("Magazine Loader")
                editor.transient(self.root)

                existing = list(item_copy.get("rounds", []) or [])
                cap = capacity
                vlist = sorted(variant_map.keys())
                color_palette = ["#c4a032", "#b87333", "#a0a0a0", "#d4af37", "#8b4513", "#cd7f32", "#e8c872", "#a08060"]
                vcols = {v: color_palette[i % len(color_palette)] for i, v in enumerate(vlist)}
                _cc_v2c = {}
                for _vn_k, (_ad_k, _vr_k) in variant_map.items():
                    _ac_k = _ad_k.get('caliber')
                    _cc_v2c[_vn_k] = (_ac_k[0] if isinstance(_ac_k, list) and _ac_k else _ac_k) or 'Unknown'
                _cc_cg_raw = {}
                for _vn_k in vlist:
                    _cc_cg_raw.setdefault(_cc_v2c.get(_vn_k, 'Unknown'), []).append(_vn_k)
                cc_caliber_order = sorted(_cc_cg_raw.keys())
                cc_caliber_groups = {k: sorted(v) for k, v in _cc_cg_raw.items()}

                def _tip_for(vname):
                    pair = variant_map.get(vname)
                    if pair and isinstance(pair[1], dict) and isinstance(pair[1].get("tip"), str) and str(pair[1].get("tip")).startswith("#"):
                        return pair[1].get("tip")
                    return "#e0c060"

                def _tip_ol_for(vname):
                    tc = _tip_for(vname)
                    try:
                        rv = int(tc[1:3], 16)
                        gv = int(tc[3:5], 16)
                        bv = int(tc[5:7], 16)
                        return f"#{max(0, rv - 40):02x}{max(0, gv - 40):02x}{max(0, bv - 40):02x}"
                    except Exception:
                        return "#aa8820"

                SLOT_H = 28
                SLOT_W = 260
                ox_mag = 20
                CHIP_W, CHIP_H, CHIP_PAD = 130, 28, 6
                CC_CAL_HEADER_H = 18
                CC_CAL_GROUP_PAD = 8
                cols = max(1, (SLOT_W + 40) // (CHIP_W + CHIP_PAD))
                _cc_sel_h = 22
                for _cc_cg in cc_caliber_order:
                    _cc_cg_rows = max(1, (len(cc_caliber_groups[_cc_cg]) + cols - 1) // cols)
                    _cc_sel_h += CC_CAL_HEADER_H + _cc_cg_rows * (CHIP_H + CHIP_PAD) + CC_CAL_GROUP_PAD
                selector_h = _cc_sel_h + 4
                mag_top = selector_h + 22
                spring_h = 14
                canvas_h = mag_top + cap * SLOT_H + spring_h + 8
                canvas_w = SLOT_W + 40

                main_f = customtkinter.CTkFrame(editor)
                main_f.grid(row = 0, column = 0, sticky = "nsew", padx = 8, pady = 8)

                effective_h = min(canvas_h, 650)
                mag_canvas = _tk_shop.Canvas(main_f, width = canvas_w, height = effective_h, bg = "#1a1a1a", highlightthickness = 1, highlightbackground = "#555555")
                if canvas_h > 650:
                    mc_scroll = _tk_shop.Scrollbar(main_f, orient = "vertical", command = mag_canvas.yview)
                    mc_scroll.pack(side = "right", fill = "y")
                    mag_canvas.configure(yscrollcommand = mc_scroll.set, scrollregion = (0, 0, canvas_w, canvas_h))
                mag_canvas.pack(side = "left", fill = "both", expand = True)

                side = customtkinter.CTkFrame(editor, fg_color = "transparent", width = 220)
                side.grid(row = 0, column = 1, sticky = "ns", padx = 8, pady = 8)

                loader_state = {
                    "dragging": False,
                    "drag_variant": None,
                    "drag_item": None,
                    "drag_tip": None,
                    "drag_text": None,
                    "stoggle": 0,
                    "animating": False,
                }
                chip_hitboxes = {}

                def _make_round(vname):
                    ammo_def, var = variant_map.get(vname, (None, None))
                    if not isinstance(ammo_def, dict):
                        return {"name": vname, "caliber": next(iter(mag_cals), None), "variant": vname}
                    preferred_cal = None
                    ammo_cals = _item_calibers(ammo_def)
                    if mag_cals and ammo_cals:
                        overlap = mag_cals.intersection(ammo_cals)
                        if overlap:
                            preferred_cal = next(iter(overlap))
                    if preferred_cal is None and ammo_cals:
                        preferred_cal = next(iter(ammo_cals))
                    rd = _build_round_data(ammo_def, preferred_caliber = preferred_cal)
                    if isinstance(var, dict):
                        if var.get("name") is not None:
                            rd["variant"] = var.get("name")
                        if var.get("type") is not None:
                            rd["type"] = var.get("type")
                        if var.get("pen") is not None:
                            rd["pen"] = var.get("pen")
                        if var.get("modifiers") is not None:
                            rd["modifiers"] = var.get("modifiers")
                        if var.get("tip") is not None:
                            rd["tip"] = var.get("tip")
                        _apply_ammo_variant_data(rd, ammo_def, var)
                    return rd

                def _play_insert():
                    try:
                        sn = f"bulletinsert{loader_state['stoggle']}"
                        loader_state["stoggle"] = 1 - loader_state["stoggle"]
                        sound_path = os.path.join("sounds", "firearms", "universal", f"{sn}.ogg")
                        if os.path.exists(sound_path):
                            sound = pygame.mixer.Sound(sound_path)
                            ch = pygame.mixer.find_channel()
                            if ch:
                                ch.play(sound)
                    except Exception:
                        pass

                def _unit_cost_for_variant(vname):
                    ammo_def, _var = variant_map.get(vname, (None, None))
                    return _ammo_unit_price(ammo_def) if isinstance(ammo_def, dict) else 0.0

                def _draw_chips():
                    mag_canvas.delete("chips")
                    chip_hitboxes.clear()
                    mag_canvas.create_text(canvas_w // 2, 10, text = "AVAILABLE ROUNDS", fill = "#888888", font = ("Consolas", 9, "bold"), tags = "chips")
                    if not vlist:
                        mag_canvas.create_text(canvas_w // 2, selector_h // 2 + 10, text = "No rounds available", fill = "#555555", font = ("Consolas", 9), tags = "chips")
                        return
                    cur_y = 22
                    for cal in cc_caliber_order:
                        cal_vns = cc_caliber_groups[cal]
                        mag_canvas.create_text(6, cur_y + CC_CAL_HEADER_H // 2, text = cal, fill = "#99aacc", font = ("Consolas", 9, "bold"), anchor = "w", tags = "chips")
                        cur_y += CC_CAL_HEADER_H
                        start_x = (canvas_w - min(len(cal_vns), cols) * (CHIP_W + CHIP_PAD) + CHIP_PAD) // 2
                        for idx, vname in enumerate(cal_vns):
                            row_i = idx // cols
                            col_i = idx % cols
                            x1 = start_x + col_i * (CHIP_W + CHIP_PAD)
                            y1 = cur_y + row_i * (CHIP_H + CHIP_PAD)
                            x2 = x1 + CHIP_W
                            y2 = y1 + CHIP_H
                            chip_hitboxes[vname] = (x1, y1, x2, y2)
                            c = vcols.get(vname, "#c4a032")
                            mag_canvas.create_rectangle(x1, y1, x2, y2, fill = c, outline = "#dddddd", width = 1, tags = "chips")
                            mag_canvas.create_oval(x1 + 3, y1 + 3, x1 + 19, y2 - 3, fill = _tip_for(vname), outline = _tip_ol_for(vname), tags = "chips")
                            disp = vname if len(vname) <= 16 else vname[:15] + "..."
                            mag_canvas.create_text((x1 + x2) // 2 + 8, (y1 + y2) // 2, text = disp, fill = "#1a1a1a", font = ("Consolas", 8, "bold"), tags = "chips")
                        cc_rows = max(1, (len(cal_vns) + cols - 1) // cols)
                        cur_y += cc_rows * (CHIP_H + CHIP_PAD) + CC_CAL_GROUP_PAD

                def _draw_mag_body():
                    mag_canvas.delete("mag")
                    oy = mag_top
                    mag_canvas.create_text(canvas_w // 2, mag_top - 10, text = "DROP INTO MAGAZINE", fill = "#555555", font = ("Consolas", 9), tags = "mag")
                    mag_canvas.create_rectangle(ox_mag, oy, ox_mag + SLOT_W, oy + cap * SLOT_H, outline = "#888888", width = 2, tags = "mag")
                    for i in range(cap):
                        sy = oy + i * SLOT_H
                        if i > 0:
                            mag_canvas.create_line(ox_mag, sy, ox_mag + SLOT_W, sy, fill = "#444444", dash = (2, 2), tags = "mag")
                        if i < len(existing):
                            r = existing[i]
                            vn = r.get("variant") if isinstance(r, dict) else "Unknown"
                            c = vcols.get(next((v for v in vcols.keys() if vn and vn in v), ""), "#c4a032")
                            mag_canvas.create_rectangle(ox_mag + 2, sy + 2, ox_mag + SLOT_W - 2, sy + SLOT_H - 2, fill = c, outline = "#222222", tags = "mag")
                            mag_canvas.create_oval(ox_mag + 4, sy + 4, ox_mag + 22, sy + SLOT_H - 4, fill = _tip_for(next((v for v in vcols.keys() if vn and vn in v), "")), outline = _tip_ol_for(next((v for v in vcols.keys() if vn and vn in v), "")), tags = "mag")
                            mag_canvas.create_text(ox_mag + SLOT_W // 2 + 10, sy + SLOT_H // 2, text = vn or "Round", fill = "#1a1a1a", font = ("Consolas", 9, "bold"), tags = "mag")
                        else:
                            mag_canvas.create_text(ox_mag + SLOT_W // 2, sy + SLOT_H // 2, text = "[empty]", fill = "#444444", font = ("Consolas", 9), tags = "mag")
                    by = oy + cap * SLOT_H
                    mag_canvas.create_rectangle(ox_mag, by, ox_mag + SLOT_W, by + spring_h, fill = "#555555", outline = "#666666", tags = "mag")

                def _refresh_summary_label():
                    ammo_cost = 0.0
                    for rr in existing:
                        if not isinstance(rr, dict):
                            continue
                        rv = str(rr.get("variant") or "")
                        match_key = next((k for k in variant_map.keys() if rv and rv in k), None)
                        if match_key:
                            ammo_cost += _unit_cost_for_variant(match_key)
                    total = round(base_price + ammo_cost, 2)
                    summary_label.configure(text = f"Capacity: {len(existing)}/{cap}\nMagazine: {format_price(base_price)}\nAmmo: {format_price(ammo_cost)}\nTotal: {format_price(total)}")

                def _draw_all():
                    _draw_chips()
                    _draw_mag_body()
                    _refresh_summary_label()

                def _hit_chip(x, y):
                    for vname, (x1, y1, x2, y2) in chip_hitboxes.items():
                        if x1 <= x <= x2 and y1 <= y <= y2:
                            return vname
                    return None

                def _on_press(event):
                    if loader_state["animating"] or len(existing) >= cap:
                        return
                    vname = _hit_chip(event.x, event.y)
                    if not vname:
                        return
                    loader_state["dragging"] = True
                    loader_state["drag_variant"] = vname
                    c = vcols.get(vname, "#c4a032")
                    loader_state["drag_item"] = mag_canvas.create_rectangle(ox_mag + 2, event.y - SLOT_H // 2, ox_mag + SLOT_W - 2, event.y + SLOT_H // 2, fill = c, outline = "#ffffff", width = 2, tags = "drag")
                    loader_state["drag_tip"] = mag_canvas.create_oval(ox_mag + 4, event.y - SLOT_H // 2 + 2, ox_mag + 22, event.y + SLOT_H // 2 - 2, fill = _tip_for(vname), outline = _tip_ol_for(vname), tags = "drag")
                    loader_state["drag_text"] = mag_canvas.create_text(ox_mag + SLOT_W // 2 + 10, event.y, text = vname, fill = "#1a1a1a", font = ("Consolas", 10, "bold"), tags = "drag")

                def _on_move(event):
                    if not loader_state["dragging"]:
                        return
                    y = event.y
                    if loader_state["drag_item"] and loader_state["drag_tip"] and loader_state["drag_text"]:
                        mag_canvas.coords(loader_state["drag_item"], ox_mag + 2, y - SLOT_H // 2, ox_mag + SLOT_W - 2, y + SLOT_H // 2)
                        mag_canvas.coords(loader_state["drag_tip"], ox_mag + 4, y - SLOT_H // 2 + 2, ox_mag + 22, y + SLOT_H // 2 - 2)
                        mag_canvas.coords(loader_state["drag_text"], ox_mag + SLOT_W // 2 + 10, y)

                def _on_release(event):
                    if not loader_state["dragging"]:
                        return
                    loader_state["dragging"] = False
                    mag_canvas.delete("drag")
                    vname = loader_state.get("drag_variant")
                    loader_state["drag_variant"] = None
                    if not vname or len(existing) >= cap:
                        return
                    if event.y >= mag_top - 15:
                        existing.insert(0, _make_round(vname))
                        _play_insert()
                        _draw_all()

                mag_canvas.bind("<Button-1>", _on_press)
                mag_canvas.bind("<B1-Motion>", _on_move)
                mag_canvas.bind("<ButtonRelease-1>", _on_release)

                summary_label = customtkinter.CTkLabel(side, text = "", font = customtkinter.CTkFont(size = 12), justify = "left", anchor = "w")
                summary_label.pack(fill = "x", pady = (10, 8))

                def _auto_fill_variant(vname):
                    if loader_state["animating"]:
                        return
                    loader_state["animating"] = True
                    def _step():
                        if len(existing) >= cap:
                            loader_state["animating"] = False
                            _draw_all()
                            return
                        existing.insert(0, _make_round(vname))
                        _play_insert()
                        _draw_all()
                        editor.after(100, _step)
                    _step()

                def _use_reloader():
                    if not vlist:
                        return
                    if len(vlist) == 1:
                        _auto_fill_variant(vlist[0])
                        return
                    _cc_avail_cg = {}
                    for vn in vlist:
                        cal = _cc_v2c.get(vn, 'Unknown')
                        _cc_avail_cg.setdefault(cal, []).append(vn)
                    _cc_calibers = sorted(_cc_avail_cg.keys())
                    def _cc_open_variant_picker(cal_vns):
                        sel_popup = customtkinter.CTkToplevel(editor)
                        sel_popup.title("Select Round Type")
                        sel_popup.transient(editor)
                        sel_popup.grab_set()
                        customtkinter.CTkLabel(sel_popup, text = "Select variant for reloader:", font = customtkinter.CTkFont(size = 12)).pack(pady = 8)
                        sel_var = customtkinter.StringVar(value = cal_vns[0])
                        sf = customtkinter.CTkScrollableFrame(sel_popup, height = min(240, len(cal_vns) * 36 + 10), width = 280)
                        sf.pack(fill = "x", padx = 8, pady = 4)
                        for vn in cal_vns:
                            customtkinter.CTkRadioButton(sf, text = vn, variable = sel_var, value = vn).pack(anchor = "w", padx = 8, pady = 2)
                        def _go_cc():
                            v = sel_var.get()
                            sel_popup.destroy()
                            _auto_fill_variant(v)
                        customtkinter.CTkButton(sel_popup, text = "Hook Up & Load", command = _go_cc, width = 170).pack(pady = 8)
                        customtkinter.CTkButton(sel_popup, text = "Cancel", command = sel_popup.destroy, width = 120, fg_color = "#444444").pack(pady = 4)
                        sel_popup.update_idletasks()
                        _sw2 = sel_popup.winfo_screenwidth(); _sh2 = sel_popup.winfo_screenheight()
                        _pw = sel_popup.winfo_reqwidth(); _ph = sel_popup.winfo_reqheight()
                        sel_popup.geometry(f"+{_sw2 // 2 - _pw // 2}+{max(0, _sh2 // 2 - _ph // 2)}")
                        sel_popup.lift()
                        self._safe_focus(sel_popup)
                    if len(_cc_calibers) == 1:
                        _cc_open_variant_picker(vlist)
                        return
                    cal_popup = customtkinter.CTkToplevel(editor)
                    cal_popup.title("Select Caliber")
                    cal_popup.transient(editor)
                    cal_popup.grab_set()
                    customtkinter.CTkLabel(cal_popup, text = "Select caliber to load:", font = customtkinter.CTkFont(size = 12)).pack(pady = 8)
                    for cal in _cc_calibers:
                        cal_vns = list(_cc_avail_cg[cal])
                        def _pick_cc(cv = cal_vns):
                            cal_popup.destroy()
                            _cc_open_variant_picker(cv)
                        customtkinter.CTkButton(cal_popup, text = cal, command = _pick_cc, width = 220, height = 32).pack(padx = 16, pady = 4)
                    customtkinter.CTkButton(cal_popup, text = "Cancel", command = cal_popup.destroy, width = 120, fg_color = "#444444").pack(pady = 8)
                    cal_popup.update_idletasks()
                    _sw3 = cal_popup.winfo_screenwidth(); _sh3 = cal_popup.winfo_screenheight()
                    _cw = cal_popup.winfo_reqwidth(); _ch2 = cal_popup.winfo_reqheight()
                    cal_popup.geometry(f"+{_sw3 // 2 - _cw // 2}+{max(0, _sh3 // 2 - _ch2 // 2)}")
                    cal_popup.lift()
                    self._safe_focus(cal_popup)

                customtkinter.CTkButton(side, text = "Use Reloader", command = _use_reloader, width = 170, height = 32, fg_color = "#2a6a2a", hover_color = "#3a7a3a").pack(pady = 4)

                def _apply():
                    item_copy["rounds"] = existing[:cap]
                    ammo_cost = 0.0
                    for rr in item_copy.get("rounds", []):
                        if not isinstance(rr, dict):
                            continue
                        rv = str(rr.get("variant") or "")
                        match_key = next((k for k in variant_map.keys() if rv and rv in k), None)
                        if match_key:
                            ammo_cost += _unit_cost_for_variant(match_key)
                    item_copy["_cc_price"] = round(base_price + ammo_cost, 2)
                    editor.destroy()
                    popup.destroy()
                    on_done(item_copy)

                customtkinter.CTkButton(side, text = "Apply", command = _apply, width = 170, height = 36).pack(pady = (10, 4))
                customtkinter.CTkButton(side, text = "Cancel", command = editor.destroy, width = 170, height = 30, fg_color = "#444444").pack(pady = 4)

                _draw_all()
                editor.update_idletasks()
                ew = max(editor.winfo_reqwidth(), 640)
                eh = max(editor.winfo_reqheight(), 520)
                sw = editor.winfo_screenwidth()
                sh = editor.winfo_screenheight()
                editor.geometry(f"{ew}x{eh}+{sw // 2 - ew // 2}+{sh // 2 - eh // 2}")
                editor.grab_set()
                editor.lift()
                self._safe_focus(editor)

            btn_frame = customtkinter.CTkFrame(popup, fg_color = "transparent")
            btn_frame.pack(fill = "x", padx = 10, pady = 10)

            def _add_empty():
                item_copy["rounds"] = []
                item_copy["_cc_price"] = base_price
                popup.destroy()
                on_done(item_copy)

            customtkinter.CTkButton(btn_frame, text = "Open Editor", command = _open_mag_loader_editor, width = 140).pack(side = "left", padx = 6)
            customtkinter.CTkButton(btn_frame, text = "Add Empty", command = _add_empty, width = 140).pack(side = "left", padx = 6)
            customtkinter.CTkButton(btn_frame, text = "Cancel", command = popup.destroy, width = 120, fg_color = "#444444").pack(side = "left", padx = 6)

            self._center_popup_on_window(popup, 520, 220)
            popup.deiconify()
            popup.lift()
            try:
                popup.grab_set()
            except Exception:
                pass

        def _is_attachment_catalog_item(item_obj):
            if not isinstance(item_obj, dict):
                return False
            table_cat = str(item_obj.get("table_category") or item_obj.get("_table_category") or "").lower()
            return bool(item_obj.get("attachment") or item_obj.get("accessory") or table_cat in ("attachments", "accessories"))

        def _attachment_slots_for_item(item_obj):
            slot_field = item_obj.get("slot") or item_obj.get("attach_to") or item_obj.get("accessory_slot") or item_obj.get("parent_accessory_slot") or []
            if isinstance(slot_field, str):
                return [slot_field.strip().lower()] if slot_field.strip() else []
            if isinstance(slot_field, (list, tuple, set)):
                return [str(s).strip().lower() for s in slot_field if str(s).strip()]
            return []

        def _attachment_candidates_for_slot(slot_name):
            sn = str(slot_name or "").strip().lower()
            out = []
            seen = set()
            for cand in all_items:
                if not _is_attachment_catalog_item(cand):
                    continue
                if sn not in _attachment_slots_for_item(cand):
                    continue
                key = (cand.get("id"), cand.get("name"))
                if key in seen:
                    continue
                seen.add(key)
                out.append(cand)
            out.sort(key = lambda c: (_cc_item_price(c), str(c.get("name") or "")))
            return out

        def _sum_installed_attachment_costs(weapon_obj):
            total = 0.0
            seen = set()
            stack = [weapon_obj]
            while stack:
                obj = stack.pop()
                if not isinstance(obj, dict):
                    continue
                oid = id(obj)
                if oid in seen:
                    continue
                seen.add(oid)
                for acc in obj.get("accessories", []) or []:
                    if not isinstance(acc, dict):
                        continue
                    cur = acc.get("current")
                    if isinstance(cur, dict):
                        if _is_attachment_catalog_item(cur):
                            total += float(cur.get("_cc_price", _cc_item_price(cur)) or 0)
                        stack.append(cur)
                for sub in obj.get("subslots", []) or []:
                    if not isinstance(sub, dict):
                        continue
                    cur = sub.get("current")
                    if isinstance(cur, dict):
                        stack.append(cur)
            return round(total, 2)

        def _prompt_firearm_attachments(item_copy, base_firearm_price, on_done):
            accessories = [a for a in (item_copy.get("accessories", []) or []) if isinstance(a, dict) and a.get("slot")]
            if not accessories:
                item_copy["_cc_price"] = round(float(base_firearm_price or 0), 2)
                on_done(item_copy)
                return

            popup = customtkinter.CTkToplevel(self.root)
            popup.title("Modify Attachments")
            popup.transient(self.root)
            popup.geometry("720x520")

            customtkinter.CTkLabel(
                popup,
                text = f"Configure attachments for {item_copy.get('name', 'firearm')}",
                font = customtkinter.CTkFont(size = 14, weight = "bold"),
            ).pack(anchor = "w", padx = 12, pady = (12, 6))

            summary_label = customtkinter.CTkLabel(popup, text = "", font = customtkinter.CTkFont(size = 11), justify = "left", anchor = "w")
            summary_label.pack(fill = "x", padx = 12, pady = (0, 6))

            scroll = customtkinter.CTkScrollableFrame(popup)
            scroll.pack(fill = "both", expand = True, padx = 12, pady = (0, 8))

            def _clear_generated_subslots(parent_slot):
                item_copy["accessories"] = [
                    a for a in (item_copy.get("accessories", []) or [])
                    if not (isinstance(a, dict) and a.get("_is_attachment_subslot") and a.get("_parent_accessory_slot") == parent_slot)
                ]

            def _refresh_summary():
                att_cost = _sum_installed_attachment_costs(item_copy)
                total = round(float(base_firearm_price or 0) + att_cost, 2)
                summary_label.configure(
                    text = (
                        f"Base firearm: {format_price(base_firearm_price)}\n"
                        f"Attachments: {format_price(att_cost)}\n"
                        f"Total firearm price: {format_price(total)}"
                    )
                )

            def _pick_attachment_for(accessory):
                slot_name = accessory.get("slot")
                candidates = _attachment_candidates_for_slot(slot_name)

                choose = customtkinter.CTkToplevel(popup)
                choose.title(f"Select Attachment - {slot_name}")
                choose.transient(popup)
                choose.geometry("560x480")

                customtkinter.CTkLabel(
                    choose,
                    text = f"Slot: {slot_name}",
                    font = customtkinter.CTkFont(size = 13, weight = "bold"),
                ).pack(anchor = "w", padx = 10, pady = (10, 6))

                inner = customtkinter.CTkScrollableFrame(choose)
                inner.pack(fill = "both", expand = True, padx = 10, pady = (0, 8))

                def _set_none():
                    accessory["current"] = None
                    _clear_generated_subslots(slot_name)
                    choose.destroy()
                    _render_rows()

                self._create_sound_button(inner, "(None)", _set_none, width = 110, height = 30).pack(anchor = "w", padx = 6, pady = 6)

                for cand in candidates:
                    row = customtkinter.CTkFrame(inner)
                    row.pack(fill = "x", padx = 6, pady = 4)

                    cprice = _cc_item_price(cand)
                    customtkinter.CTkLabel(
                        row,
                        text = f"{cand.get('name', 'Unknown')} ({format_price(cprice)})",
                        font = customtkinter.CTkFont(size = 12, weight = "bold"),
                        anchor = "w",
                    ).pack(side = "left", padx = 8, pady = 6)

                    def _apply_attachment(src = cand):
                        att = add_subslots_to_item({k: v for k, v in src.items() if k != "table_category"})
                        _set_full_part_durability(att)
                        att["_cc_price"] = _cc_item_price(att)
                        accessory["current"] = att
                        _clear_generated_subslots(slot_name)
                        _add_attachment_subslots_to_weapon(item_copy, accessory, att)
                        choose.destroy()
                        _render_rows()

                    self._create_sound_button(row, "Select", _apply_attachment, width = 90, height = 30).pack(side = "right", padx = 8, pady = 6)

                self._create_sound_button(choose, "Close", choose.destroy, width = 120, height = 32).pack(pady = (0, 10))

            def _render_rows():
                for w in scroll.winfo_children():
                    w.destroy()
                for acc in [a for a in (item_copy.get("accessories", []) or []) if isinstance(a, dict) and a.get("slot") and not a.get("_is_attachment_subslot")]:
                    slot_name = acc.get("slot")
                    cur = acc.get("current") if isinstance(acc.get("current"), dict) else None
                    row = customtkinter.CTkFrame(scroll)
                    row.pack(fill = "x", padx = 4, pady = 4)
                    row.grid_columnconfigure(0, weight = 1)

                    cur_name = cur.get("name", "(none)") if cur else "(none)"
                    cur_price = format_price(cur.get("_cc_price", _cc_item_price(cur))) if cur else format_price(0)

                    customtkinter.CTkLabel(
                        row,
                        text = f"{slot_name}: {cur_name} [{cur_price}]",
                        font = customtkinter.CTkFont(size = 12),
                        anchor = "w",
                    ).grid(row = 0, column = 0, sticky = "w", padx = 8, pady = 8)

                    self._create_sound_button(
                        row,
                        "Modify",
                        lambda a = acc: _pick_attachment_for(a),
                        width = 100,
                        height = 30,
                    ).grid(row = 0, column = 1, padx = 8, pady = 8)

                _refresh_summary()

            def _confirm():
                item_copy["_cc_price"] = round(float(base_firearm_price or 0) + _sum_installed_attachment_costs(item_copy), 2)
                popup.destroy()
                on_done(item_copy)

            btn_row = customtkinter.CTkFrame(popup, fg_color = "transparent")
            btn_row.pack(pady = (0, 12))
            self._create_sound_button(btn_row, "Confirm", _confirm, width = 130, height = 34).pack(side = "left", padx = 6)
            self._create_sound_button(btn_row, "Skip", lambda: (popup.destroy(), on_done(item_copy)), width = 130, height = 34).pack(side = "left", padx = 6)

            _render_rows()
            self._center_popup_on_window(popup, 720, 520)
            popup.deiconify()
            popup.lift()
            try:
                popup.grab_set()
            except Exception:
                pass

        ITEMS_PER_PAGE = 20
        cat_page = [0]
        cat_filtered = [all_items]
        search_timer = [None]

        def _item_shop_cat(i):
            return str(i.get("shop_category") or "").strip()
        def _item_shop_subcat(i):
            return str(i.get("shop_subcategory") or i.get("subcategory") or "").strip()
        def _item_shop_subcat2(i):
            return str(i.get("shop_subcategory2") or i.get("subcategory2") or "").strip()

        ALL_CAT = "All Categories"
        ALL_SUB = "All Subcategories"
        ALL_SUB2 = "All Subcategory2"
        cat_var = customtkinter.StringVar(value = ALL_CAT)
        sub_var = customtkinter.StringVar(value = ALL_SUB)
        sub2_var = customtkinter.StringVar(value = ALL_SUB2)

        filter_row = customtkinter.CTkFrame(search_frame, fg_color = "transparent")
        filter_row.grid(row = 1, column = 0, sticky = "ew", pady = (6, 0))
        filter_row.grid_columnconfigure((0, 1, 2), weight = 1)

        all_categories = sorted({c for c in (_item_shop_cat(i) for i in all_items) if c})
        cat_menu = customtkinter.CTkOptionMenu(filter_row, variable = cat_var, values = [ALL_CAT] + all_categories)
        cat_menu.grid(row = 0, column = 0, sticky = "ew", padx = (0, 4))
        sub_menu = customtkinter.CTkOptionMenu(filter_row, variable = sub_var, values = [ALL_SUB])
        sub_menu.grid(row = 0, column = 1, sticky = "ew", padx = 4)
        sub2_menu = customtkinter.CTkOptionMenu(filter_row, variable = sub2_var, values = [ALL_SUB2])
        sub2_menu.grid(row = 0, column = 2, sticky = "ew", padx = (4, 0))

        def _refresh_filter_options():
            sel_cat = cat_var.get()
            sel_sub = sub_var.get()

            sub_vals = set()
            sub2_vals = set()
            for it in all_items:
                c = _item_shop_cat(it)
                s = _item_shop_subcat(it)
                s2 = _item_shop_subcat2(it)
                if sel_cat != ALL_CAT and c != sel_cat:
                    continue
                if s:
                    sub_vals.add(s)
                if (sel_sub == ALL_SUB or s == sel_sub) and s2:
                    sub2_vals.add(s2)

            sub_values = [ALL_SUB] + sorted(sub_vals)
            sub2_values = [ALL_SUB2] + sorted(sub2_vals)

            sub_menu.configure(values = sub_values)
            if sub_var.get() not in sub_values:
                sub_var.set(ALL_SUB)
            sub2_menu.configure(values = sub2_values)
            if sub2_var.get() not in sub2_values:
                sub2_var.set(ALL_SUB2)

        # ── Slot display ──────────────────────────────────────────────────────
        def refresh_slots_display():
            for w in slots_scroll.winfo_children():
                w.destroy()
            equipment = new_save.get("equipment", {})

            def _slot_match_for_choice(choice, target_slot):
                if not isinstance(choice, dict):
                    return False
                return choice.get("slot") == target_slot or choice.get("parent_slot") == target_slot

            def _slot_has_catalog_candidates(target_slot):
                try:
                    for cand in all_items:
                        if not isinstance(cand, dict):
                            continue
                        choices = _get_equip_choices_for_item(cand)
                        if any(_slot_match_for_choice(c, target_slot) for c in choices):
                            return True
                except Exception:
                    pass
                return False

            def _render_subslots(parent_slot, parent_item, parent_frame, indent = 20):
                try:
                    for subslot_data in parent_item.get("subslots", []) or []:
                        subslot_name = subslot_data.get("name", "Unknown Subslot")
                        current_item = subslot_data.get("current")

                        sub_f = customtkinter.CTkFrame(parent_frame)
                        sub_f.pack(fill = "x", pady = 2, padx = 5 + indent)

                        customtkinter.CTkLabel(
                            sub_f,
                            text = f" ↳ {subslot_name}:",
                            font = customtkinter.CTkFont(size = 11),
                            text_color = "#FFA500",
                            anchor = "w",
                        ).pack(side = "top", anchor = "w", padx = 20, pady = (5, 0))

                        if current_item and isinstance(current_item, dict):
                            customtkinter.CTkLabel(
                                sub_f,
                                text = f" {current_item.get('name', 'Unknown')}",
                                font = customtkinter.CTkFont(size = 11),
                                text_color = "lightgreen",
                                anchor = "w",
                            ).pack(side = "top", anchor = "w", padx = 20)

                            btn_box = customtkinter.CTkFrame(sub_f, fg_color = "transparent")
                            btn_box.pack(side = "right", padx = 10, pady = 5)

                            def _make_unequip_sub(ss):
                                def _do():
                                    cur = ss.get("current")
                                    if not isinstance(cur, dict):
                                        return
                                    val = cur.get("_cc_price", _cc_item_price(cur))
                                    remaining_budget[0] += val
                                    ss["current"] = None
                                    new_save.setdefault("hands", {}).setdefault("items", []).append(cur)
                                    refresh_budget_label()
                                    refresh_slots_display()
                                    refresh_inventory_display()
                                return _do

                            self._create_sound_button(
                                btn_box, "Unequip", _make_unequip_sub(subslot_data),
                                width = 80, height = 25, font = customtkinter.CTkFont(size = 10),
                            ).pack(side = "left", padx = 2)

                            if current_item.get("subslots"):
                                _render_subslots(parent_slot, current_item, parent_frame, indent = indent + 16)
                        else:
                            customtkinter.CTkLabel(
                                sub_f,
                                text = " (empty)",
                                text_color = "#666",
                                anchor = "w",
                            ).pack(side = "top", anchor = "w", padx = 20)
                except Exception:
                    pass

            for slot_name, equipped_item in equipment.items():
                slot_f = customtkinter.CTkFrame(slots_scroll)
                slot_f.pack(fill = "x", pady = 5, padx = 5)

                customtkinter.CTkLabel(
                    slot_f,
                    text = f"{slot_name.title()}:",
                    font = customtkinter.CTkFont(size = 12, weight = "bold"),
                    anchor = "w",
                ).pack(side = "top", anchor = "w", padx = 10, pady = (5, 0))

                if equipped_item and isinstance(equipped_item, dict):
                    customtkinter.CTkLabel(
                        slot_f,
                        text = f" {equipped_item.get('name', 'Unknown')}",
                        anchor = "w",
                        text_color = "lightblue",
                    ).pack(side = "top", anchor = "w", padx = 10)

                    btn_box = customtkinter.CTkFrame(slot_f, fg_color = "transparent")
                    btn_box.pack(side = "right", padx = 10, pady = 5)

                    def _make_unequip(sn, it):
                        def _do():
                            val = it.get("_cc_price", _cc_item_price(it))
                            remaining_budget[0] += val
                            new_save["equipment"][sn] = None
                            new_save.setdefault("hands", {}).setdefault("items", []).append(it)
                            refresh_budget_label()
                            refresh_slots_display()
                            refresh_inventory_display()
                        return _do

                    self._create_sound_button(
                        btn_box, "Unequip", _make_unequip(slot_name, equipped_item),
                        width = 80, height = 30, font = customtkinter.CTkFont(size = 10),
                    ).pack(side = "left", padx = 2)

                    self._create_sound_button(
                        btn_box,
                        "Equip",
                        lambda s = slot_name: _open_slot_equip_popup(s),
                        width = 80,
                        height = 30,
                        font = customtkinter.CTkFont(size = 10),
                        state = "normal" if _slot_has_catalog_candidates(slot_name) else "disabled",
                    ).pack(side = "left", padx = 2)

                    if equipped_item.get("subslots"):
                        _render_subslots(slot_name, equipped_item, slots_scroll)
                else:
                    customtkinter.CTkLabel(
                        slot_f,
                        text = " (empty)",
                        text_color = "gray",
                        anchor = "w",
                    ).pack(side = "top", anchor = "w", padx = 10)

                    btn_box = customtkinter.CTkFrame(slot_f, fg_color = "transparent")
                    btn_box.pack(side = "right", padx = 10, pady = 5)

                    self._create_sound_button(
                        btn_box,
                        "Equip",
                        lambda s = slot_name: _open_slot_equip_popup(s),
                        width = 80,
                        height = 30,
                        font = customtkinter.CTkFont(size = 10),
                        state = "normal" if _slot_has_catalog_candidates(slot_name) else "disabled",
                    ).pack(side = "left", padx = 2)

        # ── Inventory display ─────────────────────────────────────────────────
        def refresh_inventory_display():
            for w in inv_scroll.winfo_children():
                w.destroy()

            hands_items = new_save.get("hands", {}).get("items", [])
            storage_items = new_save.get("storage", [])

            def _item_row(parent, idx, it, source_list):
                item_frame = customtkinter.CTkFrame(parent)
                item_frame.pack(fill = "x", pady = 5, padx = 10)
                item_frame.grid_columnconfigure(0, weight = 1)

                item_name = self._format_item_name(it)
                item_qty = it.get("quantity", 1)
                item_weight = (it.get("weight", 0) or 0) * item_qty
                item_price = it.get("_cc_price", _cc_item_price(it))

                display_text = f"{item_name} x{item_qty}"
                if it.get("consumable"):
                    if it.get("uses_left"):
                        display_text += f" ({it.get('uses_left')} uses left)"
                    elif it.get("used_up"):
                        display_text += " (1 use left)"
                    else:
                        display_text += " (inf uses)"

                name_label = customtkinter.CTkLabel(
                    item_frame,
                    text = display_text,
                    font = customtkinter.CTkFont(size = 14, weight = "bold"),
                    anchor = "w",
                )
                name_label.grid(row = 0, column = 0, sticky = "w", padx = 15, pady = (10, 2))

                info_label = customtkinter.CTkLabel(
                    item_frame,
                    text = f"Weight: {self._format_weight(item_weight)} | Cost: {format_price(item_price)}",
                    font = customtkinter.CTkFont(size = 11),
                    text_color = "gray",
                    anchor = "w",
                )
                info_label.grid(row = 1, column = 0, sticky = "w", padx = 15, pady = (0, 10))

                equip_choices = _get_equip_choices_for_item(it)

                def _make_inv_equip(i, lst, choices):
                    def _do():
                        the_item = lst[i]
                        def _apply(choice):
                            existing = None
                            if choice.get("slot"):
                                existing = new_save["equipment"].get(choice["slot"])
                                new_save["equipment"][choice["slot"]] = the_item
                            elif choice.get("subslot") is not None:
                                ss = choice.get("subslot")
                                existing = ss.get("current") if isinstance(ss, dict) else None
                                if isinstance(ss, dict):
                                    ss["current"] = the_item
                            if existing and isinstance(existing, dict):
                                lst.append(existing)
                            if the_item in lst:
                                lst.remove(the_item)
                            refresh_slots_display()
                            refresh_inventory_display()
                        _select_equip_choice_popup(choices, _apply)
                    return _do

                def _make_remove(i, lst):
                    def _do():
                        val = lst[i].get("_cc_price", _cc_item_price(lst[i]))
                        remaining_budget[0] += val
                        lst.pop(i)
                        refresh_budget_label()
                        refresh_inventory_display()
                    return _do

                def _make_fill(i, lst):
                    def _do():
                        old_price = lst[i].get("_cc_price", _cc_item_price(lst[i]))
                        def _on_done(updated_item):
                            lst[i] = updated_item
                            new_price = updated_item.get("_cc_price", _cc_item_price(updated_item))
                            remaining_budget[0] -= (new_price - old_price)
                            refresh_budget_label()
                            refresh_inventory_display()
                        _prompt_magazine_fill(lst[i], _on_done)
                    return _do

                button_col = 1
                if equip_choices:
                    self._create_sound_button(
                        item_frame,
                        "Equip",
                        _make_inv_equip(idx, source_list, equip_choices),
                        width = 100,
                        height = 35,
                        font = customtkinter.CTkFont(size = 12),
                    ).grid(row = 0, column = button_col, rowspan = 2, padx = (0, 8), pady = 10)
                    button_col += 1
                if _is_magazine_item(it):
                    self._create_sound_button(
                        item_frame,
                        "Fill",
                        _make_fill(idx, source_list),
                        width = 90,
                        height = 35,
                        font = customtkinter.CTkFont(size = 12),
                    ).grid(row = 0, column = button_col, rowspan = 2, padx = (0, 8), pady = 10)
                    button_col += 1
                self._create_sound_button(
                    item_frame,
                    "Remove",
                    _make_remove(idx, source_list),
                    width = 110,
                    height = 35,
                    font = customtkinter.CTkFont(size = 12),
                ).grid(row = 0, column = button_col, rowspan = 2, padx = 15, pady = 10)

            customtkinter.CTkLabel(
                inv_scroll,
                text = f"Hands ({len(hands_items)})",
                font = customtkinter.CTkFont(size = 14, weight = "bold"),
            ).pack(anchor = "w", padx = 10, pady = (6, 4))
            if not hands_items:
                customtkinter.CTkLabel(inv_scroll, text = "Container is empty", font = customtkinter.CTkFont(size = 14), text_color = "gray").pack(pady = 12)
            else:
                for i, it in enumerate(hands_items):
                    _item_row(inv_scroll, i, it, hands_items)

            customtkinter.CTkLabel(
                inv_scroll,
                text = f"Storage ({len(storage_items)})",
                font = customtkinter.CTkFont(size = 14, weight = "bold"),
            ).pack(anchor = "w", padx = 10, pady = (10, 4))
            if not storage_items:
                customtkinter.CTkLabel(inv_scroll, text = "Container is empty", font = customtkinter.CTkFont(size = 14), text_color = "gray").pack(pady = 12)
            else:
                for i, it in enumerate(storage_items):
                    _item_row(inv_scroll, i, it, storage_items)

        # ── Firearm condition dialog ───────────────────────────────────────────
        def _prompt_firearm_condition(item_copy, on_done):
            popup = customtkinter.CTkToplevel(self.root)
            popup.title("Firearm Condition")
            popup.geometry("700x500")
            popup.transient(self.root)

            customtkinter.CTkLabel(
                popup,
                text = f"Is \"{item_copy.get('name', 'this firearm')}\" new or used?",
                font = customtkinter.CTkFont(size = 13, weight = "bold"),
                wraplength = 660,
            ).pack(pady = (14, 4), padx = 16)

            btn_row = customtkinter.CTkFrame(popup, fg_color = "transparent")
            btn_row.pack(pady = 4)

            body_frame = customtkinter.CTkFrame(popup, fg_color = "transparent")
            body_frame.pack(fill = "both", expand = True, padx = 12, pady = 4)
            body_frame.grid_columnconfigure(0, weight = 1)
            body_frame.grid_columnconfigure(1, weight = 1)
            body_frame.grid_rowconfigure(0, weight = 1)

            left_f = customtkinter.CTkFrame(body_frame)
            left_f.grid(row = 0, column = 0, sticky = "nsew", padx = (0, 5))

            right_f = customtkinter.CTkFrame(body_frame)
            right_f.grid(row = 0, column = 1, sticky = "nsew", padx = (5, 0))
            right_f.grid_rowconfigure(1, weight = 1)
            right_f.grid_columnconfigure(0, weight = 1)

            base_price_raw = _cc_item_price(item_copy, apply_firearm_modifiers = False)
            base_price = _cc_item_price(item_copy)

            price_label = customtkinter.CTkLabel(
                right_f,
                text = f"Price: {format_price(base_price)}",
                font = customtkinter.CTkFont(size = 13, weight = "bold"),
                text_color = "#A8E6CF",
            )
            price_label.grid(row = 0, column = 0, pady = (10, 4), padx = 10)

            parts_scroll = customtkinter.CTkScrollableFrame(right_f, label_text = "Parts Condition")
            parts_scroll.grid(row = 1, column = 0, sticky = "nsew", padx = 6, pady = (0, 6))

            def _dur_text_local(cur_dur):
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

            def update_preview(rf):
                preview = _copy.deepcopy(item_copy)
                if rf > 0:
                    _set_durability_from_rounds_fired(preview, rf)
                    disp_price = round(_apply_firearm_round_wear_to_value(base_price_raw, preview), 2)
                    price_color = "#FFD700" if disp_price > base_price * 0.5 else "#FF7070"
                else:
                    _set_full_part_durability(preview)
                    disp_price = base_price
                    price_color = "#A8E6CF"

                price_label.configure(
                    text = f"Price: {format_price(disp_price)}",
                    text_color = price_color,
                )

                for w in parts_scroll.winfo_children():
                    w.destroy()

                parts = preview.get("parts") or []
                if not parts:
                    customtkinter.CTkLabel(
                        parts_scroll, text = "(no parts)",
                        font = customtkinter.CTkFont(size = 10), text_color = "#555",
                    ).pack(anchor = "w", padx = 6, pady = 4)
                    return

                for p in parts:
                    if not isinstance(p, dict):
                        continue
                    cur = p.get("current")
                    resolved_name = cur.get("name") if isinstance(cur, dict) else None
                    pname = resolved_name or p.get("name") or (p.get("type") or "").replace("_", " ").title() or "Part"
                    slot_lbl = (p.get("type") or "").replace("_", " ").title() or pname
                    cur_dur = p.get("current_durability")
                    if cur_dur is None and isinstance(cur, dict):
                        cur_dur = cur.get("current_durability")
                    dur_text, dur_col = _dur_text_local(cur_dur)

                    row_f = customtkinter.CTkFrame(parts_scroll)
                    row_f.pack(fill = "x", padx = 3, pady = 1)
                    row_f.grid_columnconfigure(1, weight = 1)
                    customtkinter.CTkLabel(
                        row_f, text = slot_lbl,
                        font = customtkinter.CTkFont(size = 9, weight = "bold"),
                        width = 90, anchor = "w",
                    ).grid(row = 0, column = 0, padx = (4, 2), pady = 2, sticky = "w")
                    customtkinter.CTkLabel(
                        row_f, text = pname,
                        font = customtkinter.CTkFont(size = 9), anchor = "w",
                    ).grid(row = 0, column = 1, padx = 2, pady = 2, sticky = "w")
                    customtkinter.CTkLabel(
                        row_f, text = dur_text,
                        font = customtkinter.CTkFont(size = 9),
                        text_color = dur_col, width = 68, anchor = "e",
                    ).grid(row = 0, column = 2, padx = (2, 4), pady = 2, sticky = "e")

            rounds_entry_var = customtkinter.StringVar(value = "0")
            rounds_slider_var = customtkinter.IntVar(value = 0)
            used_detail_frame = customtkinter.CTkFrame(left_f, fg_color = "transparent")

            def _show_used_controls():
                new_btn.configure(state = "disabled")
                used_btn.configure(state = "disabled")
                used_detail_frame.pack(fill = "x", padx = 12, pady = 4)

                customtkinter.CTkLabel(
                    used_detail_frame,
                    text = "Rounds fired through this firearm:",
                    font = customtkinter.CTkFont(size = 11),
                ).pack(anchor = "w")

                entry_row = customtkinter.CTkFrame(used_detail_frame, fg_color = "transparent")
                entry_row.pack(fill = "x", pady = 4)

                rf_entry = customtkinter.CTkEntry(entry_row, textvariable = rounds_entry_var, width = 90)
                rf_entry.pack(side = "left", padx = (0, 8))

                rf_slider = customtkinter.CTkSlider(
                    entry_row, from_ = 1, to = 150000,
                    variable = rounds_slider_var, width = 180,
                )
                rf_slider.pack(side = "left", expand = True, fill = "x")

                _syncing = [False]
                def _s_to_e(val):
                    if _syncing[0]: return
                    _syncing[0] = True
                    v = int(float(val))
                    rounds_entry_var.set(str(v))
                    update_preview(v)
                    _syncing[0] = False
                def _e_to_s(*_):
                    if _syncing[0]: return
                    _syncing[0] = True
                    try:
                        v = max(1, min(150000, int(rounds_entry_var.get())))
                        rounds_slider_var.set(v)
                        update_preview(v)
                    except Exception:
                        pass
                    _syncing[0] = False

                rf_slider.configure(command = _s_to_e)
                rounds_entry_var.trace_add("write", _e_to_s)

                def _confirm_used():
                    try:
                        rf = max(1, int(rounds_entry_var.get()))
                    except Exception:
                        rf = 1
                    _set_durability_from_rounds_fired(item_copy, rf)
                    _sync_firearm_cleanliness_from_rounds_fired(item_copy)
                    # Update _cc_price so the budget charge reflects the used condition
                    item_copy["_cc_price"] = round(_apply_firearm_round_wear_to_value(base_price_raw, item_copy), 2)
                    popup.destroy()
                    _prompt_firearm_attachments(item_copy, item_copy.get("_cc_price", base_price), on_done)

                self._create_sound_button(
                    used_detail_frame, "Confirm", _confirm_used,
                    width = 140, height = 34,
                ).pack(pady = (10, 0))

            def _on_new():
                _set_full_part_durability(item_copy)
                item_copy["rounds_fired"] = 0
                item_copy["barrel_cleanliness"] = 100.0
                item_copy["_cc_price"] = base_price
                popup.destroy()
                _prompt_firearm_attachments(item_copy, base_price, on_done)

            new_btn = self._create_sound_button(btn_row, "New (Full Condition)", _on_new, width = 170, height = 36)
            new_btn.pack(side = "left", padx = 8)
            used_btn = self._create_sound_button(btn_row, "Used", _show_used_controls, width = 100, height = 36)
            used_btn.pack(side = "left", padx = 8)

            # Show new-condition preview initially
            update_preview(0)

            self._center_popup_on_window(popup, 700, 500)
            popup.deiconify()
            popup.lift()
            try:
                self._safe_focus(popup)
            except Exception:
                pass
            try:
                popup.grab_set()
            except Exception:
                pass

        # ── Add item to character ─────────────────────────────────────────────
        def add_item_to_char(item):
            item_copy = {k: v for k, v in item.items() if k != "table_category"}
            if item.get("table_category") is not None and item_copy.get("_table_category") is None:
                item_copy["_table_category"] = item.get("table_category")
            item_copy = add_subslots_to_item(item_copy)
            item_val = _cc_item_price(item_copy)
            item_copy["_cc_price"] = item_val

            def _finalize(it):
                # Use _cc_price from item in case firearm dialog adjusted it for condition
                charge = it.get("_cc_price", item_val)
                new_save.setdefault("hands", {}).setdefault("items", []).append(it)
                remaining_budget[0] -= charge
                refresh_budget_label()
                refresh_inventory_display()

            if item_copy.get("firearm"):
                _prompt_firearm_condition(item_copy, _finalize)
            elif _is_magazine_item(item_copy):
                _prompt_magazine_fill(item_copy, _finalize)
            else:
                _set_full_part_durability(item_copy)
                _finalize(item_copy)

        # ── Equip item from catalog directly into a slot ──────────────────────
        def equip_from_catalog(item, equip_choices):
            item_copy = {k: v for k, v in item.items() if k != "table_category"}
            if item.get("table_category") is not None and item_copy.get("_table_category") is None:
                item_copy["_table_category"] = item.get("table_category")
            item_copy = add_subslots_to_item(item_copy)
            item_val = _cc_item_price(item_copy)
            item_copy["_cc_price"] = item_val

            def _do_equip(it, choice):
                existing = None
                if choice.get("slot"):
                    existing = new_save["equipment"].get(choice["slot"])
                    new_save["equipment"][choice["slot"]] = it
                elif choice.get("subslot") is not None:
                    ss = choice.get("subslot")
                    if isinstance(ss, dict):
                        existing = ss.get("current")
                        ss["current"] = it
                refund = existing.get("_cc_price", _cc_item_price(existing)) if existing and isinstance(existing, dict) else 0
                if existing and isinstance(existing, dict):
                    new_save.setdefault("hands", {}).setdefault("items", []).append(existing)
                charge = it.get("_cc_price", item_val)
                remaining_budget[0] -= charge
                remaining_budget[0] += refund
                refresh_budget_label()
                refresh_slots_display()
                refresh_inventory_display()

            def _finalize(it):
                _select_equip_choice_popup(equip_choices, lambda ch, it2 = it: _do_equip(it2, ch))

            if item_copy.get("firearm"):
                _prompt_firearm_condition(item_copy, _finalize)
            elif _is_magazine_item(item_copy):
                _prompt_magazine_fill(item_copy, _finalize)
            else:
                _set_full_part_durability(item_copy)
                _finalize(item_copy)

        def _open_slot_equip_popup(target_slot):
            slot_candidates = []
            for cand in all_items:
                if not isinstance(cand, dict):
                    continue
                choices = [
                    c for c in _get_equip_choices_for_item(cand)
                    if isinstance(c, dict) and (c.get("slot") == target_slot or c.get("parent_slot") == target_slot)
                ]
                if choices:
                    slot_candidates.append((cand, choices))

            if not slot_candidates:
                self._popup_show_info("Equip", f"No items in catalog can currently be equipped to {target_slot.title()}.", sound = "popup")
                return

            popup = customtkinter.CTkToplevel(self.root)
            popup.title(f"Equip to {target_slot.title()}")
            popup.transient(self.root)
            popup.geometry("640x520")

            customtkinter.CTkLabel(
                popup,
                text = f"Equip to {target_slot.title()}",
                font = customtkinter.CTkFont(size = 15, weight = "bold"),
            ).pack(anchor = "w", padx = 12, pady = (12, 6))

            search_var = customtkinter.StringVar(value = "")
            search_entry = customtkinter.CTkEntry(
                popup,
                textvariable = search_var,
                placeholder_text = "Search by ID, name, or category...",
            )
            search_entry.pack(fill = "x", padx = 12, pady = (0, 8))

            list_scroll = customtkinter.CTkScrollableFrame(popup)
            list_scroll.pack(fill = "both", expand = True, padx = 12, pady = (0, 10))

            def _render_list():
                for w in list_scroll.winfo_children():
                    w.destroy()
                sl = search_var.get().strip().lower()

                shown = 0
                for cand, choices in slot_candidates:
                    if sl:
                        hay = " ".join([
                            str(cand.get("id", "")),
                            str(cand.get("name", "")),
                            str(cand.get("table_category", "")),
                            str(cand.get("shop_category", "")),
                            str(cand.get("shop_subcategory", "")),
                            str(cand.get("shop_subcategory2", "")),
                        ]).lower()
                        if sl not in hay:
                            continue

                    row = customtkinter.CTkFrame(list_scroll)
                    row.pack(fill = "x", pady = 2, padx = 2)
                    row.grid_columnconfigure(1, weight = 1)

                    customtkinter.CTkLabel(
                        row,
                        text = f"ID:{cand.get('id', '?')}",
                        font = customtkinter.CTkFont(size = 10, weight = "bold"),
                        width = 62,
                    ).grid(row = 0, column = 0, padx = (6, 4), pady = 4, sticky = "w")

                    info = customtkinter.CTkFrame(row, fg_color = "transparent")
                    info.grid(row = 0, column = 1, sticky = "ew", padx = 2)

                    customtkinter.CTkLabel(
                        info,
                        text = cand.get("name", "Unknown"),
                        font = customtkinter.CTkFont(size = 11, weight = "bold"),
                        anchor = "w",
                    ).pack(anchor = "w")

                    customtkinter.CTkLabel(
                        info,
                        text = f"{cand.get('table_category', '')} | {cand.get('shop_category', '-')}",
                        font = customtkinter.CTkFont(size = 9),
                        text_color = "gray",
                        anchor = "w",
                    ).pack(anchor = "w")

                    if _is_new_historical_firearm(cand):
                        customtkinter.CTkLabel(
                            info,
                            text = "Historical Premium x25",
                            font = customtkinter.CTkFont(size = 9, weight = "bold"),
                            text_color = "#FFD700",
                            anchor = "w",
                        ).pack(anchor = "w")

                    customtkinter.CTkLabel(
                        row,
                        text = format_price(_cc_item_price(cand)),
                        font = customtkinter.CTkFont(size = 10, weight = "bold"),
                        width = 82,
                        anchor = "e",
                    ).grid(row = 0, column = 2, padx = (2, 4), pady = 4, sticky = "e")

                    self._create_sound_button(
                        row,
                        "Equip",
                        lambda it = cand, ch = choices: (popup.destroy(), equip_from_catalog(it, ch)),
                        width = 62,
                        height = 26,
                        font = customtkinter.CTkFont(size = 10),
                    ).grid(row = 0, column = 3, padx = (2, 6), pady = 4)

                    shown += 1

                if shown == 0:
                    customtkinter.CTkLabel(
                        list_scroll,
                        text = "No matching items.",
                        font = customtkinter.CTkFont(size = 11),
                        text_color = "gray",
                    ).pack(pady = 10)

            def _on_search(*_):
                _render_list()

            search_entry.bind("<KeyRelease>", _on_search)
            _render_list()

            self._center_popup_on_window(popup, 640, 520)
            popup.deiconify()
            popup.lift()
            try:
                popup.grab_set()
            except Exception:
                pass

        # ── Catalog widget ────────────────────────────────────────────────────
        def create_catalog_widget(item):
            item_price = _cc_item_price(item)
            rarity = item.get("rarity") or ""
            equip_choices = _get_equip_choices_for_item(item)
            can_equip = bool(equip_choices)

            f = customtkinter.CTkFrame(catalog_scroll)
            f.pack(fill = "x", pady = 2, padx = 3)
            f.grid_columnconfigure(1, weight = 1)

            customtkinter.CTkLabel(
                f,
                text = f"ID:{item.get('id', '?')}",
                font = customtkinter.CTkFont(size = 10, weight = "bold"),
                width = 64, fg_color = ("gray75", "gray25"), corner_radius = 4,
            ).grid(row = 0, column = 0, padx = 5, pady = 5, sticky = "w")

            info_f = customtkinter.CTkFrame(f, fg_color = "transparent")
            info_f.grid(row = 0, column = 1, sticky = "ew", padx = 3)

            customtkinter.CTkLabel(
                info_f,
                text = item.get("name", "Unknown"),
                font = customtkinter.CTkFont(size = 11, weight = "bold"),
                anchor = "w",
            ).pack(anchor = "w")

            customtkinter.CTkLabel(
                info_f,
                text = f"{item.get('table_category', '')} | {_item_shop_cat(item) or '-'} | {_item_shop_subcat(item) or '-'} | {_item_shop_subcat2(item) or '-'} | {rarity}",
                font = customtkinter.CTkFont(size = 9),
                text_color = "gray",
                anchor = "w",
            ).pack(anchor = "w")

            if _is_new_historical_firearm(item):
                customtkinter.CTkLabel(
                    info_f,
                    text = "Historical Premium x25",
                    font = customtkinter.CTkFont(size = 9, weight = "bold"),
                    text_color = "#FFD700",
                    anchor = "w",
                ).pack(anchor = "w")

            rarity_color = {"Uncommon": "#A8D8A8", "Rare": "#7EC8E3", "Legendary": "#FFD700", "Mythic": "#FF69B4"}.get(rarity, "#CCCCCC")
            customtkinter.CTkLabel(
                f,
                text = format_price(item_price),
                font = customtkinter.CTkFont(size = 10, weight = "bold"),
                text_color = rarity_color,
                width = 76,
                anchor = "e",
            ).grid(row = 0, column = 2, padx = (2, 4), pady = 4, sticky = "e")

            btn_col = 3
            if can_equip:
                self._create_sound_button(
                    f, "Equip", lambda it = item, ch = equip_choices: equip_from_catalog(it, ch),
                    width = 52, height = 26, font = customtkinter.CTkFont(size = 10),
                ).grid(row = 0, column = btn_col, padx = (2, 2), pady = 4)
                btn_col += 1
            self._create_sound_button(
                f, "Give", lambda it = item: add_item_to_char(it),
                width = 52, height = 26, font = customtkinter.CTkFont(size = 10),
            ).grid(row = 0, column = btn_col, padx = (2, 5), pady = 4)

        def display_catalog_page(page_num):
            items = cat_filtered[0]
            total_pages = max(1, (len(items) + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE)
            page_num = max(0, min(page_num, total_pages - 1))
            cat_page[0] = page_num

            for w in catalog_scroll.winfo_children():
                w.destroy()

            if not items:
                customtkinter.CTkLabel(catalog_scroll, text = "No items found.", font = customtkinter.CTkFont(size = 12), text_color = "gray").pack(pady = 10)
                for w in pagination_frame.winfo_children():
                    w.destroy()
                return

            s = page_num * ITEMS_PER_PAGE
            for i in range(s, min(s + ITEMS_PER_PAGE, len(items))):
                create_catalog_widget(items[i])

            for w in pagination_frame.winfo_children():
                w.destroy()
            if total_pages > 1:
                if page_num > 0:
                    self._create_sound_button(pagination_frame, "<", lambda: display_catalog_page(cat_page[0] - 1), width = 34, height = 24).pack(side = "left", padx = 1)
                for p in range(max(0, page_num - 2), min(total_pages, page_num + 3)):
                    fg = ("gray75", "gray25") if p == page_num else None
                    customtkinter.CTkButton(
                        pagination_frame, text = str(p + 1), width = 30, height = 24,
                        fg_color = fg,
                        command = lambda pp = p: display_catalog_page(pp),
                    ).pack(side = "left", padx = 1)
                if page_num < total_pages - 1:
                    self._create_sound_button(pagination_frame, ">", lambda: display_catalog_page(cat_page[0] + 1), width = 34, height = 24).pack(side = "left", padx = 1)
            try:
                catalog_scroll._parent_canvas.yview_moveto(0)
            except Exception:
                pass

        def filter_catalog(term):
            sl = term.lower().strip()
            sel_cat = cat_var.get()
            sel_sub = sub_var.get()
            sel_sub2 = sub2_var.get()

            def _matches(i):
                c = _item_shop_cat(i)
                s = _item_shop_subcat(i)
                s2 = _item_shop_subcat2(i)

                if sel_cat != ALL_CAT and c != sel_cat:
                    return False
                if sel_sub != ALL_SUB and s != sel_sub:
                    return False
                if sel_sub2 != ALL_SUB2 and s2 != sel_sub2:
                    return False

                if not sl:
                    return True
                return (
                    sl in str(i.get("id", ""))
                    or sl in i.get("name", "").lower()
                    or sl in i.get("table_category", "").lower()
                    or sl in c.lower()
                    or sl in s.lower()
                    or sl in s2.lower()
                )

            cat_filtered[0] = [i for i in all_items if _matches(i)]
            display_catalog_page(0)

        def on_search(*_):
            if search_timer[0]:
                try:
                    self.root.after_cancel(search_timer[0])
                except Exception:
                    pass
            search_timer[0] = self.root.after(250, lambda: filter_catalog(search_entry.get()))

        search_entry.bind("<KeyRelease>", on_search)
        cat_var.trace_add("write", lambda *_: (_refresh_filter_options(), filter_catalog(search_entry.get())))
        sub_var.trace_add("write", lambda *_: (_refresh_filter_options(), filter_catalog(search_entry.get())))
        sub2_var.trace_add("write", lambda *_: filter_catalog(search_entry.get()))
        _refresh_filter_options()

        # ── Finalise character ────────────────────────────────────────────────
        def _iter_current_items():
            eq_vals = list(new_save.get("equipment", {}).values())
            hands = new_save.get("hands", {}).get("items", [])
            storage = new_save.get("storage", [])
            for it in eq_vals + hands + storage:
                if isinstance(it, dict):
                    yield it

        def _has_any_firearm():
            return any(bool(it.get("firearm")) for it in _iter_current_items())

        def _has_loaded_compatible_mag_for_any_firearm():
            firearms = [it for it in _iter_current_items() if it.get("firearm")]
            magazines = [it for it in _iter_current_items() if _is_magazine_item(it)]

            for fw in firearms:
                fw_cals = _item_calibers(fw)
                fw_sys = _item_mag_systems(fw)
                for mag in magazines:
                    rounds = mag.get("rounds", []) or []
                    if not rounds:
                        continue
                    mag_cals = _item_calibers(mag)
                    mag_sys = _item_mag_systems(mag)

                    sys_ok = True
                    if fw_sys and mag_sys:
                        sys_ok = bool(fw_sys.intersection(mag_sys))
                    if not sys_ok:
                        continue

                    round_cals = set()
                    for rd in rounds:
                        if isinstance(rd, dict):
                            round_cals.update(_norm_lower_set(rd.get("caliber")))

                    cal_ok = True
                    if fw_cals:
                        if round_cals:
                            cal_ok = bool(fw_cals.intersection(round_cals))
                        elif mag_cals:
                            cal_ok = bool(fw_cals.intersection(mag_cals))
                    if cal_ok:
                        return True
            return False

        def _confirm_without_magazine(on_continue):
            popup = customtkinter.CTkToplevel(self.root)
            popup.title("Missing Loaded Magazine")
            popup.transient(self.root)

            msg = (
                "You have at least one firearm, but no compatible magazine with ammo loaded.\n\n"
                "Do you want to finalise character creation anyway?"
            )
            customtkinter.CTkLabel(
                popup,
                text = msg,
                wraplength = 420,
                justify = "left",
                font = customtkinter.CTkFont(size = 12),
            ).pack(padx = 16, pady = (14, 12))

            btn_row = customtkinter.CTkFrame(popup, fg_color = "transparent")
            btn_row.pack(pady = (0, 14))

            self._create_sound_button(btn_row, "Go Back", popup.destroy, width = 120, height = 34).pack(side = "left", padx = 6)
            self._create_sound_button(btn_row, "Finalise Anyway", lambda: (popup.destroy(), on_continue()), width = 140, height = 34).pack(side = "left", padx = 6)

            self._center_popup_on_window(popup, 460, 190)
            popup.deiconify()
            popup.lift()
            try:
                popup.grab_set()
            except Exception:
                pass

        def _do_finalize_character():
            try:
                char_uuid = str(_uuid2.uuid4())
                save_basename = f"{char_name}_{char_uuid}"
                save_path = os.path.join(saves_folder or "saves", save_basename + ".sldsv")

                final_save = _copy.deepcopy(new_save)
                surplus = max(0, remaining_budget[0])
                final_save["money"] = surplus

                self._write_save_to_path(save_path, final_save)
                persistentdata["save_uuids"][char_uuid] = char_name
                persistentdata["last_loaded_save"] = char_uuid
                self.currentsave = save_basename
                self._save_persistent_data()
                self._load_file(save_basename + ".sldsv")

                surplus_msg = f"\n\nSurplus budget of {format_price(surplus)} added to character funds." if surplus > 0 else ""
                logging.info("Character '%s' created via equipment editor, budget remaining: %s", char_name, remaining_budget[0])
                self._popup_show_info("Success", f"Character '{char_name}' created!{surplus_msg}", sound = "success")
                self._clear_window()
                self._open_character_management()
            except Exception as exc:
                logging.error("Equipment editor: failed to finalise character: %s", exc)
                self._popup_show_info("Error", f"Failed to create character: {exc}", sound = "error")

        def finalize_character():
            if _has_any_firearm() and not _has_loaded_compatible_mag_for_any_firearm():
                _confirm_without_magazine(_do_finalize_character)
                return
            _do_finalize_character()

        def go_back_to_page1():
            self._clear_window()
            self._create_new_character()

        self._create_sound_button(
            btn_frame, "← Back", go_back_to_page1,
            width = 120, height = 40, font = customtkinter.CTkFont(size = 13),
        ).pack(side = "left", padx = 10)

        self._create_sound_button(
            btn_frame, "Finalise Character →", finalize_character,
            width = 200, height = 40, font = customtkinter.CTkFont(size = 13),
        ).pack(side = "left", padx = 10)

        # Initial render
        refresh_slots_display()
        refresh_inventory_display()
        display_catalog_page(0)

    def _load_existing_character(self):
        import json
        import os

        logging.info("Load Existing Character definition called")

        save_files =[]
        current_table = global_variables.get('current_table')
        incompatible_saves =[]
        try:
            for filename in os.listdir(saves_folder):
                if filename.endswith(".sldsv.sldsv"):
                    continue
                if filename.endswith(".sldsv")and filename not in["persistent_data.sldsv", "settings.sldsv", "appearance_settings.sldsv", "dm_settings.sldsv"]:
                    save_path = os.path.join(saves_folder or "saves", filename)
                    try:
                        save_data = self._read_save_from_path(save_path)
                        if save_data is None:
                            char_name = "Unknown"
                        else:
                            char_name = save_data.get("charactername", "Unknown")
                            save_table = save_data.get('_table')or save_data.get('table')

                            if current_table and save_table:
                                current_table_base = os.path.splitext(current_table)[0]
                                save_table_base = os.path.splitext(save_table)[0]
                                if current_table_base !=save_table_base and current_table !=save_table:
                                    incompatible_saves.append({'filename':filename, 'character_name':char_name, 'save_table':save_table})
                                    continue

                            uuid_part = filename.replace(".sldsv", "").split("_")[-1]
                            save_files.append({
                            "filename":filename,
                            "character_name":char_name,
                            "uuid":uuid_part,
                            "data":save_data,
                            "save_table":save_table
                            })
                    except Exception as e:
                        logging.warning(f"Failed to load save file {filename}: {e}")
        except Exception as e:
            logging.error(f"Failed to read saves folder: {e}")
            self._popup_show_info("Error", f"Failed to read saves folder: {e}", sound = "error")
            return

        if not save_files:
            msg = "No character save files found for the current table."
            if incompatible_saves:
                msg +=f"\n\n{len(incompatible_saves)} save(s) found for other tables."
            self._popup_show_info("No Saves Found", msg, sound = "error")
            return

        self.root.grid_rowconfigure(0, weight = 1)
        self.root.grid_columnconfigure(0, weight = 1)

        main_frame = customtkinter.CTkFrame(self.root)
        main_frame.grid(row = 0, column = 0, sticky = "nsew", padx = 20, pady = 20)
        main_frame.grid_rowconfigure(1, weight = 1)
        main_frame.grid_columnconfigure(0, weight = 1)

        title = customtkinter.CTkLabel(main_frame, text = "Load Existing Character", font = customtkinter.CTkFont(size = 24, weight = "bold"))
        title.grid(row = 0, column = 0, pady =(0, 20))

        scroll_frame = customtkinter.CTkScrollableFrame(main_frame, width = 700, height = 400)
        scroll_frame.grid(row = 1, column = 0, sticky = "nsew", pady =(0, 20))
        scroll_frame.grid_columnconfigure(0, weight = 1)

        def load_character(save_info):
            try:
                self.currentsave = save_info["filename"].replace(".sldsv", "")
                persistentdata["save_uuids"].setdefault(save_info["uuid"], save_info["character_name"])
                persistentdata["last_loaded_save"]= save_info["uuid"]
                self._save_persistent_data()
                logging.info(f"Loaded character '{save_info['character_name']}' with UUID: {save_info['uuid']}")
                self._popup_show_info("Success", f"Character '{save_info['character_name']}' loaded successfully!", sound = "success")
                self._clear_window()
                self._build_main_menu()
            except Exception as e:
                logging.error(f"Failed to load character: {e}")
                self._popup_show_info("Error", f"Failed to load character: {e}", sound = "error")

        for i, save_info in enumerate(save_files):
            char_frame = customtkinter.CTkFrame(scroll_frame)
            char_frame.grid(row = i, column = 0, sticky = "ew", pady = 5, padx = 10)
            char_frame.grid_columnconfigure(0, weight = 1)

            name_label = customtkinter.CTkLabel(
            char_frame,
            text = save_info["character_name"],
            font = customtkinter.CTkFont(size = 18, weight = "bold"),
            anchor = "w"
            )
            name_label.grid(row = 0, column = 0, sticky = "w", padx = 15, pady =(10, 5))

            stats = save_info["data"].get("stats", {})
            stats_text = " | ".join([f"{stat}: {value:+d}"for stat, value in stats.items()])
            stats_label = customtkinter.CTkLabel(
            char_frame,
            text = stats_text,
            font = customtkinter.CTkFont(size = 11),
            text_color = "gray",
            anchor = "w"
            )
            stats_label.grid(row = 1, column = 0, sticky = "w", padx = 15, pady =(0, 5))

            equipment_count = len(save_info["data"].get("equipment", {}))
            equipment_label = customtkinter.CTkLabel(
            char_frame,
            text = f"Equipment Slots: {equipment_count}",
            font = customtkinter.CTkFont(size = 11),
            text_color = "gray",
            anchor = "w"
            )
            equipment_label.grid(row = 2, column = 0, sticky = "w", padx = 15, pady =(0, 5))

            save_table_name = save_info.get("save_table")or "Unknown"
            table_label = customtkinter.CTkLabel(
            char_frame,
            text = f"Data Table: {save_table_name}",
            font = customtkinter.CTkFont(size = 11),
            text_color = "gray",
            anchor = "w"
            )
            table_label.grid(row = 3, column = 0, sticky = "w", padx = 15, pady =(0, 5))

            file_name = save_info["filename"]
            file_name_label = customtkinter.CTkLabel(
            char_frame,
            text = f"Filename: {file_name}",
            font = customtkinter.CTkFont(size = 11),
            text_color = "gray",
            anchor = "w"
            )
            file_name_label.grid(row = 4, column = 0, sticky = "w", padx = 15, pady =(0, 10))

            load_button = self._create_sound_button(
            char_frame,
            "Load Character",
            lambda s = save_info:load_character(s),
            width = 150,
            height = 35,
            font = customtkinter.CTkFont(size = 13)
            )
            load_button.grid(row = 0, column = 1, rowspan = 4, padx = 15, pady = 10)

        button_frame = customtkinter.CTkFrame(main_frame, fg_color = "transparent")
        button_frame.grid(row = 2, column = 0, pady =(10, 0))

        load_backup_button = self._create_sound_button(
        button_frame,
        "Load from Backup",
        lambda:self._open_load_from_backup(),
        width = 200,
        height = 50,
        font = customtkinter.CTkFont(size = 14),
        fg_color = "#4a5568"
        )
        load_backup_button.pack(side = "left", padx = 10)

        back_button = self._create_sound_button(
        button_frame,
        "Back to Character Management",
        lambda:[self._clear_window(), self._open_character_management()],
        width = 300,
        height = 50,
        font = customtkinter.CTkFont(size = 14)
        )
        back_button.pack(side = "left", padx = 10)

    def _open_load_from_backup(self):

        logging.info("Load from Backup definition called")

        self._clear_window()
        self._play_ui_sound("whoosh1")

        backup_base = os.path.join(saves_folder or "saves", "backups")

        character_folders =[]
        if os.path.exists(backup_base):
            for folder_name in os.listdir(backup_base):
                folder_path = os.path.join(backup_base, folder_name)
                if os.path.isdir(folder_path)and folder_name !="archive":
                    backup_files = glob.glob(os.path.join(folder_path, "*.sldsv"))
                    if backup_files:
                        character_folders.append({
                        "name":folder_name,
                        "path":folder_path,
                        "backup_count":len(backup_files)
                        })

        self.root.grid_rowconfigure(0, weight = 1)
        self.root.grid_columnconfigure(0, weight = 1)

        main_frame = customtkinter.CTkFrame(self.root)
        main_frame.grid(row = 0, column = 0, sticky = "nsew", padx = 20, pady = 20)
        main_frame.grid_rowconfigure(1, weight = 1)
        main_frame.grid_columnconfigure(0, weight = 1)

        title = customtkinter.CTkLabel(main_frame, text = "Load from Backup", font = customtkinter.CTkFont(size = 24, weight = "bold"))
        title.grid(row = 0, column = 0, pady =(0, 20))

        if not character_folders:
            no_backups = customtkinter.CTkLabel(
            main_frame,
            text = "No backups found.\nBackups are created automatically when saving characters.",
            font = customtkinter.CTkFont(size = 14),
            text_color = "gray"
            )
            no_backups.grid(row = 1, column = 0, pady = 20)
        else:
            scroll_frame = customtkinter.CTkScrollableFrame(main_frame, width = 700, height = 400)
            scroll_frame.grid(row = 1, column = 0, sticky = "nsew", pady =(0, 20))
            scroll_frame.grid_columnconfigure(0, weight = 1)

            for i, char_folder in enumerate(character_folders):
                folder_frame = customtkinter.CTkFrame(scroll_frame)
                folder_frame.grid(row = i, column = 0, sticky = "ew", pady = 5, padx = 10)
                folder_frame.grid_columnconfigure(0, weight = 1)

                name_label = customtkinter.CTkLabel(
                folder_frame,
                text = char_folder["name"],
                font = customtkinter.CTkFont(size = 18, weight = "bold"),
                anchor = "w"
                )
                name_label.grid(row = 0, column = 0, sticky = "w", padx = 15, pady =(10, 5))

                count_label = customtkinter.CTkLabel(
                folder_frame,
                text = f"{char_folder['backup_count']} backup(s) available",
                font = customtkinter.CTkFont(size = 11),
                text_color = "gray",
                anchor = "w"
                )
                count_label.grid(row = 1, column = 0, sticky = "w", padx = 15, pady =(0, 10))

                browse_button = self._create_sound_button(
                folder_frame,
                "Browse Backups",
                lambda cf = char_folder:self._browse_character_backups(cf),
                width = 150,
                height = 35,
                font = customtkinter.CTkFont(size = 13)
                )
                browse_button.grid(row = 0, column = 1, rowspan = 2, padx = 15, pady = 10)

        back_button = self._create_sound_button(
        main_frame,
        "Back to Load Character",
        lambda:[self._clear_window(), self._load_existing_character()],
        width = 300,
        height = 50,
        font = customtkinter.CTkFont(size = 14)
        )
        back_button.grid(row = 2, column = 0, pady =(10, 0))

    def _browse_character_backups(self, char_folder):

        logging.info(f"Browsing backups for: {char_folder['name']}")

        self._clear_window()
        self._play_ui_sound("whoosh1")

        backup_files =[]
        for backup_path in glob.glob(os.path.join(char_folder["path"], "*.sldsv")):
            try:
                filename = os.path.basename(backup_path)
                mtime = os.path.getmtime(backup_path)
                mtime_str = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M:%S")

                timestamp_part = filename.replace("backup_", "").replace(".sldsv", "")
                try:
                    if "_"in timestamp_part:
                        parts = timestamp_part.split("_")
                        if len(parts)>=2:
                            date_str = f"{parts[0][:4]}-{parts[0][4:6]}-{parts[0][6:8]}"
                            time_str = f"{parts[1][:2]}:{parts[1][2:4]}:{parts[1][4:6]}"
                            display_time = f"{date_str} {time_str}"
                        else:
                            display_time = mtime_str
                    else:
                        display_time = mtime_str
                except Exception:
                    display_time = mtime_str

                backup_files.append({
                "path":backup_path,
                "filename":filename,
                "mtime":mtime,
                "display_time":display_time
                })
            except Exception as e:
                logging.warning(f"Failed to read backup file info: {e}")

        backup_files.sort(key = lambda x:x["mtime"], reverse = True)

        self.root.grid_rowconfigure(0, weight = 1)
        self.root.grid_columnconfigure(0, weight = 1)

        main_frame = customtkinter.CTkFrame(self.root)
        main_frame.grid(row = 0, column = 0, sticky = "nsew", padx = 20, pady = 20)
        main_frame.grid_rowconfigure(1, weight = 1)
        main_frame.grid_columnconfigure(0, weight = 1)

        title = customtkinter.CTkLabel(
        main_frame,
        text = f"Backups: {char_folder['name']}",
        font = customtkinter.CTkFont(size = 24, weight = "bold")
        )
        title.grid(row = 0, column = 0, pady =(0, 20))

        scroll_frame = customtkinter.CTkScrollableFrame(main_frame, width = 700, height = 400)
        scroll_frame.grid(row = 1, column = 0, sticky = "nsew", pady =(0, 20))
        scroll_frame.grid_columnconfigure(0, weight = 1)

        def load_backup(backup_info):
            try:
                backup_data = self._read_save_from_path(backup_info["path"])
                if backup_data is None:
                    self._popup_show_info("Error", "Failed to read backup file.", sound = "error")
                    return

                def confirm_load():
                    try:
                        char_name = backup_data.get("charactername", "Unknown")
                        uuid_val = backup_data.get("uuid")
                        if not uuid_val:
                            import uuid
                            uuid_val = str(uuid.uuid4())
                            backup_data["uuid"]= uuid_val

                        save_filename = f"{char_name}_{uuid_val}"
                        save_path = os.path.join(saves_folder or "saves", f"{save_filename}.sldsv")

                        self._write_save_to_path(save_path, backup_data)

                        self.currentsave = save_filename
                        persistentdata["save_uuids"].setdefault(uuid_val, char_name)
                        persistentdata["last_loaded_save"]= uuid_val
                        self._save_persistent_data()

                        logging.info(f"Restored backup for '{char_name}' from {backup_info['filename']}")
                        self._popup_show_info("Success", f"Backup restored for '{char_name}'!\nBackup time: {backup_info['display_time']}", sound = "success")
                        self._clear_window()
                        self._build_main_menu()
                    except Exception as e:
                        logging.error(f"Failed to restore backup: {e}")
                        self._popup_show_info("Error", f"Failed to restore backup: {e}", sound = "error")

                self._popup_confirm(
                "Restore Backup",
                f"This will restore the backup from:\n{backup_info['display_time']}\n\nThis will overwrite the current save for this character.\nContinue?",
                confirm_load
                )
            except Exception as e:
                logging.error(f"Failed to load backup: {e}")
                self._popup_show_info("Error", f"Failed to load backup: {e}", sound = "error")

        for i, backup_info in enumerate(backup_files):
            is_latest =(i ==0)
            backup_frame = customtkinter.CTkFrame(
            scroll_frame,
            fg_color =("#2d5a2d", "#1a3d1a")if is_latest else None,
            border_width = 2 if is_latest else 0,
            border_color = "#4ade80"if is_latest else None
            )
            backup_frame.grid(row = i, column = 0, sticky = "ew", pady = 3, padx = 10)
            backup_frame.grid_columnconfigure(0, weight = 1)

            time_text = backup_info["display_time"]
            if is_latest:
                time_text = f"☆ {time_text}(Latest)"

            time_label = customtkinter.CTkLabel(
            backup_frame,
            text = time_text,
            font = customtkinter.CTkFont(size = 14, weight = "bold"),
            text_color = "#4ade80"if is_latest else None,
            anchor = "w"
            )
            time_label.grid(row = 0, column = 0, sticky = "w", padx = 15, pady =(8, 2))

            file_label = customtkinter.CTkLabel(
            backup_frame,
            text = backup_info["filename"],
            font = customtkinter.CTkFont(size = 10),
            text_color = "#86efac"if is_latest else "gray",
            anchor = "w"
            )
            file_label.grid(row = 1, column = 0, sticky = "w", padx = 15, pady =(0, 8))

            load_btn = self._create_sound_button(
            backup_frame,
            "Restore",
            lambda bi = backup_info:load_backup(bi),
            width = 100,
            height = 30,
            font = customtkinter.CTkFont(size = 12)
            )
            load_btn.grid(row = 0, column = 1, rowspan = 2, padx = 15, pady = 5)

        back_button = self._create_sound_button(
        main_frame,
        "Back to Backup List",
        lambda:self._open_load_from_backup(),
        width = 300,
        height = 50,
        font = customtkinter.CTkFont(size = 14)
        )
        back_button.grid(row = 2, column = 0, pady =(10, 0))
