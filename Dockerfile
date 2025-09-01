# ----------------------------------------------------
# 使用官方 Ubuntu 24.04 LTS 作为基础镜像
# ----------------------------------------------------
FROM ubuntu:24.04

# ----------------------------------------------------
# 安装软件源管理工具和 `deadsnakes` PPA
# ----------------------------------------------------
RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        software-properties-common \
    && rm -rf /var/lib/apt/lists/* && \
    add-apt-repository ppa:deadsnakes/ppa

# ----------------------------------------------------
# 安装 Python 3.11 和其他系统依赖
# ----------------------------------------------------
# 再次更新 apt-get 以便加载新的 PPA 包信息
# 注意：这里添加了 python3.11-distutils 包
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
    && apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# ----------------------------------------------------
# 配置环境和安装 Python 依赖
# ----------------------------------------------------
# 设置环境变量，优化 Python 运行时
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# 升级 pip 和 setuptools
RUN python3.11 -m pip install --no-cache-dir --upgrade pip setuptools wheel

# 设置工作目录
WORKDIR /app

# 复制依赖文件并安装依赖
COPY requirements.txt .
RUN python3.11 -m pip install --no-cache-dir -r requirements.txt

# ----------------------------------------------------
# 复制应用代码和配置启动命令
# ----------------------------------------------------
# 复制应用代码
COPY . .

# 暴露端口
EXPOSE 8000

# 启动 FastAPI 应用
CMD ["python3.11", "-m", "uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]