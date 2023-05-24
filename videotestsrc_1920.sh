#!/bin/bash

#gst-variable-rtsp-server -p 9003 -u "videotestsrc pattern=21 ! video/x-raw, width=1920, height=1080 ! gdkpixbufoverlay location=clipart333306.png positioning-mode=0 offset-x=572 offset-y=152 ! videoconvert ! vpuenc_h264 ! rtph264pay name=pay0 pt=96" &
gst-variable-rtsp-server -p 9003 -u "videotestsrc pattern=25 ! video/x-raw, width=1920, height=1080 ! videoconvert ! vpuenc_h264 ! rtph264pay name=pay0 pt=96" &
