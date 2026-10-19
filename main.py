#!/usr/bin/env python

import json
import sys
import time
from pathlib import Path

import requests

BASE = "http://localhost:31270"
CONFIG_FILE = Path(__file__).parent / "config.json"
HEADERS = {}  # dont worry this gets filled in main loop

UNITS = {
    "kmh": ("km/h", 3.6, "{:3.0f}"),
    "mph": ("mph", 2.23694, "{:3.0f}"),
    "ms": ("m/s", 1.0, "{:4.1f}"),
}

FULLPERCENT = ["111"]

SLOW = 20 # this is in loops, not seconds (thanks copilot)

def load_config():
    config = {}
    if CONFIG_FILE.exists():
        config = json.loads(CONFIG_FILE.read_text())

    if "key_path" not in config:
        config["key_path"] = input("path to api key (including the .txt): ").strip().strip('"')

    config.setdefault("units", "kmh")  # change to "mph" or "ms" in config.json (which should be in the parent directory, if not FUCK YOU)
    CONFIG_FILE.write_text(json.dumps(config, indent=2))
    return config


def read_key(config):
    path = Path(config["key_path"]).expanduser()
    if not path.exists():
        sys.exit(f"key file not found: {path}")

    key = path.read_text().strip()
    if len(key) != 44:
        sys.exit("exit time :D")
    return key


def get(endpoint):
    r = requests.get(f"{BASE}/get/{endpoint}", headers=HEADERS, timeout=2)

    if r.status_code == 403:
        sys.exit("api key wrong")

    try:
        data = r.json()
    except ValueError:
        return None

    return data.get("Values")


def pick(data, *keys):
    for key in keys:
        if not isinstance(data, dict) or key not in data:
            return None
        data = data[key]
    return data


def scale(value, factor):
    if value is None:
        return None
    return value * factor


def clean_time(text):
    if not isinstance(text, str):
        return None
    return text.lstrip("+")[:5]


def get_loco_name():
    obj = get("CurrentDrivableActor.ObjectClass")
    if isinstance(obj, dict) and obj:
        return str(next(iter(obj.values())))

    # older way lowkey as fallback because i like this code and totally not because i had to bring it back from the undead because the example above sucks
    info = get("CurrentDrivableActor.Function.IS_GetVehicleInfo")
    for key, value in (pick(info, "Output") or {}).items():
        if key.startswith("class_"):
            return str(value)

    return "unknown"

def read_throttle(loco):
    handle = get("CurrentDrivableActor.Function.HUD_GetPowerHandle")
    power = pick(handle, "Power")
    if power is None:
        return None

    if pick(handle, "IsNegative"):
        power = -power

    if any(word in loco for word in FULLPERCENT):
        return round(power)
    return round(power) * 10


def read_emergency(brake_pos):
    data = get("CurrentDrivableActor.Function.GetEmergencyBrakeState")

    if data is not None:
        return bool(pick(data, "bEmergencyBrakeState") or pick(data, "ReturnValue"))

    if brake_pos is not None:
        return brake_pos >= 1
    return None


def read_traction_locked():
    data = get("CurrentDrivableActor.Function.IS_GetTractionLock")
    if data is None:
        data = get("CurrentDrivableActor.Property.TractionLocked")

    locked = pick(data, "IsTractionLocked")
    if locked is None:
        locked = pick(data, "Value")
    return locked


def read_state(loco):
    speed = pick(get("CurrentDrivableActor.Function.HUD_GetSpeed"), "Speed (ms)")
    accel = pick(get("CurrentDrivableActor.Function.HUD_GetAcceleration"), "Acceleration (ms2)")

    aid = get("DriverAid.Data")
    limit = pick(aid, "speedLimit", "value")
    if limit is not None and limit > 1000:
        limit = None

    signal = pick(aid, "signalAspectClass")
    signal_dist = scale(pick(aid, "distanceToSignal"), 1 / 100)
    if pick(aid, "signalSeen") is False:
        signal = None
        signal_dist = None

    brake_pos = pick(get("CurrentDrivableActor.Function.HUD_GetTrainBrakeHandle"), "HandlePosition")

    speeding = None
    if speed is not None and limit is not None:
        speeding = speed >= limit

    return {
        "loco": loco,
        "speed_ms": speed,
        "accel": accel,
        "limit_ms": limit,
        "speeding": speeding,
        "gradient": pick(aid, "gradient"),
        "signal": signal,
        "signal_dist_m": signal_dist,
        "throttle_pct": read_throttle(loco),
        "brake_pct": None if brake_pos is None else round(brake_pos * 100),
        "emergency": read_emergency(brake_pos),
        "traction_locked": read_traction_locked(),
    }


def read_slow_state():
    weather_data = get("WeatherManager.Data")
    time_data = get("TimeOfDay.Data")

    iso = pick(time_data, "LocalTimeISO8601")
    clock = None
    if isinstance(iso, str) and "T" in iso:
        clock = iso.split("T")[1][:5]

    return {
        "weather": {
            "temp_c": pick(weather_data, "Temperature"),
            "cloud": pick(weather_data, "Cloudiness"),
            "precip": pick(weather_data, "Precipitation"),
            "fog": pick(weather_data, "FogDensity"),
        },
        "tod": {
            "time": clock,
            "sunrise": clean_time(pick(time_data, "SunriseTime")),
            "sunset": clean_time(pick(time_data, "SunsetTime")),
        },
    }

def fmt(value, template):
    if value is None:
        return "--"
    return template.format(value)


def show(state, unit):
    label, factor, limit_template = UNITS[unit]
    speed = scale(state["speed_ms"], factor)
    limit = scale(state["limit_ms"], factor)

    accel = state["accel"]
    if accel is None:
        motion = ""
    elif accel > 0.05:
        motion = "ACCEL"
    elif accel < -0.05:
        motion = "DECEL"
    else:
        motion = "COAST"

    flags = []
    if state["speeding"]:
        flags.append("SPEEDING")
    if state["emergency"]:
        flags.append("EMERGENCY")
    if state["traction_locked"] and motion != "DECEL":
        flags.append("LOCK")

    print(
        f"{fmt(speed, '{:5.1f}')} {label}  limit {fmt(limit, limit_template)}  {motion:5}  "
        f"handle {fmt(state['throttle_pct'], '{:+4d}')}%  "
        f"signal {state['signal'] or '--'} in {fmt(state['signal_dist_m'], '{:5.0f}')} m  "
        + " ".join(flags)
    )


def show_slow(slow):
    weather = slow["weather"]
    tod = slow["tod"]
    print(
        f"   time {tod['time'] or '--'}  sunrise {tod['sunrise'] or '--'}  sunset {tod['sunset'] or '--'}  "
        f"temp {fmt(weather['temp_c'], '{:.1f}')} C  "
        f"cloud {fmt(scale(weather['cloud'], 100), '{:.0f}')}%  "
        f"rain {fmt(scale(weather['precip'], 100), '{:.0f}')}%"
    )

def main():
    config = load_config()

    unit = config["units"]
    if unit not in UNITS:
        sys.exit()

    HEADERS["DTGCommKey"] = read_key(config)
    print("good key, thank")

    try:
        r = requests.get(f"{BASE}/list", headers=HEADERS, timeout=5)
    except requests.RequestException:
        sys.exit("no api key?????????")
    if r.status_code == 403:
        sys.exit("game no likey api key")
    if r.status_code == 200:
        print("it worky")
    else:
        sys.exit("client not up")

    loco = None
    tick = 0

    try:
        while True:
            try:
                if tick % SLOW == 0:
                    new_loco = get_loco_name()
                    if new_loco != loco:
                        loco = new_loco
                        print("loco:", loco)
                    show_slow(read_slow_state())

                show(read_state(loco), unit)

            except requests.RequestException:
                print("waiting...")
                tick = 0
                time.sleep(3)
                continue

            tick += 1
            time.sleep(0.5)

    except KeyboardInterrupt:
        print("bye")


if __name__ == "__main__":
    main()
