# Use a slim Python base image
FROM python:3.11-slim

# Set working directory inside the container
WORKDIR /app

# Copy your bot code into the container
COPY liza_bot/ ./liza_bot/

# Optionally copy requirements if you have them
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Set environment variables (optional but recommended)
ENV PYTHONUNBUFFERED=1

# Run your bot (adjust the entry point as needed)
CMD ["python", "liza_bot/main.py"]
