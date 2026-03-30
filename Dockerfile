FROM python:3.12-slim

WORKDIR /app

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git curl && rm -rf /var/lib/apt/lists/*

# Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Application code
COPY . .

# Volumes for persistent data
VOLUME ["/app/data", "/app/logs", "/app/backups"]

ENV TZ=Asia/Seoul
ENV PYTHONUNBUFFERED=1

CMD ["python", "main.py"]
