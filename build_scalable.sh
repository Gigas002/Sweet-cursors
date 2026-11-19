#!/bin/sh
# Builds the scalable theme; see build.py.
exec python3 "$(dirname "$0")/build.py" scalable
