#!/usr/bin/env python3

import sys
import os
import argparse
import uvicorn
import logging
import socket
from scailx_python_webgui.server import app

def main():
    """
    Entry point for the scailx-webgui command.
    This function runs the FastAPI application.
    """
    parser = argparse.ArgumentParser(description='Run the Scailx Python WebGUI server')
    parser.add_argument('--dev', '-d', action='store_true', help='Run in development mode with auto-reload')
    parser.add_argument('--port', type=int, default=8089, help='Port to bind the server to')
    parser.add_argument('--workers', type=int, default=1, help='Number of worker processes')
    parser.add_argument('--log-level', default='warning', choices=['critical', 'error', 'warning', 'info', 'debug', 'trace'], help='Log level (default: info)')

    args = parser.parse_args()

    # Configure logging
    log_level = getattr(logging, args.log_level.upper())
    logging.basicConfig(level=log_level, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # Common uvicorn options
    uvicorn_options = {
        "host": "0.0.0.0",
        "port": args.port,
        "log_level": args.log_level,
        "workers": args.workers if not args.dev else 1,  # Only use 1 worker in dev mode
    }

    hostname = socket.gethostname()
    ip_addr  = socket.gethostbyname(socket.getfqdn())

    if args.dev:
        print(f"Running webgui dev at http://{hostname}.local:{args.port} or http://{ip_addr}:{args.port}")
        uvicorn.run("scailx_python_webgui.server:app", **uvicorn_options, reload=True)
    else:
        print(f"Running webgui at http://{hostname}.local:{args.port} or http://{ip_addr}:{args.port}")
        uvicorn.run("scailx_python_webgui.server:app", **uvicorn_options)

if __name__ == "__main__":
    main()
