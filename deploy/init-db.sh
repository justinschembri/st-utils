#!/bin/sh
set -e
# Load credentials from JSON
export POSTGRES_USER=$(awk -F'"' '/"postgres_user"/ {print $4}' /run/secrets/postgres_credentials)
export POSTGRES_PASSWORD=$(awk -F'"' '/"postgres_password"/ {print $4}' /run/secrets/postgres_credentials)

set -e
# this is the default entry point for the image
/usr/local/bin/docker-entrypoint.sh postgres &
# brief wait untill PG is ready:
until pg_isready -h database -U $POSTGRES_USER -d sensorthings; do
    echo "Waiting for PostgreSQL to be ready"
    sleep 10
done

echo "Database initialization complete."

wait $!
