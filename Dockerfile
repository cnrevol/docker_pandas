# ----------------------------------------------------
# Stage 1: Build dependencies with Python slim
# ----------------------------------------------------
FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install build tools only in builder stage (won't enter final image)
RUN apt-get update && \
    apt-get install -y --no-install-recommends build-essential && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Copy requirements and install into /python (target folder)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt --target /python

# Copy project code
COPY . .

# ----------------------------------------------------
# Stage 2: Distroless runtime image
# ----------------------------------------------------
FROM gcr.io/distroless/python3-debian12

WORKDIR /app

# Copy only Python dependencies + source code
COPY --from=builder /python /usr/local/lib/python3.11/site-packages
COPY --from=builder /app /app

# Expose FastAPI port
EXPOSE 8000

# Distroless requires JSON array CMD
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]
