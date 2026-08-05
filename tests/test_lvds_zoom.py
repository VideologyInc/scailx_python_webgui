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

# timeout in seconds using float
TIMEOUT_SEC = 5.0

# enum to do benchmark test of 3 types
VISCA_INQ = 1
VISCA_CMD = 2

# Utility functions
def show_keys(my_dict, message):
    print(message)
    print(*my_dict, sep=", ")


def show_dict(my_dict, message):
    print(message)
    for key, val in my_dict.items():
        print(key, ":", val)

# Count 3 types of items in dicts.
def count_items(my_dicts):
    visca_inq, visca_cmd, visca_zoom = my_dicts

    # Exclude 2 ir commands for now ;-)
    num_inq = len(visca_inq)
    num_cmd = sum(1 for key in visca_cmd if ("zoom" not in key) and ("ir_on" != key) and ("ir_off" != key))
    num_zoom = sum(1 for key in visca_cmd if "zoom" in key)

    return num_inq, num_cmd, num_zoom


# Zoom direct by scale to match zoom table.
# Need to replace 0p0q0r0s using strings from zoom table
# zoompqrs = 810104470p0q0r0sFF.
# scale is 1,2,3,...,10.
# zoom_pos_inq = zoom_pos inquiry string
# check_pos = True to use zoom_pos inquiry to check current position util it matches the set position.
# check_pos = False to return immediately.
def visca_zoom_scale(lvds_serial_device, zoom_pqrs, scale, zoom_table, zoom_pos_inq, check_pos = False):
    zoom_pos = zoom_table[str(scale)]
    zoom_8char = "0" + zoom_pos[0] + "0" + zoom_pos[1] + "0" + zoom_pos[2] + "0" + zoom_pos[3]
    n = len("81010447")
    zoom_cmd = zoom_pqrs[0:n] + zoom_8char + "FF"

    data = bytearray.fromhex(zoom_cmd)
    response_data = lvds_serial_device.transceive(data, start_wait_ms=TIMEOUT)
    response_hex = response_data.hex()

    print("scale = ", scale, ": ", zoom_cmd, " => ", response_hex)

    if not check_pos:
        return 0

    # Call zoom_pos
    nchecks = 0
    start_time = time.monotonic()
    while time.monotonic() < start_time + TIMEOUT_SEC:
        data = bytearray.fromhex(zoom_pos_inq)
        response_data = lvds_serial_device.transceive(data, start_wait_ms=TIMEOUT)
        response_hex = response_data.hex()

        nchecks +=1
        # should be in format y0500p0q0r0sFF
        if len(response_hex) == len("y0500p0q0r0sFF"):
            current_8char = response_hex[4:12]
            # print(current_8char)
            # Current position string matches input cmd string. => Done.
            if current_8char.casefold() == zoom_8char.casefold():
                return nchecks
        # time.sleep(0.05)

#######################################################################################

# speed test function called by benchmark.
# method = VISCA_INQ or VISCA_CMD
def lvds_visca(lvds_serial_device, visca_dicts, method = VISCA_INQ):
    visca_inq, visca_cmd, visca_zoom = visca_dicts

    if method == VISCA_INQ:
        for key, inq in visca_inq.items():
            data = bytearray.fromhex(inq)
            response_data = lvds_serial_device.transceive(data, start_wait_ms=TIMEOUT)
            response_hex = response_data.hex()
    elif method == VISCA_CMD:
        for key, cmd in visca_cmd.items():
            # Skip 2 ir commands for now.
            # Skip zoom command tests now => will do in a separate func.
            if ("zoom" in key) or ("ir_on" == key) or ("ir_off" == key):
                continue

            data = bytearray.fromhex(cmd)
            response_data = lvds_serial_device.transceive(data, start_wait_ms=TIMEOUT)
            response_hex = response_data.hex()



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


# Use benchmark to test serial communication time.
def test_visca_inquiry_time(benchmark, lvds_serial_device, visca_dicts):
    num_inq, num_cmd, num_zoom = count_items(visca_dicts)
    print("Number of Visca Inquiries = ", num_inq)
    benchmark.pedantic(
        lvds_visca, args=(lvds_serial_device, visca_dicts, VISCA_INQ), iterations=10, rounds=10
    )

def test_visca_commands_time(benchmark, lvds_serial_device, visca_dicts):
    num_inq, num_cmd, num_zoom = count_items(visca_dicts)
    print("Number of Visca Commands (not Zoom related) = ", num_cmd)
    benchmark.pedantic(
        lvds_visca, args=(lvds_serial_device, visca_dicts, VISCA_CMD), iterations=10, rounds=10
    )

###################################################################
# Zoom related tests

def test_visca_zoom_direct(lvds_serial_device, visca_dicts):
    visca_inq, visca_cmd, visca_zoom = visca_dicts

    zoom_pqrs = visca_cmd["zoom_direct"]
    zoom_pos_inq = visca_inq["zoom_pos"]

    # Nocheck tests
    for scale in range(1,11):
        start = time.monotonic()
        visca_zoom_scale(lvds_serial_device, zoom_pqrs, scale, visca_zoom, zoom_pos_inq, False)
        end = time.monotonic()
        # The resulting unit here is strictly in seconds
        elapsed_ms = (end - start)*1000 
        print(f"Scale {scale}, elapsed time = {elapsed_ms:.2f} ms \n")

    # Check to verify zoom position tests.
    # Set zoom from scale = 1, .., 10.
    for scale in range(1,11):
        start = time.monotonic()
        nchecks = visca_zoom_scale(lvds_serial_device, zoom_pqrs, scale, visca_zoom, zoom_pos_inq, True)
        end = time.monotonic()
        # The resulting unit here is strictly in seconds
        elapsed_ms = (end - start)*1000
        # total inq + cmd = Number of checks inq + 1 (set zoom direction)
        ave_ms = elapsed_ms / (nchecks + 1)
        print(f"Scale {scale}, elapsed time = {elapsed_ms:.2f} ms, checks = {nchecks}, average time = {ave_ms:.2f} \n")
    # Reset to zoom 1
    # visca_zoom_scale(lvds_serial_device, zoom_pqrs, 1, visca_zoom)
