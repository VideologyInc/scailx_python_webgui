#! /usr/bin/env pyhton3

#===================================
# crosslink serial tcpserver
# I2C-serial <-> tcp server
#===================================

import select
import socket
import argparse
import logging
import sys
import socketserver
import time
import threading
import glob
from crosslink_visca import CrosslinkSerial

logging.basicConfig(level=logging.DEBUG)

class ViscaUdpHandler(socketserver.BaseRequestHandler):
    def handle(self):
        data = bytearray(self.request[0])
        recv = self.server.crtvv.transceive(data)
        logging.debug('recv: %s', recv)
        self.request[1].sendto(recv, self.client_address)

class ViscaUdpServer(socketserver.UDPServer):
    def __init__(self, server_address, RequestHandlerClass, crosslinkdev: CrosslinkSerial):
        super().__init__(server_address, RequestHandlerClass)
        self.crtvv = crosslinkdev

class ViscaTcpHandler(socketserver.BaseRequestHandler):
    def handle(self):
        data = bytearray(self.request.recv(1024).strip())
        recv = self.server.crtvv.transceive(data)
        logging.debug('recv: %s', recv)
        self.request.sendall(recv)

class ViscaTcpServer(socketserver.TCPServer):
    def __init__(self, server_address, RequestHandlerClass, crosslinkdev: CrosslinkSerial):
        super().__init__(server_address, RequestHandlerClass)
        self.crtvv = crosslinkdev


def main():
    """Main"""
    # parser = argparse.ArgumentParser(description='Crosslink Serial TCP Server')
    # parser.add_argument( 'server_port', type=int, help="server port", default=52381)

    # args = parser.parse_args()
    crosslinks = glob.glob('/dev/links/crosslink_mipi*')
    if len(crosslinks) == 0:
        print('No crosslink devices found')
        sys.exit(1)

    crtvv = CrosslinkSerial(crosslinks[0])

    with ViscaTcpServer(('', 52381), ViscaTcpHandler, crtvv) as server:
        ip, port = server.server_address
        logging.info('server started at %s:%s', ip, port)
        server.serve_forever()


if __name__ == '__main__':

    main()