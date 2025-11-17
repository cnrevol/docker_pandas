# -----------------------------
# Dockerfile: Python 3.12 + FastAPI + Ubuntu 24.04
# -----------------------------
FROM ubuntu:24.04

# 设置非交互模式
ENV DEBIAN_FRONTEND=noninteractive

# 安装基础依赖 + Python 3.12 + 编译工具
RUN apt-get update && apt-get install -y \
    python3.12 python3.12-venv python3.12-dev \
    build-essential gcc g++ make gfortran \
    libopenblas-dev liblapack-dev \
    libffi-dev libssl-dev curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# 创建 Python 虚拟环境
RUN python3.12 -m venv /opt/venv

# 升级 pip、setuptools、wheel、build
RUN /opt/venv/bin/python -m pip install --upgrade pip setuptools wheel build

# 设置工作目录
WORKDIR /app

# 复制依赖文件并安装
COPY requirements.txt .
# 强制使用最新 build 环境
RUN /opt/venv/bin/python -m pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY . .

# 设置 PATH，优先使用虚拟环境
ENV PATH="/opt/venv/bin:$PATH"

# 暴露端口
EXPOSE 8000

# 启动命令
CMD ["python3", "-m", "uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]
