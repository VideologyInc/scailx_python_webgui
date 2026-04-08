"""

read_imx_json.py

Read imx parameters 'Window Name' and their values from a json file.

"""

import json

AEC_LIST = [
    "AEC Gain",
    "AEC ExposureTime",
    "AEC Sensitivity",
]
AWB_LIST = [
    "GAIN INPUT",
    "Offset INPUT",
]

IMX900_PARA = {
    "AEC Gain": "40.0",
    "AEC ExposureTime": "0.00957",
    "AEC Sensitivity": "100",
    "GAIN INPUT": "1.32,1.0,1.0,3.0",
    "Offset INPUT": "-29,-32,-33",
    "CPROC ON/OFF": "1",
    "Adjust brightness": "0",
    "Adjust contrast": "1.1",
    "Adjust saturation": "1.0",
    "Adjust HUE": "0",
}

IMX678_PARA = {
    "AEC Gain": "40.0",
    "AEC ExposureTime": "0.03072",
    "AEC Sensitivity": "100",
    "GAIN INPUT": "1.22,1.0,1.0,2.83",
    "Offset INPUT": "-36,-38,-29",
    "CPROC ON/OFF": "1",
    "Adjust brightness": "0",
    "Adjust contrast": "1.2",
    "Adjust saturation": "1.0",
    "Adjust HUE": "0",
}

DEFAULT_PARA = {
    "AEC Gain": "40.0",
    "AEC ExposureTime": "0.009",
    "AEC Sensitivity": "100",
    "GAIN INPUT": "1.3,1.0,1.0,2.83",
    "Offset INPUT": "-30,-30,-30",
    "CPROC ON/OFF": "1",
    "Adjust brightness": "0",
    "Adjust contrast": "1.0",
    "Adjust saturation": "1.0",
    "Adjust HUE": "0",
}

GRAY_PARA = {
    "AEC Gain": "40.0",
    "AEC ExposureTime": "0.009",
    "AEC Sensitivity": "100",
    "GAIN INPUT": "1.0,1.0,1.0,1.0",
    "Offset INPUT": "-30,-30,-30",
    "CPROC ON/OFF": "1",
    "Adjust brightness": "0",
    "Adjust contrast": "1.0",
    "Adjust saturation": "0.0",
    "Adjust HUE": "0",
}


# Set default parameters if json not found or read error.
def default_imx(camera_type):
    if camera_type == "imx900":
        return IMX900_PARA
    elif camera_type == "imx678":
        return IMX678_PARA
    elif camera_type == "imxgray":
        return GRAY_PARA
    else:
        return DEFAULT_PARA


# Parse data dict from json file.
def parse_imx(data_dict):

    return data_dict


def read_imx(filename):

    try:
        with open(filename, "r", encoding="utf-8") as file:
            data_dict = json.load(
                file
            )  # Deserialize the file data into a Python dictionary
            # print(data_dict)

            para_dict = parse_imx(data_dict)

            return para_dict

    except FileNotFoundError:
        print(f"Error: The file '{filename}' was not found.")
        return {}
    except json.JSONDecodeError:
        print(f"Error: Could not decode JSON from the file. Check file format.")
        return {}

    return {}

# Parse only interest line from vvget output message.
def parse_vvget_output(message, keyword):
    for s in message.splitlines():
        if keyword in s:
            return "a"+s+"\n" if s[0:2]=="ec" else s+"\n"
    return ""

# imx900 = read_imx("imx900.json")
# print(imx900)

# imx678 = read_imx("imx678.json")
# print(imx678)
