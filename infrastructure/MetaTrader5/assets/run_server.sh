#!/bin/sh
# Start the rpyc slave that exposes this container's Windows Python.
#
# Both scripts run under the *Windows* interpreter on purpose: the MetaTrader5
# package is a win_amd64 wheel, so there is no Linux import of it to fall back
# on. Auto-login is allowed to fail without killing the server: a container that
# comes up read-only (no credentials supplied, or a broker server temporarily
# down) is still useful, and it can be logged in later through the web desktop.

set -u

PY="${WINPY:-C:\\Python311\\python.exe}"

if wine "$PY" "$HOME/auto_login.py"; then
    echo "[run_server] auto-login reported success"
else
    echo "[run_server] auto-login did not succeed -- continuing without a session"
fi

exec wine "$PY" "$HOME/server.py" --host "${SERVER_HOST:-0.0.0.0}" -p "${SERVER_PORT:-1234}"
