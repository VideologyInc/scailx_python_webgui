# server app
import http.server
import socketserver
import socket 
import time
import os
import base64
#import serial
import logging
import json
import psutil
import binascii
import subprocess, signal
from datetime import timezone
import datetime
 
import pickle

#-----------------------------------------------------------------------------------

from periphery import Serial
from time import sleep, time_ns
import argparse
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

#-----------------------------------------------------------------------------------
# Open the device file
def send(dev_path, data: bytes):
    ioctl_serial = CrosslinkIoctlSerial()
    ioctl_serial.len = len(data)
    ioctl_serial.data = (ctypes.c_uint8 * 64)(*data)
    # Call an IOCTL
    with open(dev_path) as f:
        fcntl.ioctl(f, CROSSLINK_CMD_SERIAL_SEND_TX, ioctl_serial)

def recv(dev_path, count:int=0):
    ioctl_serial = CrosslinkIoctlSerial()
    ioctl_serial.len = count
    with open(dev_path) as f:
        fcntl.ioctl(f, CROSSLINK_CMD_SERIAL_RECV_RX, ioctl_serial)
    return bytes(ioctl_serial.data[:ioctl_serial.len])

def get_rx_count(dev_path):
    ioctl_serial = CrosslinkIoctlSerial()
    with open(dev_path) as f:
        fcntl.ioctl(f, CROSSLINK_CMD_SERIAL_RX_CNT, ioctl_serial)
    return ioctl_serial.len

def get_baud(dev_path):
    ioctl_serial = CrosslinkIoctlSerial()
    with open(dev_path) as f:
        fcntl.ioctl(f, CROSSLINK_CMD_SERIAL_BAUD, ioctl_serial)
    return ioctl_serial.len

def set_baud(dev_path, baud:int):
    ioctl_serial = CrosslinkIoctlSerial()
    ioctl_serial.len = baud
    with open(dev_path) as f:
        fcntl.ioctl(f, CROSSLINK_CMD_SERIAL_BAUD, ioctl_serial)

def wait_for_rx_stable(dev_path, start_wait_ms, stop_wait_ms):
    start = time_ns()
    while get_rx_count(dev_path) == 0:
        sleep(0.002)
        if time_ns() - start > start_wait_ms*1e6:
            return False
    byte_count = get_rx_count(dev_path)
    start = time_ns()
    while time_ns() - start < stop_wait_ms*1e6:
        sleep(0.002)
        cnt = get_rx_count(dev_path)
        if cnt != byte_count:
            byte_count = cnt
            start = time_ns()
    return True

#-----------------------------------------------------------------------------------

#print("serial.__version__ = {}".format(serial.__version__))

PORT = 8089
DEV  = "/dev/v4l-subdev1"

max_temp = -40
min_temp = 120
max_temp_24h = -40
min_temp_24h = 120

cur_path = os.path.dirname(__file__)

#if(os.path.isfile(cur_path + "/temperature.p")):
#   min_temp, max_temp, min_temp_24h, max_temp_24h = pickle.load(open(os.path.dirname(__file__) + "/temperature.p","rb"))
#else:
#   pickle.dump([min_temp, max_temp, min_temp_24h, max_temp_24h], open(os.path.dirname(__file__) + "/temperature.p", "wb"))

pickle.dump([min_temp, max_temp, min_temp_24h, max_temp_24h], open(cur_path + "/temperature.p", "wb"))
 
print(min_temp)
print(max_temp)
print(min_temp_24h)
print(max_temp_24h)

def read_pickle():
  objects = []
  with (open(cur_path + "/time_temp.p", "rb")) as openfile:
      while True:
          try:
              objects.append(pickle.load(openfile))
          except EOFError:
              break


class HttpRequestHandler(http.server.SimpleHTTPRequestHandler):

    extensions_map = {
        '': 'application/octet-stream',
        '.manifest': 'text/cache-manifest',
        '.html': 'text/html',
        '.png': 'image/png',
        '.jpg': 'image/jpg',
        '.svg':	'image/svg+xml',
        '.css':	'text/css',
        '.js':'application/x-javascript',
        '.wasm': 'application/wasm',
        '.json': 'application/json',
        '.xml': 'application/xml',
    }

    def do_PUT(self):
        print("PUT request")

    def do_PATCH(self):
        print("PATCH request")

    def do_GET(self):

        global ser
        global visca_resp
        global min_temp, max_temp

#        ser = serial.Serial('/dev/ttyVISCA1', baudrate=9600, timeout=0)
        
        do_reply = False
        cur_path = os.path.dirname(__file__)
        if self.path == '/':
            self.path = '/index.html'
        if self.path.endswith('favicon.ico'):
            self.path = '/videologyinc_favicon.png'
        ctype = self.guess_type(self.path)
#        try:
#        print(self.path)

        if self.path.startswith('/imx8') == False:
 
                if self.path.endswith(".html"):
                    f = open(cur_path + self.path[0:]).read()
                    self.send_response(200)
                    self.send_header('Content-type',ctype)
                    self.end_headers()
                    self.wfile.write(bytes(f, 'utf-8'))
                    do_reply = True
                if self.path.endswith(".svg"):
                    f = open(cur_path + self.path[0:]).read()
                    self.send_response(200)
                    self.send_header('Content-type',ctype)
                    self.end_headers()
                    self.wfile.write(bytes(f, 'utf-8'))
                    do_reply = True
                if self.path.endswith(".png"):
                    f = open(cur_path + self.path[0:], 'rb').read()
                    self.send_response(200)
                    self.send_header('Content-type',ctype)
                    self.end_headers()
#                    self.wfile.write(bytes(f, 'utf-8'))
                    self.wfile.write(open(cur_path + self.path[0:],'rb').read())
                    do_reply = True
                if self.path.endswith(".jpg"):
#                    print('> '+cur_path+self.path[0:])
                    self.send_response(200)
                    self.send_header('Content-type',ctype)
                    self.end_headers()
                    self.wfile.write(open(cur_path + self.path[0:],'rb').read())
                    do_reply = True
                if self.path.endswith(".ttf"):
                    f = open(cur_path + self.path[0:], 'rb').read()
                    self.send_response(200)
                    self.send_header('Content-type',ctype)
                    self.end_headers()
                    self.wfile.write(bytes(f, 'utf-8'))
#                    self.wfile.write(open(cur_path + self.path[0:], 'rb').read())
                    do_reply = True
                if self.path.endswith(".woff"):
                    f = open(cur_path + self.path[0:], 'rb').read()
                    self.send_response(200)
                    self.send_header('Content-type',ctype)
                    self.end_headers()
                    self.wfile.write(bytes(f, 'utf-8'))
#                    self.wfile.write(open(cur_path + self.path[0:], 'rb').read())
                    do_reply = True
                if self.path.endswith(".woff2"):
                    f = open(cur_path + self.path[0:], 'rb').read()
                    self.send_response(200)
                    self.send_header('Content-type',ctype)
                    self.end_headers()
#                    self.wfile.write(bytes(f, 'utf-8'))
                    self.wfile.write(open(cur_path + self.path[0:], 'rb').read())
                    do_reply = True
                if self.path.endswith(".eot"):
                    f = open(cur_path + self.path[0:], 'rb').read()
                    self.send_response(200)
                    self.send_header('Content-type',ctype)
                    self.end_headers()
                    self.wfile.write(open(cur_path + self.path[0:], 'rb').read())
                    do_reply = True
                if self.path.endswith(".js"):
                    f = open(cur_path + self.path[0:], 'rb').read()
                    self.send_response(200)
                    self.send_header('Content-type',ctype)
                    self.end_headers()
                    self.wfile.write(open(cur_path + self.path[0:], 'rb').read())
                    do_reply = True
                if self.path.endswith(".otf"):
                    f = open(cur_path + self.path[0:], 'rb').read()
                    self.send_response(200)
                    self.send_header('Content-type',ctype)
                    self.end_headers()
                    self.wfile.write(open(cur_path + self.path[0:], 'rb').read())
                    do_reply = True

        else:
                if self.path.startswith('/imx8/frame.jpg'):
#                    print('> '+cur_path + '/imx8/frame.jpg')
                    self.send_response(200)
                    self.send_header('Content-type',ctype)
                    self.end_headers()
                    self.wfile.write(open(cur_path + '/frame.jpg','rb').read())
                    do_reply = True
                if self.path.startswith('/imx8/temperature'):
                    fd = open('/sys/devices/virtual/thermal/thermal_zone0/temp')
                    temp = 'data: '+str(int(fd.read())/1000) + '\n\n'
                    self.send_response(200)
                    self.send_header('Content-type', 'text/event-stream')
                    self.end_headers()
                    self.wfile.write(bytes(temp, 'utf-8'))

                if self.path.startswith('/imx8/uptime'):
                    upt = 'data: ' + str(uptime()) + '\n\n'
                    self.send_response(200)
                    self.send_header('Content-type', 'text/event-stream')
                    self.end_headers()
                    self.wfile.write(bytes(upt, 'utf-8'))

                if self.path.startswith('/imx8/visca_response'):
#                    with open("capture.py") as f:
#                        exec(f.read())

                    s = '{' + '"visca_response": "' + visca_resp + '"}'
                    print(s)
                    self.send_response(200)
                    self.send_header('Content-type', 'text/event-stream')
                    self.end_headers()
                    self.wfile.write(bytes('data: ' + s + '\n\n', 'utf-8'))


                if self.path.startswith('/imx8/_cameracontrol'):

                    send(DEV, b'\x81\x09\x04\x43\xFF')        #
                    while (ser.in_waiting == 0):
                       i=0
                    print(ser.in_waiting)
                    x = ser.read(ser.in_waiting)
                    CAM_RGain = "{0:0{1}x}".format(16*x[4]+x[5], 2)

                    send(DEV, b'\x81\x09\x04\x44\xFF')
                    while (ser.in_waiting == 0):
                       i=0
                    x = ser.read(ser.in_waiting)
                    CAM_BGain = "{0:0{1}x}".format(16*x[4]+x[5], 2)

                    send(DEV, b'\x81\x09\x04\x13\xFF')
                    while (ser.in_waiting == 0):
                       i=0
                    x = ser.read(ser.in_waiting)
                    CAM_Chroma = "{0:0{1}x}".format(16*x[4]+x[5], 2)

                    send(DEV, b'\x81\x09\x04\x4D\xFF')
                    while (ser.in_waiting == 0):
                       i=0
                    x = ser.read(ser.in_waiting)
                    CAM_Bright  = "{0:0{1}x}".format(16*x[4]+x[5], 2)

                    send(DEV, b'\x81\x09\x04\x42\xFF')
                    while (ser.in_waiting == 0):
                       i=0
                    x = ser.read(ser.in_waiting)
                    CAM_Aperture    = "{0:0{1}x}".format(16*x[4]+x[5], 2)

                    send(DEV, b'\x81\x09\x04\x4A\xFF')
                    while (ser.in_waiting == 0):
                       i=0
                    x = ser.read(ser.in_waiting)
                    CAM_Shutter     = "{0:0{1}x}".format(16*x[4]+x[5], 2)

                    send(DEV, b'\x81\x09\x04\x4B\xFF')
                    while (ser.in_waiting == 0):
                       i=0
                    x = ser.read(ser.in_waiting)
                    CAM_Iris    = "{0:0{1}x}".format(16*x[4]+x[5], 2)

                    send(DEV, b'\x81\x09\x04\x4C\xFF')
                    while (ser.in_waiting == 0):
                       i=0
                    x = ser.read(ser.in_waiting)
                    CAM_Gain    = "{0:0{1}x}".format(16*x[4]+x[5], 2)

                    send(DEV, b'\x81\x09\x04\x27\xFF')
                    while (ser.in_waiting == 0):
                       i=0
                    x = ser.read(ser.in_waiting)
                    CAM_AF_Mode_Active   = "{0:0{1}x}".format(16*x[2]+x[3], 2)
                    CAM_AF_Mode_Interval = "{0:0{1}x}".format(16*x[4]+x[5], 2)

                    send(DEV, b'\x81\x09\x04\x47\xFF')
                    while (ser.in_waiting == 0):
                       i=0
                    x = ser.read(ser.in_waiting)
                    zoompos  = "{0:0{1}x}".format(16*(16*(16*x[2]+x[3])+x[4])+x[5], 4)

                    send(DEV, b'\x81\x09\x04\x48\xFF')
                    while (ser.in_waiting == 0):
                       i=0
                    x = ser.read(ser.in_waiting)
                    focuspos  = "{0:0{1}x}".format(16*(16*(16*x[2]+x[3])+x[4])+x[5], 4)

                    send(DEV, b'\x81\x09\x04\x39\xFF')
                    while (ser.in_waiting == 0):
                       i=0
                    x = ser.read(ser.in_waiting)
                    if (x[2] == 0x00):
                        CAM_AEMode = '1'
                    if (x[2] == 0x03):
                        CAM_AEMode = '0'

                    send(DEV, b'\x81\x09\x04\x5C\xFF')
                    while (ser.in_waiting == 0):
                       i=0
                    x = ser.read(ser.in_waiting)
                    if (x[2] == 0x02):
                        CAM_AGCMode = '1'
                    if (x[2] == 0x03):
                        CAM_AGCMode = '0'

                    send(DEV, b'\x81\x09\x04\x35\xFF')
                    while (ser.in_waiting == 0):
                       i=0
                    x = ser.read(ser.in_waiting)
                    if (x[2] == 0x00):
                        CAM_WBMode = 'Auto'
                    if (x[2] == 0x01):
                        CAM_WBMode = 'Indoor'
                    if (x[2] == 0x02):
                        CAM_WBMode = 'Outdoor'
                    if (x[2] == 0x03):
                        CAM_WBMode = 'One Push AWB'
                    if (x[2] == 0x05):
                        CAM_WBMode = 'Manual'
       
                    send(DEV, b'\x81\x09\x04\x38\xFF')
                    while (ser.in_waiting == 0):
                       i=0
                    x = ser.read(ser.in_waiting)
                    if (x[2] == 0x02):
                        CAM_AFMode = '1'
                    if (x[2] == 0x03):
                        CAM_AFMode = '0'

                    s = '{'
                    s += '"CAM_RGain": "'            + CAM_RGain  + '",'
                    s += '"CAM_BGain": "'            + CAM_BGain  + '",'
                    s += '"CAM_Chroma": "'           + CAM_Chroma  + '",'
                    s += '"CAM_Bright": "'           + CAM_Bright  + '",'
                    s += '"CAM_Aperture": "'         + CAM_Aperture  + '",'
                    s += '"CAM_Shutter": "'          + CAM_Shutter  + '",'
                    s += '"CAM_Iris": "'             + CAM_Iris  + '",'
                    s += '"CAM_Gain": "'             + CAM_Gain  + '",'
                    s += '"CAM_AF_Mode_Active": "'   + CAM_AF_Mode_Active  + '",'
                    s += '"CAM_AF_Mode_Interval": "' + CAM_AF_Mode_Interval + '",'

                    s += '"CAM_WBMode": "'  + CAM_WBMode + '",'
                    s += '"CAM_AEMode": "'  + CAM_AEMode + '",'
                    s += '"CAM_AGCMode": "' + CAM_AGCMode + '",'
                    s += '"CAM_AFMode": "'  + CAM_AFMode + '",'

                    s += '"zoompos": "' + zoompos   + '",'
                    s += '"focuspos": "' + focuspos 
                    s += '"}'
#                    print(s)
                    self.send_response(200)
                    self.send_header('Content-type', 'text/event-stream')
                    self.end_headers()
#                    self.wfile.write(bytes('retry: 1000\n', 'utf-8'))
                    self.wfile.write(bytes('data: ' + s + '\n\n', 'utf-8'))

#                print('OK')

                if self.path.startswith('/imx8/status'):
                    fd = open('/sys/class/thermal/thermal_zone0/temp')
                    temp      = int(fd.read())/1000
                    
                    if temp>max_temp:
                        max_temp=temp
                    if temp<min_temp:
                        min_temp=temp
                    pickle.dump([min_temp, max_temp, min_temp_24h, max_temp_24h], open(cur_path + "/temperature.p", "wb"))
                    print(min_temp, max_temp)
                      
                    upt       = str(uptime())
                    cpu_freq  = str(psutil.cpu_freq().current)
                    cpu_perc  = psutil.cpu_percent(percpu=True)
                    ram_usage     = str(int((psutil.virtual_memory().total - psutil.virtual_memory().available)/1024/1024))
                    ram_total     = str(int(psutil.virtual_memory().total)/1024/1024)
                    ram_available = str(int(psutil.virtual_memory().available)/1024/1024)
                    ram_percent   = str(int(psutil.virtual_memory().percent))
                    ram_used      = str(int(psutil.virtual_memory().used)/1024/1024)
                    ram_free      = str(int(psutil.virtual_memory().free)/1024/1024)
                    cpu_avg   = psutil.getloadavg()
#                    print ("ETH RX "+ bytes2human( psutil.net_io_counters().bytes_sent ) )
#                    print ("ETH TX "+ bytes2human( psutil.net_io_counters().bytes_recv ) )
                    eth_sent = str( psutil.net_io_counters().bytes_sent )
                    eth_recv = str( psutil.net_io_counters().bytes_recv )
                    eth_pkt_sent = str( psutil.net_io_counters().packets_sent )
                    eth_pkt_recv = str( psutil.net_io_counters().packets_recv )

                    net_in, net_out = net_usage()

#                    print(f"Current net-usage: IN: {net_in} MB/s, OUT: {net_out} MB/s")

                    """
                    print('> ' + visca_resp)
                    if visca_resp == '<NO INFO>':
                        visca_response = '"' + str(0) + '"'
                    else:               
                        visca_response = '"' + visca_resp + '"'
                    """

#                    print("RTSP running")
                    p = subprocess.Popen(['ps', '-ax'], stdout=subprocess.PIPE)
                    out, err = p.communicate()
                    rtsp1 = kill_gst_pid(b'gst-variable-rtsp-server -p 9001', out, False)
                    if (rtsp1 == 0):
                         rtsp1_running = "0" 
                    else:
                         rtsp1_running = "1"
                    rtsp2 = kill_gst_pid(b'gst-variable-rtsp-server -p 9002', out, False)
                    if (rtsp2 == 0):
                         rtsp2_running = "0"
                    else:
                         rtsp2_running = "1"
                    rtsp3 = kill_gst_pid(b'gst-variable-rtsp-server -p 9003', out, False)
                    if (rtsp3 == 0):
                         rtsp3_running = "0"
                    else:
                         rtsp3_running = "1"
                    rtsp4 = kill_gst_pid(b'gst-variable-rtsp-server -p 9004', out, False)
                    if (rtsp4 == 0):
                         rtsp4_running = "0"
                    else:
                         rtsp4_running = "1"

                    global IP
                    IP = socket.gethostbyname(socket.getfqdn())

                    json_txt = '{' + '"cpu_perc1":' + str(cpu_perc[0])    + ',' \
                                   + '"cpu_perc2":' + str(cpu_perc[1])    + ',' \
                                   + '"cpu_perc3":' + str(cpu_perc[2])    + ',' \
                                   + '"cpu_perc4":' + str(cpu_perc[3])    + ',' \
                                   + '"cpu_avg1":'  + str(cpu_avg[0]*100) + ',' \
                                   + '"cpu_avg10":' + str(cpu_avg[1]*100) + ',' \
                                   + '"cpu_avg15":' + str(cpu_avg[2]*100) + ',' \
                                   + '"ram_usage":'     + ram_usage       + ',' \
                                   + '"ram_total":'     + ram_total       + ',' \
                                   + '"ram_available":' + ram_available   + ',' \
                                   + '"ram_percent":'   + ram_percent     + ',' \
                                   + '"ram_used":'      + ram_used        + ',' \
                                   + '"ram_free":'      + ram_free        + ',' \
                                   + '"eth_sent":'      + eth_sent        + ',' \
                                   + '"eth_recv":'      + eth_recv        + ',' \
                                   + '"eth_pkt_sent":'  + eth_pkt_sent    + ',' \
                                   + '"eth_pkt_recv":'  + eth_pkt_recv    + ',' \
                                   + '"temperature":'   + str(temp)            + ',' \
                                   + '"min_temp":'      + str(min_temp)   + ',' \
                                   + '"max_temp":'      + str(max_temp)   + ',' \
                                   + '"uptime":'        + upt             + ',' \
                                   + '"net_in":'        + str(net_in)     + ',' \
                                   + '"net_out":'       + str(net_out)    + ',' \
                                   + '"rtsp1_running":' + rtsp1_running   + ',' \
                                   + '"rtsp2_running":' + rtsp2_running   + ',' \
                                   + '"rtsp3_running":' + rtsp3_running   + ',' \
                                   + '"rtsp4_running":' + rtsp4_running   + ',' \
                                   + '"HOST_NAME":'     + '"'+HOST_NAME+'"'  + ',' \
                                   + '"IP":'            + '"'+IP+'"'         + ',' \
                                   + '"cpu_freq":'      + cpu_freq        + '}'

#                                   + '"visca_response":'    + visca_response + ',' \

                    now = datetime.datetime.now()

#                    print("now =", now)
#                    pickle.dump([now, temp], open(cur_path + "/time_temp.p", "ab+"))

#                    print(json_txt)
                    self.send_response(200)
                    self.send_header('Content-type', 'text/event-stream')
                    self.end_headers()
                    self.wfile.write(bytes('data: ' + json_txt + '\n\n', 'utf-8'))

    def do_POST(self):

        global ser
        global visca_resp

#HH        ser = serial.Serial('/dev/ttyVISCA1', baudrate=9600, timeout=0)

#        print("POST: " + self.path)
        self.send_response(301)
        self.send_header('content-type', 'text/html')
        self.send_header('Location', '/')
        self.end_headers()

        z = self.path.rsplit('/')
        if self.path.startswith('/imx8'):
            if z[2] == 'CAM_POWER':
               send(DEV, b'\x81\x01\x04\x00\x03\xFF') 
#               send(DEV, b'\x81\x01\x04\x00\x03\xFF')

            #***************************************************
            # INQUIRY
            #***************************************************
            if (z[2].startswith('8109') and z[2].endswith('FF')):
               s = []
               for x in range(0, len(z[2])-1, 2):
                  s.append(int("0x"+z[2][x]+z[2][x+1],16))
#                  print(int("0x"+z[2][x]+z[2][x+1],16))
#               print(s)

               send(DEV, bytearray(s))
               time.sleep(1)
               recv(DEV, data)
#HH               data = ser.readline()
               print(len(data))
               print(data)
               visca_resp = binascii.hexlify(data).decode('ascii')
               print(visca_resp)

#               print('VISCA resp. INQUIRY:'+visca_resp)
               if z[2][3]=='\x39':  # AE mode inq
                  if data[2] == '\x00':
                     CAM_AEMode='Full Auto'
                  if data[2] == '\x03':
                     CAM_AEMode='Manual'
                  print('AEMode Inq:' + str(data[2]))

               if z[2][3]=='\x38':  # FocusMode inq
                  if data[2] == '\x02':
                     CAM_AFMode='Auto'
                  if data[2] == '\x03':
                     CAM_AFMode='Manual'
                  print('FocusMode Inq:' + str(data[2]))

               if z[2][3]=='\x5C':  # AGC mode inq
                  if data[2] == '\x02':
                     CAM_AGCMode='On'
                  if data[2] == '\x03':
                     CAM_AGCMode='Off'
                  print('AGCMode Inq:' + str(data[2]))

               if z[2][3]=='\x35':  # WB mode inq
                  if data[2] == '\x00':
                     CAM_WBMode='Auto'
                  if data[2] == '\x01':
                     CAM_WBMode='Indoor'
                  if data[2] == '\x02':
                     CAM_WBMode='Outdoor'
                  if data[2] == '\x03':
                     CAM_WBMode='One push AWB'
                  if data[2] == '\x05':
                     CAM_WBMode='Manual'
                  print('AGCMode Inq:' + str(data[2]))

            if (z[2].startswith('8101') and z[2].endswith('FF')):
               s = []
               for x in range(0, len(z[2])-1, 2):
                  s.append(int("0x"+z[2][x]+z[2][x+1],16))
                  print(int("0x"+z[2][x]+z[2][x+1],16))
               print(s)

               send(DEV, bytearray(s))
               time.sleep(1)

#HH               data = ser.readline()
#               print(len(data))
#               print(data)
               visca_resp = binascii.hexlify(data).decode('ascii')
               print('VISCA resp. CMD:'+visca_resp)


               """
               i=0
               while (ser.out_waiting > 0):
                   i = i+1
               print('i=' + str(i) + ' out_waiting=' + str(ser.out_waiting))

               i=0
               while (i < 300):
                   print('i=' + str(i) + '  in_waiting=' + str(ser.in_waiting))
                   i = i+1

               print('i=' + str(i) + '  in_waiting=' + str(ser.in_waiting))
               print('in_waiting:' + str(ser.in_waiting))
               if (ser.in_waiting > 0):
                       print('in_waiting=' + str(ser.in_waiting))
                       while (ser.in_waiting > 0):
                           x = ser.read(1)
                           print(str(x) +' > '+ str(ser.in_waiting))
               else:
                       print('NOT > 0 ->'+ str(ser.in_waiting))
#                  data.append(x)
#               print(data)
               visca_resp = binascii.hexlify(data).decode('ascii')
               print('VISCA resp.:'+visca_resp)
               """
            else:
               visca_resp=''

            if z[2] == 'CAM_ICR':
               if z[3] == 'NIGHT':
                  send(DEV, b'\x81\x01\x04\x01\x02\xFF')
               if z[3] == 'DAY':
                  send(DEV, b'\x81\x01\x04\x01\x03\xFF')

            if z[2] == 'CAM_MENU':
               if z[3] == 'ENTER':
                  send(DEV, b'\x81\x01\x04\x16\x10\xFF')
               if z[3] == 'ESC':
                  send(DEV, b'\x81\x01\x04\x16\x20\xFF')
               if z[3] == 'UP':
                  send(DEV, b'\x81\x01\x04\x16\x01\xFF')
               if z[3] == 'DOWN':
                  send(DEV, b'\x81\x01\x04\x16\x02\xFF')
               if z[3] == 'RIGHT':
                  send(DEV, b'\x81\x01\x04\x16\x08\xFF')
               if z[3] == 'LEFT':
                  send(DEV, b'\x81\x01\x04\x16\x04\xFF') 

            if z[2] == 'CAM_MEMORY':
#HH               send(DEV, b'\x81\x01\x04\x3F\x01\x00\xFF')
               time.sleep(2)
               send(DEV, b'\x81\x01\x04\x3F\x01\x7F\xFF')
               time.sleep(2)
               send(DEV, b'\x81\x01\x04\x00\x03\xFF')


            if z[2] == 'CAM_videotestsrc':
               if z[3] =='0':
                   p = subprocess.Popen(os.path.dirname(__file__) + "/videotestsrc_640.sh", shell=True)
                   p = subprocess.Popen(['ps', '-ax'], stdout=subprocess.PIPE)
                   out, err = p.communicate()
                   pid = kill_gst_pid(b'gst-variable-rtsp-server -p 9003', out, False)
                   print(pid)
               if z[3] =='1':
                   p = subprocess.Popen(os.path.dirname(__file__) + "/videotestsrc_1920.sh", shell=True)
                   p = subprocess.Popen(['ps', '-ax'], stdout=subprocess.PIPE)
                   out, err = p.communicate()
                   pid = kill_gst_pid(b'gst-variable-rtsp-server -p 9004', out, False)
                   print(pid)

            if z[2] == 'CAM_videotestsrc_kill':
               p = subprocess.Popen(['ps', '-ax'], stdout=subprocess.PIPE)
               out, err = p.communicate()
               if z[3]=='0':
                   kill_gst_pid(b'gst-variable-rtsp-server -p 9003', out, True)
               if z[3]=='1':
                   kill_gst_pid(b'gst-variable-rtsp-server -p 9004', out, True)


            if z[2] == 'CAM_Zoom':
               if z[3] == 'Stop':
                  send(DEV, b'\x81\x01\x04\x07\x00\xFF')
               if z[3] == 'Tele':
                  send(DEV, b'\x81\x01\x04\x07\x02\xFF')
               if z[3] == 'Wide':
                  send(DEV, b'\x81\x01\x04\x07\x03\xFF')
               if z[3] == '1X':
                  x = bytearray()
                  x = [0x81,0x01,0x04,0x47,0x00,0x00,0x00,0x00,0xFF]
                  print(x)
#                  send(DEV, b'\x81\x01\x04\x47\x00\x00\x00\x00\xFF')
                  send(DEV, bytearray(x))
               if z[3] == 'DIRECT':
                  s = [0x81, 0x01, 0x04, 0x47, int("0x0"+z[4][0],16), int("0x0"+z[4][1],16), int("0x0"+z[4][2],16), int("0x0"+z[4][3],16), 0xFF]
                  send(DEV, bytearray(s))
               if z[3][0] == 'X':
                  if len(z[3]) == 2:
                       s = [0x81, 0x01, 0x04, 0x47, 0x00, 0x00, 0x00, int("0x0"+z[3][1],16), 0xFF]
                  if len(z[3]) == 3:
                       s = [0x81, 0x01, 0x04, 0x47, 0x00, 0x00, int("0x0"+z[3][1],16), int("0x0"+z[3][1],16), 0xFF]
                  if len(z[3]) == 4:
                       s = [0x81, 0x01, 0x04, 0x47, 0x00, int("0x0"+z[3][1],16), int("0x0"+z[3][2],16), int("0x0"+z[3][3],16), 0xFF]
                  if len(z[3]) == 5:
                       s = [0x81, 0x01, 0x04, 0x47, int("0x0"+z[3][1],16), int("0x0"+z[3][2],16), int("0x0"+z[3][3],16), int("0x0"+z[3][4],16), 0xFF]
                  print(s)
                  send(DEV, bytearray(s))

            if z[2] == 'CAM_Focus':
               if z[3] == 'AUTO':
                  send(DEV, b'\x81\x01\x04\x38\x02\xFF')	# auto focus
               if z[3] == 'MANUAL':
                  send(DEV, b'\x81\x01\x04\x38\x03\xFF')	# manual focus
               if z[3] == 'Far':
                  send(DEV, b'\x81\x01\x04\x08\x27\xFF')
               if z[3] == 'Near':
                  send(DEV, b'\x81\x01\x04\x08\x37\xFF')
               if z[3] == 'Near_near_limit':
                  send(DEV, b'\x81\x01\x04\x28\x0F\x00\x00\x00\xFF')

            if z[2] == 'CAM_DispSel':
                  x = int(z[3][3])*8 + int(z[3][2])*4 + int(z[3][1])*2 + int(z[3][0])
                  s = [0x81, 0x01, 0x04, 0x14, 0x00, x, 0xFF]
                  print(s)
                  send(DEV, bytearray(s))
                  
    extensions_map = {
        '': 'application/octet-stream',
        '.manifest': 'text/cache-manifest',
        '.html': 'text/html',
        '.png': 'image/png',
        '.jpg': 'image/jpg',
        '.svg':	'image/svg+xml',
        '.css':	'text/css',
        '.js':'application/x-javascript',
        '.wasm': 'application/wasm',
        '.json': 'application/json',
        '.xml': 'application/xml',
    }



def uptime():  
    with open('/proc/uptime', 'r') as f:
        uptime_seconds = float(f.readline().split()[0])
        return uptime_seconds


def convert_to_hrs_min_sec(sec):
   sec = sec % (24 * 3600)
   hour = sec // 3600
   sec %= 3600
   min = sec // 60
   sec %= 60
   return "%02d:%02d:%02d" % (hour, min, sec) 


def bytes2human(n, format="%(value).1f%(symbol)s"):
    """Used by various scripts. See:
    http://goo.gl/zeJZl
    >>> bytes2human(10000)
    '9.8K'
    >>> bytes2human(100001221)
    '95.4M'
    """
    symbols = ('B', 'K', 'M', 'G', 'T', 'P', 'E', 'Z', 'Y')
    prefix = {}
    for i, s in enumerate(symbols[1:]):
        prefix[s] = 1 << (i + 1) * 10
    for symbol in reversed(symbols[1:]):
        if n >= prefix[symbol]:
            value = float(n) / prefix[symbol]
            return format % locals()
    return format % dict(symbol=symbols[0], value=n)


def net_usage(inf = "end0"):   #change the inf variable according to the interface
    net_stat = psutil.net_io_counters(pernic=True, nowrap=True)[inf]
    net_in_1 = net_stat.bytes_recv
    net_out_1 = net_stat.bytes_sent
    time.sleep(1)
    net_stat = psutil.net_io_counters(pernic=True, nowrap=True)[inf]
    net_in_2 = net_stat.bytes_recv
    net_out_2 = net_stat.bytes_sent

    net_in = round((net_in_2 - net_in_1) / 1024 / 1024, 3)
    net_out = round((net_out_2 - net_out_1) / 1024 / 1024, 3)
    
    return net_in, net_out

#    print(psutil.net_if_stats())
#    print(psutil.net_if_addrs())
#    print(f"Current net-usage:\nIN: {net_in} MB/s, OUT: {net_out} MB/s")


def kill_gst_pid(tekst, out, kill):
    pid = 0
    for line in out.splitlines():
         if tekst in line:
#            print(line)
            pid = int(line.split(None, 1)[0])
#            print('Process PID: '+ str(pid))
            if kill:
               os.kill(pid, signal.SIGKILL) 
    return pid


#*********************************************************************************************
#
#  STOP serial-getty on /dev/ttymxc3
#

def checkServiceStatus():
    try:
        print("getty@ttymxc3 status...")
        
        #Check getty service
        for line in os.popen("sudo systemctl status serial-getty@ttymxc3.service"):
            services = line.split()
            print(services)
            
            pass
        
    except OSError as ose:
        print("Error while running the command", ose)
   
    pass

#checkServiceStatus()

#os.popen("systemctl stop serial-getty@ttymxc3.service")


#*********************************************************************************************


httpd = socketserver.TCPServer(("0.0.0.0", PORT), HttpRequestHandler, bind_and_activate=False)
httpd.allow_reuse_address = True
httpd.daemon_threads = True

try:

#    ser = serial.Serial('/dev/ttyVISCA1', baudrate=9600, timeout=0)

    set_baud(DEV, 9600)

    visca_resp = ''


    HOST_NAME = socket.gethostname()
    IP        = socket.gethostbyname(socket.getfqdn())
    print(HOST_NAME)
    print('IP:'+IP)
    print(f"serving at <{IP}>:{PORT}")

#    ser = serial.Serial('/dev/ttyVISCA1', baudrate=9600, timeout=0)
#    send(DEV, b'\x81\x01\x04\x00\x03\xFF')


#    print(socket.getaddrinfo(HOST_NAME, PORT))
#    print(socket.gethostbyname_ex(socket.gethostname())[-1])
#    print(socket.gethostbyname_ex(HOST_NAME))
#    print(socket.gethostbyaddr(IP))

    httpd.server_bind()
    httpd.server_activate()
    httpd.serve_forever()
except KeyboardInterrupt:
    pass
finally:
    # Clean-up server (close socket, etc.)
    httpd.server_close()
    print(time.asctime(),'Stop Server - %s:%s' %(HOST_NAME,PORT))

