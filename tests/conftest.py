
import fcntl
import glob
from pathlib import Path
from vdlg_lvds.serial import LvdsSerial
from vdlg_lvds.ioctl import *

import pytest


# root_path is project's root path = parent of ~/tests.
@pytest.fixture
def root_path(request):
    return request.config.rootpath


# Prefix to save images under ~/tests/assets/
@pytest.fixture
def prefix(root_path):
    full_path = Path(root_path) / "tests" / "assets" / "test"
    return str(full_path.relative_to(Path.cwd()))


# Two json files to test
@pytest.fixture
def camera_dict_name(root_path):
    full_path = Path(root_path) / "tests" / "assets" / "camera_dict.json"
    return str(full_path.relative_to(Path.cwd()))


@pytest.fixture
def camera_gst_name(root_path):
    full_path = Path(root_path) / "tests" / "assets" / "camera_gst_dict.json"
    return str(full_path.relative_to(Path.cwd()))

# lvds device path
@pytest.fixture
def lvds_device_path():
    lvds_devs = glob.glob("/dev/links/lvds*")
    default_lvds = lvds_devs[0] if lvds_devs else "/dev/v4l-subdev1"
    return default_lvds

# lvds serial device object
@pytest.fixture
def lvds_serial_device(lvds_device_path):
    serial_device = LvdsSerial(lvds_device_path)
    return serial_device

# firmware version: B7 or new B8, etc.
@pytest.fixture
def lvds_fw_version(lvds_device_path):
    ioctl_serial = LvdsIoctlSerial()
    with open(lvds_device_path) as f:
        fcntl.ioctl(f, LVDS_CMD_GET_FW_VERSION, ioctl_serial)
        ret = ioctl_serial.len
        return ret

    return "N/A"
