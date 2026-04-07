#!/bin/bash

# Run migrations
python3 ./scripts/migrate_up.py

python3 -m celery -A nad_ch.infrastructure.task_queue worker --loglevel=INFO & python3 ./nad_ch/main.py serve_flask_app
