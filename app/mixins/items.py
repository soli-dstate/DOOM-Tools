"""ItemsMixin — App methods for the "items" feature area."""
from app.foundation import *


class ItemsMixin:

    def _add_item_to_container(self, container_items, item_to_add, force_no_stack = False):

        if not isinstance(container_items, list):
            return False
        if not isinstance(item_to_add, dict):
            container_items.append(item_to_add)
            return False

        if force_no_stack or item_to_add.get("can_stack")==False:
            container_items.append(item_to_add)
            return False

        non_stackable_keys =["magazinesystem", "capacity", "firearm", "attachment", "subslots", "loaded", "chambered"]
        if any(k in item_to_add for k in non_stackable_keys):
            container_items.append(item_to_add)
            return False

        def items_match_for_stacking(existing, new_item):

            if existing.get("name")!=new_item.get("name"):
                return False
            if existing.get("id")!=new_item.get("id"):
                return False

            if existing.get("caliber")!=new_item.get("caliber"):
                return False

            if existing.get("variant")!=new_item.get("variant"):
                return False

            if existing.get("can_stack")==False:
                return False

            if any(k in existing for k in non_stackable_keys):
                return False
            return True

        for existing_item in container_items:
            if not isinstance(existing_item, dict):
                continue
            if items_match_for_stacking(existing_item, item_to_add):

                existing_qty = existing_item.get("quantity", 1)
                new_qty = item_to_add.get("quantity", 1)
                try:
                    existing_qty = int(existing_qty)if existing_qty else 1
                    new_qty = int(new_qty)if new_qty else 1
                except(ValueError, TypeError):
                    existing_qty = 1
                    new_qty = 1
                existing_item["quantity"]= existing_qty +new_qty
                return True

        container_items.append(item_to_add)
        return False

    def _add_rounds_to_container(self, container_items, rounds_list):

        if not isinstance(container_items, list)or not isinstance(rounds_list, list):
            return

        round_groups = {}
        for r in rounds_list:
            if not isinstance(r, dict):
                continue
            caliber = r.get("caliber", "Unknown")
            variant = r.get("variant", "Unknown")
            key =(str(caliber), str(variant))
            if key not in round_groups:
                round_groups[key]=[]
            round_groups[key].append(r)

        for(caliber, variant), group_rounds in round_groups.items():

            sample = group_rounds[0]if group_rounds else {}
            stack_item = {
            "name":sample.get("name", f"{caliber} | {variant}"),
            "caliber":caliber,
            "variant":variant,
            "quantity":len(group_rounds)
            }

            for k in["type", "pen", "modifiers", "tip", "rarity"]:
                if k in sample:
                    stack_item[k]= sample[k]

            self._add_item_to_container(container_items, stack_item)

    def _find_item_container(self, save_data, target, include_storage = True):
        """Find the live container holding `target` (by identity).

        Returns (parent, key): parent is a list (integer index key) or a subslot/
        accessory dict (key 'current'). Returns (None, None) if not found.
        """
        found = [None, None]
        seen = set()

        def _walk(node):
            if found[0] is not None or not isinstance(node, dict):
                return
            nid = id(node)
            if nid in seen:
                return
            seen.add(nid)
            lst = node.get("items")
            if isinstance(lst, list):
                for i, it in enumerate(lst):
                    if it is target:
                        found[0], found[1] = lst, i
                        return
                for it in lst:
                    _walk(it)
                    if found[0] is not None:
                        return
            for field in ("subslots", "accessories"):
                for entry in node.get(field, []) or []:
                    if isinstance(entry, dict):
                        if entry.get("current") is target:
                            found[0], found[1] = entry, "current"
                            return
                        _walk(entry.get("current"))
                        if found[0] is not None:
                            return

        hands = save_data.get("hands", {})
        if isinstance(hands, dict):
            _walk(hands)
        if found[0] is None:
            for _slot, eq_item in (save_data.get("equipment", {}) or {}).items():
                _walk(eq_item)
                if found[0] is not None:
                    break
        if found[0] is None and include_storage:
            storage = save_data.get("storage", [])
            if isinstance(storage, list):
                for i, it in enumerate(storage):
                    if it is target:
                        found[0], found[1] = storage, i
                        break
                    _walk(it)
                    if found[0] is not None:
                        break
        return found[0], found[1]

    def _manage_containers(self):
        logging.info("Container Management definition called")

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

        self.root.grid_rowconfigure(0, weight = 1)
        self.root.grid_columnconfigure(0, weight = 1)

        main_frame = customtkinter.CTkFrame(self.root)
        main_frame.grid(row = 0, column = 0, sticky = "nsew", padx = 20, pady = 20)
        main_frame.grid_rowconfigure(1, weight = 1)
        main_frame.grid_columnconfigure(0, weight = 1)

        title = customtkinter.CTkLabel(main_frame, text = "Manage Containers & Transfer Items", font = customtkinter.CTkFont(size = 20, weight = "bold"))
        title.grid(row = 0, column = 0, pady =(0, 10))

        tabview = customtkinter.CTkTabview(main_frame, width = 1000, height = 600)
        tabview.grid(row = 1, column = 0, sticky = "nsew", pady = 10)

        tabview.add("View Inventory")
        tabview.add("Transfer Items")

        view_tab = tabview.tab("View Inventory")
        view_tab.grid_rowconfigure(1, weight = 1)
        view_tab.grid_columnconfigure(0, weight = 1)

        enc_info_frame = customtkinter.CTkFrame(view_tab, fg_color =("gray90", "gray20"))
        enc_info_frame.grid(row = 0, column = 0, sticky = "ew", padx = 10, pady = 10)
        enc_info_frame.grid_columnconfigure(0, weight = 1)

        enc_info_label = customtkinter.CTkLabel(enc_info_frame, font = customtkinter.CTkFont(size = 12), anchor = "w")
        enc_info_label.grid(row = 0, column = 0, sticky = "ew", padx = 15, pady = 10)

        def refresh_enc_info():
            encumbrance_info = self._calculate_encumbrance_status(save_data)
            enc_info_label.configure(
            text =(
            f"Total Weight: {self._format_weight(encumbrance_info['total_weight'])} | "
            f"Encumbrance: {self._format_weight(encumbrance_info['encumbrance'])} / {self._format_weight(encumbrance_info['threshold'])} | "
            f"Encumbrance level: {encumbrance_info['encumbrance_level']} | "
            f"Status: {'ENCUMBERED'if encumbrance_info['is_encumbered']else 'OK'}"
            )
            )

        tabview.configure(command = lambda value = None:refresh_enc_info())

        def get_containers():
            containers = []
            equipment = save_data.get("equipment", {})

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

            def _slot_blocked_by_subslots(slot_name):
                try:
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
                                    targets_l = _resolve_conflicts(conflicts)
                                    if slot_name_l in targets_l:
                                        return True
                                except Exception:
                                    pass

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
                                            pass
                                except Exception:
                                    pass

                            try:
                                item_conflicts = oi.get('conflicts_with')
                                if item_conflicts:
                                    targets_l = _resolve_conflicts(item_conflicts)
                                    if slot_name_l in targets_l:
                                        return True
                            except Exception:
                                pass
                    return False
                except Exception:
                    return False

            def _get_conflict_sources(slot_name):
                sources = []
                try:
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
                                        subname = subslot_data.get('name') or subslot_data.get('slot') or 'subslot'
                                        sources.append(f"{other_slot}.{subname}")
                                except Exception:
                                    pass

                            for acc in oi.get('accessories', []) or []:
                                try:
                                    curacc = acc.get('current')
                                    if not isinstance(curacc, dict):
                                        continue
                                    for subslot_data in curacc.get('subslots', []) or []:
                                        try:
                                            conflicts = subslot_data.get('conflicts_with')

                                            targets_l = _resolve_conflicts(conflicts)
                                            if slot_name_l in targets_l:
                                                subname = subslot_data.get('name') or subslot_data.get('slot') or 'subslot'
                                                sources.append(f"{other_slot}.{subname}")
                                        except Exception:
                                            pass
                                except Exception:
                                    pass

                            try:
                                item_conflicts = oi.get('conflicts_with')
                                if item_conflicts:
                                    targets_l = _resolve_conflicts(item_conflicts)
                                    if slot_name_l in targets_l:
                                        sources.append(f"{other_slot}")
                            except Exception:
                                pass
                except Exception:
                    pass

                seen = set()
                out = []
                for s in sources:
                    if s not in seen:
                        seen.add(s)
                        out.append(s)
                return out

            def _get_conflicting_item_names(slot_name):
                names = []
                try:
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

                                    targets_l = _resolve_conflicts(conflicts)
                                    if slot_name_l in targets_l:

                                        nm = None
                                        try:
                                            if isinstance(oi, dict):
                                                nm = oi.get('name') or oi.get('id')
                                        except Exception:
                                            nm = None
                                        if not nm:
                                            cur = subslot_data.get('current')
                                            if isinstance(cur, dict):
                                                nm = cur.get('name') or cur.get('id')
                                        if not nm:
                                            nm = other_slot
                                        if nm:
                                            names.append(str(nm))
                                except Exception:
                                    pass

                            for acc in oi.get('accessories', []) or []:
                                try:

                                    curacc = acc.get('current') if isinstance(acc, dict) else None
                                    acc_subslots = []
                                    if isinstance(curacc, dict):
                                        acc_subslots.extend(curacc.get('subslots', []) or [])
                                    if isinstance(acc, dict):
                                        acc_subslots.extend(acc.get('subslots', []) or [])

                                    for subslot_data in acc_subslots:
                                        try:
                                            conflicts = subslot_data.get('conflicts_with')
                                            targets_l = _resolve_conflicts(conflicts)
                                            if slot_name_l in targets_l:

                                                nm = None
                                                try:
                                                    if isinstance(curacc, dict):
                                                        nm = curacc.get('name') or curacc.get('id')
                                                except Exception:
                                                    nm = None
                                                if not nm:
                                                    try:
                                                        if isinstance(acc, dict):
                                                            nm = acc.get('name') or acc.get('id')
                                                    except Exception:
                                                        nm = None
                                                if not nm:
                                                    try:
                                                        if isinstance(oi, dict):
                                                            nm = oi.get('name') or oi.get('id')
                                                    except Exception:
                                                        nm = None
                                                if not nm:
                                                    nm = other_slot
                                                if nm:
                                                    names.append(str(nm))
                                        except Exception:
                                            pass
                                except Exception:
                                    pass

                            try:
                                item_conflicts = oi.get('conflicts_with')
                                if item_conflicts:
                                    targets_l = _resolve_conflicts(item_conflicts)
                                    if slot_name_l in targets_l:
                                        nm = oi.get('name') or oi.get('id') or other_slot
                                        if nm:
                                            names.append(str(nm))
                            except Exception:
                                pass
                except Exception:
                    pass

                seen = set(); out = []
                for n in names:
                    if n not in seen:
                        seen.add(n); out.append(n)
                return out

            def _find_any_item_with_conflict(slot_name):

                try:
                    slot_name_l = str(slot_name).lower() if slot_name is not None else ''
                    def check_item(it):
                        if not isinstance(it, dict):
                            return None

                        for ss in it.get('subslots', []) or []:
                            try:
                                conflicts = ss.get('conflicts_with')
                                targets_l = _resolve_conflicts(conflicts)
                                if any(slot_name_l == t for t in targets_l):
                                    return it.get('name') or it.get('id')
                            except Exception:
                                pass

                        for acc in it.get('accessories', []) or []:
                            try:

                                for src in (acc, acc.get('current')):
                                    if not isinstance(src, dict):
                                        continue
                                    for ss in src.get('subslots', []) or []:
                                        try:
                                            conflicts = ss.get('conflicts_with')
                                            targets_l = _resolve_conflicts(conflicts)
                                            if any(slot_name_l == t for t in targets_l):

                                                return(src.get('name') or src.get('id') or it.get('name') or it.get('id'))
                                        except Exception:
                                            pass
                            except Exception:
                                pass
                        try:
                            item_conflicts = it.get('conflicts_with')
                            if item_conflicts:
                                targets_l = _resolve_conflicts(item_conflicts)
                                if any(slot_name_l == t for t in targets_l):
                                    return it.get('name') or it.get('id')
                        except Exception:
                            pass
                        return None

                    for s, it in equipment.items():
                        if isinstance(it, dict):
                            nm = check_item(it)
                            if nm:
                                return str(nm)
                        elif isinstance(it, list):
                            for sub in it:
                                nm = check_item(sub)
                                if nm:
                                    return str(nm)

                    for it in save_data.get('storage', []) or []:
                        nm = check_item(it)
                        if nm:
                            return str(nm)

                    for it in (save_data.get('hands') or {}).get('items', []) or []:
                        nm = check_item(it)
                        if nm:
                            return str(nm)

                except Exception:
                    pass
                return None

            containers.append({"name":"Hands", "location":"hands"})
            containers.append({"name":"Storage", "location":"storage"})

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
                            pass

            return containers

        containers = get_containers()

        def get_container_items(location):

            if location =="storage":
                return save_data.get("storage", [])
            elif location =="hands":
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

        def set_container_items(location, items):

            if location =="storage":
                save_data["storage"]= items
            elif location =="hands":
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

        def get_container_weight(location):

            items = get_container_items(location)
            return sum(i.get("weight", 0)*i.get("quantity", 1)for i in items if isinstance(i, dict))

        def get_container_capacity(location):

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

        def rebuild_container_labels():

            labels =[]
            for c in containers:

                total_weight = get_container_weight(c["location"])

                try:
                    capacity = get_container_capacity(c.get("location"))
                except Exception:
                    capacity = None
                capacity_text = self._format_weight(capacity)if capacity is not None else "∞"
                c["label"]= f"{c['name']}({self._format_weight(total_weight)}/{capacity_text})"
                labels.append(c["label"])
            return labels

        labels = rebuild_container_labels()

        refresh_enc_info()

        view_tab = tabview.tab("View Inventory")
        view_tab.grid_rowconfigure(2, weight = 1)
        view_tab.grid_columnconfigure(0, weight = 1)

        view_frame = customtkinter.CTkFrame(view_tab)
        view_frame.grid(row = 0, column = 0, rowspan = 3, sticky = "nsew", padx = 10, pady = 10)
        view_frame.grid_rowconfigure(2, weight = 1)
        view_frame.grid_columnconfigure(0, weight = 1)

        top_view_frame = customtkinter.CTkFrame(view_frame, fg_color = "transparent")
        top_view_frame.grid(row = 0, column = 0, sticky = "ew", pady =(0, 10))
        top_view_frame.grid_columnconfigure(2, weight = 1)

        container_selector = customtkinter.CTkOptionMenu(
        top_view_frame,
        values = labels,
        width = 300,
        font = customtkinter.CTkFont(size = 14)
        )
        container_selector.grid(row = 0, column = 0, padx =(0, 20))
        container_selector.set(labels[0]if labels else "")

        view_search_label = customtkinter.CTkLabel(top_view_frame, text = "Search:", font = customtkinter.CTkFont(size = 12))
        view_search_label.grid(row = 0, column = 1, padx =(0, 5))

        view_search_entry = customtkinter.CTkEntry(top_view_frame, placeholder_text = "Filter items...", width = 200)
        view_search_entry.grid(row = 0, column = 2, sticky = "w")

        view_info_label = customtkinter.CTkLabel(top_view_frame, text = "", font = customtkinter.CTkFont(size = 11), text_color = "gray")
        view_info_label.grid(row = 0, column = 3, padx = 10)

        view_scroll = customtkinter.CTkScrollableFrame(view_frame, width = 900, height = 380)
        view_scroll.grid(row = 2, column = 0, sticky = "nsew", padx = 10, pady = 10)

        view_pagination_frame = customtkinter.CTkFrame(view_frame, fg_color = "transparent")
        view_pagination_frame.grid(row = 3, column = 0, pady = 5)

        ITEMS_PER_PAGE_VIEW = 20
        view_current_page =[0]
        view_current_filtered =[[]]
        view_search_timer =[None]
        view_all_items =[[]]

        def refresh_view():
            current_label = container_selector.get()
            new_labels = rebuild_container_labels()
            container_selector.configure(values = new_labels)
            if current_label in new_labels:
                container_selector.set(current_label)
            elif new_labels:
                container_selector.set(new_labels[0])
            refresh_enc_info()

            selected_label = container_selector.get()
            selected_container = next((c for c in containers if c.get("label")==selected_label), None)

            if not selected_container:
                view_all_items[0]=[]
                view_current_filtered[0]=[]
                view_current_page[0]= 0
                display_view_page(0)
                return

            location = selected_container["location"]
            items = get_container_items(location)
            view_all_items[0]= items if items else[]
            view_search_entry.delete(0, "end")
            view_current_filtered[0]= view_all_items[0]
            view_current_page[0]= 0
            display_view_page(0)

        def show_item_details(item_data):
            detail_window = customtkinter.CTkToplevel(self.root)
            detail_window.title("Item Details")
            detail_window.transient(self.root)
            self._center_popup_on_window(detail_window, 500, 600)

            scroll = customtkinter.CTkScrollableFrame(detail_window, width = 450, height = 550)
            scroll.pack(pady = 10, padx = 10, fill = "both", expand = True)

            title = customtkinter.CTkLabel(scroll, text = item_data.get("name", "Unknown"), font = customtkinter.CTkFont(size = 18, weight = "bold"))
            title.pack(pady =(10, 20))

            def _summarize_value(key, value):
                key_l = str(key).lower()

                if value is None:
                    return "None"

                if isinstance(value, bool):
                    return "Yes" if value else "No"

                if isinstance(value, (int, float, str)):
                    return str(value)

                if isinstance(value, list):
                    if not value:
                        return "None"

                    if key_l == "rounds":
                        variants = []
                        for rd in value:
                            if isinstance(rd, dict):
                                rv = rd.get("variant") or rd.get("name")
                                if rv and rv not in variants:
                                    variants.append(str(rv))
                        if variants:
                            variant_text = ", ".join(variants[:3])
                            if len(variants) > 3:
                                variant_text += ", ..."
                            return f"{len(value)} rounds ({variant_text})"
                        return f"{len(value)} rounds"

                    if key_l == "parts":
                        part_lines = []
                        for p in value:
                            if not isinstance(p, dict):
                                continue
                            p_name = p.get("name") or p.get("type") or "Unknown Part"
                            p_dur = p.get("current_durability")
                            if p_dur is None and isinstance(p.get("current"), dict):
                                p_dur = p["current"].get("current_durability")
                            if isinstance(p_dur, (int, float)):
                                pct = max(0.0, min(100.0, (float(p_dur) / PART_DURABILITY_MAX) * 100.0))
                                part_lines.append(f"- {p_name}: {pct:.1f}%")
                            else:
                                part_lines.append(f"- {p_name}")
                        return "\n".join(part_lines) if part_lines else f"{len(value)} entries"

                    if all(isinstance(v, dict) for v in value):
                        names = []
                        for v in value:
                            nm = v.get("name") if isinstance(v, dict) else None
                            if nm:
                                names.append(str(nm))
                        if names:
                            text = ", ".join(names[:4])
                            if len(names) > 4:
                                text += ", ..."
                            return f"{len(value)} items: {text}"

                    return ", ".join(str(v) for v in value[:6]) + (", ..." if len(value) > 6 else "")

                if isinstance(value, dict):
                    if key_l in ("loaded", "chambered", "current"):
                        nm = value.get("name") or value.get("id") or "Unknown"
                        cap = value.get("capacity")
                        rds = value.get("rounds")
                        if isinstance(rds, list):
                            if isinstance(cap, (int, float)):
                                return f"{nm} ({len(rds)}/{int(cap)} rounds)"
                            return f"{nm} ({len(rds)} rounds)"
                        return str(nm)

                    preferred = ["name", "type", "slot", "id", "value", "weight"]
                    chunks = []
                    for pkey in preferred:
                        if pkey in value:
                            chunks.append(f"{pkey}: {value.get(pkey)}")
                    if chunks:
                        return "; ".join(chunks)
                    return f"{len(value)} fields"

                return str(value)

            for key, value in item_data.items():
                if key =="name":
                    continue
                if isinstance(key, str) and key.startswith("_"):
                    continue

                prop_frame = customtkinter.CTkFrame(scroll, fg_color = "transparent")
                prop_frame.pack(fill = "x", pady = 2, padx = 10)

                key_label = customtkinter.CTkLabel(
                prop_frame,
                text = f"{key.replace('_', ' ').title()}:",
                font = customtkinter.CTkFont(size = 12, weight = "bold"),
                anchor = "w",
                width = 150
                )
                key_label.pack(side = "left", padx = 5)

                value_text = _summarize_value(key, value)

                value_label = customtkinter.CTkLabel(
                prop_frame,
                text = value_text,
                font = customtkinter.CTkFont(size = 11),
                anchor = "w",
                wraplength = 250
                )
                value_label.pack(side = "left", padx = 5, fill = "x", expand = True)

            close_button = self._create_sound_button(scroll, "Close", detail_window.destroy, width = 120, height = 35)
            close_button.pack(pady = 20)

            detail_window.update_idletasks()
            detail_window.deiconify()
            detail_window.grab_set()

        def create_item_view_widget(item):
            selected_label = container_selector.get()
            selected_container = next((c for c in containers if c.get("label")==selected_label), None)
            location = selected_container["location"]if selected_container else ""

            item_frame = customtkinter.CTkFrame(view_scroll)
            item_frame.pack(fill = "x", pady = 5, padx = 10)
            item_frame.grid_columnconfigure(0, weight = 1)

            item_name = self._format_item_name(item)
            item_qty = item.get("quantity", 1)
            item_weight = item.get("weight", 0)*item_qty
            item_value = item.get("value", 0)
            item_purchase_price = item.get("_purchase_price")

            display_text = f"{item_name} x{item_qty}"
            if item.get("consumable"):
                if item.get("uses_left"):
                    display_text +=f"({item.get('uses_left')} uses left)"
                elif item.get("used_up"):
                    display_text +="(1 use left)"
                else:
                    display_text +="(∞ uses)"

            name_label = customtkinter.CTkLabel(
            item_frame,
            text = display_text,
            font = customtkinter.CTkFont(size = 14, weight = "bold"),
            anchor = "w"
            )
            name_label.grid(row = 0, column = 0, sticky = "w", padx = 15, pady =(10, 2))

            item_info_parts = [f"Weight: {self._format_weight(item_weight)}", f"Value: {format_price(item_value)}"]
            if item_purchase_price is not None:
                item_info_parts.append(f"Paid: {format_price(item_purchase_price)}")

            item_info_label = customtkinter.CTkLabel(
            item_frame,
            text = " | ".join(item_info_parts),
            font = customtkinter.CTkFont(size = 11),
            text_color = "gray",
            anchor = "w"
            )
            item_info_label.grid(row = 1, column = 0, sticky = "w", padx = 15, pady =(0, 10))

            button_col = 1
            details_button = self._create_sound_button(
            item_frame,
            "View Details",
            lambda it = item:show_item_details(it),
            width = 120,
            height = 35,
            font = customtkinter.CTkFont(size = 12)
            )
            details_button.grid(row = 0, column = button_col, rowspan = 2, padx = 15, pady = 10)

            if item.get("consumable"):
                button_col +=1
                consume_button = self._create_sound_button(
                item_frame,
                "Consume",
                lambda it = item, loc = location:self._consume_item(it, loc, save_data, on_complete = refresh_view),
                width = 100,
                height = 35,
                font = customtkinter.CTkFont(size = 12)
                )
                consume_button.grid(row = 0, column = button_col, rowspan = 2, padx =(0, 15), pady = 10)

            if item.get("stratagem"):
                button_col +=1
                stratagem_button = self._create_sound_button(
                item_frame,
                "Use Stratagem",
                lambda it = item, loc = location:self._use_stratagem(it, loc, save_data, on_complete = refresh_view),
                width = 120,
                height = 35,
                font = customtkinter.CTkFont(size = 12)
                )
                stratagem_button.grid(row = 0, column = button_col, rowspan = 2, padx =(0, 15), pady = 10)

            if item.get("inspectable"):
                button_col +=1
                inspect_button = self._create_sound_button(
                item_frame,
                "Inspect",
                lambda it = item, loc = location:self._inspect_item(it, loc, save_data),
                width = 100,
                height = 35,
                font = customtkinter.CTkFont(size = 12)
                )
                inspect_button.grid(row = 0, column = button_col, rowspan = 2, padx =(0, 15), pady = 10)

        def display_view_page(page_num):
            items = view_current_filtered[0]
            total_pages = max(1, (len(items)+ITEMS_PER_PAGE_VIEW -1)//ITEMS_PER_PAGE_VIEW)
            page_num = max(0, min(page_num, total_pages -1))
            view_current_page[0]= page_num

            for widget in view_scroll.winfo_children():
                widget.destroy()

            if not items:
                empty_label = customtkinter.CTkLabel(view_scroll, text = "Container is empty", font = customtkinter.CTkFont(size = 14), text_color = "gray")
                empty_label.pack(pady = 30)
                view_info_label.configure(text = "No items")
                update_view_pagination(0, 0)
                return

            start_idx = page_num *ITEMS_PER_PAGE_VIEW
            end_idx = min(start_idx +ITEMS_PER_PAGE_VIEW, len(items))

            for i in range(start_idx, end_idx):
                create_item_view_widget(items[i])

            view_info_label.configure(text = f"Page {page_num +1}/{total_pages} | {len(items)} items")
            update_view_pagination(page_num, total_pages)

            try:
                view_scroll._parent_canvas.yview_moveto(0)
            except Exception:
                pass

        def update_view_pagination(current, total):
            for widget in view_pagination_frame.winfo_children():
                widget.destroy()

            if total <=1:
                return

            first_btn = customtkinter.CTkButton(view_pagination_frame, text = "<<", width = 40, height = 30, command = lambda:display_view_page(0), state = "normal"if current >0 else "disabled")
            first_btn.pack(side = "left", padx = 2)

            prev_btn = customtkinter.CTkButton(view_pagination_frame, text = "<", width = 40, height = 30, command = lambda:display_view_page(current -1), state = "normal"if current >0 else "disabled")
            prev_btn.pack(side = "left", padx = 2)

            start_page = max(0, current -3)
            end_page = min(total, start_page +7)
            if end_page -start_page <7:
                start_page = max(0, end_page -7)

            for p in range(start_page, end_page):
                btn = customtkinter.CTkButton(view_pagination_frame, text = str(p +1), width = 35, height = 30, fg_color =("gray75", "gray25")if p ==current else None, command = lambda page = p:display_view_page(page))
                btn.pack(side = "left", padx = 1)

            next_btn = customtkinter.CTkButton(view_pagination_frame, text = ">", width = 40, height = 30, command = lambda:display_view_page(current +1), state = "normal"if current <total -1 else "disabled")
            next_btn.pack(side = "left", padx = 2)

            last_btn = customtkinter.CTkButton(view_pagination_frame, text = ">>", width = 40, height = 30, command = lambda:display_view_page(total -1), state = "normal"if current <total -1 else "disabled")
            last_btn.pack(side = "left", padx = 2)

        def filter_view_items(search_term):
            search_lower = search_term.lower().strip()

            if search_lower:
                filtered =[
                item for item in view_all_items[0]
                if search_lower in item.get("name", "").lower()
                ]
            else:
                filtered = view_all_items[0]

            view_current_filtered[0]= filtered
            view_current_page[0]= 0
            display_view_page(0)

        def on_view_search_change(*args):
            if view_search_timer[0]is not None:
                try:
                    self.root.after_cancel(view_search_timer[0])
                except Exception:
                    pass
            view_search_timer[0]= self.root.after(200, lambda:filter_view_items(view_search_entry.get()))# type: ignore

        view_search_entry.bind("<KeyRelease>", on_view_search_change)
        container_selector.configure(command = lambda _:refresh_view())
        refresh_view()

        transfer_tab = tabview.tab("Transfer Items")
        transfer_tab.grid_rowconfigure(1, weight = 1)
        transfer_tab.grid_columnconfigure((0, 1), weight = 1)

        info_label = customtkinter.CTkLabel(transfer_tab, text = "Select source and destination containers to move items:", font = customtkinter.CTkFont(size = 13))
        info_label.grid(row = 0, column = 0, columnspan = 2, pady = 10)

        container_frame = customtkinter.CTkFrame(transfer_tab)
        container_frame.grid(row = 1, column = 0, columnspan = 2, sticky = "nsew", pady = 10)
        container_frame.grid_rowconfigure(0, weight = 1)
        container_frame.grid_columnconfigure((0, 1), weight = 1)

        source_frame = customtkinter.CTkFrame(container_frame)
        source_frame.grid(row = 0, column = 0, sticky = "nsew", padx =(0, 10))
        source_frame.grid_rowconfigure(3, weight = 1)
        source_frame.grid_columnconfigure(0, weight = 1)

        source_label = customtkinter.CTkLabel(source_frame, text = "Source Container", font = customtkinter.CTkFont(size = 16, weight = "bold"))
        source_label.grid(row = 0, column = 0, pady = 10)

        source_selector = customtkinter.CTkOptionMenu(source_frame, values =[c["name"]for c in containers], width = 300)
        source_selector.grid(row = 1, column = 0, pady = 5)
        source_selector.set(containers[1]["name"]if len(containers)>1 else containers[0]["name"])

        source_search_frame = customtkinter.CTkFrame(source_frame, fg_color = "transparent")
        source_search_frame.grid(row = 2, column = 0, sticky = "ew", padx = 10, pady = 5)
        source_search_frame.grid_columnconfigure(1, weight = 1)

        customtkinter.CTkLabel(source_search_frame, text = "Search:", font = customtkinter.CTkFont(size = 11)).grid(row = 0, column = 0, padx =(0, 5))
        source_search_entry = customtkinter.CTkEntry(source_search_frame, placeholder_text = "Filter...", width = 150)
        source_search_entry.grid(row = 0, column = 1, sticky = "w")
        source_info_label = customtkinter.CTkLabel(source_search_frame, text = "", font = customtkinter.CTkFont(size = 10), text_color = "gray")
        source_info_label.grid(row = 0, column = 2, padx = 10)

        source_scroll = customtkinter.CTkScrollableFrame(source_frame, width = 350, height = 320)
        source_scroll.grid(row = 3, column = 0, sticky = "nsew", padx = 10, pady =(5, 5))

        source_pagination_frame = customtkinter.CTkFrame(source_frame, fg_color = "transparent")
        source_pagination_frame.grid(row = 4, column = 0, pady = 5)

        dest_frame = customtkinter.CTkFrame(container_frame)
        dest_frame.grid(row = 0, column = 1, sticky = "nsew", padx =(10, 0))
        dest_frame.grid_rowconfigure(3, weight = 1)
        dest_frame.grid_columnconfigure(0, weight = 1)

        dest_label = customtkinter.CTkLabel(dest_frame, text = "Destination Container", font = customtkinter.CTkFont(size = 16, weight = "bold"))
        dest_label.grid(row = 0, column = 0, pady = 10)

        dest_selector = customtkinter.CTkOptionMenu(dest_frame, values =[c["name"]for c in containers], width = 300)
        dest_selector.grid(row = 1, column = 0, pady = 5)
        dest_selector.set(containers[0]["name"])

        dest_search_frame = customtkinter.CTkFrame(dest_frame, fg_color = "transparent")
        dest_search_frame.grid(row = 2, column = 0, sticky = "ew", padx = 10, pady = 5)
        dest_search_frame.grid_columnconfigure(1, weight = 1)

        customtkinter.CTkLabel(dest_search_frame, text = "Search:", font = customtkinter.CTkFont(size = 11)).grid(row = 0, column = 0, padx =(0, 5))
        dest_search_entry = customtkinter.CTkEntry(dest_search_frame, placeholder_text = "Filter...", width = 150)
        dest_search_entry.grid(row = 0, column = 1, sticky = "w")
        dest_info_label = customtkinter.CTkLabel(dest_search_frame, text = "", font = customtkinter.CTkFont(size = 10), text_color = "gray")
        dest_info_label.grid(row = 0, column = 2, padx = 10)

        dest_scroll = customtkinter.CTkScrollableFrame(dest_frame, width = 350, height = 320)
        dest_scroll.grid(row = 3, column = 0, sticky = "nsew", padx = 10, pady =(5, 5))

        dest_pagination_frame = customtkinter.CTkFrame(dest_frame, fg_color = "transparent")
        dest_pagination_frame.grid(row = 4, column = 0, pady = 5)

        TRANSFER_ITEMS_PER_PAGE = 15
        source_page =[0]
        source_all_items =[[]]
        source_filtered =[[]]
        source_search_timer =[None]
        dest_page =[0]
        dest_all_items =[[]]
        dest_filtered =[[]]
        dest_search_timer =[None]
        source_location_ref =[""]
        dest_location_ref =[""]

        def update_source_pagination(current, total):
            for widget in source_pagination_frame.winfo_children():
                widget.destroy()
            if total <=1:
                return
            prev_btn = customtkinter.CTkButton(source_pagination_frame, text = "<", width = 30, height = 25, command = lambda:display_source_page(current -1), state = "normal"if current >0 else "disabled")
            prev_btn.pack(side = "left", padx = 2)
            for p in range(max(0, current -2), min(total, current +3)):
                btn = customtkinter.CTkButton(source_pagination_frame, text = str(p +1), width = 28, height = 25, fg_color =("gray75", "gray25")if p ==current else None, command = lambda page = p:display_source_page(page))
                btn.pack(side = "left", padx = 1)
            next_btn = customtkinter.CTkButton(source_pagination_frame, text = ">", width = 30, height = 25, command = lambda:display_source_page(current +1), state = "normal"if current <total -1 else "disabled")
            next_btn.pack(side = "left", padx = 2)

        def update_dest_pagination(current, total):
            for widget in dest_pagination_frame.winfo_children():
                widget.destroy()
            if total <=1:
                return
            prev_btn = customtkinter.CTkButton(dest_pagination_frame, text = "<", width = 30, height = 25, command = lambda:display_dest_page(current -1), state = "normal"if current >0 else "disabled")
            prev_btn.pack(side = "left", padx = 2)
            for p in range(max(0, current -2), min(total, current +3)):
                btn = customtkinter.CTkButton(dest_pagination_frame, text = str(p +1), width = 28, height = 25, fg_color =("gray75", "gray25")if p ==current else None, command = lambda page = p:display_dest_page(page))
                btn.pack(side = "left", padx = 1)
            next_btn = customtkinter.CTkButton(dest_pagination_frame, text = ">", width = 30, height = 25, command = lambda:display_dest_page(current +1), state = "normal"if current <total -1 else "disabled")
            next_btn.pack(side = "left", padx = 2)

        def display_source_page(page_num):
            items = source_filtered[0]
            total_pages = max(1, (len(items)+TRANSFER_ITEMS_PER_PAGE -1)//TRANSFER_ITEMS_PER_PAGE)
            page_num = max(0, min(page_num, total_pages -1))
            source_page[0]= page_num

            for widget in source_scroll.winfo_children():
                widget.destroy()

            if not items:
                empty_label = customtkinter.CTkLabel(source_scroll, text = "Container is empty", text_color = "gray")
                empty_label.pack(pady = 20)
                source_info_label.configure(text = "0 items")
                update_source_pagination(0, 0)
                return

            start_idx = page_num *TRANSFER_ITEMS_PER_PAGE
            end_idx = min(start_idx +TRANSFER_ITEMS_PER_PAGE, len(items))

            for i in range(start_idx, end_idx):
                item_data = items[i]
                original_idx = item_data["_original_idx"]
                item = item_data["item"]

                item_frame = customtkinter.CTkFrame(source_scroll)
                item_frame.pack(fill = "x", pady = 2)

                item_name = self._format_item_name(item)
                item_weight = item.get("weight", 0)*item.get("quantity", 1)

                item_label = customtkinter.CTkLabel(
                item_frame,
                text = f"{item_name} x{item.get('quantity', 1)}({self._format_weight(item_weight)})",
                anchor = "w"
                )
                item_label.pack(side = "left", padx = 10, pady = 5)

                move_button = self._create_sound_button(
                item_frame,
                "Move →",
                lambda idx = original_idx:move_item(idx, source_location_ref[0], dest_location_ref[0]),
                width = 80,
                height = 30
                )
                move_button.pack(side = "right", padx = 10, pady = 5)

            source_info_label.configure(text = f"Pg {page_num +1}/{total_pages}({len(items)})")
            update_source_pagination(page_num, total_pages)

        def display_dest_page(page_num):
            items = dest_filtered[0]
            total_pages = max(1, (len(items)+TRANSFER_ITEMS_PER_PAGE -1)//TRANSFER_ITEMS_PER_PAGE)
            page_num = max(0, min(page_num, total_pages -1))
            dest_page[0]= page_num

            for widget in dest_scroll.winfo_children():
                widget.destroy()

            if not items:
                empty_label = customtkinter.CTkLabel(dest_scroll, text = "Container is empty", text_color = "gray")
                empty_label.pack(pady = 20)
                dest_info_label.configure(text = "0 items")
                update_dest_pagination(0, 0)
                return

            start_idx = page_num *TRANSFER_ITEMS_PER_PAGE
            end_idx = min(start_idx +TRANSFER_ITEMS_PER_PAGE, len(items))

            for i in range(start_idx, end_idx):
                item_data = items[i]
                item = item_data["item"]

                item_frame = customtkinter.CTkFrame(dest_scroll)
                item_frame.pack(fill = "x", pady = 2)

                item_name = self._format_item_name(item)
                item_weight = item.get("weight", 0)*item.get("quantity", 1)

                item_label = customtkinter.CTkLabel(
                item_frame,
                text = f"{item_name} x{item.get('quantity', 1)}({self._format_weight(item_weight)})",
                anchor = "w"
                )
                item_label.pack(side = "left", padx = 10, pady = 5)

            dest_info_label.configure(text = f"Pg {page_num +1}/{total_pages}({len(items)})")
            update_dest_pagination(page_num, total_pages)

        def filter_source_items(search_term):
            search_lower = search_term.lower().strip()
            if search_lower:
                filtered =[item for item in source_all_items[0]if search_lower in item["item"].get("name", "").lower()]
            else:
                filtered = source_all_items[0]
            source_filtered[0]= filtered
            source_page[0]= 0
            display_source_page(0)

        def filter_dest_items(search_term):
            search_lower = search_term.lower().strip()
            if search_lower:
                filtered =[item for item in dest_all_items[0]if search_lower in item["item"].get("name", "").lower()]
            else:
                filtered = dest_all_items[0]
            dest_filtered[0]= filtered
            dest_page[0]= 0
            display_dest_page(0)

        def on_source_search_change(*args):
            if source_search_timer[0]is not None:
                try:
                    self.root.after_cancel(source_search_timer[0])
                except Exception:
                    pass
            source_search_timer[0]= self.root.after(200, lambda:filter_source_items(source_search_entry.get()))# type: ignore

        def on_dest_search_change(*args):
            if dest_search_timer[0]is not None:
                try:
                    self.root.after_cancel(dest_search_timer[0])
                except Exception:
                    pass
            dest_search_timer[0]= self.root.after(200, lambda:filter_dest_items(dest_search_entry.get()))# type: ignore

        source_search_entry.bind("<KeyRelease>", on_source_search_change)
        dest_search_entry.bind("<KeyRelease>", on_dest_search_change)

        def refresh_containers():
            source_name = source_selector.get()
            dest_name = dest_selector.get()

            if source_name ==dest_name:
                source_selector.set(dest_name)
                dest_selector.set(source_name)
                source_name = source_selector.get()
                dest_name = dest_selector.get()
                if source_name ==dest_name:
                    for c in containers:
                        if c["name"]!=source_name:
                            dest_selector.set(c["name"])
                            dest_name = c["name"]
                            break

            source_container = next((c for c in containers if c["name"]==source_name), None)
            dest_container = next((c for c in containers if c["name"]==dest_name), None)

            if not source_container or not dest_container:
                return

            source_location_ref[0]= source_container["location"]
            dest_location_ref[0]= dest_container["location"]
            source_items = get_container_items(source_location_ref[0])
            dest_items = get_container_items(dest_location_ref[0])

            source_all_items[0]=[{"item":item, "_original_idx":i}for i, item in enumerate(source_items)if isinstance(item, dict)]
            dest_all_items[0]=[{"item":item, "_original_idx":i}for i, item in enumerate(dest_items)if isinstance(item, dict)]

            source_search_entry.delete(0, "end")
            dest_search_entry.delete(0, "end")
            source_filtered[0]= source_all_items[0]
            dest_filtered[0]= dest_all_items[0]
            source_page[0]= 0
            dest_page[0]= 0
            display_source_page(0)
            display_dest_page(0)

        def move_item(item_idx, source_location, dest_location):
            try:
                source_items = get_container_items(source_location)
                dest_items = get_container_items(dest_location)

                if item_idx >=len(source_items):
                    return

                item = source_items[item_idx]

                if not isinstance(item, dict):
                    item = {"name":str(item), "weight":0, "quantity":1}
                item_weight = item.get("weight", 0)*item.get("quantity", 1)

                dest_capacity = get_container_capacity(dest_location)
                if dest_capacity is not None:
                    current_dest_weight = sum(i.get("weight", 0)*i.get("quantity", 1)for i in dest_items)
                    if current_dest_weight +item_weight >dest_capacity:
                        self._popup_show_info("Error", "Not enough capacity in destination!", sound = "error")
                        return

                source_items.pop(item_idx)
                item = add_subslots_to_item(item)
                dest_items.append(item)

                set_container_items(source_location, source_items)
                set_container_items(dest_location, dest_items)

                encumbrance_info = self._calculate_encumbrance_status(save_data)
                save_data["encumbrance"]= encumbrance_info["total_weight"]

                self._save_file(save_data)

                refresh_containers()
                refresh_enc_info()
                self._play_ui_sound("success")
            except Exception as e:
                logging.error(f"Move failed: {e}")
                self._popup_show_info("Error", f"Move failed: {e}", sound = "error")

        source_selector.configure(command = lambda _:refresh_containers())
        dest_selector.configure(command = lambda _:refresh_containers())

        refresh_containers()

        back_button = self._create_sound_button(
        main_frame,
        "Back",
        lambda:[self._clear_window(), self._open_inventory_management()],
        width = 200,
        height = 40
        )
        back_button.grid(row = 2, column = 0, pady = 10)
