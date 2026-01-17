# Lightweight Python base image (no GPU needed for GCS)
FROM python:3.10-slim

# Install system dependencies for pymavlink
RUN apt-get update && apt-get install -y \
    build-essential \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY gcs_server.py /app/
COPY static/ /app/static/

# Expose GCS server port
EXPOSE 8080

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Run GCS server (using 127.0.0.1 for host network mode)
CMD ["python3", "gcs_server.py", "--port=8080", "--mavlink=udp:127.0.0.1:14550", "--llm-server=http://127.0.0.1:5000"]
