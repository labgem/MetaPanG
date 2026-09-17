# Build from the repository root:
#   docker build -f packaging/docker/Dockerfile -t metapang .
FROM mambaorg/micromamba:latest

COPY --chown=$MAMBA_USER:$MAMBA_USER packaging/docker/env.yaml /tmp/env.yaml
RUN micromamba install -y -n base -f /tmp/env.yaml && \
    micromamba clean --all --yes

COPY --chown=$MAMBA_USER:$MAMBA_USER pyproject.toml README.md LICENSE /src/
COPY --chown=$MAMBA_USER:$MAMBA_USER metapang /src/metapang
RUN micromamba run -n base python -m pip install --no-cache-dir /src

ENV PATH=/opt/conda/bin:/opt/conda/condabin:$PATH

# _entrypoint.sh activates the base environment before running the command.
ENTRYPOINT ["/usr/local/bin/_entrypoint.sh", "metapang"]
CMD ["--help"]
