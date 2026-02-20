#! /usr/bin/env python3
import os
import yaml
import re
import glob
import tempfile

# Currently supports 4 camera types:
# global shutter = AR0234   => ar0234
# ZoomBlock = lvds2mipi     => zoomblock
# Boson = flir or boson     => boson
# imx series = imx          => imx

# Camera key words in device tree and its regular names
camera_dict = {
    "AR0234": "ar0234",
    "lvds2mipi": "zoomblock",
    "flir": "boson",
    "imx": "imx",
}

# Camera gst dict (high resolution and low resolution 2 settings tuples)
camera_gst_dict = {
    "ar0234": [
        (1920, 1080, "video/x-raw,width=1920,height=1080,framerate=60/1"),
        (1280, 720, "video/x-raw,width=1280,height=720,framerate=60/1"),
    ],
    "zoomblock": [
        (1920, 1080, "video/x-raw,width=1920,height=1080,framerate=25/1"),
        (1280, 720, "video/x-raw,width=1280,height=720,framerate=25/1"),
    ],
    "boson": [
        (640, 512, "video/x-raw,width=640,height=512,framerate=60/1"),
        (320, 256, "video/x-raw,width=320,height=256,framerate=60/1"),
    ],
    "imx": [
        (1920, 1080, "video/x-raw,width=1920,height=1080,framerate=30/1"),
        (1280, 720, "video/x-raw,width=1280,height=720,framerate=30/1"),
    ],
}


# Given camera name from device tree, find its matching regular name in camera_dict.
def detect_camera_by_name(cam):
    for key, val in camera_dict.items():
        if key in cam:
            return val
    # cannot find matching camera, use default global shutter ar0234.
    return "ar0234"


# Given camera name, return its width, height and gst string.
# To Do, for ZoomBlock cameras connected through LVDS2MIPI port, still need to detect and get camera gst info using gst-device-monitor ;-)
# Or with a more complex way, get its format using v4l2-ctl --list-formats-ext and "translate" to gst strings ;-)
def get_camera_gst(name):

    info = (
        camera_gst_dict[name] if name in camera_gst_dict else camera_gst_dict["ar0234"]
    )

    width_high, height_high, gst_high = info[0]
    width_low, height_low, gst_low = info[1]

    return width_high, height_high, gst_high, width_low, height_low, gst_low


with open("/tmp/cam_config.yaml", "w") as f:
    # print(f'{f.name}')
    config = {"streams": {}}
    # itterate over cam overlays in /proc/device-tree/chosen/overlays/
    for camfile in glob.iglob("/proc/device-tree/chosen/overlays/cam*"):
        cam = os.path.basename(camfile)
        idn, typ = re.findall(r"cam(\d+)-(\w+)", cam)[0]
        vdev = glob.glob(f"/dev/video*csi{idn}")[0]

        # Get camera name and matching gst info
        name = detect_camera_by_name(cam)

        width_high, height_high, gst_high, width_low, height_low, gst_low = (
            get_camera_gst(name)
        )

        # VPU quality settings: qp above35 gives a grainy image. Below 20 the bitrate starts getting excessive.
        config["streams"][
            f"{cam}_{width_high}x{height_high}"
        ] = f"exec:gst-launch-1.0 -q v4l2src device={vdev} ! {gst_high} ! vpuenc_h264 qp-max=30 qp-min=20 ! fdsink"
        config["streams"][
            f"{cam}_{width_low}x{height_low}"
        ] = f"exec:gst-launch-1.0 -q v4l2src device={vdev} ! {gst_low} ! vpuenc_h264 qp-max=30 qp-min=20 ! fdsink"

    yaml.dump(config, f)
