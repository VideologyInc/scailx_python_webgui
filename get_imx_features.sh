echo Run vvget to get feature values of imx camera.

echo
echo FrameRate and Black Level Subtraction
echo
./vvget 0 'FPS'
./vvget 0 'BLS'

echo
echo Gamma and Denoise PreFilter
echo
./vvget 0 'GAMMA ON/OFF'
./vvget 0 'DPF ON/OFF'

echo
echo Color Processing, Brightness, Contrast, Saturation, Hue
echo
./vvget 0 'CPROC ON/OFF'
./vvget 0 'Adjust brightness'
./vvget 0 'Adjust contrast'
./vvget 0 'Adjust saturation'
./vvget 0 'Adjust HUE'

echo
echo AEC, SetPoint, Gain, ExposureTime, etc.
echo
./vvget 0 'AEC On/Off'
./vvget 0 'AEC SetPoint'
./vvget 0 'AEC DampOver'
./vvget 0 'AEC DampUnder'
./vvget 0 'AEC Tolerance'
./vvget 0 'AEC Gain'
./vvget 0 'AEC ExposureTime'
./vvget 0 'AEC Sensitivity'

echo
echo AWB, Gain, CCM, Offset, etc.
echo
./vvget 0 'AWB On/Off'
./vvget 0 'AWB Auto Ctrl item'
./vvget 0 'GAIN INPUT'
./vvget 0 'CCM INPUT'
./vvget 0 'Offset INPUT'

echo Finished




