"""CombatMixin — App methods for the "combat" feature area."""
from app.foundation import *
import logging


class CombatMixin:

    def _check_weapon_suppressed(self, weapon):

        try:
            if weapon.get("suppressed")or weapon.get("integrally_suppressed"):
                return True
        except Exception:
            logging.exception("Suppressed exception")

        if weapon.get("accessories"):
            for accessory in weapon["accessories"]:
                if accessory.get("current")and accessory["current"].get("suppressor"):
                    return True

        return False

    def _cycle_bolt_sounds(self, weapon, single_forward = False, delay = 0.12):

        try:
            bolt_setting = str(weapon.get("bolt")or "").lower()
            bolt_catch = bool(weapon.get("bolt_catch", False))

            _cbs_act_raw = weapon.get('action', '') or ''
            if isinstance(_cbs_act_raw, (list, tuple)):
                _cbs_act_raw = _cbs_act_raw[0] if _cbs_act_raw else ''
            _cbs_act = str(_cbs_act_raw).lower()
            _cbs_plat_raw = weapon.get('platform', '') or ''
            if isinstance(_cbs_plat_raw, (list, tuple)):
                _cbs_plat_raw = _cbs_plat_raw[0] if _cbs_plat_raw else ''
            _cbs_plat = str(_cbs_plat_raw).lower()
            _cbs_mag = str(weapon.get('magazinetype', '') or '').lower()
            _cbs_is_pump = ('pump' in _cbs_plat or _cbs_act == 'pump' or 'pump' in _cbs_mag)
            _cbs_is_bolt = _cbs_act in ('bolt', 'lever', 'single')

            if _cbs_is_pump:
                _snd_back = 'pumpback'
                _snd_fwd = 'pumpforward'
            elif _cbs_is_bolt:
                _snd_back = 'boltactionback'
                _snd_fwd = 'boltactionforward'
            else:
                _snd_back = 'boltback'
                _snd_fwd = 'boltforward'

            if bolt_setting =="open":
                if single_forward:
                    if bolt_catch:

                        self._play_weapon_action_sound(weapon, _snd_back, block = True)
                    else:
                        self._play_weapon_action_sound(weapon, _snd_fwd)
                        time.sleep(delay)

                        self._play_weapon_action_sound(weapon, _snd_back, block = True)
                else:

                    self._play_weapon_action_sound(weapon, _snd_fwd)
                    time.sleep(delay)
                    self._play_weapon_action_sound(weapon, _snd_back, block = True)
            else:

                if single_forward:
                    if bolt_catch:
                        self._play_weapon_action_sound(weapon, _snd_fwd)
                    else:

                        self._play_weapon_action_sound(weapon, _snd_back, block = True)
                        time.sleep(delay)
                        self._play_weapon_action_sound(weapon, _snd_fwd)
                else:

                    self._play_weapon_action_sound(weapon, _snd_back, block = True)
                    time.sleep(delay)
                    self._play_weapon_action_sound(weapon, _snd_fwd)
        except Exception:
            try:

                self._play_weapon_action_sound(weapon, "boltforward")
                time.sleep(delay)
                self._play_weapon_action_sound(weapon, "boltback", block = True)
            except Exception:
                logging.exception("Suppressed exception")

    def _scan_belt_available_variants(self, weapon):
        """Scan inventory for loose rounds compatible with a belt-fed weapon. Returns {variant_name: count}."""
        try:
            save_data = globals().get('save_data')or {}
            calibers = []
            try:
                c = weapon.get('caliber')or weapon.get('calibers')or[]
                if isinstance(c, (list, tuple)):
                    calibers = [str(x).strip().lower() for x in c]
                elif c:
                    calibers = [str(c).strip().lower()]
            except Exception:
                calibers = []

            def _cal_ok(item_cal):
                if not calibers:
                    return True
                if not item_cal:
                    return False
                if isinstance(item_cal, list):
                    return any(str(x).strip().lower() in calibers for x in item_cal)
                return str(item_cal).strip().lower() in calibers

            variants = {}

            def _scan(itm):
                if not isinstance(itm, dict):
                    return
                if itm is weapon:
                    return
                if itm.get('magazinesystem')or itm.get('capacity'):
                    return
                if isinstance(itm.get('rounds'), list)and itm.get('rounds'):
                    for r in itm['rounds']:
                        if isinstance(r, dict)and _cal_ok(r.get('caliber')):
                            vn = r.get('variant')or r.get('name')or 'Unknown'
                            variants[vn]= variants.get(vn, 0)+1
                    return
                qty = int(itm.get('quantity')or 0)if isinstance(itm.get('quantity'), (int, float))else 0
                if qty > 0 and _cal_ok(itm.get('caliber')):
                    vn = itm.get('variant')or itm.get('name')or 'Unknown'
                    variants[vn]= variants.get(vn, 0)+qty
                    return
                if itm.get('caliber')and _cal_ok(itm.get('caliber'))and not itm.get('capacity'):
                    vn = itm.get('variant')or itm.get('name')or 'Unknown'
                    variants[vn]= variants.get(vn, 0)+1

            for itm in save_data.get('hands', {}).get('items', []):
                _scan(itm)
            for slot_name, eq_item in save_data.get('equipment', {}).items():
                if not eq_item or not isinstance(eq_item, dict):
                    continue
                for itm in eq_item.get('items', [])or[]:
                    _scan(itm)
                for sub in eq_item.get('subslots', [])or[]:
                    curr = sub.get('current')
                    if curr and isinstance(curr, dict):
                        for itm in curr.get('items', [])or[]:
                            _scan(itm)
            return variants
        except Exception:
            logging.exception('_scan_belt_available_variants error')
            return {}

    def _show_belt_variant_selection(self, weapon, quick=False):
        """Show variant selection popup for belt-fed reload, or auto-select if quick/only one variant."""
        try:
            variants = self._scan_belt_available_variants(weapon)
            if not variants:
                self._popup_show_info('Reload Belt', 'No compatible loose rounds available to load belt')
                return

            if quick or len(variants)==1:
                best = max(variants, key=lambda v: variants[v])
                t = threading.Thread(
                    target=self._perform_belt_reload_sequence,
                    args=(weapon,),
                    kwargs={'quick': quick, 'selected_variant': best},
                    daemon=True
                )
                t.start()
                return

            popup = customtkinter.CTkToplevel(self.root)
            popup.title("Belt Feed - Select Ammunition")
            popup.transient(self.root)

            customtkinter.CTkLabel(
                popup,
                text=f"Select round type for {weapon.get('name', 'this weapon')}:",
                font=customtkinter.CTkFont(size=13),
                wraplength=400
            ).pack(pady=(15, 5), padx=20)

            caliber_info = weapon.get('caliber')or[]
            if isinstance(caliber_info, list):
                caliber_info = ', '.join(str(c) for c in caliber_info)
            customtkinter.CTkLabel(
                popup,
                text=f"Caliber: {caliber_info}",
                font=customtkinter.CTkFont(size=10),
                text_color='#888888'
            ).pack(pady=(0, 10), padx=20)

            scroll_frame = customtkinter.CTkScrollableFrame(popup, fg_color="transparent")
            scroll_frame.pack(fill="both", expand=True, padx=10, pady=5)

            selected_var = customtkinter.StringVar(value="")
            sorted_variants = sorted(variants.items(), key=lambda x: x[1], reverse=True)
            if sorted_variants:
                selected_var.set(sorted_variants[0][0])

            for vn, cnt in sorted_variants:
                radio = customtkinter.CTkRadioButton(
                    scroll_frame,
                    text=f"{vn}  ({cnt} available)",
                    variable=selected_var,
                    value=vn,
                    font=customtkinter.CTkFont(size=12)
                )
                radio.pack(anchor="w", pady=4, padx=10)

            btn_frame = customtkinter.CTkFrame(popup, fg_color="transparent")
            btn_frame.pack(fill="x", padx=20, pady=10)

            def _do_load():
                chosen = selected_var.get()
                if not chosen:
                    return
                popup.destroy()
                t = threading.Thread(
                    target=self._perform_belt_reload_sequence,
                    args=(weapon,),
                    kwargs={'quick': False, 'selected_variant': chosen},
                    daemon=True
                )
                t.start()

            customtkinter.CTkButton(
                btn_frame,
                text="Load Belt",
                command=_do_load,
                width=200,
                height=40
            ).pack(side="left", padx=5)

            customtkinter.CTkButton(
                btn_frame,
                text="Cancel",
                command=popup.destroy,
                width=100,
                height=40,
                fg_color="#444444",
                hover_color="#555555"
            ).pack(side="left", padx=5)

            popup.update_idletasks()
            self._center_popup_on_window(popup, 420, 350)
            popup.grab_set()
            popup.lift()
            self._safe_focus(popup)
        except Exception:
            logging.exception('_show_belt_variant_selection error')

    def _perform_belt_reload_sequence(self, weapon, quick=False, selected_variant=None):
        try:
            save_data = globals().get('save_data')or {}

            if weapon.get("dualfeed") and isinstance(weapon.get("loaded"), dict):
                ejected_mag = weapon.get("loaded")
                if ejected_mag and not weapon.get("infinite_ammo"):
                    save_data.get("hands", {}).get("items", []).append(ejected_mag)
                weapon["loaded"] = None
                weapon["_dualfeed_mode"] = "belt"

            capacity = None
            try:
                capacity = int(weapon.get('capacity')or(weapon.get('loaded')or {}).get('capacity')or 0)
            except Exception:
                capacity = 0
            if not capacity:
                try:
                    capacity = int(weapon.get('mag_capacity')or 200)
                except Exception:
                    capacity = 200

            current_rounds = weapon.get('rounds')or[]
            try:
                if not isinstance(current_rounds, list):
                    current_rounds =[]
            except Exception:
                current_rounds =[]

            need = max(0, capacity -len(current_rounds))
            if need <=0:
                try:
                    self._popup_show_info('Reload Belt', 'Belt already full')
                except Exception:
                    logging.exception("Suppressed exception")
                return

            rounds_collected =[]

            def round_matches(r, calib_list):
                try:
                    if not isinstance(r, dict):
                        return True
                    rcal = r.get('caliber')or r.get('cal')or None
                    if not rcal:
                        return True
                    if not calib_list:
                        return True
                    rcal_low = str(rcal).strip().lower()
                    for c in calib_list:
                        try:
                            if rcal_low==str(c).strip().lower():
                                return True
                        except Exception:
                            logging.exception("Suppressed exception")
                    return False
                except Exception:
                    return True

            def item_cal_matches(itm_cal, calib_list):
                """Check if an item-level caliber matches the weapon calibers."""
                if not calib_list:
                    return True
                if not itm_cal:
                    return False
                if isinstance(itm_cal, list):
                    return any(str(x).strip().lower() in [str(c).strip().lower() for c in calib_list] for x in itm_cal)
                return str(itm_cal).strip().lower() in [str(c).strip().lower() for c in calib_list]

            def variant_matches(itm):
                """Check if item variant/name matches the selected_variant filter."""
                if not selected_variant:
                    return True
                vn = itm.get('variant')or itm.get('name')or 'Unknown'
                return str(vn)==selected_variant

            def round_variant_matches(r):
                """Check if a round dict matches the selected_variant filter."""
                if not selected_variant:
                    return True
                if not isinstance(r, dict):
                    return True
                vn = r.get('variant')or r.get('name')or 'Unknown'
                return str(vn)==selected_variant

            calibers =[]
            try:
                c = weapon.get('caliber')or weapon.get('calibers')or[]
                if isinstance(c, (list, tuple)):
                    calibers = c
                elif c:
                    calibers =[c]
            except Exception:
                calibers =[]

            try:

                hands = save_data.get('hands', {}).get('items', [])
                for hi in range(len(hands)-1, -1, -1):
                    if need <=0:
                        break
                    itm = hands[hi]
                    if not isinstance(itm, dict):
                        continue
                    if itm is weapon:
                        continue
                    if itm.get('magazinesystem')or itm.get('capacity'):

                        continue

                    if isinstance(itm.get('rounds'), list)and itm.get('rounds'):
                        take =[]
                        keep =[]
                        rlist = itm.get('rounds')or[]
                        for r in rlist:
                            if len(take)<need and round_matches(r, calibers)and round_variant_matches(r):
                                take.append(r)
                            else:
                                keep.append(r)
                        for r in take:
                            rounds_collected.append(r)
                            need -=1
                        itm['rounds']= keep
                        if not itm.get('rounds'):
                            try:
                                hands.pop(hi)
                            except Exception:
                                logging.exception("Suppressed exception")
                        continue

                    qty = int(itm.get('quantity')or 0)if isinstance(itm.get('quantity'), (int, float))else 0
                    if qty >0 and('caliber'in itm or 'name'in itm)and item_cal_matches(itm.get('caliber'), calibers)and variant_matches(itm):
                        take_n = min(need, qty)
                        for _ in range(take_n):
                            r = {k:v for k, v in itm.items()if k !='quantity'}
                            rounds_collected.append(r)
                            need -=1
                        itm['quantity']= qty -take_n
                        if itm['quantity']<=0:
                            try:
                                hands.pop(hi)
                            except Exception:
                                logging.exception("Suppressed exception")
                        continue

                    if itm.get('caliber')and item_cal_matches(itm.get('caliber'), calibers)and variant_matches(itm):
                        try:
                            hands.pop(hi)
                            rounds_collected.append(itm)
                            need -=1
                        except Exception:
                            logging.exception("Suppressed exception")

                for slot_name, eq_item in list(save_data.get('equipment', {}).items()):
                    if need <=0:
                        break
                    if not eq_item or not isinstance(eq_item, dict):
                        continue
                    for itm in list(eq_item.get('items', [])or[]):
                        if need <=0:
                            break
                        if not isinstance(itm, dict):
                            continue
                        if itm.get('magazinesystem')or itm.get('capacity'):
                            continue
                        if isinstance(itm.get('rounds'), list)and itm.get('rounds'):
                            take =[]
                            keep =[]
                            rlist = itm.get('rounds')or[]
                            for r in rlist:
                                if len(take)<need and round_matches(r, calibers)and round_variant_matches(r):
                                    take.append(r)
                                else:
                                    keep.append(r)
                            for r in take:
                                rounds_collected.append(r)
                                need -=1
                            itm['rounds']= keep
                            if not itm.get('rounds'):
                                try:
                                    eq_item['items'].remove(itm)
                                except Exception:
                                    logging.exception("Suppressed exception")
                            continue
                        qty = int(itm.get('quantity')or 0)if isinstance(itm.get('quantity'), (int, float))else 0
                        if qty >0 and('caliber'in itm or 'name'in itm)and item_cal_matches(itm.get('caliber'), calibers)and variant_matches(itm):
                            take_n = min(need, qty)
                            for _ in range(take_n):
                                r = {k:v for k, v in itm.items()if k !='quantity'}
                                rounds_collected.append(r)
                                need -=1
                            itm['quantity']= qty -take_n
                            if itm['quantity']<=0:
                                try:
                                    eq_item['items'].remove(itm)
                                except Exception:
                                    logging.exception("Suppressed exception")
                            continue
            except Exception:
                logging.exception('Error collecting loose rounds for belt reload')

            if not rounds_collected:
                try:
                    self._popup_show_info('Reload Belt', 'No loose rounds available in hands or equipment to load belt')
                except Exception:
                    logging.exception("Suppressed exception")
                return

            try:
                self._play_weapon_action_sound(weapon, 'boltback')
            except Exception:
                logging.exception("Suppressed exception")
            try:
                self._play_weapon_action_sound(weapon, 'boltforward')
            except Exception:
                logging.exception("Suppressed exception")
            time.sleep(random.uniform(0.4, 0.6))

            try:
                self._play_weapon_action_sound(weapon, 'coveropen')
            except Exception:
                logging.exception("Suppressed exception")
            time.sleep(random.uniform(0.4, 0.6))

            try:
                self._play_weapon_action_sound(weapon, 'magout')
            except Exception:
                logging.exception("Suppressed exception")
            time.sleep(random.uniform(0.15, 0.25))

            if quick:
                try:
                    magdrop_sound = f"magdrop{random.randint(0, 1)}"
                    self._safe_sound_play("", f"sounds/firearms/universal/{magdrop_sound}.ogg")
                except Exception:
                    logging.exception("Suppressed exception")
            else:
                try:
                    self._play_weapon_action_sound(weapon, 'pouchin')
                except Exception:
                    logging.exception("Suppressed exception")
            time.sleep(random.uniform(1.0, 1.5))

            try:
                self._play_weapon_action_sound(weapon, 'pouchout')
            except Exception:
                logging.exception("Suppressed exception")
            time.sleep(random.uniform(0.15, 0.25))

            try:
                self._play_weapon_action_sound(weapon, 'magin')
            except Exception:
                logging.exception("Suppressed exception")
            time.sleep(random.uniform(0.4, 0.6))

            try:
                self._play_weapon_action_sound(weapon, 'beltalign')
            except Exception:
                logging.exception("Suppressed exception")
            time.sleep(random.uniform(0.4, 0.6))

            try:
                self._play_weapon_action_sound(weapon, 'coverclose')
            except Exception:
                logging.exception("Suppressed exception")
            time.sleep(random.uniform(0.4, 0.6))

            try:
                self._play_weapon_action_sound(weapon, 'boltback')
            except Exception:
                logging.exception("Suppressed exception")
            try:
                self._play_weapon_action_sound(weapon, 'boltforward')
            except Exception:
                logging.exception("Suppressed exception")

            try:
                existing = weapon.get('rounds')or[]
                if not isinstance(existing, list):
                    existing =[]
                weapon['rounds']= existing +rounds_collected

                try:
                    if 'loaded'in weapon:
                        weapon['loaded']= None
                except Exception:
                    logging.exception("Suppressed exception")
            except Exception:
                logging.exception('Failed to insert collected rounds into weapon rounds')

            try:
                self._popup_show_info('Reload Belt', f'Loaded {len(rounds_collected)} rounds into belt')
            except Exception:
                logging.exception("Suppressed exception")
            try:

                update_weapon_view()
            except Exception:
                logging.exception("Suppressed exception")
        except Exception:
            logging.exception('_perform_belt_reload_sequence error')

    def _perform_dualfeed_belt_reload_sequence(self, weapon, quick=False):
        try:
            sub_mag_system = weapon.get("submagazinesystem")
            sub_mag_type = weapon.get("submagazinetype")
            if not sub_mag_system and not sub_mag_type:
                self._show_belt_variant_selection(weapon, quick=quick)
                return

            popup = customtkinter.CTkToplevel(self.root)
            popup.title("Select Feed Type")
            popup.transient(self.root)
            self._center_popup_on_window(popup, 350, 200)

            label = customtkinter.CTkLabel(
                popup,
                text=f"How do you want to reload {weapon.get('name', 'this weapon')}?",
                font=customtkinter.CTkFont(size=13),
                wraplength=300
            )
            label.pack(pady=15, padx=20)

            button_frame = customtkinter.CTkFrame(popup, fg_color="transparent")
            button_frame.pack(fill="x", padx=20, pady=10)

            def choose_belt():
                popup.destroy()
                try:
                    self._show_belt_variant_selection(weapon, quick=quick)
                except Exception:
                    logging.exception("dualfeed belt reload error")

            def choose_magazine():
                popup.destroy()
                try:
                    save_data = globals().get('save_data') or {}
                    table_data = globals().get('table_data') or {}
                    current_weapon_state = globals().get('current_weapon_state') or {}
                    update_cb = globals().get('update_weapon_view') or (lambda: None)
                    self._show_dualfeed_magazine_selection(weapon, save_data, table_data, current_weapon_state, update_cb)
                except Exception:
                    logging.exception("dualfeed magazine reload error")

            belt_btn = customtkinter.CTkButton(
                button_frame,
                text="Belt Feed (loose rounds)",
                command=choose_belt,
                width=280,
                height=40
            )
            belt_btn.pack(pady=5)

            mag_btn = customtkinter.CTkButton(
                button_frame,
                text=f"Magazine ({sub_mag_system or sub_mag_type or 'detachable'})",
                command=choose_magazine,
                width=280,
                height=40
            )
            mag_btn.pack(pady=5)

            cancel_btn = customtkinter.CTkButton(
                button_frame,
                text="Cancel",
                command=popup.destroy,
                width=280,
                height=35,
                fg_color="#444444",
                hover_color="#555555"
            )
            cancel_btn.pack(pady=5)

            popup.update_idletasks()
            popup.grab_set()
            popup.lift()
            self._safe_focus(popup)
        except Exception:
            logging.exception('_perform_dualfeed_belt_reload_sequence error')

    def _show_dualfeed_magazine_selection(self, weapon, save_data, table_data, current_weapon_state, update_callback):
        try:
            sub_mag_system = weapon.get("submagazinesystem")
            sub_mag_type = (weapon.get("submagazinetype") or "").lower()
            weapon_calibers = weapon.get("caliber") or []
            if isinstance(weapon_calibers, str):
                weapon_calibers = [weapon_calibers]

            compatible_mags = []

            def mag_is_compatible(mag):
                if not mag or not isinstance(mag, dict):
                    return False
                try:
                    if mag.get("firearm") is True:
                        return False
                except Exception:
                    logging.exception("Suppressed exception")
                compat = False
                try:
                    if sub_mag_system and mag.get("magazinesystem") == sub_mag_system:
                        compat = True
                except Exception:
                    logging.exception("Suppressed exception")
                try:
                    mag_mt = str(mag.get("magazinetype", "") or "").lower()
                    if sub_mag_type and mag_mt == sub_mag_type:
                        compat = True
                except Exception:
                    logging.exception("Suppressed exception")
                if not compat:
                    return False
                try:
                    if weapon_calibers:
                        mag_rounds = mag.get("rounds", [])
                        if mag_rounds:
                            for rd in mag_rounds:
                                if isinstance(rd, dict):
                                    rcal = rd.get("caliber", "")
                                    if isinstance(rcal, list):
                                        rcal = rcal[0] if rcal else ""
                                    if rcal and str(rcal) not in [str(c) for c in weapon_calibers]:
                                        return False
                except Exception:
                    logging.exception("Suppressed exception")
                return True

            for item in save_data.get("hands", {}).get("items", []):
                if mag_is_compatible(item) and len(item.get("rounds", [])) > 0:
                    compatible_mags.append(("hands", item))

            for slot_name, item in save_data.get("equipment", {}).items():
                if item and isinstance(item, dict):
                    if "items" in item and isinstance(item["items"], list):
                        for mag in item["items"]:
                            if mag_is_compatible(mag) and len(mag.get("rounds", [])) > 0:
                                compatible_mags.append(("equipment", mag))
                    if item.get("subslots"):
                        for subslot in item["subslots"]:
                            if subslot.get("current"):
                                curr = subslot["current"]
                                if "items" in curr and isinstance(curr["items"], list):
                                    for mag in curr["items"]:
                                        if mag_is_compatible(mag) and len(mag.get("rounds", [])) > 0:
                                            compatible_mags.append(("equipment", mag))

            if not compatible_mags:
                self._popup_show_info("Magazine", f"No compatible {sub_mag_system or 'detachable'} magazines found in inventory!")
                return

            popup = customtkinter.CTkToplevel(self.root)
            popup.title("Select Magazine")
            popup.transient(self.root)
            self._center_popup_on_window(popup, 500, 450)

            label = customtkinter.CTkLabel(
                popup,
                text=f"Select a magazine for {weapon.get('name')} ({sub_mag_system or sub_mag_type}):",
                font=customtkinter.CTkFont(size=13),
                wraplength=450
            )
            label.pack(pady=10, padx=20)

            scroll_frame = customtkinter.CTkScrollableFrame(popup, fg_color="transparent")
            scroll_frame.pack(fill="both", expand=True, padx=10, pady=10)

            selected_mag = customtkinter.StringVar(value="0")

            for idx, (location, mag_item) in enumerate(compatible_mags):
                mag_name = mag_item.get("name", "Unknown Magazine")
                capacity = mag_item.get("capacity", "?")
                rounds = len(mag_item.get("rounds", []))

                radio_frame = customtkinter.CTkFrame(scroll_frame, fg_color="transparent")
                radio_frame.pack(fill="x", pady=5, padx=5)

                radio_text = f"{mag_name} ({rounds}/{capacity})"
                radio_text += f" - from {location}"
                _mag_rds_list = mag_item.get("rounds", [])
                if _mag_rds_list and isinstance(_mag_rds_list, list) and len(_mag_rds_list) > 0:
                    _mnr = _mag_rds_list[0]
                    if isinstance(_mnr, dict):
                        _mnv = _mnr.get("variant") or _mnr.get("name")
                        if _mnv:
                            radio_text += f" [next: {_mnv}]"
                radio = customtkinter.CTkRadioButton(
                    radio_frame,
                    text=radio_text,
                    variable=selected_mag,
                    value=str(idx),
                    font=customtkinter.CTkFont(size=11)
                )
                radio.pack(anchor="w")

            def load_magazine():
                if not selected_mag.get():
                    self._popup_show_info("Magazine", "Please select a magazine!")
                    return
                idx = int(selected_mag.get())
                location, mag_item = compatible_mags[idx]

                current_belt_rounds = weapon.get("rounds") or []
                if current_belt_rounds:
                    save_data.get("hands", {}).get("items", []).extend(
                        [{"name": r.get("name", "Round"), "caliber": r.get("caliber"), "variant": r.get("variant"), "type": r.get("type"), "pen": r.get("pen"), "rounds": [r]} for r in current_belt_rounds] if False else []
                    )

                current_mag = weapon.get("loaded")
                chambered = weapon.get("chambered")
                is_gun_empty = not chambered and (not current_mag or not current_mag.get("rounds", []))

                if current_mag and not weapon.get("infinite_ammo"):
                    save_data.get("hands", {}).get("items", []).append(current_mag)

                try:
                    self._play_weapon_action_sound(weapon, "coveropen")
                except Exception:
                    logging.exception("Suppressed exception")
                time.sleep(random.uniform(0.5, 0.8))

                try:
                    self._safe_sound_play("", "sounds/firearms/universal/pouchout.ogg")
                except Exception:
                    logging.exception("Suppressed exception")
                time.sleep(random.uniform(0.8, 1.2))

                try:
                    self._play_weapon_action_sound(weapon, "magin")
                except Exception:
                    logging.exception("Suppressed exception")
                time.sleep(random.uniform(0.5, 0.8))

                try:
                    self._play_weapon_action_sound(weapon, "coverclose")
                except Exception:
                    logging.exception("Suppressed exception")
                time.sleep(random.uniform(0.3, 0.5))

                weapon["loaded"] = mag_item
                weapon["rounds"] = []
                weapon["_dualfeed_mode"] = "magazine"

                if is_gun_empty and mag_item.get("rounds", []):
                    try:
                        self._play_weapon_action_sound(weapon, "boltback", block=True)
                    except Exception:
                        logging.exception("Suppressed exception")
                    try:
                        self._play_weapon_action_sound(weapon, "boltforward")
                    except Exception:
                        logging.exception("Suppressed exception")
                    weapon["chambered"] = mag_item["rounds"].pop(0)
                else:
                    weapon["chambered"] = None

                if not weapon.get("infinite_ammo"):
                    if location == "hands":
                        if mag_item in save_data.get("hands", {}).get("items", []):
                            save_data["hands"]["items"].remove(mag_item)
                    elif location == "equipment":
                        for slot_name, item in save_data.get("equipment", {}).items():
                            if item and isinstance(item, dict):
                                if "items" in item and isinstance(item["items"], list):
                                    if mag_item in item["items"]:
                                        item["items"].remove(mag_item)
                                if item.get("subslots"):
                                    for subslot in item["subslots"]:
                                        if subslot.get("current"):
                                            curr = subslot["current"]
                                            if "items" in curr and isinstance(curr["items"], list):
                                                if mag_item in curr["items"]:
                                                    curr["items"].remove(mag_item)

                popup.destroy()
                mag_name = mag_item.get("name", "magazine")
                rounds = len(mag_item.get("rounds", []))
                chambered_info = " +1 in chamber" if is_gun_empty and weapon.get("chambered") else ""
                self._popup_show_info("Magazine", f"Loaded {mag_name} ({rounds}{chambered_info} rounds) into magazine well!")
                update_callback()

            btn_frame = customtkinter.CTkFrame(popup, fg_color="transparent")
            btn_frame.pack(fill="x", padx=10, pady=10)

            load_btn = customtkinter.CTkButton(btn_frame, text="Load Magazine", command=load_magazine, width=150, height=40)
            load_btn.pack(side="left", padx=5)

            cancel_btn = customtkinter.CTkButton(btn_frame, text="Cancel", command=popup.destroy, width=150, height=40, fg_color="#444444", hover_color="#555555")
            cancel_btn.pack(side="left", padx=5)

            popup.update_idletasks()
            popup.grab_set()
            popup.lift()
            self._safe_focus(popup)
        except Exception:
            logging.exception("_show_dualfeed_magazine_selection error")

    def _fire_weapon_impl(self, weapon, combat_state, rounds_to_fire = 3, fire_mode = None, save_data = None):# type: ignore

        weapon_id = str(weapon.get("id"))
        logging.info(
        "_fire_weapon start: id=%s name=%s rounds=%s mode=%s",
        weapon_id,
        weapon.get("name", "Unknown"),
        rounds_to_fire,
        fire_mode or "unknown"
        )

        roll_summary_text = None

        chambered = weapon.get("chambered")
        loaded_mag = weapon.get("loaded")
        magazine_type = str(weapon.get("magazinetype", "")or "").lower()
        is_en_bloc = "en bloc" in magazine_type

        raw_platform = weapon.get("platform", "")or ""
        if isinstance(raw_platform, (list, tuple)):
            raw_platform = raw_platform[0]if raw_platform else ""
        platform = str(raw_platform)

        is_dualfeed_mag_mode = weapon.get("dualfeed") and isinstance(loaded_mag, dict) and loaded_mag
        is_internal = ("internal"in magazine_type or "tube"in magazine_type or "cylinder"in magazine_type or "break"in magazine_type or "en bloc" in magazine_type or "revolver"in platform.lower()or("belt"in magazine_type)or("m249"in platform.lower())) and not is_dualfeed_mag_mode
        is_cylinder_sim = is_internal and ("cylinder" in magazine_type or "revolver" in platform.lower())
        cylinder_capacity = 0
        cylinder_layout = []
        cylinder_index = 0

        if is_cylinder_sim:
            try:
                cylinder_capacity = int(weapon.get("capacity", 0) or 0)
            except Exception:
                cylinder_capacity = 0
            if cylinder_capacity <= 0:
                try:
                    cylinder_capacity = int(len(weapon.get("rounds", []) or []) + int(weapon.get("_cylinder_spent", 0) or 0))
                except Exception:
                    cylinder_capacity = 0
            if cylinder_capacity <= 0:
                cylinder_capacity = 6

            def _is_spent_slot(v):
                if isinstance(v, str):
                    return v.strip().lower() in ("spent", "case", "casing", "_spent_", "__spent__")
                if isinstance(v, dict):
                    nm = str(v.get("name") or "").lower()
                    vr = str(v.get("variant") or "").lower()
                    return ("spent" in nm) or ("case" in nm) or ("casing" in nm) or ("spent" in vr) or ("case" in vr) or ("casing" in vr)
                return False

            raw_layout = weapon.get("_cylinder_layout")
            use_raw_layout = isinstance(raw_layout, list) and len(raw_layout) == cylinder_capacity
            expected_live = len([r for r in (weapon.get("rounds", []) or []) if isinstance(r, dict)])
            try:
                expected_spent = max(0, int(weapon.get("_cylinder_spent", 0) or 0))
            except Exception:
                expected_spent = 0

            if use_raw_layout:
                tmp_layout = []
                for slot in raw_layout:
                    if _is_spent_slot(slot):
                        tmp_layout.append("__spent__")
                    elif isinstance(slot, dict):
                        tmp_layout.append(slot)
                    else:
                        tmp_layout.append(None)
                raw_live = sum(1 for slot in tmp_layout if isinstance(slot, dict))
                raw_spent = sum(1 for slot in tmp_layout if slot == "__spent__")
                if raw_live == expected_live and raw_spent == expected_spent:
                    cylinder_layout = tmp_layout
                else:
                    use_raw_layout = False

            if not use_raw_layout:
                legacy_live = [r for r in (weapon.get("rounds", []) or []) if isinstance(r, dict)]
                try:
                    legacy_spent = max(0, int(weapon.get("_cylinder_spent", 0) or 0))
                except Exception:
                    legacy_spent = 0
                for i in range(cylinder_capacity):
                    if i < legacy_spent:
                        cylinder_layout.append("__spent__")
                    elif legacy_live:
                        cylinder_layout.append(legacy_live.pop(0))
                    else:
                        cylinder_layout.append(None)

            try:
                cylinder_index = int(weapon.get("_cylinder_index", 0) or 0)
            except Exception:
                cylinder_index = 0
            if cylinder_capacity > 0:
                cylinder_index %= cylinder_capacity

        is_belt = False

        raw_action = weapon.get("action", "")or ""
        if isinstance(raw_action, (list, tuple)):
            action_list =[str(a).lower()for a in raw_action if a is not None]
        else:
            action_list =[str(raw_action).lower()]
        is_single_action_weapon = any((a == "single") or ("single" in a) for a in action_list)

        is_pump =(
        "pump"in platform.lower()
        or any("pump"in a for a in action_list)
        or "pump"in magazine_type
        )

        fire_mode_norm = str(fire_mode or "").title()
        _fire_mode_l = str(fire_mode or "").strip().lower()
        is_double_action_mode = _fire_mode_l in ("double", "double action", "da")
        effective_is_pump = is_pump and fire_mode_norm =="Pump"

        magicsys = str(weapon.get("magicsoundsystem")or "").lower()
        is_magic =(str(weapon.get("type")or "").lower()=="magic")or(magicsys in("hg", "at", "mg", "rf"))

        if is_magic:

            magic_folder = os.path.join("sounds", "firearms", "magic", magicsys if magicsys else "hg")

            requires_charge = magicsys in("at", "rf")

            temperature = combat_state.get("barrel_temperatures", {}).get(weapon_id, combat_state.get("ambient_temperature", 70))

            pre_fire_temp = temperature

            if requires_charge:
                charge_file = os.path.join(magic_folder, "charge.ogg")
                if os.path.exists(charge_file):
                    try:
                        self._safe_sound_play("", charge_file, block = True)
                    except Exception:
                        logging.exception("Failed to play charge sound for magic weapon")

            if magicsys =="rf":
                prefire_file = os.path.join(magic_folder, "prefire.ogg")
                if os.path.exists(prefire_file):
                    try:
                        self._safe_sound_play("", prefire_file, block = True)
                    except Exception:
                        logging.exception("Failed to play prefire for rf magic weapon")

            try:
                nshots = max(1, int(rounds_to_fire or 1))
            except Exception:
                nshots = 1

            if magicsys in("at", "rf"):
                nshots = 1

            try:
                raw_rpm = weapon.get("cyclic", weapon.get("rpm", 600))
                if isinstance(raw_rpm, list):
                    rpm = _resolve_effective_cyclic(weapon, combat_state)
                else:
                    rpm = float(raw_rpm or 600)
                if rpm <=0:
                    rpm = 600.0
            except Exception:
                rpm = 600.0
            shot_delay = 60.0 /float(rpm)

            try:
                import glob as _glob
                fire_candidates = _glob.glob(os.path.join(magic_folder, "fire*.ogg"))
            except Exception:
                fire_candidates =[]

            try:
                temp_gain = float(weapon.get("temp_gain_per_shot", weapon.get("temp_gain", 20)or 20))
            except Exception:
                temp_gain = random.uniform(15, 25)
            if self._check_weapon_suppressed(weapon):
                temp_gain *=1.5

            for i in range(nshots):

                try:

                    block_this_shot = magicsys in("at", "rf")
                    if fire_candidates:
                        chosen = random.choice(fire_candidates)
                        self._safe_sound_play("", chosen, block = block_this_shot)
                    else:

                        fallback_path = os.path.join("sounds", weapon.get("sound_folder", ""), "fire.ogg")
                        self._safe_sound_play("", fallback_path, block = block_this_shot)
                except Exception:
                    logging.exception("Magic weapon fire sound failed")

                if magicsys in("at", "rf"):
                    try:
                        self._play_weapon_action_sound_strict(weapon, "boltback", block = False)
                    except Exception:
                        logging.exception("Suppressed exception")

                try:
                    temperature +=temp_gain
                except Exception:
                    temperature = temperature +(temp_gain if isinstance(temp_gain, (int, float))else 0)

                try:
                    if not(magicsys in("at", "rf")):

                        try:
                            if str(fire_mode or "").title()=="Semi":
                                jitter = random.uniform(-0.06, 0.06)
                                time.sleep(max(0.0, shot_delay +0.18 +jitter))
                            else:
                                time.sleep(shot_delay)
                        except Exception:

                            time.sleep(shot_delay)
                except Exception:
                    logging.exception("Suppressed exception")

            cooling_file = os.path.join(magic_folder, "cooling.ogg")
            if magicsys in("at", "rf")and os.path.exists(cooling_file):
                try:
                    self._safe_sound_play("", cooling_file, block = True)
                except Exception:
                    logging.exception("Failed to play cooling sound for magic weapon")

            try:
                cool_amount = float(weapon.get("temp_loss_per_cooling_cycle", weapon.get("temp_loss", 20)or 20))
            except Exception:
                cool_amount = random.uniform(5, 15)

            cool_amount = cool_amount *float(weapon.get("magic_cooling_multiplier", 1.8))

            temperature = max(pre_fire_temp, temperature -cool_amount)

            try:
                combat_state.setdefault("magic_weapon_ids", {})[weapon_id]= True
            except Exception:
                logging.exception("Suppressed exception")

            if magicsys in("at", "rf"):
                try:
                    self._play_weapon_action_sound(weapon, "boltforward")
                except Exception:
                    logging.exception("Suppressed exception")

            combat_state.setdefault("barrel_temperatures", {})[weapon_id]= temperature
            return "Fired(magic)"

        if is_internal:
            internal_rounds = weapon.get("rounds", [])

            if not chambered and not internal_rounds:
                logging.info("Weapon empty(internal) - no rounds present")
                self._safe_sound_play("", "sounds/firearms/universal/dryfire.ogg")
                return "Empty! No rounds loaded."
        else:

            if not chambered and not loaded_mag:
                logging.info("Weapon empty - no magazine loaded")
                self._safe_sound_play("", "sounds/firearms/universal/dryfire.ogg")
                return "Empty! No magazine loaded."

            if not chambered and loaded_mag and not loaded_mag.get("rounds"):
                logging.info("Weapon empty - magazine loaded but empty")
                self._safe_sound_play("", "sounds/firearms/universal/dryfire.ogg")
                return "Empty! Magazine loaded but no rounds."

        can_fire, cant_fire_reason = _check_weapon_can_fire(weapon)
        if not can_fire:
            logging.info("Weapon cannot fire due to worn/missing part: %s", cant_fire_reason)
            self._safe_sound_play("", "sounds/firearms/universal/dryfire.ogg")
            return cant_fire_reason or "Weapon cannot fire - parts failure!"

        part_effects = _get_weapon_part_effects(weapon)
        if part_effects.get("force_manual_action"):
            weapon["gas_melted"] = True
            logging.info("Part worn - forcing manual action (recoil spring or gas piston)")

        wrong_ammo_firing = False
        try:
            weapon_calibers = weapon.get("caliber") or []
            if isinstance(weapon_calibers, str):
                weapon_calibers = [weapon_calibers]
            next_round = None
            if chambered and isinstance(chambered, dict):
                next_round = chambered
            elif is_internal and weapon.get("rounds"):
                next_round = weapon["rounds"][0] if weapon["rounds"] else None
            elif loaded_mag and loaded_mag.get("rounds"):
                next_round = loaded_mag["rounds"][0] if loaded_mag["rounds"] else None
            if next_round and isinstance(next_round, dict):
                round_caliber = next_round.get("caliber", "")
                if isinstance(round_caliber, list):
                    round_caliber = round_caliber[0] if round_caliber else ""
                if round_caliber and weapon_calibers and round_caliber not in weapon_calibers:
                    wrong_ammo_firing = True
                    logging.warning("Firing wrong ammo type: %s in weapon calibered for %s", round_caliber, weapon_calibers)
        except Exception:
            wrong_ammo_firing = False

        temperature = combat_state.get("barrel_temperatures", {}).get(weapon_id, combat_state["ambient_temperature"])
        cleanliness = _get_weapon_cleanliness(combat_state, weapon, default = 100.0, cache_to_state = True)

        base_jamrate = weapon.get("jamrate", 0.01)

        ambient = combat_state.get("ambient_temperature", 70)
        temp_above_boiling = max(0, temperature -212)
        temp_mult = 1.0 +(temp_above_boiling /400.0)

        clean_mult = 1.0 -(cleanliness -50)/100.0
        clean_mult = max(0.5, min(1.5, clean_mult))

        mag_reliability_mult = 1.0
        try:
            is_hardcore_jam = False
            tbl_jam = globals().get('table_data', {})
            if isinstance(tbl_jam, dict):
                is_hardcore_jam = bool((tbl_jam.get('additional_settings') or {}).get('hardcore_mode'))
            if is_hardcore_jam:
                loaded_mag_jam = weapon.get("loaded")
                if isinstance(loaded_mag_jam, dict):
                    mag_reliability = loaded_mag_jam.get("reliability")
                    if mag_reliability is not None:
                        try:
                            mag_reliability = float(mag_reliability)
                        except (ValueError, TypeError):
                            mag_reliability = 100.0
                        mag_reliability = max(0.0, min(100.0, mag_reliability))
                        if mag_reliability < 100.0:
                            mag_reliability_mult = 1.0 + (100.0 - mag_reliability) / 50.0

                    spring_dur = loaded_mag_jam.get("spring_durability")
                    if spring_dur is not None:
                        try:
                            spring_dur = float(spring_dur)
                        except (ValueError, TypeError):
                            spring_dur = None
                    if spring_dur is not None and spring_dur < 80.0:
                        spring_penalty = (80.0 - spring_dur) / 80.0
                        mag_reliability_mult *= (1.0 + spring_penalty * 2.0)
        except Exception:
            mag_reliability_mult = 1.0

        part_jam_mult = 1.0
        low_durability_jam_parts = []
        try:
            part_jam_mult, low_durability_jam_parts = _get_weapon_part_jam_data(weapon)
        except Exception:
            part_jam_mult = 1.0
            low_durability_jam_parts = []

        total_jamrate = base_jamrate *temp_mult *clean_mult * mag_reliability_mult * part_jam_mult

        logging.debug(
        "Jam calc: base=%s temp_mult=%s clean_mult=%s mag_mult=%s part_mult=%s total=%s temp=%s clean=%s",
        base_jamrate,
        temp_mult,
        clean_mult,
        mag_reliability_mult,
        part_jam_mult,
        total_jamrate,
        temperature,
        cleanliness
        )

        cyclic = _resolve_effective_cyclic(weapon, combat_state)
        base_delay = max(0.0, 60.0 /cyclic)

        burst_cyclic = weapon.get("burst_cyclic")
        try:
            if burst_cyclic:
                burst_cyclic = float(burst_cyclic)
            else:
                burst_cyclic = None
        except Exception:
            burst_cyclic = None
        burst_base_delay = max(0.0, 60.0 /burst_cyclic)if burst_cyclic and burst_cyclic >0 else base_delay

        try:
            burst_pause = float(weapon.get("burst_pause"))
            if burst_pause <0:
                burst_pause = None
        except Exception:
            burst_pause = None
        if burst_pause is None:

            burst_pause = max(0.22, base_delay *1.5)

        actual_rounds_to_fire = rounds_to_fire
        burst_count = weapon.get("burst_count", 0)

        if fire_mode =="Bolt":
            actual_rounds_to_fire = 1
            logging.debug("Bolt-action fire mode: forcing rounds to 1")

        elif fire_mode =="Double":
            actual_rounds_to_fire = 1
            logging.debug("Double-action fire mode: forcing rounds to 1")

        elif effective_is_pump:
            actual_rounds_to_fire = 1
            logging.debug("Pump-action weapon(selected): forcing rounds to 1")
        elif fire_mode =="Burst"and burst_count >0:

            actual_rounds_to_fire =((rounds_to_fire +burst_count -1)//burst_count)*burst_count
            logging.debug(
            "Burst fire mode: requested=%s burst_count=%s actual=%s",
            rounds_to_fire,
            burst_count,
            actual_rounds_to_fire
            )

        if is_single_action_weapon and actual_rounds_to_fire != 1:
            logging.debug("Single-action weapon detected: limiting actual_rounds_to_fire to 1")
            actual_rounds_to_fire = 1

        if weapon.get("gas_melted", False):
            actual_rounds_to_fire = 1
            logging.debug("Gas-melted weapon detected: forcing single-shot behavior")

        is_semi = fire_mode =="Semi"
        is_burst = fire_mode =="Burst"and burst_count >0
        is_auto = fire_mode =="Auto"

        is_bolt = fire_mode =="Bolt"or bool(weapon.get("gas_melted", False))

        rounds_fired = 0
        jammed = False
        fired_rounds_list = []

        fire_to_pump_delay = weapon.get("pump_fire_to_back_delay", 0.12)
        pump_back_to_forward_delay = weapon.get("pump_back_to_forward_delay", 0.15)

        if effective_is_pump:
            if actual_rounds_to_fire !=1:
                logging.debug("Pump-action weapon detected(selected): limiting actual_rounds_to_fire to 1")
            actual_rounds_to_fire = 1

        rotary_channel = None
        rotary_sound = None
        rotary_playing = False
        try:
            if weapon.get("rotary_gun"):
                def _find_sound_candidate(action_name):
                    try:
                        fs = weapon.get("fire_sounds")or weapon.get("sounds")or weapon.get("sound_folder")or weapon.get("reload_sounds")
                    except Exception:
                        fs = None

                    candidates =[]
                    if fs:
                        wf = os.path.join("sounds", "firearms", str(fs).lower())
                        for pat in(f"{action_name}*.ogg", f"{action_name}*.wav"):
                            candidates +=glob.glob(os.path.join(wf, pat))
                        if not candidates:
                            wf2 = os.path.join("sounds", "firearms", "weaponsounds", str(fs).lower().replace('/', '_'))
                            for pat in(f"{action_name}*.ogg", f"{action_name}*.wav"):
                                candidates +=glob.glob(os.path.join(wf2, pat))

                    try:
                        plat = str(weapon.get("platform")or "").lower().replace('/', '_')
                    except Exception:
                        plat = None
                    if plat:
                        wf3 = os.path.join("sounds", "firearms", "weaponsounds", plat)
                        for pat in(f"{action_name}*.ogg", f"{action_name}*.wav"):
                            candidates +=glob.glob(os.path.join(wf3, pat))

                    uni = os.path.join("sounds", "firearms", "universal")
                    for pat in(f"{action_name}*.ogg", f"{action_name}*.wav"):
                        candidates +=glob.glob(os.path.join(uni, pat))

                    return candidates[0]if candidates else None

                try:
                    path_windup = _find_sound_candidate("rotarywindup")
                    if path_windup:
                        try:
                            self._safe_sound_play("", path_windup, block = True)
                        except Exception:
                            logging.exception("Suppressed exception")
                    else:

                        try:
                            self._safe_sound_play("", os.path.join("sounds", "firearms", "universal", "rotarywindup.ogg"), block = True)
                        except Exception:
                            logging.exception("Suppressed exception")
                except Exception:
                    logging.exception("Suppressed exception")

                try:
                    path_loop = _find_sound_candidate("rotaryloop")
                    if not path_loop:
                        path_loop = os.path.join("sounds", "firearms", "universal", "rotaryloop.ogg")
                    if os.path.exists(path_loop):
                        try:
                            rotary_sound = pygame.mixer.Sound(path_loop)
                            rotary_channel = pygame.mixer.find_channel()
                            if rotary_channel:
                                rotary_channel.play(rotary_sound, loops = -1)
                                rotary_playing = True
                        except Exception:
                            rotary_channel = None
                            rotary_sound = None
                except Exception:
                    rotary_channel = None
                    rotary_sound = None
        except Exception:
            rotary_channel = None
            rotary_sound = None

        try:
            if isinstance(weapon, dict) and str(weapon.get("subtype", "")).lower() == "musket":
                musket_sound_folder = os.path.join("sounds", "firearms", "weaponsounds", "musket")
                hammer_file = os.path.join(musket_sound_folder, "hammer.ogg")
                if os.path.exists(hammer_file):
                    self._safe_sound_play("", hammer_file, block=True)
                    time.sleep(0.15)
        except Exception:
            logging.exception("Error playing musket pre-fire hammer cock")

        for i in range(actual_rounds_to_fire):

            _shot_start_time = time.perf_counter()

            next_round_for_jam = None
            try:
                if is_cylinder_sim and cylinder_capacity > 0:
                    slot = cylinder_layout[cylinder_index]
                    if isinstance(slot, dict):
                        next_round_for_jam = slot
                elif chambered and isinstance(chambered, dict):
                    next_round_for_jam = chambered
                elif is_internal and weapon.get("rounds"):
                    rr = weapon.get("rounds") or []
                    next_round_for_jam = rr[0] if rr else None
                elif loaded_mag and loaded_mag.get("rounds"):
                    rr = loaded_mag.get("rounds") or []
                    next_round_for_jam = rr[0] if rr else None
            except Exception:
                next_round_for_jam = None

            shot_jamrate = total_jamrate
            if isinstance(next_round_for_jam, dict):
                jam_modifier = _safe_float(next_round_for_jam.get("jam_modifier"), 1.0)
                if jam_modifier is not None:
                    shot_jamrate *= max(0.05, jam_modifier)

            if random.random()<shot_jamrate:
                jammed = True
                logging.info(f"Weapon jammed after {rounds_fired} rounds!")
                break

            fired_this_iteration = False
            fired_round = None
            if is_cylinder_sim and cylinder_capacity > 0:
                slot = cylinder_layout[cylinder_index]
                if isinstance(slot, dict):
                    fired_round = slot
                    fired_rounds_list.append(fired_round)

                    try:
                        self._play_firearm_sound(weapon, "fire", fired_round = fired_round)
                    except Exception:
                        self._play_firearm_sound(weapon, "fire")
                    rounds_fired +=1
                    fired_this_iteration = True
                    cylinder_layout[cylinder_index] = "__spent__"
                else:
                    self._safe_sound_play("", "sounds/firearms/universal/dryfire.ogg")
                cylinder_index = (cylinder_index + 1) % cylinder_capacity
                chambered = None
            elif chambered:
                fired_round = chambered
                fired_rounds_list.append(fired_round)

                try:

                    self._play_firearm_sound(weapon, "fire", fired_round = fired_round)
                except Exception:
                    self._play_firearm_sound(weapon, "fire")
                rounds_fired +=1
                chambered = None
                fired_this_iteration = True
            elif is_internal and weapon.get("rounds"):
                chambered = weapon["rounds"].pop(0)
                fired_round = chambered
                fired_rounds_list.append(fired_round)
                try:
                    self._play_firearm_sound(weapon, "fire", fired_round = fired_round)
                except Exception:
                    self._play_firearm_sound(weapon, "fire")
                rounds_fired +=1
                chambered = None
                fired_this_iteration = True
            elif loaded_mag and loaded_mag.get("rounds"):
                chambered = loaded_mag["rounds"].pop(0)
                fired_round = chambered
                fired_rounds_list.append(fired_round)
                try:
                    self._play_firearm_sound(weapon, "fire", fired_round = fired_round)
                except Exception:
                    self._play_firearm_sound(weapon, "fire")
                rounds_fired +=1
                fired_this_iteration = True
            else:

                logging.info("Ran out of ammo mid-burst after %s rounds", rounds_fired)
                break

            if is_cylinder_sim and cylinder_capacity > 0 and not fired_this_iteration:
                try:
                    time.sleep(0.08)
                except Exception:
                    logging.exception("Suppressed exception")
                continue

            if fired_this_iteration:

                try:
                    _has_more_rounds = bool(
                        (is_internal and weapon.get("rounds")) or
                        (loaded_mag and isinstance(loaded_mag, dict) and loaded_mag.get("rounds"))
                    )
                    if not _has_more_rounds:
                        if is_en_bloc:
                            try:
                                self._play_weapon_action_sound(weapon, "clipeject", block = False)
                            except Exception:
                                logging.exception("Suppressed exception")
                        elif weapon.get("bolt_catch"):
                            try:
                                self._safe_sound_play("", os.path.join("sounds", "firearms", "universal", "rifleboltlock.ogg"))
                            except Exception:
                                logging.exception("Suppressed exception")
                except Exception:
                    logging.exception("Suppressed exception")

                try:
                    if fired_round:

                        is_40mm = False
                        try:
                            if isinstance(fired_round, dict):
                                name = str(fired_round.get("name")or "").lower()
                                if "40x46"in name or "40mm"in name or "40 x 46"in name:
                                    is_40mm = True
                                calib = fired_round.get("caliber")
                                if calib and not is_40mm:
                                    if isinstance(calib, (list, tuple)):
                                        for c in calib:
                                            if isinstance(c, str)and "40"in c and "mm"in c:
                                                is_40mm = True
                                                break
                                    elif isinstance(calib, str)and "40"in calib and "mm"in calib:
                                        is_40mm = True

                                if not is_40mm and(str(fired_round.get("ammo_type")or "").lower()=="40mm_grenade"or str(fired_round.get("sounds")or "").lower()in("40mm_grenade", "40mm")):
                                    is_40mm = True
                        except Exception:
                            logging.exception("Error inspecting fired_round for 40mm detection")

                        if is_40mm:
                            try:
                                self._handle_40mm_post_fire_effects(weapon, fired_round)
                            except Exception:
                                logging.exception("Failed to schedule 40mm post-fire effects")
                except Exception:
                    logging.exception("Error checking fired_round for 40mm handling")

                try:
                    if isinstance(weapon, dict)and weapon.get("_ub_loaded")is not None:
                        try:
                            weapon["_ub_loaded"]= max(0, int(weapon.get("_ub_loaded", 0))-1)
                        except Exception:
                            weapon["_ub_loaded"]= 0
                        if weapon.get("_ub_loaded", 0)<=0:

                            pass
                except Exception:
                    logging.exception("Failed updating underbarrel loaded count after fire")

                try:
                    play_casing = False
                    if fired_round:
                        try:

                            is_40mm = False
                            if isinstance(fired_round, dict):
                                fname = str(fired_round.get("name")or "").lower()
                                if "40x46"in fname or "40mm"in fname or "40 x 46"in fname:
                                    is_40mm = True
                                fcal = fired_round.get("caliber")
                                if fcal and not is_40mm:
                                    if isinstance(fcal, (list, tuple)):
                                        for c in fcal:
                                            if isinstance(c, str)and "40"in c and "mm"in c:
                                                is_40mm = True
                                                break
                                    elif isinstance(fcal, str)and "40"in fcal and "mm"in fcal:
                                        is_40mm = True
                                if not is_40mm and(str(fired_round.get("ammo_type")or "").lower()=="40mm_grenade"or str(fired_round.get("sounds")or "").lower()in("40mm_grenade", "40mm")):
                                    is_40mm = True
                            if not is_40mm:
                                play_casing = True
                        except Exception:
                            logging.exception("Error detecting 40mm for casing logic")

                    if play_casing:
                        try:

                            try:
                                if str(weapon.get("type")or "").lower()=="caseless":
                                    play_casing = False
                            except Exception:
                                logging.exception("Suppressed exception")

                            try:
                                _pc_mag_type = str(weapon.get("magazinetype", "") or "").lower()
                                _pc_platform = str(weapon.get("platform", "") or "").lower()
                                if is_cylinder_sim or "cylinder" in _pc_mag_type or "break" in _pc_mag_type or "revolver" in _pc_platform:
                                    play_casing = False
                            except Exception:
                                logging.exception("Suppressed exception")

                            is_shotgun = False
                            try:

                                if isinstance(fired_round, dict):
                                    fr_name = str(fired_round.get("name")or "").lower()
                                    fr_cal = fired_round.get("caliber")
                                    fr_cal_str = ""
                                    if isinstance(fr_cal, (list, tuple)):
                                        fr_cal_str = " ".join([str(x)for x in fr_cal]).lower()
                                    elif fr_cal:
                                        fr_cal_str = str(fr_cal).lower()
                                    if "gauge"in fr_name or "gauge"in fr_cal_str or "bore"in fr_cal_str:
                                        is_shotgun = True

                                if not is_shotgun:
                                    mag_type = str(weapon.get("magazinetype", "")or "").lower()
                                    platform = str(weapon.get("platform", "")or "").lower()
                                    calib = weapon.get("caliber")or[]
                                    calib_str = " ".join([str(x)for x in calib])if isinstance(calib, (list, tuple))else str(calib)
                                    if "tube"in mag_type or "shotgun"in platform or "gauge"in calib_str.lower()or "bore"in calib_str.lower():
                                        is_shotgun = True
                            except Exception:
                                logging.exception("Suppressed exception")

                            if is_shotgun:
                                candidates = glob.glob(os.path.join("sounds", "firearms", "universal", "shelldrop*.ogg"))+glob.glob(os.path.join("sounds", "firearms", "universal", "shelldrop*.wav"))
                            else:
                                candidates = glob.glob(os.path.join("sounds", "firearms", "universal", "casing*.ogg"))+glob.glob(os.path.join("sounds", "firearms", "universal", "casing*.wav"))

                            if candidates:
                                try:
                                    self._safe_sound_play("", random.choice(candidates))
                                except Exception:
                                    logging.exception("Failed to play casing/shelldrop sound")
                        except Exception:
                            logging.exception("Error selecting/playing casing sound")
                except Exception:
                    logging.exception("Casing/shelldrop handling failed")
                if effective_is_pump:

                    time.sleep(fire_to_pump_delay)
                    self._play_weapon_action_sound(weapon, "pumpback")
                    time.sleep(pump_back_to_forward_delay)

                    if is_internal and weapon.get("rounds"):
                        chambered = weapon["rounds"].pop(0)
                    elif loaded_mag and loaded_mag.get("rounds"):
                        chambered = loaded_mag["rounds"].pop(0)
                    self._play_weapon_action_sound(weapon, "pumpforward")
                else:

                    if not is_bolt:
                        if is_internal and weapon.get("rounds"):
                            chambered = weapon["rounds"].pop(0)
                        elif loaded_mag and loaded_mag.get("rounds"):
                            chambered = loaded_mag["rounds"].pop(0)

                try:
                    is_cylinder = "cylinder"in magazine_type
                    is_break_action = "break"in magazine_type

                    if is_cylinder:
                        weapon['_cylinder_spent'] = int(weapon.get('_cylinder_spent', 0)) + 1

                    if is_break_action:
                        weapon['_break_spent'] = int(weapon.get('_break_spent', 0)) + 1

                    if is_single_action_weapon and not is_double_action_mode:
                        time.sleep(0.08)
                        try:
                            self._play_cylinder_sound(weapon, "hammerdown")
                        except Exception:
                            self._play_weapon_action_sound(weapon, "hammerdown", block = False)
                except Exception:
                    logging.exception("Error handling single-action hammer pull")
            else:

                logging.info("Ran out of ammo mid-burst after %s rounds", rounds_fired)
                break

            try:
                temp_gain = float(weapon.get("temp_gain_per_shot", weapon.get("temp_gain", None)))
            except Exception:
                temp_gain = None
            if temp_gain is None:

                temp_gain = random.uniform(5.0, 10.0)
            if self._check_weapon_suppressed(weapon):
                temp_gain *=1.5
            temperature +=temp_gain

            try:
                melt_temp = float(weapon.get("melt_temp", 3000))
            except Exception:
                melt_temp = 3000.0
            if temperature >=melt_temp and not weapon.get("gas_melted", False)and weapon.get("can_melt", True):
                weapon["gas_melted"]= True
                is_bolt = True
                logging.warning("Weapon %s gas system MELTED at %.1f°F(in-shot)", weapon.get("name", weapon_id), temperature)

            dirtiness_modifier = 1.0
            if isinstance(fired_round, dict):
                dirtiness_modifier = _safe_float(fired_round.get("dirtiness_modifier"), 1.0) or 1.0
            cleanliness -= random.uniform(0.1, 0.3) * max(0.0, dirtiness_modifier)
            cleanliness = max(0, cleanliness)

            try:
                newly_broken = _apply_part_wear(weapon, shots_fired=1, wrong_ammo=wrong_ammo_firing)

                _cal_mismatched = _get_caliber_mismatched_parts(weapon)
                if _cal_mismatched:
                    _fired_round_dia = None
                    if fired_round and isinstance(fired_round, dict):
                        _fr_cal = fired_round.get("caliber", "")
                        if isinstance(_fr_cal, list):
                            _fr_cal = _fr_cal[0] if _fr_cal else ""
                        _fired_round_dia = _parse_caliber_diameter_mm(_fr_cal)
                    for _mp in (weapon.get("parts") or []):
                        if not isinstance(_mp, dict) or id(_mp) not in _cal_mismatched:
                            continue
                        if _mp.get("type") == "barrel" and _fired_round_dia is not None:
                            _barrel_cur = _mp.get("current")
                            _barrel_cals = _barrel_cur.get("caliber") if isinstance(_barrel_cur, dict) else None
                            if _barrel_cals:
                                if isinstance(_barrel_cals, str):
                                    _barrel_cals = [_barrel_cals]
                                _barrel_dias = [_parse_caliber_diameter_mm(c) for c in _barrel_cals if isinstance(c, str)]
                                _barrel_dias = [d for d in _barrel_dias if d is not None]
                                _barrel_dia = max(_barrel_dias) if _barrel_dias else None
                                if _barrel_dia is not None and _fired_round_dia < _barrel_dia:
                                    _dia_ratio = _barrel_dia / _fired_round_dia
                                    _heavy_wear = PART_DURABILITY_PER_SHOT.get("barrel", 0.15) * _dia_ratio * 25.0
                                    _bbl_dur = _mp.get("current_durability")
                                    try:
                                        _bbl_dur = float(_bbl_dur)
                                    except (ValueError, TypeError):
                                        _bbl_dur = 0
                                    _bbl_dur = max(0, _bbl_dur - _heavy_wear)
                                    _mp["current_durability"] = _bbl_dur
                                    if _bbl_dur <= 0:
                                        _mp["broken"] = True
                                        if _mp not in newly_broken:
                                            newly_broken.append(_mp)
                                    logging.warning("Undersized round (%.2fmm) in barrel (%.2fmm) - heavy wear: %.2f, ratio: %.2f",
                                                    _fired_round_dia, _barrel_dia, _heavy_wear, _dia_ratio)
                                    continue
                        _mp["current_durability"] = 0
                        _mp["broken"] = True
                        if _mp not in newly_broken:
                            newly_broken.append(_mp)
                        logging.warning("Caliber-incompatible part destroyed on firing: %s (%s)", _mp.get("name"), _mp.get("type"))

                if newly_broken:
                    for bp in newly_broken:
                        logging.warning("Part worn out during firing: %s (%s)", bp.get("name"), bp.get("type"))
                    can_still_fire, reason = _check_weapon_can_fire(weapon)
                    if not can_still_fire:
                        logging.info("Weapon can no longer fire due to part failure: %s", reason)
                        rounds_fired += 0
                        jammed = False
                        weapon["chambered"] = chambered
                        weapon["loaded"] = loaded_mag
                        combat_state.setdefault("barrel_temperatures", {})[weapon_id] = temperature
                        combat_state.setdefault("barrel_cleanliness", {})[weapon_id] = cleanliness
                        part_names = ", ".join(bp.get("name", bp.get("type", "unknown")) for bp in newly_broken)
                        return f"Fired {rounds_fired} round(s) - PART FAILURE! {part_names} worn out. {reason}"
                    pe = _get_weapon_part_effects(weapon)
                    if pe.get("force_manual_action") and not weapon.get("gas_melted"):
                        weapon["gas_melted"] = True
                        is_bolt = True
                    if pe.get("inconsistent_feeding") and random.random() < 0.35:
                        is_bolt = True
            except Exception:
                logging.exception("Error applying part wear")

            try:
                if loaded_mag and isinstance(loaded_mag, dict):
                    _sd_fire = loaded_mag.get("spring_durability")
                    if _sd_fire is not None:
                        try:
                            _sd_fire = float(_sd_fire)
                            _sd_fire = max(0.0, _sd_fire - random.uniform(0.02, 0.06))
                            loaded_mag["spring_durability"] = round(_sd_fire, 4)
                        except (ValueError, TypeError):
                            logging.exception("Suppressed exception")
            except Exception:
                logging.exception("Suppressed exception")

            _shot_elapsed = time.perf_counter() - _shot_start_time

            if is_bolt:

                pass
            elif is_semi:

                _semi_target = base_delay +0.18
                _semi_remaining = _semi_target - _shot_elapsed
                if _semi_remaining >0:
                    time.sleep(_semi_remaining)
            elif is_burst:

                shots_in_burst =(i +1)%burst_count
                if shots_in_burst ==0 and i +1 <actual_rounds_to_fire:

                    _burst_pause_remaining = burst_pause - _shot_elapsed
                    if _burst_pause_remaining >0:
                        time.sleep(_burst_pause_remaining)
                else:

                    _burst_remaining = burst_base_delay - _shot_elapsed
                    if _burst_remaining >0:
                        time.sleep(_burst_remaining)
            else:

                _auto_remaining = base_delay - _shot_elapsed
                if _auto_remaining >0:
                    time.sleep(_auto_remaining)

        try:
            if rotary_playing and rotary_channel:
                try:
                    rotary_channel.stop()
                except Exception:
                    logging.exception("Suppressed exception")

                try:
                    def _find_winddown():
                        try:
                            fs = weapon.get("fire_sounds")or weapon.get("sounds")or weapon.get("sound_folder")or weapon.get("reload_sounds")
                        except Exception:
                            fs = None
                        cand_list =[]
                        if fs:
                            wf = os.path.join("sounds", "firearms", str(fs).lower())
                            cand_list +=glob.glob(os.path.join(wf, "rotarywinddown*.ogg"))+glob.glob(os.path.join(wf, "rotarywinddown*.wav"))
                            wf2 = os.path.join("sounds", "firearms", "weaponsounds", str(fs).lower().replace('/', '_'))
                            cand_list +=glob.glob(os.path.join(wf2, "rotarywinddown*.ogg"))+glob.glob(os.path.join(wf2, "rotarywinddown*.wav"))

                        try:
                            plat = str(weapon.get("platform")or "").lower().replace('/', '_')
                        except Exception:
                            plat = None
                        if plat:
                            wf3 = os.path.join("sounds", "firearms", "weaponsounds", plat)
                            cand_list +=glob.glob(os.path.join(wf3, "rotarywinddown*.ogg"))+glob.glob(os.path.join(wf3, "rotarywinddown*.wav"))

                        uni = os.path.join("sounds", "firearms", "universal")
                        cand_list +=glob.glob(os.path.join(uni, "rotarywinddown*.ogg"))+glob.glob(os.path.join(uni, "rotarywinddown*.wav"))

                        return cand_list[0]if cand_list else None

                    winddown_path = _find_winddown()
                    if winddown_path:
                        try:
                            self._safe_sound_play("", winddown_path, block = True)
                        except Exception:
                            logging.exception("Suppressed exception")
                    else:
                        try:
                            self._safe_sound_play("", os.path.join("sounds", "firearms", "universal", "rotarywinddown.ogg"), block = True)
                        except Exception:
                            logging.exception("Suppressed exception")
                except Exception:
                    try:
                        self._safe_sound_play("", os.path.join("sounds", "firearms", "universal", "rotarywinddown.ogg"), block = True)
                    except Exception:
                        logging.exception("Suppressed exception")
        except Exception:
            logging.exception("Suppressed exception")

        if is_cylinder_sim and cylinder_capacity > 0:
            weapon["_cylinder_layout"] = [slot if isinstance(slot, dict) else ("__spent__" if slot == "__spent__" else None) for slot in cylinder_layout]
            weapon["_cylinder_index"] = int(cylinder_index)
            weapon["_cylinder_spent"] = sum(1 for slot in cylinder_layout if slot == "__spent__")
            weapon["rounds"] = [slot for slot in cylinder_layout if isinstance(slot, dict)]
            chambered = None

        weapon["chambered"]= chambered
        weapon["loaded"]= loaded_mag

        if "barrel_temperatures"not in combat_state:
            combat_state["barrel_temperatures"]= {}
        if "barrel_cleanliness"not in combat_state:
            combat_state["barrel_cleanliness"]= {}
        if "weapon_last_used"not in combat_state:
            combat_state["weapon_last_used"]= {}

        try:
            melt_temp = float(weapon.get("melt_temp", 3000))
        except Exception:
            melt_temp = 3000.0
        if temperature >=melt_temp and weapon.get("can_melt", True):
            weapon["gas_melted"]= True
            logging.warning("Weapon %s gas system MELTED at %.1f°F", weapon.get("name", weapon_id), temperature)

        combat_state["barrel_temperatures"][weapon_id]= temperature
        combat_state["barrel_cleanliness"][weapon_id]= cleanliness
        weapon["barrel_cleanliness"] = cleanliness
        combat_state["weapon_last_used"][weapon_id]= time.time()

        if is_bolt and rounds_fired >0 and not jammed:

            time.sleep(0.28)

            try:
                if is_internal:
                    if weapon.get("rounds"):
                        next_round = weapon["rounds"].pop(0)
                        weapon["chambered"]= next_round
                        cycle_result = "next round automatically chambered"
                    else:
                        weapon["chambered"]= None
                        cycle_result = "bolt cycled(no rounds left to chamber)"
                else:
                    if loaded_mag and loaded_mag.get("rounds"):
                        next_round = loaded_mag["rounds"].pop(0)
                        weapon["chambered"]= next_round
                        cycle_result = "next round automatically chambered"
                    else:
                        weapon["chambered"]= None
                        cycle_result = "bolt cycled(no rounds left to chamber)"
            except Exception:
                cycle_result = None

            try:
                if weapon.get("gas_melted", False):

                    self._cycle_bolt_sounds(weapon, single_forward = False, delay = 0.0)
                else:

                    if weapon.get("chambered")is None:

                        if bool(weapon.get("bolt_catch", False)):
                            try:
                                self._play_weapon_action_sound(weapon, "boltforward")
                            except Exception:
                                logging.exception("Suppressed exception")
                    else:

                        self._cycle_bolt_sounds(weapon, single_forward = False, delay = 0.12)
            except Exception:
                try:

                    self._cycle_bolt_sounds(weapon, single_forward = False, delay = 0.12)
                except Exception:
                    logging.exception("Suppressed exception")
        else:
            cycle_result = None

        if rounds_fired >0:
            rolls, median = self._roll_d20_dice(rounds_fired)
            weapon_name = weapon.get("name", "Unknown")
            caliber_list = weapon.get("caliber", [])or["Unknown"]
            if isinstance(caliber_list, str):
                caliber_list = [caliber_list]
            caliber = caliber_list[0] if caliber_list else "Unknown"

            variant = "Unknown"
            src_round_for_display = None

            def _cal_from_round_name(name_val):
                try:
                    nm = str(name_val or "").strip()
                    if not nm:
                        return None
                    if " | " in nm:
                        left = nm.split(" | ", 1)[0].strip()
                        return left or None
                    if " - " in nm:
                        left = nm.split(" - ", 1)[0].strip()
                        return left or None
                except Exception:
                    return None
                return None

            if fired_rounds_list:
                _fr0 = fired_rounds_list[0]
                src_round_for_display = _fr0
                if isinstance(_fr0, dict):
                    variant = _fr0.get("variant") or _fr0.get("name") or "Unknown"
                    _fr_name_cal = _cal_from_round_name(_fr0.get("name"))
                    if _fr_name_cal:
                        caliber = _fr_name_cal
                    _fr_cal = _fr0.get("caliber")
                    if isinstance(_fr_cal, list):
                        _fr_cal = _fr_cal[0] if _fr_cal else None
                    if _fr_cal:
                        caliber = _fr_cal
                elif isinstance(_fr0, str) and " | " in _fr0:
                    _parts = _fr0.split(" | ", 1)
                    if _parts and _parts[0].strip():
                        caliber = _parts[0].strip()
                    variant = _fr0.split(" | ")[1]
            elif chambered and isinstance(chambered, dict):
                src_round_for_display = chambered
                variant = chambered.get("variant", "Unknown")
                _ch_cal = chambered.get("caliber")
                if isinstance(_ch_cal, list):
                    _ch_cal = _ch_cal[0] if _ch_cal else None
                if _ch_cal:
                    caliber = _ch_cal
            elif loaded_mag and loaded_mag.get("rounds"):
                first_round = loaded_mag["rounds"][0]
                src_round_for_display = first_round
                if isinstance(first_round, dict):
                    variant = first_round.get("variant", "Unknown")
                    _lr_name_cal = _cal_from_round_name(first_round.get("name"))
                    if _lr_name_cal:
                        caliber = _lr_name_cal
                    _lr_cal = first_round.get("caliber")
                    if isinstance(_lr_cal, list):
                        _lr_cal = _lr_cal[0] if _lr_cal else None
                    if _lr_cal:
                        caliber = _lr_cal
                elif isinstance(first_round, str)and " | "in first_round:
                    _parts = first_round.split(" | ", 1)
                    if _parts and _parts[0].strip():
                        caliber = _parts[0].strip()
                    variant = first_round.split(" | ")[1]

            elif chambered and isinstance(chambered, str)and " | "in chambered:
                _parts = chambered.split(" | ", 1)
                if _parts and _parts[0].strip():
                    caliber = _parts[0].strip()
                variant = chambered.split(" | ")[1]

            effective_aim = 0
            try:

                if save_data and isinstance(save_data, dict):
                    sd_stats = save_data.get("stats", {})or {}
                    if isinstance(sd_stats, dict):
                        if "Aim"in sd_stats:
                            effective_aim +=float(sd_stats.get("Aim", 0)or 0)
                        else:

                            effective_aim +=float(sd_stats.get("aim", 0)or 0)
                    effective_aim += float(self._get_temporary_aim_modifier(save_data))
            except Exception:
                logging.exception("Suppressed exception")
            try:

                if isinstance(weapon, dict):
                    mods = weapon.get("_active_modifiers", {})or {}
                    stats_mods = mods.get("stats", {})if isinstance(mods, dict)else {}
                    if isinstance(stats_mods, dict):
                        effective_aim +=float(stats_mods.get("aim", 0)or 0)

                    wstats = weapon.get("stats", {})or {}
                    if isinstance(wstats, dict):
                        effective_aim +=float(wstats.get("aim", 0)or 0)
            except Exception:
                logging.exception("Suppressed exception")

            try:
                pe_aim = _get_weapon_part_effects(weapon)
                effective_aim += pe_aim.get("aim_debuff", 0)
            except Exception:
                logging.exception("Suppressed exception")

            try:
                if isinstance(weapon, dict) and str(weapon.get("subtype", "")).lower() == "musket":
                    if not weapon.get("rifling", False):
                        effective_aim -= 5
            except Exception:
                logging.exception("Suppressed exception")

            try:
                if not combat_state.get("indoors"):
                    w_weather = combat_state.get("weather", {})
                    w_type = w_weather.get("weather", "clear") if isinstance(w_weather, dict) else "clear"
                    weather_aim_map = {"rain": -1, "hard_rain": -2, "thunderstorm": -1, "thunder_hard_rain": -2, "thunder": -1, "snowstorm": -2, "thundersnow": -2}
                    if w_type in weather_aim_map:
                        effective_aim += weather_aim_map[w_type]
                    w_sev = w_weather.get("wind_severity", 0) if isinstance(w_weather, dict) else 0
                    if w_sev > 0:
                        effective_aim -= max(1, min(3, w_sev))
            except Exception:
                logging.exception("Suppressed exception")

            try:
                fired_round_for_bonus = fired_rounds_list[0] if fired_rounds_list else chambered
                if not fired_round_for_bonus and loaded_mag and loaded_mag.get("rounds"):
                    fired_round_for_bonus = loaded_mag["rounds"][0]if loaded_mag["rounds"]else None

                if fired_round_for_bonus and isinstance(fired_round_for_bonus, dict):
                    round_mods = fired_round_for_bonus.get("modifiers", {})or {}
                    if isinstance(round_mods, dict):
                        round_stats = round_mods.get("stats", {})or {}
                        if isinstance(round_stats, dict):
                            effective_aim +=float(round_stats.get("aim", 0)or 0)
            except Exception:
                logging.exception("Suppressed exception")

            try:
                pre_clamp_aim = effective_aim
                clamp_val = None

                try:
                    if isinstance(weapon, dict)and weapon.get("bonus_clamp")is not None:
                        clamp_val = float(weapon.get("bonus_clamp"))
                except Exception:
                    clamp_val = None

                if clamp_val is None:
                    try:
                        current_tbl = global_variables.get('current_table')
                        if current_tbl:
                            tbl_path = os.path.join("tables", current_tbl)
                        else:
                            tbl_path = os.path.join("tables", sorted(glob.glob(os.path.join("tables", "*.sldtbl")))[0])if glob.glob(os.path.join("tables", "*.sldtbl"))else None
                        if tbl_path and os.path.exists(tbl_path):
                            with open(tbl_path, 'r', encoding = 'utf-8')as tf:
                                import json as _json
                                tdata = _json.load(tf)
                                clamp_val = tdata.get('additional_settings', {}).get('bonus_clamp')
                    except Exception:
                        clamp_val = None

                applied_clamp = False
                if clamp_val is not None:
                    try:
                        clamp_num = float(clamp_val)
                        if effective_aim >clamp_num:
                            effective_aim = clamp_num
                            applied_clamp = True
                    except Exception:
                        applied_clamp = False
                final_total = int(median)+int(round(effective_aim))
            except Exception:
                final_total = median

            round_display = str(caliber)
            try:

                if isinstance(variant, dict):
                    vname = variant.get("name")or variant.get("variant")or variant.get("variant_name")
                    if vname:
                        round_display = f"{caliber} {vname}"

                elif isinstance(variant, (list, tuple)):
                    try:
                        parts =[str(x).strip()for x in variant if x is not None]
                        if parts:
                            round_display = f"{caliber} {' '.join(parts)}"
                    except Exception:
                        logging.exception("Suppressed exception")
                elif isinstance(variant, str)and variant and variant !="Unknown":
                    maybe = variant.strip()

                    try:
                        simple = True

                        for ch in "{}[](), '\"":
                            if ch in maybe:
                                simple = False
                                break

                        if "caliber"in maybe.lower()or "variant"in maybe.lower():
                            simple = False
                        if simple and maybe:
                            round_display = f"{caliber} {maybe}"

                            maybe = None
                    except Exception:
                        logging.exception("Suppressed exception")
                    if not maybe:

                        pass
                    else:
                        parsed = None
                    parsed = None

                    if maybe[0]in("{", "[", "("):
                        try:
                            import ast as _ast
                            parsed = _ast.literal_eval(maybe)
                        except Exception:
                            parsed = None
                    if isinstance(parsed, dict):
                        vname = parsed.get("name")or parsed.get("variant")or parsed.get("variant_name")
                        if vname:
                            round_display = f"{caliber} {vname}"
                        elif parsed.get("caliber")and parsed.get("variant"):
                            round_display = f"{parsed.get('caliber')} {parsed.get('variant')}"
                    elif isinstance(parsed, (list, tuple)):
                        try:
                            parts =[str(x).strip()for x in parsed if x is not None]
                            if parts:
                                round_display = f"{caliber} {' '.join(parts)}"
                        except Exception:
                            logging.exception("Suppressed exception")
                    else:

                        try:
                            import re as _re
                            m = _re.search(r"variant\s*[:=]\s*['\"]([^'\"]+)['\"]", maybe, _re.IGNORECASE)
                            if m:
                                round_display = f"{caliber} {m.group(1)}"
                            else:

                                cleaned = maybe
                        except Exception:
                            cleaned = maybe

                        if(cleaned.startswith("{")and cleaned.endswith("}"))or(cleaned.startswith("[")and cleaned.endswith("]"))or(cleaned.startswith("(")and cleaned.endswith(")")):
                            cleaned = cleaned[1:-1]

                        parts =[p.strip().strip("'\"")for p in cleaned.split(", ")if p.strip()]
                        if len(parts)==1:
                            if parts[0]:
                                round_display = f"{caliber} {parts[0]}"
                        elif len(parts)>=2:

                            candidate = parts[-1]
                            try:
                                import re as _re

                                m = _re.search(r"['\"]([^'\"]+)['\"]", candidate)
                                if m:
                                    candidate = m.group(1)
                                else:

                                    m2 = _re.search(r"variant\s*[:=]\s*([^,}\)\]]+)", candidate, _re.IGNORECASE)
                                    if m2:
                                        candidate = m2.group(1).strip().strip("'\"{}[]() ")
                                    else:

                                        candidate = candidate.strip().strip("'\"{}[]() ")
                            except Exception:
                                candidate = candidate.strip().strip("'\"{}[]() ")
                            round_display = f"{caliber} {candidate}"
            except Exception:
                logging.exception("Suppressed exception")

            try:
                import re as _re

                round_display = _re.sub(r"[\s:|]+$", "", round_display)

                round_display = _re.sub(r"\s+", " ", round_display).strip()
            except Exception:
                try:
                    round_display = round_display.strip()
                except Exception:
                    logging.exception("Suppressed exception")

            try:
                if round_display ==str(caliber):
                    current_tbl = global_variables.get('current_table')
                    if current_tbl:
                        tbl_path = os.path.join("tables", current_tbl)
                    else:
                        tbl_path = os.path.join("tables", sorted(glob.glob(os.path.join("tables", "*.sldtbl")))[0])if glob.glob(os.path.join("tables", "*.sldtbl"))else None
                    if tbl_path and os.path.exists(tbl_path):
                        try:
                            with open(tbl_path, 'r', encoding = 'utf-8')as tf:
                                import json as _json
                                tdata = _json.load(tf)
                                ammo_arr = tdata.get('tables', {}).get('ammunition', [])
                                for a in ammo_arr:
                                    try:
                                        if a.get('caliber')==caliber:
                                            variants = a.get('variants')or[]
                                            if variants and isinstance(variants, list):
                                                first = variants[0]
                                                if isinstance(first, dict)and first.get('name'):
                                                    round_display = f"{caliber} {first.get('name')}"
                                                    break
                                                elif isinstance(first, str)and first:
                                                    round_display = f"{caliber} {first}"
                                                    break
                                    except Exception:
                                        logging.exception("Suppressed exception")
                                        continue
                        except Exception:
                            logging.exception("Suppressed exception")
            except Exception:
                logging.exception("Suppressed exception")

            # Resolve display fields for fired ammo. Prefer authoritative variant data from table
            # to avoid stale per-round snapshots (e.g. showing old NIJ-only pen text).
            pen_val = None
            type_val = None
            round_labels = []
            try:
                src_round = None
                try:
                    if fired_rounds_list:
                        src_round = fired_rounds_list[0]
                    elif chambered and isinstance(chambered, dict):
                        src_round = chambered
                    elif loaded_mag and loaded_mag.get('rounds'):
                        src_round = loaded_mag['rounds'][0]
                except Exception:
                    src_round = None

                src_variant_name = None
                src_caliber = caliber
                if isinstance(src_round, dict):
                    try:
                        _sv = src_round.get('variant')
                        if _sv:
                            src_variant_name = str(_sv).strip()
                    except Exception:
                        logging.exception("Suppressed exception")
                    try:
                        _sc = src_round.get('caliber')
                        if isinstance(_sc, list):
                            _sc = _sc[0] if _sc else None
                        if _sc:
                            src_caliber = _sc
                    except Exception:
                        logging.exception("Suppressed exception")
                    try:
                        _rncal = _cal_from_round_name(src_round.get('name'))
                        if _rncal:
                            src_caliber = _rncal
                    except Exception:
                        logging.exception("Suppressed exception")
                    if not src_variant_name:
                        try:
                            _rn = str(src_round.get('name') or '')
                            if ' | ' in _rn:
                                src_variant_name = _rn.split(' | ', 1)[1].strip()
                        except Exception:
                            logging.exception("Suppressed exception")

                if isinstance(src_round, dict):
                    pen_val = src_round.get('pen')
                    if pen_val is None:
                        v = src_round.get('variant')
                        if isinstance(v, dict):
                            pen_val = v.get('pen')
                    type_val = src_round.get('type')
                    _rl = src_round.get('ammo_labels')
                    if isinstance(_rl, list):
                        round_labels = [str(x) for x in _rl if x]

                elif isinstance(src_round, str):
                    var_name = None
                    if ' | ' in src_round:
                        parts = src_round.split(' | ')
                        if len(parts) > 1:
                            var_name = parts[1]
                    elif isinstance(variant, str) and variant and variant != 'Unknown':
                        var_name = variant

                    src_variant_name = var_name

                    if var_name:
                        try:
                            current_tbl = global_variables.get('current_table')
                            if current_tbl:
                                tbl_path = os.path.join('tables', current_tbl)
                            else:
                                tbl_path = os.path.join('tables', sorted(glob.glob(os.path.join('tables', '*.sldtbl')))[0]) if glob.glob(os.path.join('tables', '*.sldtbl')) else None
                            if tbl_path and os.path.exists(tbl_path):
                                with open(tbl_path, 'r', encoding='utf-8') as tf:
                                    import json as _json
                                    tdata = _json.load(tf)
                                    ammo_arr = tdata.get('tables', {}).get('ammunition', [])
                                    for a in ammo_arr:
                                        try:
                                            if a.get('caliber') == caliber:
                                                variants = a.get('variants') or []
                                                for var in variants:
                                                    if isinstance(var, dict):
                                                        vname = var.get('name') or var.get('variant') or var.get('variant_name')
                                                        if vname and str(vname).strip() == str(var_name).strip():
                                                            pen_val = var.get('pen')
                                                            if not type_val:
                                                                type_val = var.get('type')
                                                            if not round_labels:
                                                                _lbl = _get_ammo_variant_labels(var)
                                                                if _lbl:
                                                                    round_labels = [str(x) for x in _lbl if x]
                                                            break
                                                if pen_val is not None:
                                                    break
                                        except Exception:
                                            logging.exception("Suppressed exception")
                                            continue
                        except Exception:
                            logging.exception("Suppressed exception")

                # If we have a variant name, refresh display fields from the best matching table
                # variant entry. This preserves detailed pen strings like "IV+ (34mm RHA)"
                # and avoids defaulting to the first weapon caliber alias.
                if src_variant_name:
                    try:
                        current_tbl = global_variables.get('current_table')
                        if current_tbl:
                            tbl_path = os.path.join('tables', current_tbl)
                        else:
                            tbl_path = os.path.join('tables', sorted(glob.glob(os.path.join('tables', '*.sldtbl')))[0]) if glob.glob(os.path.join('tables', '*.sldtbl')) else None
                        if tbl_path and os.path.exists(tbl_path):
                            with open(tbl_path, 'r', encoding='utf-8') as tf:
                                import json as _json
                                tdata = _json.load(tf)
                                ammo_arr = tdata.get('tables', {}).get('ammunition', [])
                                def _norm_cal_set(v):
                                    out = set()
                                    if isinstance(v, list):
                                        for x in v:
                                            if x is not None:
                                                out.add(str(x).strip().lower())
                                    elif v is not None:
                                        out.add(str(v).strip().lower())
                                    return out

                                src_cal_set = _norm_cal_set(src_caliber)
                                weapon_cal_set = _norm_cal_set(caliber_list)
                                best_match = None
                                best_score = -1

                                for a in ammo_arr:
                                    try:
                                        variants = a.get('variants') or []
                                        entry_cal_set = _norm_cal_set(a.get('caliber'))
                                        entry_name = str(a.get('name') or '').strip().lower()
                                        for var in variants:
                                            if not isinstance(var, dict):
                                                continue
                                            vname = var.get('name') or var.get('variant') or var.get('variant_name')
                                            if not(vname and str(vname).strip() == str(src_variant_name).strip()):
                                                continue

                                            score = 1
                                            if src_cal_set and entry_cal_set and src_cal_set.intersection(entry_cal_set):
                                                score += 8
                                            if weapon_cal_set and entry_cal_set and weapon_cal_set.intersection(entry_cal_set):
                                                score += 3
                                            if isinstance(src_round, dict):
                                                _sn = str(src_round.get('name') or '').lower()
                                                if _sn:
                                                    for ec in entry_cal_set:
                                                        if ec and ec in _sn:
                                                            score += 2
                                                            break
                                                    if entry_name and entry_name in _sn:
                                                        score += 6
                                                    elif entry_name:
                                                        # Light fuzzy boost if many entry words appear in round name.
                                                        _hit_words = 0
                                                        for _w in entry_name.replace('-', ' ').split():
                                                            if len(_w) >= 4 and _w in _sn:
                                                                _hit_words += 1
                                                        score += min(3, _hit_words)

                                            if score > best_score:
                                                best_score = score
                                                best_match = var
                                    except Exception:
                                        logging.exception("Suppressed exception")
                                        continue

                                if isinstance(best_match, dict):
                                    if best_match.get('pen') not in (None, ''):
                                        pen_val = best_match.get('pen')
                                    if best_match.get('type') not in (None, ''):
                                        type_val = best_match.get('type')
                                    _lbl = _get_ammo_variant_labels(best_match)
                                    if _lbl:
                                        round_labels = [str(x) for x in _lbl if x]
                    except StopIteration:
                        logging.exception("Suppressed exception")
                    except Exception:
                        logging.exception("Suppressed exception")
            except Exception:
                pen_val = None

            try:
                detail_bits = []
                if type_val is not None and str(type_val).strip() != '':
                    detail_bits.append(f"Type: {type_val}")
                if pen_val is not None and str(pen_val).strip() != '':
                    detail_bits.append(f"Pen: {pen_val}")
                if round_labels:
                    detail_bits.extend(round_labels)
                if detail_bits:
                    round_display = f"{round_display} ({' | '.join(detail_bits)})"
            except Exception:
                logging.exception("Suppressed exception")

            is_suppressed = self._check_weapon_suppressed(weapon)
            suppressed_tag = " | Suppressed"if is_suppressed else ""
            clipboard_text = f"Roll: {final_total} | Weapon: {weapon_name} | Round: {round_display} | {rounds_fired} rounds fired{suppressed_tag}"
            self._copy_to_clipboard(clipboard_text)
            logging.info(f"D20 rolls: {rolls}, Rounded avg: {median}")

            try:
                sd_ref = save_data if isinstance(save_data, dict)else globals().get('save_data')or getattr(self, '_current_save_data', None)
                if isinstance(sd_ref, dict):
                    ts = sd_ref.setdefault('tracked_stats', {})
                    if isinstance(ts, dict):
                        ts['rounds_fired_total']= int(ts.get('rounds_fired_total', 0))+int(rounds_fired)
                        try:
                            tbl = globals().get('table_data') or {}
                            if tbl.get('additional_settings', {}).get('hardcore_mode', False):
                                weapon['rounds_fired'] = int(weapon.get('rounds_fired', 0)) + int(rounds_fired)
                        except Exception:
                            logging.exception("Suppressed exception")
                        ts['d20_rolls_total']= int(ts.get('d20_rolls_total', 0))+len(rolls)
                        ts['d20_ones']= int(ts.get('d20_ones', 0))+sum(1 for r in rolls if r ==1)
                        ts['d20_twenties']= int(ts.get('d20_twenties', 0))+sum(1 for r in rolls if r ==20)
                        hist = ts.setdefault('d20_roll_history', [])
                        try:
                            hist.append({'weapon_id':weapon_id, 'rolls':rolls, 'time':time.time()})
                        except Exception:
                            logging.exception("Suppressed exception")
            except Exception:
                logging.exception('Failed updating tracked_stats after firing')

            try:
                sd_ref2 = save_data if isinstance(save_data, dict)else globals().get('save_data')or getattr(self, '_current_save_data', None)
                fired_round_ref = None
                try:
                    fired_round_ref = fired_rounds_list[0] if fired_rounds_list else fired_round
                except Exception:
                    logging.exception("Suppressed exception")
                if fired_round_ref is None:
                    try:
                        if chambered and isinstance(chambered, dict):
                            fired_round_ref = chambered
                    except Exception:
                        logging.exception("Suppressed exception")
                self._update_session_fire_stats(sd_ref2, rounds_fired, rolls, fired_round = fired_round_ref)
            except Exception:
                logging.exception('Failed updating session fire stats')

            try:
                popup_lines =[
                f"Base roll(rounded avg): {median}",
                f"Aim modifier: {int(round(effective_aim))}",
                f"Final total: {final_total}",
                f"Weapon: {weapon_name}",
                f"Round: {round_display}",
                f"Rounds fired: {rounds_fired}"
                ]
                try:
                    if 'applied_clamp'in locals()and applied_clamp:
                        popup_lines.insert(2, f"Modifier clamp applied: +{int(clamp_num)}(was {int(round(pre_clamp_aim))})")
                except Exception:
                    logging.exception("Suppressed exception")
                roll_summary_text = "\n".join(popup_lines)
            except Exception:
                roll_summary_text = None

        if jammed:

            import random as _rand

            jam_cause_parts = []
            if temp_mult > 1.1:
                jam_cause_parts.append(f"Overheated barrel ({temperature:.0f}\u00b0F)")
            if clean_mult > 1.1:
                jam_cause_parts.append(f"Dirty weapon ({cleanliness:.0f}% clean)")
            if mag_reliability_mult > 1.2:
                jam_cause_parts.append("Poor magazine/spring condition")
            if part_jam_mult > 1.15:
                if low_durability_jam_parts:
                    jam_cause_parts.append("Worn weapon parts: " + ", ".join(low_durability_jam_parts[:3]))
                else:
                    jam_cause_parts.append("Worn weapon parts")
            if base_jamrate >= 0.03:
                jam_cause_parts.append("Low weapon reliability")
            if not jam_cause_parts:
                jam_cause_parts.append("Random malfunction")
            jam_cause_text = "Jam cause: " + ", ".join(jam_cause_parts)

            if loaded_mag and isinstance(loaded_mag, dict)and loaded_mag.get("magazinetype"):
                magazine_type = str(loaded_mag.get("magazinetype", "")or "").lower()
            else:
                magazine_type = str(weapon.get("magazinetype", "")or "").lower()

            sub_mag = str(weapon.get("submagazinetype", "")or "").lower()

            weapon_platform = str(weapon.get("platform", "")or "").lower()
            if weapon.get("infinite_ammo")and not loaded_mag:

                has_detachable_mag = "box"in magazine_type and not any(k in magazine_type for k in("internal", "tube", "cylinder"))and "revolver"not in weapon_platform
            else:
                has_detachable_mag = bool(loaded_mag)and not any(k in magazine_type for k in("internal", "tube", "cylinder"))and "revolver"not in weapon_platform

            progress = None
            try:
                progress = self._create_action_minigame_popup("Clearing Jam", jam_cause_text, key_count = 7)
            except Exception:
                progress = None

            try:
                if has_detachable_mag:
                    if progress:
                        progress["update"]("Dropping magazine...")

                    try:
                        mag_type_rt =(weapon.get("magazinetype", "")or "").lower()
                        plat_rt =(weapon.get("platform", "")or "").lower()
                        mag_type_rt =(weapon.get("magazinetype", "")or "").lower()
                        plat_rt =(weapon.get("platform", "")or "").lower()
                        _dualfeed_has_mag_jc = weapon.get("dualfeed") and isinstance(loaded_mag, dict) and loaded_mag
                        is_belt_rt =(("belt"in mag_type_rt)or("belt"in plat_rt)or("m249"in plat_rt)) and not _dualfeed_has_mag_jc
                        if is_belt_rt:
                            if weapon.get("dualfeed")and(weapon.get("submagazinesystem")or weapon.get("submagazinetype")):
                                self._perform_dualfeed_belt_reload_sequence(weapon)
                            else:
                                self._perform_belt_reload_sequence(weapon)
                        else:
                            self._play_weapon_action_sound(weapon, "magout")
                    except Exception:

                        try:
                            self._play_weapon_action_sound(weapon, "magout")
                        except Exception:
                            logging.exception("Suppressed exception")

                _mg_completed = progress["completed"] if progress else None
                _mg_set_progress = progress.get("set_progress") if progress else None

                if progress:
                    progress["update"]("Waiting...")
                if _mg_completed:
                    self._interruptible_wait(_mg_completed, _rand.uniform(3.0, 4.5), progress_callback = _mg_set_progress)
                else:
                    time.sleep(_rand.uniform(3.0, 4.5))

                if progress:
                    if is_pump:
                        progress["update"]("Pumping action back...")
                    else:
                        progress["update"]("Racking bolt back...")

                if is_pump:
                    self._play_weapon_action_sound(weapon, "pumpback")
                else:

                    self._cycle_bolt_sounds(weapon, single_forward = False, delay = 0.1)

                time.sleep(0.1)

                if progress:
                    if is_pump:
                        progress["update"]("Pumping action forward...")
                    else:
                        progress["update"]("Racking bolt forward...")

                if is_pump:
                    self._play_weapon_action_sound(weapon, "pumpforward")
                else:

                    pass

                if progress:
                    progress["update"]("Waiting...")
                if _mg_completed:
                    self._interruptible_wait(_mg_completed, _rand.uniform(8.0, 12.0), progress_callback = _mg_set_progress)
                else:
                    time.sleep(_rand.uniform(8.0, 12.0))

                if has_detachable_mag:
                    if progress:
                        progress["update"]("Inserting magazine...")
                    try:
                        mag_type_rt =(weapon.get("magazinetype", "")or "").lower()
                        plat_rt =(weapon.get("platform", "")or "").lower()
                        mag_type_rt =(weapon.get("magazinetype", "")or "").lower()
                        plat_rt =(weapon.get("platform", "")or "").lower()
                        _dualfeed_has_mag_jc2 = weapon.get("dualfeed") and isinstance(loaded_mag, dict) and loaded_mag
                        is_belt_rt =(("belt"in mag_type_rt)or("belt"in plat_rt)or("m249"in plat_rt)) and not _dualfeed_has_mag_jc2
                        if is_belt_rt:
                            if weapon.get("dualfeed")and(weapon.get("submagazinesystem")or weapon.get("submagazinetype")):
                                self._perform_dualfeed_belt_reload_sequence(weapon)
                            else:
                                self._perform_belt_reload_sequence(weapon)
                        else:
                            self._play_weapon_action_sound(weapon, "magin")
                    except Exception:
                        logging.exception("Suppressed exception")

                if progress:
                    progress["update"]("Waiting...")
                if _mg_completed:
                    self._interruptible_wait(_mg_completed, _rand.uniform(2.5, 4.0), progress_callback = _mg_set_progress)
                else:
                    time.sleep(_rand.uniform(2.5, 4.0))

                if progress:
                    if is_pump:
                        progress["update"]("Pumping action back...")
                    else:
                        progress["update"]("Racking bolt back...")

                if is_pump:
                    self._play_weapon_action_sound(weapon, "pumpback")
                else:

                    self._cycle_bolt_sounds(weapon, single_forward = False, delay = 0.1)

                time.sleep(0.1)

                if progress:
                    if is_pump:
                        progress["update"]("Pumping action forward...")
                    else:
                        progress["update"]("Racking bolt forward...")

                if is_pump:
                    self._play_weapon_action_sound(weapon, "pumpforward")
                else:

                    pass
            finally:
                if progress:
                    try:
                        progress["close"]()
                    except Exception:
                        logging.exception("Suppressed exception")

            return f"Fired {rounds_fired} rounds - WEAPON JAMMED! Clear jam and try again."
        else:
            if is_bolt and rounds_fired >0 and cycle_result:
                base = f"Fired {rounds_fired} round(s) successfully - {cycle_result}."
            else:
                base = f"Fired {rounds_fired} rounds successfully."
            if roll_summary_text:
                return f"{base}\n{roll_summary_text}"
            return base

    def _fire_weapon(self, weapon, combat_state, rounds_to_fire = 3, fire_mode = None, save_data = None):
        try:
            return self._fire_weapon_impl(weapon, combat_state, rounds_to_fire = rounds_to_fire, fire_mode = fire_mode, save_data = save_data)
        except Exception:
            logging.exception("Unhandled exception in _fire_weapon for %s", weapon.get('name')if isinstance(weapon, dict)else str(weapon))
            return "Firing failed due to an internal error"

    def _reload_infinite_ammo_weapon(self, weapon, save_data):

        logging.info("_reload_infinite_ammo_weapon: %s", weapon.get("name", "Unknown"))

        try:

            caliber_list = weapon.get("caliber", [])or["Unknown"]
            caliber = caliber_list[0]if isinstance(caliber_list, list)else caliber_list

            mag_to_load = weapon.get("mag_to_load")
            has_magazine_in_pool = weapon.get("has_magazine_in_pool", True)

            table_data = None
            try:
                tbl_path = get_current_table_path()
                if tbl_path and os.path.exists(tbl_path):
                    with open(tbl_path, 'r', encoding = 'utf-8')as f:
                        table_data = json.load(f)
            except Exception:
                logging.exception("Failed to load table data for infinite ammo reload")

            new_mag = None

            if has_magazine_in_pool is False:

                if isinstance(mag_to_load, dict):
                    capacity = mag_to_load.get("capacity", 30)
                    if isinstance(capacity, list):
                        capacity = capacity[0]if capacity else 30
                    new_mag = {
                    "name":f"Infinite {caliber} Magazine",
                    "caliber":[caliber]if not isinstance(caliber, list)else caliber,
                    "capacity":capacity,
                    "magazinesystem":weapon.get("magazinesystem"),
                    "magazinetype":weapon.get("magazinetype", "Detachable box"),
                    "rounds":[],
                    "infinite":True
                    }

                    for _ in range(capacity):
                        new_mag["rounds"].append({
                        "name":f"{caliber} | Infinite",
                        "caliber":caliber,
                        "variant":"Infinite"
                        })
            elif mag_to_load is not None and table_data:

                mag_id = mag_to_load if isinstance(mag_to_load, int)else None
                if mag_id is not None:
                    magazines = table_data.get("tables", {}).get("magazines", [])
                    for mag in magazines:
                        if mag.get("id")==mag_id:

                            new_mag = json.loads(json.dumps(mag))
                            capacity = new_mag.get("capacity", 30)
                            new_mag["rounds"]=[]
                            new_mag["infinite"]= True

                            for _ in range(capacity):
                                new_mag["rounds"].append({
                                "name":f"{caliber} | Infinite",
                                "caliber":caliber,
                                "variant":"Infinite"
                                })
                            break

            if new_mag is None:
                capacity = 30
                loaded = weapon.get("loaded")
                if loaded and isinstance(loaded, dict):
                    capacity = loaded.get("capacity", 30)
                new_mag = {
                "name":f"Infinite {caliber} Magazine",
                "caliber":[caliber]if not isinstance(caliber, list)else caliber,
                "capacity":capacity,
                "magazinesystem":weapon.get("magazinesystem"),
                "magazinetype":weapon.get("magazinetype", "Detachable box"),
                "rounds":[],
                "infinite":True
                }
                for _ in range(capacity):
                    new_mag["rounds"].append({
                    "name":f"{caliber} | Infinite",
                    "caliber":caliber,
                    "variant":"Infinite"
                    })

            current_mag = weapon.get("loaded")
            is_gun_empty = not weapon.get("chambered")and(not current_mag or not current_mag.get("rounds", []))

            if current_mag:
                try:
                    self._play_weapon_action_sound(weapon, "magout", block = True)
                    time.sleep(random.uniform(0.5, 1.0))
                    magdrop_sound = f"magdrop{random.randint(0, 1)}"
                    self._safe_sound_play("", f"sounds/firearms/universal/{magdrop_sound}.ogg")
                except Exception:
                    logging.exception("Suppressed exception")

            time.sleep(random.uniform(0.25, 0.5))

            try:
                self._safe_sound_play("", "sounds/firearms/universal/pouchout.ogg")
            except Exception:
                logging.exception("Suppressed exception")
            time.sleep(random.uniform(0.5, 0.75))
            try:
                self._play_weapon_action_sound(weapon, "magin", block = True)
            except Exception:
                logging.exception("Suppressed exception")

            time.sleep(random.uniform(0.25, 0.5))

            rt_platform = str(weapon.get("platform", "")or "").lower()
            rt_mag_type = str(weapon.get("magazinetype", "")or "").lower()
            rt_action_raw = weapon.get("action", "")or ""
            if isinstance(rt_action_raw, (list, tuple)):
                rt_action_raw = rt_action_raw[0]if rt_action_raw else ""
            rt_action = str(rt_action_raw).lower()
            is_pump =("pump"in rt_platform or rt_action =="pump"or "pump"in rt_mag_type)

            if is_gun_empty:
                if is_pump:
                    try:
                        self._play_weapon_action_sound(weapon, "pumpback", block = True)
                        self._play_weapon_action_sound(weapon, "pumpforward")
                    except Exception:
                        logging.exception("Suppressed exception")
                elif not weapon.get("bolt_catch"):
                    try:
                        self._play_weapon_action_sound(weapon, "boltback", block = True)
                        self._play_weapon_action_sound(weapon, "boltforward")
                    except Exception:
                        logging.exception("Suppressed exception")
                else:
                    try:
                        self._play_weapon_action_sound(weapon, "boltforward")
                    except Exception:
                        logging.exception("Suppressed exception")

            rt_mag_type = str(weapon.get("magazinetype", "")or "").lower()

            if any(k in rt_mag_type for k in("internal", "tube", "cylinder")):
                cur_rounds = weapon.get("rounds", [])or[]

                cur_rounds.extend(list(new_mag.get("rounds", [])))
                weapon["rounds"]= cur_rounds
                if is_gun_empty and weapon["rounds"]and not is_pump:
                    weapon["chambered"]= weapon["rounds"].pop(0)
                elif is_gun_empty:
                    weapon["chambered"]= {
                    "name":f"{caliber} | Infinite",
                    "caliber":caliber,
                    "variant":"Infinite"
                    }
            else:
                weapon["loaded"]= new_mag

                if is_gun_empty and new_mag.get("rounds")and not is_pump:
                    weapon["chambered"]= new_mag["rounds"].pop(0)
                elif is_gun_empty:
                    weapon["chambered"]= {
                    "name":f"{caliber} | Infinite",
                    "caliber":caliber,
                    "variant":"Infinite"
                    }

            rounds_loaded = len(new_mag.get("rounds", []))
            capacity = new_mag.get("capacity", "?")
            return f"Reloaded with infinite ammo({rounds_loaded}/{capacity})"

        except Exception as e:
            logging.exception("Failed to reload infinite ammo weapon")
            return f"Reload failed: {e}"

    def _reload_weapon(self, weapon, save_data, combat_reload = False):

        logging.info(
        "_reload_weapon start: name=%s magsystem=%s combat_reload=%s",
        weapon.get("name", "Unknown"),
        weapon.get("magazinesystem"),
        combat_reload
        )

        try:
            pf = None
            if isinstance(weapon, dict):
                pf = weapon.get("platform")or weapon.get("underbarrel_platform")
            if weapon.get("underbarrel_weapon")or(pf and pf in self.PLATFORM_DEFAULTS):
                return self._reload_underbarrel(weapon, save_data, combat_reload)
        except Exception:
            logging.exception("Underbarrel reload handler check failed")

        if weapon.get("infinite_ammo"):
            inf_mag_type = str(weapon.get("magazinetype", "")or "").lower()
            if any(k in inf_mag_type for k in("internal", "tube", "cylinder", "en bloc")):
                return self._reload_internal_magazine(weapon, save_data, inf_mag_type)
            return self._reload_infinite_ammo_weapon(weapon, save_data)

        magazine_type = weapon.get("magazinetype", "")or ""
        magazine_type = magazine_type.lower()if isinstance(magazine_type, str)else str(magazine_type).lower()
        magazine_system = weapon.get("magazinesystem")

        if not magazine_system:

            if weapon.get("magazinetype"):
                magazine_system = weapon.get("magazinetype")
            else:

                loaded_mag = weapon.get("loaded")
                if isinstance(loaded_mag, dict)and loaded_mag.get("magazinesystem"):
                    magazine_system = loaded_mag.get("magazinesystem")
                else:

                    found_ms = None

                    for item in save_data.get("hands", {}).get("items", []):
                        if item and isinstance(item, dict)and("rounds"in item or "capacity"in item):
                            if item.get("magazinesystem"):
                                found_ms = item.get("magazinesystem");break
                            if item.get("magazinetype"):
                                found_ms = item.get("magazinetype");break

                    if not found_ms:
                        for slot_name, eq_item in save_data.get("equipment", {}).items():
                            if eq_item and isinstance(eq_item, dict)and("rounds"in eq_item or "capacity"in eq_item):
                                if eq_item.get("magazinesystem"):
                                    found_ms = eq_item.get("magazinesystem");break
                                if eq_item.get("magazinetype"):
                                    found_ms = eq_item.get("magazinetype");break
                    if found_ms:
                        magazine_system = found_ms

        if "internal"in magazine_type or "en bloc" in magazine_type:
            return self._reload_internal_magazine(weapon, save_data, magazine_type)

        if "muzzle"in magazine_type:
            check = self._reload_muzzleloader_check(weapon, save_data)
            if check:
                return check
            return self._reload_muzzleloader_finish(weapon, save_data)

        if "cylinder"in magazine_type:
            return self._reload_cylinder(weapon, save_data)

        if "revolver"in weapon.get("platform", "").lower():
            return self._reload_revolver(weapon, save_data)

        if not magazine_system:
            try:
                sugg = self.suggest_magazine_for_weapon(weapon)
                caps = sugg.get('suggested_capacities')if isinstance(sugg, dict)else None
                nid = sugg.get('next_id')if isinstance(sugg, dict)else None
                note = f"Weapon doesn't use magazines.Suggested capacities: {caps} Next ID: {nid}"
                return note
            except Exception:
                return "Weapon doesn't use magazines."

    def suggest_magazine_for_weapon(self, weapon):

        try:
            name =(weapon.get('name')or '').strip()
        except Exception:
            name = ''
        try:
            calib_raw = weapon.get('caliber')
            if isinstance(calib_raw, (list, tuple))and calib_raw:
                calib = str(calib_raw[0])
            else:
                calib = str(calib_raw or '')
        except Exception:
            calib = ''

        results = {
        'weapon_name':name,
        'caliber':calib,
        'wiki_matches':[],
        'suggested_capacities':[],
        'suggested_mag_item':None,
        'next_id':0,
        'notes':[]
        }

        caliber_map = {
        '9x19':[15, 17, 30],
        '9mm':[15, 17, 30],
        '5.56x45':[30],
        '5.56':[30],
        '7.62x39':[30],
        '7.62x51':[20, 30],
        '7.62':[20, 30],
        '.45 acp':[7, 8, 10],
        '.45':[7, 8, 10],
        '.308':[10, 20, 30],
        '.30-06':[5, 10],
        '12 gauge':[1, 4, 5, 8],
        '40mm':[1]
        }

        def _norm(s):
            try:
                return re.sub(r"[^0-9a-zA-Z\.x\-\s]", '', str(s or '')).strip().lower()
            except Exception:
                return ''

        wiki_candidates =[]
        session = requests.Session()
        try:
            if name:
                q = name
                url = 'https://en.wikipedia.org/w/api.php'
                params = {
                'action':'query',
                'list':'search',
                'srsearch':q,
                'format':'json',
                'srlimit':5
                }
                r = session.get(url, params = params, timeout = 6)
                j = r.json()
                for s in j.get('query', {}).get('search', [])or[]:
                    wiki_candidates.append(s.get('title'))
        except Exception:
            results['notes'].append('Wikipedia search failed for weapon name')

        try:
            if calib:
                q = calib
                url = 'https://en.wikipedia.org/w/api.php'
                params = {
                'action':'query',
                'list':'search',
                'srsearch':q,
                'format':'json',
                'srlimit':5
                }
                r = session.get(url, params = params, timeout = 6)
                j = r.json()
                for s in j.get('query', {}).get('search', [])or[]:
                    if s.get('title')not in wiki_candidates:
                        wiki_candidates.append(s.get('title'))
        except Exception:
            results['notes'].append('Wikipedia search failed for caliber')

        capacities_found =[]
        try:
            url = 'https://en.wikipedia.org/w/api.php'
            for title in wiki_candidates[:6]:
                try:
                    params = {
                    'action':'query',
                    'prop':'extracts',
                    'explaintext':1,
                    'titles':title,
                    'format':'json',
                    'exintro':1
                    }
                    r = session.get(url, params = params, timeout = 6)
                    j = r.json()
                    pages = j.get('query', {}).get('pages', {})or {}
                    text = ''
                    for p in pages.values():
                        text =(p.get('extract')or '')
                        break
                    if not text:

                        params['exintro']= 0
                        r = session.get(url, params = params, timeout = 6)
                        j = r.json()
                        pages = j.get('query', {}).get('pages', {})or {}
                        for p in pages.values():
                            text =(p.get('extract')or '')
                            break
                    if not text:
                        continue
                    results['wiki_matches'].append({'title':title, 'snippet':text[:800]})

                    lower = text.lower()

                    for m in re.finditer(r"magazine", lower):
                        start = max(0, m.start()-120)
                        end = min(len(lower), m.end()+120)
                        context = lower[start:end]
                        nums = re.findall(r"(\d{1, 3})\s*(?:-round|rounds|round|rd|rnd)", context)
                        for n in nums:
                            try:
                                capacities_found.append(int(n))
                            except Exception:
                                logging.exception("Suppressed exception")

                    for m in re.finditer(r"capacity|standard|commonly|usually", lower):
                        start = max(0, m.start()-120)
                        end = min(len(lower), m.end()+120)
                        context = lower[start:end]
                        nums = re.findall(r"(\d{1, 3})\s*(?:rounds|round|rnd|-round)", context)
                        for n in nums:
                            try:
                                capacities_found.append(int(n))
                            except Exception:
                                logging.exception("Suppressed exception")

                    nums = re.findall(r"(\d{1, 3})\s*-?\s*round(?:s)?", lower)
                    for n in nums:
                        try:
                            capacities_found.append(int(n))
                        except Exception:
                            logging.exception("Suppressed exception")
                except Exception:
                    logging.exception("Suppressed exception")
                    continue
        except Exception:
            results['notes'].append('Failed fetching/parsing Wikipedia extracts')

        caps =[]
        try:
            if capacities_found:

                freq = {}
                for c in capacities_found:
                    freq[c]= freq.get(c, 0)+1
                caps = sorted(freq.keys(), key = lambda x:(-freq[x], x))[:5]
        except Exception:
            caps =[]

        try:
            if not caps and calib:
                ncal = _norm(calib)
                for k, v in caliber_map.items():
                    if k in ncal or ncal in k:
                        caps = v[:3]
                        break
        except Exception:
            logging.exception("Suppressed exception")

        if not caps:
            caps =[10, 20, 30]

        results['suggested_capacities']= caps

        try:
            table_files = glob.glob(os.path.join('tables', '*.sldtbl'))
            maxid = 0
            for tf in table_files:
                try:
                    with open(tf, 'r', encoding = 'utf-8')as fh:
                        td = json.load(fh)
                    tables = td.get('tables', {})
                    for sub, items in tables.items():
                        if isinstance(items, list):
                            for it in items:
                                try:
                                    if isinstance(it, dict)and 'id'in it:
                                        iid = it.get('id')
                                        try:
                                            if iid is None:
                                                continue
                                            iv = int(iid)
                                            if iv >maxid:
                                                maxid = iv
                                        except Exception:
                                            logging.exception("Suppressed exception")
                                except Exception:
                                    logging.exception("Suppressed exception")
                except Exception:
                    logging.exception("Suppressed exception")
                    continue
            next_id = maxid +1
        except Exception:
            next_id = 0

        results['next_id']= next_id

        try:
            cap = caps[0]if caps else 30
            mag_name = f"Synthetic Mag({cap})"
            mag_item = {
            'id':next_id,
            'name':mag_name,
            'capacity':int(cap),
            'magazinetype':weapon.get('magazinetype')or 'detachable box',
            'magazinesystem':weapon.get('magazinesystem')or weapon.get('magazinetype')or '',
            'rounds':[]
            }

            try:
                round_name =(calib or 'Unknown')+' | FMJ'
            except Exception:
                round_name = 'FMJ'
            for i in range(int(cap)):
                mag_item['rounds'].append({'name':round_name, 'caliber':calib or None, 'variant':'fmj'})
            results['suggested_mag_item']= mag_item
        except Exception:
            results['notes'].append('Failed to build suggested_mag_item')

        return results

    def _categorize_40mm_round(self, round_info):

        try:
            if not isinstance(round_info, dict):
                return None
            keys = {}
            for k in("type", "variant", "subtype", "name"):
                v = round_info.get(k)
                if isinstance(v, str):
                    keys[k]= v.lower()
            name = keys.get("name", "")
            typ = keys.get("type", "")or keys.get("variant", "")or keys.get("subtype", "")

            if "airburst"in name or "air burst"in name or "airburst"in typ or "air burst"in typ:
                return "airburst"
            if "high-explosive"in name or "high explosive"in name or "he"==typ or "high-explosive"in typ:
                return "he"
            if "dual"in name and("high"in name or "explosive"in name or "dp"in name):
                return "hedp"
            if "apers"in name or "ap ers"in name or "ap"in typ or "anti-personnel"in name:
                return "apers"
            if "smoke"in name or "smoke"in typ:
                return "smoke"
            if "gas"in name or "gas"in typ:
                return "gas"

            if "expl"in name:
                return "he"
        except Exception:
            logging.exception("Suppressed exception")
        return None

    def _handle_40mm_post_fire_effects(self, weapon, round_info):

        try:

            platform_key =(weapon.get("platform")or weapon.get("underbarrel_platform")or "").strip()
            if isinstance(platform_key, (list, tuple)):
                platform_key = platform_key[0]if platform_key else ""
            wf = None
            if platform_key and platform_key in self.PLATFORM_DEFAULTS:
                wf = os.path.join("sounds", "firearms", "weaponsounds", str(self.PLATFORM_DEFAULTS[platform_key].get("reload_sound_folder", platform_key)).lower().replace('/', '_'))
            else:

                pf = str(platform_key).lower().replace('/', '_')
                wf = os.path.join("sounds", "firearms", "weaponsounds", pf)

            cat = self._categorize_40mm_round(round_info)or "he"

            def play_pattern(patterns, block = False):
                candidates =[]
                try:
                    for p in patterns:

                        candidates +=glob.glob(os.path.join(wf, p))
                        try:
                            wav_pat = p.replace('.ogg', '.wav')if '.ogg'in p else p +'.wav'
                            candidates +=glob.glob(os.path.join(wf, wav_pat))
                        except Exception:
                            logging.exception("Suppressed exception")
                except Exception:
                    logging.exception("Suppressed exception")

                if not candidates:
                    for p in patterns:
                        candidates +=glob.glob(os.path.join("sounds", "firearms", "40mm_grenade", p))
                        try:
                            wav_pat = p.replace('.ogg', '.wav')if '.ogg'in p else p +'.wav'
                            candidates +=glob.glob(os.path.join("sounds", "firearms", "40mm_grenade", wav_pat))
                        except Exception:
                            logging.exception("Suppressed exception")
                if candidates:
                    self._safe_sound_play("", random.choice(candidates), block = block)

            import threading
            import random as _r

            if cat =="apers":

                play_pattern(["apers*.ogg"], block = False)
                return

            if cat =="airburst":

                def _airburst():
                    play_pattern(["explode*.ogg"], block = False)
                t = threading.Timer(5.0, _airburst)
                t.daemon = True
                t.start()
                return

            if cat in("he", "hedp"):

                delay = _r.uniform(0.2, 1.0)
                def _do_he():

                    play_pattern(["explode*.ogg"], block = False)
                    if cat =="he":

                        time.sleep(0.08)
                        play_pattern(["explode*.ogg"], block = False)
                t = threading.Timer(delay, _do_he)
                t.daemon = True
                t.start()
                return

            if cat in("smoke", "gas"):
                delay = _r.uniform(0.5, 2.5)
                def _do_smoke():

                    play_pattern(["smoke*.ogg"], block = False)
                t = threading.Timer(delay, _do_smoke)
                t.daemon = True
                t.start()
                return

            delay = _r.uniform(0.2, 1.0)
            def _do_default():
                play_pattern(["explode*.ogg"], block = False)
            t = threading.Timer(delay, _do_default)
            t.daemon = True
            t.start()
            return
        except Exception:
            logging.exception("Error in _handle_40mm_post_fire_effects")
            return

    def _reload_underbarrel(self, accessory, save_data, combat_reload = False):

        try:
            platform = None
            if isinstance(accessory, dict):
                platform = accessory.get("platform")or accessory.get("underbarrel_platform")

            if not platform and isinstance(accessory, dict):
                try:
                    aname = str(accessory.get("name")or "").lower()
                    if "m203"in aname or "m-203"in aname or "203"in aname:
                        platform = "M203"
                except Exception:
                    logging.exception("Suppressed exception")

            try:
                ub_type = None
                if isinstance(accessory, dict):
                    ub_type = accessory.get("underbarrel_type")or accessory.get("underbarrel")

                if isinstance(ub_type, str):
                    ut = ub_type.lower()
                    if "shot"in ut or "gauge"in ut or "12"in ut:
                        defaults = {"ammo_type":"12 Gauge", "capacity":accessory.get("capacity", 1)or 1, "reload_sound_folder":"12gauge", "magazinetype":accessory.get("magazinetype", "internal")}
                    elif "40"in ut or "m203"in ut or "grenade"in ut:
                        defaults = {"ammo_type":"40mm_grenade", "capacity":accessory.get("capacity", 1)or 1, "reload_sound_folder":"m203", "magazinetype":accessory.get("magazinetype", "single")}
                    else:
                        defaults = self.PLATFORM_DEFAULTS.get(platform or "", {"ammo_type":"40mm_grenade", "capacity":1, "reload_sound_folder":"40mm_grenade"})
                else:
                    defaults = self.PLATFORM_DEFAULTS.get(platform or "", {"ammo_type":"40mm_grenade", "capacity":1, "reload_sound_folder":"40mm_grenade"})
            except Exception:
                defaults = self.PLATFORM_DEFAULTS.get(platform or "", {"ammo_type":"40mm_grenade", "capacity":1, "reload_sound_folder":"40mm_grenade"})

            capacity = defaults.get("capacity", 1)

            try:
                ub_type = None
                ub_sub = None
                if isinstance(accessory, dict):
                    ub_type = accessory.get("underbarrel_type")or accessory.get("type")
                    ub_sub = accessory.get("underbarrel_subtype")or accessory.get("underbarrel_subtype")

                is_conventional = False
                if isinstance(ub_type, str)and ub_type.lower()=="conventional":
                    is_conventional = True
                if isinstance(ub_sub, str)and "shot"in ub_sub.lower():
                    is_conventional = True

                if is_conventional:
                    mag_type = accessory.get("magazinetype")or defaults.get("magazinetype")or "internal"
                    logging.debug("Underbarrel reload: treating as conventional underbarrel(underbarrel_type=%s, underbarrel_subtype=%s, magazinetype=%s)", ub_type, ub_sub, mag_type)
                    mt_l = str(mag_type).lower()
                    if any(k in mt_l for k in("internal", "tube", "box")):
                        return self._reload_internal_magazine(accessory, save_data, mag_type)
                    if "revolver"in mt_l:
                        return self._reload_revolver(accessory, save_data)
                    return self._reload_weapon(accessory, save_data, combat_reload)
            except Exception:
                logging.exception("Failed to delegate underbarrel reload to normal handlers; falling back to custom logic")

            def _is_compatible_ammo(it, desired):
                try:
                    if not isinstance(it, dict):
                        return False
                    name =(it.get("name")or "").lower()
                    calib = it.get("caliber")
                    ammo_type_field =(it.get("ammo_type")or "").lower()
                    desired_l =(desired or "").lower()

                    if "40"in desired_l or "40mm"in desired_l or "grenade"in desired_l:
                        if "40x46"in name or "40mm"in name or "40 x 46"in name:
                            return True
                        if calib:
                            if isinstance(calib, (list, tuple)):
                                for c in calib:
                                    if isinstance(c, str)and "40"in c and "mm"in c:
                                        return True
                            elif isinstance(calib, str)and "40"in calib and "mm"in calib:
                                return True
                        if ammo_type_field =="40mm_grenade":
                            return True
                        return False

                    if "gauge"in desired_l or "12"in desired_l:
                        if "gauge"in name or "12 gauge"in name or(isinstance(calib, str)and "12"in calib.lower()and "gauge"in calib.lower()):
                            return True
                        if isinstance(calib, (list, tuple)):
                            for c in calib:
                                if isinstance(c, str)and "12"in c and "gauge"in c.lower():
                                    return True
                        if ammo_type_field and("12"in ammo_type_field or "gauge"in ammo_type_field):
                            return True
                        return False

                    if calib:
                        if isinstance(calib, (list, tuple))and any((isinstance(c, str)and desired_l in c.lower())for c in calib):
                            return True
                        if isinstance(calib, str)and desired_l in calib.lower():
                            return True
                    if desired_l and(desired_l ==ammo_type_field or desired_l in name or desired_l in(it.get("sounds")or "")):
                        return True
                except Exception:
                    logging.exception("Suppressed exception")
                return False

            found_item = None
            found_location = None

            want_mag = False
            mag_type_hint =(defaults.get("magazinetype")or "").lower()
            if "mag"in mag_type_hint or "box"in mag_type_hint or "detachable"in mag_type_hint:
                want_mag = True

            hands_list = save_data.get("hands", {}).get("items", [])
            for idx, it in enumerate(list(hands_list)):
                try:

                    if want_mag and isinstance(it, dict)and it.get("rounds"):
                        if defaults.get("magazinesystem"):
                            if str(it.get("magazinesystem")or "").lower()==str(defaults.get("magazinesystem")or "").lower():
                                found_item = it
                                found_location =("hands", idx)
                                break
                        else:
                            found_item = it
                            found_location =("hands", idx)
                            break

                    if _is_compatible_ammo(it, defaults.get("ammo_type")):
                        found_item = it
                        found_location =("hands", idx)
                        break
                except Exception:
                    logging.exception("Suppressed exception")
                    continue

            if not found_item:
                for storage_idx, container in enumerate(save_data.get("storage", [])or[]):
                    try:
                        if isinstance(container, dict)and container.get("items"):
                            for idx, it in enumerate(list(container.get("items", []))):
                                try:
                                    if want_mag and isinstance(it, dict)and it.get("rounds"):
                                        if defaults.get("magazinesystem"):
                                            if str(it.get("magazinesystem")or "").lower()==str(defaults.get("magazinesystem")or "").lower():
                                                found_item = it
                                                found_location =("storage", storage_idx, idx)
                                                break
                                        else:
                                            found_item = it
                                            found_location =("storage", storage_idx, idx)
                                            break
                                    if _is_compatible_ammo(it, defaults.get("ammo_type")):
                                        found_item = it
                                        found_location =("storage", storage_idx, idx)
                                        break
                                except Exception:
                                    logging.exception("Suppressed exception")
                                    continue
                            if found_item:
                                break
                    except Exception:
                        logging.exception("Suppressed exception")

            if not found_item:
                return f"No {defaults.get('ammo_type', 'compatible')} rounds/magazines found in inventory!"

            try:
                if found_location and found_location[0]=="hands":
                    _, idx = found_location
                    hand_items = save_data.get("hands", {}).get("items", [])
                    if idx <len(hand_items):
                        target = hand_items[idx]

                        if isinstance(target, dict)and target.get("quantity")and isinstance(target.get("quantity"), (int, float)):
                            try:
                                target["quantity"]-=1
                                if target["quantity"]<=0:
                                    hand_items.pop(idx)
                            except Exception:
                                hand_items.pop(idx)
                        else:

                            hand_items.pop(idx)
                elif found_location and found_location[0]=="storage":
                    _, storage_idx, idx = found_location
                    storage_list = save_data.get("storage", [])
                    if storage_idx <len(storage_list):
                        container = storage_list[storage_idx]
                        if isinstance(container, dict)and container.get("items"):
                            items_list = container.get("items")or[]
                            if idx <len(items_list):
                                target = items_list[idx]
                                if isinstance(target, dict)and target.get("quantity")and isinstance(target.get("quantity"), (int, float)):
                                    try:
                                        target["quantity"]-=1
                                        if target["quantity"]<=0:
                                            items_list.pop(idx)
                                    except Exception:
                                        items_list.pop(idx)
                                else:
                                    items_list.pop(idx)
            except Exception:
                logging.exception("Failed to remove consumed underbarrel ammo/magazine from inventory")

            accessory["_ub_loaded"]= capacity
            try:
                sd_ref = save_data if isinstance(save_data, dict)else globals().get('save_data')or getattr(self, '_current_save_data', None)
                if isinstance(sd_ref, dict):
                    ts = sd_ref.setdefault('tracked_stats', {})
                    if isinstance(ts, dict):
                        ts['mags_reloaded_total']= int(ts.get('mags_reloaded_total', 0))+1
                        ts['bullets_loaded_total']= int(ts.get('bullets_loaded_total', 0))+int(capacity)
                        bh = ts.setdefault('bullets_loaded_history', [])
                        try:
                            bh.append({'weapon_id':str(accessory.get('id', 'ub')), 'count':int(capacity), 'time':time.time()})
                        except Exception:
                            logging.exception("Suppressed exception")
            except Exception:
                logging.exception('Failed updating tracked_stats after underbarrel reload')
            try:
                self._update_session_reload_stats(save_data, int(capacity))
            except Exception:
                logging.exception('Failed updating session reload stats after underbarrel reload')
            try:
                accessory["_ub_loaded_item"]= found_item.get("id")or found_item.get("name")
            except Exception:
                logging.exception("Suppressed exception")

            try:
                if isinstance(found_item, dict)and found_item.get("rounds"):

                    try:
                        mag_copy = dict(found_item)

                        mag_copy["rounds"]= list(found_item.get("rounds", []))
                        accessory["loaded"]= mag_copy

                        if accessory["loaded"].get("rounds"):
                            accessory["chambered"]= accessory["loaded"]["rounds"].pop(0)
                    except Exception:
                        logging.exception("Failed to attach magazine as underbarrel loaded")
                else:

                    round_cal = None
                    if isinstance(found_item, dict):
                        raw_cal = found_item.get("caliber")or defaults.get("ammo_type")
                        if isinstance(raw_cal, (list, tuple)):
                            round_cal = raw_cal[0]if raw_cal else None
                        else:
                            round_cal = raw_cal
                        round_variant = found_item.get("variant")or found_item.get("name")
                    else:
                        round_cal = defaults.get("ammo_type")
                        round_variant = None

                    single_round = {"name":f"{round_cal} | {round_variant}"if round_variant else f"{round_cal}", "caliber":round_cal, "variant":round_variant}

                    accessory["loaded"]= {"magazinetype":"underbarrel", "magazinesystem":None, "capacity":capacity, "rounds":[dict(single_round)for _ in range(capacity)]}

                    if accessory["loaded"]["rounds"]:
                        accessory["chambered"]= accessory["loaded"]["rounds"].pop(0)
            except Exception:
                logging.exception("Failed to synthesize loaded rounds for underbarrel accessory")

            try:
                acc_id = accessory.get("id")
                acc_name = accessory.get("name")
                def _set_on_matching(obj):
                    try:
                        if not isinstance(obj, dict):
                            return False
                        if obj.get("id")==acc_id or obj.get("name")==acc_name:
                            obj["_ub_loaded"]= capacity
                            try:
                                obj["_ub_loaded_item"]= found_item.get("id")or found_item.get("name")
                            except Exception:
                                logging.exception("Suppressed exception")
                            return True

                        if obj.get("accessories")and isinstance(obj.get("accessories"), list):
                            for a in(obj.get("accessories")or[]):
                                cur = a.get("current")
                                if isinstance(cur, dict)and(cur.get("id")==acc_id or cur.get("name")==acc_name):
                                    cur["_ub_loaded"]= capacity
                                    try:
                                        cur["_ub_loaded_item"]= found_item.get("id")or found_item.get("name")
                                    except Exception:
                                        logging.exception("Suppressed exception")
                                    return True

                        if obj.get("items")and isinstance(obj.get("items"), list):
                            for it in(obj.get("items")or[]):
                                if isinstance(it, dict)and(it.get("id")==acc_id or it.get("name")==acc_name):
                                    it["_ub_loaded"]= capacity
                                    try:
                                        it["_ub_loaded_item"]= found_item.get("id")or found_item.get("name")
                                    except Exception:
                                        logging.exception("Suppressed exception")
                                    return True
                    except Exception:
                        logging.exception("Suppressed exception")
                    return False

                for slot_name, eq_item in(save_data.get("equipment")or {}).items():
                    if not eq_item or not isinstance(eq_item, dict):
                        continue
                    if _set_on_matching(eq_item):
                        break

                    if eq_item.get("subslots"):
                        for sub in(eq_item.get("subslots")or[]):
                            cur = sub.get("current")
                            if isinstance(cur, dict)and(cur.get("id")==acc_id or cur.get("name")==acc_name):
                                cur["_ub_loaded"]= capacity
                                try:
                                    cur["_ub_loaded_item"]= found_item.get("id")or found_item.get("name")
                                except Exception:
                                    logging.exception("Suppressed exception")
                                raise StopIteration

                for it in list(save_data.get("hands", {}).get("items", [])):
                    if isinstance(it, dict)and(it.get("id")==acc_id or it.get("name")==acc_name):
                        it["_ub_loaded"]= capacity
                        try:
                            it["_ub_loaded_item"]= found_item.get("id")or found_item.get("name")
                        except Exception:
                            logging.exception("Suppressed exception")
                        break
                for container in list(save_data.get("storage", [])):
                    try:
                        if isinstance(container, dict)and container.get("items"):
                            for it in(container.get("items")or[]):
                                if isinstance(it, dict)and(it.get("id")==acc_id or it.get("name")==acc_name):
                                    it["_ub_loaded"]= capacity
                                    try:
                                        it["_ub_loaded_item"]= found_item.get("id")or found_item.get("name")
                                    except Exception:
                                        logging.exception("Suppressed exception")
                                    raise StopIteration
                    except StopIteration:
                        break
            except Exception:
                logging.exception("Failed to persist underbarrel loaded state to save_data")

            wf = os.path.join("sounds", "firearms", "weaponsounds", str(defaults.get("reload_sound_folder", "40mm_grenade")).lower().replace('/', '_'))
            logging.debug("Underbarrel reload: platform=%s wf=%s, defaults=%s, found_item=%s, found_location=%s", platform, wf, defaults, getattr(found_item, 'get', lambda k:None)('name')if isinstance(found_item, dict)else found_item, found_location)

            open_candidates = glob.glob(os.path.join(wf, "open*.ogg"))+glob.glob(os.path.join(wf, "open*.wav"))
            open_candidates +=glob.glob(os.path.join(wf, "door*.ogg"))+glob.glob(os.path.join(wf, "door*.wav"))
            logging.debug("Underbarrel reload: open_candidates=%s", open_candidates)
            if open_candidates:
                logging.debug("Playing underbarrel open sound: %s", open_candidates[0])
                self._safe_sound_play("", random.choice(open_candidates), block = True)
            else:

                alt_wf = os.path.join("sounds", "firearms", "weaponsounds", "m203")
                alt_open = glob.glob(os.path.join(alt_wf, "open*.ogg"))+glob.glob(os.path.join(alt_wf, "open*.wav"))
                alt_open +=glob.glob(os.path.join(alt_wf, "door*.ogg"))+glob.glob(os.path.join(alt_wf, "door*.wav"))
                logging.debug("Underbarrel reload: alt_open_candidates=%s", alt_open)
                if alt_open:
                    logging.debug("Playing underbarrel open sound from alt m203: %s", alt_open[0])
                    self._safe_sound_play("", random.choice(alt_open), block = True)
                else:
                    try:
                        self._play_firearm_sound(accessory, "open")
                    except Exception:
                        logging.exception("Suppressed exception")

            time.sleep(random.uniform(1.0, 1.5))

            insert_candidates = glob.glob(os.path.join(wf, "insert*.ogg"))+glob.glob(os.path.join(wf, "insert*.wav"))
            logging.debug("Underbarrel reload: insert_candidates=%s", insert_candidates)
            if insert_candidates:
                logging.debug("Playing underbarrel insert sound: %s", insert_candidates[0])
                self._safe_sound_play("", random.choice(insert_candidates), block = True)
            else:
                alt_wf = os.path.join("sounds", "firearms", "weaponsounds", "m203")
                alt_insert = glob.glob(os.path.join(alt_wf, "insert*.ogg"))+glob.glob(os.path.join(alt_wf, "insert*.wav"))
                logging.debug("Underbarrel reload: alt_insert_candidates=%s", alt_insert)
                if alt_insert:
                    logging.debug("Playing underbarrel insert sound from alt m203: %s", alt_insert[0])
                    self._safe_sound_play("", random.choice(alt_insert), block = True)
                else:
                    try:
                        self._play_firearm_sound(accessory, "insert")
                    except Exception:
                        logging.exception("Suppressed exception")

            time.sleep(random.uniform(1.0, 1.5))

            close_candidates = glob.glob(os.path.join(wf, "close*.ogg"))+glob.glob(os.path.join(wf, "close*.wav"))
            close_candidates +=glob.glob(os.path.join(wf, "shut*.ogg"))+glob.glob(os.path.join(wf, "shut*.wav"))
            logging.debug("Underbarrel reload: close_candidates=%s", close_candidates)
            if close_candidates:
                logging.debug("Playing underbarrel close sound: %s", close_candidates[0])
                self._safe_sound_play("", random.choice(close_candidates), block = True)
            else:
                alt_wf = os.path.join("sounds", "firearms", "weaponsounds", "m203")
                alt_close = glob.glob(os.path.join(alt_wf, "close*.ogg"))+glob.glob(os.path.join(alt_wf, "close*.wav"))
                alt_close +=glob.glob(os.path.join(alt_wf, "shut*.ogg"))+glob.glob(os.path.join(alt_wf, "shut*.wav"))
                logging.debug("Underbarrel reload: alt_close_candidates=%s", alt_close)
                if alt_close:
                    logging.debug("Playing underbarrel close sound from alt m203: %s", alt_close[0])
                    self._safe_sound_play("", random.choice(alt_close), block = True)
                else:
                    try:
                        self._play_firearm_sound(accessory, "close")
                    except Exception:
                        logging.exception("Suppressed exception")

            return f"Reloaded {accessory.get('name', 'launcher')}({capacity})"
        except Exception:
            logging.exception("Failed to reload underbarrel accessory")
            return "Failed to reload underbarrel accessory"

    def _reload_internal_magazine(self, weapon, save_data, magazine_type):

        magazine_type = str(magazine_type or '').lower()
        is_en_bloc = 'en bloc' in magazine_type

        capacity = weapon.get("capacity", 10)
        current_rounds = weapon.get("rounds", [])
        _garand_hold_open_reload = bool(is_en_bloc and weapon.get('bolt_catch') and not weapon.get('chambered') and len(current_rounds) == 0)
        garand_thumb_result = None

        compatible_ammo =[]
        caliber_list = weapon.get("caliber", [])or[]
        caliber = caliber_list[0]if caliber_list else None
        ammo_loaded = 0

        if not caliber:
            return "Weapon has no caliber defined."

        if is_en_bloc:
            try:
                capacity = int(capacity or 0)
            except Exception:
                capacity = 0
            if capacity <= 0:
                _enbloc_cap = 0
                try:
                    loaded_like = weapon.get('loaded')
                    if isinstance(loaded_like, dict):
                        _enbloc_cap = int(loaded_like.get('capacity', 0) or 0)
                except Exception:
                    _enbloc_cap = 0
                if _enbloc_cap <= 0:
                    try:
                        desired_system = str(weapon.get('magazinesystem') or '').strip().lower()
                        for _itm in save_data.get('hands', {}).get('items', []):
                            if isinstance(_itm, dict) and str(_itm.get('magazinesystem') or '').strip().lower() == desired_system:
                                _enbloc_cap = int(_itm.get('capacity', 0) or 0)
                                if _enbloc_cap > 0:
                                    break
                    except Exception:
                        _enbloc_cap = 0
                capacity = _enbloc_cap or 8

        if weapon.get("infinite_ammo"):
            ammo_needed = capacity -len(current_rounds)
            for _ in range(ammo_needed):
                current_rounds.append({"name":f"{caliber} | Infinite", "caliber":caliber, "variant":"infinite"})
                ammo_loaded +=1

            had_chambered = bool(weapon.get("chambered"))
            if not had_chambered:
                rt_mag_type = str(weapon.get("magazinetype", "")or "").lower()
                rt_platform_raw = weapon.get("platform", "")or ""
                if isinstance(rt_platform_raw, (list, tuple)):
                    rt_platform_raw = rt_platform_raw[0]if rt_platform_raw else ""
                rt_platform = str(rt_platform_raw).lower()
                rt_action_raw = weapon.get("action", "")or ""
                if isinstance(rt_action_raw, (list, tuple)):
                    rt_action_raw = rt_action_raw[0]if rt_action_raw else ""
                rt_action = str(rt_action_raw).lower()
                is_pump_reload =("pump"in rt_platform or rt_action =="pump"or "pump"in rt_mag_type)

                _inf_is_ba = (rt_action in ('bolt', 'lever', 'single'))
                _inf_snd_back = 'boltactionback' if _inf_is_ba else 'boltback'
                _inf_snd_fwd = 'boltactionforward' if _inf_is_ba else 'boltforward'

                if is_pump_reload:
                    try:
                        self._play_weapon_action_sound(weapon, "pumpforward")
                    except Exception:
                        logging.exception("Suppressed exception")
                else:
                    if not weapon.get("bolt_catch"):
                            self._play_weapon_action_sound(weapon, _inf_snd_back, block = True)

                            if weapon.get("gas_melted", False):
                                if current_rounds:
                                    weapon["chambered"]= current_rounds.pop(0)
                                self._play_weapon_action_sound(weapon, _inf_snd_fwd)
                            else:
                                if current_rounds:
                                    weapon["chambered"]= current_rounds.pop(0)
                                self._play_weapon_action_sound(weapon, _inf_snd_fwd)
                    else:
                        if current_rounds:
                            weapon["chambered"]= current_rounds.pop(0)
                        self._play_weapon_action_sound(weapon, _inf_snd_fwd)

            weapon["rounds"]= current_rounds
            try:
                sd_ref = save_data if isinstance(save_data, dict)else globals().get('save_data')or getattr(self, '_current_save_data', None)
                if isinstance(sd_ref, dict):
                    ts = sd_ref.setdefault('tracked_stats', {})
                    if isinstance(ts, dict):
                        ts['mags_reloaded_total']= int(ts.get('mags_reloaded_total', 0))+1
                        try:
                            added = int(ammo_loaded)
                        except Exception:
                            added = 0
                        ts['bullets_loaded_total']= int(ts.get('bullets_loaded_total', 0))+added
                        bh = ts.setdefault('bullets_loaded_history', [])
                        try:
                            bh.append({'weapon_id':str(weapon.get('id', 'unknown')), 'count':added, 'time':time.time()})
                        except Exception:
                            logging.exception("Suppressed exception")
            except Exception:
                logging.exception('Failed updating tracked_stats after internal reload')
            try:
                self._update_session_reload_stats(save_data, int(ammo_loaded))
            except Exception:
                logging.exception('Failed updating session reload stats after internal reload')
            return f"Internal magazine reloaded with {ammo_loaded} rounds(total: {len(current_rounds)}/{capacity})"

        for item in save_data.get("hands", {}).get("items", []):
            if item and isinstance(item, dict)and item.get("caliber")==caliber:
                qty = item.get("quantity", 0)
                if qty >0:
                    compatible_ammo.append((item, qty))

        for slot_name, eq_item in save_data.get("equipment", {}).items():
            if eq_item and "items"in eq_item:
                for item in eq_item["items"]:
                    if item and isinstance(item, dict)and item.get("caliber")==caliber:
                        qty = item.get("quantity", 0)
                        if qty >0:
                            compatible_ammo.append((item, qty))

        if not compatible_ammo:
            return "No compatible ammunition found!"

        ammo_needed = capacity -len(current_rounds)
        if is_en_bloc and weapon.get('chambered'):
            ammo_needed -= 1
        ammo_loaded = 0

        def make_round_obj(ammo_item):

            variant = ammo_item.get("variant")if isinstance(ammo_item, dict)else None
            name = ammo_item.get("name")if isinstance(ammo_item, dict)else None
            if variant:
                rnd_name = f"{caliber} | {variant}"
            elif name:
                rnd_name = f"{caliber} | {name}"
            else:
                rnd_name = f"{caliber}"
            return {"name":rnd_name, "caliber":caliber, "variant":variant}

        if "tube"in magazine_type:

            while ammo_loaded <ammo_needed and compatible_ammo:
                ammo_item, qty = compatible_ammo[0]
                rounds_to_load = min(1, qty, ammo_needed -ammo_loaded)

                for _ in range(rounds_to_load):

                    self._play_weapon_action_sound(weapon, "tubeinsert", block = True)
                    current_rounds.append(make_round_obj(ammo_item))
                    ammo_loaded +=1
                    ammo_item["quantity"]-=1

                if ammo_item["quantity"]<=0:
                    compatible_ammo.pop(0)

        elif is_en_bloc:

            def _find_loaded_en_bloc_clip(sd):
                desired_system = str(weapon.get('magazinesystem') or '').strip().lower()
                if not desired_system:
                    return None

                def _matches(itm):
                    if not itm or not isinstance(itm, dict):
                        return False
                    if str(itm.get('magazinesystem') or '').strip().lower() != desired_system:
                        return False
                    clip_rds = itm.get('rounds', [])
                    return isinstance(clip_rds, list) and len(clip_rds) > 0

                for itm in sd.get('hands', {}).get('items', []):
                    if _matches(itm):
                        return itm
                for _sn, eq in sd.get('equipment', {}).items():
                    if not eq or not isinstance(eq, dict):
                        continue
                    for itm in eq.get('items', []) or []:
                        if _matches(itm):
                            return itm
                    for sub in eq.get('subslots', []) or []:
                        curr = sub.get('current')
                        if curr and isinstance(curr, dict):
                            for itm in curr.get('items', []) or []:
                                if _matches(itm):
                                    return itm
                return None

            clip_item = _find_loaded_en_bloc_clip(save_data)
            if not clip_item:
                return 'No loaded en bloc clip found!'

            clip_rds = clip_item.get('rounds', [])
            rounds_from_clip = min(len(clip_rds), max(0, ammo_needed))
            for _ in range(rounds_from_clip):
                if not clip_rds:
                    break
                current_rounds.append(clip_rds.pop(0))
                ammo_loaded += 1

        elif "box"in magazine_type:

            rt_action_raw = weapon.get("action", "")or ""
            if isinstance(rt_action_raw, (list, tuple)):
                rt_action_raw = rt_action_raw[0]if rt_action_raw else ""
            rt_action = str(rt_action_raw).lower()
            is_bolt_action =(rt_action =="bolt"or "bolt"in rt_action)

            boltback_performed = False

            if is_bolt_action:
                self._play_weapon_action_sound(weapon, "boltactionback", block = True)
                time.sleep(0.2)
                boltback_performed = True

            # Try clip-based loading first if weapon accepts clips
            if weapon.get('accepts_clips') and weapon.get('clip_type'):
                wpn_clip_type = str(weapon.get('clip_type')).strip()
                def _find_loaded_clip_combat(sd):
                    for itm in sd.get('hands', {}).get('items', []):
                        if itm and isinstance(itm, dict) and str(itm.get('clip_type', '')).strip() == wpn_clip_type:
                            crds = itm.get('rounds', [])
                            if isinstance(crds, list) and len(crds) > 0:
                                return itm
                    for _sn, eq in sd.get('equipment', {}).items():
                        if not eq or not isinstance(eq, dict):
                            continue
                        for itm in eq.get('items', []) or []:
                            if itm and isinstance(itm, dict) and str(itm.get('clip_type', '')).strip() == wpn_clip_type:
                                crds = itm.get('rounds', [])
                                if isinstance(crds, list) and len(crds) > 0:
                                    return itm
                        for sub in eq.get('subslots', []) or []:
                            curr = sub.get('current')
                            if curr and isinstance(curr, dict):
                                for itm in curr.get('items', []) or []:
                                    if itm and isinstance(itm, dict) and str(itm.get('clip_type', '')).strip() == wpn_clip_type:
                                        crds = itm.get('rounds', [])
                                        if isinstance(crds, list) and len(crds) > 0:
                                            return itm
                    return None

                while ammo_loaded < ammo_needed:
                    clip_item = _find_loaded_clip_combat(save_data)
                    if not clip_item:
                        break
                    clip_rds = clip_item.get('rounds', [])
                    rounds_from_clip = min(len(clip_rds), ammo_needed - ammo_loaded)
                    for _ in range(rounds_from_clip):
                        if not clip_rds:
                            break
                        rnd = clip_rds.pop(0)
                        current_rounds.append(rnd)
                        ammo_loaded += 1
                    sound_action = f"bulletinsert{ammo_loaded % 2}"
                    self._play_weapon_action_sound(weapon, sound_action, block = False)
                    time.sleep(0.3)

            insert_index = ammo_loaded
            while ammo_loaded <ammo_needed and compatible_ammo:
                ammo_item, qty = compatible_ammo[0]
                rounds_to_load = min(1, qty, ammo_needed -ammo_loaded)

                for _ in range(rounds_to_load):
                    sound_action = f"bulletinsert{insert_index %2}"

                    self._play_weapon_action_sound(weapon, sound_action, block = False)
                    time.sleep(0.5)
                    current_rounds.append(make_round_obj(ammo_item))
                    ammo_loaded +=1
                    insert_index +=1
                    ammo_item["quantity"]-=1

                if ammo_item["quantity"]<=0:
                    compatible_ammo.pop(0)

        if ammo_loaded >0:

            had_chambered = bool(weapon.get("chambered"))
            if not had_chambered:

                rt_mag_type = str(weapon.get("magazinetype", "")or "").lower()
                rt_platform_raw = weapon.get("platform", "")or ""
                if isinstance(rt_platform_raw, (list, tuple)):
                    rt_platform_raw = rt_platform_raw[0]if rt_platform_raw else ""
                rt_platform = str(rt_platform_raw).lower()
                rt_action_raw = weapon.get("action", "")or ""
                if isinstance(rt_action_raw, (list, tuple)):
                    rt_action_raw = rt_action_raw[0]if rt_action_raw else ""
                rt_action = str(rt_action_raw).lower()
                is_pump_reload =("pump"in rt_platform or rt_action =="pump"or "pump"in rt_mag_type)

                if is_pump_reload:

                    cycle_result = "reloaded(pump required to chamber)"

                    try:
                        self._play_weapon_action_sound(weapon, "pumpforward")
                    except Exception:
                        logging.exception("Suppressed exception")
                elif is_en_bloc:
                    if not weapon.get('bolt_catch'):
                        self._play_weapon_action_sound(weapon, 'boltback', block = True)
                    self._play_weapon_action_sound(weapon, 'clipinsert', block = True)
                    if _garand_hold_open_reload:
                        garand_thumb_result = self._maybe_apply_garand_thumb(weapon, save_data)
                    if current_rounds:
                        weapon['chambered'] = current_rounds.pop(0)
                    self._play_weapon_action_sound(weapon, 'boltforward')
                else:
                    _rim_is_ba = (rt_action in ('bolt', 'lever', 'single'))
                    _rim_snd_back = 'boltactionback' if _rim_is_ba else 'boltback'
                    _rim_snd_fwd = 'boltactionforward' if _rim_is_ba else 'boltforward'

                    if not weapon.get("bolt_catch"):

                        if not boltback_performed:
                            self._play_weapon_action_sound(weapon, _rim_snd_back, block = True)

                        if weapon.get("gas_melted", False):
                            if current_rounds:
                                weapon["chambered"]= current_rounds.pop(0)
                            self._play_weapon_action_sound(weapon, _rim_snd_fwd)
                        else:
                            if current_rounds:
                                weapon["chambered"]= current_rounds.pop(0)
                            self._play_weapon_action_sound(weapon, _rim_snd_fwd)
                    else:

                        if current_rounds:
                            weapon["chambered"]= current_rounds.pop(0)
                        self._play_weapon_action_sound(weapon, _rim_snd_fwd)

        weapon["rounds"]= current_rounds
        try:
            sd_ref = save_data if isinstance(save_data, dict)else globals().get('save_data')or getattr(self, '_current_save_data', None)
            if isinstance(sd_ref, dict):
                ts = sd_ref.setdefault('tracked_stats', {})
                if isinstance(ts, dict):
                    ts['mags_reloaded_total']= int(ts.get('mags_reloaded_total', 0))+1
                    try:
                        added = int(ammo_loaded)
                    except Exception:
                        added = 0
                    ts['bullets_loaded_total']= int(ts.get('bullets_loaded_total', 0))+added
                    bh = ts.setdefault('bullets_loaded_history', [])
                    try:
                        bh.append({'weapon_id':str(weapon.get('id', 'unknown')), 'count':added, 'time':time.time()})
                    except Exception:
                        logging.exception("Suppressed exception")
        except Exception:
            logging.exception('Failed updating tracked_stats after internal reload')
        try:
            self._update_session_reload_stats(save_data, int(ammo_loaded))
        except Exception:
            logging.exception('Failed updating session reload stats after internal reload 2')
        if is_en_bloc:
            result_msg = f"En bloc clip loaded with {ammo_loaded} rounds(total: {len(current_rounds) + (1 if weapon.get('chambered') else 0)}/{capacity})"
            if isinstance(garand_thumb_result, dict):
                if garand_thumb_result.get('applied'):
                    result_msg += "\nGarand thumb: rolled under 5. Aim -1 for 30 minutes."
                elif garand_thumb_result.get('locked_out'):
                    result_msg += "\nGarand thumb already received on this character."
                else:
                    result_msg += f"\nGarand thumb check: d20 roll {garand_thumb_result.get('roll')}"
            return result_msg
        return f"Internal magazine reloaded with {ammo_loaded} rounds(total: {len(current_rounds)}/{capacity})"

    def _reload_revolver(self, weapon, save_data):

        capacity = weapon.get("capacity", 6)
        current_rounds = weapon.get("rounds", [])

        compatible_ammo =[]
        caliber_list = weapon.get("caliber", [])or[]
        caliber = caliber_list[0]if caliber_list else None

        if not caliber:
            return "Weapon has no caliber defined."

        for item in save_data.get("hands", {}).get("items", []):
            if item and isinstance(item, dict)and item.get("caliber")==caliber:
                qty = item.get("quantity", 0)
                if qty >0:
                    compatible_ammo.append((item, qty))

        for slot_name, eq_item in save_data.get("equipment", {}).items():
            if eq_item and "items"in eq_item:
                for item in eq_item["items"]:
                    if item and isinstance(item, dict)and item.get("caliber")==caliber:
                        qty = item.get("quantity", 0)
                        if qty >0:
                            compatible_ammo.append((item, qty))

        if not compatible_ammo:
            return "No compatible ammunition found!"

        ammo_needed = capacity -len(current_rounds)
        ammo_loaded = 0

        if bool(weapon.get('loading_gate')):
            chambers_with_cases = min(capacity, len(current_rounds) + int(weapon.get('_cylinder_spent', 0) or 0))
            try:
                self._play_cylinder_sound(weapon, 'hammer', block = False)
            except Exception:
                logging.exception("Suppressed exception")
            time.sleep(0.08)
            self._play_cylinder_sound(weapon, 'cylinderopen', block = True)
            time.sleep(0.15)

            insert_index = 0
            current_rounds.clear()
            for chamber_idx in range(capacity):
                if chamber_idx > 0:
                    self._play_cylinder_sound(weapon, 'cylinderspinonce', block = False)
                    time.sleep(0.12)

                if chamber_idx < chambers_with_cases:
                    self._play_cylinder_sound(weapon, 'cylinderrelease', block = False)
                    time.sleep(0.18)

                if compatible_ammo:
                    ammo_item, qty = compatible_ammo[0]
                    rounds_to_load = min(1, qty)
                    for _ in range(rounds_to_load):
                        sound_action = f"bulletinsert{insert_index %2}"
                        self._play_cylinder_sound(weapon, sound_action, block = False)
                        time.sleep(0.4)
                        current_rounds.append(f"{caliber}")
                        ammo_loaded += 1
                        insert_index += 1
                        ammo_item['quantity'] -= 1

                    if ammo_item['quantity'] <= 0:
                        compatible_ammo.pop(0)

            time.sleep(0.08)
            self._play_cylinder_sound(weapon, 'cylinderclose')
            time.sleep(0.08)
            self._play_cylinder_sound(weapon, 'hammerdown')
            weapon['_cylinder_spent'] = 0
            weapon['rounds'] = current_rounds

            try:
                sd_ref = save_data if isinstance(save_data, dict)else globals().get('save_data')or getattr(self, '_current_save_data', None)
                if isinstance(sd_ref, dict):
                    ts = sd_ref.setdefault('tracked_stats', {})
                    if isinstance(ts, dict):
                        ts['mags_reloaded_total']= int(ts.get('mags_reloaded_total', 0))+1
                        try:
                            added = int(ammo_loaded)
                        except Exception:
                            added = 0
                        ts['bullets_loaded_total']= int(ts.get('bullets_loaded_total', 0))+added
                        bh = ts.setdefault('bullets_loaded_history', [])
                        try:
                            bh.append({'weapon_id':str(weapon.get('id', 'unknown')), 'count':added, 'time':time.time()})
                        except Exception:
                            logging.exception("Suppressed exception")
            except Exception:
                logging.exception('Failed updating tracked_stats after loading gate revolver reload')
            try:
                self._update_session_reload_stats(save_data, int(ammo_loaded))
            except Exception:
                logging.exception('Failed updating session reload stats after loading gate revolver reload')
            return f"Loading gate revolver reloaded with {ammo_loaded} rounds(total: {len(current_rounds)}/{capacity})"

        self._play_weapon_action_sound(weapon, "cylinderopen", block = True)
        time.sleep(0.2)

        self._play_weapon_action_sound(weapon, "cylinderrelease", block = True)
        time.sleep(0.15)
        current_rounds.clear()

        insert_index = 0
        while ammo_loaded <ammo_needed and compatible_ammo:
            ammo_item, qty = compatible_ammo[0]
            rounds_to_load = min(1, qty, ammo_needed -ammo_loaded)

            for _ in range(rounds_to_load):

                sound_action = f"bulletinsert{insert_index %2}"

                self._play_weapon_action_sound(weapon, sound_action, block = False)
                time.sleep(0.5)
                current_rounds.append(f"{caliber}")
                ammo_loaded +=1
                insert_index +=1
                ammo_item["quantity"]-=1

            if ammo_item["quantity"]<=0:
                compatible_ammo.pop(0)

        time.sleep(0.1)
        self._play_weapon_action_sound(weapon, "cylinderclose")
        time.sleep(0.1)

        weapon["rounds"]= current_rounds
        try:
            sd_ref = save_data if isinstance(save_data, dict)else globals().get('save_data')or getattr(self, '_current_save_data', None)
            if isinstance(sd_ref, dict):
                ts = sd_ref.setdefault('tracked_stats', {})
                if isinstance(ts, dict):
                    ts['mags_reloaded_total']= int(ts.get('mags_reloaded_total', 0))+1
                    try:
                        added = int(ammo_loaded)
                    except Exception:
                        added = 0
                    ts['bullets_loaded_total']= int(ts.get('bullets_loaded_total', 0))+added
                    bh = ts.setdefault('bullets_loaded_history', [])
                    try:
                        bh.append({'weapon_id':str(weapon.get('id', 'unknown')), 'count':added, 'time':time.time()})
                    except Exception:
                        logging.exception("Suppressed exception")
        except Exception:
            logging.exception('Failed updating tracked_stats after revolver reload')
        try:
            self._update_session_reload_stats(save_data, int(ammo_loaded))
        except Exception:
            logging.exception('Failed updating session reload stats after revolver reload')
        return f"Revolver reloaded with {ammo_loaded} rounds(total: {len(current_rounds)}/{capacity})"

    def _reload_cylinder(self, weapon, save_data):

        capacity = weapon.get("capacity", 6)
        current_rounds = weapon.get("rounds", [])

        compatible_ammo =[]
        caliber_list = weapon.get("caliber", [])or[]
        caliber = caliber_list[0]if caliber_list else None

        if not caliber:
            return "Weapon has no caliber defined."

        for item in save_data.get("hands", {}).get("items", []):
            if item and isinstance(item, dict)and item.get("caliber")==caliber:
                qty = item.get("quantity", 0)
                if qty >0:
                    compatible_ammo.append((item, qty))

        for slot_name, eq_item in save_data.get("equipment", {}).items():
            if eq_item and "items"in eq_item:
                for item in eq_item["items"]:
                    if item and isinstance(item, dict)and item.get("caliber")==caliber:
                        qty = item.get("quantity", 0)
                        if qty >0:
                            compatible_ammo.append((item, qty))

        if not compatible_ammo:
            return "No compatible ammunition found!"

        ammo_needed = capacity -len(current_rounds)
        ammo_loaded = 0

        if bool(weapon.get('loading_gate')):
            chambers_with_cases = min(capacity, len(current_rounds) + int(weapon.get('_cylinder_spent', 0) or 0))
            try:
                self._play_cylinder_sound(weapon, 'hammer', block = False)
            except Exception:
                logging.exception("Suppressed exception")
            time.sleep(0.08)
            self._play_cylinder_sound(weapon, "cylinderopen", block = True)
            time.sleep(0.15)

            insert_index = 0
            current_rounds.clear()
            for chamber_idx in range(capacity):
                if chamber_idx > 0:
                    self._play_cylinder_sound(weapon, 'cylinderspinonce', block = False)
                    time.sleep(0.12)

                if chamber_idx < chambers_with_cases:
                    self._play_cylinder_sound(weapon, 'cylinderrelease', block = False)
                    time.sleep(0.18)

                if compatible_ammo:
                    ammo_item, qty = compatible_ammo[0]
                    rounds_to_load = min(1, qty)
                    for _ in range(rounds_to_load):
                        sound_action = f"bulletinsert{insert_index %2}"
                        self._play_cylinder_sound(weapon, sound_action, block = False)
                        time.sleep(0.4)
                        current_rounds.append(f"{caliber}")
                        ammo_loaded += 1
                        insert_index += 1
                        ammo_item['quantity'] -= 1

                    if ammo_item['quantity'] <= 0:
                        compatible_ammo.pop(0)

            time.sleep(0.08)
            self._play_cylinder_sound(weapon, "cylinderclose")
            time.sleep(0.08)
            self._play_cylinder_sound(weapon, "hammerdown")
            weapon['_cylinder_spent'] = 0
            weapon["rounds"] = current_rounds

            try:
                sd_ref = save_data if isinstance(save_data, dict)else globals().get('save_data')or getattr(self, '_current_save_data', None)
                if isinstance(sd_ref, dict):
                    ts = sd_ref.setdefault('tracked_stats', {})
                    if isinstance(ts, dict):
                        ts['mags_reloaded_total']= int(ts.get('mags_reloaded_total', 0))+1
                        try:
                            added = int(ammo_loaded)
                        except Exception:
                            added = 0
                        ts['bullets_loaded_total']= int(ts.get('bullets_loaded_total', 0))+added
                        bh = ts.setdefault('bullets_loaded_history', [])
                        try:
                            bh.append({'weapon_id':str(weapon.get('id', 'unknown')), 'count':added, 'time':time.time()})
                        except Exception:
                            logging.exception("Suppressed exception")
            except Exception:
                logging.exception('Failed updating tracked_stats after loading gate cylinder reload')
            try:
                self._update_session_reload_stats(save_data, int(ammo_loaded))
            except Exception:
                logging.exception('Failed updating session reload stats after loading gate cylinder reload')
            return f"Loading gate cylinder reloaded with {ammo_loaded} rounds(total: {len(current_rounds)}/{capacity})"

        if bool(weapon.get('revolver_topbreak')):
            self._play_cylinder_sound(weapon, "cylinderopen", block = True)
            time.sleep(0.18)

            self._play_cylinder_sound(weapon, "cylinderrelease", block = True)
            time.sleep(0.16)
            current_rounds.clear()
            weapon['_cylinder_spent'] = 0

            insert_index = 0
            while ammo_loaded <ammo_needed and compatible_ammo:
                ammo_item, qty = compatible_ammo[0]
                rounds_to_load = min(1, qty, ammo_needed -ammo_loaded)

                for _ in range(rounds_to_load):
                    sound_action = f"bulletinsert{insert_index %2}"
                    self._play_cylinder_sound(weapon, sound_action, block = False)
                    time.sleep(0.45)
                    current_rounds.append(f"{caliber}")
                    ammo_loaded +=1
                    insert_index +=1
                    ammo_item["quantity"]-=1

                if ammo_item["quantity"]<=0:
                    compatible_ammo.pop(0)

            time.sleep(0.08)
            self._play_cylinder_sound(weapon, "cylinderclose")
            time.sleep(0.1)

            weapon["rounds"]= current_rounds

            action = weapon.get("action", "")
            if isinstance(action, (list, tuple)):
                action = action[0]if action else ""
            action = str(action).lower()
            if action =="single":
                time.sleep(0.1)
                self._play_cylinder_sound(weapon, "hammerdown")

            try:
                sd_ref = save_data if isinstance(save_data, dict)else globals().get('save_data')or getattr(self, '_current_save_data', None)
                if isinstance(sd_ref, dict):
                    ts = sd_ref.setdefault('tracked_stats', {})
                    if isinstance(ts, dict):
                        ts['mags_reloaded_total']= int(ts.get('mags_reloaded_total', 0))+1
                        try:
                            added = int(ammo_loaded)
                        except Exception:
                            added = 0
                        ts['bullets_loaded_total']= int(ts.get('bullets_loaded_total', 0))+added
                        bh = ts.setdefault('bullets_loaded_history', [])
                        try:
                            bh.append({'weapon_id':str(weapon.get('id', 'unknown')), 'count':added, 'time':time.time()})
                        except Exception:
                            logging.exception("Suppressed exception")
            except Exception:
                logging.exception('Failed updating tracked_stats after top-break cylinder reload')
            try:
                self._update_session_reload_stats(save_data, int(ammo_loaded))
            except Exception:
                logging.exception('Failed updating session reload stats after top-break cylinder reload')
            return f"Top-break revolver reloaded with {ammo_loaded} rounds(total: {len(current_rounds)}/{capacity})"

        self._play_cylinder_sound(weapon, "cylinderopen", block = True)
        time.sleep(0.2)

        self._play_cylinder_sound(weapon, "cylinderrelease", block = True)
        time.sleep(0.15)
        current_rounds.clear()

        insert_index = 0
        while ammo_loaded <ammo_needed and compatible_ammo:
            ammo_item, qty = compatible_ammo[0]
            rounds_to_load = min(1, qty, ammo_needed -ammo_loaded)

            for _ in range(rounds_to_load):
                sound_action = f"bulletinsert{insert_index %2}"
                self._play_cylinder_sound(weapon, sound_action, block = False)
                time.sleep(0.5)
                current_rounds.append(f"{caliber}")
                ammo_loaded +=1
                insert_index +=1
                ammo_item["quantity"]-=1

            if ammo_item["quantity"]<=0:
                compatible_ammo.pop(0)

        time.sleep(0.1)
        self._play_cylinder_sound(weapon, "cylinderclose")
        time.sleep(0.1)

        weapon["rounds"]= current_rounds

        action = weapon.get("action", "")
        if isinstance(action, (list, tuple)):
            action = action[0]if action else ""
        action = str(action).lower()
        if action =="single":
            time.sleep(0.1)
            self._play_cylinder_sound(weapon, "hammerdown")

        try:
            sd_ref = save_data if isinstance(save_data, dict)else globals().get('save_data')or getattr(self, '_current_save_data', None)
            if isinstance(sd_ref, dict):
                ts = sd_ref.setdefault('tracked_stats', {})
                if isinstance(ts, dict):
                    ts['mags_reloaded_total']= int(ts.get('mags_reloaded_total', 0))+1
                    try:
                        added = int(ammo_loaded)
                    except Exception:
                        added = 0
                    ts['bullets_loaded_total']= int(ts.get('bullets_loaded_total', 0))+added
                    bh = ts.setdefault('bullets_loaded_history', [])
                    try:
                        bh.append({'weapon_id':str(weapon.get('id', 'unknown')), 'count':added, 'time':time.time()})
                    except Exception:
                        logging.exception("Suppressed exception")
        except Exception:
            logging.exception('Failed updating tracked_stats after cylinder reload')
        try:
            self._update_session_reload_stats(save_data, int(ammo_loaded))
        except Exception:
            logging.exception('Failed updating session reload stats after cylinder reload')
        return f"Cylinder reloaded with {ammo_loaded} rounds(total: {len(current_rounds)}/{capacity})"

    def _muzzleloader_get_ammo_availability(self, weapon, save_data):

        caliber_list = weapon.get("musket_caliber") or weapon.get("caliber") or []
        caliber = caliber_list[0] if caliber_list else None
        caliber_lower = str(caliber or "").lower()

        all_items = []
        for item in save_data.get("hands", {}).get("items", []):
            if item and isinstance(item, dict):
                all_items.append(item)
        for slot_name, eq_item in save_data.get("equipment", {}).items():
            if eq_item and isinstance(eq_item, dict) and "items" in eq_item:
                for item in eq_item["items"]:
                    if item and isinstance(item, dict):
                        all_items.append(item)

        has_cartridge = False
        has_ball = False
        has_powder = False

        for item in all_items:
            item_type = str(item.get("type", "")).lower()
            item_caliber = item.get("musket_caliber") or item.get("caliber")
            if isinstance(item_caliber, list):
                item_caliber = item_caliber[0] if item_caliber else None
            item_caliber_lower = str(item_caliber or "").lower()

            if item_type == "gunpowder" and item.get("grains_left", 0) > 0:
                has_powder = True
            if item_type == "musket_paper_cartridge":
                qty = item.get("quantity", 0) or item.get("random_quantity", 0)
                if isinstance(qty, dict):
                    qty = 1
                if qty > 0 and item_caliber_lower == caliber_lower:
                    has_cartridge = True
            elif item_type == "musket_ball":
                qty = item.get("quantity", 0) or item.get("random_quantity", 0)
                if isinstance(qty, dict):
                    qty = 1
                if qty > 0 and item_caliber_lower == caliber_lower:
                    has_ball = True

        return has_cartridge, (has_ball and has_powder)

    def _muzzleloader_pour_minigame(self, popup, status_label, intelligence, on_complete):

        BAR_WIDTH = 350
        BAR_HEIGHT = 30

        green_width = max(30, min(160, 40 + int(intelligence) * 6))
        speed = max(1.5, min(8.0, 6.0 - float(intelligence) * 0.35))

        green_start = random.randint(10, max(11, BAR_WIDTH - green_width - 10))
        green_end = green_start + green_width

        status_label.configure(text="Pour gunpowder — press SPACE to stop!")

        mg_frame = customtkinter.CTkFrame(popup, fg_color="transparent")
        mg_frame.pack(pady=(5, 5))

        instr_label = customtkinter.CTkLabel(
            mg_frame, text="Stop the marker in the green zone!",
            font=customtkinter.CTkFont(size=11)
        )
        instr_label.pack(pady=(0, 3))

        canvas = _tk.Canvas(mg_frame, width=BAR_WIDTH, height=BAR_HEIGHT,
                            bg='#8B0000', highlightthickness=1, highlightbackground='#444444')
        canvas.pack()

        canvas.create_rectangle(green_start, 0, green_end, BAR_HEIGHT,
                                fill='#228B22', outline='')

        slider = canvas.create_rectangle(0, 0, 5, BAR_HEIGHT, fill='white', outline='#CCCCCC')

        mg_state = {'pos': 0.0, 'direction': 1, 'active': True}

        def _animate():
            if not mg_state['active']:
                return
            mg_state['pos'] += speed * mg_state['direction']
            if mg_state['pos'] >= BAR_WIDTH - 5:
                mg_state['pos'] = BAR_WIDTH - 5
                mg_state['direction'] = -1
            elif mg_state['pos'] <= 0:
                mg_state['pos'] = 0
                mg_state['direction'] = 1
            canvas.coords(slider, int(mg_state['pos']), 0, int(mg_state['pos']) + 5, BAR_HEIGHT)
            popup.after(16, _animate)

        def _stop(event=None):
            if not mg_state['active']:
                return
            mg_state['active'] = False
            pos = mg_state['pos']
            success = green_start <= pos <= green_end - 5

            color = '#00FF00' if success else '#FF4444'
            canvas.create_rectangle(int(pos), 0, int(pos) + 5, BAR_HEIGHT,
                                    fill=color, outline='')
            result_text = "Good pour!" if success else "Spilled powder!"
            instr_label.configure(text=result_text)

            def _cleanup():
                try:
                    popup.unbind('<space>', bind_id)
                except Exception:
                    logging.exception("Suppressed exception")
                try:
                    mg_frame.destroy()
                except Exception:
                    logging.exception("Suppressed exception")
                on_complete(success)

            popup.after(600, _cleanup)

        bind_id = popup.bind('<space>', _stop)
        popup.after(50, _animate)

    def _reload_muzzleloader_ui(self, weapon, save_data, update_weapon_view=None):

        try:
            result = self._reload_muzzleloader_check(weapon, save_data)
            if result:
                self._popup_show_info("Reload Result", result)
                return
        except Exception as e:
            self._popup_show_info("Reload Error", str(e))
            return

        has_cartridge, has_ball_powder = self._muzzleloader_get_ammo_availability(weapon, save_data)

        if has_cartridge and has_ball_powder:
            sel_popup = customtkinter.CTkToplevel(self.root)
            sel_popup.title("Select Ammunition")
            sel_popup.transient(self.root)
            self._center_popup_on_window(sel_popup, 340, 160)
            sel_popup.grab_set()

            customtkinter.CTkLabel(
                sel_popup, text="Choose ammunition type:",
                font=customtkinter.CTkFont(size=14)
            ).pack(pady=(20, 10))

            btn_frame = customtkinter.CTkFrame(sel_popup, fg_color="transparent")
            btn_frame.pack(pady=10)

            def _pick(use_cart):
                try:
                    sel_popup.grab_release()
                    sel_popup.destroy()
                except Exception:
                    logging.exception("Suppressed exception")
                self._reload_muzzleloader_ui_run(weapon, save_data, update_weapon_view, use_cartridge=use_cart)

            customtkinter.CTkButton(
                btn_frame, text="Paper Cartridge", width=140,
                command=lambda: _pick(True)
            ).pack(side="left", padx=5)
            customtkinter.CTkButton(
                btn_frame, text="Powder + Ball", width=140,
                command=lambda: _pick(False)
            ).pack(side="left", padx=5)
        elif has_ball_powder:
            self._reload_muzzleloader_ui_run(weapon, save_data, update_weapon_view, use_cartridge=False)
        else:
            self._reload_muzzleloader_ui_run(weapon, save_data, update_weapon_view, use_cartridge=True)

    def _reload_muzzleloader_ui_run(self, weapon, save_data, update_weapon_view, use_cartridge):

        is_rifled = bool(weapon.get("rifling", False))
        musket_sound_folder = os.path.join("sounds", "firearms", "weaponsounds", "musket")

        popup_height = 160 if use_cartridge else 240
        popup = customtkinter.CTkToplevel(self.root)
        popup.title("Reloading Muzzleloader")
        popup.transient(self.root)
        self._center_popup_on_window(popup, 420, popup_height)
        popup.grab_set()

        status_label = customtkinter.CTkLabel(
            popup,
            text="Preparing to reload...",
            font=customtkinter.CTkFont(size=14)
        )
        status_label.pack(pady=(20, 10))

        progress_bar = customtkinter.CTkProgressBar(popup, width=350)
        progress_bar.pack(pady=10)
        progress_bar.set(0.0)

        if use_cartridge:
            steps = [
                ("Half-cocking hammer", "hammer.ogg", 0.3, False),
                ("Looking for cartridge", "search.ogg", 0.5, False),
                ("Tearing cartridge open with mouth", "tear.ogg", 0, False),
                ("Spitting paper out", "spit.ogg", 0.2, False),
                ("Pouring gunpowder in flash pan", "pour.ogg", 0.4, False),
                ("Closing frizzen", "frizzen.ogg", 0.5, False),
                ("Inserting cartridge", "insert.ogg", 0.4, False),
                ("Drawing ramrod", "ramrod_holder.ogg", 0.2, False),
            ]

            if not is_rifled:
                steps.append(("Ramming ball", "ramrod_barrel.ogg", 0, False))
            else:
                steps.append(("Ramming ball...", None, 5.0, False))

            steps.extend([
                ("Tamping ball", "ramrod_tap.ogg", 0, False),
                ("Withdrawing ramrod", "ramrod_barrel.ogg", 0.3, False),
                ("Stowing ramrod", "ramrod_holder.ogg", 0.1, False),
            ])
        else:
            steps = [
                ("Half-cocking hammer", "hammer.ogg", 0.3, False),
                ("Looking for ball and powder", "search.ogg", 0.5, False),
                ("Pouring gunpowder in flash pan", "pour.ogg", 0, True),
                ("Closing frizzen", "frizzen.ogg", 0.5, False),
                ("Pouring gunpowder in barrel", "pour.ogg", 0, True),
                ("Drawing ramrod", "ramrod_holder.ogg", 0.2, False),
            ]

            if not is_rifled:
                steps.append(("Ramming powder", "ramrod_barrel.ogg", 0, False))
            else:
                steps.append(("Ramming powder...", None, 5.0, False))

            steps.extend([
                ("Stowing ramrod", "ramrod_holder.ogg", 0.1, False),
                ("Inserting ball", "insert.ogg", 0.4, False),
                ("Drawing ramrod", "ramrod_holder.ogg", 0.2, False),
                ("Seating ball", "ramrod_barrel.ogg", 0, False),
                ("Tamping ball", "ramrod_tap.ogg", 0, False),
                ("Withdrawing ramrod", "ramrod_barrel.ogg", 0.3, False),
                ("Stowing ramrod", "ramrod_holder.ogg", 0.1, False),
            ])

        total_steps = len(steps)
        state = {"index": 0, "minigame_wins": 0, "minigame_losses": 0}

        intelligence = 0
        try:
            sd_stats = save_data.get("stats", {}) or {}
            intelligence = float(sd_stats.get("Intelligence", 0) or 0)
        except Exception:
            intelligence = 0

        def _play_step():
            idx = state["index"]
            if idx >= total_steps:
                progress_bar.set(1.0)
                status_label.configure(text="Reload complete!")

                aim_bonus = 0
                if not use_cartridge:
                    wins = state["minigame_wins"]
                    losses = state["minigame_losses"]
                    if wins == 2:
                        aim_bonus = 1
                    aim_bonus -= losses

                result = self._reload_muzzleloader_finish(weapon, save_data, use_cartridge=use_cartridge, aim_bonus=aim_bonus)

                def _close():
                    try:
                        popup.grab_release()
                        popup.destroy()
                    except Exception:
                        logging.exception("Suppressed exception")
                    self._popup_show_info("Reload Result", result)
                    if update_weapon_view:
                        try:
                            update_weapon_view()
                        except Exception:
                            logging.exception("Suppressed exception")

                popup.after(400, _close)
                return

            step_label, sound_file, delay, is_minigame = steps[idx]
            progress_bar.set(idx / total_steps)
            status_label.configure(text=step_label)

            sound_duration = 0
            if sound_file:
                path = os.path.join(musket_sound_folder, sound_file)
                if os.path.exists(path):
                    try:
                        snd = pygame.mixer.Sound(path)
                        sound_duration = snd.get_length()
                        channel = pygame.mixer.find_channel()
                        if channel:
                            channel.play(snd)
                    except Exception:
                        try:
                            self._safe_sound_play("", path, block=False)
                        except Exception:
                            logging.exception("Suppressed exception")

            state["index"] += 1

            if is_minigame:
                def _on_minigame_done(success):
                    if success:
                        state["minigame_wins"] += 1
                    else:
                        state["minigame_losses"] += 1
                    popup.after(200, _play_step)

                wait_time = max(sound_duration, delay)
                delay_ms = max(100, int(wait_time * 1000))
                popup.after(delay_ms, lambda: self._muzzleloader_pour_minigame(popup, status_label, intelligence, _on_minigame_done))
            else:
                wait_time = max(sound_duration, delay)
                delay_ms = max(100, int(wait_time * 1000))
                popup.after(delay_ms, _play_step)

        popup.after(100, _play_step)

    def _reload_muzzleloader_check(self, weapon, save_data):

        if weapon.get("chambered"):
            return "Weapon is already loaded."

        caliber_list = weapon.get("musket_caliber") or weapon.get("caliber") or []
        caliber = caliber_list[0] if caliber_list else None
        caliber_lower = str(caliber or "").lower()

        all_items = []
        for item in save_data.get("hands", {}).get("items", []):
            if item and isinstance(item, dict):
                all_items.append(item)
        for slot_name, eq_item in save_data.get("equipment", {}).items():
            if eq_item and isinstance(eq_item, dict) and "items" in eq_item:
                for item in eq_item["items"]:
                    if item and isinstance(item, dict):
                        all_items.append(item)

        has_cartridge = False
        has_ball = False
        has_powder = False

        for item in all_items:
            item_type = str(item.get("type", "")).lower()
            item_caliber = item.get("musket_caliber") or item.get("caliber")
            if isinstance(item_caliber, list):
                item_caliber = item_caliber[0] if item_caliber else None
            item_caliber_lower = str(item_caliber or "").lower()

            if item_type == "gunpowder" and item.get("grains_left", 0) > 0:
                has_powder = True
            if item_type == "musket_paper_cartridge":
                qty = item.get("quantity", 0) or item.get("random_quantity", 0)
                if isinstance(qty, dict):
                    qty = 1
                if qty > 0 and item_caliber_lower == caliber_lower:
                    has_cartridge = True
            elif item_type == "musket_ball":
                qty = item.get("quantity", 0) or item.get("random_quantity", 0)
                if isinstance(qty, dict):
                    qty = 1
                if qty > 0 and item_caliber_lower == caliber_lower:
                    has_ball = True

        if has_cartridge or (has_ball and has_powder):
            return None
        if has_ball and not has_powder:
            return "No black powder available!"
        return "No compatible ammunition found!"

    def _reload_muzzleloader_finish(self, weapon, save_data, use_cartridge=None, aim_bonus=0):

        try:
            caliber_list = weapon.get("musket_caliber") or weapon.get("caliber") or []
            caliber = caliber_list[0] if caliber_list else None
            caliber_lower = str(caliber or "").lower()

            compatible_ball = []
            compatible_cartridge = []
            powder_source = None

            all_items = []
            for item in save_data.get("hands", {}).get("items", []):
                if item and isinstance(item, dict):
                    all_items.append(item)
            for slot_name, eq_item in save_data.get("equipment", {}).items():
                if eq_item and isinstance(eq_item, dict) and "items" in eq_item:
                    for item in eq_item["items"]:
                        if item and isinstance(item, dict):
                            all_items.append(item)

            for item in all_items:
                item_type = str(item.get("type", "")).lower()
                item_caliber = item.get("musket_caliber") or item.get("caliber")
                if isinstance(item_caliber, list):
                    item_caliber = item_caliber[0] if item_caliber else None
                item_caliber_lower = str(item_caliber or "").lower()

                if item_type == "gunpowder" and item.get("grains_left", 0) > 0:
                    if not powder_source:
                        powder_source = item
                if item_type == "musket_paper_cartridge":
                    qty = item.get("quantity", 0) or item.get("random_quantity", 0)
                    if isinstance(qty, dict):
                        qty = 1
                    if qty > 0 and item_caliber_lower == caliber_lower:
                        compatible_cartridge.append(item)
                elif item_type == "musket_ball":
                    qty = item.get("quantity", 0) or item.get("random_quantity", 0)
                    if isinstance(qty, dict):
                        qty = 1
                    if qty > 0 and item_caliber_lower == caliber_lower:
                        compatible_ball.append(item)

            cartridge_item = None
            ball_item = None
            grains_used = random.randint(110, 130)

            if use_cartridge is None:
                if compatible_cartridge:
                    use_cartridge = True
                    cartridge_item = compatible_cartridge[0]
                elif compatible_ball and powder_source:
                    use_cartridge = False
                    ball_item = compatible_ball[0]
                else:
                    return "No compatible ammunition found!"
            elif use_cartridge:
                if compatible_cartridge:
                    cartridge_item = compatible_cartridge[0]
                else:
                    return "No paper cartridges found!"
            else:
                if compatible_ball and powder_source:
                    ball_item = compatible_ball[0]
                else:
                    return "No musket balls or black powder found!"

            if use_cartridge:
                qty = cartridge_item.get("quantity", 1)
                if isinstance(qty, (int, float)) and qty > 0:
                    cartridge_item["quantity"] = qty - 1
                round_name = f"{caliber} | Paper Cartridge"
            else:
                qty = ball_item.get("quantity", 1)
                if isinstance(qty, (int, float)) and qty > 0:
                    ball_item["quantity"] = qty - 1
                current_grains = powder_source.get("grains_left", 0)
                powder_source["grains_left"] = max(0, current_grains - grains_used)
                try:
                    full_grains = int(powder_source.get("grain_storage", 0) or 0)
                except(Exception, ValueError, TypeError):
                    full_grains = 0
                if full_grains <= 0:
                    try:
                        full_grains = max(1, int(current_grains or 0))
                    except(Exception, ValueError, TypeError):
                        full_grains = 1
                powder_source["grain_storage"] = full_grains
                try:
                    full_weight = float(powder_source.get("weight_full", powder_source.get("weight", 0)) or 0)
                except(Exception, ValueError, TypeError):
                    full_weight = 0.0
                powder_source["weight_full"] = full_weight
                try:
                    grains_after = int(powder_source.get("grains_left", 0) or 0)
                except(Exception, ValueError, TypeError):
                    grains_after = 0
                ratio = 0.0 if full_grains <= 0 else max(0.0, min(1.0, float(grains_after) / float(full_grains)))
                powder_source["weight"] = round(full_weight * ratio, 6)
                round_name = f"{caliber} | Musket Ball"

            chambered_round = {"name": round_name, "caliber": caliber}
            if aim_bonus != 0:
                chambered_round["modifiers"] = {"stats": {"aim": aim_bonus}}

            weapon["chambered"] = chambered_round
            weapon["rounds"] = []

            try:
                sd_ref = save_data if isinstance(save_data, dict) else globals().get('save_data') or getattr(self, '_current_save_data', None)
                if isinstance(sd_ref, dict):
                    ts = sd_ref.setdefault('tracked_stats', {})
                    if isinstance(ts, dict):
                        ts['mags_reloaded_total'] = int(ts.get('mags_reloaded_total', 0)) + 1
                        ts['bullets_loaded_total'] = int(ts.get('bullets_loaded_total', 0)) + 1
                        bh = ts.setdefault('bullets_loaded_history', [])
                        try:
                            bh.append({'weapon_id': str(weapon.get('id', 'unknown')), 'count': 1, 'time': time.time()})
                        except Exception:
                            logging.exception("Suppressed exception")
            except Exception:
                logging.exception('Failed updating tracked_stats after muzzleloader reload')
            try:
                self._update_session_reload_stats(save_data, 1)
            except Exception:
                logging.exception('Failed updating session reload stats after muzzleloader reload')

            method = "paper cartridge" if use_cartridge else f"musket ball + {grains_used} grains black powder"
            result_msg = f"Muzzleloader reloaded with {method}"
            if aim_bonus > 0:
                result_msg += f"\nPowder pour bonus: +{aim_bonus} aim"
            elif aim_bonus < 0:
                result_msg += f"\nPowder pour penalty: {aim_bonus} aim"
            return result_msg

        except Exception as e:
            logging.exception("Failed to reload muzzleloader")
            return f"Reload failed: {e}"

    def _play_cylinder_sound(self, weapon, action_type, block = False):

        try:
            platform = str(weapon.get("platform", "")or "").lower().replace('/', '_')
            sound_folder = weapon.get("sounds")or weapon.get("sound_folder")or weapon.get("fire_sounds")or weapon.get("reload_sounds")

            candidates =[]

            if sound_folder:
                wf = os.path.join("sounds", "firearms", "weaponsounds", str(sound_folder).lower().replace('/', '_'))
                candidates = glob.glob(os.path.join(wf, f"{action_type}*.ogg"))+glob.glob(os.path.join(wf, f"{action_type}*.wav"))

            if not candidates and platform:
                wf = os.path.join("sounds", "firearms", "weaponsounds", platform)
                candidates = glob.glob(os.path.join(wf, f"{action_type}*.ogg"))+glob.glob(os.path.join(wf, f"{action_type}*.wav"))

            if not candidates:
                uni = os.path.join("sounds", "firearms", "universal")
                candidates = glob.glob(os.path.join(uni, f"{action_type}*.ogg"))+glob.glob(os.path.join(uni, f"{action_type}*.wav"))

            if candidates:
                sound_file = random.choice(candidates)
                logging.debug("_play_cylinder_sound: %s -> %s", action_type, sound_file)
                self._safe_sound_play("", sound_file, block = block)
            else:
                logging.debug("_play_cylinder_sound: no sound found for %s", action_type)
        except Exception as e:
            logging.error(f"Error playing cylinder sound: {e}")

    def _clean_weapon(self, weapon, combat_state):

        weapon_id = str(weapon.get("id"))
        logging.info("_clean_weapon start: id=%s name=%s", weapon_id, weapon.get("name", "Unknown"))

        cleanliness = _get_weapon_cleanliness(combat_state, weapon, default = 100.0, cache_to_state = True)
        cause_text = f"Cleaning weapon (current cleanliness: {cleanliness:.0f}%)"

        mg_popup = None
        try:
            mg_popup = self._create_action_minigame_popup("Cleaning Weapon", cause_text, key_count = 5)
        except Exception:
            mg_popup = None

        cleaning_channel = None
        try:
            if mg_popup:
                mg_popup["update"]("Disassembling...")

            try:
                cleaning_path = os.path.join("sounds", "firearms", "universal", "cleaning.ogg")
                if os.path.exists(cleaning_path):
                    if not hasattr(self, "_sound_cache"):
                        self._sound_cache = {}
                    snd = self._sound_cache.get(cleaning_path)
                    if snd is None:
                        snd = pygame.mixer.Sound(cleaning_path)
                        self._sound_cache[cleaning_path] = snd
                    cleaning_channel = snd.play()
                else:
                    self._play_weapon_action_sound(weapon, "cleaning")
            except Exception:
                self._play_weapon_action_sound(weapon, "cleaning")

            _mg_completed = mg_popup["completed"] if mg_popup else None
            _mg_set_progress = mg_popup.get("set_progress") if mg_popup else None
            wait_time = random.uniform(6.0, 10.0)

            if mg_popup:
                mg_popup["update"]("Cleaning and lubricating...")
            if _mg_completed:
                self._interruptible_wait(_mg_completed, wait_time, progress_callback = _mg_set_progress)
            else:
                time.sleep(wait_time)

            if mg_popup:
                mg_popup["update"]("Reassembling...")
            time.sleep(0.3)
        finally:
            if cleaning_channel:
                try:
                    cleaning_channel.stop()
                except Exception:
                    logging.exception("Suppressed exception")
            if mg_popup:
                try:
                    mg_popup["close"]()
                except Exception:
                    logging.exception("Suppressed exception")

        if "barrel_cleanliness"not in combat_state:
            combat_state["barrel_cleanliness"]= {}

        combat_state["barrel_cleanliness"][weapon_id]= 100

        try:
            if weapon.get("gas_melted", False):
                weapon["gas_melted"]= False
                logging.info("Weapon %s gas system repaired by cleaning", weapon.get("name", weapon_id))
        except Exception:
            logging.exception("Suppressed exception")

        return "Weapon cleaned and maintained."

    def _cycle_bolt(self, weapon):

        logging.info("_cycle_bolt start: name=%s", weapon.get("name", "Unknown"))

        actions = weapon.get("action", [])
        magazine_type =(weapon.get("magazinetype")or "").lower()
        is_internal = "internal"in magazine_type or "tube"in magazine_type
        is_revolver = "revolver"in(weapon.get("platform", "")or "").lower()

        chambered = weapon.get("chambered")
        if chambered:
            logging.info("Cycle action: ejecting chambered round")
            self._play_weapon_action_sound(weapon, "boltback", block = True)
            self._play_weapon_action_sound(weapon, "shelleject")
            time.sleep(0.2)

            weapon["chambered"]= None
            message = "Ejected chambered round."
        else:
            message = ""

        if is_internal or is_revolver:
            internal_rounds = weapon.get("rounds", [])
            if not internal_rounds:
                self._play_weapon_action_sound(weapon, "boltback", block = True)
                self._play_weapon_action_sound(weapon, "boltforward")
                return message +"No rounds in magazine - action cycled but no round chambered."

            self._play_weapon_action_sound(weapon, "boltback", block = True)
            next_round = internal_rounds.pop(0)
            weapon["chambered"]= next_round
            self._play_weapon_action_sound(weapon, "boltforward")
            next_var = next_round.get("variant")or next_round.get("name")if isinstance(next_round, dict)else str(next_round)
            return message +f"Action cycled - chambered {next_var or 'a round'}."

        loaded_mag = weapon.get("loaded")

        if not loaded_mag:
            belt_rounds = weapon.get("rounds", [])
            if belt_rounds and ("belt" in magazine_type or "m249" in (weapon.get("platform", "") or "").lower()):
                self._play_weapon_action_sound(weapon, "boltback", block = True)
                next_round = belt_rounds.pop(0)
                weapon["chambered"]= next_round
                self._play_weapon_action_sound(weapon, "boltforward")
                next_var = next_round.get("variant")or next_round.get("name")if isinstance(next_round, dict)else str(next_round)
                return message +f"Action cycled - chambered {next_var or 'a round'} from belt."

            self._play_weapon_action_sound(weapon, "boltback", block = True)
            self._play_weapon_action_sound(weapon, "boltforward")
            return message +"No magazine loaded - action cycled but no round chambered."

        rounds = loaded_mag.get("rounds", [])
        if not rounds:
            self._play_weapon_action_sound(weapon, "boltback", block = True)
            self._play_weapon_action_sound(weapon, "boltforward")
            return message +"Magazine empty - action cycled but no round chambered."

        self._play_weapon_action_sound(weapon, "boltback", block = True)
        next_round = rounds.pop(0)
        weapon["chambered"]= next_round
        self._play_weapon_action_sound(weapon, "boltforward")
        next_var = next_round.get("variant")or next_round.get("name")if isinstance(next_round, dict)else str(next_round)
        return message +f"Action cycled - chambered {next_var or 'a round'}."

    def _show_magazine_selection_menu(self, weapon, save_data, table_data, current_weapon_state, update_callback):

        magazine_system = weapon.get("magazinesystem")
        platform = str(weapon.get("platform", "")or "").lower()
        mag_type_weapon = str(weapon.get("magazinetype", "")or "").lower()

        is_belt_weapon =("belt"in mag_type_weapon)or("m249"in platform)
        sub_mag_type = str(weapon.get("submagazinetype", "")or "").lower()

        def _norm_token_set(value):
            out = set()
            if isinstance(value, (list, tuple, set)):
                for v in value:
                    sv = str(v or "").strip().lower()
                    if sv:
                        out.add(sv)
            else:
                sv = str(value or "").strip().lower()
                if sv:
                    out.add(sv)
            return out

        weapon_primary_systems = _norm_token_set(magazine_system)
        weapon_sub_systems = _norm_token_set(weapon.get("submagazinesystem"))

        compatible_mags =[]

        def mag_is_compatible(mag):

            if not mag or not isinstance(mag, dict):
                return False

            try:
                if mag.get("firearm")is True:
                    return False
            except Exception:
                logging.exception("Suppressed exception")

            compat = False

            try:
                mag_systems = _norm_token_set(mag.get("magazinesystem"))
                if weapon_primary_systems and mag_systems and weapon_primary_systems.intersection(mag_systems):
                    compat = True
            except Exception:
                logging.exception("Suppressed exception")

            try:
                mag_type = str(mag.get("magazinetype", "")or "").lower()
                if is_belt_weapon and("belt"in mag_type):
                    compat = True
            except Exception:
                logging.exception("Suppressed exception")

            try:
                if sub_mag_type and mag_type ==sub_mag_type:
                    compat = True
            except Exception:
                logging.exception("Suppressed exception")

            try:
                mag_systems = _norm_token_set(mag.get("magazinesystem"))
                if weapon_sub_systems and mag_systems and weapon_sub_systems.intersection(mag_systems):
                    compat = True
            except Exception:
                logging.exception("Suppressed exception")

            try:
                if is_belt_weapon and weapon.get("beltlink")and mag.get("beltlink")and str(mag.get("beltlink")).lower()==str(weapon.get("beltlink")).lower():
                    compat = True
            except Exception:
                logging.exception("Suppressed exception")

            if not compat:
                return False

            try:
                dev_cal_var = None
                if isinstance(current_weapon_state, dict):
                    dev_cal_var = current_weapon_state.get("dev_caliber_var")
                if dev_cal_var and hasattr(dev_cal_var, 'get'):
                    sel_cal = dev_cal_var.get()
                    if sel_cal:
                        def _mag_matches_cal(m, c):
                            try:
                                mcal = m.get("caliber")
                                if isinstance(mcal, (list, tuple)):
                                    for e in mcal:
                                        try:
                                            if str(e)==str(c):
                                                return True
                                        except Exception:
                                            logging.exception("Suppressed exception")
                                elif isinstance(mcal, str):
                                    if str(mcal)==str(c):
                                        return True

                                rds = m.get("rounds")
                                if isinstance(rds, list)and rds:
                                    first = rds[0]
                                    if isinstance(first, dict):
                                        if str(first.get("caliber"))==str(c):
                                            return True
                                    elif isinstance(first, str):
                                        if str(c)in first:
                                            return True
                            except Exception:
                                logging.exception("Suppressed exception")
                            return False

                        if not _mag_matches_cal(mag, sel_cal):
                            return False
            except Exception:
                logging.exception("Suppressed exception")

            return True

        if weapon.get("has_magazine_in_pool")is not False:
            for item in save_data.get("hands", {}).get("items", []):
                if mag_is_compatible(item)and len(item.get("rounds", []))>0:
                    compatible_mags.append(("hands", item))

        for slot_name, item in save_data.get("equipment", {}).items():
                if item:

                    if "items"in item and isinstance(item["items"], list):
                        for mag in item["items"]:
                            if mag_is_compatible(mag)and len(mag.get("rounds", []))>0:
                                compatible_mags.append(("equipment", mag))

                    if item.get("subslots"):
                        for subslot in item["subslots"]:
                            if subslot.get("current"):
                                curr = subslot["current"]
                                if "items"in curr and isinstance(curr["items"], list):
                                    for mag in curr["items"]:
                                        if mag_is_compatible(mag)and len(mag.get("rounds", []))>0:
                                            compatible_mags.append(("equipment", mag))

        if not compatible_mags:
            if is_belt_weapon:

                try:
                    if weapon.get("dualfeed") and (weapon.get("submagazinesystem") or weapon.get("submagazinetype")):
                        self._perform_dualfeed_belt_reload_sequence(weapon)
                    else:
                        self._show_belt_variant_selection(weapon, quick=False)
                    return
                except Exception:
                    try:
                        self._popup_show_info("Magazine", "No belts or compatible magazines in inventory for this weapon!")
                    except Exception:
                        logging.exception("Suppressed exception")
                    return
            else:
                _needed = sorted(weapon_primary_systems) if weapon_primary_systems else []
                _needed_text = ", ".join(_needed) if _needed else str(magazine_system or "this")
                self._popup_show_info("Magazine", f"No compatible magazines in inventory for {_needed_text} system!")
            return

        popup = customtkinter.CTkToplevel(self.root)
        popup.title("Select Magazine")
        popup.transient(self.root)
        self._center_popup_on_window(popup, 500, 450)

        label = customtkinter.CTkLabel(
        popup,
        text = f"Select a magazine for {weapon.get('name')}:",
        font = customtkinter.CTkFont(size = 13),
        wraplength = 450
        )
        label.pack(pady = 10, padx = 20)

        scroll_frame = customtkinter.CTkScrollableFrame(popup, fg_color = "transparent")
        scroll_frame.pack(fill = "both", expand = True, padx = 10, pady = 10)

        selected_mag = customtkinter.StringVar(value = "0")

        for idx, (location, mag_item)in enumerate(compatible_mags):
            mag_name = mag_item.get("name", "Unknown Magazine")
            capacity = mag_item.get("capacity", "?")
            rounds = len(mag_item.get("rounds", []))

            mag_cal_display = None
            try:
                mag_cals =[]
                rds = mag_item.get('rounds')if isinstance(mag_item, dict)else[]
                if isinstance(rds, list)and rds:

                    seen =[]
                    for first in rds:
                        try:
                            if isinstance(first, dict):
                                fc = first.get('caliber')
                                if isinstance(fc, (list, tuple)):
                                    for x in fc:
                                        if x and str(x)not in seen:
                                            seen.append(str(x))
                                elif isinstance(fc, str)and fc and str(fc)not in seen:
                                    seen.append(str(fc))
                            elif isinstance(first, str)and first:
                                calpart = first.split('|', 1)[0].strip()
                                if calpart and calpart not in seen:
                                    seen.append(calpart)
                        except Exception:
                            logging.exception("Suppressed exception")
                            continue
                    if seen:
                        mag_cals = seen

                if mag_cals:
                    mag_cal_display = ", ".join(mag_cals)
            except Exception:
                mag_cal_display = None

            radio_frame = customtkinter.CTkFrame(scroll_frame, fg_color = "transparent")
            radio_frame.pack(fill = "x", pady = 5, padx = 5)

            radio_text = f"{mag_name}({rounds}/{capacity})"
            if mag_cal_display:
                radio_text +=f" - {mag_cal_display}"
            radio_text +=f" - from {location}"
            _mag_rds_list = mag_item.get("rounds", [])
            if _mag_rds_list and isinstance(_mag_rds_list, list)and len(_mag_rds_list)>0:
                _mnr = _mag_rds_list[0]
                if isinstance(_mnr, dict):
                    _mnv = _mnr.get("variant")or _mnr.get("name")
                    if _mnv:
                        radio_text +=f"[next: {_mnv}]"
            radio = customtkinter.CTkRadioButton(
            radio_frame,
            text = radio_text,
            variable = selected_mag,
            value = str(idx),
            font = customtkinter.CTkFont(size = 11)
            )
            radio.pack(anchor = "w")

        def give_magazine():
            if not selected_mag.get():
                self._popup_show_info("Magazine", "Please select a magazine!")
                return

            idx = int(selected_mag.get())
            location, mag_item = compatible_mags[idx]

            try:
                wpn_cal_raw = weapon.get('caliber')or[]
                wpn_calibers = set()
                if isinstance(wpn_cal_raw, (list, tuple)):
                    for c in wpn_cal_raw:
                        if c:
                            wpn_calibers.add(str(c).lower().strip())
                elif isinstance(wpn_cal_raw, str)and wpn_cal_raw:
                    wpn_calibers.add(wpn_cal_raw.lower().strip())

                mag_rounds = mag_item.get('rounds', [])if isinstance(mag_item, dict)else[]
                if wpn_calibers and mag_rounds:
                    for rd in mag_rounds:
                        try:
                            rd_cals = set()
                            if isinstance(rd, dict):
                                rcal = rd.get('caliber')
                                if isinstance(rcal, (list, tuple)):
                                    for rc in rcal:
                                        if rc:
                                            rd_cals.add(str(rc).lower().strip())
                                elif isinstance(rcal, str)and rcal:
                                    rd_cals.add(rcal.lower().strip())
                            elif isinstance(rd, str)and rd:
                                if '|'in rd:
                                    rd_cal_part = rd.split('|', 1)[0].strip()
                                else:
                                    rd_cal_part = rd.strip()
                                if rd_cal_part:
                                    rd_cals.add(rd_cal_part.lower().strip())

                            if rd_cals and not(rd_cals &wpn_calibers):
                                self._popup_show_info("Magazine Incompatible", f"Cannot insert magazine: it contains rounds of an incompatible caliber({next(iter(rd_cals))}).", sound = "error")
                                return
                        except Exception:
                            self._popup_show_info("Magazine Incompatible", "Cannot insert magazine: failed to validate contained rounds.", sound = "error")
                            return
            except Exception:
                logging.exception("Suppressed exception")

            import time

            current_mag = weapon.get("loaded")
            chambered = weapon.get("chambered")
            is_gun_empty = not chambered and(not current_mag or not current_mag.get("rounds", []))

            if current_mag:
                try:
                    self._play_weapon_action_sound(weapon, "magout")
                except Exception:
                    logging.exception("Suppressed exception")

                time.sleep(random.uniform(1.0, 1.5))

                try:
                    self._safe_sound_play("", "sounds/firearms/universal/pouchin.wav")
                except Exception:
                    logging.exception("Suppressed exception")
                time.sleep(random.uniform(1.0, 1.5))

            try:
                self._safe_sound_play("", "sounds/firearms/universal/pouchout.ogg")
            except Exception:
                logging.exception("Suppressed exception")
            time.sleep(random.uniform(1.0, 1.5))

            mag_type = weapon.get("magazinetype", "").lower()
            platform = weapon.get("platform", "").lower()
            if not any(k in mag_type for k in("internal", "tube", "cylinder"))and "revolver"not in platform:
                try:
                    self._play_weapon_action_sound(weapon, "magin")
                except Exception:
                    logging.exception("Suppressed exception")

                time.sleep(random.uniform(0.5, 1.0))

            rt_mag_type = str(weapon.get("magazinetype", "")or "").lower()
            rt_platform_raw = weapon.get("platform", "")or ""
            if isinstance(rt_platform_raw, (list, tuple)):
                rt_platform_raw = rt_platform_raw[0]if rt_platform_raw else ""
            rt_platform = str(rt_platform_raw).lower()
            rt_action_raw = weapon.get("action", "")or ""
            if isinstance(rt_action_raw, (list, tuple)):
                rt_action_raw = rt_action_raw[0]if rt_action_raw else ""
            rt_action = str(rt_action_raw).lower()
            is_pump_reload_local =("pump"in rt_platform or rt_action =="pump"or "pump"in rt_mag_type)

            if is_gun_empty:
                if is_pump_reload_local:
                    try:
                        self._play_weapon_action_sound(weapon, "pumpback", block = True)
                    except Exception:
                        logging.exception("Suppressed exception")
                    try:
                        self._play_weapon_action_sound(weapon, "pumpforward")
                    except Exception:
                        logging.exception("Suppressed exception")
                elif not weapon.get("bolt_catch"):
                    try:
                        self._play_weapon_action_sound(weapon, "boltback", block = True)
                    except Exception:
                        logging.exception("Suppressed exception")
                    try:
                        self._play_weapon_action_sound(weapon, "boltforward")
                    except Exception:
                        logging.exception("Suppressed exception")
                else:

                    try:
                        self._play_weapon_action_sound(weapon, "boltforward")
                    except Exception:
                        logging.exception("Suppressed exception")

            if current_mag and not weapon.get("infinite_ammo"):

                save_data.get("hands", {}).get("items", []).append(current_mag)

            if not weapon.get("infinite_ammo"):
                weapon["loaded"]= mag_item
                weapon["chambered"]= None
                try:
                    _hc_tbl_ms = globals().get('table_data', {})
                    if isinstance(_hc_tbl_ms, dict) and bool((_hc_tbl_ms.get('additional_settings') or {}).get('hardcore_mode')):
                        _sd_ms = mag_item.get("spring_durability")
                        if _sd_ms is not None:
                            try:
                                _sd_ms = float(_sd_ms)
                                _sd_ms = max(0.0, _sd_ms - random.uniform(0.3, 0.8))
                                mag_item["spring_durability"] = round(_sd_ms, 2)
                            except (ValueError, TypeError):
                                logging.exception("Suppressed exception")
                except Exception:
                    logging.exception("Suppressed exception")
            else:
                weapon["chambered"]= None

            if not weapon.get("infinite_ammo")and is_gun_empty and mag_item.get("rounds", [])and not is_pump_reload_local:
                weapon["chambered"]= mag_item["rounds"].pop(0)
            elif weapon.get("infinite_ammo")and is_gun_empty and not is_pump_reload_local:
                caliber_list = weapon.get("caliber", [])or["Unknown"]
                caliber = caliber_list[0]
                weapon["chambered"]= {"name":f"{caliber} | Infinite", "caliber":caliber, "variant":"infinite"}

            if not weapon.get("infinite_ammo"):
                if location =="hands":
                    if mag_item in save_data.get("hands", {}).get("items", []):
                        save_data["hands"]["items"].remove(mag_item)
                elif location =="equipment":

                    for slot_name, item in save_data.get("equipment", {}).items():
                        if item:
                            if "items"in item and isinstance(item["items"], list):
                                if mag_item in item["items"]:
                                    item["items"].remove(mag_item)
                            if item.get("subslots"):
                                for subslot in item["subslots"]:
                                    if subslot.get("current"):
                                        curr = subslot["current"]
                                        if "items"in curr and isinstance(curr["items"], list):
                                            if mag_item in curr["items"]:
                                                curr["items"].remove(mag_item)

            popup.destroy()
            mag_name = mag_item.get("name", "magazine")
            rounds = len(mag_item.get("rounds", []))

            chambered_info = " +1 in chamber"if is_gun_empty and weapon.get("chambered")else ""
            self._popup_show_info("Magazine", f"Loaded {mag_name}({rounds}{chambered_info} rounds)!")
            update_callback()

        button_frame = customtkinter.CTkFrame(popup, fg_color = "transparent")
        button_frame.pack(fill = "x", padx = 10, pady = 10)

        load_btn = customtkinter.CTkButton(
        button_frame,
        text = "Load Magazine",
        command = give_magazine,
        width = 150,
        height = 40
        )
        load_btn.pack(side = "left", padx = 5)

        cancel_btn = customtkinter.CTkButton(
        button_frame,
        text = "Cancel",
        command = popup.destroy,
        width = 150,
        height = 40,
        fg_color = "#444444",
        hover_color = "#555555"
        )
        cancel_btn.pack(side = "left", padx = 5)

        popup.update_idletasks()
        popup_width = popup.winfo_reqwidth()
        popup_height = popup.winfo_reqheight()
        screen_width = popup.winfo_screenwidth()
        screen_height = popup.winfo_screenheight()
        x =(screen_width //2)-(popup_width //2)
        y =(screen_height //2)-(popup_height //2)
        popup.geometry(f"+{x}+{y}")
        popup.deiconify()
        popup.grab_set()
        popup.lift()
        self._safe_focus(popup)

    def _check_for_reloader_item(self, save_data):

        for slot_name, item in save_data.get("equipment", {}).items():

            if isinstance(item, list):
                for sub_item in item:
                    if sub_item and isinstance(sub_item, dict)and sub_item.get("reloader"):
                        return True
                    if sub_item and isinstance(sub_item, dict)and "subslots"in sub_item:
                        for subslot in sub_item.get("subslots", []):
                            if subslot.get("current")and subslot["current"].get("reloader"):
                                return True
                continue

            if item and isinstance(item, dict)and item.get("reloader"):
                return True

            if item and isinstance(item, dict)and "subslots"in item:
                for subslot in item["subslots"]:
                    if subslot.get("current")and subslot["current"].get("reloader"):
                        return True

        for item in save_data.get("hands", {}).get("items", []):
            if item and isinstance(item, dict)and item.get("reloader"):
                return True

        return False

    def _reload_magazine(self, magazine, save_data, max_rounds = None, has_ammo_in_pool = True, on_complete = None, is_loaded_in_weapon = False, weapon = None, variant_filter = None):

        logging.info("_reload_magazine start: capacity=%s, variant_filter=%s", magazine.get("capacity"), variant_filter)

        capacity = magazine.get("capacity", 0)
        current_rounds = magazine.get("rounds", [])
        rounds_to_add = capacity -len(current_rounds)
        if max_rounds is not None:
            try:
                rounds_to_add = min(int(max_rounds), rounds_to_add)
            except Exception:
                logging.exception("Suppressed exception")
        initial_to_add = rounds_to_add

        if rounds_to_add <=0:
            msg = f"Magazine already has {len(current_rounds)} rounds(capacity: {capacity})"
            if on_complete:
                on_complete(msg)
            return msg

        has_reloader = self._check_for_reloader_item(save_data)

        if not has_ammo_in_pool:
            msg = "No loose ammo available in pool to reload this magazine."
            if on_complete:
                on_complete(msg)
            return msg

        is_internal_box = False
        if weapon:
            mag_type = str(weapon.get("magazinetype", "")or "").lower()
            is_internal_box = "internal"in mag_type and "box"in mag_type

        rounds_collected =[]

        def round_matches_filter(r):

            if variant_filter is None:
                return True
            if not isinstance(r, dict):
                return True

            r_variant = r.get("variant")or r.get("name")or "Unknown"
            return str(r_variant).lower()==str(variant_filter).lower()

        try:
            hands_items = save_data.get("hands", {}).get("items", [])
            for hi in range(len(hands_items)-1, -1, -1):
                if rounds_to_add <=0:
                    break
                item = hands_items[hi]
                if not isinstance(item, dict):
                    continue
                if item is magazine:
                    continue

                if item.get('magazinesystem')or item.get('capacity'):
                    continue

                if isinstance(item.get("rounds"), list)and item.get("rounds"):

                    rounds_to_take =[]
                    remaining_rounds =[]
                    for r in item["rounds"]:
                        if round_matches_filter(r)and len(rounds_to_take)<rounds_to_add:
                            rounds_to_take.append(r)
                        else:
                            remaining_rounds.append(r)

                    for r in rounds_to_take:
                        rounds_collected.append(r)
                        rounds_to_add -=1

                    item["rounds"]= remaining_rounds
                    if not item.get("rounds"):
                        try:
                            hands_items.pop(hi)
                        except Exception:
                            logging.exception("Suppressed exception")
                    continue

                if variant_filter is not None:
                    item_variant = item.get("variant")or item.get("name")or "Unknown"
                    if str(item_variant).lower()!=str(variant_filter).lower():
                        continue

                qty = int(item.get("quantity")or 0)if isinstance(item.get("quantity"), (int, float))else 0
                if qty >0 and("caliber"in item or "name"in item):
                    take = min(rounds_to_add, qty)
                    for _ in range(take):
                        r = {k:v for k, v in item.items()if k !="quantity"}
                        rounds_collected.append(r)
                        rounds_to_add -=1
                    item["quantity"]= qty -take
                    if item["quantity"]<=0:
                        try:
                            hands_items.pop(hi)
                        except Exception:
                            logging.exception("Suppressed exception")
                    continue

                if item.get("caliber"):
                    try:
                        hands_items.pop(hi)
                        rounds_collected.append(item)
                        rounds_to_add -=1
                    except Exception:
                        logging.exception("Suppressed exception")
        except Exception:
            logging.exception("Failed to pull rounds from hands during reload")

        loaded_from_hands = len(rounds_collected)

        if loaded_from_hands <=0:
            msg = "No loose rounds available in hands to reload the magazine"
            if on_complete:
                on_complete(msg)
            return msg

        popup = customtkinter.CTkToplevel(self.root)
        popup.title("Reloading Magazine")
        popup.transient(self.root)
        self._center_popup_on_window(popup, 400, 150)
        popup.grab_set()

        status_text = "Using reloader..."if has_reloader else "Loading rounds manually..."
        status_label = customtkinter.CTkLabel(
        popup,
        text = status_text,
        font = customtkinter.CTkFont(size = 14)
        )
        status_label.pack(pady =(20, 10))

        progress_bar = customtkinter.CTkProgressBar(popup, width = 350)
        progress_bar.pack(pady = 10)
        progress_bar.set(0)

        count_label = customtkinter.CTkLabel(
        popup,
        text = f"0 / {loaded_from_hands} rounds",
        font = customtkinter.CTkFont(size = 12)
        )
        count_label.pack(pady = 5)

        reload_state = {
        "index":0,
        "reloader_channel":None,
        "reloader_sound":None
        }

        def play_insert_sound():
            insert_sound = f"bulletinsert{random.randint(0, 1)}"
            try:
                sound_path = os.path.join("sounds", "firearms", "universal", f"{insert_sound}.ogg")
                if os.path.exists(sound_path):
                    sound = pygame.mixer.Sound(sound_path)
                    channel = pygame.mixer.find_channel()
                    if channel:
                        channel.play(sound)
            except Exception as e:
                logging.warning(f"Failed to play {insert_sound}: {e}")

        def start_reloader_sound():
            reloader_sound_path = os.path.join("sounds", "firearms", "universal", "reloaderloop.ogg")
            if os.path.exists(reloader_sound_path):
                channel = pygame.mixer.find_channel()
                if channel:
                    try:
                        sound = pygame.mixer.Sound(reloader_sound_path)
                        channel.play(sound, loops = -1)
                        reload_state["reloader_channel"]= channel
                        reload_state["reloader_sound"]= sound
                    except Exception as e:
                        logging.warning(f"Failed to play reloader sound: {e}")

        def play_reloader_insert_sound():

            try:
                sound_path = os.path.join("sounds", "firearms", "universal", "reloaderroundinsert.ogg")
                if os.path.exists(sound_path):
                    sound = pygame.mixer.Sound(sound_path)
                    channel = pygame.mixer.find_channel()
                    if channel:
                        channel.play(sound)

                        return int(sound.get_length()*1000)
            except Exception as e:
                logging.warning(f"Failed to play reloader insert sound: {e}")
            return 0

        def play_magout_sound():

            if weapon:
                try:
                    self._play_weapon_action_sound(weapon, "magout")

                    return 500
                except Exception as e:
                    logging.warning(f"Failed to play magout sound: {e}")
            return 0

        def play_magin_sound():

            if weapon:
                try:
                    self._play_weapon_action_sound(weapon, "magin")
                except Exception as e:
                    logging.warning(f"Failed to play magin sound: {e}")

        def stop_reloader_sound():
            if reload_state["reloader_channel"]:
                try:
                    reload_state["reloader_channel"].stop()
                except Exception:
                    logging.exception("Suppressed exception")
                reload_state["reloader_channel"]= None

        def reload_step():
            idx = reload_state["index"]

            if idx >=loaded_from_hands:

                stop_reloader_sound()
                magazine["rounds"]= current_rounds

                if has_reloader:
                    message = f"Reloaded {loaded_from_hands} rounds using reloader(total: {len(current_rounds)}/{capacity})"
                else:
                    message = f"Manually reloaded {loaded_from_hands} rounds(total: {len(current_rounds)}/{capacity})"

                logging.info(message)

                if is_loaded_in_weapon:
                    play_magin_sound()

                try:
                    popup.destroy()
                except Exception:
                    logging.exception("Suppressed exception")

                if on_complete:
                    on_complete(message)
                return

            current_rounds.append(rounds_collected[idx])
            reload_state["index"]+=1

            progress = reload_state["index"]/loaded_from_hands
            progress_bar.set(progress)
            count_label.configure(text = f"{reload_state['index']} / {loaded_from_hands} rounds")

            play_insert_sound()

            if has_reloader:
                delay = 100
            else:
                delay = 500

            popup.after(delay, reload_step)

        initial_delay = 100

        is_bolt_action_reload = False
        try:
            if weapon:
                rt_action_raw = weapon.get("action", "")or ""
                if isinstance(rt_action_raw, (list, tuple)):
                    rt_action_raw = rt_action_raw[0]if rt_action_raw else ""
                rt_action = str(rt_action_raw).lower()
                is_bolt_action_reload =(rt_action =="bolt"or "bolt"in rt_action)
        except Exception:
            is_bolt_action_reload = False

        if is_loaded_in_weapon:
            magout_duration = play_magout_sound()
            initial_delay +=magout_duration

        if weapon and is_bolt_action_reload and not is_internal_box:
            try:
                self._play_weapon_action_sound(weapon, "boltback", block = True)
                time.sleep(0.12)
            except Exception:
                logging.exception("Suppressed exception")

        def play_boltback_for_internal(callback):

            if is_internal_box and weapon:
                try:

                    platform = weapon.get("platform", "").lower()
                    wf = os.path.join("sounds", "firearms", "weaponsounds", platform)if platform else None
                    sound_file = None
                    duration_ms = 800

                    if wf:
                        candidates = glob.glob(os.path.join(wf, "boltback*.ogg"))+glob.glob(os.path.join(wf, "boltback*.wav"))
                        if candidates:
                            sound_file = random.choice(candidates)

                    if sound_file and os.path.exists(sound_file):
                        try:
                            sound = pygame.mixer.Sound(sound_file)
                            duration_ms = int(sound.get_length()*1000)+100
                            channel = pygame.mixer.find_channel()
                            if channel:
                                channel.play(sound)
                        except Exception:
                            logging.exception("Suppressed exception")
                    else:

                        self._play_weapon_action_sound(weapon, "boltback", block = False)

                    popup.after(duration_ms, callback)
                    return
                except Exception:
                    logging.exception("Suppressed exception")

            callback()

        if has_reloader:

            insert_duration = play_reloader_insert_sound()

            def start_reloader_after_insert():
                start_reloader_sound()
                popup.after(100, reload_step)

            popup.after(initial_delay +insert_duration, start_reloader_after_insert)
        else:

            def start_reload_after_delay():
                play_boltback_for_internal(reload_step)

            popup.after(initial_delay, start_reload_after_delay)

        return "Reloading..."

    def _unload_magazine_rounds(self, magazine, save_data, max_rounds = None, on_complete = None, is_loaded_in_weapon = False, weapon = None, variant_filter = None):

        logging.info("_unload_magazine_rounds start: rounds=%s, variant_filter=%s", len(magazine.get("rounds", [])), variant_filter)

        current_rounds = magazine.get("rounds", [])
        if not isinstance(current_rounds, list):
            current_rounds =[]
            magazine["rounds"]= current_rounds

        if variant_filter:
            matching_count = sum(1 for r in current_rounds if isinstance(r, dict)and str(r.get('variant', 'Unknown')).lower()==str(variant_filter).lower())
            rounds_to_remove = matching_count
        else:
            rounds_to_remove = len(current_rounds)

        if max_rounds is not None:
            try:
                rounds_to_remove = min(int(max_rounds), rounds_to_remove)
            except Exception:
                logging.exception("Suppressed exception")

        if rounds_to_remove <=0:
            msg = "Magazine is already empty"
            if on_complete:
                on_complete(msg)
            return msg

        has_reloader = self._check_for_reloader_item(save_data)

        popup = customtkinter.CTkToplevel(self.root)
        popup.title("Unloading Magazine")
        popup.transient(self.root)
        self._center_popup_on_window(popup, 400, 150)
        popup.grab_set()

        status_text = "Using reloader..."if has_reloader else "Unloading rounds manually..."
        status_label = customtkinter.CTkLabel(
        popup,
        text = status_text,
        font = customtkinter.CTkFont(size = 14)
        )
        status_label.pack(pady =(20, 10))

        progress_bar = customtkinter.CTkProgressBar(popup, width = 350)
        progress_bar.pack(pady = 10)
        progress_bar.set(0)

        count_label = customtkinter.CTkLabel(
        popup,
        text = f"0 / {rounds_to_remove} rounds",
        font = customtkinter.CTkFont(size = 12)
        )
        count_label.pack(pady = 5)

        unload_state = {
        "index":0,
        "reloader_channel":None,
        "reloader_sound":None,
        "rounds_removed":[]
        }

        def play_insert_sound():
            insert_sound = f"bulletinsert{random.randint(0, 1)}"
            try:
                sound_path = os.path.join("sounds", "firearms", "universal", f"{insert_sound}.ogg")
                if os.path.exists(sound_path):
                    sound = pygame.mixer.Sound(sound_path)
                    channel = pygame.mixer.find_channel()
                    if channel:
                        channel.play(sound)
            except Exception as e:
                logging.warning(f"Failed to play {insert_sound}: {e}")

        def start_reloader_sound():
            reloader_sound_path = os.path.join("sounds", "firearms", "universal", "reloaderloop.ogg")
            if os.path.exists(reloader_sound_path):
                channel = pygame.mixer.find_channel()
                if channel:
                    try:
                        sound = pygame.mixer.Sound(reloader_sound_path)
                        channel.play(sound, loops = -1)
                        unload_state["reloader_channel"]= channel
                        unload_state["reloader_sound"]= sound
                    except Exception as e:
                        logging.warning(f"Failed to play reloader sound: {e}")

        def play_reloader_insert_sound():

            try:
                sound_path = os.path.join("sounds", "firearms", "universal", "reloaderroundinsert.ogg")
                if os.path.exists(sound_path):
                    sound = pygame.mixer.Sound(sound_path)
                    channel = pygame.mixer.find_channel()
                    if channel:
                        channel.play(sound)
                        return int(sound.get_length()*1000)
            except Exception as e:
                logging.warning(f"Failed to play reloader insert sound: {e}")
            return 0

        def play_magout_sound():

            if weapon:
                try:
                    self._play_weapon_action_sound(weapon, "magout")
                    return 500
                except Exception as e:
                    logging.warning(f"Failed to play magout sound: {e}")
            return 0

        def play_magin_sound():

            if weapon:
                try:
                    self._play_weapon_action_sound(weapon, "magin")
                except Exception as e:
                    logging.warning(f"Failed to play magin sound: {e}")

        def stop_reloader_sound():
            if unload_state["reloader_channel"]:
                try:
                    unload_state["reloader_channel"].stop()
                except Exception:
                    logging.exception("Suppressed exception")
                unload_state["reloader_channel"]= None

        def unload_step():
            idx = unload_state["index"]

            if idx >=rounds_to_remove:

                stop_reloader_sound()

                hands_items = save_data.get("hands", {}).get("items", [])
                self._add_rounds_to_container(hands_items, unload_state["rounds_removed"])

                if has_reloader:
                    message = f"Unloaded {len(unload_state['rounds_removed'])} rounds using reloader(remaining: {len(current_rounds)})"
                else:
                    message = f"Manually unloaded {len(unload_state['rounds_removed'])} rounds(remaining: {len(current_rounds)})"

                logging.info(message)

                if is_loaded_in_weapon:
                    play_magin_sound()

                    try:
                        if weapon and is_bolt_action_reload:
                            try:
                                self._play_weapon_action_sound(weapon, "boltforward")
                            except Exception:
                                logging.exception("Suppressed exception")
                    except Exception:
                        logging.exception("Suppressed exception")

                try:
                    popup.destroy()
                except Exception:
                    logging.exception("Suppressed exception")

                if on_complete:
                    on_complete(message)
                return

            if current_rounds:
                try:
                    removed = None
                    if variant_filter:

                        for i in range(len(current_rounds)-1, -1, -1):
                            r = current_rounds[i]
                            if isinstance(r, dict)and str(r.get('variant', 'Unknown')).lower()==str(variant_filter).lower():
                                removed = current_rounds.pop(i)
                                break
                    else:
                        removed = current_rounds.pop()

                    if removed is not None:
                        unload_state["rounds_removed"].append(removed)
                except Exception:
                    logging.exception("Suppressed exception")

            unload_state["index"]+=1

            progress = unload_state["index"]/rounds_to_remove
            progress_bar.set(progress)
            count_label.configure(text = f"{unload_state['index']} / {rounds_to_remove} rounds")

            play_insert_sound()

            if has_reloader:
                delay = 100
            else:
                delay = 500

            popup.after(delay, unload_step)

        initial_delay = 100

        if is_loaded_in_weapon:
            magout_duration = play_magout_sound()
            initial_delay +=magout_duration

        if has_reloader:

            insert_duration = play_reloader_insert_sound()

            def start_reloader_after_insert():
                start_reloader_sound()
                popup.after(100, unload_step)

            popup.after(initial_delay +insert_duration, start_reloader_after_insert)
        else:

            popup.after(initial_delay, unload_step)

        return "Unloading..."
