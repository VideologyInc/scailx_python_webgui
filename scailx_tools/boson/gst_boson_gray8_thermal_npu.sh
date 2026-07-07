#!/usr/bin/env bash

gst-launch-1.0 \
  v4l2src device=/dev/video0 ! video/x-raw,format=RGB,width=640,height=512,framerate=60/1 ! \
  videorate max-rate=30 ! video/x-raw,framerate=30/1 ! \
  queue leaky=2 max-size-buffers=10 ! videoscale method=0 ! video/x-raw,width=320,height=320 ! \
  tee name=t \
  t. ! queue leaky=2 max-size-buffers=10 ! \
  videoconvert ! video/x-raw,format=RGB ! \
  tensor_converter ! \
  queue leaky=2 max-size-buffers=10 ! \
  tensor_filter latency=1 framework=tensorflow2-lite model=/opt/imx8-isp/boson/thermal_yolov8n_320.tflite \
  custom=Delegate:External,ExtDelegateLib:libvx_delegate.so accelerator=true:npu ! \
  tensor_transform mode=transpose option=1:0:2:3 ! \
  queue leaky=2 max-size-buffers=10 ! \
  tensor_transform mode=arithmetic option=typecast:float32,add:-17.0,mul:0.0063448 ! \
  tensor_decoder mode=bounding_boxes option1=yolov8 option2=/opt/imx8-isp/boson/thermal.txt option4=320:320 option5=320:320 ! \
  videoconvert ! mix.sink_0 \
  t. ! queue leaky=2 max-size-buffers=10 ! videoconvert ! mix.sink_1 \
  compositor name=mix sink_0::zorder=2 sink_1::zorder=1 ! videoconvert ! fpsdisplaysink sync=false
