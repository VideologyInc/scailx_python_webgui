"""

pytest to test lvds B8 driver of Visca inquiries and commands serial communication timings, especially for zoom commands.

2026.0804.  Created.

By: jye@videologyinc.com

"""

from vdlg_lvds.ioctl import *
from vdlg_lvds.serial import LvdsSerial
from vdlg_lvds.set_res import detect_camera_brand

from hide_warnings import hide_warnings
from contextlib import redirect_stdout
import io
import os
import math
import time
import cv2
import statistics

import pytest

# timeout is 1 sec.
TIMEOUT = 1000


def show_keys(my_dict, message):
    print(message)
    print(*my_dict, sep=", ")


def show_dict(my_dict, message):
    print(message)
    for key, val in my_dict.items():
        print(key, ":", val)


# Test lvds serial with visca inquiry.
def test_lvds_inquiry(lvds_serial_device, visca_dicts):

    print("------------- Init LvdsSerial ----------------------------")
    brand = detect_camera_brand(lvds_serial_device)
    assert brand == "videology"

    visca_inq, visca_cmd, visca_zoom = visca_dicts
    assert visca_inq != None and visca_cmd != None and visca_zoom != None

    show_keys(visca_inq, "Visca Inquiries")
    show_dict(visca_zoom, "Visca Zoom Table")

    print("============== Do Visca Inquiry Tests ====================")
    for key, inq in visca_inq.items():
        data = bytearray.fromhex(inq)
        response_data = lvds_serial_device.transceive(data, start_wait_ms=TIMEOUT)
        response_hex = response_data.hex()
        print(key, " = ", inq, " => ", response_hex)


# Test lvds serial with visca commands.
def test_lvds_commands(lvds_serial_device, visca_dicts):

    print("------------- Init LvdsSerial ----------------------------")

    brand = detect_camera_brand(lvds_serial_device)
    assert brand == "videology"

    visca_inq, visca_cmd, visca_zoom = visca_dicts
    assert visca_inq != None and visca_cmd != None and visca_zoom != None

    show_keys(visca_cmd, "Visca Commands")
    show_dict(visca_zoom, "Visca Zoom Table")

    print("============== Do Visca Command Tests ====================")
    for key, cmd in visca_cmd.items():
        # Skip zoom command tests now => will do in a separate func.
        if "zoom" in key:
            continue

        data = bytearray.fromhex(cmd)
        response_data = lvds_serial_device.transceive(data, start_wait_ms=TIMEOUT)
        response_hex = response_data.hex()
        print(key, " = ", cmd, " => ", response_hex)
