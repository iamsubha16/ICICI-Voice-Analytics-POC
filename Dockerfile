# ==========================================
# 🐳 DataSutram Echo — Docker Build Stage
# ==========================================
FROM python:3.11-slim as base

# Prevent Python from writing .pyc files to disk
ENV PYTHONDONTWRITEBYTECODE=1

# Prevent Python from buffering stdout/stderr (real-time logs)
ENV PYTHONUNBUFFERED=1

# Set the container workspace directory
WORKDIR /workspace

# Install system dependencies (build-essential, curl/lib-utils if needed in the future)
# Keeps the image clean and small by purging packages and cache post-install
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy only requirements.txt to utilize Docker's build layer cache
COPY requirements.txt .

# Install Python package dependencies
RUN pip install --no-cache-dir -U pip \
    && pip install --no-cache-dir -r requirements.txt

# Create a non-privileged system user/group to run the application securely
RUN groupadd -g 10001 appgroup && \
    useradd -u 10001 -g appgroup -m -s /sbin/nologin appuser

# Copy the rest of the application codebase to the container workspace
COPY . .

# Explicitly create necessary runtime folders and adjust ownership permissions
RUN mkdir -p uploads app/static/samples && \
    chown -R appuser:appgroup /workspace

# Switch user context to the non-privileged system account
USER appuser

# Expose default application port
EXPOSE 8000

# Set default host and port environment variables for the main.py startup script
ENV HOST=0.0.0.0
ENV PORT=8000
ENV RELOAD=False

# Configure a lightweight, zero-dependency python health check targeting the login portal
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/login', timeout=5)"

# Entry point launcher running the application startup script
CMD ["python", "main.py"]
