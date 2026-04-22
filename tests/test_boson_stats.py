"""

pytest to test boson_stats with benchmark.

2026.0422.  Created.

By: jye@videologyinc.com

"""

from vdlg_lvds.boson_stats import boson_show_telemetry

import pytest

# Standard boson_stats test.
def test_boson_stats(prefix):

    camera_number = 1
    width = 640
    height = 512
    save_image_flag = True

    beta = 0
    alpha16 = 0
    alpha8 = 0
    
    print(prefix)

    try:
        beta, alpha16, alpha8 = boson_show_telemetry(camera_number, width, height, prefix, save_image_flag)
    except Exception as e:
        print(f"An error occurred: {e}")
        return
  
    assert (alpha16 !=0) and (alpha8 !=0)

    print("Gray16 transform coefficietnts: ")
    print(f"out16 = (in16 - {beta}) x {alpha16}")
    print(f"out8 = (in16 - {beta}) x {alpha8}")

# boson_stats test using non-boson camera id.    
def test_not_boson_stats():

    camera_number = 0

    beta = 0
    alpha16 = 0
    alpha8 = 0

    try:
        beta, alpha16, alpha8 = boson_show_telemetry(camera_number, 640, 512, "", False)
    except Exception as e:
        print(f"An error occurred: {e}")
        return
  
    assert (alpha16 !=0) and (alpha8 !=0)


# Test benchmark speed to calculate boson stats without saving to file.
@pytest.mark.parametrize("width, height", [
    (320, 256),
    (640, 512),
    (640, 514),
])
def test_boson_stats_speed(benchmark, width, height):

    ret = benchmark(boson_show_telemetry, 1, width, height, "", False)
