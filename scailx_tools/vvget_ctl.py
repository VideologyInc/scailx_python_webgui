#!/usr/bin/env python3

"""

File:   vvget_ctl.py

2026.0909.  Created a v4l2-ctl-like wrapper around vvget for Sony imx camera
            sensors (imx900 global shutter, imx678, imx662) that run through the
            Vivante ISP. Provides --list-ctrls / --get-ctrl / --set-ctrl so the
            portal can read and write imx controls the same way it uses v4l2-ctl
            for UVC/global-shutter cameras.

By:         mkkamarudin@videologyinc.com

Usage:
    vvget_ctl.py -d /dev/video0 --list-ctrls
    vvget_ctl.py -d /dev/video0 --list-ctrls --json
    vvget_ctl.py -d /dev/video0 --get-ctrl brightness
    vvget_ctl.py -d /dev/video0 --get-ctrl brightness,contrast
    vvget_ctl.py -d /dev/video0 --set-ctrl brightness=-20
    vvget_ctl.py -d /dev/video0 --set-ctrl brightness=-20,contrast=1.2

Notes:
    * vvget takes the numeric camera id (0 for /dev/video0), not the path.
    * imx controls come from the ISP, so vvget cannot report min/max/step;
      those ranges are defined in the CONTROLS table below and may need tuning
      against a real sensor.
    * Auto Exposure (AEC) / Auto White Balance (AWB) must be OFF before manual
      values in their group take effect, and CPROC must be ON before the color
      adjustments apply. This script enforces that ordering automatically.

"""

import argparse
import json
import subprocess
import sys


# ---------------------------------------------------------------------------
# Control metadata
# ---------------------------------------------------------------------------
# id     : v4l2-style lower_snake name exposed to callers / the portal.
# window : exact vvget "Window Name" (quoted on the command line).
# type   : 'int' | 'float' | 'bool'
# group  : 'cproc' -> needs CPROC ON before it applies.
#          'aec'   -> needs AEC On/Off = 0 before manual value applies.
#          'toggle'-> the on/off switch itself.
# min/max/step/default: ranges vvget can't report. Best-guess; verify on device.
CONTROLS = [
    # --- Color processing (CPROC) ---
    {"id": "brightness", "window": "Adjust brightness", "type": "int",
     "group": "cproc", "min": -128, "max": 127, "step": 1, "default": 0},
    {"id": "contrast", "window": "Adjust contrast", "type": "float",
     "group": "cproc", "min": 0.0, "max": 1.99, "step": 0.01, "default": 1.0},
    {"id": "saturation", "window": "Adjust saturation", "type": "float",
     "group": "cproc", "min": 0.0, "max": 1.99, "step": 0.01, "default": 1.0},
    {"id": "hue", "window": "Adjust HUE", "type": "int",
     "group": "cproc", "min": -128, "max": 127, "step": 1, "default": 0},

    # --- Auto exposure (AEC) manual values ---
    {"id": "gain", "window": "AEC Gain", "type": "float",
     "group": "aec", "min": 0.0, "max": 48.0, "step": 0.1, "default": 1.0},
    {"id": "exposure_time", "window": "AEC ExposureTime", "type": "float",
     "group": "aec", "min": 0.0, "max": 0.033, "step": 0.0001, "default": 0.009},
    {"id": "sensitivity", "window": "AEC Sensitivity", "type": "int",
     "group": "aec", "min": 100, "max": 3200, "step": 100, "default": 100},

    # --- Toggles ---
    {"id": "auto_exposure", "window": "AEC On/Off", "type": "bool",
     "group": "toggle", "min": 0, "max": 1, "step": 1, "default": 1},
    {"id": "auto_white_balance", "window": "AWB On/Off", "type": "bool",
     "group": "toggle", "min": 0, "max": 1, "step": 1, "default": 1},
    {"id": "color_processing", "window": "CPROC ON/OFF", "type": "bool",
     "group": "toggle", "min": 0, "max": 1, "step": 1, "default": 1},
    {"id": "gamma", "window": "GAMMA ON/OFF", "type": "bool",
     "group": "toggle", "min": 0, "max": 1, "step": 1, "default": 1},
    {"id": "denoise", "window": "DPF ON/OFF", "type": "bool",
     "group": "toggle", "min": 0, "max": 1, "step": 1, "default": 1},
]

CONTROL_BY_ID = {c["id"]: c for c in CONTROLS}

# vvget windows that gate a group.
AEC_ONOFF = "AEC On/Off"
AWB_ONOFF = "AWB On/Off"
CPROC_ONOFF = "CPROC ON/OFF"


# ---------------------------------------------------------------------------
# device / vvget plumbing
# ---------------------------------------------------------------------------
def device_to_id(device):
    """/dev/video0 -> 0 (the numeric id vvget expects)."""
    prefix = "/dev/video"
    if not device or not device.startswith(prefix):
        raise ValueError(f"Incorrect video device: {device}")
    try:
        return int(device[len(prefix):])
    except ValueError:
        raise ValueError(f"Incorrect video device: {device}")


def _run(cam_id, window, value=None):
    """Run vvget for one window (get if value is None, else set). Returns stdout.

    vvget usage is positional: `vvget <id> '<window>' '<param>'`. Two quirks of
    v1.00 handled here:
      * A value starting with '-' (negative brightness/hue, Offset INPUT vectors)
        is parsed as a flag and ignored. Prefixing it with a space dodges that;
        vvget's numeric parse strips the leading whitespace.
      * The 2-arg get form still prints an interactive prompt and reads stdin, so
        we feed it /dev/null to avoid hanging.
    """
    if value is None:
        cmd = f"vvget {cam_id} '{window}'"
    else:
        sval = str(value)
        if sval.startswith("-"):
            sval = " " + sval
        cmd = f"vvget {cam_id} '{window}' '{sval}'"
    result = subprocess.run(
        cmd, shell=True, capture_output=True, text=True, stdin=subprocess.DEVNULL
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"vvget failed ({cmd}): {result.stderr.strip() or result.stdout.strip()}"
        )
    return result.stdout


def _extract_value(stdout, window):
    """Pull the value out of vvget stdout for a given window name."""
    # Prefer the line that mentions the window name, else the first line with ':'.
    candidate = None
    for line in stdout.splitlines():
        if ":" not in line:
            continue
        if window.lower() in line.lower():
            candidate = line
            break
        if candidate is None:
            candidate = line
    if candidate is None:
        return ""
    return candidate.split(":", 1)[1].strip()


def _cast(ctrl, raw):
    """Cast a raw string value to the control's numeric type; fall back to raw."""
    raw = raw.strip().strip("[]")
    try:
        if ctrl["type"] == "int" or ctrl["type"] == "bool":
            return int(float(raw))
        if ctrl["type"] == "float":
            return float(raw)
    except (ValueError, TypeError):
        return raw
    return raw


def get_control(cam_id, ctrl):
    """Read one control's current value, cast to its type (None if unreadable).

    Some controls report nothing depending on state (e.g. manual AEC Gain while
    auto-exposure is on). Return None so callers/JSON emit null rather than ''.
    """
    stdout = _run(cam_id, ctrl["window"])
    raw = _extract_value(stdout, ctrl["window"])
    if raw == "":
        return None
    return _cast(ctrl, raw)


def _get_toggle(cam_id, window):
    """Read a raw on/off window as an int (0/1); -1 if unknown."""
    try:
        raw = _extract_value(_run(cam_id, window), window).strip().strip("[]")
        return int(float(raw))
    except (ValueError, RuntimeError, TypeError):
        return -1


def _ensure_off(cam_id, window, retries=10):
    """Turn an auto window off, polling until it reads 0 (AEC is unreliable)."""
    for _ in range(retries):
        if _get_toggle(cam_id, window) == 0:
            return True
        _run(cam_id, window, 0)
    return _get_toggle(cam_id, window) == 0


def _ensure_on(cam_id, window, retries=5):
    """Turn a window on, polling until it reads 1."""
    for _ in range(retries):
        if _get_toggle(cam_id, window) == 1:
            return True
        _run(cam_id, window, 1)
    return _get_toggle(cam_id, window) == 1


# ---------------------------------------------------------------------------
# operations (mirror v4l2-ctl)
# ---------------------------------------------------------------------------
def list_ctrls(cam_id, as_json=False):
    """--list-ctrls: dump every control with ranges + current value."""
    items = []
    for ctrl in CONTROLS:
        try:
            value = get_control(cam_id, ctrl)
        except RuntimeError:
            value = None
        items.append({
            "control": ctrl["window"],
            "id": ctrl["id"],
            "minimum": ctrl["min"],
            "maximum": ctrl["max"],
            "step": ctrl["step"],
            "default": ctrl["default"],
            "value": value,
        })

    if as_json:
        # Shape matches the portal's Control[] type for easy backend consumption.
        print(json.dumps(items, indent=2))
        return

    for it in items:
        print(
            f"{it['id']:<20} ({CONTROL_BY_ID[it['id']]['type']})".ljust(30)
            + f": min={it['minimum']} max={it['maximum']} step={it['step']} "
            + f"default={it['default']} value={it['value']}"
        )


def get_ctrls(cam_id, ids):
    """--get-ctrl id[,id...]: print 'id: value' lines (v4l2-ctl format)."""
    for cid in ids:
        ctrl = CONTROL_BY_ID.get(cid)
        if not ctrl:
            print(f"{cid}: unknown control", file=sys.stderr)
            continue
        print(f"{cid}: {get_control(cam_id, ctrl)}")


def set_ctrls(cam_id, pairs):
    """--set-ctrl id=value[,id=value...]: apply, honouring group ordering."""
    parsed = []
    for pair in pairs:
        if "=" not in pair:
            print(f"Skipping malformed pair: {pair}", file=sys.stderr)
            continue
        cid, value = pair.split("=", 1)
        cid, value = cid.strip(), value.strip()
        ctrl = CONTROL_BY_ID.get(cid)
        if not ctrl:
            print(f"Skipping unknown control: {cid}", file=sys.stderr)
            continue
        parsed.append((ctrl, value))

    if not parsed:
        return

    groups = {c["group"] for c, _ in parsed}
    explicit = {c["id"] for c, _ in parsed}

    # Pre-conditions, mirroring detect_imx_live.py ordering rules.
    if "cproc" in groups and "color_processing" not in explicit:
        _ensure_on(cam_id, CPROC_ONOFF)
    if "aec" in groups and "auto_exposure" not in explicit:
        # Manual AEC values only apply with auto exposure off.
        _ensure_off(cam_id, AEC_ONOFF)

    # Apply toggles first (so e.g. turning AWB off precedes its values), then rest.
    parsed.sort(key=lambda cv: 0 if cv[0]["group"] == "toggle" else 1)
    for ctrl, value in parsed:
        try:
            _run(cam_id, ctrl["window"], value)
            print(f"set {ctrl['id']} = {value}")
        except RuntimeError as e:
            print(f"failed to set {ctrl['id']}: {e}", file=sys.stderr)


# ---------------------------------------------------------------------------
# cli
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="v4l2-ctl-like control tool for Sony imx cameras via vvget",
        prog="vvget_ctl",
    )
    parser.add_argument(
        "-d", "--device", type=str, default="/dev/video0",
        help="camera device path, e.g. /dev/video0",
    )
    parser.add_argument(
        "--list-ctrls", action="store_true",
        help="list all controls with ranges and current values",
    )
    parser.add_argument(
        "--json", action="store_true",
        help="with --list-ctrls, emit JSON (portal Control[] shape)",
    )
    parser.add_argument(
        "--get-ctrl", type=str, default="",
        help="get control value(s): id or id,id,...",
    )
    parser.add_argument(
        "--set-ctrl", type=str, default="",
        help="set control value(s): id=value or id=value,id=value,...",
    )
    args = parser.parse_args()

    try:
        cam_id = device_to_id(args.device)
    except ValueError as e:
        print(e, file=sys.stderr)
        sys.exit(2)

    if args.list_ctrls:
        list_ctrls(cam_id, args.json)
    elif args.get_ctrl:
        get_ctrls(cam_id, [s.strip() for s in args.get_ctrl.split(",") if s.strip()])
    elif args.set_ctrl:
        set_ctrls(cam_id, [s.strip() for s in args.set_ctrl.split(",") if s.strip()])
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
