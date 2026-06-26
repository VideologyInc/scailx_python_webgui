"""

File:   test_lvds_reboot.py

2026.0624.  Created to test lvds ZoomBlock reboot scailx and OpenCV to access camera streams.

By:			jye@videologyinc.com

"""

import argparse
import json
import yaml
import subprocess
import time

import cv2

# ============================================
# scailx reboot and wait for it comes back
# ============================================


# Reboot scailx using ssh from Windows host.
def reboot_scailx(hostname):

    try:
        result = subprocess.run(
            ["ssh", f"root@{hostname}", '"reboot"'],
            capture_output=True,
            text=True,
            check=True,
        )
        print("reboot scailx: ", result.stdout)
    except Exception as e:
        print(f"reboot scailx failed: {e}")


def ping(host):
    """Pings the host; returns True if device replies."""
    # Use -n for Windows, -c for Linux/macOS
    command = ["ping", "-w", "2", host]
    return (
        subprocess.run(
            command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        ).returncode
        == 0
    )


# Wait for it to come back online
def wait_for_device(host, poll_interval=5, timeout=60):

    start_time = time.time()

    while not ping(host):
        time_from_start = time.time() - start_time
        if time_from_start > timeout:
            print("Timed out waiting for Scailx.")
            return False, time_from_start
        print(".", end="", flush=True)
        time.sleep(poll_interval)

    print("\nDevice is back online!")
    return True, time.time() - start_time


# Reboot Scailx and access lvds zoomblock camera stream.


def test_scailx_reboot_and_back(hostname):

    ret, pre = wait_for_device(hostname, 1, 60)
    if not ret:
        return False, pre

    reboot_scailx(hostname)

    ret, elapsed = wait_for_device(hostname)
    print(f"scailx rebooted = {ret}, {elapsed:.2f} seconds")
    return ret, elapsed


# ============================================
# streams access and tests.
# ============================================


# Parse cam_config.yaml contents to dict.
def parse_camera_yaml(cam_config_name):
    try:
        with open(cam_config_name, "r") as file:
            cam_config_dict = yaml.safe_load(file)
            return cam_config_dict["streams"] if "streams" in cam_config_dict else {}
        return {}
    except:
        return {}


# Get first lvds zoomblock stream from the dict.
def get_1st_lvds(cam_config):

    for key, val in cam_config.items():
        if "lvds" in key:
            return key
    return ""


# Open stream and Grab one frame.
def open_go2rtc_frame(stream_url):
    cap = cv2.VideoCapture(stream_url)

    while cap.isOpened():
        ret, frame = cap.read()
        if ret and frame is not None:
            cap.release()
            cv2.destroyAllWindows()
            return True, frame.shape
        else:
            cap.release()
            cv2.destroyAllWindows()
            return False, None

    return False, None


# Given stream name, test it.
def test_lvds_stream(url):
    ret, shape = open_go2rtc_frame(url)
    print(url, "=>", ret, shape)


# ============================================
# scailx reboot and lvds streams access tests.
# ============================================
def test_scailx_reboot_lvds(hostname, url, gap, idle):

    # about 4 seconds
    retr, reboot_time = test_scailx_reboot_and_back(hostname)
    if not retr:
        return False

    # waif another 20 seconds for go2rtc to access stream.
    time.sleep(gap)
    # now stream access.
    ret, shape = open_go2rtc_frame(url)
    print(url, "=>", ret, shape)

    # sleep a few seconds before next reboot.
    time.sleep(idle)

    return ret


if __name__ == "__main__":

    parser = argparse.ArgumentParser(
        description="Test lvds Scailx reboot time",
        prog="test_lvds_reboot",
    )

    parser.add_argument(
        "--hostname",
        type=str,
        default="scailx-ai.local",
        help="hostname or IP adddress of the scailx device",
    )

    parser.add_argument(
        "-y",
        "--yaml",
        type=str,
        default="cam_config.yaml",
        help="Get camera config yaml same as go2rtc.service input.",
    )

    parser.add_argument(
        "-g",
        "--gap",
        type=int,
        default=20,
        help="gap in seconds after reboot to test lvds stream.",
    )
    parser.add_argument(
        "-i",
        "--idle",
        type=int,
        default=5,
        help="idle time in seconds after lvds stream access before next Scailx reboot.",
    )

    parser.add_argument(
        "-n",
        "--num",
        type=int,
        default=1,
        help="Number of iterations to test.",
    )

    args = parser.parse_args()

    ret, pretime = wait_for_device(args.hostname)
    if not ret:
        print(f"ping {args.hostname} error")
        exit(1)

    cam_config_dict = parse_camera_yaml(args.yaml)
    lvds_stream = get_1st_lvds(cam_config_dict)

    # print(json.dumps(cam_config_dict, indent=4))
    print(lvds_stream)

    stream_str_list = [
        "rtsp://" + args.hostname + ":8554/",
        "http://" + args.hostname + ":1984/api/stream.flv?src=",
        "http://" + args.hostname + ":1984/api/frame.jpeg?src=",
    ]

    # Use jpeg to grab one frame of each stream to test.
    # test_lvds_stream(stream_str_list[2] + str(lvds_stream))
    # test_scailx_reboot_and_back(args.hostname)

    # Test reboot scailx + lvds stream access
    cnt_pass = 0
    for i in range(args.num):
        ret = test_scailx_reboot_lvds(
            args.hostname, stream_str_list[2] + str(lvds_stream), args.gap, args.idle
        )
        if ret:
            cnt_pass += 1
    print(
        f"Total number = {args.num}, successful = {cnt_pass}, failed = {args.num-cnt_pass}"
    )
