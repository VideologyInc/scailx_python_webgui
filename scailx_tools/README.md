Scailx Tools

============================================================================

Subfolders and Files:

~/boson				Bash scripts to launch gstreamer for Boson camera various resolutions and formats, including thermal detection and object detection.
~/boson/models		AI models used by above bash scripts.

~/default_xml		Imx camera series parameter default xml used by "Reset" command of vvext and vvget.

~/imx				New binary vvget and its dependency libjson. A few parameter json and txt file to test detect_imx_live.py.


boson_stats.py		For boson cameras, grab a frame and calculate its stats for gray16 format contrast enhancement.

check_fix_hostname.py		Check Scailx device hostname and fix using avahi or MAC address.

detect_cameras_live.py		Detect usb camera status live and restart go2rtc to see it is unplugged or replugged-in on webRTC port 1984.

detect_imx_live.py			Detect one imx camera stream on/off live and set parameters using json file.
	
go2rtc-create-cams-config.py	Improved main program called by go2rtc to detect cameras and set supported format gstreamer strings for webRTC.

read_imx_json.py			Read imx camera parameter json file, convert to txt file, and parse vvget outputs, etc.

v4l2_detect_formats.py		Main program called by go2rtc.service to detect camera formats by "v4l2-ctl --list-formats-ext" command and set valid gstreamer strings.

go2rtc.service		Standard go2rtc service file.	

requirements.txt	New requirements.txt file for python pip3 install for extra packages needed by py programs of this folder.


