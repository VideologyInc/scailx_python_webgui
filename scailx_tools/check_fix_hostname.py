#!/usr/bin/env python3

"""

File:   check_fix_hostname.py

By:			jye@videologyinc.com

Check Scailx camera hostname conflict using "avahi".
Optinal fix the conflict if it is detected.
Reboot camera to make it effective.

2026.0303.  Added new option '--mac 1' to change hostname using MAC address.

Usage:

    python3 check_fix_hostname.py -h    (See help.)

    python3 check_fix_hostname.py       (Just show conflict and hosname.)

    python3 check_fix_hostname.py -i 1     (Show conflict, hosname, IP addres and MAC address.)

    python3 check_fix_hostname.py --mac 1    (Change hostname using MAC address last 6 chars such as scailx-0E9A92. Reboot to be effective.)

    python3 check_fix_hostname.py -i 1 -f 1   (Show conflict and fix it by avahi. Reboot scailx to be effective.)

"""

import argparse
import time
import subprocess
import socket

import uuid
import re


# Get MAC address from local device and return as 00:0C:C6:0E:9A:92.
def get_mac_address():
    """
    Get MAC address from local device and return as string like 00:0C:C6:0E:9A:92.

    Arguments:

    Returns:
    str --  MAC address in standard format string like 00:0C:C6:0E:9A:92. Or empty if error or not found.

    """

    # Get the MAC address as a 48-bit integer
    mac_num = uuid.getnode()

    # If getnode() fails to find an address, it might return a random number.
    # It's generally reliable for local execution.
    if mac_num == 0:
        print("MAC address not found or error occurred")
        return ""

    # Format the integer into a standard hex string with colons
    hex_mac = str(":".join(re.findall("..", "%012x" % mac_num)))
    return hex_mac.upper()


# Create mac based hostname like scalix-AABBCC
def get_mac_hostname(prefix, mac):
    """
    Given input user specified prefix and MAC address string, create mac based hostname like sca-AABBCC as return.

    Arguments:
    prefix  --  User input prefix such as scalix or sca. Recommented length >=3.
    mac     --  Standard format MAC address string from function get_mac_hostname().

    Returns:
    str --  Generated new hostname in the form of prefix + "-" + 6 chars of last 3 hex strings of MAC address.

    """

    if len(mac) != 17:
        return ""
    # Use last 6 chars 9:10 + 12:13 + 14:15
    mac_hostname = prefix + "-" + mac[9:11] + mac[12:14] + mac[15:]
    return mac_hostname


# Run hostname command to get local stored hostname
def run_hostname():
    """
    Run hostname command to get local stored hostname as return.

    Arguments:

    Returns:
    str --  Hostname returned by 'hostname' command.

    """

    result = subprocess.run(
        ["hostname"],
        capture_output=True,
        text=True,
    )
    res = result.stdout
    return res


# Run avahi command to get possible hostname conflict.
def run_avahi():
    """
    Run avahi command to get possible hostname conflict.

    Arguments:

    Returns:
    (bool, str) --  Bool flag = True if conflict detected, and detected hostname by avahi.

    Notes:
    The detected hostname by avahi and by hostname commands may be different sometimes before rebooting the scailx device.

    """

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


# Set new hostname using hostnamectl command.
def fix_hostname(hostname):
    """
    Given input new hostname, set hostname by hostnamectl command.

    Arguments:
    hostname  --  User input new hostname to change into.

    Returns:
    str --  Output message from hostnamectl command.

    """

    # set hostname
    res1 = subprocess.run(["hostnamectl", "set-hostname", hostname])

    res2 = subprocess.run(
        ["hostnamectl"],
        capture_output=True,
        text=True,
    )
    return res2.stdout


def check_hostname_exists(user_hostname):
    """
    Given input new hostname, check whether it already exists on the same network.
    Return bool flag and IP address to access.

    Arguments:
    user_hostname  --  User input new hostname to change into.

    Returns:
    (bool, str) --  Bool flag = True if hostname exists, and its IP address. Or = False if it does not exist, and empty string.

    """

    try:
        # Attempt to resolve the hostname to an IPv4 address
        ip_address = socket.gethostbyname(user_hostname)
        return True, ip_address
    except:
        # user_hostname not found. It is valid for us.
        return False, ""


# Change to new hostname
def change_hostname(user_hostname):
    """
    Given input new hostname, check whether it already exists on the same network. Change to new hostname if it does not exist.
    Return exists or hostnamectl command output messages.

    Arguments:
    user_hostname  --  User input new hostname to change into.

    Returns:
    str --  Warning message if hostname already exists. Or hostnamectl command output if it is changed successfully.

    """

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
    """
    check_fix_hostname.py main() function.

    With user inputs by argmenents, the program can just show hostname + IP address and whether it has conflicts.
    Or change it by avahi suggestion automatically.
    Or force changing it by user input.
    Or force changing it by prefix + "-" + MAC address last 6 chars.

    Usage examples:

    python3 check_fix_hostname.py -h    (See help.)

    python3 check_fix_hostname.py       (Just show conflict and hosname.)

    python3 check_fix_hostname.py -i 1     (Show conflict, hosname, IP addres and MAC address.)

    python3 check_fix_hostname.py --mac 1    (Change hostname using MAC address last 6 chars such as scailx-0E9A92. Reboot to be effective.)

    python3 check_fix_hostname.py -i 1 -f 1   (Show conflict and fix it by avahi. Reboot scailx to be effective.)

    """

    parser = argparse.ArgumentParser(
        description="Check hostname conflict by avahi and fix it",
        prog="check_fix_hostname",
    )
    parser.add_argument(
        "-p", "--prefix", type=str, default="sca", help="hostname prefix"
    )
    parser.add_argument(
        "-i", "--ipaddress", type=int, default=1, help="Show IP address"
    )
    parser.add_argument(
        "-f", "--fix", type=int, default=0, help="Fix hostname conflict"
    )

    parser.add_argument(
        "--mac",
        type=int,
        default=0,
        help="Change hostname using last 6 digits of MAC address",
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
    if args.mac and mac != "":
        mac_hostname = get_mac_hostname(args.prefix, mac)

    # New hostname format example = 	sca-0E9A92	(total 10 chars)
    if len(mac_hostname) >= 10:
        res = change_hostname(mac_hostname)
        print(
            "hostname of this device is changed. Please remember it and use it to access for ssh and on web / VLC player after reboot."
        )
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
