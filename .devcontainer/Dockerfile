FROM mcr.microsoft.com/devcontainers/python:3.14-trixie

USER root
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

USER vscode