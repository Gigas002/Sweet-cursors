#!/bin/sh
# Builds the xcursor theme; see build.py.
exec python3 "$(dirname "$0")/build.py" xcursor
