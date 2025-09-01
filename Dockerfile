# ----------------------------------------------------
# 第一阶段：构建和安装依赖
# ... (这个阶段不需要改动) ...
# ----------------------------------------------------
FROM ubuntu:24.04 AS builder

# 安装软件源管理工具和 `deadsnakes` PPA
RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        software-properties-common \
    && rm -rf /var/lib/apt/lists/* && \
    add-apt-repository ppa:deadsnakes/ppa

# 安装 Python 3.11 和所有构建依赖
RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        python3.11 \
        python3.11-dev \
        python3.11-venv \
        python3.11-distutils \
        build-essential \
        libpq-dev \
        libffi-dev \
        wget \
        linux-libc-dev \
    && apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# 在第一阶段安装 pip 并安装所有 Python 依赖
RUN python3.11 -m ensurepip --upgrade
RUN python3.11 -m pip install --no-cache-dir --upgrade pip setuptools wheel

# 将依赖安装到 /usr/src/app 目录
WORKDIR /usr/src/app
COPY requirements.txt .
RUN python3.11 -m pip install --no-cache-dir -r requirements.txt \
    --target=/usr/src/app

# ----------------------------------------------------
# 第二阶段：创建精简的最终镜像
# ----------------------------------------------------
FROM python:3.11-slim

# 设置环境变量
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# 复制第一阶段安装的 Python 依赖和你的应用代码
COPY --from=builder /usr/src/app /usr/src/app
WORKDIR /usr/src/app
COPY . .

# 在最终镜像中升级 setuptools
# 这会覆盖掉 python:3.11-slim 自带的旧版本
RUN python -m pip install --no-cache-dir --upgrade setuptools

# 暴露端口
EXPOSE 8000

# 启动 FastAPI 应用
CMD ["python3.11", "-m", "uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]