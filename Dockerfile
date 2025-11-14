# --------------------------------------------------------
# Stage 1: Build dependencies using standard Python build
# --------------------------------------------------------
FROM python:3.11 AS builder

WORKDIR /app

# upgrade pip
RUN pip install --no-cache-dir --upgrade pip

# Install dependencies to /deps
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Copy source code
COPY . .

# --------------------------------------------------------
# Stage 2: Ultra-secure runtime image (Chainguard Python 3.11)
# --------------------------------------------------------
FROM cgr.dev/chainguard/python:3.11 AS runtime

WORKDIR /app

# Copy installed Python libs
COPY --from=builder /install /usr/local

# Copy application code
COPY --from=builder /app /app

EXPOSE 8000

CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]
