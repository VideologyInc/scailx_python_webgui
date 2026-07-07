lvds2mipi Driver B8 ZoomBlock Tests

Before running any pytests on Scailx devices, we need to install its python packages.

cd ~/scailx_tools

pip3 install -r requirements.txt

Now we can start pytest. Option -s to show stdout and stderr. Option -k "abc" to specify keyword to test.

============pytest lvds======================

pytest -k "lvds" --collect-only		(list all pytests containing lvds)

pytest -s -k "test_lvds_serial"   (serial communication test)

pytest -s -k "test_reboot_lvds"   (visca command to reboot ZoomBlock camera tests)

pytest -s -k "test_reboot_multi"  (visca command to reboot ZoomBlock camera with or without info check)

pytest -s -k "test_lvds_resolution"  (set/get resolution + fps tests)

