FROM python:3.11-slim

WORKDIR /app

# Copy bot code
COPY liza_bot/ ./liza_bot/

# Copy requirements if present
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Run the bot
CMD ["python", "liza_bot/main.py"]
