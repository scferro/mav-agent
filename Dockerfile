# Use NVIDIA TensorRT-LLM as base image
FROM nvcr.io/nvidia/tensorrt-llm/release:1.0.0

# Set working directory
WORKDIR /app

# Copy mav-agent code
COPY . /app/

# Install mav-agent Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Expose Flask server port
EXPOSE 5000

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV TLLM_WORKER_USE_SINGLE_PROCESS=1

# Default command - run the server
CMD ["python3", "server.py"]
