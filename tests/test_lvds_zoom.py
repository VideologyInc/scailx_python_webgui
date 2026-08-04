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
    for key, val in my_dict.items():
        print(key)


def show_dict(my_dict, message):
    print(message)
    for key, val in my_dict.items():
        print(key, ":", val)


# Test lvds serial with visca inquiry.
def test_lvds_inquiry(lvds_serial_device, visca_dicts):

    brand = detect_camera_brand(lvds_serial_device)
    assert brand == "videology"

    visca_inq, visca, cmd, visca_zoom = visca_dicts
    assert visca_inq != None and visca_cmd != None and visca_zoom != None

    show_keys(visca_inq, "Visca inquiries")
    show_dict(visca_zoom, "Visca Zoom Table")

    """
    data = bytearray.fromhex(hex_command)
    response_data = lvds_serial_device.transceive(data, start_wait_ms=TIMEOUT)
    response_hex = response_data.hex()

    print(hex_command, " => ", response_hex)
    """


# Test lvds serial with visca commands.
def test_lvds_commands(lvds_serial_device, visca_dicts):

    brand = detect_camera_brand(lvds_serial_device)
    assert brand == "videology"

    visca_inq, visca, cmd, visca_zoom = visca_dicts
    assert visca_inq != None and visca_cmd != None and visca_zoom != None

    show_keys(visca_cmd, "Visca commands")
    show_dict(visca_zoom, "Visca Zoom Table")

    """
    data = bytearray.fromhex(hex_command)
    response_data = lvds_serial_device.transceive(data, start_wait_ms=TIMEOUT)
    response_hex = response_data.hex()

    print(hex_command, " => ", response_hex)
    """
