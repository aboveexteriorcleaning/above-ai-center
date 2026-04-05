FROM python:3.11-slim

WORKDIR /app

# Install system deps for psycopg2
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy tools/ directory intact (query_engine imports from here)
COPY tools/ ./tools/

# Copy API directory
COPY api/ ./api/

# Install Python dependencies
RUN pip install --no-cache-dir -r api/requirements.txt

# Copy .env if present (Railway injects env vars directly, but useful for local Docker)
COPY .env* ./

EXPOSE 8000

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
