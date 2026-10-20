# Firefly Mini — Autonomous Cyber-Cat Desktop Agent & Defense Sentinel
# Containerized Test & Development Environment (Feature 118)

FROM python:3.11-slim-bookworm

# System dependencies for audio synthesis, sandboxing, and terminal graphics
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    alsa-utils \
    pulseaudio-utils \
    bubblewrap \
    curl \
    git \
    procps \
    && rm -rf /var/lib/apt/lists/*

# Create unprivileged application user
RUN useradd -m -u 1000 -s /bin/bash firefly

WORKDIR /home/firefly/app

# Copy dependency manifests first for build caching
COPY --chown=firefly:firefly pyproject.toml requirements.txt ./

# Install package dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -e ".[dev]" pyyaml

# Copy full application codebase
COPY --chown=firefly:firefly . .

USER firefly

ENV PYTHONUNBUFFERED=1 \
    LC_ALL=C.UTF-8 \
    LANG=C.UTF-8 \
    FIREFLY_AUTO_APPROVE_MAX_RISK=1

CMD ["firefly", "status"]
