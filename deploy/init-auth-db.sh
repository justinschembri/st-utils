#!/bin/sh
# the PostgreSQL database spun up by the docker-compose requires a first time 
# initialization of a USERS and USER_ROLES table required for basic authorization.

export POSTGRES_USER=$(awk -F'"' '/"postgres_user"/ {print $4}' /run/secrets/postgres_credentials)
export POSTGRES_PASSWORD=$(awk -F'"' '/"postgres_password"/ {print $4}' /run/secrets/postgres_credentials)
export FROST_USERNAME=$(awk -F'"' '/"frost_username"/ {print $4}' /run/secrets/frost_credentials)
export FROST_PASSWORD=$(awk -F'"' '/"frost_password"/ {print $4}' /run/secrets/frost_credentials)
echo $FROST_USERNAME
echo $FROST_PASSWORD

set -e
# this is the default entry point for the image
/usr/local/bin/docker-entrypoint.sh postgres &
# brief wait untill PG is ready:
until pg_isready -h database -U ${POSTGRES_USER} -d sensorthings; do
    echo "Waiting for PostgreSQL to be ready"
    sleep 10
done
# first auth attempt triggers FROST to create the Basic Auth tables:
wget --header="Authorization: Basic $(echo -n 'username:password' | base64)" -O Datastreams.json http://web:8080/FROST-Server/v1.1/Datastreams
# change admin, write and read passwords:
psql -U ${POSTGRES_USER} -d sensorthings <<EOF

-- Update password for existing users
UPDATE "USERS"
SET "USER_PASS" = '${FROST_PASSWORD}'
WHERE "USER_NAME" IN ('admin', 'write', 'read');

UPDATE "USERS"
SET "USER_NAME" = '${FROST_USERNAME}'
WHERE "USER_NAME" = 'admin';

UPDATE "USER_ROLES"
SET "USER_NAME" = '${FROST_PASSWORD}'
WHERE "USER_NAME" = 'admin';

EOF

echo "Database initialization complete."
wait $!
