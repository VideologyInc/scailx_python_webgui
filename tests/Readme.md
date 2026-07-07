lvds2mipi Driver B8 ZoomBlock Tests

============pytest lvds======================

pytest -k "lvds" --collect-only		(list all pytests containing lvds)

pytest -s -k "test_lvds_serial"   (serial communication test)

pytest -s -k "test_reboot_lvds"   (visca command to reboot ZoomBlock camera tests)

pytest -s -k "test_reboot_multi"  (visca command to reboot ZoomBlock camera with or without info check)

pytest -s -k "test_lvds_resolution"  (set/get resolution + fps tests)

