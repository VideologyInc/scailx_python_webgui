"""

pytest to test lvds B7 driver refactoring CoreVision pytest codes.

2026.0623.  Created.

By: jye@videologyinc.com

"""

from vdlg_lvds.ioctl import *
from vdlg_lvds.serial import LvdsSerial
from vdlg_lvds.set_res import detect_camera_brand, set_resolution
from vdlg_lvds.get_res import get_resolution
from vdlg_lvds.detect_cameras_live import detect_camera_type, MAX_CAMERA_ID

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

# fps is similar
FPS_THRESHOLD = 0.5
# fps is very close
FPS_CLOSE = 0.1

# lvds ZoomBlock cameras, we support 8 settings of resolution + fps.
zoomblock_settings_dict = {
    "720p25": (1280, 720, 25),
    "720p30": (1280, 720, 30),
    "720p50": (1280, 720, 50),
    "720p60": (1280, 720, 60),
    "1080p25": (1920, 1080, 25),
    "1080p30": (1920, 1080, 30),
    "1080p50": (1920, 1080, 50),
    "1080p60": (1920, 1080, 60),
}

# reboot hex in bytearray
REBOOT_DATA = bytearray.fromhex("8101040000FF")


# Utility function to reboot lvds and get serial info for benchmark.
def lvds_reboot_info(lvds_serial_device, test_brand_flag):
    reboot_hex = "8101040000FF"
    data = bytearray.fromhex(reboot_hex)

    with open(os.devnull, "w") as f, redirect_stdout(f):
        response_data = lvds_serial_device.transceive(data, start_wait_ms=TIMEOUT)
        if test_brand_flag:
            brand = detect_camera_brand(lvds_serial_device)


# Return 1st valid /dev/camera? path for lvds zoomblock camera.
def get_first_lvds():
    prefix = "/dev/video"
    for id in range(0, MAX_CAMERA_ID):
        camera_path = prefix + str(id)
        camera_name, devicetree_name = detect_camera_type(camera_path)
        if camera_name == "zoomblock":
            return camera_path
    return ""


# Use OpenCV to get fps and measure real fps.
@hide_warnings
def get_fps_cv_gst(w, h, fps):
    # Define your GStreamer pipeline string (ensure it ends with appsink)
    zoomblock_path = get_first_lvds()
    gst_pipeline = (
        f"v4l2src device={zoomblock_path} ! "
        f"video/x-raw, width={w}, height={h}, framerate={fps}/1, pixelformat=NV12 ! "
        "videoconvert ! video/x-raw, format=BGR ! appsink drop=1"
    )

    # Initialize video capture with GStreamer backend
    cap = cv2.VideoCapture(gst_pipeline, cv2.CAP_GSTREAMER)

    if not cap.isOpened():
        print("Error: Could not open GStreamer pipeline.")
        return 0, 0

    # Returns configured pipeline FPS (may return 0 or wrong values for raw RTSP/live feeds)
    pipeline_fps = cap.get(cv2.CAP_PROP_FPS)

    prev_time = time.time()
    fps_sum = 0
    for i in range(fps):
        ret, frame = cap.read()
        if not ret:
            break

        # Calculate current frame rate
        current_time = time.time()
        current_fps = 1 / (current_time - prev_time)
        prev_time = current_time
        fps_sum += current_fps

    cap.release()
    # cv2.destroyAllWindows()

    return pipeline_fps, fps_sum / fps


# utility function to get resolution into a tuple
@hide_warnings
def get_resolution_tuple(lvds_device_path):
    f = io.StringIO()
    with redirect_stdout(f):
        get_resolution(lvds_device_path)
    output_string = f.getvalue()
    res_list = output_string.split()
    # [0] = w, [2] = h, [4] = fps
    if len(res_list) >= 5:
        width = int(res_list[0])
        height = int(res_list[2])
        fps = float(res_list[4])
        return width, height, fps
    elif len(res_list) >= 3:
        width = int(res_list[0])
        height = int(res_list[2])
        return width, height, 0

    return 0, 0, 0


# Test basic lvds serial device connection.
def test_lvds_serial(lvds_serial_device):

    brand = detect_camera_brand(lvds_serial_device)

    assert brand == "videology"


def test_reboot_lvds(lvds_serial_device):
    response_data = lvds_serial_device.transceive(REBOOT_DATA, start_wait_ms=TIMEOUT)
    response_hex = response_data.hex()
    assert str(response_hex) == "9041ff9051ff"
    print("lvds reboot ", REBOOT_DATA.hex(), " => ", response_hex)


# Make sure reboot and serial work in pairs multiple times.
def test_reboot_multi_check(benchmark, lvds_serial_device):
    benchmark.pedantic(
        lvds_reboot_info, args=(lvds_serial_device, True), iterations=10, rounds=10
    )


def test_reboot_multi_nocheck(benchmark, lvds_serial_device):
    benchmark.pedantic(
        lvds_reboot_info, args=(lvds_serial_device, False), iterations=10, rounds=10
    )


# Test lvds serial send and receive hex data.
# 4 hex strings mean inquire: camera info, camera id, AE mode, Zoom Position.
@pytest.mark.parametrize(
    "hex_command", [("81090002FF"), ("81090422FF"), ("81090439FF"), ("81090447FF")]
)
def test_lvds_transceive(lvds_serial_device, hex_command):
    data = bytearray.fromhex(hex_command)
    response_data = lvds_serial_device.transceive(data, start_wait_ms=TIMEOUT)
    response_hex = response_data.hex()

    print(hex_command, " => ", response_hex)


# Simulate CV's init serial tests 10 times.
def test_lvds_serial_multi(lvds_serial_device):

    serial_test_count = 10
    counter = 0
    serial_failed_cnt = 0

    for i in range(serial_test_count):
        brand = detect_camera_brand(lvds_serial_device)
        if brand != "videology":
            serial_failed_cnt += 1
            time.sleep(random.random())
            counter += 1

    if serial_failed_cnt > 0:
        assert (
            False
        ), f"ERROR\tSerial test failed. Incorrect messages: {serial_failed_cnt}/{counter}"


# Test set / get resolution + fps multiple times and measure accuracy using OpenCV.
def test_lvds_resolutions(lvds_serial_device, lvds_device_path, lvds_fw_version):
    verbose = False
    # sleep 3 seconds between each pair of set / get resolution
    gap = 3

    test_cnt = 20

    brand = detect_camera_brand(lvds_serial_device)

    fpga_version = int(lvds_fw_version)
    print("lvds firmware version = ", lvds_fw_version, hex(fpga_version))

    # B7 and older version do not have support for NTSC frequencies
    if fpga_version <= 0xB7:
        test_framerates = ["25", "30", "50", "60"]
        test_gstream_framerates = ["25/1", "30/1", "50/1", "60/1"]
        check_framerates = [25, 30, 50, 60]
    else:
        test_framerates = ["25", "29", "30", "50", "59", "60"]
        test_gstream_framerates = [
            "25/1",
            "30000/1001",
            "30/1",
            "50/1",
            "60000/1001",
            "60/1",
        ]
        check_framerates = [25, 29.97, 30, 50, 59.94, 60]

    cnt_match = 0
    cnt_close = 0
    cnt_similar = 0
    cnt_diff = 0
    cnt_fail = 0

    fail_dict = {}
    for resolution_str, setting in zoomblock_settings_dict.items():
        fail_dict[resolution_str] = 0
        # if (resolution_str != "1080p30" and resolution_str != "1080p50"):
        #    continue

        fps_list_in_vs_pipe = []
        fps_list_in_vs_cv = []
        fps_list_in_vs_get = []
        for i in range(test_cnt):
            time.sleep(gap)
            if verbose:
                set_resolution(lvds_serial_device, resolution_str, brand)
            else:
                with open(os.devnull, "w") as f, redirect_stdout(f):
                    set_resolution(lvds_serial_device, resolution_str, brand)
            w, h, fps = get_resolution_tuple(lvds_device_path)
            if setting[0] == w and setting[1] == h:
                if setting[2] == fps:
                    cnt_match += 1
                elif math.fabs(setting[2] - fps) <= FPS_CLOSE:
                    cnt_close += 1
                elif math.fabs(setting[2] - fps) <= FPS_THRESHOLD:
                    cnt_similar += 1
                else:
                    cnt_diff += 1
            else:
                cnt_fail += 1
                fail_dict[resolution_str] +=1

            fps_list_in_vs_get.append(setting[2] - fps)

            pipe_fps, cv_fps = get_fps_cv_gst(setting[0], setting[1], setting[2])
            fps_list_in_vs_pipe.append(setting[2] - pipe_fps)
            fps_list_in_vs_cv.append(setting[2] - cv_fps)
            # print("OpenCV fps = ", cv_fps)

        mean_get = statistics.mean(fps_list_in_vs_get)
        std_get = statistics.stdev(fps_list_in_vs_get)
        mean_pipe = statistics.mean(fps_list_in_vs_pipe)
        std_pipe = statistics.stdev(fps_list_in_vs_pipe)
        mean_cv = statistics.mean(fps_list_in_vs_cv)
        std_cv = statistics.stdev(fps_list_in_vs_cv)
        print(
            f"{setting} stats, set/get diff = {mean_get:.4f}, {std_get:.4f}, gst diff = {mean_pipe:.4f}, {std_pipe:.4f}, OpenCV diff = {mean_cv:.4f}, {std_cv:.4f}"
        )

    print(
        f"Resolution and fps visca set / get stats:  match = {cnt_match}, very close = {cnt_close}, similar = {cnt_similar}, diff = {cnt_diff}, fail = {cnt_fail}"
    )
    # show detail fail resolution stats
    if cnt_fail>0:
        print("Failed resolution stats")
        print(fail_dict)
    
