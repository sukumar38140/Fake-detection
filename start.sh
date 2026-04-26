#!/bin/bash

# Run migrations
echo "Running migrations..."
python manage.py migrate --noinput

# Collect static files
echo "Collecting static files..."
python manage.py collectstatic --noinput

# Start Gunicorn
echo "Starting server..."
gunicorn --bind 0.0.0.0:8000 forgery_project.wsgi:application
