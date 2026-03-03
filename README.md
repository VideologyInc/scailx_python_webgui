Scailx simple web ui

================================================================================

Updates.

2026.0303.  Added new option "--mac 1" to change hostname using MAC address of the device.

2025.1215.	Added check_fix_hostname.py to use avahi to check hostname conflict and fix it.

================================================================================

go2rtc related changes. 3 files are related

go2rtc-create-cams-config.py    Need to copy to /usr/bin/ to override original.

v4l2_detect_formats.py          Need to copy to /usr/lib/python3.12/site-packages/vdlg_lvds/ as part of the python package vdlg_lvds.

go2rtc.service                  Need to copy to /usr/lib/systemd/system/go2rtc.service and restart the service to make all changes effective.






