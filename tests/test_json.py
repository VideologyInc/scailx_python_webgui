"""

pytest to test two json files.

2026.0429.  Created.

By: jye@videologyinc.com

"""

import json
import pytest


# camera_dict json test.
def test_camera_dict(camera_dict_name):

    camera_dict = {}
    with open(camera_dict_name, "r") as f:
        camera_dict = json.load(f)

    assert camera_dict != {}

    print()
    print(camera_dict)


# camera_gst dict json test.
def test_camera_gst(camera_gst_name):

    camera_gst = {}
    with open(camera_gst_name, "r") as f:
        camera_gst = json.load(f)

    assert camera_gst != {}

    print()
    print(camera_gst)
