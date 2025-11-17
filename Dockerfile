FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# 安装系统 python3.12 + venv + pip
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-venv \
    python3-pip \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# 创建虚拟环境
RUN python3 -m venv /opt/venv

# 激活 venv 并升级 pip
RUN /opt/venv/bin/pip install --no-cache-dir --upgrade pip

# 复制依赖并安装到 venv
COPY requirements.txt .
RUN /opt/venv/bin/pip install --no-cache-dir -r requirements.txt

# 复制源代码
COPY . .

EXPOSE 8000

# 使用 venv 的 python 运行
CMD ["/opt/venv/bin/python", "-m", "uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]
