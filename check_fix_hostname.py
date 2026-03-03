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

import uuid
import re

# Get MAC address from local device and return as 00:0C:C6:0E:9A:92.
def get_mac_address():
    # Get the MAC address as a 48-bit integer
    mac_num = uuid.getnode()

    # If getnode() fails to find an address, it might return a random number.
    # It's generally reliable for local execution.
    if mac_num == 0:
        print("MAC address not found or error occurred")
        return ""

    # Format the integer into a standard hex string with colons
    hex_mac = str(":".join(re.findall('..', '%012x' % mac_num)))
    return hex_mac.upper()

# Create mac based hostname like scalix-AABBCC
def get_mac_hostname(prefix, mac):
    if len(mac) !=17:
        return ""
    # Use last 6 chars 9:10 + 12:13 + 14:15
    mac_hostname = prefix + "-" + mac[9:11] + mac[12:14] + mac[15:]
    return mac_hostname


# Run hostname command to get local stored hostname
def run_hostname():
    result = subprocess.run(
        ["hostname"],
        capture_output=True,
        text=True,
    )
    res = result.stdout
    return res

# Run avahi command to get posisble hostname conflict.
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


# Set hostname by avahi output.
def fix_hostname(hostname):
    # set hostname
    res1 = subprocess.run(["hostnamectl", "set-hostname", hostname])

    res2 = subprocess.run(
        ["hostnamectl"],
        capture_output=True,
        text=True,
    )
    return res2.stdout


def check_hostname_exists(user_hostname):
    try:
        # Attempt to resolve the hostname to an IPv4 address
        ip_address = socket.gethostbyname(user_hostname)
        return True, ip_address
    except:
        # user_hostname not found. It is valid for us.
        return False, ""


# Change to new hostname
def change_hostname(user_hostname):
    # First need to check this new hostname unoccupied.
    res, ip_address = check_hostname_exists(user_hostname)
    if res:
        return f"{user_hostname} = {ip_address} exists. Please choose another one."

    # set new hostname
    res1 = subprocess.run(["hostnamectl", "set-hostname", user_hostname])

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
        "-p", "--prefix", type=str, default="scailx", help="hostname prefix"
    )
    parser.add_argument(
        "-i", "--ipaddress", type=int, default=1, help="Show IP address"
    )
    parser.add_argument(
        "-f", "--fix", type=int, default=0, help="Fix hostname conflict"
    )

    parser.add_argument(
        "--mac", type=int, default=0, help="Change hostname using last 6 digits of MAC address"
    )

    parser.add_argument(
        "-m",
        "--manualhostname",
        type=str,
        default="",
        help="Change hostname manually. Length must >=10",
    )

    args = parser.parse_args()

    # Run hostname command first
    print("Local stored hostname = ", run_hostname())

    # Run avahi to get status string.
    conflict, hostname = run_avahi()

    print(f"Conflict = {conflict}, avahi hostname = {hostname}")

    # Always show IP and MAC address ;-)
    mac = get_mac_address()
    if args.ipaddress:
        ip = ip_address = socket.gethostbyname_ex(hostname)[2][0]
        print("IP address = ", ip)
        print("MAC address = ", mac)

    # Force change host name using mac to scailx-AABBCC
    mac_hostname = ""
    if args.mac and mac !="":
        mac_hostname = get_mac_hostname(args.prefix, mac)

    if len(mac_hostname) >= 12:
        res = change_hostname(mac_hostname)
        print("hostname of this device is changed. Please remember it and use it to access for ssh and on web / VLC player after reboot.")
        print(res)
    # Force manual fix.
    elif args.fix and len(args.manualhostname) >= 10:
        # Fix by user entered hostname
        res = change_hostname(args.manualhostname)
        print(res)
    elif conflict and args.fix:
        # Fix by avahi automatically
        res = fix_hostname(hostname)
        print(res)
    else:
        print("No hostname conflict. No need to fix anything ;-)")
    