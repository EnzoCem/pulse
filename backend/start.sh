#!/bin/bash
# Pulse backend — starts Flask server on port 5001
cd "$(dirname "$0")"
python3 -m venv .venv 2>/dev/null || true
source .venv/bin/activate
pip install -q -r requirements.txt
python3 server.py
