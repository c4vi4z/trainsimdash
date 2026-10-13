#!/usr/bin/env python

import sys
import time
from pathlib import Path

import requests

# fuck sorting bro who designed this

path = Path(input("Insert path to API Key (including the .txt): ").strip().strip('"')).expanduser()
key = path.read_text().strip()

# make sure this is actually an api key
if len(key) == 44:
    print("good key, thank", key)
else:
    sys.exit("exit time, wrong stuff")

# now define header and test if connection is 200, if not print line
headers = {"DTGCommKey": key}
base = "http://localhost:31270"

r = requests.get(f"{base}/list", headers=headers, timeout=5)
if r.status_code == 200: print("it worky")
else: sys.exit("client not up")

# ok right here in this part we define which data we want (i.e. what endpoints we're gonna track per tick)
# and use a sleep timer for like once every half second so it doesnt lag too bad

# check throttle/brake value.
fast = {
    "speed": "CurrentDrivableActor.Function.HUD_GetSpeed",
    "acceleration": "CurrentDrivableActor.Function.HUD_GetAcceleration",
    "driverdata": "DriverAid.Data",
 }

slow = {
     "vehicleinfo": "CurrentDrivableActor.Function.IS_GetVehicleInfo",
 }

def get(path):
    r = requests.get(f"{base}/get/{path}", headers=headers, timeout=2)
    return r.text

tick = 0
while True:
    for name, path in fast.items():
        print(name, get (path))

        if tick % 40 == 0:
            for name, path in slow.items():
               print(name, get(path))


    tick += 1
    time.sleep(0.5)
#acceleration

# check AWS or other warning stuff here, it is indeed exposed.

# print warning line if aws shits itself

# check incline, and print

# check upcoming signals

# we want some stuff to be on a different interval, so ping it every 20 seconds instead of 0.5 to save performance. for example: ignition, loco

# some stuff should be checked on stop, so when speed = 0, check next station every 0.5 seconds.

# check weather
