#!/usr/bin/env python3

"""

File:   detect_imx_live.py

2026.0406.  Detect one imx camera live stream on/off status using lsof.

By:			jye@videologyinc.com

"""

import argparse
import time
import subprocess
import re
import json
import glob
import copy
import math
import os
from pathlib import Path
import io
import warnings
import jc

from vdlg_lvds.detect_cameras_live import detect_camera_type

# Call lsof to detect camera stream on/off
def detect_imx(device_path):
    # Run the command
    cmd = f"lsof {device}"
    try:
        # output = subprocess.check_output(cmd, shell=True)
        # Get the raw output
        cmd_output = subprocess.check_output(['lsof'], text=True)

        # Parse into a list of dictionaries
        data = jc.parse('lsof', cmd_output)        
        print(data)
        
    except subprocess.CalledProcessError:
        print("Device not found or error running lsof")
        return []
    

def restart_go2rtc():

    try:
        result = subprocess.run(
            ["systemctl", "restart", "go2rtc.service"],
            capture_output=True,
            text=True,
            check=True,
        )
        print("Restart go2rtc: ", result.stdout)
    except Exception as e:
        print(f"Restart go2rtc failed: {e}")


# Given initial camera status dict, use infinite loopt to check camera status every few seconds.
def monitor_cameras_loop(camera_status, interval):

    nitems = len(camera_status)
    while True:
        current_camera_status = detect_cameras()
        if current_camera_status == camera_status:
            print("Camera status unchanged")
        else:
            print("Camera status changed: ", current_camera_status)
            camera_status = current_camera_status
            new_items = len(camera_status)
            if nitems != new_items:
                # Camera connection changed: restart go2rtc service.
                nitems = new_items
                restart_go2rtc()

        time.sleep(interval)


if __name__ == "__main__":

    parser = argparse.ArgumentParser(
        description="Detect imx camera stream on/off",
        prog="detect_imx_live",
    )
    parser.add_argument(
        "-d", "--device", type=str, default="/dev/video0", help="camera device path"
    )
    parser.add_argument(
        "-i",
        "--interval",
        type=int,
        default="5",
        help="Interval in seconds to check cameras",
    )

    args = parser.parse_args()

    # Get current camera status
    camera_status = detect_imx(args.device)
    print(camera_status)

    # monitor_cameras_loop(camera_status, args.interval)
