# Use an official Python runtime as a parent image
FROM python:3.12-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Set work directory
WORKDIR /app

# Install system dependencies for OpenCV and SQLite
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . .

# Create directory for models and media and set permissions
RUN mkdir -p ml_models media static && chmod -R 777 ml_models media static

# Make startup script executable
RUN chmod +x start.sh

# Expose port 8000
EXPOSE 8000

# Run the startup script
CMD ["./start.sh"]
