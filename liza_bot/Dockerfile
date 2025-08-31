# Use a lightweight Python base image
FROM python:3.11-slim

# Optional: install Rust if you're using maturin or Rust-based dependencies
RUN apt-get update && apt-get install -y curl build-essential
RUN curl https://sh.rustup.rs -sSf | sh -s -- -y
ENV PATH="/root/.cargo/bin:${PATH}"

# Set working directory inside the container
WORKDIR /app

# Copy your bot code from the liza_bot folder
COPY liza_bot/ .

# Install Python dependencies
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# Start your bot
CMD ["python", "main.py"]
