#!/usr/bin/env python3

"""

File:   v4l2_detect_formats.py

Detect formats by parsing from v4l2 command v4l2-ctl -d /dev/video0 --list-formats-ext outputs.

"""

import argparse
import time
import subprocess
import re
import json


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


def fourcc_to_gst(fourcc_str):
    if fourcc_str in Fourcc_Dict:
        return Fourcc_Dict[fourcc_str]
    else:
        return Fourcc_Dict["NV12"]

def v4l2_format_mapto_gst(format_list):
    for fdict in format_list:
        print(fdict["pixelformat"], "=>", fourcc_to_gst(fdict["pixelformat"]))


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

    camera_formats = formats_filter_out_unwanted(parse_v4l2_formats(args.device))
    print(json.dumps(camera_formats, indent=2))

    v4l2_format_mapto_gst(camera_formats)
    
