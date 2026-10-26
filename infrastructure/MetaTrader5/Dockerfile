# syntax=docker/dockerfile:1.7
#
# MetaTrader 5 terminal on a current Wine, with rpyc (:1234) and noVNC (:8080).
#
# WHAT CHANGED AND WHY
# --------------------
# This image used to sit on `tobix/pywine:3.9`, i.e. Wine 7. Upstream's own
# Dockerfile ended with `# TODO: upgrade to wine >= 8 as wine 7 is unstable and
# unsupported by MT5`, and that TODO is the whole problem: MetaQuotes drops old
# terminal builds from its trade servers, so an image pinned to an abandoned
# Wine eventually cannot log in at all, no matter what credentials you give it.
#
# So the base is now plain ubuntu:24.04 + WineHQ `winehq-stable` (11.x at the
# time of writing), which is the combination MetaQuotes' own Linux users run and
# the one WineHQ actually tests.
#
# Two further differences from upstream:
#
#   1. MT5 is NOT baked in from a 172 MB git-LFS tarball. It is installed at
#      build time from the official MetaQuotes installer (`/auto`), so the image
#      can never ship a terminal build that is already years old, and this repo
#      does not have to redistribute MetaQuotes binaries through LFS.
#   2. Windows Python lives at C:\Python311 and the rpyc slave runs *inside* the
#      wine prefix, because the MetaTrader5 package is a Windows-only wheel.
#      That is what makes :1234 useful: every call is executed next to the
#      terminal, not across a wine boundary.
#
# Landing ports match the k8s manifest this image is deployed with: 8080 serves
# the noVNC web desktop (put basic auth in front of it at the ingress), 1234 is
# the rpyc endpoint. VNC 5900 stays bound to loopback inside the container.

FROM ubuntu:24.04

LABEL org.opencontainers.image.source="https://github.com/xujaan/mt5-terminal"
LABEL org.opencontainers.image.description="MetaTrader 5 terminal on Wine 11 (64-bit) with rpyc API (:1234) and noVNC web desktop (:8080)"
LABEL org.opencontainers.image.licenses=MIT
LABEL org.opencontainers.image.base.name="docker.io/library/ubuntu:24.04"

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

ENV DEBIAN_FRONTEND=noninteractive \
    DISPLAY=:0 \
    LANG=C.UTF-8 \
    HOME=/root \
    WINEPREFIX=/opt/wineprefix \
    WINEARCH=win64 \
    WINEDEBUG=-all \
    WINEDLLOVERRIDES=mscoree,mshtml= \
    SERVER_HOST=0.0.0.0 \
    SERVER_PORT=1234 \
    NOVNC_PORT=8080 \
    VNC_DESKTOP_NAME=Metatrader5 \
    VNC_GEOMETRY=1280x800 \
    MT5_TERMINAL=/opt/wineprefix/drive_c/Program Files/MetaTrader 5/terminal64.exe \
    WINPY=C:\\Python311\\python.exe \
    MT5_ACCOUNT_NUMBER="" \
    MT5_PASSWORD="" \
    MT5_SERVER=""

ARG PYTHON_VERSION=3.11.9
ARG MT5_SETUP_URL=https://download.mql5.com/cdn/web/metaquotes.software.corp/mt5/mt5setup.exe

# --- Wine, from WineHQ's own repository (not Debian's, which lags badly) ------
# i386 is enabled because the winehq-stable metapackage pulls the 32-bit build
# too; MT5 itself is 64-bit only.
RUN dpkg --add-architecture i386 \
    && apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates wget gnupg \
    && mkdir -p /etc/apt/keyrings \
    && wget -qO /etc/apt/keyrings/winehq-archive.key https://dl.winehq.org/wine-builds/winehq.key \
    && wget -qO /etc/apt/sources.list.d/winehq-noble.sources \
         https://dl.winehq.org/wine-builds/ubuntu/dists/noble/winehq-noble.sources \
    && apt-get update \
    && apt-get install -y --install-recommends winehq-stable \
    && wine --version \
    && rm -rf /var/lib/apt/lists/*

# --- virtual desktop, web front end, supervisor ---------------------------------
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        xvfb x11vnc openbox supervisor novnc websockify \
        curl procps cabextract fonts-dejavu-core fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

# --- a fresh 64-bit prefix ------------------------------------------------------
# wineboot writes the registry and creates drive_c; without a display it still
# works, but it is chatty, so it runs under xvfb-run like everything else here.
RUN xvfb-run -a wineboot --init \
    && wineserver -w \
    && test -d "$WINEPREFIX/drive_c"

# --- Windows Python inside the prefix -------------------------------------------
# The MetaTrader5 wheel is win_amd64 only; the rpyc slave therefore has to be a
# Windows interpreter, otherwise `import MetaTrader5` does not exist at all.
RUN wget -q "https://www.python.org/ftp/python/${PYTHON_VERSION}/python-${PYTHON_VERSION}-amd64.exe" -O /tmp/python.exe \
    && xvfb-run -a wine /tmp/python.exe /quiet InstallAllUsers=1 PrependPath=1 \
         Include_test=0 Include_launcher=0 "TargetDir=C:\\Python311" \
    && wineserver -w \
    && rm -f /tmp/python.exe \
    && wine "$WINPY" --version

COPY assets/requirements.txt /tmp/requirements.txt

RUN wine "$WINPY" -m pip install --no-cache-dir --upgrade pip setuptools wheel \
    && wine "$WINPY" -m pip install --no-cache-dir -r /tmp/requirements.txt \
    && wine "$WINPY" -c "import MetaTrader5, rpyc, plumbum; print('rpyc', rpyc.__version__)"

# --- MetaTrader 5, from MetaQuotes' installer -----------------------------------
# /auto is the documented unattended mode. The installer downloads the terminal
# itself, so a build failure here means MetaQuotes moved the URL or the flag --
# which is exactly the failure that should be loud rather than shipped.
RUN wget -q "$MT5_SETUP_URL" -O /tmp/mt5setup.exe \
    && xvfb-run -a wine /tmp/mt5setup.exe /auto \
    && wineserver -w \
    && rm -f /tmp/mt5setup.exe \
    && if [ ! -f "$MT5_TERMINAL" ]; then \
         echo "ERROR: MT5 installer did not produce $MT5_TERMINAL"; \
         find "$WINEPREFIX/drive_c" -maxdepth 4 -iname 'terminal64.exe' -o -maxdepth 2 -type d -print; \
         exit 1; \
       fi \
    && ls -la "$(dirname "$MT5_TERMINAL")"

# --- this repo's server + supervisor config -------------------------------------
WORKDIR /root
COPY assets/supervisord.conf /etc/supervisord.conf
COPY assets/run_server.sh assets/auto_login.py assets/healthcheck.sh /root/
COPY assets/server.py assets/menu.xml /root/
COPY assets/MQL5 /root/MQL5

RUN chmod +x /root/run_server.sh /root/healthcheck.sh \
    && mkdir -p /root/.config/openbox \
    && cp /root/menu.xml /root/.config/openbox/menu.xml

# 8080 = noVNC (this is what the ingress talks to)
# 1234 = rpyc slave, running the Windows interpreter next to the terminal
# 5900 = raw VNC, bound to loopback inside the container only
EXPOSE 8080 1234 5900

HEALTHCHECK --interval=30s --timeout=5s --start-period=90s --retries=5 \
    CMD ["/root/healthcheck.sh"]

CMD ["/usr/bin/supervisord", "-c", "/etc/supervisord.conf"]
