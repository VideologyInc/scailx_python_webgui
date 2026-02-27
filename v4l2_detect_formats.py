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

    camera_formats = parse_v4l2_formats(args.device)
    print(json.dumps(camera_formats, indent=2))
