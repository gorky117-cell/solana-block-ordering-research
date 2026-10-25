FROM python:3.11-slim

LABEL maintainer="Gaurav <gauravatwork117@gmail.com>"
LABEL description="Solana Validator Transaction Ordering Empirical Research Suite"

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency specifications
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code and datasets
COPY src/ ./src/
COPY data/ ./data/
COPY tests/ ./tests/
COPY Makefile .

# Set default execution to dry-run mode for safety
ENTRYPOINT ["python", "-m", "src.cli"]
CMD ["--benchmark-all", "--generate-report"]
