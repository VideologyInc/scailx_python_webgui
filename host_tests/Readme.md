
# Run python programs on Windows host to test Scailx and Cameras.

Please always run in a python venv.

First install pythjon packages

pip install -r requirements.txt

============================================================================

## test go2rtc streams

python test_go2rtc_https.py --hostname scailx-abc.local

With Scailx hostname entered, it grabs cam_config.yaml from the Scailx device and test all streams using OpenCV.


===========================================================================

## test_lvds_reboot_gst.py

It needs the cam_config.yaml file from above test.

It tests Scailx devices reboot multiple times with various supported resolutions and framerates, trying to access video streams and report stats afterwards.

python test_lvds_reboot_gst.py -n 10 --hostname scailx-abc.local

