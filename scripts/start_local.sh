#!/bin/bash

# Run migrations
python3 ./scripts/migrate_up.py

# Start Celery worker with proper error handling
python3 -m celery -A nad_ch.infrastructure.task_queue worker --loglevel=INFO &
CELERY_PID=$!

# Start Flask app
python3 ./nad_ch/main.py serve_flask_app

# Wait for Celery worker to finish (if it exits)
wait $CELERY_PID