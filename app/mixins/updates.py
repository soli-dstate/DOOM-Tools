"""UpdatesMixin — App methods for the "updates" feature area."""
from app.foundation import *


class UpdatesMixin:
    def _start_title_easter_egg(self, label):
        try:
            if getattr(self, '_title_easter_active', False):
                return
            self._title_easter_active = True

            try:
                orig_color = label.cget('text_color')
            except Exception:
                orig_color = None

            try:
                sound_path = os.path.join('sounds', 'firearms', 'universal', 'largestgunintheworld.ogg')
                threading.Thread(target = lambda:self._safe_sound_play('', sound_path, block = False), daemon = True).start()
            except Exception:
                logging.exception('Failed to start easter egg sound')

            colors =['red', 'orange', 'yellow', 'green', 'cyan', 'blue', 'magenta']
            interval = 120
            duration_ms = 8000
            steps = max(1, duration_ms //interval)

            def _cycle(i = 0, remaining = steps):
                try:
                    if remaining <=0:
                        try:
                            if orig_color is not None:
                                label.configure(text_color = orig_color)
                            else:
                                label.configure(text_color = None)
                        except Exception:
                            pass
                        self._title_easter_active = False
                        return
                    color = colors[i %len(colors)]
                    try:
                        label.configure(text_color = color)
                    except Exception:
                        try:
                            label.configure(fg_color = color)
                        except Exception:
                            pass
                    self.root.after(interval, lambda:_cycle(i +1, remaining -1))
                except Exception:
                    self._title_easter_active = False

            self.root.after(0, lambda:_cycle(0, steps))
        except Exception:
            logging.exception('Easter egg failed')

    def _parse_version(self, v:str):
        try:
            parts = re.findall(r"\d+", str(v))
            return tuple(int(p)for p in parts)
        except Exception:
            return()

    def _check_remote_version(self, label):
        try:
            api_url = 'https://api.github.com/repos/soli-dstate/DOOM-Tools/releases/latest'
            try:
                resp = requests.get(api_url, timeout = 5, headers = {'Accept':'application/vnd.github+json'})
                if resp.status_code !=200:
                    return
                data = resp.json()
            except Exception:
                return

            tag = data.get('tag_name', '')
            if not tag:
                return
            remote_ver = tag.lstrip('vV')
            local_ver = version

            lp = self._parse_version(local_ver)
            rp = self._parse_version(remote_ver)

            def _pad(a, b):
                la = list(a)
                lb = list(b)
                L = max(len(la), len(lb))
                while len(la)<L:
                    la.append(0)
                while len(lb)<L:
                    lb.append(0)
                return tuple(la), tuple(lb)

            lp, rp = _pad(lp, rp)

            if lp >rp:
                try:
                    label.configure(text = f"Version: {local_ver}[PRE-RELEASE]")
                    try:
                        label.configure(text_color = 'cyan')
                    except Exception:
                        pass
                except Exception:
                    pass
                try:
                    logging.warning("Running pre-release version, do not report any issues to GitHub")
                except Exception:
                    pass
                try:
                    self._update_available = False
                except Exception:
                    pass
            elif lp <rp:
                try:
                    label.configure(text = f"Version: {local_ver}[UPDATE AVAILABLE]")
                    try:
                        label.configure(text_color = 'red')
                    except Exception:
                        pass
                except Exception:
                    pass
                try:
                    logging.warning("A newer version of DOOM Tools is available.Please visit the GitHub page to download the latest version.")
                except Exception:
                    pass
                try:
                    self._update_available = True
                except Exception:
                    pass

                try:
                    self._start_version_flash(label)
                except Exception:
                    pass
            else:
                try:
                    self._update_available = False
                except Exception:
                    pass
        except Exception:
            logging.exception('Remote version check failed')

    def _start_version_flash(self, label):
        try:
            if getattr(self, '_version_flash_active', False):
                return
            self._version_flash_active = True
            try:
                orig = label.cget('text_color')
            except Exception:
                orig = None

            def _step():
                try:
                    if not getattr(self, '_version_flash_active', False):
                        try:
                            if orig is not None:
                                label.configure(text_color = orig)
                            else:
                                label.configure(text_color = None)
                        except Exception:
                            pass
                        return
                    try:
                        cur = label.cget('text_color')
                    except Exception:
                        cur = None
                    try:
                        next_color = 'red'if cur !='red'else(orig or 'black')
                        label.configure(text_color = next_color)
                    except Exception:
                        pass
                    self.root.after(400, _step)
                except Exception:
                    self._version_flash_active = False

            self.root.after(0, _step)
        except Exception:
            logging.exception('Failed to start version flash')
