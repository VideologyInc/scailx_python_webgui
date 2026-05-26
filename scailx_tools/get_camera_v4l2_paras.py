
import subprocess
import re

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
    entity_regex = re.compile(r"entity\s+(\d+):\s+(.+?)\s+\((\d+)\s+pads?,\s+(\d+)\s+links?\)")
    type_regex = re.compile(r"type\s+(.*?)\s+subtype\s+(.*?)\s+flags\s+(.*)")
    node_regex = re.compile(r"device node name\s+(.*)")
    pad_regex = re.compile(r"\s+pad(\d+):\s+(Sink|Source)")
    format_regex = re.compile(r"\[fmt:(.*?)/(.*?) field:(.*?)\]")
    link_regex = re.compile(r"->\s+\"(.*?)\":(\d+)\s+\[(.*?)\]")

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
            topology['entities'][current_entity_id] = {
                'name': entity_match.group(2).strip(),
                'pads': {},
                'links': []
            }
            continue
            
        if current_entity_id is not None:
            # Parse Entity details
            if "type" in line:
                t_match = type_regex.search(line)
                if t_match:
                    topology['entities'][current_entity_id].update({
                        'type': t_match.group(1).strip(),
                        'subtype': t_match.group(2).strip(),
                        'flags': t_match.group(3).strip()
                    })
            
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
                        'format': None,
                        'links': []
                    }
            
            # Parse Formats
            elif "[fmt:" in line:
                f_match = format_regex.search(line)
                if f_match and 'pads' in topology['entities'][current_entity_id]:
                    latest_pad = max(topology['entities'][current_entity_id]['pads'].keys())
                    topology['entities'][current_entity_id]['pads'][latest_pad]['format'] = {
                        'mbus_code': f_match.group(1),
                        'resolution': f_match.group(2),
                        'field': f_match.group(3)
                    }
            
            # Parse Links
            elif "->" in line:
                l_match = link_regex.search(line)
                if l_match:
                    topology['entities'][current_entity_id]['links'].append({
                        'target_entity': l_match.group(1),
                        'target_pad': int(l_match.group(2)),
                        'flags': l_match.group(3).split(',')
                    })

    return topology

# Example usage
if __name__ == "__main__":
    import json
    parsed_topology = parse_media_ctl()
    print(json.dumps(parsed_topology, indent=2))
