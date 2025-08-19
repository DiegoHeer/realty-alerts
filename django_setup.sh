#!/bin/bash

echo "# Run Django migrations"
python manage.py migrate --noinput

echo "# Collect Django static files"
python manage.py tailwind build
python manage.py collectstatic --noinput --ignore css/source.css

echo "Start Django application..."
exec "$@"
