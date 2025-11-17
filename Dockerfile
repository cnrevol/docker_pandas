FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

# Step 1: 安装 Python + 构建工具（只用于构建阶段）
RUN apt-get update && apt-get install -y \
    python3.12 python3.12-venv python3.12-dev \
    build-essential gcc g++ \
    libffi-dev libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Step 2: 创建虚拟环境
RUN python3.12 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

RUN pip install --upgrade pip setuptools wheel build

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Step 3: 删除高风险 dev 包（非常关键）
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
