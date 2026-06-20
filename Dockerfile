FROM python:3.12-slim

WORKDIR /app

# Install dependencies from the pinned lock for reproducible builds.
# requirements.txt keeps loose ranges for dev; requirements.lock is the source of truth here.
COPY requirements.txt requirements.lock ./
RUN pip install --no-cache-dir -r requirements.lock

# Copy application code
COPY backend/ backend/
COPY frontend/ frontend/
COPY alembic/ alembic/
COPY alembic.ini .
COPY bot.py .
COPY main.py .

# Create uploads directory
RUN mkdir -p /data uploads/photos

EXPOSE 8000

# Run DB migrations to completion, THEN exec the API server (PID 1 -> clean signals).
# The Telegram bot runs as a separate service (see docker-compose.yml), not backgrounded here.
CMD ["sh", "-c", "python -m alembic upgrade head && exec gunicorn backend.app:app --worker-class uvicorn.workers.UvicornWorker --workers 1 --bind 0.0.0.0:8000 --timeout 120 --access-logfile -"]
