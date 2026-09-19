# Eval *client* for the qualbench multimodal suite.
#
# This image contains no model and no GPU. It sends base64-encoded images
# over HTTP to an already-running FreeToken/vLLM server (on the LAN, e.g.
# http://192.168.0.88:8000) and grades the replies. That split is the whole
# point of using base64 data URLs rather than file:// paths: the container
# does not need to share a filesystem with the server.
#
# Build from the repository root so the build context includes the suite:
#   docker build -f qualbench/fixtures/multimodal/Dockerfile -t qualbench-mm .
#
# See DOCKER.md for the full runbook.

FROM python:3.12-slim

# ffmpeg/ffprobe are only needed for video items (frame extraction).
# Image-only suites run fine without them, but including them keeps the
# image usable once Video-MME media is staged.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Dependency layer first, so editing the suite does not reinstall pip deps.
COPY requirements.txt /app/requirements.txt
RUN python -m pip install --upgrade pip && python -m pip install -r /app/requirements.txt

COPY qualbench /app/qualbench

# Media is mounted at runtime (it is gigabytes and must not be baked in).
ENV QUALBENCH_MM_MEDIA_ROOT=/data/media \
    QUALBENCH_MM_SUITE=smoke

# Run as a non-root user, and make sure it can write results.
RUN useradd --create-home --uid 10001 qualbench \
    && mkdir -p /data/media /out \
    && chown -R qualbench:qualbench /app /out
USER qualbench

WORKDIR /app/qualbench/fixtures/multimodal

# Default: verify the wiring against the server given in --url.
ENTRYPOINT ["python", "check.py"]
CMD ["--all", "--emit-artifacts"]
