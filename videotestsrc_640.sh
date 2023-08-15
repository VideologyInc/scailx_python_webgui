#!/bin/bash

gst-variable-rtsp-server -p 9003 -u "videotestsrc ! video/x-raw, width=640, height=480 ! videoconvert ! vpuenc_h264 ! rtph264pay name=pay0 pt=96" &
