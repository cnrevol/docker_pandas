FROM ubuntu:24.04

# 设置非交互模式
ENV DEBIAN_FRONTEND=noninteractive

# 1. 安装 Python 3.12 + 构建工具
RUN apt-get update && apt-get install -y \
    python3.12 python3.12-venv python3.12-dev \
    build-essential gcc g++ make \
    libffi-dev libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# 2. 创建虚拟环境
RUN python3.12 -m venv /opt/venv

# 3. 确保 pip / setuptools / wheel 完整可用
RUN /opt/venv/bin/pip install --upgrade pip setuptools wheel

# 4. 复制项目文件
WORKDIR /app
COPY requirements.txt .

# 5. 安装依赖
RUN /opt/venv/bin/pip install --no-cache-dir -r requirements.txt

# 6. 复制代码
COPY . .

# 7. 设置 PATH
ENV PATH="/opt/venv/bin:$PATH"


# 使用 venv 的 python 运行
CMD ["/opt/venv/bin/python3", "-m", "uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]
