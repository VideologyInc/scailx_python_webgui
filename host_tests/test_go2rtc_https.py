"""

File:   test_go2rtc_https.py

2026.0619.  Created to use OpenCV open go2rtc https stream strings using mjpeg over http protocol.

By:			jye@videologyinc.com

"""

import argparse
import json
import yaml
import subprocess

import cv2


# Run subprocess scp to get cam_config.yaml from scailx device.
def get_yaml_from_scailx(hostname):
    cmd = "root@" + hostname + ":/var/tmp/cam_config.yaml"
    # cp remote file to current location same name.
    command = ["scp", cmd, "."]

    # Run the system command
    result = subprocess.run(command, capture_output=True, text=True)

    if result.returncode == 0:
        return "cam_config.yaml"
    else:
        return ""


# Parse cam_config.yaml contents to dict.
def parse_camera_yaml(cam_config_name):
    try:
        with open(cam_config_name, "r") as file:
            cam_config_dict = yaml.safe_load(file)
            return cam_config_dict["streams"] if "streams" in cam_config_dict else {}
        return {}
    except:
        return {}


# Open stream and Grab one frame.
def open_go2rtc_frame(stream_url):
    cap = cv2.VideoCapture(stream_url)

    while cap.isOpened():
        ret, frame = cap.read()
        if ret and frame is not None:
            cap.release()
            cv2.destroyAllWindows()
            return True, frame.shape
        else:
            cap.release()
            cv2.destroyAllWindows()
            return False, None

    return False


# Given stream name list, test it one by one by grabbing one frame each.
def test_yaml_streams(stream_prefix, stream_names):

    for name in stream_names:
        url = stream_prefix + str(name)
        ret, shape = open_go2rtc_frame(url)
        print(name, "=>", ret, shape)


def open_go2rtc_stream(stream_url):
    cap = cv2.VideoCapture(stream_url)

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        # Process your frame here with OpenCV
        cv2.imshow("go2rtc Stream", frame)

        if cv2.waitKey(1) == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":

    parser = argparse.ArgumentParser(
        description="Test go2rtc Camera Streams",
        prog="test_go2rtc_https",
    )

    parser.add_argument(
        "-v", "--video", type=int, default=0, help="Display video stream. Default = 0."
    )

    parser.add_argument(
        "--hostname",
        type=str,
        default="scailx-ai.local",
        help="hostname or IP adddress of the scailx device",
    )

    parser.add_argument(
        "-p",
        "--protocol",
        type=int,
        default=0,
        help="go2rtc endpoint protocol: 0 = rtsp, 1 = flv, 2 = jpeg",
    )

    parser.add_argument(
        "-s", "--stream", type=str, default="", help="go2rtc 1984 web https string"
    )

    parser.add_argument(
        "-y",
        "--yaml",
        type=str,
        default="cam_config.yaml",
        help="Get camera config yaml same as go2rtc.service input.",
    )

    args = parser.parse_args()

    yaml_name = ""
    if args.hostname:
        yaml_name = get_yaml_from_scailx(args.hostname)

    if yaml_name != "":
        cam_config_dict = parse_camera_yaml(yaml_name)
    elif args.yaml != "":
        cam_config_dict = parse_camera_yaml(args.yaml)

    # print(json.dumps(cam_config_dict, indent=4))

    n = len(cam_config_dict.keys())
    if n > 0:
        print(f"Camera config yaml file with {n} settings loaded.")

    stream_str_list = [
        "rtsp://" + args.hostname + ":8554/",
        "http://" + args.hostname + ":1984/api/stream.flv?src=",
        "http://" + args.hostname + ":1984/api/frame.jpeg?src=",
    ]

    # View one stream.
    # args.stream = "cam0-gs-AR0234_0_1920x1080_NV12_fps=60"
    if args.video == 1:
        if args.stream != "":
            stream_url = stream_str_list[args.protocol] + args.stream
            open_go2rtc_stream(stream_url)
        elif n > 0:
            stream_url = (
                stream_str_list[args.protocol] + list(cam_config_dict.keys())[0]
            )
            open_go2rtc_stream(stream_url)

    # Use jpeg to grab one frame of each stream to test.
    test_yaml_streams(stream_str_list[2], cam_config_dict.keys())
