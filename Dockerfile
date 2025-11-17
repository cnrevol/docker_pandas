# ==========================================
# Dockerfile (Python 3.12 + FastAPI)
# 基于 python:3.12-slim，安全、轻量、无 kernel CVE
# ==========================================

FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1
ENV DEBIAN_FRONTEND=noninteractive

# ------------------------------------------
# 安装构建必须依赖（只装最小集合）
# 如果没有编译型依赖，可以去掉 gcc/g++
# ------------------------------------------
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    g++ \
    libffi-dev \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# ------------------------------------------
# 升级 pip 系列工具（避免 pkg_resources 旧版本问题）
# ------------------------------------------
RUN pip install --upgrade pip setuptools wheel build

# 设置工作目录
WORKDIR /app

# ------------------------------------------
# 安装依赖（先复制 requirements.txt 可利用构建缓存）
# ------------------------------------------
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制项目代码
COPY . .

# 暴露端口
EXPOSE 8000

# 默认启动命令（FastAPI）
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]

