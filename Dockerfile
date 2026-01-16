# ===============================
# Base image
# ===============================
FROM python:3.11-bookworm

# ===============================
# System packages (FreeCAD + Qt headless)
# ===============================
RUN apt-get update && apt-get install -y --no-install-recommends \
    freecad \
    freecad-common \
    freecad-python3 \
    libgl1 \
    libglib2.0-0 \
    libxkbcommon0 \
    libxrender1 \
    libxext6 \
    libsm6 \
    libx11-6 \
    libxcb1 \
    libxcb-render0 \
    libxcb-shm0 \
    libxcb-xfixes0 \
    libxrandr2 \
    libxi6 \
    libxinerama1 \
    libxcursor1 \
    libxdamage1 \
    libfontconfig1 \
    libfreetype6 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# ===============================
# Workdir
# ===============================
WORKDIR /app

# ===============================
# Python deps
# ===============================
COPY backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# ===============================
# App source
# ===============================
COPY backend /app/backend

# ===============================
# Environment (🔥 핵심)
# ===============================
# Qt GUI 완전 차단 (서버용)
ENV QT_QPA_PLATFORM=offscreen

# FreeCAD Python 경로
ENV PYTHONPATH=/app/backend:/usr/lib/python3/dist-packages:/usr/lib/freecad-python3/lib:/usr/lib/freecad/lib:/usr/share/freecad/Mod

# Python 로그 즉시 출력
ENV PYTHONUNBUFFERED=1

# ===============================
# Port
# ===============================
EXPOSE 8000

# ===============================
# Run server
# ===============================
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
