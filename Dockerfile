FROM ubuntu:24.04

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# 安装 Python + 基础依赖 + 证书
RUN apt-get update && apt-get upgrade -y && \
    apt-get install -y --no-install-recommends \
    python3 python3-dev gcc g++ build-essential \
    libpq-dev libffi-dev wget curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# 用 get-pip.py 安装 pip
RUN curl -sS https://bootstrap.pypa.io/get-pip.py | python3

# 固定 setuptools 版本
RUN python3 -m pip install --no-cache-dir setuptools==78.1.1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]
s