#! /usr/bin/env python3
from vdlg_lvds.serial import LvdsSerial
import json

#----------------------------------------------------------
# CAMERACONTROL
#----------------------------------------------------------

async def gen_cameracontrol(ctv: LvdsSerial):
    if not ctv:
        yield 'data: {} \n\n'
    else:
        ctv.recv()
        y = ctv.transceive(bytearray.fromhex('8109042472FF'))
        x = list(y)
        CAM_res = 'None'
        if (len(x)>0):
    #                    print("resolution=", y.hex())
            if (x[2]==0 and x[3]==6): CAM_res = '1080p/30fps'
            if (x[2]==0 and x[3]==8): CAM_res = '1080p/25fps'
            if (x[2]==0 and x[3]==9): CAM_res = '720p/60fps'
            if (x[2]==0 and x[3]==12): CAM_res = '720p/50fps'     # 00 0C
            if (x[2]==0 and x[3]==13): CAM_res = '720p/30fps'     # 00 0E
            if (x[2]==1 and x[3]==1): CAM_res = '720p/25fps'
            if (x[2]==1 and x[3]==3): CAM_res = '1080p/60fps'
            if (x[2]==1 and x[3]==4): CAM_res = '1080p/50fps'
    #                       print(CAM_res)

        x = list(ctv.transceive(bytearray.fromhex('81090002FF')))
        CAM_brand = 'no zoom block'
        if (len(x)>0):
            if (x[4]==4 ):             CAM_brand = 'Videology'
            if (x[4]>=6 and x[4]<=7):  CAM_brand = 'Sony'
            if (x[4]==240):            CAM_brand = 'Tamron'

        # RGAIN
        x = list(ctv.transceive(bytearray.fromhex('81090443FF')))
        CAM_RGain = "00"
        if (len(x) == 7 and x[0]==144):
            CAM_RGain = "{0:0{1}x}".format(16*x[4]+x[5], 2)

        x = list(ctv.transceive(b'\x81\x09\x04\x44\xFF'))
        CAM_BGain = "00"
        if (len(x) == 7 and x[0]==144):
            CAM_BGain = "{0:0{1}x}".format(16*x[4]+x[5], 2)

        x = list(ctv.transceive(b'\x81\x09\x04\x13\xFF'))
        CAM_Chroma = "00"
        if (len(x) == 7 and x[0]==144):
            CAM_Chroma = "{0:0{1}x}".format(16*x[4]+x[5], 2)

        x = list(ctv.transceive(b'\x81\x09\x04\x4D\xFF'))
        CAM_Bright = "00"
        if (len(x) == 7 and x[0]==144):
            CAM_Bright = "{0:0{1}x}".format(16*x[4]+x[5], 2)

        x = list(ctv.transceive(b'\x81\x09\x04\x42\xFF'))
        CAM_Aperture = "00"
        if (len(x) == 7 and x[0]==144):
            CAM_Aperture = "{0:0{1}x}".format(16*x[4]+x[5], 2)

        x = list(ctv.transceive(b'\x81\x09\x04\x4A\xFF'))
        CAM_Shutter = "00"
        if (len(x) == 7 and x[0]==144):
            CAM_Shutter = "{0:0{1}x}".format(16*x[4]+x[5], 2)

        x = list(ctv.transceive(b'\x81\x09\x04\x4B\xFF'))
        CAM_Iris = "00"
        if (len(x) == 7 and x[0]==144):
            CAM_Iris = "{0:0{1}x}".format(16*x[4]+x[5], 2)

        x = list(ctv.transceive(b'\x81\x09\x04\x4C\xFF'))
        CAM_Gain = "00"
        if (len(x) == 7 and x[0]==144):
            CAM_Gain = "{0:0{1}x}".format(16*x[4]+x[5], 2)

        x = list(ctv.transceive(b'\x81\x09\x04\x27\xFF'))
        CAM_AF_Mode_Active = "00"
        CAM_AF_Mode_Interval = "00"
        if (len(x) == 7 and x[0]==144):
            CAM_AF_Mode_Active   = "{0:0{1}x}".format(16*x[2]+x[3], 2)
            CAM_AF_Mode_Interval = "{0:0{1}x}".format(16*x[4]+x[5], 2)

        x = list(ctv.transceive(b'\x81\x09\x04\x47\xFF'))
        zoompos = "0000"
        if (len(x) == 7 and x[0]==144):
            zoompos  = "{0:0{1}x}".format(16*(16*(16*x[2]+x[3])+x[4])+x[5], 4)

        x = list(ctv.transceive(b'\x81\x09\x04\x48\xFF'))
        focuspos = "0000"
        if (len(x) == 7 and x[0]==144):
            focuspos  = "{0:0{1}x}".format(16*(16*(16*x[2]+x[3])+x[4])+x[5], 4)

        x = list(ctv.transceive(b'\x81\x09\x04\x39\xFF'))
        CAM_AEMode = '1'
        if (len(x) == 4 and x[0]==144):
            if (x[2] == 0x00):
                CAM_AEMode = '1'
            if (x[2] == 0x03):
                CAM_AEMode = '0'

        x = list(ctv.transceive(b'\x81\x09\x04\x5C\xFF'))
        CAM_AGCMode = '1'
        if (len(x) == 4 and x[0]==144):
            if (x[2] == 0x02):
                CAM_AGCMode = '1'
            if (x[2] == 0x03):
                CAM_AGCMode = '0'

        x = list(ctv.transceive(b'\x81\x09\x04\x35\xFF'))
        CAM_WBMode = 'Auto'
        if (len(x) == 4 and x[0]==144):
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

        x = list(ctv.transceive(b'\x81\x09\x04\x38\xFF'))
        CAM_AEMode = '1'
        if (len(x) == 4 and x[0]==144):
            if (x[2] == 0x02):
                CAM_AFMode = '1'
            if (x[2] == 0x03):
                CAM_AFMode = '0'

        s = {
            "CAM_brand":            CAM_brand,
            "CAM_res":              CAM_res,
            "CAM_RGain":            CAM_RGain,
            "CAM_BGain":            CAM_BGain,
            "CAM_Chroma":           CAM_Chroma,
            "CAM_Bright":           CAM_Bright,
            "CAM_Aperture":         CAM_Aperture,
            "CAM_Shutter":          CAM_Shutter,
            "CAM_Iris":             CAM_Iris,
            "CAM_Gain":             CAM_Gain,
            "CAM_AF_Mode_Active":   CAM_AF_Mode_Active,
            "CAM_AF_Mode_Interval": CAM_AF_Mode_Interval,
            "CAM_WBMode":           CAM_WBMode,
            "CAM_AEMode":           CAM_AEMode,
            "CAM_AGCMode":          CAM_AGCMode,
            "CAM_AFMode":           CAM_AFMode,
            "zoompos": zoompos ,
            "focuspos": focuspos
        }
        yield 'data: ' + json.dumps(s) + '\n\n'
