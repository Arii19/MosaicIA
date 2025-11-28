FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies (inclui libmupdf-dev para PyMuPDF)
RUN apt-get update -y && \
    apt-get install -y build-essential curl git libmupdf-dev && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose port for Render
EXPOSE 8080

# Health check
HEALTHCHECK CMD curl --fail http://localhost:8080/api/health || exit 1

# Run the application
ENTRYPOINT ["uvicorn", "app:app", "--host=0.0.0.0", "--port=8080"]