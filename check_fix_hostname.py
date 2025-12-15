#!/usr/bin/env python3

"""

File:   check_fix_hostname.py

Check Scailx camera hostname conflict using "avahi".
Optinal fix the conflict if it is detected.
Reboot camera to make it effective. 

Usage:

    python3 check_fix_hostname.py -h    (see help)
    
    python3 check_fix_hostname.py       (just show conflict and hosname)
    
    python3 check_fix_hostname.py -i 1     (show conflict, hosname, and IP addres)

    python3 check_fix_hostname.py -i 1 -f 1   (show conflict and fix it. Reboot camera to be effective.)

"""

import argparse
import time
import subprocess
import socket


def run_avahi():
    result = subprocess.run(
        ["systemctl", "status", "avahi-daemon", "|", "grep", "-i", '"Host name"'],
        capture_output=True,
        text=True,
    )
    res = result.stdout
    # print(res)

    keys = "Host name is"
    id = res.find(keys)
    if id >= 0:
        # Find match and hostname
        subs = res[id + len(keys) + 1 :]
        # print(subs)
        hostname = subs.split(" ")[0]
        # remove last '.'
        hostname = hostname[:-1]
    else:
        hostname = ""

    if "conflict" in res:
        return True, hostname
    else:
        return False, hostname


def fix_hostname(hostname):
    # set hostname
    res1 = subprocess.run(["hostnamectl", "set-hostname", hostname])

    res2 = subprocess.run(
        ["hostnamectl"],
        capture_output=True,
        text=True,
    )
    return res2.stdout


if __name__ == "__main__":

    parser = argparse.ArgumentParser(
        description="Check hostname conflict by avahi and fix it",
        prog="check_fix_hostname",
    )
    parser.add_argument(
        "-p", "--prefix", type=str, default="scailx-ai", help="hostname prefix"
    )
    parser.add_argument(
        "-i", "--ipaddress", type=int, default=0, help="Show IP address"
    )
    parser.add_argument(
        "-f", "--fix", type=int, default=0, help="Fix hostname conflict"
    )

    args = parser.parse_args()

    # Run avahi to get status string.
    conflict, hostname = run_avahi()

    print(f"Conflict = {conflict}, hostname = {hostname}")

    if args.ipaddress:
        ip = ip_address = socket.gethostbyname_ex(hostname)[2][0]
        print("IP address = ", ip)

    if conflict and args.fix:
        res = fix_hostname(hostname)
        print(res)
