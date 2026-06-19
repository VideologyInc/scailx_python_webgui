Scailx simple web ui

============================================================================

Windows host tests of go2rtc streams:

2026.0619.  Added new subfolder ~\hosts_test with py program running on Windows python venv to test Scailx device go2rtc streams automatically.

Syntax and examples:

	python test_go2rtc_https.py -h		(show help)
	
	python test_go2rtc_https.py -s cam0-gs-AR0234_0_1280x720_NV12_fps=15 --hostname scailx-ai-boson8 -v 1  
	(show video and do auto tests, press q to exit video window)

	python test_go2rtc_https.py --hostname scailx-ai-boson8 -v 1  
	(show video using first item from cam_config.yaml from Scailx device, and do auto tests, press q to exit video window)

	python test_go2rtc_https.py --hostname scailx-ai-boson8
	(get cam_config.yaml from Scailx device, and do auto tests only, no video to display)


============================================================================

Updates in ~/scailx_tools/.

2026.0603.  Added detect usb live service to work together with go2rtc service. It needs new package linuxpy.

2026.0519.	Added (camera name + id + device path) to 2 lists used by go2RTC and Portal.

2026.0428.  Added functions and codes to generate cemara settings list for Portal. They are saved to /var/tmp/cam_config.json.

2026.0422.	Added subfolder ~/tests following standard pytest structure with 3 pytest files + assets subfolder to do go2rtc py codes unit tests.

2026.0410.	Added detect_imx_live.py and new ~/imx/vvget version 1.10 to set/get camera parameters from json and txt file when streams starts.

2026.0327.	Updated py to add more Boson formats to go2rtc including object and thermal detection. Also updated py to estimate gray16 linear transform parameters when go2rtc.service stats. Added bash scripts and AI model files in subfolder ~/scailx_tools/boson, including scripts to update them to correct Scailx system folder.

2026.0316.	Added new detect_camera_live.py and updated other py and bash scripts to support usb camera live detection in go2rtc / webrtc.

2026.0303.  Added new option "--mac 1" to change hostname using MAC address of the device.

2025.1215.	Added check_fix_hostname.py to use avahi to check hostname conflict and fix it.

============================================================================

go2rtc related changes. 5 files are related

go2rtc-create-cams-config.py    Need to copy to /usr/bin/ to override original.

v4l2_detect_formats.py          Need to copy to /usr/lib/python3.12/site-packages/vdlg_lvds/ as part of the python package vdlg_lvds.

detect_camera_live.py			Need to copy to /usr/lib/python3.12/site-packages/vdlg_lvds/ as part of the python package vdlg_lvds.

go2rtc.service                  Need to copy to /usr/lib/systemd/system/go2rtc.service and restart the service to make all changes effective.

update_go2rtc_formats.sh		Bash script to do above copy commands. Reboot scailx to make them effective.

============================================================================

Semi-automatic live usb camera format detection on webrtc.

Run following program. 
It will loop to check camera connection every 5 seconds. 
With camera connection status changed, it will restart go2rtc service to make it effective on webrtc port1984.

python3 /usr/lib/python3.12/site-packages/vdlg_lvds/detect_cameras_live.py





