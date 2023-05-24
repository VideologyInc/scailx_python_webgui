#!/bin/bash

gst-variable-rtsp-server -p 9002 -u "videotestsrc pattern=0 ! video/x-raw, width=640, height=480 ! gdkpixbufoverlay location=clipart333306.png positioning-mode=0 offset-x=572 offset-y=152 ! videoconvert ! vpuenc_h264 ! rtph264pay name=pay0 pt=96" &
#gst-variable-rtsp-server -p 9002 -u "videotestsrc ! video/x-raw, width=640, height=480 ! videoconvert ! vpuenc_h264 ! rtph264pay name=pay0 pt=96" &
