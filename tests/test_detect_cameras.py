"""

pytest to test detect_camera_type()

2026.0422.  Created.

By: jye@videologyinc.com

"""

from vdlg_lvds.detect_cameras_live import detect_camera_type, detect_cameras

import pytest

# Test detect camera type at port 0, 1, and 2 (no camera at this port)
@pytest.mark.parametrize("camera_id", [
    (0),
    (1),
    (2)
])
def test_detect_camera_type(camera_id):

    camera_dev = "/dev/video" + str(camera_id)
    try:
        camera_name, camera_path = detect_camera_type(camera_dev)
    except Exception as e:
        print(f"An error occurred: {e}")
        return

    if camera_id < 2:
        assert (camera_name !="") and (camera_path !="")
    else:
        assert (camera_name =="") and (camera_path =="")

    print(camera_dev, camera_name, camera_path)

