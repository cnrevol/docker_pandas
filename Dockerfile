# 使用最新的 Ubuntu 作为基础镜像
FROM ubuntu:latest

# 设置环境变量（优化 Python 运行时）
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# 设置工作目录
WORKDIR /app

# 更新系统并安装 Python + 常用依赖
RUN apt-get update && apt-get upgrade -y && \
    apt-get install -y --no-install-recommends \
    python3 \
    python3-dev \
    python3-pip \
    gcc g++ build-essential \
    libpq-dev libffi-dev wget \
    && rm -rf /var/lib/apt/lists/*

# 升级 pip 和 setuptools（修复 CVEs）
RUN python3 -m pip install --upgrade pip setuptools==78.1.1

# 复制依赖文件并安装依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY . .

# 暴露端口
EXPOSE 8000

# 启动 FastAPI 应用
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]
