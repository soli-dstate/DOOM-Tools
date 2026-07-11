import ctypes
import json
import os
import sys
from datetime import datetime, timedelta

import customtkinter
import pytz
import requests

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONTS_DIR = os.path.join(REPO_ROOT, "fonts")
CST = pytz.timezone("US/Central")

REMOTE_WEATHER_URL = "https://raw.githubusercontent.com/soli-dstate/DOOM-Tools/master/remotedata/weather.json"
DEFAULT_FORECAST = {"default": {"weather": "clear", "wind_severity": 0, "temperature_f": 70.0}}


def _cache_path():
    # Next to the built exe (persistent) when frozen, next to this script otherwise --
    # never the PyInstaller onefile temp extraction dir, which is wiped on exit.
    base = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, "weather_cache.json")


def _load_forecast():
    """Pull the live weather.json from GitHub, same as the in-app Weather Editor; fall back to a local cache, then a clear-weather default."""
    try:
        resp = requests.get(REMOTE_WEATHER_URL, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            try:
                with open(_cache_path(), "w", encoding="utf-8") as f:
                    json.dump(data, f)
            except OSError:
                pass
            return data.get("forecast", DEFAULT_FORECAST)
    except Exception:
        pass
    try:
        with open(_cache_path(), "r", encoding="utf-8") as f:
            return json.load(f).get("forecast", DEFAULT_FORECAST)
    except Exception:
        return DEFAULT_FORECAST

WEATHER_LABELS = {
    "clear": "Clear", "sun_and_cloud": "Partly Cloudy", "cloudy": "Cloudy",
    "rain": "Rain", "hard_rain": "Hard Rain", "thunderstorm": "Thunderstorm",
    "thunder_hard_rain": "Severe Thunderstorm", "thunder": "Thunder",
    "snowstorm": "Snowstorm", "thundersnow": "Thundersnow",
}

WEATHER_COLORS = {
    "clear": "#3FB950", "sun_and_cloud": "#9CA3AF", "cloudy": "#9CA3AF",
    "rain": "#58A6FF", "hard_rain": "#58A6FF",
    "thunderstorm": "#D29922", "thunder_hard_rain": "#F85149", "thunder": "#D29922",
    "snowstorm": "#E6E6E6", "thundersnow": "#E6E6E6",
}

WEATHER_ICON_CODES = {
    "clear": "1", "sun_and_cloud": "9", "cloudy": "2",
    "rain": "3", "hard_rain": "4",
    "thunderstorm": "6", "thunder_hard_rain": "7", "thunder": "8",
    "snowstorm": "5", "thundersnow": "6",
}

GHOST_COLOR = "#4F6338"
LIVE_COLOR = "#C7F089"
WATCH_BG = "#313B21"

def _register_dseg_fonts():
    """Best-effort, this-process-only registration of the bundled DSEG fonts.

    DOOM-Tools' launcher normally installs these permanently for the Windows
    user account, so this is usually a no-op; it just makes the watch render
    correctly on a fresh checkout too. Silently does nothing off Windows.
    """
    if not hasattr(ctypes, "windll"):
        return
    FR_PRIVATE = 0x10
    for fname in ("DSEG7Modern-Regular.ttf", "DSEGWeather.ttf"):
        fp = os.path.join(FONTS_DIR, fname)
        if os.path.exists(fp):
            try:
                ctypes.windll.gdi32.AddFontResourceExW(fp, FR_PRIVATE, 0)
            except Exception:
                pass


def _hour_weather(forecast, cst_dt):
    """Look up (weather, wind_severity, temperature_f) for a CST hour."""
    if cst_dt.hour < 12:
        effective_date = (cst_dt - timedelta(days=1)).strftime("%Y-%m-%d")
    else:
        effective_date = cst_dt.strftime("%Y-%m-%d")
    day = forecast.get(effective_date) or forecast.get("default") or {}
    hourly = day.get("hourly") if isinstance(day, dict) else None
    hour = hourly.get(f"{cst_dt.hour:02d}") if isinstance(hourly, dict) else None
    merged = {**day, **hour} if hour else day
    return merged.get("weather", "clear"), int(merged.get("wind_severity", 0)), float(merged.get("temperature_f", 70.0))


def _watch_temp_text(temp_f):
    temp_fi = int(round(temp_f))
    return f"{temp_fi:03d}°F" if temp_fi >= 0 else f"-{abs(temp_fi):02d}°F"


class WeatherApp(customtkinter.CTk):
    def __init__(self):
        super().__init__()
        self.title("DOOM-Tools Weather Forecast")
        self.geometry("560x860")
        customtkinter.set_appearance_mode("dark")
        _register_dseg_fonts()

        self.use_24h = customtkinter.BooleanVar(value=True)
        self._forecast = {}
        self._tick_after_id = None

        top_row = customtkinter.CTkFrame(self, fg_color="transparent")
        top_row.pack(fill="x", padx=10, pady=(10, 4))
        customtkinter.CTkButton(top_row, text="Refresh", width=90, command=self._reload).pack(side="right")
        self.toggle_btn = customtkinter.CTkButton(top_row, text="24H", width=58, command=self._toggle_24h)
        self.toggle_btn.pack(side="right", padx=(0, 6))

        self._build_watch_panel()

        self.current_label = customtkinter.CTkLabel(self, text="", font=customtkinter.CTkFont(size=20, weight="bold"))
        self.current_label.pack(pady=(8, 2))
        self.current_sub_label = customtkinter.CTkLabel(self, text="", text_color="#9CA3AF")
        self.current_sub_label.pack(pady=(0, 8))

        self.list_frame = customtkinter.CTkScrollableFrame(self, fg_color="transparent")
        self.list_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        self._reload()
        self._tick_watch()

    def _build_watch_panel(self):
        watch_frame = customtkinter.CTkFrame(self, fg_color="#2E3821")
        watch_frame.pack(fill="x", padx=10, pady=(0, 4))
        info_row = customtkinter.CTkFrame(watch_frame, fg_color=WATCH_BG)
        info_row.pack(padx=10, pady=10)

        row_h = 50

        time_stack = customtkinter.CTkFrame(info_row, fg_color="transparent", width=170, height=row_h)
        time_stack.pack(side="left", padx=(8, 4), pady=6)
        time_stack.pack_propagate(False)
        self.time_canvas = customtkinter.CTkCanvas(time_stack, width=170, height=row_h, bg=WATCH_BG, highlightthickness=0)
        self.time_canvas.pack(fill="both", expand=True)
        cy = row_h // 2
        self.time_ghost_item = self.time_canvas.create_text(166, cy, text="88:88:88", fill=GHOST_COLOR,
                                                              font=("DSEG7 Modern-Regular", 22), anchor="e")
        self.time_live_item = self.time_canvas.create_text(166, cy, text="00:00:00", fill=LIVE_COLOR,
                                                             font=("DSEG7 Modern-Regular", 22), anchor="e")

        ampm_frame = customtkinter.CTkFrame(info_row, fg_color="transparent", width=30, height=row_h)
        ampm_frame.pack(side="left", padx=(0, 4), pady=(1, 0))
        ampm_frame.pack_propagate(False)
        self.pm_label = customtkinter.CTkLabel(ampm_frame, text="PM", font=customtkinter.CTkFont(size=10), text_color=GHOST_COLOR)
        self.pm_label.place(relx=0.5, rely=0.36, anchor="center")
        self.am_label = customtkinter.CTkLabel(ampm_frame, text="AM", font=customtkinter.CTkFont(size=10), text_color=GHOST_COLOR)
        self.am_label.place(relx=0.5, rely=0.77, anchor="center")

        weather_stack = customtkinter.CTkFrame(info_row, fg_color="transparent", width=60, height=row_h)
        weather_stack.pack(side="left", padx=(2, 6), pady=6)
        weather_stack.pack_propagate(False)
        self.weather_canvas = customtkinter.CTkCanvas(weather_stack, width=60, height=row_h, bg=WATCH_BG, highlightthickness=0)
        self.weather_canvas.pack(fill="both", expand=True)
        self.weather_ghost_item = self.weather_canvas.create_text(30, cy, text="0", fill=GHOST_COLOR,
                                                                    font=("DSEG Weather", 28), anchor="center")
        self.weather_live_item = self.weather_canvas.create_text(30, cy, text="1", fill=LIVE_COLOR,
                                                                   font=("DSEG Weather", 28), anchor="center")

        temp_stack = customtkinter.CTkFrame(info_row, fg_color="transparent", width=100, height=row_h)
        temp_stack.pack(side="left", padx=(0, 8), pady=6)
        temp_stack.pack_propagate(False)
        self.temp_canvas = customtkinter.CTkCanvas(temp_stack, width=100, height=row_h, bg=WATCH_BG, highlightthickness=0)
        self.temp_canvas.pack(fill="both", expand=True)
        self.temp_ghost_item = self.temp_canvas.create_text(96, cy, text="8888", fill=GHOST_COLOR,
                                                              font=("DSEG7 Modern-Regular", 22), anchor="e")
        self.temp_live_item = self.temp_canvas.create_text(96, cy, text="070°F", fill=LIVE_COLOR,
                                                             font=("DSEG7 Modern-Regular", 22), anchor="e")

    def _tick_watch(self):
        now_local = datetime.now()
        use_24h = self.use_24h.get()
        self.time_canvas.itemconfigure(self.time_live_item, text=self._format_clock(now_local, seconds=True))
        if use_24h:
            self.am_label.configure(text_color=GHOST_COLOR)
            self.pm_label.configure(text_color=GHOST_COLOR)
        else:
            is_pm = now_local.hour >= 12
            self.am_label.configure(text_color=GHOST_COLOR if is_pm else LIVE_COLOR)
            self.pm_label.configure(text_color=LIVE_COLOR if is_pm else GHOST_COLOR)

        now_cst = datetime.now(CST)
        w, _sev, temp = _hour_weather(self._forecast, now_cst) if self._forecast else ("clear", 0, 70.0)
        self.weather_canvas.itemconfigure(self.weather_live_item, text=WEATHER_ICON_CODES.get(w, ":"))
        self.temp_canvas.itemconfigure(self.temp_live_item, text=_watch_temp_text(temp))

        self._tick_after_id = self.after(1000, self._tick_watch)

    def _format_clock(self, dt, seconds=False):
        if self.use_24h.get():
            return dt.strftime("%H:%M:%S" if seconds else "%H:%M")
        return dt.strftime("%I:%M:%S" if seconds else "%I:%M")

    def _toggle_24h(self):
        self.use_24h.set(not self.use_24h.get())
        self.toggle_btn.configure(text="24H" if self.use_24h.get() else "12H")
        self._render_list()

    def _reload(self):
        self._forecast = _load_forecast()
        self._render_list()

    def _render_list(self):
        for child in self.list_frame.winfo_children():
            child.destroy()

        now_cst = datetime.now(CST).replace(minute=0, second=0, microsecond=0)

        w, sev, temp = _hour_weather(self._forecast, now_cst)
        local_now = now_cst.astimezone()
        self.current_label.configure(text=f"{WEATHER_LABELS.get(w, w)}, {temp:.0f}F", text_color=WEATHER_COLORS.get(w, "#FFFFFF"))
        self.current_sub_label.configure(text=f"Wind severity {sev} — {local_now.strftime('%Y-%m-%d')} {self._format_clock(local_now)}")

        last_day = None
        for i in range(7 * 24):
            cst_dt = now_cst + timedelta(hours=i)
            local_dt = cst_dt.astimezone()
            day = local_dt.strftime("%A, %Y-%m-%d")
            if day != last_day:
                customtkinter.CTkLabel(self.list_frame, text=day, font=customtkinter.CTkFont(size=14, weight="bold")).pack(
                    fill="x", anchor="w", pady=(10, 2))
                last_day = day

            w, sev, temp = _hour_weather(self._forecast, cst_dt)
            row = customtkinter.CTkFrame(self.list_frame, fg_color="transparent")
            row.pack(fill="x", pady=1)
            customtkinter.CTkLabel(row, text=self._format_clock(local_dt), width=60, anchor="w").pack(side="left")
            customtkinter.CTkLabel(row, text=WEATHER_LABELS.get(w, w), width=160, anchor="w", text_color=WEATHER_COLORS.get(w, "#FFFFFF")).pack(side="left")
            customtkinter.CTkLabel(row, text=f"{temp:.1f}F", width=60, anchor="w").pack(side="left")
            customtkinter.CTkLabel(row, text=f"wind {sev}", width=60, anchor="w").pack(side="left")


def main():
    WeatherApp().mainloop()


if __name__ == "__main__":
    main()