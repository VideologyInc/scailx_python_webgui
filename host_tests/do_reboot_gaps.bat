echo Call test_lvds_reboot_gst.py multiple times with various gap.


# python test_lvds_reboot_gst.py --hostname scailx-abc.local -g 30 -n 10 -i 10  > zb_gap30_log.txt

# python test_lvds_reboot_gst.py --hostname scailx-abc.local -g 25 -n 10 -i 10  > zb_gap25_log.txt

python test_lvds_reboot_gst.py --hostname scailx-abc.local -g 20 -n 10 -i 10  > zb_gap20_log.txt

python test_lvds_reboot_gst.py --hostname scailx-abc.local -g 15 -n 10 -i 10  > zb_gap15_log.txt

python test_lvds_reboot_gst.py --hostname scailx-abc.local -g 10 -n 10 -i 10  > zb_gap10_log.txt

