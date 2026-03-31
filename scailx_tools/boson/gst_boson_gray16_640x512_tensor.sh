#!/usr/bin/env bash
# CANNOT use 640 x 512 directly in videoscale and tensor_decoder !

gst-launch-1.0 \
  v4l2src device=/dev/video0 ! video/x-raw,format=GRAY16_LE,width=640,height=514,framerate=60/1 ! \
  videorate max-rate=10 ! video/x-raw,framerate=10/1 ! \
  queue leaky=2 max-size-buffers=10 ! \
  videoscale ! video/x-raw, width=640, height=530 ! \
  tensor_converter ! \
  tensor_transform mode=arithmetic option=typecast:float32,add:-6000.0,mul:0.43878 ! \
  queue leaky=2 max-size-buffers=10 ! \
  tensor_transform mode=clamp option=0.0:255.0 ! \
  tensor_transform mode=typecast option=uint8 ! \
  queue leaky=2 max-size-buffers=10 ! \
  tensor_decoder mode=direct_video option1=GRAY8 ! \
  videoconvert ! autovideosink sync=false
