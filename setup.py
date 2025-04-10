#!/usr/bin/env python3

from setuptools import setup, find_packages
import os
import shutil
from setuptools.command.install import install

class PostInstallCommand(install):
    """Post-installation for installation mode."""
    def run(self):
        # Run parent install first
        install.run(self)

        # Install systemd service file
        print("Installing systemd service file...")
        service_file = os.path.join(self.install_dir, 'webservice.service')
        systemd_dir = '/etc/systemd/system/'

        if os.path.exists('webservice.service'):
            if not os.path.exists(systemd_dir):
                os.makedirs(systemd_dir, exist_ok=True)

            # Copy service file to systemd directory
            shutil.copy2('webservice.service', os.path.join(systemd_dir, 'webservice.service'))

            # Reload systemd daemon
            os.system('systemctl daemon-reload')
            print(f"Systemd service file installed to {systemd_dir}webservice.service")
            print("To enable and start the service, run:")
            print("  sudo systemctl enable webservice.service")
            print("  sudo systemctl start webservice.service")
        else:
            print("Warning: webservice.service file not found in current directory")

setup(
    name="scailx_python_webgui",
    version="0.1.0",
    description="Scailx simple web UI",
    author="Scailx",
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        "fastapi",
        "uvicorn",
        "psutil",
        "pyyaml",
    ],
    python_requires=">=3.6",
    cmdclass={
        'install': PostInstallCommand,
    },
    # Include non-python files
    package_data={
        '': ['*.service', 'public/*', 'public/assets/*', 'public/assets/fonts/*', 'public/assets/scripts/*'],
    },
    # Create a scailx-webgui command to run the server
    entry_points={
        'console_scripts': [
            'scailx-webgui=server:main',
        ],
    },
)