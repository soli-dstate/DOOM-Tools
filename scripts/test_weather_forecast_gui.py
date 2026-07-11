#!/usr/bin/env python3
"""Self-check for the noon-boundary day lookup in weather_forecast_gui.py."""

from datetime import datetime

from weather_forecast_gui import CST, _hour_weather

FORECAST = {
    "2026-06-26": {"weather": "rain", "wind_severity": 1, "temperature_f": 60.0,
                   "hourly": {"23": {"weather": "thunderstorm", "wind_severity": 2, "temperature_f": 61.0}}},
    "2026-06-27": {"weather": "clear", "wind_severity": 0, "temperature_f": 70.0,
                   "hourly": {"11": {"weather": "cloudy", "wind_severity": 1, "temperature_f": 65.0},
                              "12": {"weather": "rain", "wind_severity": 2, "temperature_f": 68.0}}},
    "default": {"weather": "clear", "wind_severity": 0, "temperature_f": 70.0},
}

# 23:00 on the 26th belongs to the 26th's hourly table.
assert _hour_weather(FORECAST, CST.localize(datetime(2026, 6, 26, 23))) == ("thunderstorm", 2, 61.0)
# 11:00 on the 27th is before noon, so it still reads from the 26th's day entry (no hourly match -> day default).
assert _hour_weather(FORECAST, CST.localize(datetime(2026, 6, 27, 11))) == ("rain", 1, 60.0)
# 12:00 on the 27th crosses the noon boundary onto the 27th's own data.
assert _hour_weather(FORECAST, CST.localize(datetime(2026, 6, 27, 12))) == ("rain", 2, 68.0)
# Dates outside the forecast fall back to "default".
assert _hour_weather(FORECAST, CST.localize(datetime(2026, 7, 15, 15))) == ("clear", 0, 70.0)

print("ok")
