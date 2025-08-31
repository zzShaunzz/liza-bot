# Use official Python image
FROM python:3.11-slim

# Optional: Install Rust if you're using maturin or Rust-based dependencies
RUN apt-get update && apt-get install -y curl build-essential
RUN curl https://sh.rustup.rs -sSf | sh -s -- -y
ENV PATH="/root/.cargo/bin:${PATH}"

# Set working directory
WORKDIR /app

# Copy bot code and dependencies
COPY bot/ .

# Install Python dependencies
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# Optional: Build Rust extensions if needed
# RUN maturin develop  # Uncomment if you're using maturin

# Start the bot
CMD ["python", "main.py"]
