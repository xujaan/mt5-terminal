# MetaTrader 5 terminal on Wine 11, with rpyc and a web desktop

A container that runs the **MetaTrader 5 terminal** on Linux and exposes two
things you can actually use from outside:

| Port | What | Notes |
| --- | --- | --- |
| `8080` | noVNC web desktop (HTTP) | put basic auth in front of it at the ingress |
| `1234` | rpyc endpoint | a Windows Python process living next to the terminal |
| `5900` | raw VNC | bound to loopback inside the container only |

Image: `ghcr.io/xujaan/mt5-python-wine` (also `docker.io/xujaan/mt5-python-wine`
when the Docker Hub secrets are configured).

## Why this exists, and what was wrong with the old image

This folder used to build on `tobix/pywine:3.9`, i.e. **Wine 7**, and its
Dockerfile ended with:

```
# TODO: upgrade to wine >= 8 as wine 7 is unstable and unsupported by MT5
```

That TODO is the entire failure mode. MetaQuotes retires old terminal builds on
its servers, so an image pinned to an abandoned Wine does not merely crash —
eventually it cannot log in to the broker at all, and no amount of correct
credentials helps. A terminal that cannot reach the trade server is worse than
no terminal, because it looks like it is working.

The base is now `ubuntu:24.04` + WineHQ's `winehq-stable` (**11.x**), the same
combination MetaQuotes' own Linux users run.

Three other changes:

1. **MT5 is installed at build time** from the official MetaQuotes installer
   (`wine mt5setup.exe /auto`) instead of being unpacked from a 172 MB Git-LFS
   tarball. Consequence: the image can never ship a terminal that is already
   years old, and this repository does not redistribute MetaQuotes binaries.
   If MetaQuotes moves the URL, the build fails loudly instead of silently
   producing a dead image.
2. **Login uses the API, not keystrokes.** The old `auto_login.py` drove the VNC
   session by clicking pixel coordinates (`client.mouseMove(20, 22)`) and typing
   into whatever had focus; it broke whenever a dialog moved. It is kept as
   `assets/auto_login_vnc.py` for reference, and replaced by
   `MetaTrader5.initialize(login=..., password=..., server=...)`, which also
   reports *why* it failed.
3. **Ports match the deployment**: `8080` + `1234`, not `18812` + `8000`.

## Build

```bash
docker build -t xujaan/mt5-python-wine:latest infrastructure/MetaTrader5
```

The build pulls ~2 GB (WineHQ, a Windows Python, the terminal itself), so
building on GitHub Actions is the intended path — see
[`.github/workflows/build-mt5-wine.yml`](../../.github/workflows/build-mt5-wine.yml),
which builds, pushes, and then **smoke-tests the pushed image** (wine version,
terminal binary, noVNC HTTP 200, rpyc accepting a connection, `import
MetaTrader5` inside the prefix).

## Run

```bash
docker run -d --name mt5 \
  -p 8080:8080 -p 1234:1234 \
  -e MT5_ACCOUNT_NUMBER=12345678 \
  -e MT5_PASSWORD='...' \
  -e MT5_SERVER='Broker-Server-01' \
  ghcr.io/xujaan/mt5-python-wine:latest
```

Then open <http://localhost:8080/> for the desktop.

To keep the terminal's own state (saved passwords, charts, history) across
container replacement, mount the terminal data directory:

```bash
-v mt5data:/opt/wineprefix/drive_c/users/root/AppData/Roaming/MetaQuotes
```

## Environment variables

| Variable | Default | Meaning |
| --- | --- | --- |
| `MT5_ACCOUNT_NUMBER` | *(empty)* | Account to log in to. Empty → attach to the terminal without logging in; finish the login in the web desktop. |
| `MT5_PASSWORD` | *(empty)* | Account password. |
| `MT5_SERVER` | *(empty)* | Broker server name exactly as MT5 shows it, e.g. `Exness-MT5Real8`. |
| `SERVER_HOST` | `0.0.0.0` | rpyc bind address. |
| `SERVER_PORT` | `1234` | rpyc port. |
| `NOVNC_PORT` | `8080` | noVNC HTTP port. |
| `VNC_GEOMETRY` | `1280x800` | Desktop size. |

A missing or wrong credential set is **not** fatal: `run_server.sh` starts the
rpyc server anyway, and `auto_login.py` says what went wrong in the logs.

## Talking to it from Python

The rpyc endpoint runs the *Windows* interpreter inside the prefix, because the
`MetaTrader5` package is a `win_amd64` wheel — there is no Linux import of it.

```python
import rpyc

conn = rpyc.classic.connect("localhost", 1234)          # plain, no TLS
mt5 = conn.modules["MetaTrader5"]                       # the real Windows module
print(mt5.terminal_info())
print(mt5.account_info())

# Run something in the container's Windows Python:
conn.execute("import MetaTrader5 as mt5; print(mt5.symbols_total())")
```

rpyc's classic service executes arbitrary code for anyone who can reach the
port. Do **not** expose `1234` on the public internet; keep it ClusterIP-only
(as the manifest does) and reach it through a port-forward.

## Kubernetes

[`k8s/mt5-deployment.yaml`](k8s/mt5-deployment.yaml) is the deployment,
service, basic-auth secret and ingress (`mt5.gnt.my.id`). Credentials come from
an optional secret so the pod starts even before you create it:

```bash
kubectl -n third-party create secret generic mt5-credentials \
  --from-literal=MT5_ACCOUNT_NUMBER='12345678' \
  --from-literal=MT5_PASSWORD='...' \
  --from-literal=MT5_SERVER='Broker-Server-01'
```

## Licence note

The image contains MetaTrader 5, downloaded from MetaQuotes at build time.
MetaQuotes' licence does not grant redistribution of the terminal, so a
**public** Docker Hub repository is a grey area; keeping the repository private
(and pulling it with an `imagePullSecret`) is the safer choice. The surrounding
code in this repository is MIT.

## Known limitations

- **No broker login is tested in CI.** The smoke test proves Wine, the terminal
  binary, the web desktop, rpyc and the Windows Python stack work; whether *your*
  account logs in depends on your broker's server, and is verified by you.
- **Wine 11 is not Windows.** Some MT5 features (specific indicators' graphics,
  the news feed, some MQL5 market content) behave differently or need the
  terminal restarted once.
- **Single terminal per container.** Two terminals sharing one prefix corrupt
  each other's data directory; run two pods if you need two accounts.
