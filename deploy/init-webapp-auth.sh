#!/bin/sh
set -e

# Set up FROST persistence credentials (from init-frost.sh)
export persistence_db_username=$(awk -F'"' '/"postgres_user"/ {print $4}' /run/secrets/postgres_credentials)
export persistence_db_password=$(awk -F'"' '/"postgres_password"/ {print $4}' /run/secrets/postgres_credentials)

# Set up FROST auth credentials if frost_credentials secret exists (from init-auth-frost.sh)
if [ -f "/run/secrets/frost_credentials" ]; then
    export auth_db_username=$(awk -F'"' '/"frost_username"/ {print $4}' /run/secrets/frost_credentials)
    export auth_db_password=$(awk -F'"' '/"frost_password"/ {print $4}' /run/secrets/frost_credentials)
fi

# tomcat-users.xml is mounted directly from secrets, no generation needed

# Start Tomcat
exec /usr/local/tomcat/bin/catalina.sh run
