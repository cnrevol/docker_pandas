FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV PATH="/opt/venv/bin:$PATH"

# ---------------------------------------------------------
# Step 1: 安装 Python + 构建工具（用于构建阶段）
# ---------------------------------------------------------
RUN apt-get update && apt-get install -y \
    python3.12 python3.12-venv python3.12-dev \
    build-essential gcc g++ \
    libffi-dev libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# ---------------------------------------------------------
# Step 2: 创建 venv 并升级 pip（避免 CVE）
# ---------------------------------------------------------
RUN python3.12 -m venv /opt/venv
RUN pip install --upgrade pip setuptools wheel

# ---- 删除 Ubuntu 自带的 python3-pip-whl（有 CVE）----
RUN apt-get update && apt-get remove -y python3-pip-whl \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

# ---------------------------------------------------------
# Step 3: 删除一些不需要的系统工具（降低 CVE）
# ---------------------------------------------------------
RUN apt-get update && apt-get remove -y \
    gpgv \ 
    libssl-dev \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

# 升级 openssl 到最新 patch（减少扫描工具报警）
RUN apt-get update && apt-get install -y --only-upgrade \
    openssl libssl3t64 \
    && rm -rf /var/lib/apt/lists/*

# ---------------------------------------------------------
# Step 4: 安装 Python 项目依赖
# ---------------------------------------------------------
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 拷贝项目代码
COPY . .

# ---------------------------------------------------------
# Step 5: 删除构建依赖（极大减少 CVE）
# ---------------------------------------------------------
RUN apt-get remove -y \
    build-essential \
    gcc \
    g++ \
    python3.12-dev \
    linux-libc-dev \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/* \
       /usr/share/man/* \
       /usr/share/doc/* \
       /usr/share/local/* \
       /tmp/* \
       /var/tmp/*

EXPOSE 8000

CMD ["python3", "-m", "uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]
