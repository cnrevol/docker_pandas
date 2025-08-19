# 使用轻量级 Python 基础镜像
FROM python:3.11

# 设置环境变量（优化 Python 运行时）
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# 设置工作目录
WORKDIR /app

# 先复制依赖清单，安装依赖（利用缓存）
COPY requirements.txt .

RUN pip install --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# 再复制应用代码
COPY . .

# 暴露容器端口（uvicorn 会监听 8000）
EXPOSE 8000

# 启动命令（使用 uvicorn 启动 FastAPI）
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
