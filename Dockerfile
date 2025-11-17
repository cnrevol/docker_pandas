FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

# Step 1: 安装 Python + 构建工具（构建阶段）
RUN apt-get update && apt-get install -y \
    python3.12 python3.12-venv python3.12-dev \
    build-essential gcc g++ \
    libffi-dev libssl-dev \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Step 2: 创建虚拟环境
RUN python3.12 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# 升级 pip（避免 Ubuntu pip-whl CVE）
RUN pip install --upgrade pip setuptools wheel

# 删除高危 pip-whl（但不能删 gpgv）
RUN apt-get update && apt-get remove -y python3-pip-whl \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Step 3: 删除构建依赖（不能删系统核心依赖）
RUN apt-get remove -y \
    build-essential \
    gcc \
    g++ \
    python3.12-dev \
    libffi-dev \
    libssl-dev \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/* \
    /usr/share/man/* \
    /usr/share/doc/* \
    /tmp/* \
    /var/tmp/*

EXPOSE 8000

CMD ["python3", "-m", "uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]
