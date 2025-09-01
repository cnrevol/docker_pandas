# 构建阶段
FROM python:3.11-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y gcc g++ build-essential libpq-dev python3-dev libffi-dev wget \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir --upgrade pip setuptools==78.1.1 wheel

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# 运行阶段
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y libpq-dev libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# 只拷贝 site-packages 和 bin，避免覆盖标准库
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY --from=builder /app /app

EXPOSE 8000

CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]
