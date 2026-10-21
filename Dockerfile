FROM docker.io/library/python:3.13-slim-bookworm
ENV PYTHONUNBUFFERED=1 DISPLAY=:99 XDG_CONFIG_HOME=/data/config XDG_DATA_HOME=/data/share LIBGL_ALWAYS_SOFTWARE=1 LP_NUM_THREADS=2
RUN apt-get update && apt-get install -y --no-install-recommends xvfb x11vnc x11-utils websockify novnc nginx libgl1-mesa-dri libglx-mesa0 libegl1 libxrandr2 libxcursor1 libxi6 libxinerama1 libasound2 apache2-utils ca-certificates && rm -rf /var/lib/apt/lists/*
WORKDIR /opt/aquarium
COPY pyproject.toml LICENSE README.md ./
COPY tank ./tank
RUN pip install --no-cache-dir .
COPY container /opt/stream
EXPOSE 8099
HEALTHCHECK --interval=30s --timeout=3s --start-period=40s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8099/health')"
ENTRYPOINT ["python", "/opt/stream/entrypoint.py"]
