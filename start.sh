#!/bin/bash

# Run migrations
echo "Running migrations..."
python manage.py migrate --noinput

# Collect static files
echo "Collecting static files..."
python manage.py collectstatic --noinput

# Start Gunicorn (Binding to $PORT which Render/Railway provide)
echo "Starting server on port ${PORT:-8000}..."
gunicorn --bind 0.0.0.0:${PORT:-8000} forgery_project.wsgi:application
