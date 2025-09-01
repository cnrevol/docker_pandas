# ----------------------------------------------------
# 第一阶段：构建和安装依赖
# 使用一个完整的镜像来执行编译和安装
# ----------------------------------------------------
FROM ubuntu:24.04 AS builder

# 安装软件源管理工具和 `deadsnakes` PPA
RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        software-properties-common \
    && rm -rf /var/lib/apt/lists/* && \
    add-apt-repository ppa:deadsnakes/ppa

# 安装 Python 3.11 和所有构建依赖，包括 linux-libc-dev
# 注意：这些包只存在于这个阶段，不会进入最终镜像
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

# 设置工作目录并安装 Python 依赖
WORKDIR /app
COPY requirements.txt .
RUN python3.11 -m pip install --no-cache-dir --upgrade pip setuptools wheel
RUN python3.11 -m pip install --no-cache-dir -r requirements.txt \
    --target=/usr/src/app

# ----------------------------------------------------
# 第二阶段：创建精简的最终镜像
# 只包含运行时所需的文件
# ----------------------------------------------------
FROM python:3.11-slim

# 设置环境变量，优化 Python 运行时
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# 复制第一阶段安装的 Python 依赖和你的应用代码
COPY --from=builder /usr/src/app /usr/src/app
WORKDIR /usr/src/app
COPY . .

# 暴露端口
EXPOSE 8000

# 启动 FastAPI 应用
CMD ["python3.11", "-m", "uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]