#!/usr/bin/env python

import requests
from pathlib import Path

path = Path(input("Insert path to API Key (including the .txt): ").strip().strip('"')).expanduser()
key = path.read_text().strip()

print(key)
