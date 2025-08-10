#!/bin/bash

echo "# Run Django migrations"
python manage.py migrate --noinput

echo "# Collect Django static files"
python manage.py collectstatic --noinput

echo "Start Django application..."
exec "$@"
