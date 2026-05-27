"""

File:   get_camera_v4l2_paras.py

2026.0527.  Added core function to parse 'media-ctl -p' command outputs.

By:			jye@videologyinc.com

"""

import argparse
import json
import subprocess
import re

# Camera driver names with extrac 'streams' line in media-ctl command outputs.
Driver_Streams_List = ["gs_ar0234", "crosslink", "flir_boson"]

# Run media-ctl command and get entities containing above 3 camera driver names.
# return dict of detected entities.
def parse_media_ctl(device=None):
    cmd = ['media-ctl', '-p']
    if device:
        cmd.extend(['-d', device])
    
    # Run the command and capture output
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"media-ctl failed: {result.stderr}")
    
    output = result.stdout
    topology = {
        'device_info': {},
        'entities': {}
    }
    
    # Regex patterns
    entity_regex = re.compile(r"entity\s+(\d+):\s+(\w+)")
    type_regex = re.compile(r"type\s+(.*?)\s+subtype\s+(.*?)\s+flags\s+(.*)")
    node_regex = re.compile(r"device node name\s+(.*)")
    pad_regex = re.compile(r"\s+pad(\d+):\s+(Sink|Source)")
    format_regex = re.compile(r"\[stream:(.*?)/(.*?) field:(.*?)\]")
    linkto_regex = re.compile(r"->\s+\"(.*?)\":(\d+)\s+\[(.*?)\]")
    linkfrom_regex = re.compile(r"<-\s+\"(.*?)\":(\d+)\s+\[(.*?)\]")

    current_entity_id = None
    
    for line in output.splitlines():
        # Parse Device Information Header
        if line.startswith("Media device information"):
            continue
        if "driver" in line or "model" in line:
            parts = line.strip().split(':', 1)
            if len(parts) == 2:
                topology['device_info'][parts[0].strip()] = parts[1].strip()

        # Parse Entities
        entity_match = entity_regex.search(line)
        if entity_match:
            current_entity_id = int(entity_match.group(1))
            name = entity_match.group(2).strip()

            # print(current_entity_id, name)

            if name not in Driver_Streams_List:
                current_entity_id = None
                continue
            topology['entities'][current_entity_id] = {
                'name': name,
                'pads': {},
            }
            continue
            
        if current_entity_id is not None:
            # Parse Entity details
            if "type" in line:
                t_match = type_regex.search(line)
                if t_match:
                    topology['entities'][current_entity_id]['type'] = t_match.group(1).strip()
                    topology['entities'][current_entity_id]['subtype'] = t_match.group(2).strip()
                    topology['entities'][current_entity_id]['flags'] = t_match.group(3).strip()
            
            elif "device node name" in line:
                n_match = node_regex.search(line)
                if n_match:
                    topology['entities'][current_entity_id]['device_node'] = n_match.group(1).strip()
            
            # Parse Pads
            elif "pad" in line:
                p_match = pad_regex.search(line)
                if p_match:
                    pad_id = int(p_match.group(1))
                    pad_type = p_match.group(2)
                    topology['entities'][current_entity_id]['pads'][pad_id] = {
                        'type': pad_type,
                        'link': {}
                    }
            
            # Parse Formats
            elif ("[stream:" in line) and (pad_id is not None):
                has_stream = 1
            # Parse Links
            elif ("->" in line) and (pad_id is not None) and (has_stream is not None):
                l_match = linkto_regex.search(line)
                if l_match:
                    topology['entities'][current_entity_id]['pads'][pad_id]['link'] = {
                        'target_entity': l_match.group(1),
                        'target_pad': int(l_match.group(2)),
                        'flags': l_match.group(3).split(',')
                    }
            elif ("<-" in line) and (pad_id is not None) and (has_stream is not None):
                l_match = linkfrom_regex.search(line)
                if l_match:
                    topology['entities'][current_entity_id]['pads'][pad_id]['link'] = {
                        'source_entity': l_match.group(1),
                        'source_pad': int(l_match.group(2)),
                        'flags': l_match.group(3).split(',')
                    }

    for key, val in topology['entities'].items():
        for kp in list(val['pads'].keys()):
            if val['pads'][kp]['link']=={}:
                val['pads'].pop(kp)

    return topology

# Given detected entities, extract camera path and subdev path with v4l2 controls.
def extract_subdev(topo):
    ret_list = []
    for key, val in topo["entities"].items():
        # print(val)
        name = val["name"]
        mipi = val["pads"][0]["link"]["target_entity"]
        subdev = val["device_node"]
        ret_list.append((name, mipi, subdev))
    
    return ret_list


# Example usage
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Get camera v4l2 parameters using media-ct command outputs",
        prog="get_camera_v4l2_paras",
    )
    parser.add_argument(
        "-t", "--topology", type=int, default=0, help="Show topology. Default = 0 (off)"
    )
    args = parser.parse_args()

    parsed_topology = parse_media_ctl()
    if args.topology:
        print(json.dumps(parsed_topology, indent=4))

    subdev_list = extract_subdev(parsed_topology)
    print(subdev_list)
