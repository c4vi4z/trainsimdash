#!/usr/bin/env python

import sys
import time
from pathlib import Path

import requests

path = Path(input("Insert path to API Key (including the .txt): ").strip().strip('"')).expanduser()
key = path.read_text().strip()

# make sure this is actually an api key
if len(key) == 44:
    print("good key, thank", key)
else:
    sys.exit("exit time, wrong stuff")

# now define header and test if connection is 200 (good), if not print line
headers = {"DTGCommKey": key}
base = "http://localhost:31270"

r = requests.get(f"{base}/list", headers=headers, timeout=5)
if r.status_code == 200: print("it worky")
else: sys.exit("client not up")

# ok right here in this part we define which data we want (i.e. what endpoints we're gonna track per tick)
# and use a sleep timer for like once every half second so it doesnt lag too bad

def get(endpoint):
    r = requests.get(f"{base}/get/{endpoint}", headers=headers, timeout=2)
    return r.json()["Values"]

# read the loco name once at the start
info = get("CurrentDrivableActor.Function.IS_GetVehicleInfo")["Output"]
for k, v in info.items():
    if k.startswith("class_"):
        print("loco:", v)

while True:
    speed = get("CurrentDrivableActor.Function.HUD_GetSpeed")["Speed (ms)"]
    accel = get("CurrentDrivableActor.Function.HUD_GetAcceleration")["Acceleration (ms2)"]
    aid = get("DriverAid.Data")
    handle = get("CurrentDrivableActor.Function.HUD_GetPowerHandle")
#    brake = get("CurrentDrivableActor.Function.HUD_GetTrainBrakeHandle")
    emergency = get("CurrentDrivableActor.Function.GetEmergencyBrakeState")
    tractionlock = get("CurrentDrivableActor.Function.IS_GetTractionLock")

    power = handle["Power"]
    if handle["IsNegative"]:
        power = -power

    throttle = round(power) * 10

    if accel > 0.05:
        state = "ACCEL"
    elif accel < -0.05:
        state = "DECEL"
    else:
        state = "COAST"

    if emergency["bEmergencyBrakeState"]:
        emergency = "EMERGENCY"
    else:
        emergency = ""

    if tractionlock["IsTractionLocked"] and state != "DECEL":
        traction = "LOCK"
    else:
        traction = ""

    limit = aid["speedLimit"]["value"]
    signal = aid["signalAspectClass"]
    signal_dist = aid["distanceToSignal"] / 100

    if speed >= limit:
        speed_warning = "SPEEDING"
    else:
        speed_warning = ""

# add brake with {brake['HandlePosition']}
    print(f"{speed * 3.6:5.1f} km/h  limit {limit * 3.6:3.0f}  {state:5}  handle {throttle:+4d}%  signal {signal} in {signal_dist:5.0f} m {speed_warning}  {emergency} {traction}")

    time.sleep(0.5)
