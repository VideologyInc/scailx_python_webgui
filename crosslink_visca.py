#! /usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0
#
# ioctl based access to I2C <-> Serial adapter of the FPGA.
#

from time import sleep, time_ns
import argparse
import threading
import fcntl
import ctypes

# Define the struct
class CrosslinkIoctlSerial(ctypes.Structure):
    _fields_ = [
        ("len", ctypes.c_uint32),
        ("data", ctypes.c_uint8 * 64),
    ]

# # define UART status bits
# CROSSLINK_UART_STAT_BUSY_TX       = 0b0010_0000
# CROSSLINK_UART_STAT_BUSY_RX       = 0b0001_0000
# CROSSLINK_UART_STAT_DATA_FULLTX   = 0b0000_1000
# CROSSLINK_UART_STAT_DATA_EMPTYTX  = 0b0000_0100
# CROSSLINK_UART_STAT_DATA_FULLRX   = 0b0000_0010
# CROSSLINK_UART_STAT_DATA_EMPTYRX  = 0b0000_0001

# Define the IOCTL commands
CROSSLINK_CMD_SERIAL_SEND_TX    = 0x7601
CROSSLINK_CMD_SERIAL_RECV_RX    = 0x7602
CROSSLINK_CMD_SERIAL_RX_CNT     = 0x7603
CROSSLINK_CMD_SERIAL_BAUD       = 0x7604

class CrosslinkSerial():
    def __init__(self, dev_path, start_wait_ms=100, stop_wait_ms=25, baud=9600):
        self.lock = threading.Lock()
        self.dev = dev
        self.baud = baud
        self.bwms = start_wait_ms
        self.ewms = stop_wait_ms
        self.set_baud(self.dev, self.baud)
        self.recv(self.dev)        # clear RX fifo

    # Open the device file
    def send(self, data: bytes):
        ioctl_serial = CrosslinkIoctlSerial()
        ioctl_serial.len = len(data)
        ioctl_serial.data = (ctypes.c_uint8 * 64)(*data)
        # Call an IOCTL
        with open(self.dev) as f:
            fcntl.ioctl(f, CROSSLINK_CMD_SERIAL_SEND_TX, ioctl_serial)

    def recv(self, count:int=0):
        ioctl_serial = CrosslinkIoctlSerial()
        ioctl_serial.len = count
        with open(self.dev) as f:
            fcntl.ioctl(f, CROSSLINK_CMD_SERIAL_RECV_RX, ioctl_serial)
        return bytes(ioctl_serial.data[:ioctl_serial.len])

    def get_rx_count(self):
        ioctl_serial = CrosslinkIoctlSerial()
        with open(self.dev) as f:
            fcntl.ioctl(f, CROSSLINK_CMD_SERIAL_RX_CNT, ioctl_serial)
        return ioctl_serial.len

    def get_baud(self):
        ioctl_serial = CrosslinkIoctlSerial()
        with open(self.dev) as f:
            fcntl.ioctl(f, CROSSLINK_CMD_SERIAL_BAUD, ioctl_serial)
        return ioctl_serial.len

    def set_baud(self, baud:int):
        ioctl_serial = CrosslinkIoctlSerial()
        ioctl_serial.len = baud
        with open(self.dev) as f:
            fcntl.ioctl(f, CROSSLINK_CMD_SERIAL_BAUD, ioctl_serial)

    def wait_for_rx_stable(self, start_wait_ms, stop_wait_ms):
        start = time_ns()
        while get_rx_count(self.dev) == 0:
            sleep(0.002)
            if time_ns() - start > start_wait_ms*1e6:
                return False
        byte_count = get_rx_count(self.dev)
        start = time_ns()
        while time_ns() - start < stop_wait_ms*1e6:
            sleep(0.002)
            cnt = get_rx_count(self.dev)
            if cnt != byte_count:
                byte_count = cnt
                start = time_ns()
        return True

    def transceive(self, data: bytes, count:int=0, start_wait_ms=self.bwms, stop_wait_ms=self.ewms):
        with self.lock:
            self.recv()
            self.send(data)
            self.wait_for_rx_stable(start_wait_ms, stop_wait_ms)
            data = self.recv(count)
        return data

def main():
    # get argparse for dev, baudrate, data
    parser = argparse.ArgumentParser(prog='Crosslink_Visca')
    parser.add_argument('-d', '--dev', type=str, default="/dev/v4l-subdev1", help='device path')
    parser.add_argument('-t', '--timeout', type=int, default=100, help='read timeout to wait for RX data')
    parser.add_argument('data', type=str, help='data to send, as hex string')
    args = parser.parse_args()
    data = bytearray.fromhex(args.data)
    crtvx = CrosslinkSerial(args.dev)

    send(args.dev, data)

    wait_for_rx_stable(args.dev, args.timeout, args.timeout/4)
    count = get_rx_count(args.dev)
    data = recv(args.dev)
    print(data.hex())

if __name__ == "__main__":
    main()