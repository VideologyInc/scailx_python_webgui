#!/usr/bin/env python3

"""

File:   zoomblock_settings.py

2026.0612.  Created to call lvds set_res.py and get_res.py to set / get resolution + fps of a zoomblock camera.

By:			jye@videologyinc.com

"""

from contextlib import redirect_stdout
import io

import argparse
import glob
import subprocess
import json

from vdlg_lvds.serial import LvdsSerial
from vdlg_lvds.get_res import get_resolution
from vdlg_lvds.set_res import detect_camera_brand, set_resolution

from vdlg_lvds.detect_cameras_live import detect_camera_type


# Check whether there is lvds in /dev/links and get current resolution.
def zoomblock_get_resolution():
    lvds_devs = glob.glob("/dev/links/lvds*")
    default_lvds = lvds_devs[0] if lvds_devs else "/dev/v4l-subdev1"

    f = io.StringIO()
    with redirect_stdout(f):
        get_resolution(default_lvds)
    output_string = f.getvalue()
    return default_lvds, output_string

# Given camera device path and resolution str, set it calling set_resolution function.
def zoomblock_set_resolution(device, resolution):

    try:
        f = io.StringIO()
        with redirect_stdout(f):
            serial_device = LvdsSerial(device)
            brand = detect_camera_brand(serial_device)
            set_resolution(serial_device, resolution, brand)
    except:
        # Maybe wrong format string
        return "", ""

    # check and return real current resolution
    return zoomblock_get_resolution()

# Example Usage
if __name__ == "__main__":
    """
    zoomblock_settings.py main() function.

    With user input argument of camera device path, and setting string, this program calls visca get_res and set_res to set correct resolution + fps.

    """

    parser = argparse.ArgumentParser(
        description="ZoomBlock camera set / get setting",
        prog="zoomblock_settings",
    )
    parser.add_argument(
        "-d", "--device", type=str, default="/dev/video0", help="camera device path"
    )

    parser.add_argument(
        "-r",
        "--resolution",
        type=str,
        default="",
        help="Resolution and fps to set. String format is 1080p60 or 720p25 etc.",
    )

    parser.add_argument(
        "-i", "--input", type=str, default="", help="Input json file with camera setting to set."
    )
    parser.add_argument(
        "-o", "--output", type=str, default="", help="Output json file with current valid camera setting."
    )

    args = parser.parse_args()

    camera_name, tree_name = detect_camera_type(args.device)
    if camera_name != "zoomblock":
        print(f"{args.device} is not a zoomblock camera.")
        exit(1)

    lvds_device, current = zoomblock_get_resolution()
    print("Current resolution and framerate is:", current)

    if args.resolution != "":
        lvds_device, new_resolution = zoomblock_set_resolution(lvds_device, args.resolution)
        if new_resolution !="":
            print("New resolution and framerate is:", new_resolution)
        else:
            print(f"{args.resolution} is not supported.")