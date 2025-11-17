# --------------------------------------------------------
# Stage 1: Build dependencies using standard Python build
# --------------------------------------------------------
FROM python:3.11 AS builder

WORKDIR /app

RUN pip install --no-cache-dir --upgrade pip

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

COPY . .

# --------------------------------------------------------
# Stage 2: Runtime image (Chainguard Python 3.11)
# --------------------------------------------------------
FROM cgr.dev/chainguard/python:3.11-dev AS runtime

WORKDIR /app

COPY --from=builder /install /usr/local
COPY --from=builder /app /app

EXPOSE 8000

CMD ["python3", "-m", "uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]
