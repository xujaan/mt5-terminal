"""Log the terminal into the account given by env vars, then exit.

This replaces the VNC-typing auto-login (kept as assets/auto_login_vnc.py for
reference). That script connected to :5900, clicked at pixel coordinates and
typed into whatever had focus; it broke whenever MetaQuotes moved a button.
MetaTrader5.initialize() does the same thing through the documented API and
tells you *why* it failed when it fails.

Runs under the Windows interpreter inside the wine prefix, so it can import the
win_amd64 MetaTrader5 package.

Exit codes: 0 logged in (or no credentials configured and the terminal is at
least reachable), 1 credentials configured but login failed.
"""

import os
import sys
import time

import MetaTrader5 as mt5

ATTEMPTS = 6
DELAY_SECONDS = 5


def env(name: str) -> str:
    return (os.getenv(name) or "").strip()


def describe_error() -> str:
    code, message = mt5.last_error()
    return f"code={code} message={message}"


def attempt(login: int, password: str, server: str) -> bool:
    if login:
        return mt5.initialize(
            login=login,
            password=password,
            server=server,
            timeout=60000,
            portable=False,
        )
    # No credentials: attach to the terminal supervisor already started and use
    # whatever account it last remembered.
    return mt5.initialize(timeout=60000)


def main() -> int:
    raw_login = env("MT5_ACCOUNT_NUMBER")
    password = os.getenv("MT5_PASSWORD") or ""
    server = env("MT5_SERVER")

    login = 0
    if raw_login:
        try:
            login = int(raw_login)
        except ValueError:
            print(f"[auto_login] MT5_ACCOUNT_NUMBER is not an integer: {raw_login!r}", flush=True)
            return 1
        if not server or not password:
            print(
                "[auto_login] MT5_ACCOUNT_NUMBER is set but MT5_SERVER/MT5_PASSWORD "
                "is empty -- refusing to try a login that cannot work",
                flush=True,
            )
            return 1
        print(f"[auto_login] logging in as {login} on {server}", flush=True)
    else:
        print("[auto_login] no MT5_ACCOUNT_NUMBER set; attaching to the running terminal", flush=True)

    for i in range(1, ATTEMPTS + 1):
        if attempt(login, password, server):
            info = mt5.account_info()
            if info is not None:
                print(
                    f"[auto_login] connected: account {info.login} ({info.server}), "
                    f"balance {info.balance} {info.currency}, leverage 1:{info.leverage}",
                    flush=True,
                )
            else:
                print("[auto_login] initialize() succeeded but account_info() is empty", flush=True)
            mt5.shutdown()
            return 0
        print(f"[auto_login] attempt {i}/{ATTEMPTS} failed: {describe_error()}", flush=True)
        if i < ATTEMPTS:
            time.sleep(DELAY_SECONDS)

    print(f"[auto_login] giving up: {describe_error()}", flush=True)
    return 1


if __name__ == "__main__":
    sys.exit(main())
