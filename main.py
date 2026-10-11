import requests
from pathlib import Path

path = Path(input("pls input path to commapikey thingymabob: ").strip().strip('"')).expanduser()
key = path.read_text().strip()
