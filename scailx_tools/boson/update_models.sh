
echo Copy AI model files to /opt/imx8-isp/boson.

echo Create new folder
mkdir /opt/imx8-isp/boson

echo Copy model files
cp models/* /opt/imx8-isp/boson/

ls -l /opt/imx8-isp/boson/
echo Now we can access these model files using absolute path /opt/imx8-isp/boson/something.

