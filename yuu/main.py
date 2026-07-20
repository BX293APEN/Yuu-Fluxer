#!/usr/bin/env python3
import os, sys
DIR_ABS_PATH = os.path.dirname(os.path.abspath(__file__))
sys.path.append(DIR_ABS_PATH)
from lib.yuu import MyClient

if __name__ == "__main__":
    MyClient(f"{DIR_ABS_PATH}", f"config/fluxer.token", f"config/config.json")