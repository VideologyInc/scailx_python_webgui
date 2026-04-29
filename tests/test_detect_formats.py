"""

pytest to test 4 functions in detect_cameras_live and v4l2_detect_formats.

2026.0422.  Created.

By: jye@videologyinc.com

"""

import importlib

from vdlg_lvds.detect_cameras_live import detect_camera_type, detect_cameras
from vdlg_lvds.v4l2_detect_formats import (
    camera_to_gst_list,
    fourcc_to_gst,
    parse_v4l2_formats,
)

# Must use importlib to import module containing "-" ;-)
cam_config = importlib.import_module("vdlg_lvds.go2rtc-create-cams-config")

import pytest


# Test camera to gst list at port 0, 1, and 2 (no camera at this port)
@pytest.mark.parametrize("camera_id", [(0), (1), (2)])
def test_camera_to_gst_list(camera_id):

    camera_dev = "/dev/video" + str(camera_id)
    try:
        info_list = camera_to_gst_list(camera_dev)
    except Exception as e:
        print(f"An error occurred: {e}")
        return

    assert info_list is not []

    print(camera_dev, "number of formats = ", len(info_list))


# Test fourcc to gst
def test_fourcc_to_gst():

    for f in ["Y16 ", "NV12", "GREY", "YUYV", "AR24", "YUV4", "BA81", "RGB3", "RGGB"]:
        gst_fmt = fourcc_to_gst(f)
        print(f, gst_fmt)


# Test parse_v4l2_formats.
@pytest.mark.parametrize("camera_id", [(0), (1), (2)])
def test_parse_v4l2_formats(camera_id):
    camera_dev = "/dev/video" + str(camera_id)
    try:
        fmt_list = parse_v4l2_formats(camera_dev)
    except Exception as e:
        print(f"An error occurred: {e}")
        return

    assert fmt_list is not []

    print(camera_dev, "parse formats = ", len(fmt_list))


# Test get_camera_gst.
@pytest.mark.parametrize(
    "camera_id",
    [
        (0),
        (1),
        (2),
    ],
)
def test_get_camera_gst(camera_id):
    camera_dev = "/dev/video" + str(camera_id)
    name = detect_camera_type(camera_dev)
    try:
        info_list = cam_config.get_camera_gst(name, camera_dev)
    except Exception as e:
        print(f"An error occurred: {e}")
        return

    assert info_list is not []

    print(name, camera_dev, "detected formats = ", len(info_list))
