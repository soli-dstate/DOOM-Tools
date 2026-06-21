"""InspectMixin — App methods for the "inspect" feature area."""
from app.foundation import *
import logging


class InspectMixin:

    def _open_shop_item_inspect(self, item, buy_price, table_data, current_store=None, on_test_purchase=None):
        """Show a popup with detailed inspection info for a shop item."""
        base_value = item.get("value", 0) or 0

        # --- Cross-shop price comparison ---
        cheaper_stores = []  # list of (store_name, price)
        try:
            item_id = item.get("id")
            item_name = item.get("name", "")
            current_store_name = (current_store or {}).get("name", "")
            all_stores = (table_data or {}).get("tables", {}).get("stores", []) or []
            other_stores = [s for s in all_stores if isinstance(s, dict)
                            and s.get("type") == "store"
                            and s.get("name", "") != current_store_name]
            other_demand = _get_market_demand()
            tables = (table_data or {}).get("tables", {})
            for other_store in other_stores:
                other_sell_mult = other_store.get("prices", {}).get("sell", 1.0)
                for inv_entry in (other_store.get("inventory") or []):
                    matches = []
                    if inv_entry.get("type") == "table":
                        tname = inv_entry.get("table")
                        for candidate in (tables.get(tname) or []):
                            if not isinstance(candidate, dict):
                                continue
                            if (item_id and candidate.get("id") == item_id) or \
                               (item_name and candidate.get("name", "") == item_name):
                                matches.append(candidate)
                    elif inv_entry.get("type") == "id":
                        eid = inv_entry.get("id")
                        if (item_id and eid == item_id) or (item_name and eid == item_name):
                            for tname, titems in tables.items():
                                if isinstance(titems, list):
                                    for candidate in titems:
                                        if isinstance(candidate, dict) and candidate.get("id") == eid:
                                            matches.append(candidate)
                                            break
                    for match in matches:
                        match_copy = match.copy()
                        match_copy.setdefault("_table_category", inv_entry.get("table", ""))
                        raw_other_price = ((match_copy.get("value", 0) or 0)
                                           * other_sell_mult
                                           * _get_item_market_multiplier(match_copy, other_demand))
                        other_price = round(raw_other_price, 2)
                        if str(match_copy.get("_table_category", "")).lower() == "ammunition" and raw_other_price > 0 and other_price < 0.01:
                            other_price = 0.01
                        if other_price < buy_price:
                            cheaper_stores.append((other_store.get("name", "Unknown"), other_price))
                        break  # one match per store is enough
        except Exception:
            logging.exception("Suppressed exception")
        cheaper_stores.sort(key=lambda x: x[1])

        popup_height = 420 + (len(cheaper_stores) > 0) * 60 + len(cheaper_stores) * 26
        popup = customtkinter.CTkToplevel(self.root)
        popup.title(f"Inspect: {self._format_item_name(item)}")
        popup.transient(self.root)
        popup.grab_set()
        popup.withdraw()
        self._center_popup_on_window(popup, 620, popup_height)

        frame = customtkinter.CTkFrame(popup, fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=20, pady=16)

        customtkinter.CTkLabel(
            frame,
            text=self._format_item_name(item),
            font=customtkinter.CTkFont(size=15, weight="bold"),
            wraplength=560, justify="center"
        ).pack(pady=(0, 14))

        def add_row(label, value_text, value_color="white"):
            row = customtkinter.CTkFrame(frame, fg_color="transparent")
            row.pack(fill="x", pady=2)
            customtkinter.CTkLabel(
                row, text=label,
                font=customtkinter.CTkFont(size=12), text_color="gray",
                anchor="w", width=150
            ).pack(side="left")
            customtkinter.CTkLabel(
                row, text=value_text,
                font=customtkinter.CTkFont(size=12), text_color=value_color,
                anchor="w"
            ).pack(side="left", padx=(8, 0))

        depreciated_value = _get_depreciated_item_value(base_value, item)

        add_row("Base Value:", format_price(float(base_value)))
        add_row("Depreciated Value:", format_price(float(depreciated_value)))
        add_row("Shop Price:", format_price(float(buy_price)))

        compare_value = float(depreciated_value)
        if compare_value > 0:
            diff = buy_price - compare_value
            diff_pct = (diff / compare_value) * 100
            if diff > 0:
                diff_str = f"+{format_price(float(diff))}  (+{diff_pct:.0f}%)"
                diff_color = "#ff6644"
            elif diff < 0:
                diff_str = f"-{format_price(float(abs(diff)))}  ({diff_pct:.0f}%)"
                diff_color = "#44cc44"
            else:
                diff_str = "At depreciated value"
                diff_color = "gray"
        else:
            diff_str = "N/A"
            diff_color = "gray"
        add_row("Price vs Value:", diff_str, diff_color)

        if item.get("firearm"):
            rf = item.get("rounds_fired")
            firearm_state = "New (unissued)"
            firearm_state_color = "#44cc44"
            if rf is not None:
                try:
                    rf_int = int(rf)
                    add_row("Rounds Fired:", f"{rf_int:,}")
                    if rf_int > 0:
                        firearm_state = "Used"
                        firearm_state_color = "#ffaa44"
                except (ValueError, TypeError):
                    add_row("Rounds Fired:", str(rf))
                    firearm_state = "Used"
                    firearm_state_color = "#ffaa44"
            else:
                add_row("Rounds Fired:", "New (unissued)", "#888888")

            add_row("State:", firearm_state, firearm_state_color)

            if _is_new_historical_firearm(item):
                add_row("Premium:", "Historical Premium x25", "#FFD700")
                add_row("Testing:", "Unavailable for new historical firearms", "#FFD700")

            cond_text, cond_color = _get_weapon_condition_label(item)
            add_row("Condition:", cond_text, cond_color)

        if cheaper_stores:
            customtkinter.CTkLabel(
                frame,
                text="Cheaper elsewhere:",
                font=customtkinter.CTkFont(size=11, weight="bold"),
                text_color="#aaddff",
                anchor="w"
            ).pack(fill="x", pady=(12, 2))
            for sname, sprice in cheaper_stores:
                saving = buy_price - sprice
                add_row(f"  {sname}:", f"{format_price(sprice)}  (save {format_price(saving)})", "#44cc44")

        btn_row = customtkinter.CTkFrame(frame, fg_color = "transparent")
        btn_row.pack(pady = (18, 0))

        if item.get("firearm"):
            try:
                _trf = item.get("rounds_fired")
                _t_is_new = (_trf is None or int(_trf or 0) == 0)
            except Exception:
                _t_is_new = True
            _t_historical_blocked = _is_new_historical_firearm(item)
            try:
                _t_bp = float(buy_price or 0)
            except Exception:
                _t_bp = 0.0
            _t_cost = max(25.0, round(_t_bp * 0.04, 2)) if (_t_is_new and _t_bp > 0) else 10.0
            _t_already_used = bool(item.get("_test_used"))
            _t_btn_ref = [None]
            def _on_test_started_cb(ref = _t_btn_ref):
                if ref[0]:
                    try:
                        ref[0].configure(state = "disabled", text = "Already Tested")
                    except Exception:
                        logging.exception("Suppressed exception")
            _t_btn = self._create_sound_button(
                btn_row,
                "Testing Disabled" if _t_historical_blocked else ("Already Tested" if _t_already_used else f"Test Firearm ({format_price(_t_cost)})"),
                lambda: self._start_shop_firearm_test(item, table_data, on_test_purchase = on_test_purchase, buy_price = buy_price, on_test_started = _on_test_started_cb),
                width = 170,
                height = 32,
                font = customtkinter.CTkFont(size = 12),
            )
            if _t_already_used or _t_historical_blocked:
                _t_btn.configure(state = "disabled")
            _t_btn.pack(side = "left", padx = (0, 8))
            _t_btn_ref[0] = _t_btn

        customtkinter.CTkButton(
            btn_row, text = "Close", command = popup.destroy, width = 120
        ).pack(side = "left")

        popup.deiconify()

    def _inspect_item(self, item, location, save_data):
        if item.get("puzzle"):
            self._inspect_puzzle_item(item, location, save_data)
            return

        inspect_path = item.get("inspect")
        if inspect_path:
            self._inspect_image_item(item, inspect_path)
            return

        self._popup_show_info("Inspect", "Nothing to inspect.", sound = "popup")

    def _inspect_image_item(self, item, image_path):
        base_dir = os.path.dirname(__file__)
        full_path = os.path.join(base_dir, image_path)
        if not os.path.exists(full_path):
            self._popup_show_info("Error", "Image file not found.", sound = "error")
            return

        try:
            from PIL import Image
            img = Image.open(full_path)
            w, h = img.size
            max_w, max_h = 800, 800
            if w >max_w or h >max_h:
                ratio = min(max_w /w, max_h /h)
                w, h = int(w *ratio), int(h *ratio)
            ctk_img = customtkinter.CTkImage(light_image = img, dark_image = img, size =(w, h))

            popup = customtkinter.CTkToplevel(self.root)
            popup.title(item.get("name", "Inspect"))
            popup.transient(self.root)
            self._center_popup_on_window(popup, w +40, h +80)
            label = customtkinter.CTkLabel(popup, image = ctk_img, text = "")
            label.pack(padx = 20, pady =(20, 10))
            label._ctk_img_ref = ctk_img
            close_btn = self._create_sound_button(popup, "Close", popup.destroy, width = 100, height = 30)
            close_btn.pack(pady =(0, 15))
            popup.update_idletasks()
            popup.deiconify()
            popup.grab_set()
        except Exception as e:
            logging.error(f"Failed to open inspect image: {e}")
            self._popup_show_info("Error", f"Failed to open image: {e}", sound = "error")

    def _inspect_puzzle_item(self, item, location, save_data):
        try:
            encoded_type = item.get("puzzle_type", "")
            puzzle_type = base64.a85decode(encoded_type).decode()
        except Exception:
            self._popup_show_info("Error", "Unknown puzzle type.", sound = "error")
            return

        if puzzle_type =="off-screen":
            self._inspect_offscreen_puzzle(item, location, save_data)
        else:
            self._popup_show_info("Error", f"Unknown puzzle type.", sound = "error")

    def _inspect_offscreen_puzzle(self, item, location, save_data):
        try:
            code = base64.a85decode(item.get("code", "")).decode()
        except Exception:
            self._popup_show_info("Error", "Failed to read puzzle data.", sound = "error")
            return

        PAPER_W = 612
        PAPER_H = 792
        MARGIN = 40
        FONT_SIZE = 14
        LINE_HEIGHT = 20
        CHAR_WIDTH = 9

        cols =(PAPER_W -2 *MARGIN)//CHAR_WIDTH
        rows =(PAPER_H -2 *MARGIN)//LINE_HEIGHT

        puzzle_state = item.get("_puzzle_state")
        if puzzle_state and puzzle_state.get("grid")and puzzle_state.get("code_positions"):
            grid = puzzle_state["grid"]
            code_positions = puzzle_state["code_positions"]
        else:
            grid =[]
            for r in range(rows):
                row_chars =[]
                for c in range(cols):
                    row_chars.append(str(random.randint(0, 9)))
                grid.append(row_chars)

            total_cells = rows *cols
            code_digits = list(code)
            positions = random.sample(range(total_cells), len(code_digits))
            positions.sort()
            code_positions =[]
            for i, pos in enumerate(positions):
                r = pos //cols
                c = pos %cols
                grid[r][c]= code_digits[i]
                code_positions.append([r, c])

            item["_puzzle_state"]= {"grid":grid, "code_positions":code_positions}

            containers = save_data.get("containers", {})
            if location in containers:
                for idx, it in enumerate(containers[location]):
                    if it is item:
                        containers[location][idx]= item
                        break
            self._save_file(save_data)

        puzzle_window = customtkinter.CTkToplevel(self.root)
        puzzle_window.title(item.get("name", "Inspect"))
        puzzle_window.resizable(False, False)
        puzzle_window.configure(fg_color = "white")

        canvas = _tk.Canvas(
        puzzle_window,
        width = PAPER_W,
        height = PAPER_H,
        bg = "white",
        highlightthickness = 0
        )
        canvas.pack()

        code_text_items =[]
        code_pos_set = set()
        for cp in code_positions:
            code_pos_set.add((cp[0], cp[1]))

        for r in range(len(grid)):
            for c in range(len(grid[r])):
                x = MARGIN +c *CHAR_WIDTH +CHAR_WIDTH //2
                y = MARGIN +r *LINE_HEIGHT +LINE_HEIGHT //2
                char = grid[r][c]
                is_code =(r, c)in code_pos_set
                tid = canvas.create_text(
                x, y,
                text = char,
                font =("Courier", FONT_SIZE),
                fill = "black"
                )
                if is_code:
                    code_text_items.append({"id":tid, "x":x})

        self._center_popup_on_window(puzzle_window, PAPER_W, PAPER_H)
        puzzle_window.update_idletasks()

        highlight_state = {}
        revealed = set()
        poll_count =[0]

        def update_code_highlights():
            try:
                if not puzzle_window.winfo_exists():
                    return
                crx = canvas.winfo_rootx()
                sw = canvas.winfo_screenwidth()
                ww = canvas.winfo_width()
                visible_left = max(0, -crx)
                visible_right = min(ww, sw -crx)

                poll_count[0]+=1
                if poll_count[0]%20 ==1:
                    logging.debug(f"[offscreen puzzle]crx={crx} sw={sw} ww={ww} vis_left={visible_left} vis_right={visible_right} code_items={len(code_text_items)}")

                for ti in code_text_items:
                    tid = ti["id"]
                    off = ti["x"]<visible_left or ti["x"]>=visible_right
                    if off:
                        revealed.add(tid)
                    should_be_red = tid in revealed
                    if highlight_state.get(tid)!=should_be_red:
                        highlight_state[tid]= should_be_red
                        canvas.itemconfig(tid, fill = "red"if should_be_red else "black", font =("Courier", FONT_SIZE, "bold")if should_be_red else("Courier", FONT_SIZE))
            except Exception as e:
                logging.error(f"[offscreen puzzle]error: {e}")

        def poll_highlights():
            try:
                if not puzzle_window.winfo_exists():
                    return
                update_code_highlights()
                puzzle_window.after(100, poll_highlights)
            except Exception as e:
                logging.error(f"[offscreen puzzle]poll error: {e}")

        logging.debug(f"[offscreen puzzle]Starting poll.code_text_items count: {len(code_text_items)}")
        puzzle_window.after(100, poll_highlights)

        puzzle_window.deiconify()
        puzzle_window.lift()
        puzzle_window.attributes("-topmost", True)
        puzzle_window.after(100, lambda:puzzle_window.attributes("-topmost", False))
