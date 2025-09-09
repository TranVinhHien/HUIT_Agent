# ===== Stage 1: Build dependencies =====
FROM python:3.13-slim AS builder

WORKDIR /app

COPY requirements.txt .

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && pip install --no-cache-dir --prefix=/install -r requirements.txt \
    && rm -rf /var/lib/apt/lists/*

# ===== Stage 2: Runtime =====
FROM python:3.13-slim

WORKDIR /app

# Copy installed packages từ stage builder sang
COPY --from=builder /install /usr/local

# Copy source code
COPY . .

EXPOSE 10001

CMD ["python", "-m", "app.__main__"]
