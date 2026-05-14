#!/bin/sh
cd "$(dirname "$0")"
pip3 install -r requirements.txt -q
exec python3 monitor.py
