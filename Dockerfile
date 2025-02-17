# Use lightweight Python image
FROM python:3.9-slim

# Set working directory inside the container
WORKDIR /app

# Install necessary dependencies (if any)
RUN apt-get update && apt-get install -y unzip && rm -rf /var/lib/apt/lists/*

# Clone your forked repo (replace with your forked repo URL)
RUN apt-get update && apt-get install -y git && \
    git clone https://github.com/rickardliljeberg/chat-export.git /app/chat-export && \
    rm -rf /var/lib/apt/lists/*

# Set entrypoint to run the script
ENTRYPOINT ["python3", "/app/chat-export/main.py"]
