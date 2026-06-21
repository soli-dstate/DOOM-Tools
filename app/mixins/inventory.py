"""InventoryMixin — App methods for the "inventory" feature area."""
from app.foundation import *
import logging


class InventoryMixin:

    def _open_item_bet_dialog(self, save_data, wagered_items, on_update_cb = None):
        if not save_data:
            self._popup_show_info("Error", "No character data available for item betting.", sound = "error")
            return

        popup = customtkinter.CTkToplevel(self.root)
        popup.title("Wager Items")
        popup.transient(self.root)
        popup.grab_set()
        popup.withdraw()

        all_items = self._get_all_player_items_from_save(save_data)

        wager_total =[sum(int(e["item"].get("value", 0))for e in wagered_items)]

        status_label = customtkinter.CTkLabel(popup, text = f"Wagered Items Value: {format_price(wager_total[0])}", font = customtkinter.CTkFont(size = 14, weight = "bold"), text_color = "gold")
        status_label.pack(pady =(10, 5))

        hint_label = customtkinter.CTkLabel(popup, text = "Click items to toggle wager(green = wagered)", font = customtkinter.CTkFont(size = 11), text_color = "gray")
        hint_label.pack(pady =(0, 5))

        scroll_frame = customtkinter.CTkScrollableFrame(popup, width = 450, height = 400)
        scroll_frame.pack(fill = "both", expand = True, padx = 10, pady = 5)

        for item_data in all_items:
            item = item_data["item"]
            location = item_data["location"]
            item_idx = item_data["index"]

            if item.get("_from_armory"):
                continue

            item_value = int(item.get("value", 0))
            if item_value <=0:
                continue

            item_frame = customtkinter.CTkFrame(scroll_frame)
            item_frame.pack(fill = "x", pady = 3, padx = 5)

            cart_key = f"{location}:{item_idx}"
            is_selected = any(f"{e['location']}:{e['index']}"==cart_key for e in wagered_items)
            if is_selected:
                item_frame.configure(fg_color =("green", "darkgreen"))

            location_text = location.replace("equipment.", "").replace(".list.", " #").replace(".subslot.", " sub#")

            name_label = customtkinter.CTkLabel(item_frame, text = f"{self._format_item_name(item)}({format_price(item_value)})", font = customtkinter.CTkFont(size = 11), anchor = "w")
            name_label.pack(anchor = "w", padx = 8, pady =(5, 0))

            loc_label = customtkinter.CTkLabel(item_frame, text = f"{location_text}", font = customtkinter.CTkFont(size = 9), text_color = "gray", anchor = "w")
            loc_label.pack(anchor = "w", padx = 8, pady =(0, 3))

            def toggle_item(loc = location, i = item_idx, it = item, val = item_value, frame = item_frame):
                cart_key = f"{loc}:{i}"
                existing =[idx for idx, e in enumerate(wagered_items)if f"{e['location']}:{e['index']}"==cart_key]
                if existing:
                    wagered_items.pop(existing[0])
                    wager_total[0]-=val
                    frame.configure(fg_color =("gray86", "gray17"))
                else:
                    wagered_items.append({"location":loc, "index":i, "item":it, "value":val})
                    wager_total[0]+=val
                    frame.configure(fg_color =("green", "darkgreen"))
                status_label.configure(text = f"Wagered Items Value: {format_price(wager_total[0])}")
                self._play_ui_sound("click")

            item_frame.bind("<Button-1>", lambda e, f = toggle_item:f())
            name_label.bind("<Button-1>", lambda e, f = toggle_item:f())
            loc_label.bind("<Button-1>", lambda e, f = toggle_item:f())

        def confirm_wager():
            if on_update_cb:
                on_update_cb()
            popup.destroy()

        def clear_wager():
            wagered_items.clear()
            wager_total[0]= 0
            status_label.configure(text = f"Wagered Items Value: {format_price(wager_total[0])}")
            for widget in scroll_frame.winfo_children():
                try:
                    widget.configure(fg_color =("gray86", "gray17"))
                except Exception:
                    logging.exception("Suppressed exception")
            if on_update_cb:
                on_update_cb()
            self._play_ui_sound("click")

        btn_frame = customtkinter.CTkFrame(popup, fg_color = "transparent")
        btn_frame.pack(pady = 10)

        clear_btn = self._create_sound_button(btn_frame, "Clear All", clear_wager, width = 120, height = 35, font = customtkinter.CTkFont(size = 12))
        clear_btn.pack(side = "left", padx = 5)

        confirm_btn = self._create_sound_button(btn_frame, "Confirm", confirm_wager, width = 120, height = 35, font = customtkinter.CTkFont(size = 12))
        confirm_btn.pack(side = "left", padx = 5)

        self._play_ui_sound("click")
        popup.update_idletasks()
        w, h = 500, 550
        x = self.root.winfo_x()+(self.root.winfo_width()//2)-(w //2)
        y = self.root.winfo_y()+(self.root.winfo_height()//2)-(h //2)
        popup.geometry(f"{w}x{h}+{x}+{y}")
        popup.deiconify()

    def _process_item_bet_loss(self, save_data, save_path, wagered_items):
        if not wagered_items or not save_data or not save_path:
            return
        try:
            locations_to_remove = {}
            for entry in wagered_items:
                loc = entry["location"]
                idx = entry["index"]
                if loc not in locations_to_remove:
                    locations_to_remove[loc]=[]
                locations_to_remove[loc].append(idx)

            for loc in locations_to_remove:
                locations_to_remove[loc]= sorted(locations_to_remove[loc], reverse = True)

            for loc, indices in locations_to_remove.items():
                for idx in indices:
                    self._remove_item_from_save_location(save_data, loc, idx)

            self._write_save_to_path(save_path, save_data)

            item_names =[e["item"].get("name", "Unknown")for e in wagered_items]
            logging.info(f"Items lost in gambling: {item_names}")
        except Exception as e:
            logging.error(f"Failed to process item bet loss: {e}")

    def _open_inventory_manager_tool(self):
        logging.info("Inventory Manager definition called")
        self._clear_window()

        self.root.grid_rowconfigure(0, weight = 1)
        self.root.grid_columnconfigure(0, weight = 1)

        main_frame = customtkinter.CTkFrame(self.root)
        main_frame.grid(row = 0, column = 0, sticky = "nsew")

        title_label = customtkinter.CTkLabel(main_frame, text = "Inventory Manager", font = customtkinter.CTkFont(size = 24, weight = "bold"))
        title_label.pack(pady = 20)

        character_management_button = self._create_sound_button(main_frame, "Character Management", lambda:[self._clear_window(), self._open_character_management()], width = 500, height = 50, font = customtkinter.CTkFont(size = 16))
        character_management_button.pack(pady = 20)
        inventory_management_button = self._create_sound_button(main_frame, "Inventory Management", lambda:[self._clear_window(), self._open_inventory_management()], width = 500, height = 50, font = customtkinter.CTkFont(size = 16), state = "disabled"if self.currentsave is None else "normal")
        inventory_management_button.pack(pady = 20)
        item_equip_button = self._create_sound_button(main_frame, "Item Equipping", lambda:[self._clear_window(), self._open_item_equipping()], width = 500, height = 50, font = customtkinter.CTkFont(size = 16), state = "disabled"if self.currentsave is None else "normal")
        item_equip_button.pack(pady = 20)
        back_button = self._create_sound_button(main_frame, "Back to Main Menu", lambda:[self._clear_window(), self._build_main_menu()], width = 500, height = 50, font = customtkinter.CTkFont(size = 16))
        back_button.pack(pady = 20)

        if self.currentsave is None:
            warning_label = customtkinter.CTkLabel(main_frame, text = "Load or create a character to access inventory features.", font = customtkinter.CTkFont(size = 14), text_color = "orange")
            warning_label.pack(pady = 10)

    def _open_inventory_management(self):
        logging.info("Inventory Management definition called")

        self._clear_window()

        self.root.grid_rowconfigure(0, weight = 1)
        self.root.grid_columnconfigure(0, weight = 1)

        main_frame = customtkinter.CTkFrame(self.root)
        main_frame.grid(row = 0, column = 0, sticky = "nsew", padx = 20, pady = 20)
        main_frame.grid_columnconfigure(0, weight = 1)

        title = customtkinter.CTkLabel(main_frame, text = "Inventory Management", font = customtkinter.CTkFont(size = 24, weight = "bold"))
        title.pack(pady =(0, 20))

        container_management_button = self._create_sound_button(
        main_frame,
        "Manage Containers & Transfer Items",
        lambda:[self._clear_window(), self._manage_containers()],
        width = 500,
        height = 50,
        font = customtkinter.CTkFont(size = 16)
        )
        container_management_button.pack(pady = 10)

        player_transfer_button = self._create_sound_button(
        main_frame,
        "Transfer to Another Player(Export/Import)",
        lambda:[self._clear_window(), self._transfer_player()],
        width = 500,
        height = 50,
        font = customtkinter.CTkFont(size = 16)
        )
        player_transfer_button.pack(pady = 10)

        back_button = self._create_sound_button(
        main_frame,
        "Back to Inventory Manager",
        lambda:[self._clear_window(), self._open_inventory_manager_tool()],
        width = 500,
        height = 50,
        font = customtkinter.CTkFont(size = 16)
        )
        back_button.pack(pady = 10)

    def _format_weight(self, weight_kg):

        if appearance_settings["units"]=="imperial":
            weight_lb = weight_kg *2.20462
            return f"{weight_lb:.2f} lb"
        elif appearance_settings["units"]=="cheese":
            cheese_wheels = weight_kg /40.0
            if cheese_wheels ==1.0:
                return "1 cheese wheel"
            elif cheese_wheels ==int(cheese_wheels):
                return f"{int(cheese_wheels)} cheese wheels"
            else:
                return f"{cheese_wheels:.2f} cheese wheels"
        else:
            return f"{weight_kg:.2f} kg"

    def _iter_carried_items(self, save_data, include_storage = False):
        """Yield (location, item) for every item the player is carrying.

        Recurses through hands and all equipment containers (items, subslots,
        accessories and nested containers) so consumables / lighting devices are
        found no matter which worn container they sit in. Storage is excluded
        unless include_storage is True.
        """
        results = []
        seen = set()

        def _walk(node, loc):
            if not isinstance(node, dict):
                return
            nid = id(node)
            if nid in seen:
                return
            seen.add(nid)
            for child in node.get("items", []) or []:
                if isinstance(child, dict):
                    results.append((loc, child))
                    _walk(child, loc)
            for field in ("subslots", "accessories"):
                for entry in node.get(field, []) or []:
                    if isinstance(entry, dict):
                        curr = entry.get("current")
                        if isinstance(curr, dict):
                            results.append((loc, curr))
                            _walk(curr, loc)

        hands = save_data.get("hands", {})
        if isinstance(hands, dict):
            _walk(hands, "hands")

        for slot_name, eq_item in (save_data.get("equipment", {}) or {}).items():
            if isinstance(eq_item, dict):
                _walk(eq_item, f"equipment.{slot_name}")

        if include_storage:
            for st_item in save_data.get("storage", []) or []:
                if isinstance(st_item, dict):
                    results.append(("storage", st_item))
                    _walk(st_item, "storage")

        return results

    def _remove_item_by_identity(self, save_data, target, include_storage = True):
        """Remove `target` from whichever carried/stored container holds it."""
        parent, key = self._find_item_container(save_data, target, include_storage = include_storage)
        if parent is None:
            return False
        try:
            if key == "current":
                parent["current"] = None
            elif isinstance(key, int):
                parent.pop(key)
            else:
                return False
            return True
        except Exception:
            return False

    def _consume_item(self, item, location, save_data, on_complete = None):

        import threading

        if not item or not isinstance(item, dict):
            self._popup_show_info("Error", "Invalid item.", sound = "error")
            return

        if not item.get("consumable"):
            self._popup_show_info("Error", "This item is not consumable.", sound = "error")
            return

        table_items_map = {}
        try:
            table_files = sorted(glob.glob(os.path.join("tables", f"*{global_variables.get('table_extension', '.sldtbl')}")))
            cur_tbl = global_variables.get("current_table")
            target_file = None
            if cur_tbl:
                for fpath in table_files:
                    if os.path.abspath(fpath).endswith(cur_tbl)or os.path.basename(fpath)==cur_tbl:
                        target_file = fpath
                        break
            if not target_file and table_files:
                target_file = table_files[0]
            if target_file:
                with open(target_file, 'r', encoding = 'utf-8')as f:
                    table_data = json.load(f)
                for table_name, items_list in table_data.get("tables", {}).items():
                    if isinstance(items_list, list):
                        for tbl_item in items_list:
                            if isinstance(tbl_item, dict)and "id"in tbl_item:
                                table_items_map[tbl_item["id"]]= tbl_item
        except Exception as e:
            logging.warning(f"Failed to load table for weight calculation: {e}")

        if item.get("disinfectant_required"):

            disinfectant_found = None

            for _loc, inv_item in self._iter_carried_items(save_data, include_storage = False):
                if isinstance(inv_item, dict)and inv_item.get("id")==257:
                    disinfectant_found = inv_item
                    break

            if not disinfectant_found:
                self._popup_show_info("Disinfectant Required",
                f"You need isopropyl alcohol(disinfectant) to use {item.get('name', 'this item')}.",
                sound = "error")
                return

            disinfectant_sounds = disinfectant_found.get("consumable_sounds", [])

            if disinfectant_found.get("used_up"):
                uses = disinfectant_found.get("uses_left", 1)
                if uses >1:
                    disinfectant_found["uses_left"]= uses -1

                    dis_id = disinfectant_found.get("id")
                    if dis_id is not None and dis_id in table_items_map:
                        dis_table = table_items_map[dis_id]
                        dis_orig_uses = dis_table.get("uses_left", 1)
                        dis_orig_weight = dis_table.get("weight", 0)
                        if dis_orig_uses >0 and dis_orig_weight >0:
                            disinfectant_found["weight"]= dis_orig_weight *(uses -1)/dis_orig_uses
                else:
                    self._remove_item_by_identity(save_data, disinfectant_found, include_storage = False)

        def find_item_in_location(loc, target_item):

            if loc =="hands":
                items_list = save_data.get("hands", {}).get("items", [])
                for idx, it in enumerate(items_list):
                    if it is target_item:
                        return items_list, idx
            elif loc.startswith("equipment."):
                parts = loc.split(".")
                slot = parts[1]
                eq = save_data.get("equipment", {}).get(slot)
                if eq and isinstance(eq, dict):

                    if len(parts)>=5 and parts[2]=="subslots":
                        try:
                            subslot_idx = int(parts[3])
                            subslots = eq.get("subslots", [])
                            if subslot_idx <len(subslots):
                                subslot = subslots[subslot_idx]
                                curr = subslot.get("current")if isinstance(subslot, dict)else None
                                if curr and isinstance(curr, dict):

                                    if curr is target_item:

                                        return subslot, "current"

                                    items_list = curr.get("items", [])
                                    for idx, it in enumerate(items_list):
                                        if it is target_item:
                                            return items_list, idx
                        except(ValueError, IndexError):
                            logging.exception("Suppressed exception")
                    else:

                        items_list = eq.get("items", [])
                        for idx, it in enumerate(items_list):
                            if it is target_item:
                                return items_list, idx

            # Fallback: locate the item anywhere it is carried/stored by identity,
            # so deeply-nested consumables can still be removed when used up.
            parent, key = self._find_item_container(save_data, target_item, include_storage = True)
            if parent is not None:
                return parent, key
            return None, -1

        def play_sounds_and_finish():

            sounds = item.get("consumable_sounds", [])

            if item.get("lighting_device_required"):

                lighting_device = None
                for _loc, inv_item in self._iter_carried_items(save_data, include_storage = False):
                    if isinstance(inv_item, dict)and inv_item.get("lighting_device"):
                        lighting_device = inv_item
                        break

                if not lighting_device:
                    self._popup_show_info("Lighting Device Required",
                    f"You need a lighter or matches to use {item.get('name', 'this item')}.",
                    sound = "error")
                    return

                new_sounds =[]
                for s in sounds:
                    if s =="lightingdevice":
                        ld_sounds = lighting_device.get("consumable_sounds", [])
                        new_sounds.extend(ld_sounds)
                    else:
                        new_sounds.append(s)
                sounds = new_sounds

                if lighting_device.get("used_up"):
                    uses = lighting_device.get("uses_left", 1)
                    if uses >1:
                        lighting_device["uses_left"]= uses -1

                        ld_id = lighting_device.get("id")
                        if ld_id is not None and ld_id in table_items_map:
                            ld_table = table_items_map[ld_id]
                            ld_orig_uses = ld_table.get("uses_left", 1)
                            ld_orig_weight = ld_table.get("weight", 0)
                            if ld_orig_uses >0 and ld_orig_weight >0:
                                lighting_device["weight"]= ld_orig_weight *(uses -1)/ld_orig_uses
                    else:
                        self._remove_item_by_identity(save_data, lighting_device, include_storage = False)

            if item.get("disinfectant_required")and disinfectant_found:
                for snd in disinfectant_sounds:
                    self._safe_sound_play("misc/consumable", snd.replace(".ogg", ""), block = True)

            for snd in sounds:
                if snd and snd !="lightingdevice":
                    self._safe_sound_play("misc/consumable", snd.replace(".ogg", ""), block = True)

            if item.get("used_up"):
                uses = item.get("uses_left", 1)
                if uses >1:
                    item["uses_left"]= uses -1

                    item_id = item.get("id")
                    if item_id is not None and item_id in table_items_map:
                        table_item = table_items_map[item_id]
                        original_uses = table_item.get("uses_left", 1)
                        original_weight = table_item.get("weight", 0)
                        if original_uses >0 and original_weight >0:
                            new_weight = original_weight *(uses -1)/original_uses
                            item["weight"]= new_weight
                            logging.info(f"Consumed {item.get('name')}, {uses -1} uses remaining, weight now {new_weight:.4f}")
                        else:
                            logging.info(f"Consumed {item.get('name')}, {uses -1} uses remaining")
                    else:
                        logging.info(f"Consumed {item.get('name')}, {uses -1} uses remaining")
                else:

                    items_list_or_subslot, idx = find_item_in_location(location, item)
                    if items_list_or_subslot is not None:
                        if idx =="current":

                            items_list_or_subslot["current"]= None
                            logging.info(f"Consumed and removed {item.get('name')} from subslot")
                        elif isinstance(idx, int)and idx >=0:
                            items_list_or_subslot.pop(idx)
                            logging.info(f"Consumed and removed {item.get('name')}")
            else:
                logging.info(f"Used {item.get('name')}(reusable)")

            self._save_file(save_data)

            if on_complete:
                self.root.after(0, on_complete)

        thread = threading.Thread(target = play_sounds_and_finish, daemon = True)
        thread.start()

    def _use_stratagem(self, item, location, save_data, on_complete = None):

        import threading

        if not item or not isinstance(item, dict):
            self._popup_show_info("Error", "Invalid item.", sound = "error")
            return

        if not item.get("stratagem"):
            self._popup_show_info("Error", "This item is not a stratagem.", sound = "error")
            return

        num_rounds = item.get("rounds", 1)

        rounds_data =[]
        for r in range(1, num_rounds +1):
            seq = item.get(f"round_{r}", [])
            if seq:
                rounds_data.append(seq)

        if not rounds_data:
            self._popup_show_info("Error", "No stratagem sequences defined.", sound = "error")
            return

        dir_to_arrow = {
        "up":"↑",
        "down":"↓",
        "left":"←",
        "right":"→"
        }

        arrow_to_dir = {
        "Up":"up",
        "Down":"down",
        "Left":"left",
        "Right":"right"
        }

        strat_window = customtkinter.CTkToplevel(self.root)
        strat_window.title(f"Stratagem: {self._format_item_name(item)}")
        strat_window.transient(self.root)
        self._center_popup_on_window(strat_window, 600, 400)
        strat_window.grab_set()
        strat_window.focus_force()

        state = {
        "current_round":0,
        "current_index":0,
        "music_channel":None,
        "is_complete":False
        }

        main_frame = customtkinter.CTkFrame(strat_window)
        main_frame.pack(fill = "both", expand = True, padx = 20, pady = 20)

        title_label = customtkinter.CTkLabel(
        main_frame,
        text = "Starting Stratagem Sequence",
        font = customtkinter.CTkFont(size = 24, weight = "bold")
        )
        title_label.pack(pady = 20)

        round_label = customtkinter.CTkLabel(
        main_frame,
        text = "",
        font = customtkinter.CTkFont(size = 16)
        )
        round_label.pack(pady = 10)

        arrows_frame = customtkinter.CTkFrame(main_frame, fg_color = "transparent")
        arrows_frame.pack(pady = 30)

        arrow_labels =[]

        def play_sound_blocking(sound_name):

            sound_path = os.path.join("sounds", "misc", "stratagem", f"{sound_name}.ogg")
            if os.path.exists(sound_path):
                try:
                    sound = pygame.mixer.Sound(sound_path)
                    sound.play()
                    time.sleep(sound.get_length())
                except Exception as e:
                    logging.warning(f"Failed to play stratagem sound {sound_name}: {e}")

        def play_sound(sound_name):

            sound_path = os.path.join("sounds", "misc", "stratagem", f"{sound_name}.ogg")
            if os.path.exists(sound_path):
                try:
                    sound = pygame.mixer.Sound(sound_path)
                    sound.play()
                except Exception as e:
                    logging.warning(f"Failed to play stratagem sound {sound_name}: {e}")

        def start_music():

            sound_path = os.path.join("sounds", "misc", "stratagem", "game_music.ogg")
            if os.path.exists(sound_path):
                try:
                    sound = pygame.mixer.Sound(sound_path)
                    state["music_channel"]= sound.play(loops = -1)
                except Exception as e:
                    logging.warning(f"Failed to start stratagem music: {e}")

        def stop_music():

            if state["music_channel"]:
                try:
                    state["music_channel"].stop()
                except Exception:
                    logging.exception("Suppressed exception")

        def display_round(round_idx):

            nonlocal arrow_labels

            for lbl in arrow_labels:
                lbl.destroy()
            arrow_labels =[]

            if round_idx >=len(rounds_data):
                return

            sequence = rounds_data[round_idx]
            round_label.configure(text = f"Round {round_idx +1} of {len(rounds_data)}")

            for i, direction in enumerate(sequence):
                arrow = dir_to_arrow.get(direction.lower(), "?")
                lbl = customtkinter.CTkLabel(
                arrows_frame,
                text = arrow,
                font = customtkinter.CTkFont(size = 48, weight = "bold"),
                text_color = "gray"
                )
                lbl.pack(side = "left", padx = 10)
                arrow_labels.append(lbl)

            if arrow_labels:
                arrow_labels[0].configure(text_color = "#3B8ED0")

        def update_arrow_colors():

            sequence = rounds_data[state["current_round"]]
            for i, lbl in enumerate(arrow_labels):
                if i <state["current_index"]:
                    lbl.configure(text_color = "gray")
                elif i ==state["current_index"]:
                    lbl.configure(text_color = "#3B8ED0")
                else:
                    lbl.configure(text_color = "white")

        def show_error():

            for lbl in arrow_labels:
                lbl.configure(text_color = "red")
            play_sound("button_press_error")

            def reset_after_error():
                state["current_index"]= 0
                update_arrow_colors()

            strat_window.after(500, reset_after_error)

        def show_success():

            for lbl in arrow_labels:
                lbl.configure(text_color = "green")

        def on_sequence_complete():

            show_success()

            def after_success():
                play_sound_blocking("sequence_success")
                play_sound_blocking("round_over")

                state["current_round"]+=1
                state["current_index"]= 0

                if state["current_round"]>=len(rounds_data):

                    on_game_complete()
                else:

                    strat_window.after(0, lambda:display_round(state["current_round"]))

            threading.Thread(target = after_success, daemon = True).start()

        def on_game_complete():

            state["is_complete"]= True
            stop_music()

            def finish_game():
                play_sound_blocking("game_over")

                def find_and_remove():
                    if location =="hands":
                        items_list = save_data.get("hands", {}).get("items", [])
                        for idx, it in enumerate(items_list):
                            if it is item:
                                items_list.pop(idx)
                                break
                    elif location.startswith("equipment."):
                        parts = location.split(".")
                        slot = parts[1]
                        eq = save_data.get("equipment", {}).get(slot)
                        if eq and isinstance(eq, dict):
                            items_list = eq.get("items", [])
                            for idx, it in enumerate(items_list):
                                if it is item:
                                    items_list.pop(idx)
                                    break

                find_and_remove()
                self._save_file(save_data)
                logging.info(f"Stratagem {item.get('name')} completed and consumed")

                def close_and_callback():
                    strat_window.destroy()
                    if on_complete:
                        on_complete()

                strat_window.after(0, close_and_callback)

            threading.Thread(target = finish_game, daemon = True).start()

        def on_key_press(event):

            if state["is_complete"]:
                return

            if state["current_round"]>=len(rounds_data):
                return

            key_dir = arrow_to_dir.get(event.keysym)
            if not key_dir:
                return

            sequence = rounds_data[state["current_round"]]
            expected = sequence[state["current_index"]].lower()

            if key_dir ==expected:

                play_sound("button_press")
                state["current_index"]+=1

                if state["current_index"]>=len(sequence):

                    on_sequence_complete()
                else:
                    update_arrow_colors()
            else:

                show_error()

        def start_game():

            title_label.configure(text = item.get("name", "Stratagem"))
            start_music()
            display_round(0)
            update_arrow_colors()
            strat_window.bind("<Key>", on_key_press)

        def intro_sequence():

            play_sound_blocking("round_start_coin")
            strat_window.after(0, start_game)

        def on_window_close():

            stop_music()
            strat_window.destroy()

        strat_window.protocol("WM_DELETE_WINDOW", on_window_close)

        threading.Thread(target = intro_sequence, daemon = True).start()

    def _calculate_encumbrance_status(self, save_data):

        def compute_item_weight(itm, include_contained = True):

            if not itm or not isinstance(itm, dict):
                return 0.0
            qty = itm.get("quantity", 1)
            weight = itm.get("weight", 0)*qty

            if include_contained:
                for contained in (itm.get("items") or []):
                    weight +=compute_item_weight(contained, include_contained = True)

            if "subslots"in itm:
                for ss in (itm.get("subslots") or []):
                    if not isinstance(ss, dict):
                        continue
                    current = ss.get("current")
                    weight +=compute_item_weight(current, include_contained = True)

            if "accessories"in itm:
                for acc in (itm.get("accessories") or []):
                    if not isinstance(acc, dict):
                        continue
                    current = acc.get("current")
                    weight +=compute_item_weight(current, include_contained = True)
            return weight

        def compute_encumbrance_contribution(itm, is_equipped = False):

            if not itm or not isinstance(itm, dict):
                return 0.0

            qty = itm.get("quantity", 1)
            base_weight = itm.get("weight", 0)*qty

            reduction = itm.get("encumbrance_reduction", 1.0)if is_equipped else 1.0
            if reduction <=0:
                reduction = 1.0

            encumbrance = base_weight

            contained_weight = 0.0
            for contained in (itm.get("items") or []):
                contained_weight +=compute_item_weight(contained, include_contained = True)

            if is_equipped and reduction >0:

                encumbrance +=contained_weight /reduction
            else:

                encumbrance +=contained_weight

            if "subslots"in itm:
                for ss in (itm.get("subslots") or []):
                    if not isinstance(ss, dict):
                        continue
                    current = ss.get("current")
                    encumbrance +=compute_encumbrance_contribution(current, is_equipped = is_equipped)

            if "accessories"in itm:
                for acc in (itm.get("accessories") or []):
                    if not isinstance(acc, dict):
                        continue
                    current = acc.get("current")
                    encumbrance +=compute_encumbrance_contribution(current, is_equipped = is_equipped)

            return encumbrance

        total_weight = 0.0
        total_encumbrance = 0.0

        for item in save_data.get("hands", {}).get("items", []):
            item_weight = compute_item_weight(item, include_contained = True)
            total_weight +=item_weight
            total_encumbrance +=item_weight

        for slot, item in save_data.get("equipment", {}).items():
            if item and isinstance(item, dict):
                item_weight = compute_item_weight(item, include_contained = True)
                total_weight +=item_weight

                total_encumbrance +=compute_encumbrance_contribution(item, is_equipped = True)

        encumbrance = max(total_encumbrance, 0.0)

        strength = save_data.get("stats", {}).get("Strength", 0)

        stat_clamp = 4
        try:
            import glob, json, os
            tbl_path = get_current_table_path()
            if tbl_path and os.path.exists(tbl_path):
                with open(tbl_path, 'r', encoding = 'utf-8-sig')as tf:
                    td = json.load(tf)
                    sc = td.get("additional_settings", {}).get("stat_clamp")
                    if isinstance(sc, (int, float)):
                        stat_clamp = int(sc)
        except Exception:
            logging.exception("Suppressed exception")

        stat_min = -20
        stat_max = stat_clamp

        m_clamped = max(stat_min, min(strength, stat_max))

        span = float(stat_max -stat_min)
        if span <=0:
            span = 24.0

        threshold = 15.0 +85.0 *(m_clamped -stat_min)/span

        threshold = max(15.0, min(100.0, threshold))

        encumbrance_level = 0
        if encumbrance >threshold:
            overflow_percent =(encumbrance -threshold)/threshold
            encumbrance_level = int(overflow_percent *10)

        return {
        "total_weight":total_weight,
        "total_reduction":0.0,
        "encumbrance":encumbrance,
        "threshold":threshold,
        "encumbrance_level":encumbrance_level,
        "is_encumbered":encumbrance_level >0
        }

    def _transfer_player(self):
        import json
        import base64
        from datetime import datetime

        if self.currentsave is None:
            self._popup_show_info("Error", "No character loaded.", sound = "error")
            return

        self._clear_window()

        try:
            self._set_dnd_refresh_handler(
                callback = self._transfer_player,
                exts = [".sldtrf"],
            )
        except Exception:
            logging.exception("Suppressed exception")

        try:
            self.root.after(50, self._setup_drag_drop)
        except Exception:
            logging.exception("Suppressed exception")

        main_frame = customtkinter.CTkFrame(self.root)
        main_frame.pack(fill = "both", expand = True, padx = 20, pady = 20)

        title = customtkinter.CTkLabel(main_frame, text = "Player Transfer", font = customtkinter.CTkFont(size = 20, weight = "bold"))
        title.pack(pady =(0, 20))

        export_frame = customtkinter.CTkFrame(main_frame)
        export_frame.pack(fill = "x", pady = 10, padx = 10)

        export_label = customtkinter.CTkLabel(export_frame, text = "Export Items/Money", font = customtkinter.CTkFont(size = 16, weight = "bold"))
        export_label.pack(pady = 10)

        money_frame = customtkinter.CTkFrame(export_frame, fg_color = "transparent")
        money_frame.pack(pady = 5)

        money_label = customtkinter.CTkLabel(money_frame, text = "Money Amount:")
        money_label.pack(side = "left", padx = 5)

        money_entry = customtkinter.CTkEntry(money_frame, placeholder_text = format_price(0), width = 150)
        money_entry.pack(side = "left", padx = 5)

        items_label = customtkinter.CTkLabel(export_frame, text = "Select items to export from storage:", font = customtkinter.CTkFont(size = 13))
        items_label.pack(pady =(10, 5))

        items_scroll = customtkinter.CTkScrollableFrame(export_frame, width = 700, height = 200)
        items_scroll.pack(pady = 5, padx = 10)

        selected_items =[]

        def refresh_export_items():
            for widget in items_scroll.winfo_children():
                widget.destroy()
            selected_items.clear()

            save_path = os.path.join(saves_folder or "", (self.currentsave or "")+".sldsv")
            try:
                save_data = self._load_file((self.currentsave or "")+".sldsv")
                if save_data is None:
                    raise RuntimeError("Failed to load current save for export")

                storage_items = save_data.get("storage", [])

                if not storage_items:
                    empty_label = customtkinter.CTkLabel(items_scroll, text = "No items in storage", text_color = "gray")
                    empty_label.pack(pady = 20)
                    return

                for idx, item in enumerate(storage_items):
                    item_frame = customtkinter.CTkFrame(items_scroll)
                    item_frame.pack(fill = "x", pady = 2, padx = 5)

                    var = customtkinter.BooleanVar(value = False)

                    def on_check(index = idx, var_ref = var):
                        if var_ref.get():
                            if index not in selected_items:
                                selected_items.append(index)
                        else:
                            if index in selected_items:
                                selected_items.remove(index)

                    checkbox = customtkinter.CTkCheckBox(
                    item_frame,
                    text = f"{self._format_item_name(item)} x{item.get('quantity', 1)}",
                    variable = var,
                    command = on_check
                    )
                    checkbox.pack(side = "left", padx = 10, pady = 5)
            except Exception as e:
                logging.error(f"Failed to load items: {e}")

        refresh_export_items()

        def create_export():
            try:
                save_path = os.path.join(saves_folder or "", (self.currentsave or "")+".sldsv")
                save_data = self._load_file((self.currentsave or "")+".sldsv")
                if save_data is None:
                    raise RuntimeError("Failed to load current save for export")

                money_amount = parse_display_price_to_usd(money_entry.get(), default = 0, round_to_int = True)

                if money_amount >save_data.get("money", 0):
                    self._popup_show_info("Error", "Not enough money!", sound = "error")
                    return

                storage_items = save_data.get("storage", [])
                items_to_export =[storage_items[i]for i in sorted(selected_items)if i <len(storage_items)]

                transfer_data = {
                "money":money_amount,
                "items":items_to_export,
                "timestamp":datetime.now().isoformat(),
                "from_character":save_data.get("charactername", "Unknown")
                }

                save_data["money"]= save_data.get("money", 0)-money_amount

                for idx in sorted(selected_items, reverse = True):
                    if idx <len(storage_items):
                        storage_items.pop(idx)

                save_data["storage"]= storage_items

                self._save_file(save_data)

                transfer_filename = f"transfers/transfer_{datetime.now().strftime('%Y%m%d_%H%M%S')}.sldtrf"
                _signed_json_write(transfer_filename, transfer_data, portable = True)

                self._popup_show_info("Success", f"Exported {len(items_to_export)} items and {format_price(money_amount)}!", sound = "success")
                logging.info(f"Created transfer file: {transfer_filename}")
                refresh_export_items()
            except Exception as e:
                logging.error(f"Export failed: {e}")
                self._popup_show_info("Error", f"Export failed: {e}", sound = "error")

        export_button = self._create_sound_button(export_frame, "Create Transfer File", create_export, width = 200, height = 40)
        export_button.pack(pady = 10)

        import_frame = customtkinter.CTkFrame(main_frame)
        import_frame.pack(fill = "x", pady = 10, padx = 10)

        import_label = customtkinter.CTkLabel(import_frame, text = "Import Transfer File", font = customtkinter.CTkFont(size = 16, weight = "bold"))
        import_label.pack(pady = 10)

        def list_transfers():
            try:
                transfer_files = glob.glob("transfers/*.sldtrf")
                if not transfer_files:
                    self._popup_show_info("Info", "No transfer files found.", sound = "popup")
                    return

                select_window = customtkinter.CTkToplevel(self.root)
                select_window.title("Select Transfer File")
                select_window.transient(self.root)
                self._center_popup_on_window(select_window, 500, 400)

                scroll_frame = customtkinter.CTkScrollableFrame(select_window, width = 450, height = 300)
                scroll_frame.pack(pady = 10, padx = 10, fill = "both", expand = True)

                def import_transfer(filepath):
                    try:
                        transfer_data, _, t_status = _signed_json_read(filepath, allow_unsigned = False, portable = True)
                        if t_status == "tampered":
                            raise ValueError(f"Transfer file '{filepath}' has been tampered with — signature verification failed.")
                        elif t_status in ("unsigned", "incompatible_format"):
                            raise ValueError(f"Transfer file '{filepath}' is unsigned or incompatible. Download and run convert_legacy_saves.py from github and run with --resign flag to sign it.")
                        elif transfer_data is None:
                            raise ValueError(f"Transfer file '{filepath}' could not be loaded.")

                        save_data = self._load_file((self.currentsave or "")+".sldsv")
                        if save_data is None:
                            raise RuntimeError("Failed to load current save for import")
                        save_data["money"]= save_data.get("money", 0)+transfer_data.get("money", 0)
                        for item in transfer_data.get("items", []):
                            save_data["storage"].append(item)
                        self._save_file(save_data)

                        os.remove(filepath)

                        select_window.destroy()
                        self._popup_show_info("Success", f"Received {format_price(transfer_data.get('money', 0))} and {len(transfer_data.get('items', []))} items!", sound = "success")
                    except Exception as e:
                        logging.error(f"Import failed: {e}")
                        self._popup_show_info("Error", f"Import failed: {e}", sound = "error")

                for i, filepath in enumerate(transfer_files):
                    try:
                        transfer_data, _, t_status = _signed_json_read(filepath, allow_unsigned = False, portable = True)
                        if t_status != "ok" or transfer_data is None:
                            logging.warning(f"Transfer file '{filepath}' could not be verified (status: {t_status}) — skipping.")
                            continue

                        file_frame = customtkinter.CTkFrame(scroll_frame)
                        file_frame.pack(fill = "x", pady = 5, padx = 5)

                        info_label = customtkinter.CTkLabel(
                        file_frame,
                        text = f"From: {transfer_data.get('from_character', 'Unknown')}\nMoney: {format_price(transfer_data.get('money', 0))} | Items: {len(transfer_data.get('items', []))}",
                        anchor = "w"
                        )
                        info_label.pack(side = "left", padx = 10, pady = 5)

                        import_btn = self._create_sound_button(
                        file_frame,
                        "Import",
                        lambda f = filepath:import_transfer(f),
                        width = 100,
                        height = 35
                        )
                        import_btn.pack(side = "right", padx = 10, pady = 5)
                    except Exception as e:
                        logging.warning(f"Failed to read transfer file {filepath}: {e}")

                select_window.update_idletasks()
                select_window.deiconify()
                select_window.grab_set()
            except Exception as e:
                logging.error(f"Failed to list transfers: {e}")
                self._popup_show_info("Error", f"Failed to list transfers: {e}", sound = "error")

        import_button = self._create_sound_button(import_frame, "Browse Transfer Files", list_transfers, width = 200, height = 40)
        import_button.pack(pady = 10)

        back_button = self._create_sound_button(main_frame, "Back", lambda:[self._clear_window(), self._open_inventory_management()], width = 200, height = 40)
        back_button.pack(pady = 20)

    def _open_item_equipping(self):

        logging.info("Item Equipping definition called")

        if self.currentsave is None:
            self._popup_show_info("Error", "No character loaded.", sound = "error")
            return

        self._clear_window()

        save_filename =(self.currentsave or "")+".sldsv"
        save_data = self._load_file(save_filename)

        if save_data is None:
            logging.error(f"Failed to load save file {save_filename}")
            self._popup_show_info("Error", f"Failed to load character data", sound = "error")
            return

        main_frame = customtkinter.CTkFrame(self.root)
        main_frame.pack(fill = "both", expand = True, padx = 20, pady = 20)

        title = customtkinter.CTkLabel(main_frame, text = "Item Equipping", font = customtkinter.CTkFont(size = 20, weight = "bold"))
        title.pack(pady =(0, 20))

        content_frame = customtkinter.CTkFrame(main_frame)
        content_frame.pack(fill = "both", expand = True)
        content_frame.grid_rowconfigure(0, weight = 1)
        content_frame.grid_columnconfigure((0, 1), weight = 1)

        slots_frame = customtkinter.CTkFrame(content_frame)
        slots_frame.grid(row = 0, column = 0, sticky = "nsew", padx =(0, 10))
        slots_frame.grid_rowconfigure(1, weight = 1)

        slots_frame.grid_columnconfigure(0, weight = 1)

        slots_label = customtkinter.CTkLabel(slots_frame, text = "Equipment Slots", font = customtkinter.CTkFont(size = 16, weight = "bold"))
        slots_label.grid(row = 0, column = 0, pady = 10)

        slots_scroll = customtkinter.CTkScrollableFrame(slots_frame, height = 600)
        slots_scroll.grid(row = 1, column = 0, sticky = "nsew", padx = 10, pady =(0, 10))

        items_frame = customtkinter.CTkFrame(content_frame)
        items_frame.grid(row = 0, column = 1, sticky = "nsew", padx =(10, 0))
        items_frame.grid_rowconfigure(1, weight = 1)

        items_frame.grid_columnconfigure(0, weight = 1)

        items_label = customtkinter.CTkLabel(items_frame, text = "Available Items(Storage & Hands)", font = customtkinter.CTkFont(size = 16, weight = "bold"))
        items_label.grid(row = 0, column = 0, pady = 10)

        items_scroll = customtkinter.CTkScrollableFrame(items_frame, height = 600)
        items_scroll.grid(row = 1, column = 0, sticky = "nsew", padx = 10, pady =(0, 10))

        def refresh_display():

            for widget in slots_scroll.winfo_children():
                widget.destroy()
            for widget in items_scroll.winfo_children():
                widget.destroy()

            equipment = save_data.get("equipment", {})

            def _slot_blocked_by_subslots(slot_name):
                try:
                    def _resolve_conflicts(conflicts):
                        targets = []
                        try:
                            if isinstance(conflicts, dict):
                                slot_field = conflicts.get('slot')
                                if slot_field:
                                    if isinstance(slot_field, (list, tuple)):
                                        targets = [str(c) for c in slot_field]
                                    else:
                                        targets = [str(slot_field)]
                            elif isinstance(conflicts, (list, tuple)):
                                targets = [str(c) for c in conflicts]
                            elif conflicts:
                                targets = [str(conflicts)]
                        except Exception:
                            targets = []
                        return [t.lower() for t in targets if t is not None]

                    slot_name_l = str(slot_name).lower() if slot_name is not None else ''
                    for other_slot, other_item in equipment.items():
                        if not other_item:
                            continue
                        items_to_check = []
                        if isinstance(other_item, dict):
                            items_to_check = [other_item]
                        elif isinstance(other_item, list):
                            items_to_check = [it for it in other_item if isinstance(it, dict)]

                        for oi in items_to_check:

                            for subslot_data in oi.get('subslots', []) or []:
                                try:
                                    conflicts = subslot_data.get('conflicts_with')
                                    cur = subslot_data.get('current')
                                    if not cur:
                                        continue
                                    targets_l = _resolve_conflicts(conflicts)
                                    if slot_name_l in targets_l:
                                        return True
                                except Exception:
                                    logging.exception("Suppressed exception")

                            for acc in oi.get('accessories', []) or []:
                                try:
                                    curacc = acc.get('current')
                                    if not isinstance(curacc, dict):
                                        continue
                                    for subslot_data in curacc.get('subslots', []) or []:
                                        try:
                                            conflicts = subslot_data.get('conflicts_with')
                                            cur = subslot_data.get('current')
                                            if not cur:
                                                continue
                                            targets_l = _resolve_conflicts(conflicts)
                                            if slot_name_l in targets_l:
                                                return True
                                        except Exception:
                                            logging.exception("Suppressed exception")
                                except Exception:
                                    logging.exception("Suppressed exception")

                            try:
                                item_conflicts = oi.get('conflicts_with')
                                if item_conflicts:
                                    targets_l = _resolve_conflicts(item_conflicts)
                                    if slot_name_l in targets_l:
                                        return True
                            except Exception:
                                logging.exception("Suppressed exception")
                    return False
                except Exception:
                    return False

            for slot, item in equipment.items():
                slot_frame = customtkinter.CTkFrame(slots_scroll)
                slot_frame.pack(fill = "x", pady = 5, padx = 5)

                slot_label = customtkinter.CTkLabel(
                slot_frame,
                text = f"{slot.title()}:",
                font = customtkinter.CTkFont(size = 12, weight = "bold"),
                anchor = "w"
                )
                slot_label.pack(side = "top", anchor = "w", padx = 10, pady =(5, 0))

                if item:

                    if isinstance(item, list):
                        counts = {}
                        for it in item:
                            try:
                                if isinstance(it, dict):
                                    name = it.get('name', 'Unknown')
                                else:
                                    name = str(it)
                            except Exception:
                                name = 'Unknown'
                            counts[name]= counts.get(name, 0)+1

                        if len(counts)==1:
                            name, cnt = next(iter(counts.items()))
                            display_text = f" {name} x{cnt}"
                        else:

                            parts =[f"{n} x{c}"for n, c in counts.items()]
                            display_text = "(MIXED - NOT ALLOWED) "+", ".join(parts)

                            item_label = customtkinter.CTkLabel(
                            slot_frame,
                            text = display_text,
                            anchor = "w",
                            text_color = "#FF4444"
                            )
                            item_label.pack(side = "top", anchor = "w", padx = 10)

                            continue
                    else:
                        item_name = self._format_item_name(item)if isinstance(item, dict)else str(item)
                        display_text = f" {item_name}"

                    item_label = customtkinter.CTkLabel(
                    slot_frame,
                    text = display_text,
                    anchor = "w",
                    text_color = "lightblue"
                    )
                    item_label.pack(side = "top", anchor = "w", padx = 10)

                    unequip_button = self._create_sound_button(
                    slot_frame,
                    "Unequip",
                    lambda s = slot:unequip_item(s),
                    width = 80,
                    height = 30
                    )
                    unequip_button.pack(side = "right", padx = 10, pady = 5)

                    if isinstance(item, dict)and item.get("subslots"):
                        for subslot_data in item["subslots"]:
                            subslot_name = subslot_data.get("name", "Unknown Subslot")
                            subslot_type = subslot_data.get("slot", "unknown")
                            current_item = subslot_data.get("current")

                            subslot_frame = customtkinter.CTkFrame(slots_scroll)
                            subslot_frame.pack(fill = "x", pady = 2, padx = 5)

                            subslot_label = customtkinter.CTkLabel(
                            subslot_frame,
                            text = f" ↳ {subslot_name}:",
                            font = customtkinter.CTkFont(size = 11),
                            anchor = "w",
                            text_color = "#FFA500"
                            )
                            subslot_label.pack(side = "top", anchor = "w", padx = 20, pady =(5, 0))

                            if current_item:
                                subitem_name = current_item.get("name", "Unknown")if isinstance(current_item, dict)else str(current_item)

                                is_container = isinstance(current_item, dict)and current_item.get("container", False)
                                if is_container:
                                    total_weight = sum(i.get("weight", 0)*i.get("quantity", 1)for i in current_item.get("items", []))
                                    capacity = current_item.get("capacity", 0)
                                    subitem_text = f" {subitem_name}[{self._format_weight(total_weight)}/{self._format_weight(capacity)}]"
                                elif isinstance(current_item, dict) and current_item.get("hits_left") is not None:
                                    subitem_text = f" {subitem_name} [{current_item['hits_left']} hits left]"
                                else:
                                    subitem_text = f" {subitem_name}"

                                subitem_label = customtkinter.CTkLabel(
                                subslot_frame,
                                text = subitem_text,
                                anchor = "w",
                                text_color = "lightgreen"
                                )
                                subitem_label.pack(side = "top", anchor = "w", padx = 20)

                                button_container = customtkinter.CTkFrame(subslot_frame, fg_color = "transparent")
                                button_container.pack(side = "right", padx = 10, pady = 5)

                                unequip_sub_button = self._create_sound_button(
                                button_container,
                                "Unequip",
                                lambda s = slot, ss = subslot_data:unequip_from_subslot(s, ss),
                                width = 80,
                                height = 25
                                )
                                unequip_sub_button.pack(side = "left", padx = 2)

                                if isinstance(current_item, dict) and (current_item.get("hits_left") is not None or current_item.get("material") in ("ceramic", "steel")):
                                    _hit_item = current_item
                                    _hit_subslot = subslot_data
                                    _hit_slot = slot

                                    def _armor_hit_register(ci=_hit_item, ss=_hit_subslot, sl=_hit_slot):
                                        try:
                                            mat = str(ci.get("material", "") or "").lower()
                                            plate_name = ci.get("name", "Armor Plate")
                                            has_uses = ci.get("hits_left") is not None
                                            self._safe_sound_play("misc/armor", "impact" + str(random.randint(0, 2)))

                                            if has_uses:
                                                old_hits = int(ci.get("hits_left", 0) or 0)
                                                new_hits = max(0, old_hits - 1)
                                                ci["hits_left"] = new_hits

                                                if new_hits <= 0:
                                                    if mat == "ceramic":
                                                        import time as _t_armor
                                                        _t_armor.sleep(0.3)
                                                        self._safe_sound_play("misc/armor", "ceramicshatter")
                                                    d20 = random.randint(1, 20)
                                                    if d20 == 1:
                                                        dmg_text = "VITAL ORGAN HIT"
                                                        dmg_color = "#FF0000"
                                                    elif d20 <= 5:
                                                        dmg_text = "Heavy Damage"
                                                        dmg_color = "#FF4444"
                                                    elif d20 <= 10:
                                                        dmg_text = "Medium Damage"
                                                        dmg_color = "#FFA500"
                                                    elif d20 <= 19:
                                                        dmg_text = "Light Damage"
                                                        dmg_color = "#FFFF00"
                                                    else:
                                                        dmg_text = "No Damage"
                                                        dmg_color = "#33FF33"

                                                    import time as _t_armor2
                                                    _t_armor2.sleep(0.4)
                                                    self._safe_sound_play("misc/armor", "fleshhit")

                                                    spall_text = ""
                                                    if mat == "steel":
                                                        d4 = random.randint(1, 4)
                                                        if d4 <= 3:
                                                            spall_text = "\n\nSpall: YES (d4 = {})".format(d4)
                                                        else:
                                                            spall_text = "\n\nSpall: No (d4 = {})".format(d4)

                                                    shatter_text = ""
                                                    if mat == "ceramic":
                                                        shatter_text = "\n\nPlate SHATTERED!"

                                                    ss["current"] = None
                                                    self._save_file(save_data)
                                                    self._popup_show_info(
                                                        "Plate Destroyed",
                                                        f"{plate_name} has been destroyed!\n\n"
                                                        f"d20 = {d20}: {dmg_text}{shatter_text}{spall_text}",
                                                        sound="error"
                                                    )
                                                    refresh_display()
                                                    return
                                                else:
                                                    self._save_file(save_data)
                                                    self._popup_show_info(
                                                        "Armor Hit",
                                                        f"{plate_name} absorbed the hit.\n\n"
                                                        f"Hits remaining: {new_hits}",
                                                        sound="popup"
                                                    )
                                                    refresh_display()
                                                    return
                                            else:
                                                spall_text = ""
                                                if mat == "steel":
                                                    d4 = random.randint(1, 4)
                                                    if d4 <= 3:
                                                        spall_text = f"\n\nSpall: YES (d4 = {d4})"
                                                    else:
                                                        spall_text = f"\n\nSpall: No (d4 = {d4})"
                                                self._popup_show_info(
                                                    "Armor Hit",
                                                    f"{plate_name} absorbed the hit.{spall_text}",
                                                    sound="popup"
                                                )
                                        except Exception:
                                            logging.exception("Armor hit register failed")

                                    hit_reg_button = self._create_sound_button(
                                    button_container,
                                    "Hit",
                                    _armor_hit_register,
                                    width = 50,
                                    height = 25
                                    )
                                    hit_reg_button.pack(side = "left", padx = 2)

                                if is_container:
                                    view_button = self._create_sound_button(
                                    button_container,
                                    "View",
                                    lambda ci = current_item:view_container_contents(ci),
                                    width = 60,
                                    height = 25
                                    )
                                    view_button.pack(side = "left", padx = 2)

                                try:
                                    def _render_nested_subslots(parent_item, parent_frame, parent_slot, parent_subslot):
                                        try:
                                            for n_idx, n_sub in enumerate(parent_item.get('subslots', [])or[]):
                                                try:
                                                    n_name = n_sub.get('name', 'Unknown Subslot')
                                                    n_slot = n_sub.get('slot', 'unknown')
                                                    n_current = n_sub.get('current')

                                                    n_frame = customtkinter.CTkFrame(parent_frame)
                                                    n_frame.pack(fill = 'x', pady = 2, padx = 20)

                                                    n_label = customtkinter.CTkLabel(
                                                    n_frame,
                                                    text = f" ↳ {n_name}:",
                                                    font = customtkinter.CTkFont(size = 10),
                                                    anchor = "w",
                                                    text_color = "#FFD700"
                                                    )
                                                    n_label.pack(side = "top", anchor = "w", padx = 10, pady =(4, 0))

                                                    if n_current:
                                                        try:
                                                            nn_name = n_current.get('name', 'Unknown')if isinstance(n_current, dict)else str(n_current)
                                                        except Exception:
                                                            nn_name = 'Unknown'
                                                        nn_label = customtkinter.CTkLabel(n_frame, text = f" {nn_name}", anchor = 'w', text_color = 'lightgreen', font = customtkinter.CTkFont(size = 10))
                                                        nn_label.pack(side = 'top', anchor = 'w', padx = 10)

                                                        btn_cont = customtkinter.CTkFrame(n_frame, fg_color = 'transparent')
                                                        btn_cont.pack(side = 'right', padx = 10, pady = 4)

                                                        unequip_n = self._create_sound_button(btn_cont, 'Unequip', lambda s = parent_slot, ss = parent_subslot, idx = n_idx:unequip_from_subslot(s, ss, subindex = idx)if callable(unequip_from_subslot)else None, width = 70, height = 22)
                                                        unequip_n.pack(side = 'left', padx = 2)

                                                        try:
                                                            if isinstance(n_current, dict):
                                                                _render_nested_subslots(n_current, n_frame, parent_slot, n_sub)
                                                        except Exception:
                                                            logging.exception("Suppressed exception")
                                                    else:
                                                        empty_n = customtkinter.CTkLabel(n_frame, text = f"(empty - accepts: {n_slot})", anchor = 'w', text_color = 'gray', font = customtkinter.CTkFont(size = 9))
                                                        empty_n.pack(side = 'top', anchor = 'w', padx = 10, pady =(0, 4))
                                                except Exception:
                                                    logging.exception("Suppressed exception")
                                        except Exception:
                                            logging.exception("Suppressed exception")

                                    if isinstance(current_item, dict)and current_item.get('subslots'):
                                        _render_nested_subslots(current_item, subslot_frame, slot, subslot_data)
                                except Exception:
                                    logging.exception("Suppressed exception")
                            else:
                                try:
                                    conflicts = subslot_data.get('conflicts_with')
                                except Exception:
                                    conflicts = None

                                if conflicts:
                                    try:
                                        if isinstance(conflicts, dict):
                                            conf_slots =[conflicts.get('slot')]if conflicts.get('slot')else[]
                                        elif isinstance(conflicts, (list, tuple)):
                                            conf_slots =[str(c)for c in conflicts]
                                        else:
                                            conf_slots =[str(conflicts)]
                                        conf_slots =[c for c in conf_slots if c]
                                        conf_text = ', '.join(conf_slots)if conf_slots else 'unknown'
                                    except Exception:
                                        conf_text = 'unknown'
                                    empty_text = f"Conflicts with: {conf_text}"
                                    text_color = "#FF4444"
                                else:
                                    empty_text = f"(empty - accepts: {subslot_type})"
                                    text_color = "gray"

                                empty_sub_label = customtkinter.CTkLabel(
                                subslot_frame,
                                text = empty_text,
                                anchor = "w",
                                text_color = text_color,
                                font = customtkinter.CTkFont(size = 10)
                                )
                                empty_sub_label.pack(side = "top", anchor = "w", padx = 20, pady =(0, 5))

                                try:
                                    nested_list = subslot_data.get('subslots')or[]
                                    if nested_list:
                                        for nsub in nested_list:
                                            try:
                                                n_name = nsub.get('name', 'Unknown Subslot')
                                                n_slot = nsub.get('slot', 'unknown')

                                                n_frame = customtkinter.CTkFrame(subslot_frame)
                                                n_frame.pack(fill = 'x', pady = 2, padx = 20)

                                                n_label = customtkinter.CTkLabel(
                                                n_frame,
                                                text = f" ↳ {n_name}:",
                                                font = customtkinter.CTkFont(size = 10),
                                                anchor = "w",
                                                text_color = "#FFD700"
                                                )
                                                n_label.pack(side = "top", anchor = "w", padx = 10, pady =(4, 0))

                                                empty_n = customtkinter.CTkLabel(n_frame, text = f"(empty - accepts: {n_slot})", anchor = 'w', text_color = 'gray', font = customtkinter.CTkFont(size = 9))
                                                empty_n.pack(side = 'top', anchor = 'w', padx = 10, pady =(0, 4))
                                            except Exception:
                                                logging.exception("Suppressed exception")
                                except Exception:
                                    logging.exception("Suppressed exception")
                else:

                    try:
                        conflict_sources = _get_conflict_sources(slot)
                    except Exception:
                        conflict_sources =[]

                    try:
                        conflict_item = _find_any_item_with_conflict(slot)
                    except Exception:
                        conflict_item = None

                    if conflict_item:
                        empty_text = f"Conflicts with: {conflict_item}"
                        text_color = "#FF4444"
                    elif conflict_sources:

                        parents =[]
                        for s in conflict_sources:
                            try:
                                parent = s.split('.', 1)[0]if '.'in s else s
                            except Exception:
                                parent = s
                            parents.append(parent)

                        seen = set()
                        uniq_parents =[]
                        for p in parents:
                            if p not in seen:
                                seen.add(p)
                                uniq_parents.append(p)
                        conf_text = ', '.join(uniq_parents)
                        empty_text = f"Conflicts with: {conf_text}"
                        text_color = "#FF4444"
                    else:
                        empty_text = "(empty)"
                        text_color = "gray"

                    empty_label = customtkinter.CTkLabel(
                    slot_frame,
                    text = empty_text,
                    anchor = "w",
                    text_color = text_color
                    )
                    empty_label.pack(side = "top", anchor = "w", padx = 10, pady =(0, 5))

                    def open_equip_candidates(target_slot):

                        candidates =[]

                        for hi, hit in enumerate(save_data.get("hands", {}).get("items", [])):
                            if not isinstance(hit, dict):
                                continue
                            if hit.get("equippable"):
                                slot_field = hit.get("slot")
                                slots = slot_field if isinstance(slot_field, list)else[slot_field]
                                if target_slot in slots:
                                    candidates.append(("hands", hi, hit))

                        equipment = save_data.get("equipment", {})
                        for eq_slot, eq_item in equipment.items():
                            if not eq_item or not isinstance(eq_item, dict):
                                continue

                            if "items"in eq_item and isinstance(eq_item.get("items"), list):
                                for ci, citem in enumerate(eq_item["items"]):
                                    if not isinstance(citem, dict):
                                        continue
                                    if citem.get("equippable"):
                                        slot_field = citem.get("slot")
                                        slots = slot_field if isinstance(slot_field, list)else[slot_field]
                                        if target_slot in slots:
                                            candidates.append((f"equipment.{eq_slot}.items", ci, citem))

                            for ss_idx, subslot_data in enumerate(eq_item.get("subslots", [])or[]):
                                subslot_item = subslot_data.get("current")
                                if subslot_item and isinstance(subslot_item, dict)and "items"in subslot_item:
                                    for ci, citem in enumerate(subslot_item["items"]):
                                        if not isinstance(citem, dict):
                                            continue
                                        if citem.get("equippable"):
                                            slot_field = citem.get("slot")
                                            slots = slot_field if isinstance(slot_field, list)else[slot_field]
                                            if target_slot in slots:
                                                candidates.append((f"equipment.{eq_slot}.subslot.{ss_idx}.items", ci, citem))

                        if not candidates:
                            self._popup_show_info("Equip", f"No equippable items for slot: {target_slot}")
                            return

                        popup = customtkinter.CTkToplevel(self.root)
                        popup.title(f"Equip to {target_slot}")
                        popup.transient(self.root)
                        self._center_popup_on_window(popup, 420, 300)
                        list_frame = customtkinter.CTkScrollableFrame(popup, fg_color = "transparent")
                        list_frame.pack(fill = "both", expand = True, padx = 10, pady = 10)

                        sel_var = customtkinter.StringVar(value = "0")
                        for idx, (loc, iidx, itm)in enumerate(candidates):
                            name = itm.get("name", "Unknown")
                            lab = customtkinter.CTkLabel(list_frame, text = f"{name} - {loc}")
                            lab.pack(anchor = "w", pady = 4)
                            rb = customtkinter.CTkRadioButton(list_frame, text = "", variable = sel_var, value = str(idx))
                            rb.pack(anchor = "e")

                        def do_equip():
                            sel = int(sel_var.get())
                            loc, iidx, itm = candidates[sel]
                            popup.destroy()
                            equip_item(loc, iidx, itm)

                        btn_frame = customtkinter.CTkFrame(popup, fg_color = "transparent")
                        btn_frame.pack(fill = "x", padx = 10, pady = 8)
                        customtkinter.CTkButton(btn_frame, text = "Equip Selected", command = do_equip, width = 140).pack(side = "left", padx = 6)
                        customtkinter.CTkButton(btn_frame, text = "Cancel", command = popup.destroy, width = 120).pack(side = "right", padx = 6)

                    equip_slot_btn = self._create_sound_button(
                    slot_frame,
                    "Equip",
                    lambda s = slot:open_equip_candidates(s),
                    width = 80,
                    height = 30,
                    state = "disabled"if _slot_blocked_by_subslots(slot)else "normal"
                    )
                    equip_slot_btn.pack(side = "right", padx = 10, pady = 5)

            all_items =[]

            for i, item in enumerate(save_data["hands"].get("items", [])):
                if isinstance(item, dict):
                    is_equippable = item.get("equippable", False)
                    is_firearm = item.get("firearm", False)
                    is_melee = item.get("melee", False)
                    if is_equippable or is_firearm or is_melee:
                        all_items.append(("hands", i, item))

            equipment = save_data.get("equipment", {})

            def _collect_from_obj(loc_prefix, obj):
                try:
                    if isinstance(obj, dict):

                        if "items"in obj and isinstance(obj.get("items"), list):
                            for ci, citem in enumerate(obj.get("items")or[]):
                                if not isinstance(citem, dict):
                                    continue
                                is_equippable = citem.get("equippable", False)
                                is_firearm = citem.get("firearm", False)
                                is_melee = citem.get("melee", False)
                                if is_equippable or is_firearm or is_melee:
                                    all_items.append((f"{loc_prefix}.items", ci, citem))

                        for ss_idx, subslot_data in enumerate(obj.get("subslots")or[]):
                            try:
                                subcur = subslot_data.get("current")
                                if isinstance(subcur, dict):
                                    _collect_from_obj(f"{loc_prefix}.subslot.{ss_idx}", subcur)
                            except Exception:
                                logging.exception("Suppressed exception")

                        for list_idx, lst_item in enumerate(obj.get("items")or[]):
                            try:
                                if isinstance(lst_item, dict):
                                    _collect_from_obj(f"{loc_prefix}.list.{list_idx}", lst_item)
                            except Exception:
                                logging.exception("Suppressed exception")

                    elif isinstance(obj, list):
                        for idx, sub in enumerate(obj):
                            try:
                                if isinstance(sub, dict):
                                    _collect_from_obj(f"{loc_prefix}.list.{idx}", sub)
                            except Exception:
                                logging.exception("Suppressed exception")
                except Exception:
                    logging.exception("Suppressed exception")

            for eq_slot, eq_item in equipment.items():
                try:
                    if eq_item is None:
                        continue
                    _collect_from_obj(f"equipment.{eq_slot}", eq_item)
                except Exception:
                    logging.exception("Suppressed exception")

            for location, idx, item in all_items:
                item_frame = customtkinter.CTkFrame(items_scroll)
                item_frame.pack(fill = "x", pady = 2, padx = 5)

                item_name = self._format_item_name(item)

                if item.get("equippable"):
                    slots = item.get("slot", [])
                    if not isinstance(slots, list):
                        slots =[slots]
                    slots_text = f"Slots: {', '.join(str(s)for s in slots)}"
                elif item.get("firearm")or item.get("melee"):

                    if item.get("firearm"):
                        weapon_type = item.get("subtype", "unknown")
                    else:
                        weapon_type = item.get("type", "unknown")

                    if weapon_type =="pistol":
                        slots_text = "Slots: holster/sling subslots or waistband"
                    else:
                        slots_text = f"Slots: holster/sling subslots(type: {weapon_type})"
                else:
                    slots_text = "Slots: unknown"

                item_label = customtkinter.CTkLabel(
                item_frame,
                text = f"{item_name}\n {slots_text}",
                anchor = "w",
                font = customtkinter.CTkFont(size = 11)
                )
                item_label.pack(side = "left", padx = 10, pady = 5)

                equip_button = self._create_sound_button(
                item_frame,
                "Equip",
                lambda loc = location, i = idx, itm = item:equip_item(loc, i, itm),
                width = 80,
                height = 30
                )
                equip_button.pack(side = "right", padx = 10, pady = 5)

            if not all_items:
                empty_label = customtkinter.CTkLabel(items_scroll, text = "No equippable items available", text_color = "gray")
                empty_label.pack(pady = 20)

        def equip_item(location, item_idx, item):
            try:
                equipment = save_data.get("equipment", {})

                choices = []

                def add_choice(label, slot = None, parent_slot = None, subslot = None):
                    choices.append({"label": label, "slot": slot, "parent_slot": parent_slot, "subslot": subslot})

                def _resolve_conflict_slots(conflicts):
                    out = []
                    try:
                        if isinstance(conflicts, dict):
                            slot_field = conflicts.get('slot')
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

                is_weapon = item.get("firearm", False)or item.get("melee", False)

                if is_weapon:
                    weapon_subtype = item.get("subtype", "unknown")
                    weapon_melee_type = item.get("type")if item.get("melee")else None

                    def _slot_blocked_by_subslots(slot_name):
                        try:
                            slot_name_l = str(slot_name).lower() if slot_name is not None else ''
                            for other_slot, other_item in equipment.items():
                                if not other_item or not isinstance(other_item, dict):
                                    continue

                                for subslot_data in other_item.get('subslots', []) or []:
                                    try:
                                        conflicts = subslot_data.get('conflicts_with')
                                        cur = subslot_data.get('current')
                                        if not cur:
                                            continue
                                        targets = _resolve_conflict_slots(conflicts)
                                        for conflict_slot in targets:
                                            if str(conflict_slot).lower() == slot_name_l:
                                                return True
                                    except Exception:
                                        logging.exception("Suppressed exception")

                                for acc in other_item.get('accessories', []) or []:
                                    try:
                                        curacc = acc.get('current')
                                        if not isinstance(curacc, dict):
                                            continue
                                        for subslot_data in curacc.get('subslots', []) or []:
                                            try:
                                                conflicts = subslot_data.get('conflicts_with')
                                                cur = subslot_data.get('current')
                                                if not cur:
                                                    continue
                                                targets = _resolve_conflict_slots(conflicts)
                                                for conflict_slot in targets:
                                                    if str(conflict_slot).lower() == slot_name_l:
                                                        return True
                                            except Exception:
                                                logging.exception("Suppressed exception")
                                    except Exception:
                                        logging.exception("Suppressed exception")

                                try:
                                    item_conflicts = other_item.get('conflicts_with')
                                    if item_conflicts:
                                        targets = _resolve_conflict_slots(item_conflicts)
                                        for conflict_slot in targets:
                                            if str(conflict_slot).lower() == slot_name_l:
                                                return True
                                except Exception:
                                    logging.exception("Suppressed exception")
                            return False
                        except Exception:
                            return False

                    if weapon_subtype =="pistol"and "waistband"in equipment and equipment["waistband"]is None and not _slot_blocked_by_subslots("waistband"):
                        add_choice("Waistband", slot = "waistband")

                    def _check_holster_sling(equipped_item, parent_slot, label_prefix = None):
                        if not isinstance(equipped_item, dict) or not equipped_item.get("holster_sling", False):
                            return
                        compatible_types = equipped_item.get("weapon_types", [])
                        if weapon_subtype in compatible_types or weapon_melee_type in compatible_types:
                            for subslot_data in equipped_item.get("subslots", []):
                                if subslot_data.get("slot") != "weapon_slot" or subslot_data.get("current") is not None:
                                    continue
                                conflicts = subslot_data.get("conflicts_with")
                                blocked = False
                                if conflicts:
                                    targets = _resolve_conflict_slots(conflicts)
                                    for conflict_slot in targets:
                                        if conflict_slot in equipment and equipment.get(conflict_slot) is not None:
                                            blocked = True
                                            break
                                if blocked:
                                    continue
                                lbl = label_prefix or parent_slot.title()
                                label = f"{lbl} - {subslot_data.get('name', 'Weapon Slot')}"
                                add_choice(label, parent_slot = parent_slot, subslot = subslot_data)

                    for parent_slot, equipped_item in equipment.items():
                        if isinstance(equipped_item, dict):
                            _check_holster_sling(equipped_item, parent_slot)
                            for ss in equipped_item.get("subslots", [])or[]:
                                cur = ss.get("current")
                                if isinstance(cur, dict)and cur.get("holster_sling", False):
                                    _check_holster_sling(cur, parent_slot, label_prefix = f"{parent_slot.title()} - {ss.get('name', 'Subslot')}")

                    if not choices:
                        if weapon_subtype =="pistol":
                            self._popup_show_info("Error", "No available holster/sling or waistband slot for this pistol.", sound = "error")
                        else:
                            self._popup_show_info("Error", f"No available holster/sling slot for this weapon(type: {weapon_subtype or weapon_melee_type}).", sound = "error")
                        return

                else:

                    valid_slots = item.get("slot", [])
                    if not isinstance(valid_slots, list):
                        valid_slots =[valid_slots]

                    def _slot_blocked_by_subslots(slot_name):
                        try:
                            slot_name_l = str(slot_name).lower() if slot_name is not None else ''
                            for other_slot, other_item in equipment.items():
                                if not other_item or not isinstance(other_item, dict):
                                    continue
                                for subslot_data in other_item.get('subslots', []) or []:
                                    try:
                                        conflicts = subslot_data.get('conflicts_with')
                                        cur = subslot_data.get('current')
                                        if not cur:
                                            continue
                                        targets = _resolve_conflict_slots(conflicts)
                                        for conflict_slot in targets:
                                            if str(conflict_slot).lower() == slot_name_l:
                                                return True
                                    except Exception:
                                        logging.exception("Suppressed exception")
                                for acc in other_item.get('accessories', []) or []:
                                    try:
                                        curacc = acc.get('current')
                                        if not isinstance(curacc, dict):
                                            continue
                                        for subslot_data in curacc.get('subslots', []) or []:
                                            try:
                                                conflicts = subslot_data.get('conflicts_with')
                                                cur = subslot_data.get('current')
                                                if not cur:
                                                    continue
                                                targets = _resolve_conflict_slots(conflicts)
                                                for conflict_slot in targets:
                                                    if str(conflict_slot).lower() == slot_name_l:
                                                        return True
                                            except Exception:
                                                logging.exception("Suppressed exception")
                                    except Exception:
                                        logging.exception("Suppressed exception")

                                try:
                                    item_conflicts = other_item.get('conflicts_with')
                                    if item_conflicts:
                                        targets = _resolve_conflict_slots(item_conflicts)
                                        for conflict_slot in targets:
                                            if str(conflict_slot).lower() == slot_name_l:
                                                return True
                                except Exception:
                                    logging.exception("Suppressed exception")
                            return False
                        except Exception:
                            return False

                    def _item_own_conflicts_occupied():
                        try:
                            own_conflicts = item.get('conflicts_with', [])
                            if not own_conflicts:
                                return False
                            targets = _resolve_conflict_slots(own_conflicts)
                            for ct in targets:
                                ct_l = str(ct).lower()
                                for sk, sv in equipment.items():
                                    if str(sk).lower() == ct_l and sv is not None:
                                        return True
                                for _, eq_oi in equipment.items():
                                    if not isinstance(eq_oi, dict):
                                        continue
                                    for ss in eq_oi.get('subslots', []) or []:
                                        if str(ss.get('slot', '')).lower() == ct_l and ss.get('current') is not None:
                                            return True
                            return False
                        except Exception:
                            return False

                    _own_conflict_blocked = _item_own_conflicts_occupied()

                    for slot in valid_slots:
                        cur = equipment.get(slot)

                        if slot in equipment and cur is None:

                            if _slot_blocked_by_subslots(slot) or _own_conflict_blocked:
                                continue
                            add_choice(f"{slot.title()}", slot = slot)
                        else:

                            try:
                                if item.get('can_equip_multiple'):
                                    max_e = item.get('max_equip')

                                    count = 0
                                    if isinstance(cur, dict)and cur.get('id')==item.get('id'):
                                        count = 1
                                    elif isinstance(cur, list):

                                        same =[c for c in cur if isinstance(c, dict)and c.get('id')==item.get('id')]
                                        count = len(same)

                                    if max_e is None or(isinstance(max_e, int)and count <int(max_e)):

                                        allow = False
                                        if cur is None:
                                            allow = True
                                        elif isinstance(cur, dict)and cur.get('id')==item.get('id'):
                                            allow = True
                                        elif isinstance(cur, list)and all(isinstance(c, dict)and c.get('id')==item.get('id')for c in cur):
                                            allow = True
                                        if allow:
                                            lbl = f"{slot.title()}"
                                            if count >0:
                                                lbl = f"{lbl}(x{count})"
                                            add_choice(lbl, slot = slot)
                            except Exception:
                                logging.exception("Suppressed exception")

                    def _recurse_find_subslots(root_slot, container, label_prefix = None):
                        try:
                            if not container or not isinstance(container, dict):
                                return
                            for subslot_data in container.get('subslots', []) or []:
                                try:
                                    subslot_type = subslot_data.get('slot', '')

                                    lbl_suffix = subslot_data.get('name', subslot_type)
                                    label = f"{root_slot.title()} - {lbl_suffix}" if not label_prefix else f"{label_prefix} -> {lbl_suffix}"

                                    if subslot_type in valid_slots and subslot_data.get('current') is None:
                                        conflicts = subslot_data.get('conflicts_with')
                                        blocked = False
                                        if conflicts:
                                            targets = _resolve_conflict_slots(conflicts)
                                            for conflict_slot in targets:
                                                if conflict_slot in equipment and equipment.get(conflict_slot) is not None:
                                                    blocked = True
                                                    break
                                        if not blocked and not _own_conflict_blocked:
                                            add_choice(label, parent_slot = root_slot, subslot = subslot_data)

                                    cur = subslot_data.get('current')
                                    if isinstance(cur, dict):
                                        _recurse_find_subslots(root_slot, cur, label_prefix = label)
                                except Exception:
                                    logging.exception("Suppressed exception")
                        except Exception:
                            logging.exception("Suppressed exception")

                    for parent_slot, equipped_item in equipment.items():
                        if isinstance(equipped_item, dict):
                            _recurse_find_subslots(parent_slot, equipped_item)
                        elif isinstance(equipped_item, list):
                            for idx, subitem in enumerate(equipped_item):
                                _recurse_find_subslots(parent_slot, subitem, label_prefix = f"{parent_slot.title()}#{idx}")

                    def _recurse_accessory_subslots(root_slot, accessory, label_prefix = None):
                        try:
                            cur = accessory.get('current')if isinstance(accessory, dict)else None
                            if not isinstance(cur, dict):
                                return

                            _recurse_find_subslots(root_slot, cur, label_prefix = label_prefix or f"{root_slot.title()} - {accessory.get('name', 'Accessory')}")
                        except Exception:
                            logging.exception("Suppressed exception")

                    for parent_slot, equipped_item in equipment.items():
                        if isinstance(equipped_item, dict)and isinstance(equipped_item.get('accessories'), list):
                            for acc in equipped_item.get('accessories')or[]:
                                try:
                                    _recurse_accessory_subslots(parent_slot, acc)
                                except Exception:
                                    logging.exception("Suppressed exception")

                    if not choices:
                        self._popup_show_info("Error", f"No available slots for this item.Valid slots: {', '.join(valid_slots)}", sound = "error")
                        return

                def apply_choice(choice):
                    def _take_one_from_list(lst, idx):
                        try:
                            import copy as _copy
                            if not isinstance(lst, list):
                                return None
                            if idx is None or not(0 <=int(idx)<len(lst)):
                                return None
                            it = lst[int(idx)]
                            if isinstance(it, dict):
                                qty = it.get('quantity')
                                if isinstance(qty, (int, float))and qty >1:

                                    try:
                                        it['quantity']= int(qty)-1
                                    except Exception:
                                        logging.exception("Suppressed exception")
                                    single = _copy.deepcopy(it)
                                    single['quantity']= 1
                                    return single

                            try:
                                return lst.pop(int(idx))
                            except Exception:
                                try:

                                    val = lst[int(idx)]
                                    lst[int(idx)]= None
                                    return val
                                except Exception:
                                    return None
                        except Exception:
                            return None

                    if location =="storage":
                        removed_item = _take_one_from_list(save_data["storage"], item_idx)
                    elif location =="hands":
                        removed_item = _take_one_from_list(save_data["hands"]["items"], item_idx)
                        item_weight =(removed_item.get("weight", 0)*removed_item.get("quantity", 1))if isinstance(removed_item, dict)else 0
                        save_data["hands"]["encumbrance"]= max(0, save_data["hands"].get("encumbrance", 0)-item_weight)
                    elif location.startswith("equipment."):

                        parts = location.split('.')
                        removed_item = item
                        try:
                            eq_slot = parts[1]
                            cur = save_data.get('equipment', {}).get(eq_slot)
                            i = 2
                            while i <len(parts):
                                token = parts[i]
                                if token =='items':

                                    if isinstance(cur, dict)and 'items'in cur:
                                        removed_item = _take_one_from_list(cur['items'], item_idx)
                                    elif isinstance(cur, list):
                                        removed_item = _take_one_from_list(cur, item_idx)
                                    else:
                                        removed_item = item
                                    break
                                elif token =='subslot':

                                    idx = int(parts[i +1])if i +1 <len(parts)else None
                                    if idx is None:
                                        removed_item = item
                                        break
                                    if isinstance(cur, dict)and 'subslots'in cur and idx <len(cur['subslots']):
                                        cur = cur['subslots'][idx].get('current')
                                        if cur is None:
                                            removed_item = item
                                            break
                                        i +=2
                                        continue
                                    else:
                                        removed_item = item
                                        break
                                elif token =='list':
                                    idx = int(parts[i +1])if i +1 <len(parts)else None
                                    if idx is None:
                                        removed_item = item
                                        break
                                    if isinstance(cur, list)and 0 <=idx <len(cur):
                                        cur = cur[idx]
                                        i +=2
                                        continue
                                    else:
                                        removed_item = item
                                        break
                                else:

                                    removed_item = item
                                    break
                        except Exception:
                            removed_item = item
                    else:
                        removed_item = item

                    if choice.get("slot"):
                        slot = choice["slot"]
                        cur = save_data["equipment"].get(slot)

                        if cur is None:
                            save_data["equipment"][slot]= removed_item
                        else:

                            try:
                                if item.get('can_equip_multiple')and item.get('id')is not None:
                                    max_e = item.get('max_equip')

                                    if isinstance(cur, dict):
                                        if cur.get('id')==item.get('id'):
                                            lst =[cur, removed_item]
                                            save_data["equipment"][slot]= lst
                                        else:

                                            save_data["equipment"][slot]= removed_item
                                    elif isinstance(cur, list):

                                        same =[c for c in cur if isinstance(c, dict)and c.get('id')==item.get('id')]
                                        if len(same)==len(cur):

                                            if max_e is None or len(cur)<int(max_e):
                                                cur.append(removed_item)
                                                save_data["equipment"][slot]= cur
                                            else:
                                                self._popup_show_info("Equip", f"Cannot equip more than {max_e} of this item into slot '{slot}'.", sound = "error")
                                                return
                                        else:

                                            save_data["equipment"][slot]= removed_item
                                    else:
                                        save_data["equipment"][slot]= removed_item
                                else:

                                    save_data["equipment"][slot]= removed_item
                            except Exception:
                                save_data["equipment"][slot]= removed_item
                    elif choice.get("subslot")is not None:
                        choice["subslot"]["current"]= removed_item

                    self._save_file(save_data)
                    try:
                        globals()['ATTACHMENTS_VERSION']= globals().get('ATTACHMENTS_VERSION', 0)+1
                    except Exception:
                        logging.exception("Suppressed exception")
                    refresh_display()

                    try:
                        played = False

                        if choice.get("slot")=="waistband":
                            logging.debug("Playing slingequip for waistband equip: sounds/firearms/universal/slingequip.ogg")

                            self._safe_sound_play("", "sounds/firearms/universal/slingequip.ogg", block = False)
                            played = True
                        elif choice.get("parent_slot"):
                            parent = save_data.get("equipment", {}).get(choice.get("parent_slot"))
                            if parent and isinstance(parent, dict):
                                pname = parent.get("name", "").lower()
                                ptypes =[pt.lower()for pt in parent.get("weapon_types", [])if isinstance(pt, str)]

                                if "pistol"in ptypes or "holster"in pname:
                                    logging.debug("Playing holsterequip for holster equip: sounds/firearms/universal/holsterequip.ogg")

                                    self._safe_sound_play("", "sounds/firearms/universal/holsterequip.ogg", block = False)
                                    played = True
                                else:
                                    logging.debug("Playing slingequip for sling equip: sounds/firearms/universal/slingequip.ogg")
                                    self._safe_sound_play("", "sounds/firearms/universal/slingequip.ogg", block = False)
                                    played = True
                        if not played:

                            self._play_ui_sound("success")
                    except Exception:
                        try:
                            self._play_ui_sound("success")
                        except Exception:
                            logging.exception("Suppressed exception")

                    try:
                        logging.debug("apply_choice: about to play per-item equip sound for %s", removed_item.get("name"))
                        self._play_firearm_sound(removed_item, "equip")
                    except Exception:
                        logging.exception("Failed to play per-item equip sound")

                if len(choices)==1:
                    apply_choice(choices[0])
                    return

                popup = customtkinter.CTkToplevel(self.root)
                popup.title("Select Slot")
                popup.transient(self.root)
                self._center_popup_on_window(popup, 360, 200)

                prompt_label = customtkinter.CTkLabel(popup, text = "Choose where to equip:", font = customtkinter.CTkFont(size = 14, weight = "bold"))
                prompt_label.pack(pady =(15, 10))

                choice_labels =[c["label"]for c in choices]
                selection = customtkinter.StringVar(value = choice_labels[0])

                choice_menu = customtkinter.CTkOptionMenu(popup, values = choice_labels, variable = selection)
                choice_menu.pack(pady = 10, padx = 20, fill = "x")

                def _on_equip_selection_change(*a):
                    try:
                        label = selection.get()
                        chosen = next((c for c in choices if c["label"]==label), None)
                        if not chosen:
                            return

                        if chosen.get("slot")=="waistband":
                            self._safe_sound_play("", "sounds/firearms/universal/slingequip.ogg")
                        elif chosen.get("parent_slot"):
                            parent = save_data.get("equipment", {}).get(chosen.get("parent_slot"))
                            if parent and isinstance(parent, dict):
                                pname = parent.get("name", "").lower()
                                ptypes =[pt.lower()for pt in parent.get("weapon_types", [])if isinstance(pt, str)]
                                if "pistol"in ptypes or "holster"in pname:
                                    self._safe_sound_play("", "sounds/firearms/universal/holsterequip.ogg")
                                else:
                                    self._safe_sound_play("", "sounds/firearms/universal/slingequip.ogg")
                        else:

                            try:
                                self._play_ui_sound("hover")
                            except Exception:
                                logging.exception("Suppressed exception")
                    except Exception:
                        logging.exception("Suppressed exception")

                try:

                    selection.trace_add("write", _on_equip_selection_change)
                except Exception:
                    try:
                        selection.trace("w", lambda *a:_on_equip_selection_change())
                    except Exception:
                        logging.exception("Suppressed exception")

                button_frame = customtkinter.CTkFrame(popup, fg_color = "transparent")
                button_frame.pack(pady = 15)

                def confirm_choice():
                    label = selection.get()
                    chosen = next((c for c in choices if c["label"]==label), None)
                    if chosen:
                        apply_choice(chosen)
                    popup.destroy()

                def cancel_choice():
                    popup.destroy()

                confirm_btn = self._create_sound_button(button_frame, "Equip", confirm_choice, width = 120, height = 35)
                confirm_btn.pack(side = "left", padx = 10)

                cancel_btn = self._create_sound_button(button_frame, "Cancel", cancel_choice, width = 120, height = 35)
                cancel_btn.pack(side = "left", padx = 10)

                popup.grab_set()
                popup.lift()
                self._safe_focus(popup)
            except Exception as e:
                logging.error(f"Equip failed: {e}")
                self._popup_show_info("Error", f"Equip failed: {e}", sound = "error")

        def unequip_item(slot):
            try:
                item = save_data["equipment"].get(slot)
                if not item:
                    return

                if isinstance(item, dict)and item.get("curse_of_binding"):
                    self._popup_show_info("Curse of Binding", f"{item.get('name', 'This item')} is bound and cannot be unequipped.", sound = "error")
                    return
                if isinstance(item, list):
                    last_item = item[-1]if item else None
                    if isinstance(last_item, dict)and last_item.get("curse_of_binding"):
                        self._popup_show_info("Curse of Binding", f"{last_item.get('name', 'This item')} is bound and cannot be unequipped.", sound = "error")
                        return

                played = False
                try:
                    if slot =="waistband":
                        logging.debug("Playing slingunequip for waistband unequip: sounds/firearms/universal/slingunequip.ogg")

                        self._safe_sound_play("", "sounds/firearms/universal/slingunequip.ogg", block = True)
                        played = True
                    else:
                        parent = save_data.get("equipment", {}).get(slot)
                        if parent and isinstance(parent, dict):
                            pname = parent.get("name", "").lower()
                            ptypes =[pt.lower()for pt in parent.get("weapon_types", [])if isinstance(pt, str)]
                            if "pistol"in ptypes or "holster"in pname:
                                logging.debug("Playing holsterunequip: sounds/firearms/universal/holsterunequip.ogg")
                                self._safe_sound_play("", "sounds/firearms/universal/holsterunequip.ogg", block = True)
                                played = True
                            elif parent.get("holster_sling"):
                                logging.debug("Playing slingunequip: sounds/firearms/universal/slingunequip.ogg")
                                self._safe_sound_play("", "sounds/firearms/universal/slingunequip.ogg", block = True)
                                played = True
                except Exception:
                    played = False

                if isinstance(item, list):
                    rem = item.pop()
                    save_data["hands"]["items"].append(rem)
                    if len(item)==1 and isinstance(item[0], dict):

                        save_data["equipment"][slot]= item[0]
                    elif len(item)==0:
                        save_data["equipment"][slot]= None
                    else:
                        save_data["equipment"][slot]= item
                else:
                    save_data["hands"]["items"].append(item)
                    save_data["equipment"][slot]= None

                self._save_file(save_data)

                refresh_display()
                if not played:
                    self._play_ui_sound("success")
            except Exception as e:
                logging.error(f"Unequip failed: {e}")
                self._popup_show_info("Error", f"Unequip failed: {e}", sound = "error")

        def unequip_from_subslot(parent_slot, subslot_data, subindex = None):
            try:

                if subindex is not None:
                    try:
                        nested = subslot_data.get('subslots')or[]
                        if 0 <=int(subindex)<len(nested):
                            target = nested[int(subindex)]
                            current_item = target.get('current')
                            target_key = target
                        else:
                            current_item = None
                            target_key = None
                    except Exception:
                        current_item = None
                        target_key = None
                else:
                    current_item = subslot_data.get("current")
                    target_key = subslot_data
                if not current_item:
                    return

                if isinstance(current_item, dict)and current_item.get("curse_of_binding"):
                    self._popup_show_info("Curse of Binding", f"{current_item.get('name', 'This item')} is bound and cannot be unequipped.", sound = "error")
                    return

                played = False
                try:
                    parent = save_data.get("equipment", {}).get(parent_slot)
                    if parent and isinstance(parent, dict):
                        pname = parent.get("name", "").lower()
                        ptypes =[pt.lower()for pt in parent.get("weapon_types", [])if isinstance(pt, str)]
                        if parent_slot =="waistband"or(parent.get("holster_sling")and any(pt in("rifle", "smg", "shotgun", "mg")for pt in ptypes)):

                            self._safe_sound_play("", "sounds/firearms/universal/slingunequip.ogg", block = True)
                            played = True
                        else:

                            if "pistol"in ptypes or "holster"in pname:
                                self._safe_sound_play("", "sounds/firearms/universal/holsterunequip.ogg", block = True)
                                played = True
                except Exception:
                    played = False

                try:
                    if not isinstance(current_item, dict)and(isinstance(current_item, int)or(isinstance(current_item, str)and current_item.isdigit())):
                        iid = int(current_item)

                        table_files = sorted(glob.glob(os.path.join("tables", f"*{global_variables.get('table_extension', '.sldtbl')}")))
                        for tf in table_files:
                            try:
                                with open(tf, 'r', encoding = 'utf-8')as f:
                                    td = json.load(f)
                            except Exception:
                                logging.exception("Suppressed exception")
                                continue
                            for arr in td.get('tables', {}).values():
                                if isinstance(arr, list):
                                    for cand in arr:
                                        if isinstance(cand, dict)and cand.get('id')==iid:
                                            current_item = cand.copy()
                                            break
                                    if isinstance(current_item, dict):
                                        break
                            if isinstance(current_item, dict):
                                break
                except Exception:
                    logging.exception("Suppressed exception")

                save_data["hands"]["items"].append(current_item)
                try:
                    if subindex is not None and target_key is not None:
                        target_key['current']= None
                    else:
                        subslot_data["current"]= None
                except Exception:
                    try:
                        subslot_data["current"]= None
                    except Exception:
                        logging.exception("Suppressed exception")

                self._save_file(save_data)

                refresh_display()
                if not played:
                    self._play_ui_sound("success")
            except Exception as e:
                logging.error(f"Unequip from subslot failed: {e}")
                self._popup_show_info("Error", f"Unequip failed: {e}", sound = "error")

        def view_container_contents(container_item):
            try:
                self._play_ui_sound("click")

                popup = customtkinter.CTkToplevel(self.root)
                popup.title(f"Container: {self._format_item_name(container_item)}")
                popup.transient(self.root)
                self._center_popup_on_window(popup, 500, 600)

                main_container = customtkinter.CTkFrame(popup)
                main_container.pack(fill = "both", expand = True, padx = 20, pady = 20)

                title = customtkinter.CTkLabel(
                main_container,
                text = container_item.get('name', 'Unknown Container'),
                font = customtkinter.CTkFont(size = 18, weight = "bold")
                )
                title.pack(pady =(0, 10))

                total_weight = sum(i.get("weight", 0)*i.get("quantity", 1)for i in container_item.get("items", []))
                capacity = container_item.get("capacity", 0)
                capacity_label = customtkinter.CTkLabel(
                main_container,
                text = f"Capacity: {self._format_weight(total_weight)} / {self._format_weight(capacity)}",
                font = customtkinter.CTkFont(size = 14)
                )
                capacity_label.pack(pady =(0, 15))

                items_frame = customtkinter.CTkScrollableFrame(main_container, height = 400)
                items_frame.pack(fill = "both", expand = True, pady =(0, 10))

                items = container_item.get("items", [])
                if items:
                    for i, item in enumerate(items):
                        item_frame = customtkinter.CTkFrame(items_frame)
                        item_frame.pack(fill = "x", pady = 3, padx = 5)

                        item_name = self._format_item_name(item)
                        quantity = item.get("quantity", 1)
                        weight = item.get("weight", 0)

                        info_text = f"{item_name}"
                        if quantity >1:
                            info_text +=f"(x{quantity})"
                        info_text +=f" - {self._format_weight(weight *quantity)}"

                        item_label = customtkinter.CTkLabel(
                        item_frame,
                        text = info_text,
                        anchor = "w"
                        )
                        item_label.pack(side = "left", padx = 10, pady = 5, fill = "x", expand = True)
                else:
                    empty_label = customtkinter.CTkLabel(
                    items_frame,
                    text = "Container is empty",
                    text_color = "gray"
                    )
                    empty_label.pack(pady = 20)

                close_button = self._create_sound_button(
                main_container,
                "Close",
                popup.destroy,
                width = 120,
                height = 35
                )
                close_button.pack(pady =(10, 0))

                popup.update_idletasks()
                popup.grab_set()
                popup.lift()
                self._safe_focus(popup)
            except Exception as e:
                logging.error(f"View container failed: {e}")
                self._popup_show_info("Error", f"Failed to view container: {e}", sound = "error")

        refresh_display()

        back_button = self._create_sound_button(
        main_frame,
        "Back",
        lambda:[self._clear_window(), self._open_inventory_manager_tool()],
        width = 200,
        height = 40
        )
        back_button.pack(pady = 10)
