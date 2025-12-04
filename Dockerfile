FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

# Step 1: 创建非 root 用户（尽早创建）
RUN groupadd -g 999 appgroup && \
    useradd -m -u 999 -g appgroup appuser

# Step 2: 安装 Python + 构建工具
RUN apt-get update && apt-get install -y \
    python3.12 python3.12-venv python3.12-dev \
    build-essential gcc g++ \
    libffi-dev libssl-dev \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Step 3: 创建虚拟环境并设置权限
RUN python3.12 -m venv /opt/venv && \
    chown -R appuser:appgroup /opt/venv

ENV PATH="/opt/venv/bin:$PATH"

# Step 4: 切换到非 root 用户进行后续操作
USER appuser

# Step 5: 升级 pip（以非 root 用户身份）
RUN pip install --upgrade pip setuptools wheel

# Step 6: 创建工作目录
WORKDIR /app

# Step 7: 安装依赖
COPY --chown=appuser:appgroup requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Step 8: 复制应用代码
COPY --chown=appuser:appgroup . .

# Step 9: 清理（需要切换回 root）
USER root
RUN apt-get update && apt-get remove -y \
    python3-pip-whl \
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

# Step 10: 最终切换回非 root 用户
USER appuser

EXPOSE 8000

CMD ["python3", "-m", "uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]