FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn

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

# Run migrations, start bot in background, then start API server
CMD ["sh", "-c", "python -m alembic upgrade head && python bot.py & gunicorn backend.app:app --worker-class uvicorn.workers.UvicornWorker --workers 1 --bind 0.0.0.0:8000 --timeout 120 --access-logfile -"]
