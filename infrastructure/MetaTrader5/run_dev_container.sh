#!/bin/sh
# Rebuild happens separately; this just runs the image with the local .env.
# 8080 = noVNC web desktop, 1234 = rpyc.
docker run --rm -it \
  -p 8080:8080/tcp -p 1234:1234/tcp \
  --shm-size 256m \
  --env-file ./.env \
  --name mt5_terminal \
  mt5-python-wine:dev
