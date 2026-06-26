"""

pytest to test lvds B7 driver refactoring CoreVision pytest codes.

2026.0623.  Created.

By: jye@videologyinc.com

"""

from vdlg_lvds.ioctl import *
from vdlg_lvds.serial import LvdsSerial
from vdlg_lvds.set_res import detect_camera_brand, set_resolution
from vdlg_lvds.get_res import get_resolution
from vdlg_lvds.detect_cameras_live import detect_camera_type, MAX_CAMERA_ID

from hide_warnings import hide_warnings
from contextlib import redirect_stdout
import io
import os
import math
import time
import cv2
import statistics

import pytest

# timeout is 1 sec.
TIMEOUT = 1000

# fps is similar
FPS_THRESHOLD = 0.5
# fps is very close
FPS_CLOSE = 0.1

# lvds ZoomBlock cameras, we support 8 settings of resolution + fps.
zoomblock_settings_dict = {
    "720p25" : (1280, 720, 25),
    "720p30" : (1280, 720, 30),
    "720p50" : (1280, 720, 50),
    "720p60" : (1280, 720, 60),
    "1080p25" : (1920, 1080, 25),
    "1080p30" : (1920, 1080, 30),
    "1080p50" : (1920, 1080, 50),
    "1080p60" : (1920, 1080, 60)
}

# reboot hex in bytearray
REBOOT_DATA = bytearray.fromhex("8101040000FF")


# Utility function to reboot lvds and get serial info for benchmark.
def lvds_reboot_info(lvds_serial_device, test_brand_flag):
    reboot_hex = "8101040000FF"
    data = bytearray.fromhex(reboot_hex)

    with open(os.devnull, 'w') as f, redirect_stdout(f):
        response_data = lvds_serial_device.transceive(data, start_wait_ms=TIMEOUT)
        if test_brand_flag:
            brand = detect_camera_brand(lvds_serial_device)


# Return 1st valid /dev/camera? path for lvds zoomblock camera.
def get_first_lvds():
    prefix = "/dev/video"
    for id in range(0, MAX_CAMERA_ID):
        camera_path = prefix + str(id)
        camera_name, devicetree_name = detect_camera_type(camera_path)
        if camera_name=="zoomblock":
            return camera_path
    return ""

# Use OpenCV to get fps and measure real fps.
@hide_warnings
def get_fps_cv_gst(w, h, fps):
    # Define your GStreamer pipeline string (ensure it ends with appsink)
    zoomblock_path = get_first_lvds()
    gst_pipeline = (
        f"v4l2src device={zoomblock_path} ! "
        f"video/x-raw, width={w}, height={h}, framerate={fps}/1, pixelformat=NV12 ! "
        "videoconvert ! video/x-raw, format=BGR ! appsink drop=1"
    )

    # Initialize video capture with GStreamer backend
    cap = cv2.VideoCapture(gst_pipeline, cv2.CAP_GSTREAMER)

    if not cap.isOpened():
        print("Error: Could not open GStreamer pipeline.")
        return 0, 0

    # Returns configured pipeline FPS (may return 0 or wrong values for raw RTSP/live feeds)
    pipeline_fps = cap.get(cv2.CAP_PROP_FPS)

    prev_time = time.time()
    fps_sum = 0
    for i in range(fps):
        ret, frame = cap.read()
        if not ret:
            break

        # Calculate current frame rate
        current_time = time.time()
        current_fps = 1 / (current_time - prev_time)
        prev_time = current_time
        fps_sum += current_fps

    cap.release()
    # cv2.destroyAllWindows()

    return pipeline_fps, fps_sum / fps

# utility function to get resolution into a tuple
@hide_warnings
def get_resolution_tuple(lvds_device_path):
    f = io.StringIO()
    with redirect_stdout(f):
        get_resolution(lvds_device_path)
    output_string = f.getvalue()
    res_list = output_string.split()
    # [0] = w, [2] = h, [4] = fps
    if len(res_list)>=5:
        width = int(res_list[0])
        height = int(res_list[2])
        fps = float(res_list[4])
        return width, height, fps
    elif len(res_list)>=3:
        width = int(res_list[0])
        height = int(res_list[2])
        return width, height, 0

    return 0, 0, 0

# Test basic lvds serial device connection.
def test_lvds_serial(lvds_serial_device):

    brand = detect_camera_brand(lvds_serial_device)

    assert brand == "videology"

def test_reboot_lvds(lvds_serial_device):
    response_data = lvds_serial_device.transceive(REBOOT_DATA, start_wait_ms=TIMEOUT)
    response_hex = response_data.hex()
    assert str(response_hex)=="9041ff9051ff"
    print("lvds reboot ", REBOOT_DATA.hex(), " => ", response_hex)


# Make sure reboot and serial work in pairs multiple times.
def test_reboot_multi_check(benchmark, lvds_serial_device):
    benchmark.pedantic(lvds_reboot_info, args=(lvds_serial_device, True), iterations=10, rounds=10)

def test_reboot_multi_nocheck(benchmark, lvds_serial_device):
    benchmark.pedantic(lvds_reboot_info, args=(lvds_serial_device, False), iterations=10, rounds=10)

# Test lvds serial send and receive hex data.
# 4 hex strings mean inquire: camera info, camera id, AE mode, Zoom Position.
@pytest.mark.parametrize("hex_command", [("81090002FF"), ("81090422FF"), ("81090439FF"), ("81090447FF")])
def test_lvds_transceive(lvds_serial_device, hex_command):
    data = bytearray.fromhex(hex_command)
    response_data = lvds_serial_device.transceive(data, start_wait_ms=TIMEOUT)
    response_hex = response_data.hex()

    print(hex_command, " => ", response_hex)


# Simulate CV's init serial tests 10 times.
def test_lvds_serial_multi(lvds_serial_device):

    serial_test_count = 10
    counter = 0
    serial_failed_cnt = 0

    for i in range(serial_test_count):
        brand = detect_camera_brand(lvds_serial_device)
        if brand != "videology":
            serial_failed_cnt += 1
            time.sleep(random.random())
            counter += 1

    if serial_failed_cnt > 0:
        assert False, f"ERROR\tSerial test failed. Incorrect messages: {serial_failed_cnt}/{counter}"
			
# Test set / get resolution + fps multiple times and measure accuracy using OpenCV.
def test_lvds_resolutions(lvds_serial_device, lvds_device_path, lvds_fw_version):
    verbose = False
    # sleep 3 seconds between each pair of set / get resolution
    gap = 3

    test_cnt = 100

    brand = detect_camera_brand(lvds_serial_device)

    fpga_version = int(lvds_fw_version)
    print("lvds firmware version = ", lvds_fw_version, hex(fpga_version))

    # B7 and older version do not have support for NTSC frequencies
    if fpga_version <= 0xB7:
        test_framerates = ["25", "30", "50", "60"]
        test_gstream_framerates = ["25/1", "30/1", "50/1", "60/1"]
        check_framerates = [25, 30, 50, 60]
    else:
        test_framerates = ["25", "29", "30", "50", "59", "60"]
        test_gstream_framerates = ["25/1", "30000/1001", "30/1", "50/1", "60000/1001", "60/1"]
        check_framerates = [25, 29.97, 30, 50, 59.94, 60]

    cnt_match = 0
    cnt_close = 0
    cnt_similar = 0
    cnt_diff = 0
    cnt_fail = 0

    for resolution_str, setting in zoomblock_settings_dict.items():

        # if (resolution_str != "1080p30" and resolution_str != "1080p50"):
        #    continue
        
        fps_list_in_vs_pipe = []
        fps_list_in_vs_cv = []
        fps_list_in_vs_get = []
        for i in range(test_cnt):
            time.sleep(gap)
            if verbose:
                set_resolution(lvds_serial_device, resolution_str, brand)
            else:
                with open(os.devnull, 'w') as f, redirect_stdout(f):
                    set_resolution(lvds_serial_device, resolution_str, brand)
            w, h, fps = get_resolution_tuple(lvds_device_path)
            if setting[0]==w and setting[1]==h:
                if setting[2]==fps:
                    cnt_match +=1
                elif math.fabs(setting[2] - fps)<=FPS_CLOSE:
                    cnt_close +=1
                elif math.fabs(setting[2] - fps)<=FPS_THRESHOLD:
                    cnt_similar +=1
                else:
                    cnt_diff +=1
            else:
                cnt_fail +=1
            fps_list_in_vs_get.append(setting[2] - fps)

            pipe_fps, cv_fps = get_fps_cv_gst(setting[0], setting[1], setting[2]) 
            fps_list_in_vs_pipe.append(setting[2] - pipe_fps)
            fps_list_in_vs_cv.append(setting[2] - cv_fps)
            # print("OpenCV fps = ", cv_fps)

        mean_get = statistics.mean(fps_list_in_vs_get)          
        std_get = statistics.stdev(fps_list_in_vs_get)          
        mean_pipe = statistics.mean(fps_list_in_vs_pipe)          
        std_pipe = statistics.stdev(fps_list_in_vs_pipe)          
        mean_cv = statistics.mean(fps_list_in_vs_cv)          
        std_cv = statistics.stdev(fps_list_in_vs_cv)          
        print(f"{setting} stats, set/get diff = {mean_get:.4f}, {std_get:.4f}, gst diff = {mean_pipe:.4f}, {std_pipe:.4f}, OpenCV diff = {mean_cv:.4f}, {std_cv:.4f}")

    print(f"Resolution and fps visca set / get stats:  match = {cnt_match}, very close = {cnt_close}, similar = {cnt_similar}, diff = {cnt_diff}, fail = {cnt_fail}")


"""
    def test_01_h_reboots(scailx: Scailx):
    
        imx_num = 0
        link_num = 1
        FPGA_board = "01"
        reboot_count_total = 500
        frame_height = "1080"
        frame_width = "1920"
        frame_rate = "60"
        stream_test_frames = 610
    
        max_normal_reboot_time = 50
        max_medium_reboot_time = 75
    
        log_percentage = 10
        log_count = reboot_count_total * log_percentage / 100
    
        scailx[imx_num].check_setup(link_num)
        dev_num = scailx[imx_num].fpga[link_num].device_number
    
        scailx[imx_num].set_resolution(link_num, frame_height, frame_rate)
        # Give the camera time to respond to the new resolution.
        time.sleep(1)
    
        reboot_count = 0
        unstable_count = 0
        incorrect_fps_count = 0
        incorrect_parm_count = 0
        long_reboot_count = 0
        medium_reboot_count = 0
        reboot_time = 0
        reboot_time_accurate = None
        reboot_time_acc_seconds = 0
    
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
        print(f"TEST reboot write fps_stats_{timestamp} header")
        output_file = f"output/fps_stats_{timestamp}.txt"
        with open(output_file, "w") as f:
                f.write(f"{timestamp}\n"
                        f"imx: {scailx[imx_num].id}\n"
                        f"ip: {scailx[imx_num].ip}\n"
                        f"FPGA: {FPGA_board}\t"
                            f"Version: {scailx[imx_num].fpga[link_num].firmware_version}\t"
                            f"Link number: {link_num}\t"
                            f"Device number: {scailx[imx_num].fpga[link_num].device_number}\n"
                        f"Camera: {scailx[imx_num].fpga[link_num].brand}\n"
                        f"Model: {scailx[imx_num].fpga[link_num].model}\n\n")
    
        scailx[imx_num].ssh.upload_file("sources/read_data.py", "/tmp/read_data.py")
        scailx[imx_num].ssh.upload_file("sources/get_serial_info.py", "/tmp/get_serial_info.py")
    
        try:
            for i in range(reboot_count_total):
                _, old_dmesg = scailx[imx_num].run("dmesg")
    
                stream_command_1 = f"v4l2-ctl --device /dev/video{dev_num}"
                stream_command_2 = f"v4l2-ctl --device /dev/video{dev_num} --set-fmt-video=width={frame_width},height={frame_height},pixelformat=NV12"
                stream_command_3 = f"v4l2-ctl --device /dev/video{dev_num} --stream-mmap=3 --stream-count={stream_test_frames} --stream-to=/dev/null"
                scailx[imx_num].run(stream_command_1)
                scailx[imx_num].run(stream_command_2)
                _, output = scailx[imx_num].run(stream_command_3)
    
                if "<<<<" not in output:
                    _, dmesg_out = scailx[imx_num].run("dmesg")
                    dmesg_out = dmesg_out[len(old_dmesg):]
                    pytest.fail(
                        f"Stream failed at FPGA {scailx[imx_num].id}{link_num}\n"
                        f"Command:\n"
                        f"{stream_command_1}\n"
                        f"{stream_command_2}\n"
                        f"{stream_command_3}\n"
                        f"Output:\n"
                        f"{output}\n"
                        f"Dmesg:\n"
                        f"{dmesg_out}\n"
                    )
    
                try:
                    _, get_parm_output = scailx[imx_num].run(
                        f"v4l2-ctl --device /dev/video{dev_num} --get-parm")
                    get_parm_fps = int(float(get_parm_output.splitlines()[2].split(' ')[3]))
                except Exception:
                    pytest.fail(
                    f"--get-parm failed at FPGA {scailx[imx_num].id}{link_num}",
                    pytrace=True
                )
    
                framerates = []
                for line in output.splitlines():
                    split_line = line.split()
                    if len(split_line) == 3:
                        framerates.append(float(line.split()[-2]))
    
                try:
                    avg = statistics.mean(framerates)
                    var = statistics.pvariance(framerates)
                except Exception:
                    print(f'Output:\n{output}')
    
                framerates_string = ' '.join(f'{fps:5.2f}' for fps in framerates)
    
                print(framerates_string)
                print(f"Average: {avg:.2f}Hz")
                print(f"Variance: {var:.4f}")
                print(f"get_parm: {get_parm_fps:d}Hz")
    
                stable_fps = var < 0.001
                if not stable_fps:
                    unstable_count += 1
    
                avg_fps_correct = int(frame_rate) * 0.999 <= avg <= int(frame_rate) * 1.001
                if not avg_fps_correct:
                    incorrect_fps_count += 1
    
                get_parm_correct = get_parm_fps == int(frame_rate)
                if not get_parm_correct:
                    incorrect_parm_count += 1
    
                normal_reboot = reboot_time_acc_seconds <= max_normal_reboot_time
                if not normal_reboot:
                    if reboot_time_acc_seconds <= max_medium_reboot_time:
                        medium_reboot_count += 1
                    else:
                        long_reboot_count += 1
    
                with open(output_file, "a") as f:
                    f.write(f"{i:2} Reboot time: {reboot_time:3}\t"
                            f"get_param: {get_parm_fps}\t"
                            f"Avg: {avg:.2f}\t"
                            f"Variance: {var:.4f}\t"
                            f"Stable: {stable_fps:1}\t"
                            f"Correct FPS: {avg_fps_correct:1}\t"
                            f"Correct get_parm: {get_parm_correct:1}\t"
                            f"Normal reboot: {normal_reboot:1}\t"
                            f"Reboot time Accurate: {reboot_time_accurate}\n\t\t"
                            f"FPS: {framerates_string}\n")
    
                time.sleep(random.random())
                time_before_reboot = datetime.now()
                reboot_time, reboot_done_time = scailx[imx_num].reboot(retries=200, base_delay = 2, log_reboot=True)
                reboot_time_accurate = reboot_done_time - time_before_reboot
                reboot_time_acc_seconds = reboot_time_accurate.total_seconds()
                scailx[imx_num].ssh.upload_file("sources/read_data.py", "/tmp/read_data.py")
                scailx[imx_num].ssh.upload_file("sources/get_serial_info.py", "/tmp/get_serial_info.py")
                scailx[imx_num].check_setup(link_num)
                if reboot_count % log_count == 0:
                    logging.info(f"Reboot {reboot_count} is done {reboot_done_time}\n")
                reboot_count += 1
    
    
        except Exception as e:
            print(f"Exception: {e}")
        finally:
            end_time = datetime.now().strftime("%Y-%m-%d_%H-%M")
            end_text = (f"\n{end_time}\n"
                        f"Total reboots:\t\t\t{reboot_count+1}\n"
                        f"Total unstable counts:\t\t{unstable_count}\n"
                        f"Total incorrect fps:\t\t{incorrect_fps_count}\n"
                        f"Total incorrect get_parms:\t{incorrect_parm_count}\n"
                        f"Total medium reboots:\t\t{medium_reboot_count}\n"
                        f"Total long reboots:\t\t{long_reboot_count}\n")
            print(end_text)
            with open(output_file, "a") as f:
                    f.write(end_text)
    
            if long_reboot_count > 0:
               pytest.fail(f"Reboot test failed. Long reboots detected:\n{end_text}")
"""