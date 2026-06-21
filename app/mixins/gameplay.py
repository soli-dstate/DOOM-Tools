"""GameplayMixin — App methods for the "gameplay" feature area."""
from app.foundation import *
import logging


class GameplayMixin:

    def _cleanup_temporary_effects(self, save_data):
        if not isinstance(save_data, dict):
            return []
        effects = save_data.get('temporary_effects')
        if not isinstance(effects, list):
            save_data['temporary_effects'] = []
            return []
        now_ts = time.time()
        active_effects = []
        for effect in effects:
            if not isinstance(effect, dict):
                continue
            expires_at = effect.get('expires_at')
            if expires_at is None:
                active_effects.append(effect)
                continue
            try:
                expires_at = float(expires_at)
            except (TypeError, ValueError):
                logging.exception("Suppressed exception")
                continue
            if expires_at > now_ts:
                active_effects.append(effect)
        if len(active_effects) != len(effects):
            save_data['temporary_effects'] = active_effects
        return active_effects

    def _get_active_temporary_effects(self, save_data, effect_name = None):
        active_effects = self._cleanup_temporary_effects(save_data)
        if effect_name is None:
            return active_effects
        name_key = str(effect_name).strip().lower()
        return [fx for fx in active_effects if str(fx.get('name') or fx.get('id') or '').strip().lower() == name_key]

    def _get_temporary_aim_modifier(self, save_data):
        total_aim = 0.0
        for effect in self._get_active_temporary_effects(save_data):
            try:
                stats = effect.get('stats') or {}
                if isinstance(stats, dict):
                    total_aim += float(stats.get('aim', 0) or 0)
            except Exception:
                logging.exception("Suppressed exception")
        return total_aim

    def _format_temporary_effect_remaining(self, effect, now_ts = None):
        if now_ts is None:
            now_ts = time.time()
        if not isinstance(effect, dict):
            return 'Unknown'
        expires_at = effect.get('expires_at')
        if expires_at is None:
            return 'Persistent'
        try:
            remaining = max(0, int(float(expires_at) - float(now_ts)))
        except (TypeError, ValueError):
            return 'Expired'
        rem_m, rem_s = divmod(remaining, 60)
        if rem_m >= 60:
            rem_h, rem_m = divmod(rem_m, 60)
            return f'{rem_h}h {rem_m}m {rem_s:02d}s'
        return f'{rem_m}m {rem_s:02d}s'

    def _get_temporary_effect_display_lines(self, save_data, now_ts = None):
        lines = []
        for effect in self._get_active_temporary_effects(save_data):
            if not isinstance(effect, dict):
                continue
            try:
                effect_name = str(effect.get('name') or effect.get('id') or 'Unknown Effect')
                stats = effect.get('stats') or {}
                stat_parts = []
                if isinstance(stats, dict):
                    for stat_name, stat_value in stats.items():
                        try:
                            stat_parts.append(f'{stat_name.title()} {float(stat_value):+g}')
                        except Exception:
                            stat_parts.append(f'{stat_name.title()} {stat_value}')
                stat_text = ', '.join(stat_parts) if stat_parts else 'No stat changes'
                timer_text = self._format_temporary_effect_remaining(effect, now_ts)
                lines.append(f'  {effect_name}: {stat_text} | Remaining: {timer_text}')
            except Exception:
                lines.append(f'  {effect}')
        return lines

    def _maybe_apply_garand_thumb(self, weapon, save_data):
        if not isinstance(weapon, dict) or not isinstance(save_data, dict):
            return None
        mag_type = str(weapon.get('magazinetype', '') or '').lower()
        if 'en bloc' not in mag_type or not weapon.get('bolt_catch'):
            return None

        garand_state = save_data.setdefault('defect_flags', {})
        if not isinstance(garand_state, dict):
            garand_state = {}
            save_data['defect_flags'] = garand_state
        if garand_state.get('garand_thumb_received'):
            return {'applied': False, 'locked_out': True}

        roll = random.randint(1, 20)
        if roll >= 5:
            return {'roll': roll, 'applied': False}

        effects = save_data.setdefault('temporary_effects', [])
        if not isinstance(effects, list):
            effects = []
            save_data['temporary_effects'] = effects

        now_ts = time.time()
        expires_at = now_ts + (30 * 60)
        effect_payload = {
            'id': 'garand_thumb',
            'name': 'Garand Thumb',
            'source_weapon_id': str(weapon.get('id', 'unknown')),
            'source_weapon_name': weapon.get('name', 'Unknown'),
            'applied_at': now_ts,
            'expires_at': expires_at,
            'stats': {'aim': -1},
        }

        replaced = False
        for idx, effect in enumerate(list(effects)):
            if not isinstance(effect, dict):
                continue
            effect_name = str(effect.get('name') or effect.get('id') or '').strip().lower()
            if effect_name == 'garand thumb' or effect_name == 'garand_thumb':
                effects[idx] = effect_payload
                replaced = True
                break
        if not replaced:
            effects.append(effect_payload)

        garand_state['garand_thumb_received'] = True

        return {'roll': roll, 'applied': True, 'expires_at': expires_at}

    def _get_local_central_tz(self):
        try:
            from zoneinfo import ZoneInfo
            return ZoneInfo("America/Chicago")
        except Exception:
            try:
                import pytz
                return pytz.timezone("America/Chicago")
            except Exception:
                try:
                    return timezone(timedelta(hours = -6))
                except Exception:
                    return None
    def _sync_equipment_slots(self, data):

        try:
            if not isinstance(data, dict):
                return data

            equip = data.setdefault('equipment', {})or {}
            empty_equip = emptysave.get('equipment', {})if isinstance(emptysave, dict)else {}

            hands = data.setdefault('hands', {})or {}
            hands_items = hands.setdefault('items', [])if isinstance(hands, dict)else[]

            extra_slots =[k for k in list(equip.keys())if k not in empty_equip]
            for slot in extra_slots:
                val = equip.pop(slot, None)
                if not val:
                    continue
                if isinstance(val, dict):
                    hands_items.append(val)
                elif isinstance(val, list):
                    for it in val:
                        if isinstance(it, dict):
                            hands_items.append(it)
                        else:
                            hands_items.append({'name':str(it)})
                else:
                    hands_items.append({'name':str(val)})

            for slot in empty_equip.keys():
                if slot not in equip:
                    equip[slot]= None

            new_equip = {}
            for slot in empty_equip.keys():
                new_equip[slot]= equip.get(slot)
            data['equipment']= new_equip

            return data
        except Exception:
            logging.exception('Error while syncing equipment slots')
            return data
