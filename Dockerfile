# api 컨테이너. 모델(4GB)과 데이터는 이미지에 넣지 않고 compose 가 볼륨으로 붙인다.
FROM python:3.12-slim

# torch 는 CPU 판. 기본 인덱스의 CUDA 빌드는 이미지를 수 GB 키운다.
ENV PIP_EXTRA_INDEX_URL=https://download.pytorch.org/whl/cpu \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src \
    HF_HOME=/models \
    TOKENIZERS_PARALLELISM=false

WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends build-essential curl \
    && rm -rf /var/lib/apt/lists/*

# 패키지를 먼저 깐다. 코드만 바뀌면 이 층은 캐시에서 온다(재빌드 10초).
COPY requirements.txt ./
RUN grep -v -i "jupyterlab" requirements.txt > /tmp/req.txt \
    && pip install --no-cache-dir -r /tmp/req.txt

COPY src ./src
COPY pipelines ./pipelines
COPY scripts ./scripts
COPY ui ./ui

EXPOSE 8000
CMD ["uvicorn", "finrag.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
