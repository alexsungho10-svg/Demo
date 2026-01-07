FROM python:3.11-slim

WORKDIR /app

# (주의) FreeCADCmd/Part 모듈이 필요한 경우: 기존 네 FreeCAD 기반 이미지/Dockerfile을 쓰는게 정답.
# 지금 Dockerfile은 "API/DB/흐름" 샘플용.
# FreeCAD가 필요한 운영 환경이면 기존 FreeCADCmd 이미지 기반으로 병합해줘.

COPY backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY backend /app/backend

ENV PYTHONUNBUFFERED=1
EXPOSE 8000

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
