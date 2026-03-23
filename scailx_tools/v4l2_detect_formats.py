#!/usr/bin/env python3

"""

File:   v4l2_detect_formats.py

2026.0227.  Detect formats by parsing from v4l2 command v4l2-ctl -d /dev/video0 --list-formats-ext outputs.
2026.0302.  Added Zoom Block camera format full list (resolution, fps, formats) from Visca commands.

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

from vdlg_lvds.detect_cameras_live import detect_camera_type

# Camera key words in device tree and its regular names
camera_dict = {
    "AR0234": "ar0234",
    "lvds2mipi": "zoomblock",
    "flir": "boson",
    "imx900": "imx900",
    "imx678": "imx678",
    "imx662": "imx662",
}

Format_Exclude_List = ["NM12", "YUV4", "YM24"]
Desc_Exclude_List = ["Bayer", "JPEG", "10-bit", "12-bit", "5-6-5"]
Fourcc_Dict = {"YUYV" : "YUY2", "NV12" : "NV12",
    "GREY" : "GRAY8", "Y16 " : "GRAY16_LE", "RGB3" : "RGB", 
    "BGR3" : "BGR", "XR24" : "BGRx", "AR24" : "BGRA"
    }


def parse_v4l2_formats(device="/dev/video0"):
    # Run the command
    cmd = f"v4l2-ctl -d {device} --list-formats-ext"
    try:
        output = subprocess.check_output(cmd, shell=True).decode("utf-8")
    except subprocess.CalledProcessError:
        print("Device not found or error running v4l2-ctl")
        return []

    formats = []
    current_format = None

    # Regex patterns
    fmt_pattern = re.compile(r"\[\d+\]:\s+'(.+?)'\s+\((.+)\)")
    size_pattern = re.compile(r"Size:\s+Discrete\s+(\d+)x(\d+)")
    fps_pattern = re.compile(r"Interval:\s+Discrete\s+.*?\s+\(([\d\.]+)\s+fps\)")

    for line in output.splitlines():
        line = line.strip()

        # Match Format line
        fmt_match = fmt_pattern.search(line)
        if fmt_match:
            current_format = {
                "pixelformat": fmt_match.group(1),
                "description": fmt_match.group(2),
                "sizes": [],
            }
            formats.append(current_format)
            continue

        # Match Size line
        size_match = size_pattern.search(line)
        if size_match and current_format is not None:
            current_size = {
                "width": int(size_match.group(1)),
                "height": int(size_match.group(2)),
                "fps": [],
            }
            current_format["sizes"].append(current_size)
            continue

        # Match FPS line
        fps_match = fps_pattern.search(line)
        if fps_match and current_format is not None:
            current_format["sizes"][-1]["fps"].append(float(fps_match.group(1)))

    return formats

# Given format list from above, filter out 3 big conditions:
# empty sizes, some special formats, and description containing Bayer, JPEG, 10-bit or 12-bit.
def formats_filter_out_unwanted(format_list):
    format_list_filtered = []
    for fdict in format_list:
        if fdict["pixelformat"] in Format_Exclude_List:
            continue
        if len(fdict["sizes"])==0:
            continue
        if any(sub in fdict["description"] for sub in Desc_Exclude_List):
            continue
        format_list_filtered.append(fdict)
    
    return format_list_filtered

# For Zoom Block cameras connecte to LVDS port, add fps = 25,30,50,60 and 1920 x 1080, plus 1280 x 720 to the list.
def add_formats_lvds(format_list):
    formats = {"YUYV" : "YUYV 4:2:2", "NV12" : "Y/UV 4:2:0"}
    resolution_list = [(1920,1080), (1280, 720)]
    fps_list = [25.0, 30.0, 50.0, 60.0]
    # Add all combinations 2 x 2 x 4 = 16 total possible formats
    sample = {
        "pixelformat": "YUYV",
        "description": "YUYV 4:2:2",
        "sizes": [
            {
                "width": 1920,
                "height": 1080,
                "fps": [25.0]
            }
        ]
    }

    format_list = []
    for f in formats.keys():
        for w,h in resolution_list:
            for fps in fps_list:

                print(f, w, h, fps)
                one = copy.deepcopy(sample)
                one["pixelformat"] = f
                one["description"] = formats[f]
                one["sizes"][0]["width"] = w
                one["sizes"][0]["height"] = h
                one["sizes"][0]["fps"][0] = fps
                format_list.append(one)

    return format_list


def fourcc_to_gst(fourcc_str):
    if fourcc_str in Fourcc_Dict:
        return Fourcc_Dict[fourcc_str]
    else:
        return Fourcc_Dict["NV12"]

def v4l2_format_mapto_gst(format_list):
    for fdict in format_list:
        print(fdict["pixelformat"], "=>", fourcc_to_gst(fdict["pixelformat"]))

# For Boson camera, given width, height, framerate, and format=GRAY16_LE, return nnstreamer pipeline str.
def boson_gray16_nnstreamer(w, h, fps, f_gst, out16=True):
    # Always need this to avoid gst crash if using same width and height as input.
    hh = h + 16
    # These 2 values are calculated based on boson_stats.py output.
    # out = (in - vmin) / (vmax - vmin) * 65535; (or *255 for 8bits)
    beta = -5474.0
    alpha = 112.77 if out16 else 0.43878
    cmax = 65535.0 if out16 else 255.0
    outype = "uint16" if out16 else "uint8"
    outformat = "GRAY16_LE" if out16 else "GRAY8"

    s = (
        rf"video/x-raw,width={w},height={h},framerate={fps}/1,format={f_gst} ! "
        r"videorate max-rate=10 ! video/x-raw,framerate=10/1 ! "
        r"queue leaky=2 max-size-buffers=10 ! "
        rf"videoscale ! video/x-raw, width={w}, height={hh} ! "
        r"tensor_converter ! "
        rf"tensor_transform mode=arithmetic option=typecast:float32,add:{beta},mul:{alpha} ! "
        r"queue leaky=2 max-size-buffers=10 ! "
        rf"tensor_transform mode=clamp option=0.0:{cmax} ! "
        rf"tensor_transform mode=typecast option={outype} ! "
        r"queue leaky=2 max-size-buffers=10 ! "
        rf"tensor_decoder mode=direct_video option1={outformat} ! "
        "videoconvert "
    )

    return s


# Given one format dict, return its gstreamer string.
# Now use camera_type to handle Boson camera GRAY16_LE using nnstreamer pipeline.
def v4l2_format_to_gst(format_dict, camera_type=""):
    s_list = []
    for sz in format_dict["sizes"]:
        w = sz["width"]
        h = sz["height"]
        fps = int(math.ceil(sz["fps"][0]))
        f = format_dict["pixelformat"]
        f_gst = fourcc_to_gst(f)
        if camera_type=="boson" and f_gst=="GRAY16_LE":
        # Boson gray16 special treatment.
            s8 = boson_gray16_nnstreamer(w, h, fps, f_gst, False)
            s16 = boson_gray16_nnstreamer(w, h, fps, f_gst, True)
            t8 = (w, h, f"fps={fps},format={f_gst}, out=8bit", s8)
            t16 = (w, h, f"fps={fps},format={f_gst}, out=16bit", s16)
            s_list.append(t8)
            s_list.append(t16)
        else:
        # Regular gst string.
            s = f"video/x-raw,width={w},height={h},framerate={fps}/1,format={f_gst} ! videoconvert"
            t = (w, h, f"fps={fps},format={f_gst}", s)
            s_list.append(t)

    return s_list

# Given camera device path, return supported gstreamer str list.
def camera_to_gst_list(device):
    camera_type, cam_path = detect_camera_type(device)

    camera_formats = formats_filter_out_unwanted(parse_v4l2_formats(device))
    # print(camera_type)
    if camera_type=="zoomblock":
    # Add full resolution and framerate support for ZoomBlock (from visca commands)
        print("Create new format list for ZoomBlock cameras.")
        camera_formats = add_formats_lvds(camera_formats)
    # print(json.dumps(camera_formats, indent=2))

    info_list = []
    for fd in camera_formats:
        s_list = v4l2_format_to_gst(fd, camera_type)
        info_list += s_list

    return info_list

# Example Usage
if __name__ == "__main__":

    parser = argparse.ArgumentParser(
        description="Detect camera formats by parsing v4l2 command outputs",
        prog="v4l2_detect_formats",
    )
    parser.add_argument(
        "-d", "--device", type=str, default="/dev/video0", help="camera device path"
    )

    args = parser.parse_args()

    info_list = camera_to_gst_list(args.device)

    for info in info_list:
        print(info)
    