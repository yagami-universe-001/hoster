# Yagami Bot Manager - Dockerfile
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Create necessary directories
RUN mkdir -p deployed_bots logs

# Make scripts executable
RUN chmod +x main.py

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Run the bot
CMD ["python3", "main.py"]
