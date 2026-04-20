#! /usr/bin/env python3
import os
import yaml
import re
import glob
import shutil
from pathlib import Path

from vdlg_lvds.v4l2_detect_formats import camera_to_gst_list
from vdlg_lvds.detect_cameras_live import camera_dict


"""

File:   go2rtc-create-cams-config.py

2026.0420.  Added Boson 320 and Boson 640 formats without special formats exclusion.
2026.0310.  Added more resolution formats for 3 Sony imx sensors from Framos driver repository xml files.
2026.0302.  Added Zoom Block camera format full list (resolution, fps, formats) from Visca commands.
2026.0226.  Added known camera popular resolution, framerate and format list. 
2026.0226.  Fixed crashing if not /dev/video? detected.

By:			Kobus (in Dec 2025 and before) and jye@videologyinc.com (Since Jan 2026)

"""


# Camera gst dict (high resolution, low resolution and format multiple settings tuples with 4 items each)
camera_gst_dict = {
    "ar0234": [
        (1920, 1080, "default", "video/x-raw,width=1920,height=1080,framerate=60/1"),
        (1280, 720, "default", "video/x-raw,width=1280,height=720,framerate=60/1"),
    ],
    "zoomblock": [
        # Default Zoom Block format and framerate.
        (1920, 1080, "default", "video/x-raw,width=1920,height=1080,framerate=60/1"),
        (1280, 720, "default", "video/x-raw,width=1280,height=720,framerate=60/1"),
    ],
    "boson": [
        # Both Boson 320 and Boson 640 support these color formats.
        (640, 512, "default", "video/x-raw,width=640,height=512,format=NV12,framerate=60/1"),
        (640, 514, "default", "video/x-raw,width=640,height=514,format=NV12,framerate=60/1"),
    ],
    # imx sensors use their *.xml from framos-vvcam-module repository
    "imx900": [
        (
            1920,
            1080,
            "default",
            "video/x-raw,width=1920,height=1080,framerate=15/1,format=YUY2",
        ),
        (
            1280,
            720,
            "default",
            "video/x-raw,width=1280,height=720,framerate=15/1,format=YUY2",
        ),
        # Not supported by vpuenc_h264 (2048, 1536, "default", "video/x-raw,width=2048,height=1536,framerate=15/1,format=YUY2"),
        (
            1024,
            768,
            "default",
            "video/x-raw,width=1024,height=768,framerate=15/1,format=YUY2",
        ),
        (
            1008,
            704,
            "default",
            "video/x-raw,width=1008,height=704,framerate=15/1,format=YUY2",
        ),
    ],
    "imx678": [
        (
            1920,
            1080,
            "default",
            "video/x-raw,width=1920,height=1080,framerate=30/1,format=NV12",
        ),
        (
            1280,
            720,
            "default",
            "video/x-raw,width=1280,height=720,framerate=30/1,format=NV12",
        ),
    ],
    "imx662": [
        (
            1920,
            1080,
            "default",
            "video/x-raw,width=1920,height=1080,framerate=60/1,format=YUY2",
        ),
        (
            1280,
            720,
            "default",
            "video/x-raw,width=1280,height=720,framerate=60/1,format=YUY2",
        ),
        (
            960,
            540,
            "default",
            "video/x-raw,width=960,height=540,framerate=60/1,format=YUY2",
        ),
        (
            640,
            480,
            "default",
            "video/x-raw,width=640,height=480,framerate=60/1,format=YUY2",
        ),
    ],
}
""" Camera gst dict of tuples with 4 items each = (high resolution, low resolution, format, gstreamer string) """


# Given camera name from device tree, find its matching regular name in camera_dict.
def detect_camera_by_name(cam):
    """
    Given camera name from device tree, find its matching regular name in camera_dict as return.

    Arguments:
    cam --  Camera name in system active device tree /proc/device-tree/chosen/overlays/.

    Returns:
    str --  Matching normal camera name if found in dict. Or default "ar0234" if not found.

    """

    for key, val in camera_dict.items():
        if key in cam:
            return val
    # cannot find matching camera, use default global shutter ar0234.
    return "ar0234"


# Given camera name, return its width, height and gst string.
# To Do, for ZoomBlock cameras connected through LVDS2MIPI port, still need to detect and get camera gst info using gst-device-monitor ;-)
# Or with a more complex way, get its format using v4l2-ctl --list-formats-ext and "translate" to gst strings ;-)
def get_camera_gst(name, vdev):
    """
    Given camera name, return its supported list of width, height, format and gst string.

    Arguments:
    name --     Camera name in normal name dict.
    vdev --     Camera device path like /dev/video0 etc.

    Returns:
    list[int,int,str,str] --  Camera supported format list of tuples with 4 items = (width, height, format, gstreamer string).

    Notes:
    (width, height, format) triple is used in go2rtc/ webRTC stream list on the port 1984 web GUI.
    In case of duplicates, extra info such as fps etc. is added to the format string.
    For example, 'fps=60/1,format=NV12' and 'fps=30/1,format=NV12', etc.

    """

    if name == "zoomblock" or name == "boson" or name == "usb":
        # For Zoom Block camera through LVDS board, use newly created info list (from Visca commands).
        # For Boson and usb camera, use auto-generated format lists parsed from v4l2-ctl --list-formats-ext command.
        cam_real_path = Path(vdev).resolve()
        info_list = []
        try:
            info_list = camera_to_gst_list(str(cam_real_path))
        except:
            return []
        else:
            return info_list                  
    else:
        # For global shutter ar0234 and Sony sensors imx series, use constant format list (no auto generated from v4l2 commands).
        info_list = (
            camera_gst_dict[name]
            if name in camera_gst_dict
            else camera_gst_dict["ar0234"]
        )

    return info_list


# Main function loop to open new camera config yaml to write to fill all camera supported streams,
# which is used by go2rtc.service.
with open("/var/tmp/cam_config_new.yaml", "w") as f:
    print(f"Start get camera config from device tree path to file {f.name}")
    config = {"streams": {}}
    # iterate over cam overlays in /proc/device-tree/chosen/overlays/
    for camfile in glob.iglob("/proc/device-tree/chosen/overlays/cam*"):
        cam = os.path.basename(camfile)
        camlist = re.findall(r"cam(\d+)-(\w+)", cam)
        if len(camlist) == 0:
            continue
        idn, typ = camlist[0]
        devlist = glob.glob(f"/dev/video*csi{idn}")
        if len(devlist) == 0:
            continue
        vdev = devlist[0]

        # Get camera name and matching gst info
        name = detect_camera_by_name(cam)

        info_list = get_camera_gst(name, vdev)

        # VPU quality settings: qp above35 gives a grainy image. Below 20 the bitrate starts getting excessive.
        # Parse all resolutions and formats of the camera, may be >=2 ;-)
        for info in info_list:
            width, height, format_str, gst_str = info
            config["streams"][
                f"{cam}_{width}x{height}_{format_str}"
            ] = f"exec:gst-launch-1.0 -q v4l2src device={vdev} ! {gst_str} ! vpuenc_h264 qp-max=30 qp-min=20 ! fdsink"

    # Do the same for usb camera if any. Just one now ;-)
    usb_list = glob.glob("/dev/v4l/by-path/*")
    if usb_list:
        # Find first usb camera on the list.
        for s in usb_list:
            if "usb" in s:
                vdev = str(Path(s).resolve())
                name = "usb"

                info_list = get_camera_gst(name, vdev)
                for info in info_list:
                    width, height, format_str, gst_str = info
                    config["streams"][
                        f"{name}_{width}x{height}_{format_str}"
                    ] = f"exec:gst-launch-1.0 -q v4l2src device={vdev} ! {gst_str} ! vpuenc_h264 qp-max=30 qp-min=20 ! fdsink"

    print(config)

    yaml.dump(config, f)

# Create back up copy of /var/tmp/cam_config_new.yaml into /var/tmp/cam_config.yaml
shutil.copyfile("/var/tmp/cam_config_new.yaml", "/var/tmp/cam_config.yaml")
