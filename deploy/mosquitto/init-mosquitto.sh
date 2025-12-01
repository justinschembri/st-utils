#!/bin/sh
set -e

PASSWORD_FILE=/mosquitto/config/passwords.txt
rm -f "$PASSWORD_FILE"

# Check if the secret file exists
SECRET_FILE=/run/secrets/MQTT_USERS
if [ -f "$SECRET_FILE" ]; then
    echo "Generating Mosquitto users from secret..."
    while IFS='=' read -r username password; do
        # Skip empty lines
        [ -z "$username" ] && continue
        mosquitto_passwd -b -c "$PASSWORD_FILE" "$username" "$password"
    done < "$SECRET_FILE"
else
    echo "No MQTT users secret found at $SECRET_FILE"
fi

chown mosquitto:mosquitto "$PASSWORD_FILE"

echo "Starting Mosquitto..."
exec mosquitto -c /mosquitto/config/mosquitto.conf
