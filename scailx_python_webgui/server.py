# server app
import sys
import uvicorn
from fastapi import FastAPI, Request, Response
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
import socket
import time
import os
import base64
import crosslink_visca
import logging
import json
import psutil
import subprocess, signal
from datetime import timezone
import datetime

import pickle
import glob
import yaml

from cameracontrol import gen_cameracontrol
#-----------------------------------------------------------------------------------

from time import sleep, time_ns
import argparse
from enum import Enum


appdir = os.path.dirname(os.path.realpath(__file__))
app = FastAPI()
@app.get("/", response_class=FileResponse)
def main():
    return os.path.join(appdir, "public/index.html")
app.mount("/assets", StaticFiles(directory=os.path.join(appdir, "public/assets")), name="assets")

PORT = 8088
IP = None
max_temp = -40
min_temp = 120
max_temp_24h = -40
min_temp_24h = 120
ctv = None
fw_version = None

crosslinks = glob.glob("/dev/links/lvds2mipi_*")
if crosslinks:
    print(crosslinks)
    DEV = os.path.realpath(crosslinks[0])
    ctv = crosslink_visca.CrosslinkSerial(DEV, baud=9600)

stream1 = ""
try:
    with open('/tmp/cam_config.yaml', 'r') as f:
        data = yaml.load(f, Loader=yaml.SafeLoader)
    stream1 = list(data['streams'])[0]
    print(stream1)
except:
    print("No cam_config.yaml file found")

visca_resp = ''

cur_path = os.path.dirname(__file__)

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

def get_default_iface_name_linux():
    route = "/proc/net/route"
    with open(route) as f:
        for line in f.readlines():
            try:
                iface, dest, _, flags, _, _, _, _, _, _, _, =  line.strip().split()
                if dest != '00000000' or not int(flags, 16) & 2:
                    continue
                return iface
            except:
                continue

intf = get_default_iface_name_linux()

@app.get("/imx8/temperature")
async def get_temperature():
    with open('/sys/devices/virtual/thermal/thermal_zone0/temp') as fd:
        return 'data: '+str(int(fd.read())/1000) + '\n\n'

@app.get("/imx8/uptime")
async def get_uptime():
    upt = 'data: ' + str(uptime()) + '\n\n'
    return upt

@app.get("/imx8/visca_response")
async def get_visca_response():
    return { "visca_response": visca_resp }


@app.get("/imx8/cameracontrol")
async def get_cameracontrol():
    return StreamingResponse(gen_cameracontrol(ctv), media_type="text/event-stream")

async def gen_status():
    global min_temp, max_temp, IP, fw_version
    status = {}

    with open('/sys/class/thermal/thermal_zone0/temp') as fd:
        temp = int(fd.read())/1000

    if temp>max_temp:
        max_temp=temp
    if temp<min_temp:
        min_temp=temp
    pickle.dump([min_temp, max_temp, min_temp_24h, max_temp_24h], open(cur_path + "/temperature.p", "wb"))
    print(min_temp, max_temp)

    with open('/proc/uptime', 'r') as f:
        uptime_seconds = float(f.readline().split()[0])
    status['fw_version']    = fw_version
    status['uptime']        = uptime_seconds
    status['cpu_freq']      = psutil.cpu_freq().current
    cpu_perc = psutil.cpu_percent(percpu=True)
    for i, cp in enumerate(cpu_perc):
        status[f'cpu_perc{i+1}'] = cp
    status['ram_usage']     = int((psutil.virtual_memory().total - psutil.virtual_memory().available)/1024/1024)
    status['ram_total']     = int(psutil.virtual_memory().total)/1024/1024
    status['ram_available'] = int(psutil.virtual_memory().available)/1024/1024
    status['ram_percent']   = int(psutil.virtual_memory().percent)
    status['ram_used']      = int(psutil.virtual_memory().used)/1024/1024
    status['ram_free']      = int(psutil.virtual_memory().free)/1024/1024
    cpu_avg = psutil.getloadavg()
    status['cpu_avg1']      = cpu_avg[0]*100,
    status['cpu_avg10']     = cpu_avg[1]*100,
    status['cpu_avg15']     = cpu_avg[2]*100,
#                    print ("ETH RX "+ bytes2human( psutil.net_io_counters().bytes_sent ) )
#                    print ("ETH TX "+ bytes2human( psutil.net_io_counters().bytes_recv ) )
    status['eth_sent']      =  psutil.net_io_counters().bytes_sent
    status['eth_recv']      =  psutil.net_io_counters().bytes_recv
    status['eth_pkt_sent']  =  psutil.net_io_counters().packets_sent
    status['eth_pkt_recv']  =  psutil.net_io_counters().packets_recv

    if os.path.isfile('/sys/class/hwmon/hwmon2/power1_input'):
        f=open('/sys/class/hwmon/hwmon2/power1_input')
        pwr = f.read().splitlines()[0]
        f.close()
    else: pwr = '0'

    status['pwr'] = pwr

    net_in, net_out = net_usage(intf)

#                    print(f"Current net-usage: IN: {net_in} MB/s, OUT: {net_out} MB/s")

    print('> ' + visca_resp)
    if visca_resp == '<NO INFO>':
        visca_response = '"' + str(0) + '"'
    else:
        visca_response = '"' + visca_resp + '"'

    IP = socket.gethostbyname(socket.getfqdn())
    
    print(status)

    status |= {
        'temperature': temp,
        'min_temp': min_temp,
        'max_temp': max_temp,
        'net_in': net_in,
        'net_out': net_out,
        'rtsp1_running': 0,
        'rtsp2_running': 0,
        'rtsp3_running': 0,
        'rtsp4_running': 0,
        'HOST_NAME': HOST_NAME,
        'IP': IP,
        'visca_response': visca_response,
        'stream1': stream1,
    }
    yield 'data: ' + json.dumps(status) + '\n\n'

@app.get("/imx8/status")
async def get_status():
    return StreamingResponse(gen_status(), media_type="text/event-stream")

@app.post("/imx8/CAM_POWER")
async def post_cam_power():
    ctv.transceive(b'\x81\x01\x04\x00\x03\xFF')

#***************************************************
# VISCA INQUIRY
#***************************************************
@app.post("/imx8/{visca}")
async def inquiry(visca: str):
    if (visca.startswith('8109') and visca.endswith('FF')):
        s = []
        print(f"VISCA: {visca}")
        visca_resp = ""
        data = bytearray
        for x in range(0, len(visca)-1, 2):
            s.append(int("0x"+visca[x]+visca[x+1],16))

        y = ctv.transceive(bytearray.fromhex(visca))
        print("visca_resp=", y.hex())
        visca_resp = y.hex()
#               print(s[3])

#               print('VISCA resp. INQUIRY:'+visca_resp)
        if s[3]=='\x39':  # AE mode inq
            if data[2] == '\x00':
                CAM_AEMode='Full Auto'
            if data[2] == '\x03':
                CAM_AEMode='Manual'
            print('AEMode Inq:' + str(data[2]))

        if s[3]=='\x38':  # FocusMode inq
            if data[2] == '\x02':
                CAM_AFMode='Auto'
            if data[2] == '\x03':
                CAM_AFMode='Manual'
            print('FocusMode Inq:' + str(data[2]))

        if s[3]=='\x5C':  # AGC mode inq
            if data[2] == '\x02':
                CAM_AGCMode='On'
            if data[2] == '\x03':
                CAM_AGCMode='Off'
            print('AGCMode Inq:' + str(data[2]))

        if s[3]=='\x35':  # WB mode inq
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

    if (visca.startswith('8101') and visca.endswith('FF')):
        s = []
        print(f"VISCA: {visca}")
        for x in range(0, len(visca)-1, 2):
            s.append(int("0x"+visca[x]+visca[x+1],16))
            print(int("0x"+visca[x]+visca[x+1],16))
        print(s)

        data = ctv.transceive(bytearray.fromhex(visca), start_wait_ms=1000)

@app.post("/imx8/CAM_ICR/{type}")
async def cam_icr(type: str):
    if type == 'NIGHT':
        ctv.transceive(b'\x81\x01\x04\x01\x02\xFF')
    if type == 'DAY':
        ctv.transceive(b'\x81\x01\x04\x01\x03\xFF')

class CamMenu(str, Enum):
    ENTER = 'ENTER'
    ESC = 'ESC'
    UP = 'UP'
    DOWN = 'DOWN'
    RIGHT = 'RIGHT'
    LEFT = 'LEFT'

@app.post("/imx8/CAM_MENU/{menu_entry}")
async def cam_icr(menu_entry: CamMenu):
    if menu_entry.value == 'ENTER':
        ctv.transceive(b'\x81\x01\x04\x16\x10\xFF')
    if menu_entry.value == 'ESC':
        ctv.transceive(b'\x81\x01\x04\x16\x20\xFF')
    if menu_entry.value == 'UP':
        ctv.transceive(b'\x81\x01\x04\x16\x01\xFF')
    if menu_entry.value == 'DOWN':
        ctv.transceive(b'\x81\x01\x04\x16\x02\xFF')
    if menu_entry.value == 'RIGHT':
        ctv.transceive(b'\x81\x01\x04\x16\x08\xFF')
    if menu_entry.value == 'LEFT':
        ctv.transceive(b'\x81\x01\x04\x16\x04\xFF')

@app.post("/imx8/CAM_MEMORY")
async def cam_memory():
#HH               ctv.transceive(b'\x81\x01\x04\x3F\x01\x00\xFF')
    time.sleep(2)
    ctv.transceive(b'\x81\x01\x04\x3F\x01\x7F\xFF')
    time.sleep(2)
    ctv.transceive(b'\x81\x01\x04\x00\x03\xFF')

@app.post("/imx8/CAM_videotestsrc/{src}")
async def cam_videotestsrc(src: str):
    if src =='0':
        p = subprocess.Popen(os.path.dirname(__file__) + "/videotestsrc_640.sh", shell=True)
        p = subprocess.Popen(['ps', '-ax'], stdout=subprocess.PIPE)
        out, err = p.communicate()
        pid = kill_gst_pid(b'gst-variable-rtsp-server -p 9003', out, False)
        print(pid)
    if src =='1':
        p = subprocess.Popen(os.path.dirname(__file__) + "/videotestsrc_1920.sh", shell=True)
        p = subprocess.Popen(['ps', '-ax'], stdout=subprocess.PIPE)
        out, err = p.communicate()
        pid = kill_gst_pid(b'gst-variable-rtsp-server -p 9004', out, False)
        print(pid)

@app.post("/imx8/CAM_videotestsrc_kill/{src}")
async def cam_videotestsrc(src: str):
    p = subprocess.Popen(['ps', '-ax'], stdout=subprocess.PIPE)
    out, err = p.communicate()
    if src =='0':
        kill_gst_pid(b'gst-variable-rtsp-server -p 9003', out, True)
    if src =='1':
        kill_gst_pid(b'gst-variable-rtsp-server -p 9004', out, True)

@app.post("/imx8/CAM_Zoom/{zoom}")
async def cam_zoom(zoom: str):
    if zoom == 'Stop':
        ctv.transceive(b'\x81\x01\x04\x07\x00\xFF')
    if zoom == 'Tele':
        ctv.transceive(b'\x81\x01\x04\x07\x02\xFF')
    if zoom == 'Wide':
        ctv.transceive(b'\x81\x01\x04\x07\x03\xFF')
    if zoom == '1X':
        x = bytearray()
        x = [0x81,0x01,0x04,0x47,0x00,0x00,0x00,0x00,0xFF]
        print(x)
#                  ctv.transceive(b'\x81\x01\x04\x47\x00\x00\x00\x00\xFF')
        ctv.transceive(bytearray(x))
    if zoom == 'DIRECT':
        s = [0x81, 0x01, 0x04, 0x47, int("0x0"+z[4][0],16), int("0x0"+z[4][1],16), int("0x0"+z[4][2],16), int("0x0"+z[4][3],16), 0xFF]
        ctv.transceive(bytearray(s))
    if zoom[0] == 'X':
        if len(zoom) == 2:
            s = [0x81, 0x01, 0x04, 0x47, 0x00, 0x00, 0x00, int("0x0"+zoom[1],16), 0xFF]
        if len(zoom) == 3:
            s = [0x81, 0x01, 0x04, 0x47, 0x00, 0x00, int("0x0"+zoom[1],16), int("0x0"+zoom[1],16), 0xFF]
        if len(zoom) == 4:
            s = [0x81, 0x01, 0x04, 0x47, 0x00, int("0x0"+zoom[1],16), int("0x0"+zoom[2],16), int("0x0"+zoom[3],16), 0xFF]
        if len(zoom) == 5:
            s = [0x81, 0x01, 0x04, 0x47, int("0x0"+zoom[1],16), int("0x0"+zoom[2],16), int("0x0"+zoom[3],16), int("0x0"+zoom[4],16), 0xFF]
        print(s)
        ctv.transceive(bytearray(s))

@app.post("/imx8/CAM_Focus/{focus}")
async def cam_focus(focus: str):
    if focus == 'AUTO':
        ctv.transceive(b'\x81\x01\x04\x38\x02\xFF')	# auto focus
    if focus == 'MANUAL':
        ctv.transceive(b'\x81\x01\x04\x38\x03\xFF')	# manual focus
    if focus == 'Far':
        ctv.transceive(b'\x81\x01\x04\x08\x27\xFF')
    if focus == 'Near':
        ctv.transceive(b'\x81\x01\x04\x08\x37\xFF')
    if focus == 'Near_near_limit':
        ctv.transceive(b'\x81\x01\x04\x28\x0F\x00\x00\x00\xFF')

@app.post("/imx8/CAM_DispSel")
async def cam_dispel():
    x = int(z[3][3])*8 + int(z[3][2])*4 + int(z[3][1])*2 + int(z[3][0])
    s = [0x81, 0x01, 0x04, 0x14, 0x00, x, 0xFF]
    print(s)
    ctv.transceive(bytearray(s))


# def convert_to_hrs_min_sec(sec):
#    sec = sec % (24 * 3600)
#    hour = sec // 3600
#    sec %= 3600
#    min = sec // 60
#    sec %= 60
#    return "%02d:%02d:%02d" % (hour, min, sec)


# def bytes2human(n, format="%(value).1f%(symbol)s"):
#     """Used by various scripts. See:
#     http://goo.gl/zeJZl
#     >>> bytes2human(10000)
#     '9.8K'
#     >>> bytes2human(100001221)
#     '95.4M'
#     """
#     symbols = ('B', 'K', 'M', 'G', 'T', 'P', 'E', 'Z', 'Y')
#     prefix = {}
#     for i, s in enumerate(symbols[1:]):
#         prefix[s] = 1 << (i + 1) * 10
#     for symbol in reversed(symbols[1:]):
#         if n >= prefix[symbol]:
#             value = float(n) / prefix[symbol]
#             return format % locals()
#     return format % dict(symbol=symbols[0], value=n)


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

HOST_NAME = socket.gethostname()
IP        = socket.gethostbyname(socket.getfqdn())
print(HOST_NAME)
print('IP:'+IP)
print(f"serving at <{IP}>:{PORT}")

with open('/etc/scailx-version') as fd:
        fw_version = fd.read().splitlines()[0]
        fd.close()

print(fw_version)

if __name__ == "__main__" and len(sys.argv) > 1:
    match sys.argv[1]:
        case 'dev' | "--dev" | "-d":
            print("dev")
            uvicorn.run("server:app", host="0.0.0.0", port=PORT, reload=True)
        case _:
            uvicorn.run("server:app", host="0.0.0.0", port=PORT)
