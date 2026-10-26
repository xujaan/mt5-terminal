#!/bin/sh
# Container health: the web desktop answers AND the terminal binary is where we
# expect it. Deliberately does not check a broker session -- a container with no
# credentials is healthy, just logged out.
set -eu

curl -fsS -o /dev/null --max-time 4 "http://127.0.0.1:${NOVNC_PORT:-8080}/"
test -f "$MT5_TERMINAL"
