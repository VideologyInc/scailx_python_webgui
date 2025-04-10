#!/usr/bin/env python3

from setuptools import setup, find_packages
import os
import shutil
import importlib.util
from setuptools.command.install import install

# Check if vdlg_lvds is already installed
def is_package_installed(package_name):
    """Check if a package is already installed"""
    try:
        spec = importlib.util.find_spec(package_name)
        return spec is not None
    except (ModuleNotFoundError, ValueError):
        return False

class PostInstallCommand(install):
    """Post-installation for installation mode."""
    def run(self):
        # Run parent install first
        install.run(self)
# Install systemd service file
print("Installing systemd service file...")
systemd_dir = '/etc/systemd/system/'
service_file_path = 'webservice.service'

if os.path.exists(service_file_path):
    if not os.path.exists(systemd_dir):
        os.makedirs(systemd_dir, exist_ok=True)

    # Copy service file to systemd directory
    shutil.copy2(service_file_path, os.path.join(systemd_dir, 'webservice.service'))

    # Reload systemd daemon
    os.system('systemctl daemon-reload')
    print(f"Systemd service file installed to {systemd_dir}webservice.service")
    print("To enable and start the service, run:")
    print("  sudo systemctl enable webservice.service")
    print("  sudo systemctl start webservice.service")
else:
    print(f"Warning: webservice.service file not found at {service_file_path}")
            print("Warning: webservice.service file not found in current directory")

setup(
    name="scailx_python_webgui",
    version="0.1.0",
    description="Scailx simple web UI",
    author="Scailx",
    packages=['scailx_python_webgui'],
    include_package_data=True,
    install_requires=[
        "fastapi",
        "uvicorn",
        "psutil",
        "pyyaml",
    ] + ([] if is_package_installed("vdlg_lvds") else ["vdlg_lvds @ git+https://github.com/VideologyInc/kernel-module-crosslink"]),
    python_requires=">=3.6",
    cmdclass={
        'install': PostInstallCommand,
    },
    # Include non-python files
    package_data={
        'scailx_python_webgui': [
            'public/*',
            'public/assets/*',
            'public/assets/fonts/*',
            'public/assets/scripts/*',
        ],
    },
    # Include data files
    data_files=[
        ('', ['webservice.service']),
    ],
    # Create a scailx-webgui command to run the server
    entry_points={
        'console_scripts': [
            'scailx-webgui=scailx_python_webgui.server:main',
        ],
    },
)