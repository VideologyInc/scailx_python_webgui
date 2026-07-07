#!/usr/bin/env bash
# Camera 14bit raw => nnstreamer => gray 8bit => rgb 24bit => yolo

gst-launch-1.0 \
  v4l2src device=/dev/video0 ! video/x-raw,format=GRAY16_LE,width=320,height=256,framerate=60/1 ! \
  videorate max-rate=10 ! video/x-raw,framerate=10/1 ! \
  queue leaky=2 max-size-buffers=10 ! \
  videoscale ! video/x-raw, width=320, height=320 ! \
  tensor_converter ! \
  tensor_transform mode=arithmetic option=typecast:float32,add:-5474.0,mul:0.43878 ! \
  queue leaky=2 max-size-buffers=10 ! \
  tensor_transform mode=clamp option=0.0:255.0 ! \
  tensor_transform mode=typecast option=uint8 ! \
  queue leaky=2 max-size-buffers=10 ! \
  tensor_decoder mode=direct_video option1=GRAY8 ! \
  tee name=t \
  t. ! queue leaky=2 max-size-buffers=10 ! \
  videoconvert ! video/x-raw,format=RGB ! \
  tensor_converter ! \
  tensor_transform mode=arithmetic option=typecast:float32,add:0.0,div:255.0 ! \
  queue leaky=2 max-size-buffers=10 ! \
  tensor_filter latency=1 framework=tensorflow2-lite model=/opt/imx8-isp/boson/yolov8n_float16.tflite ! \
  tensor_transform mode=transpose option=1:0:2:3 ! \
  queue leaky=2 max-size-buffers=10 ! \
  tensor_decoder mode=bounding_boxes option1=yolov8 option2=/opt/imx8-isp/boson/coco.txt option4=320:320 option5=320:320 ! \
  videoconvert ! mix.sink_0 \
  t. ! queue leaky=2 max-size-buffers=10 ! videoconvert ! mix.sink_1 \
  compositor name=mix sink_0::zorder=2 sink_1::zorder=1 ! videoconvert ! autovideosink sync=false
