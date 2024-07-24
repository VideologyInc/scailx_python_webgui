#!/bin/bash

gst-variable-rtsp-server -p 9004 -u "videotestsrc ! video/x-raw, width=1920, height=1080 ! videoconvert ! vpuenc_h264 ! rtph264pay name=pay0 pt=96" &
