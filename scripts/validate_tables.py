"""
Table Validator — standalone CustomTkinter GUI that runs the same table
verification checks as main.py's validate_table_ids().

Usage:
    python scripts/validate_tables.py
"""

import json
import os
import sys
import argparse
import customtkinter


# ─── Core ─────────────────────────────────────────────────────────────────────

TABLES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tables")


def load_table(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _platforms_compatible(fplat, tplat, secondary=None):
    try:
        lf = str(fplat).strip().lower() if fplat is not None else ""
        lt = str(tplat).strip().lower() if tplat is not None else ""
        if not lf or not lt:
            return True
        if lf in lt or lt in lf:
            return True
        # Known equivalences between platforms (case-insensitive)
        PLATFORM_EQUIVALENTS = {
            "hk21": {"g3"},
            "g3": {"hk21"},
        }

        if secondary:
            ls = str(secondary).strip().lower()
            if ls and (ls in lf or lf in ls or ls in lt or lt in ls):
                return True

        try:
            if lt in PLATFORM_EQUIVALENTS.get(lf, set()):
                return True
            if lf in PLATFORM_EQUIVALENTS.get(lt, set()):
                return True
        except Exception:
            pass

        return False
    except Exception:
        return False


def _token_set(value):
    tokens = set()
    values = value if isinstance(value, (list, tuple, set)) else [value]
    for entry in values:
        if entry is None or isinstance(entry, dict):
            continue
        sval = str(entry).strip().lower()
        if sval and sval != "null":
            tokens.add(sval)
    return tokens


def _extract_ammo_fields(item):
    if not isinstance(item, dict):
        return set(), set()

    ammo_names = set()
    calibers = set()

    ammo_names |= _token_set(item.get("ammo_type"))
    ammo_names |= _token_set(item.get("ammunition"))
    calibers |= _token_set(item.get("caliber"))

    overrides = item.get("overrides")
    if isinstance(overrides, dict):
        ammo_names |= _token_set(overrides.get("ammo_type"))
        ammo_names |= _token_set(overrides.get("ammunition"))
        calibers |= _token_set(overrides.get("caliber"))

    return ammo_names, calibers


def _resolve_current_item(cur, id_map, source=None):
    if isinstance(cur, int):
        target = id_map.get(cur)
        ref_overrides = {}
    elif isinstance(cur, dict):
        target_id = cur.get("id") if "id" in cur else None
        if isinstance(target_id, int):
            target = id_map.get(target_id)
            ref_overrides = {k: v for k, v in cur.items() if k not in ("id", "sub_attachment")}
        else:
            target = cur
            ref_overrides = {}
    else:
        return None

    if not isinstance(target, dict):
        return None

    effective = dict(target)
    if isinstance(target.get("overrides"), dict):
        effective.update(target.get("overrides") or {})
    if ref_overrides:
        effective.update(ref_overrides)

    # If we're resolving something coming from parts/accessories/subslots,
    # avoid resolving to ammunition-like entries (they usually have 'caliber'
    # and lack 'type'/'slot'). This prevents mistakenly treating ammo as a
    # weapon part due to ID collisions across subtables.
    try:
        if isinstance(source, str) and source.lower() in ("parts", "accessories", "subslots"):
            if ("caliber" in target) and (not target.get("type") and not target.get("slot")):
                return None
    except Exception:
        pass

    return effective


def _collect_firearm_ammo_profiles(firearm, id_map):
    profiles = []
    base_names, base_calibers = _extract_ammo_fields(firearm)
    profiles.append(("base firearm", base_names, base_calibers))

    queue = []
    for key in ("parts", "accessories", "subslots"):
        entries = firearm.get(key) or []
        if isinstance(entries, list):
            for entry in entries:
                if isinstance(entry, dict) and "current" in entry:
                    queue.append((key, entry.get("current")))

    seen = set()
    while queue:
        source, cur = queue.pop(0)
        effective = _resolve_current_item(cur, id_map, source)
        if not isinstance(effective, dict):
            continue

        marker = id(effective)
        if marker in seen:
            continue
        seen.add(marker)

        names, calibers = _extract_ammo_fields(effective)
        if names or calibers:
            profiles.append((source, names, calibers))

        for nested_key in ("parts", "accessories", "subslots"):
            nested = effective.get(nested_key) or []
            if isinstance(nested, list):
                for nested_entry in nested:
                    if isinstance(nested_entry, dict) and "current" in nested_entry:
                        queue.append((nested_key, nested_entry.get("current")))

    return profiles


def _magazine_matches_systems(mag_item, required_systems):
    if not isinstance(mag_item, dict):
        return False
    if not required_systems:
        return True
    mag_systems = _token_set(mag_item.get("magazinesystem"))
    return bool(mag_systems & required_systems)


def _caliber_supported(item, caliber):
    if not isinstance(item, dict):
        return False
    cal_set = _token_set(item.get("caliber"))
    # If caliber is unspecified, treat as generic compatibility.
    if not cal_set:
        return True
    return caliber in cal_set


def validate_tables(tables_dir=None, secondary_platform=None):
    """
    Run every validation check that main.py's validate_table_ids() runs.
    Returns (active_errors, disabled_errors, warnings) where each item is
    a tuple of (category, message).
    """
    tables_dir = tables_dir or TABLES_DIR

    if not os.path.isdir(tables_dir):
        return [("Load Errors", f"Tables directory '{tables_dir}' not found.")], [], []

    table_files = [f for f in os.listdir(tables_dir) if f.endswith(".sldtbl") or f.endswith(".disabled")]
    if not table_files:
        return [], [], [("Load Errors", "No table files found to validate.")]

    disabled_files = {f for f in table_files if f.endswith(".disabled")}

    errors = []           # (category, msg) — blocking
    warnings = []         # (category, msg) — non-blocking

    global_id_map = {}
    all_table_items = []
    table_pretty_names = {}
    table_hardcore = {}
    table_magazines_by_file = {}
    referenced_slots_by_table = {}
    error_source = []  # (msg, table_file) — to split disabled vs active

    for table_file in sorted(table_files):
        table_path = os.path.join(tables_dir, table_file)
        try:
            table_data = load_table(table_path)
        except Exception as e:
            errors.append(("Load Errors", f"Failed to load '{table_file}': {e}"))
            error_source.append((errors[-1][1], table_file))
            continue

        table_name = table_data.get("prettyname", table_file)
        table_pretty_names[table_file] = table_name
        tables = table_data.get("tables", {})

        try:
            table_hardcore[table_file] = bool((table_data.get("additional_settings") or {}).get("hardcore_mode"))
        except Exception:
            table_hardcore[table_file] = False

        # ── 1. Magazine compatibility ─────────────────────────────────────
        try:
            magazine_items = tables.get("magazines", []) or [] if isinstance(tables, dict) else []
            table_magazines_by_file[table_file] = [m for m in magazine_items if isinstance(m, dict)]
            magazine_systems = set()
            for mag in magazine_items:
                if isinstance(mag, dict):
                    ms = mag.get("magazinesystem")
                    if ms is None:
                        continue
                    if isinstance(ms, list):
                        for m in ms:
                            magazine_systems.add(str(m))
                    else:
                        magazine_systems.add(str(ms))

            for subtable_name, items in tables.items():
                if not isinstance(items, list):
                    continue
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    if item.get("firearm") and str(item.get("magazinetype", "")).lower() == "detachable box":
                        if item.get("has_magazine_in_pool") is False:
                            continue
                        friendly = f"Table '{table_name}': Firearm '{item.get('name')}' (ID {item.get('id')})"
                        f_ms = item.get("magazinesystem")
                        if f_ms is None:
                            msg = f"{friendly} missing 'magazinesystem' field"
                            errors.append(("Magazine Compatibility", msg))
                            error_source.append((msg, table_file))
                            continue
                        needed = [f_ms] if not isinstance(f_ms, list) else f_ms
                        needed = [str(n) for n in needed]
                        if not any(n in magazine_systems for n in needed):
                            msg = f"{friendly} has no magazines matching magazinesystem(s): {needed}"
                            errors.append(("Magazine Compatibility", msg))
                            error_source.append((msg, table_file))
        except Exception as e:
            warnings.append(("Magazine Compatibility", f"Magazine check failed for '{table_file}': {e}"))

        # ── Collect IDs and items ─────────────────────────────────────────
        file_ids = []
        for subtable_name, items in tables.items():
            if not isinstance(items, list):
                continue
            for idx, item in enumerate(items):
                if isinstance(item, dict) and "id" in item:
                    item_id = item["id"]
                    file_ids.append(item_id)
                    entry = (table_file, subtable_name, item.get("name") or f"index_{idx}")
                    global_id_map.setdefault(item_id, []).append(entry)

                if isinstance(item, dict):
                    all_table_items.append((item, table_file, subtable_name))

                    # collect referenced slots
                    for key in ("accessories", "subslots"):
                        lst = item.get(key) or []
                        if isinstance(lst, list):
                            for entry_item in lst:
                                if isinstance(entry_item, dict) and entry_item.get("slot"):
                                    slot_name = str(entry_item["slot"]).strip()
                                    referenced_slots_by_table.setdefault(table_file, set()).add(slot_name)

        # ── 2. ID sequence ────────────────────────────────────────────────
        if not file_ids:
            warnings.append(("ID Sequence", f"Table '{table_name}': No items with IDs found."))
            continue

        file_ids.sort()
        min_id = file_ids[0]
        max_id = file_ids[-1]
        next_id = max_id + 1
        expected_ids = set(range(min_id, max_id + 1))
        actual_ids = set(file_ids)

        if expected_ids == actual_ids:
            # IDs valid — informational
            pass
        else:
            missing_ids = sorted(expected_ids - actual_ids)

            # build suggested fixes
            try:
                file_entries = []
                for iid in sorted(actual_ids):
                    locs = global_id_map.get(iid, [])
                    for f, sub, name in locs:
                        if f == table_file:
                            file_entries.append((iid, sub, name))
                            break
                suggested_lines = []
                new_id = min_id
                for old_id, sub, name in file_entries:
                    if old_id != new_id:
                        suggested_lines.append(f"  Change ID {old_id} ({sub}:{name}) -> {new_id}")
                    new_id += 1
            except Exception:
                suggested_lines = ["  Unable to build suggested ID changes."]

            msg_lines = [
                f"Table '{table_name}': ID sequence broken",
                f"  Missing IDs: {missing_ids}",
                f"  Last ID: {max_id}",
                f"  Next ID: {next_id}",
            ]
            if suggested_lines:
                msg_lines.append("  Suggested changes:")
                msg_lines.extend(suggested_lines)

            msg = "\n".join(msg_lines)
            errors.append(("ID Sequence", msg))
            error_source.append((msg, table_file))

    id_to_item_by_table = {}
    id_subtable_map = {}  # (table_file, item_id) -> subtable_name
    for it, tf, sub in all_table_items:
        if isinstance(it, dict) and "id" in it:
            id_to_item_by_table.setdefault(tf, {})[it["id"]] = it
            id_subtable_map[(tf, it["id"])] = sub

    # ── 3. Hardcore mode validation ───────────────────────────────────────
    try:
        for item, tf, sub in all_table_items:
            if not isinstance(item, dict):
                continue
            if not table_hardcore.get(tf):
                continue
            if not item.get("firearm"):
                continue
            fname = item.get("name") or "<unnamed>"
            fplat = item.get("platform") or ""
            parts = item.get("parts") or []
            for p in parts:
                if not isinstance(p, dict):
                    continue
                cur = p.get("current")
                if cur is None:
                    continue
                target_id = None
                if isinstance(cur, int):
                    target_id = cur
                elif isinstance(cur, dict) and "id" in cur:
                    target_id = cur.get("id")
                if target_id is None or (isinstance(target_id, str) and str(target_id).strip().lower() == "null"):
                    msg = f"Table '{table_pretty_names.get(tf, tf)}': Firearm '{fname}' has part '{p.get('name')}' with invalid 'current' id: {target_id}"
                    errors.append(("Hardcore Mode", msg))
                    error_source.append((msg, tf))
                    continue
                table_id_map = id_to_item_by_table.get(tf, {})
                if target_id not in table_id_map:
                    msg = f"Table '{table_pretty_names.get(tf, tf)}': Firearm '{fname}' has part '{p.get('name')}' referencing missing item ID {target_id}"
                    errors.append(("Hardcore Mode", msg))
                    error_source.append((msg, tf))
                    continue
                target = table_id_map.get(target_id) or {}
                tplat = target.get("platform") or ""
                # Prefer per-item secondary_platform if present, otherwise fall back to global arg
                item_secondary = item.get("secondary_platform") if isinstance(item, dict) else None
                item_secondary = item_secondary or secondary_platform
                if str(fplat).strip() and str(tplat).strip() and not _platforms_compatible(fplat, tplat, item_secondary):
                    msg = f"Table '{table_pretty_names.get(tf, tf)}': Firearm '{fname}' part '{p.get('name')}' references item ID {target_id} with platform '{tplat}' which does not match firearm platform '{fplat}'"
                    errors.append(("Hardcore Mode", msg))
                    error_source.append((msg, tf))
    except Exception as e:
        warnings.append(("Hardcore Mode", f"Hardcore mode check failed: {e}"))

    # ── 3b. Part reference validation (all tables) ───────────────────────
    try:
        for item, tf, sub in all_table_items:
            if not isinstance(item, dict) or not item.get("firearm"):
                continue
            fname = item.get("name") or "<unnamed>"
            display = table_pretty_names.get(tf, tf)
            firearm_platform = item.get("platform") or ""
            item_secondary = item.get("secondary_platform") if isinstance(item, dict) else None
            item_secondary = item_secondary or secondary_platform
            table_id_map = id_to_item_by_table.get(tf, {})

            for p in item.get("parts") or []:
                if not isinstance(p, dict):
                    continue
                cur = p.get("current")
                if cur is None:
                    continue
                target_id = None
                if isinstance(cur, int):
                    target_id = cur
                elif isinstance(cur, dict) and "id" in cur:
                    target_id = cur["id"]
                if target_id is None:
                    continue

                target_item = table_id_map.get(target_id)
                if target_item is None:
                    # Missing IDs are reported by the Hardcore Mode check
                    continue

                # The resolved item must live in the 'parts' subtable
                resolved_sub = id_subtable_map.get((tf, target_id), "")
                if str(resolved_sub).lower() != "parts":
                    msg = (
                        f"Table '{display}': Firearm '{fname}' part slot "
                        f"'{p.get('name', '?')}' references item ID {target_id} "
                        f"('{target_item.get('name', '?')}') which is in subtable "
                        f"'{resolved_sub}', not 'parts'."
                    )
                    errors.append(("Part References", msg))
                    error_source.append((msg, tf))
                    continue

                # Platform of the referenced part must match the firearm
                tplat = target_item.get("platform") or ""
                if str(firearm_platform).strip() and str(tplat).strip() and not _platforms_compatible(firearm_platform, tplat, item_secondary):
                    msg = (
                        f"Table '{display}': Firearm '{fname}' part slot "
                        f"'{p.get('name', '?')}' references item ID {target_id} "
                        f"('{target_item.get('name', '?')}') with platform '{tplat}', "
                        f"incompatible with firearm platform '{firearm_platform}'."
                    )
                    errors.append(("Part References", msg))
                    error_source.append((msg, tf))
    except Exception as e:
        warnings.append(("Part References", f"Part reference check failed: {e}"))

    # ── 4. Ammunition compatibility ───────────────────────────────────────
    ammo_names_present = set()
    ammo_calibers_present = set()
    try:
        for item, tf, sub in all_table_items:
            if isinstance(sub, str) and sub.lower() in ("ammunition", "ammo"):
                name = item.get("name")
                if name:
                    ammo_names_present.add(str(name).strip().lower())
                calib = item.get("caliber")
                ammo_calibers_present |= _token_set(calib)
    except Exception:
        pass

    try:
        for item, tf, sub in all_table_items:
            if not isinstance(item, dict) or not item.get("firearm"):
                continue
            name = item.get("name") or "<unnamed>"
            display = table_pretty_names.get(tf, tf)
            table_id_map = id_to_item_by_table.get(tf, {})
            profiles = _collect_firearm_ammo_profiles(item, table_id_map)

            required_calibers = set()
            for src, prof_ammo_names, prof_calibers in profiles:
                required_calibers |= prof_calibers

                missing_profile_ammo = sorted(prof_ammo_names - ammo_names_present)
                if missing_profile_ammo:
                    msg = (
                        f"Firearm '{name}' in table '{display}' has {src} override/profile requiring ammunition "
                        f"{missing_profile_ammo} but no matching ammunition entry found."
                    )
                    errors.append(("Ammunition", msg))
                    error_source.append((msg, tf))

                missing_profile_calibers = sorted(prof_calibers - ammo_calibers_present)
                if missing_profile_calibers:
                    msg = (
                        f"Firearm '{name}' in table '{display}' has {src} override/profile requiring caliber(s) "
                        f"{missing_profile_calibers} but no ammunition with those caliber(s) exists."
                    )
                    errors.append(("Ammunition", msg))
                    error_source.append((msg, tf))

            if item.get("has_magazine_in_pool") is not False and str(item.get("magazinetype", "")).lower() == "detachable box":
                required_systems = _token_set(item.get("magazinesystem"))
                if item.get("dualfeed"):
                    required_systems |= _token_set(item.get("submagazinesystem"))

                compatible_mags = [
                    mag for mag in (table_magazines_by_file.get(tf) or [])
                    if _magazine_matches_systems(mag, required_systems)
                ]

                if required_systems and not compatible_mags:
                    msg = (
                        f"Table '{display}': Firearm '{name}' has no compatible magazine items for "
                        f"magazine systems {sorted(required_systems)}."
                    )
                    errors.append(("Magazine Compatibility", msg))
                    error_source.append((msg, tf))
                else:
                    missing_mag_calibers = []
                    for cal in sorted(required_calibers):
                        if not any(_caliber_supported(mag, cal) for mag in compatible_mags):
                            missing_mag_calibers.append(cal)
                    if missing_mag_calibers:
                        msg = (
                            f"Table '{display}': Firearm '{name}' can accept caliber(s) {missing_mag_calibers} "
                            f"across its ammo profiles, but no compatible magazine covers those caliber(s)."
                        )
                        errors.append(("Magazine Compatibility", msg))
                        error_source.append((msg, tf))

            firearm_platform = item.get("platform") or ""
            item_secondary = item.get("secondary_platform") if isinstance(item, dict) else None
            item_secondary = item_secondary or secondary_platform

            # If the `parts` key is explicitly present and set to null,
            # the firearm intentionally has no wear/replaceable parts.
            # In that case, skip the part-compatibility checks so we
            # don't raise spurious errors for weapons that simply don't use parts.
            parts_key_present = isinstance(item, dict) and ("parts" in item)
            parts_explicitly_null = parts_key_present and item.get("parts") is None

            if not parts_explicitly_null:
                part_candidates = []
                for part_item, part_tf, part_sub in all_table_items:
                    if part_tf != tf:
                        continue
                    if not isinstance(part_item, dict):
                        continue
                    if str(part_sub).lower() != "parts":
                        continue
                    pplat = part_item.get("platform") or ""
                    if str(firearm_platform).strip() and str(pplat).strip() and not _platforms_compatible(firearm_platform, pplat, item_secondary):
                        continue
                    part_candidates.append(part_item)

                for p in item.get("parts") or []:
                    if not isinstance(p, dict):
                        continue
                    resolved = _resolve_current_item(p.get("current"), table_id_map, 'parts')
                    if isinstance(resolved, dict):
                        part_candidates.append(resolved)

                missing_part_calibers = []
                for cal in sorted(required_calibers):
                    if not any(_caliber_supported(pc, cal) for pc in part_candidates):
                        missing_part_calibers.append(cal)

                if missing_part_calibers:
                    msg = (
                        f"Table '{display}': Firearm '{name}' can accept caliber(s) {missing_part_calibers}, "
                        f"but no compatible part supports those caliber(s)."
                    )
                    errors.append(("Ammunition", msg))
                    error_source.append((msg, tf))
    except Exception as e:
        warnings.append(("Ammunition", f"Ammunition check failed: {e}"))

    # ── 5. Duplicate IDs ─────────────────────────────────────────────────
    duplicate_suggestions = []
    for item_id, locations in global_id_map.items():
        by_file = {}
        for f, sub, name in locations:
            by_file.setdefault(f, []).append((f, sub, name))
        for file_locs in by_file.values():
            if len(file_locs) > 1:
                loc_str = "; ".join(f"{f}:{sub}:{name}" for f, sub, name in file_locs)
                msg = f"Duplicate ID detected: {item_id} used in: {loc_str}"
                errors.append(("Duplicate IDs", msg))
                error_source.append((msg, file_locs[0][0]))
                max_id_all = max(global_id_map.keys()) if global_id_map else item_id
                for idx, (f, sub, name) in enumerate(file_locs):
                    if idx == 0:
                        continue
                    max_id_all += 1
                    duplicate_suggestions.append(f"  Change ID {item_id} ({f}:{sub}:{name}) -> {max_id_all}")

    # ── 6. Weapon sound folders ──────────────────────────────────────────
    sound_root = os.path.join(os.path.dirname(tables_dir), "sounds", "firearms", "weaponsounds")
    seen_platforms = set()
    for item, tf, sub in all_table_items:
        if not isinstance(item, dict) or not item.get("firearm"):
            continue
        if item.get("ignore_weaponsound_in_log"):
            continue
        plat = item.get("platform")
        if not plat:
            continue
        plat_key = str(plat).strip().lower()
        if not plat_key or plat_key in seen_platforms:
            continue
        seen_platforms.add(plat_key)
        folder = os.path.join(sound_root, plat_key)
        if not os.path.isdir(folder):
            warnings.append(("Weapon Sounds", f"Table '{table_pretty_names.get(tf, tf)}': Firearm '{item.get('name')}' platform '{plat}' missing weaponsound folder '{folder}'"))

    # ── 7. Slot references ────────────────────────────────────────────────
    def item_matches_slot(item, slot_name):
        if isinstance(item, (list, tuple)) and item:
            item = item[0]
        if not isinstance(item, dict):
            return False
        for v in item.values():
            if isinstance(v, str) and v.strip().lower() == slot_name.lower():
                return True
            if isinstance(v, (list, tuple)):
                for e in v:
                    if isinstance(e, str) and e.strip().lower() == slot_name.lower():
                        return True
        if isinstance(item.get("slot"), str) and item["slot"].strip().lower() == slot_name.lower():
            return True
        return False

    for table_file_ref, slots in referenced_slots_by_table.items():
        for slot in sorted(slots):
            if isinstance(slot, str) and slot.strip().lower() == "weapon_slot":
                continue
            found = any(item_matches_slot(it, slot) for it, tf, sub in all_table_items if tf == table_file_ref)
            if not found:
                display = table_pretty_names.get(table_file_ref, table_file_ref)
                warnings.append(("Slot References", f"Table '{display}' references slot '{slot}' but no items are available in that table to populate it."))

    # ── 8. Store categories ──────────────────────────────────────────────
    for table_file_sc in sorted(table_files):
        try:
            table_path_sc = os.path.join(tables_dir, table_file_sc)
            table_data_sc = load_table(table_path_sc)
            tables_sc = table_data_sc.get("tables", {})
            stores_sc = tables_sc.get("stores", []) or []
            if not stores_sc:
                continue
            display_sc = table_pretty_names.get(table_file_sc, table_file_sc)
            store_item_ids = set()
            store_table_names = set()
            for store_sc in stores_sc:
                if not isinstance(store_sc, dict):
                    continue
                for inv_entry in store_sc.get("inventory", []) or []:
                    if not isinstance(inv_entry, dict):
                        continue
                    if inv_entry.get("type") == "table":
                        tname = inv_entry.get("table")
                        if tname:
                            store_table_names.add(tname)
                    elif inv_entry.get("type") == "id":
                        iid = inv_entry.get("id")
                        if iid is not None:
                            store_item_ids.add(iid)
            for sub_name, sub_items in tables_sc.items():
                if not isinstance(sub_items, list):
                    continue
                in_store_table = sub_name in store_table_names
                for item_sc in sub_items:
                    if not isinstance(item_sc, dict):
                        continue
                    in_store = in_store_table or item_sc.get("id") in store_item_ids
                    if in_store and not item_sc.get("shop_category"):
                        item_name_sc = item_sc.get("name") or f"ID {item_sc.get('id', '?')}"
                        warnings.append(("Store Categories", f"Table '{display_sc}': Item '{item_name_sc}' in subtable '{sub_name}' is referenced by a store but missing 'shop_category' field."))
        except Exception:
            pass

    # ── 9. Missing armory/shop category ──────────────────────────────────
    skip_subtables = {"stores", "armories", "businesses", "settings", "additional_settings"}
    for item_cat, tf_cat, sub_cat in all_table_items:
        if not isinstance(item_cat, dict):
            continue
        if sub_cat and str(sub_cat).lower() in skip_subtables:
            continue
        has_armory = bool(item_cat.get("armory_category"))
        has_shop = bool(item_cat.get("shop_category"))
        if not has_armory and not has_shop:
            item_name_cat = item_cat.get("name") or f"ID {item_cat.get('id', '?')}"
            display_cat = table_pretty_names.get(tf_cat, tf_cat)
            warnings.append(("Missing Categories", f"Table '{display_cat}': Item '{item_name_cat}' in subtable '{sub_cat}' is missing both 'armory_category' and 'shop_category' fields."))

    # ── 10. Equipment slot coverage ───────────────────────────────────────
    KNOWN_EQUIPMENT_SLOTS = {
        "head", "face", "torso", "left wrist", "right wrist",
        "left hand", "right hand", "legs", "feet", "neck", "chest",
        "back", "waist", "waistband", "left shoulder", "right shoulder",
        "left arm", "right arm", "left leg", "right leg",
    }
    try:
        # First pass: collect every slot name referenced inside a subslots[] list
        # so that items designed to fill subslots (NVGs, ARC accessories, etc.)
        # are not mistakenly treated as main body-slot items.
        known_subslot_names: set = set()
        for item_eq, _tf_eq, _sub_eq in all_table_items:
            if not isinstance(item_eq, dict):
                continue
            for ss in (item_eq.get("subslots") or []):
                if isinstance(ss, dict) and ss.get("slot"):
                    known_subslot_names.add(str(ss["slot"]).strip().lower())

        # Second pass: coverage check — only consider items whose slot is a
        # known body slot, not items filling equipment subslots.
        globally_covered: set = set()
        any_equippable = False
        for item_eq, tf_eq, _sub_eq in all_table_items:
            if not isinstance(item_eq, dict) or not item_eq.get("equippable"):
                continue
            slot_val = item_eq.get("slot")
            if not slot_val or not isinstance(slot_val, str):
                continue
            slot_norm = slot_val.strip().lower()
            any_equippable = True

            if slot_norm in KNOWN_EQUIPMENT_SLOTS:
                globally_covered.add(slot_norm)
            elif slot_norm not in known_subslot_names:
                # Not a body slot and not a known subslot filler — likely a typo
                item_name_eq = item_eq.get("name") or f"ID {item_eq.get('id', '?')}"
                display_eq = table_pretty_names.get(tf_eq, tf_eq)
                warnings.append((
                    "Equipment Slots",
                    f"Table '{display_eq}': Equippable item '{item_name_eq}' uses unrecognized equipment slot '{slot_val}'.",
                ))

        if any_equippable:
            for known_slot in sorted(KNOWN_EQUIPMENT_SLOTS):
                if known_slot not in globally_covered:
                    warnings.append((
                        "Equipment Slots",
                        f"Equipment slot '{known_slot}' has no items available in any table.",
                    ))
    except Exception as e:
        warnings.append(("Equipment Slots", f"Equipment slot check failed: {e}"))

    # ── Split disabled vs active errors ──────────────────────────────────
    disabled_err_set = set()
    for msg, tf in error_source:
        if tf in disabled_files:
            disabled_err_set.add(msg)

    active_errors = [(cat, m) for cat, m in errors if m not in disabled_err_set]
    disabled_errors = [(cat, m) for cat, m in errors if m in disabled_err_set]

    if duplicate_suggestions:
        active_errors.append(("Duplicate IDs", "Suggested duplicate ID fixes:\n" + "\n".join(duplicate_suggestions)))

    return active_errors, disabled_errors, warnings


# ─── GUI ──────────────────────────────────────────────────────────────────────

ALL_CATEGORIES = [
    "Load Errors",
    "Magazine Compatibility",
    "ID Sequence",
    "Hardcore Mode",
    "Ammunition",
    "Duplicate IDs",
    "Weapon Sounds",
    "Slot References",
    "Equipment Slots",
    "Store Categories",
    "Missing Categories",
]


class ValidatorApp(customtkinter.CTk):
    def __init__(self, secondary_platform=None):
        super().__init__()
        self.title("Table Validator")
        self.geometry("900x650")
        self.minsize(700, 450)
        # Keep window on top of other windows
        self.attributes("-topmost", True)

        # Optional secondary platform to allow when checking parts
        self._secondary_platform = secondary_platform

        self._active_errors = []
        self._disabled_errors = []
        self._warnings = []
        self._filter_vars = {}

        # ── Top bar ───────────────────────────────────────────────────────
        top = customtkinter.CTkFrame(self, fg_color="transparent")
        top.pack(fill="x", padx=10, pady=(10, 4))

        self.status_label = customtkinter.CTkLabel(top, text="", anchor="w",
                                                    font=customtkinter.CTkFont(size=13, weight="bold"))
        self.status_label.pack(side="left", fill="x", expand=True)

        self.refresh_btn = customtkinter.CTkButton(top, text="Refresh", width=100,
                                                    command=self.run_validation)
        self.refresh_btn.pack(side="right")

        # ── Filter bar ───────────────────────────────────────────────────
        filter_frame = customtkinter.CTkFrame(self, fg_color="transparent")
        filter_frame.pack(fill="x", padx=10, pady=(2, 2))

        customtkinter.CTkLabel(filter_frame, text="Filters:",
                               font=customtkinter.CTkFont(size=12, weight="bold")
                               ).pack(side="left", padx=(0, 6))

        for cat in ALL_CATEGORIES:
            var = customtkinter.BooleanVar(value=True)
            self._filter_vars[cat] = var
            cb = customtkinter.CTkCheckBox(filter_frame, text=cat, variable=var,
                                            font=customtkinter.CTkFont(size=11),
                                            checkbox_width=18, checkbox_height=18,
                                            command=self._redraw)
            cb.pack(side="left", padx=4)

        # ── Results area ──────────────────────────────────────────────────
        self.textbox = customtkinter.CTkTextbox(self, wrap="word",
                                                 font=customtkinter.CTkFont(family="Consolas", size=13),
                                                 state="disabled")
        self.textbox.pack(fill="both", expand=True, padx=10, pady=(4, 10))

        self.textbox.tag_config("error", foreground="#e05555")
        self.textbox.tag_config("warning", foreground="#e0a030")
        self.textbox.tag_config("ok", foreground="#50c878")
        self.textbox.tag_config("heading", foreground="#5dade2")
        self.textbox.tag_config("info", foreground="#aaaaaa")
        self.textbox.tag_config("cat_label", foreground="#c0c0c0")

        self.run_validation()

    # ──────────────────────────────────────────────────────────────────────

    def _insert(self, text, tag=None):
        self.textbox.configure(state="normal")
        if tag:
            self.textbox.insert("end", text, tag)
        else:
            self.textbox.insert("end", text)
        self.textbox.configure(state="disabled")

    def _enabled_categories(self):
        return {cat for cat, var in self._filter_vars.items() if var.get()}

    def _group_by_category(self, items):
        groups = {}
        for cat, msg in items:
            groups.setdefault(cat, []).append(msg)
        return groups

    def run_validation(self):
        self._active_errors, self._disabled_errors, self._warnings = validate_tables(secondary_platform=getattr(self, "_secondary_platform", None))
        self._redraw()

    def _redraw(self):
        self.textbox.configure(state="normal")
        self.textbox.delete("1.0", "end")
        self.textbox.configure(state="disabled")

        enabled_cats = self._enabled_categories()

        # ── Tables scanned ────────────────────────────────────────────────
        tables_dir = TABLES_DIR
        if os.path.isdir(tables_dir):
            table_files = [f for f in os.listdir(tables_dir)
                           if f.endswith(".sldtbl") or f.endswith(".disabled")]
            enabled = [f for f in table_files if not f.endswith(".disabled")]
            disabled = [f for f in table_files if f.endswith(".disabled")]

            self._insert("Tables scanned\n", "heading")
            for f in sorted(enabled):
                try:
                    td = load_table(os.path.join(tables_dir, f))
                    pretty = td.get("prettyname", f)
                    max_id = 0
                    for items in (td.get("tables") or {}).values():
                        if isinstance(items, list):
                            for it in items:
                                if isinstance(it, dict) and "id" in it:
                                    max_id = max(max_id, it["id"])
                    self._insert(f"  ✓ {pretty} ({f})  next ID: {max_id + 1}\n", "ok")
                except Exception:
                    self._insert(f"  ✓ {f}\n", "ok")
            for f in sorted(disabled):
                try:
                    td = load_table(os.path.join(tables_dir, f))
                    pretty = td.get("prettyname", f)
                    max_id = 0
                    for items in (td.get("tables") or {}).values():
                        if isinstance(items, list):
                            for it in items:
                                if isinstance(it, dict) and "id" in it:
                                    max_id = max(max_id, it["id"])
                    self._insert(f"  ○ {pretty} ({f}) [DISABLED]  next ID: {max_id + 1}\n", "info")
                except Exception:
                    self._insert(f"  ○ {f} [DISABLED]\n", "info")

        # ── Errors (grouped by category) ──────────────────────────────────
        filtered_errors = [(c, m) for c, m in self._active_errors if c in enabled_cats]
        if filtered_errors:
            self._insert(f"\nErrors ({len(filtered_errors)})\n", "heading")
            groups = self._group_by_category(filtered_errors)
            n = 1
            for cat in ALL_CATEGORIES:
                if cat not in groups:
                    continue
                self._insert(f"\n  [{cat}]\n", "cat_label")
                for msg in groups[cat]:
                    self._insert(f"    {n}. {msg}\n", "error")
                    n += 1
        else:
            self._insert("\nErrors\n", "heading")
            hidden = len(self._active_errors) - len(filtered_errors)
            if not self._active_errors:
                self._insert("  None — all checks passed!\n", "ok")
            else:
                self._insert(f"  All {len(self._active_errors)} error(s) hidden by filters.\n", "info")

        # ── Disabled table errors (grouped) ───────────────────────────────
        filtered_disabled = [(c, m) for c, m in self._disabled_errors if c in enabled_cats]
        if filtered_disabled:
            self._insert(f"\nDisabled table errors ({len(filtered_disabled)})\n", "heading")
            groups = self._group_by_category(filtered_disabled)
            n = 1
            for cat in ALL_CATEGORIES:
                if cat not in groups:
                    continue
                self._insert(f"\n  [{cat}]\n", "cat_label")
                for msg in groups[cat]:
                    self._insert(f"    {n}. {msg}\n", "warning")
                    n += 1

        # ── Warnings (grouped) ────────────────────────────────────────────
        filtered_warnings = [(c, m) for c, m in self._warnings if c in enabled_cats]
        if filtered_warnings:
            self._insert(f"\nWarnings ({len(filtered_warnings)})\n", "heading")
            groups = self._group_by_category(filtered_warnings)
            n = 1
            for cat in ALL_CATEGORIES:
                if cat not in groups:
                    continue
                self._insert(f"\n  [{cat}]\n", "cat_label")
                for msg in groups[cat]:
                    self._insert(f"    {n}. {msg}\n", "warning")
                    n += 1

        # ── Status bar ───────────────────────────────────────────────────
        total_errors = len(self._active_errors)
        if total_errors:
            shown = len(filtered_errors)
            self.status_label.configure(
                text=f"{total_errors} error(s) total ({shown} shown) — would block main.py startup.",
                text_color="#e05555")
        else:
            self.status_label.configure(
                text="Tables are valid — main.py would start without issues.",
                text_color="#50c878")


def main():
    customtkinter.set_appearance_mode("dark")
    customtkinter.set_default_color_theme("dark-blue")
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('--secondary-platform', help='Optional secondary platform to allow when checking part compatibility', default=None)
    args, _ = parser.parse_known_args()

    app = ValidatorApp(secondary_platform=args.secondary_platform)
    app.mainloop()


if __name__ == "__main__":
    main()
