# Use Python 3.11 slim image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install system dependencies (including FFmpeg for video compression)
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first (for caching)
COPY requirements.txt .

# Install Python dependencies (gunicorn and eventlet are pinned in requirements.txt)
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create directories for QR codes and temp uploads
RUN mkdir -p static/qrcodes static/uploads/temp

# Expose port
EXPOSE 5000

# Run with gunicorn + eventlet for Socket.IO support
CMD ["gunicorn", "--worker-class", "eventlet", "--workers", "1", "--bind", "0.0.0.0:5000", "--timeout", "120", "app:app"]
