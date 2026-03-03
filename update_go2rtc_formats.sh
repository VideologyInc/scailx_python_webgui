
echo Copy 3 files to update go2rtc format changes of the camera sensors.

echo Copy go2rtc*.py to /usr/bin/
cp go2rtc-create-cams-config.py /usr/bin/

echo Copy v4l2_detect*.py to /usr/lib/python3.12/site-packages/vdlg_lvds/ 
cp v4l2_detect_formats.py /usr/lib/python3.12/site-packages/vdlg_lvds/

echo Copy go2rtc.service to /usr/lib/systemd/system/
cp go2rtc.service /usr/lib/systemd/system/

echo Try python3 go2rtc-create-cams-config.py and cat /var/tmp/cam_config.yaml to make sure they are correct.
echo Then reboot device to check in 1984 web GUI to test streams.

