FROM ghcr.io/prefix-dev/pixi:latest

LABEL org.opencontainers.image.source="https://github.com/LABGeM/MetaPanG"

RUN apt-get update \
 && apt-get install -y --no-install-recommends procps \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . /app

ARG GIT_COMMIT=""
RUN [ -z "$GIT_COMMIT" ] || printf 'COMMIT = "%s"\n' "$GIT_COMMIT" > /app/metapang/_commit.py

RUN pixi install --locked -e default -e metagraph

RUN pixi shell-hook -e default -s bash > /shell-hook.sh

ENTRYPOINT ["/bin/bash", "-c", "source /shell-hook.sh && exec metapang \"$@\"", "--"]
CMD ["--help"]
