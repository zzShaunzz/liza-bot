# Use a lightweight Python base image
FROM python:3.11-slim

# Set working directory inside the container
WORKDIR /app

# Copy all contents of liza_bot/ into the container
COPY . .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Optional: set environment variables
ENV PYTHONUNBUFFERED=1

# Run your bot
CMD ["python", "main.py"]
