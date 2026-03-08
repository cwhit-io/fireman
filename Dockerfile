# syntax=docker/dockerfile:1
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# System deps:
# - cups-client: lp, lpstat, lpadmin (client-side printing)
# - ca-certificates: common TLS dependency for pip/npm fetching
# - curl: useful for debugging and often required in builds
RUN apt-get update && apt-get install -y --no-install-recommends \
    cups-client \
    ca-certificates \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js (better than Debian's often-old nodejs/npm)
# If you truly only need Tailwind in dev, consider moving this to a dev-only image.
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get update \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

RUN lpadmin -p fiery_hold -E \
  -v lpd://10.10.96.103/hold \
  -m raw

# Python deps
COPY requirements.txt ./
RUN pip install --upgrade pip && pip install -r requirements.txt

# Node deps
COPY package.json package-lock.json* ./
RUN npm ci --omit=dev

# App source
COPY . .

# Helpful sanity check (optional; remove if you want)
RUN command -v lp lpstat lpadmin

EXPOSE 8085
