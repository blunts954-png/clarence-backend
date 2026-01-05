# Start with Python 3.9
FROM python:3.9-slim

# Install Chromium and dependencies (The "Muscle")
RUN apt-get update && apt-get install -y \
    chromium \
    chromium-driver \
    wget \
    --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# Set up work directory
WORKDIR /app

# Copy files
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the app
COPY . .

# Environment variables for Chrome (Crucial for Render)
ENV CHROME_BIN=/usr/bin/chromium
ENV CHROMEDRIVER_PATH=/usr/bin/chromedriver

# Command to run the API
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "10000"]